"""ANV-028: fixed-endpoint discovery, no prose copying and durable throttling."""

import hashlib
import json
import sqlite3
from concurrent.futures import ThreadPoolExecutor
from contextlib import closing
from dataclasses import replace
from email.utils import formatdate

import httpx
import pytest
from fastapi.testclient import TestClient

from anvesha import providers
from anvesha.api import create_app
from anvesha.cli import DEMO_DOCUMENTS, diagnostics, main
from anvesha.config import Settings
from anvesha.llm import LLMConfig, LLMReranker
from anvesha.ranking import rank_candidates
from anvesha.runtime import load_settings
from anvesha.store import Store
from anvesha.worker import process_one

IDENTITY = "AnveshaBot/0.1 (https://example.test/operator)"
KEY = "synthetic-client-key-" + "x" * 32


def entry(**changes):
    return {
        "ns": 0,
        "pageid": 123,
        "title": "Synthetic article",
        "wordcount": 42,
        "timestamp": "2026-10-20T01:02:03Z",
        **changes,
    }


def response(rows=None, **kwargs):
    return httpx.Response(
        200,
        headers={"Content-Type": "application/json"},
        stream=httpx.ByteStream(json.dumps({"query": {"search": rows or []}, **kwargs}).encode()),
    )


def retrieve(rows=None, handler=None, **kwargs):
    with httpx.Client(
        transport=httpx.MockTransport(handler or (lambda _: response(rows)))
    ) as client:
        return providers.search_wikipedia(
            "synthetic query", client=client, user_agent=IDENTITY, **kwargs
        )


@pytest.fixture
def store(tmp_path):
    result = Store(tmp_path / "synthetic.db")
    result.initialize()
    result.upsert_document(DEMO_DOCUMENTS[0])
    return result


def test_fixed_endpoint_preserves_query_and_requests_no_prose(monkeypatch):
    seen = []
    monkeypatch.setenv("ANVESHA_WIKIPEDIA_USER_AGENT", IDENTITY)

    def handle(request):
        seen.append(request)
        return response([entry(snippet="UNAPPROVED prose", fullurl="http://127.0.0.1/secret")])

    with httpx.Client(transport=httpx.MockTransport(handle)) as client:
        rows = providers.search_wikipedia('"SQLite WAL" -android', client=client)
        assert not client.is_closed
    assert len(seen) == 1
    req = seen[0]
    assert str(req.url).startswith(providers.WIKIPEDIA_ENDPOINT + "?")
    assert req.url.params["srsearch"] == '"SQLite WAL" -android'
    assert req.url.params["srnamespace"] == "0"
    assert req.url.params["srprop"] == "timestamp|wordcount"
    assert req.url.params["maxlag"] == "5"
    assert req.headers["User-Agent"] == IDENTITY
    assert req.headers["Accept-Encoding"] == "identity"
    assert rows[0]["url"] == "https://en.wikipedia.org/?curid=123"
    assert "UNAPPROVED" not in json.dumps(rows) and "127.0.0.1" not in json.dumps(rows)
    assert rows[0]["evidence_status"] == "metadata_only"
    assert rows[0]["source_modified_at"] == "2026-10-20T01:02:03Z"
    assert (
        rows[0]["observed_at"] > 0
        and rows[0]["rights_manifest_version"] == "wikipedia-discovery-v1"
    )


@pytest.mark.parametrize(
    "changes",
    [
        {"pageid": True},
        {"pageid": "123"},
        {"pageid": -1},
        {"pageid": 2**63},
        {"ns": 1},
        {"ns": False},
        {"title": ""},
        {"title": "x\nsecret"},
        {"title": "x" * 501},
        {"wordcount": True},
        {"wordcount": -1},
        {"timestamp": "2026-02-30T00:00:00Z"},
        {"timestamp": "2026-10-20"},
        {"timestamp": []},
    ],
)
def test_bad_metadata_fails_closed(changes):
    with pytest.raises(providers.ProviderError, match="^invalid_response$"):
        retrieve([entry(**changes)])


def test_duplicates_and_excess_results_fail_closed():
    for rows, limit in [([entry(), entry()], 20), ([entry(), entry(pageid=124)], 1)]:
        with pytest.raises(providers.ProviderError, match="invalid_response"):
            retrieve(rows, limit=limit)


def test_empty_success_and_untrusted_title_never_becomes_url():
    assert retrieve() == []
    rows = retrieve([entry(title="<img src=x onerror=alert(1)>")])
    assert rows[0]["title"].startswith("<img")
    assert rows[0]["url"] == "https://en.wikipedia.org/?curid=123"


@pytest.mark.parametrize(
    "payload", [[], {}, {"query": []}, {"query": {"search": None}}, {"query": {"search": [None]}}]
)
def test_missing_or_malformed_result_structure(payload):
    def handle(_):
        return httpx.Response(
            200,
            headers={"Content-Type": "application/json"},
            stream=httpx.ByteStream(json.dumps(payload).encode()),
        )

    with pytest.raises(providers.ProviderError, match="^invalid_response$"):
        retrieve(handler=handle)


@pytest.mark.parametrize(
    ("headers", "body", "code"),
    [
        ({"Content-Type": "text/html"}, b"not JSON", "invalid_response"),
        (
            {"Content-Type": "application/json", "Content-Encoding": "gzip"},
            b"",
            "unexpected_encoding",
        ),
        (
            {"Content-Type": "application/json", "Content-Length": "1048577"},
            b"",
            "response_too_large",
        ),
        ({"Content-Type": "application/json"}, b"bad JSON", "invalid_response"),
    ],
)
def test_transport_rejects_unbounded_or_unapproved_content(headers, body, code):
    with pytest.raises(providers.ProviderError, match=f"^{code}$"):
        retrieve(
            handler=lambda _: httpx.Response(200, headers=headers, stream=httpx.ByteStream(body))
        )


@pytest.mark.parametrize(("query", "limit"), [("", 20), ("x" * 2001, 20), ("x", True), ("x", 51)])
def test_bad_input_never_opens_transport(query, limit):
    with pytest.raises(providers.ProviderError):
        providers.search_wikipedia(query, limit, user_agent=IDENTITY)


def test_missing_identity_and_redirect_never_leak_queries(monkeypatch):
    monkeypatch.delenv("ANVESHA_WIKIPEDIA_USER_AGENT", raising=False)
    with pytest.raises(providers.ProviderError, match="^missing_user_agent$"):
        providers.search_wikipedia("synthetic private query")
    seen = []

    def handle(request):
        seen.append(request)
        return httpx.Response(302, headers={"Location": "http://127.0.0.1/private"})

    with httpx.Client(transport=httpx.MockTransport(handle), follow_redirects=True) as client:
        with pytest.raises(providers.ProviderError, match="^redirect_rejected$"):
            providers.search_wikipedia(
                "synthetic private query", client=client, user_agent=IDENTITY
            )
    assert len(seen) == 1


@pytest.mark.parametrize(
    ("status", "header", "code", "delay"),
    [
        (429, "120", "rate_limited", 120),
        (503, "90", "upstream_http_error", 90),
        (429, "bad-private-header", "rate_limited", 60),
        (429, "0", "rate_limited", 1),
    ],
)
def test_throttling_is_sanitized_and_carries_wait(status, header, code, delay):
    def handle(_):
        return httpx.Response(status, headers={"Retry-After": header})

    with pytest.raises(providers.ProviderError) as problem:
        retrieve(handler=handle)
    assert str(problem.value) == code and problem.value.retry_after_seconds == delay


def test_retry_after_dates_maxlag_and_large_delays(monkeypatch):
    monkeypatch.setattr(providers.time, "time", lambda: 1000.0)
    assert providers._retry_delay(formatdate(1120, usegmt=True)) == 121
    assert providers._retry_delay(" 120 ") == 120
    assert providers._retry_delay("9" * 40) == 2**53
    with pytest.raises(providers.ProviderError) as problem:
        retrieve(handler=lambda _: response(error={"code": "maxlag", "info": "not public"}))
    assert str(problem.value) == "upstream_busy" and problem.value.retry_after_seconds == 5


def test_rights_and_freshness_survive_deduplication_without_relicensing_local_text():
    candidate = retrieve([entry()])[0]
    local = {
        **candidate,
        "source": "local",
        "snippet": "Synthetic permitted local excerpt",
        "license": "Apache-2.0",
        "attribution": "Synthetic local author",
        "evidence_status": "local_document",
        "rights_manifest_version": "local-v1",
    }
    for key in (
        "license_url",
        "attribution_url",
        "source_modified_at",
        "observed_at",
        "content_transformation",
    ):
        local.pop(key)
    result = rank_candidates([candidate, local])[0]
    assert result == rank_candidates([local, candidate])[0]
    assert result["license"] == "Apache-2.0" and "license_url" not in result
    wikipedia = next(p for p in result["provenance"] if p["source"] == "wikipedia")
    assert wikipedia["license"] == "CC-BY-SA-4.0" and wikipedia["source_modified_at"]
    assert wikipedia["license_url"] == candidate["license_url"]


def test_durable_shared_cooldown_is_atomic_and_does_not_extend_on_read(store, monkeypatch):
    clock = [1000.0]
    monkeypatch.setattr("anvesha.store.time.time", lambda: clock[0])
    with ThreadPoolExecutor(max_workers=4) as pool:
        list(pool.map(lambda delay: Store(store.path).pause_wikimedia(delay), [60, 20, 120, 30]))
    assert Store(store.path).wikimedia_paused()
    clock[0] = 1119.0
    assert store.wikimedia_paused()
    clock[0] = 1120.0
    assert not store.wikimedia_paused()
    with closing(sqlite3.connect(store.path)) as db:
        assert db.execute("SELECT until FROM provider_backoff").fetchone()[0] == 1120


def test_throttled_wikipedia_pauses_wikidata_across_worker_restart_but_local_works(store):
    job = store.create_search("client", "Anvesha", ["local", "wikipedia"])[0]
    calls = []

    def throttle(*args, **kwargs):
        calls.append(1)
        raise providers.ProviderError("rate_limited", 120)

    process_one(store, wikipedia_search=throttle)
    assert store.get_job("client", job["id"])["state"] == "completed_partial"
    next_job = store.create_search("client", "Anvesha", ["local", "wikidata"])[0]
    process_one(
        Store(store.path), wikidata_search=lambda *a, **kw: pytest.fail("Cooldown bypassed")
    )
    status = store.get_job("client", next_job["id"])
    assert status["warnings"] == ["wikidata:cooldown_active"] and len(calls) == 1
    assert store.get_results("client", next_job["id"])["total"] == 1


def test_default_source_request_never_selects_live_discovery(store):
    settings = Settings(database_path=store.path, api_keys=(KEY,), llm=LLMConfig(model="fixture"))
    with TestClient(create_app(settings), headers={"X-API-Key": KEY}) as api:
        created = api.post("/v1/searches", json={"query": "Anvesha", "ranking": "lexical"}).json()
        assert created["sources"] == ["local"]
        refused = api.post("/v1/searches", json={"query": "Anvesha", "sources": ["wikipedia"]})
        assert refused.status_code == 422 and refused.json()["detail"] == "source_not_enabled"
    process_one(store, wikipedia_search=lambda *a, **kw: pytest.fail("Unexpected network"))
    assert (
        store.get_job(hashlib.sha256(KEY.encode()).hexdigest(), created["id"])["state"]
        == "completed"
    )


@pytest.mark.parametrize("action", ["cancel", "delete", "expire"])
def test_live_source_return_cannot_publish_after_interruption(store, monkeypatch, action):
    now = [1000.0]
    monkeypatch.setattr("anvesha.store.time.time", lambda: now[0])
    job = store.create_search("client", "Anvesha", ["wikipedia"], retention_seconds=10)[0]
    candidates = retrieve([entry()])

    def discovery(*a, **kw):
        if action == "cancel":
            store.cancel_job("client", job["id"])
        elif action == "delete":
            store.delete_job("client", job["id"])
        else:
            now[0] = 1010.0
        return candidates

    process_one(store, wikipedia_search=discovery)
    if action == "cancel":
        assert store.get_job("client", job["id"])["results_version"] == 0
        with closing(sqlite3.connect(store.path)) as db:
            assert db.execute("SELECT count(*) FROM snapshots").fetchone()[0] == 0
    else:
        assert store.get_results("client", job["id"]) is None
        assert store.get_job("client", job["id"]) is None


def test_empty_discovery_success_differs_from_total_failure(store):
    one = store.create_search("client", "Anvesha", ["wikipedia"])[0]
    process_one(store, wikipedia_search=lambda *a, **kw: [])
    assert store.get_job("client", one["id"])["state"] == "completed"
    assert store.get_results("client", one["id"])["total"] == 0
    two = store.create_search("client", "Anvesha", ["wikipedia"])[0]

    def fail(*a, **kw):
        raise providers.ProviderError("timeout")

    process_one(store, wikipedia_search=fail)
    assert store.get_job("client", two["id"])["error_code"] == "all_sources_failed"


def test_mixed_source_model_failure_preserves_discovery_rights_in_visible_fallback(store):
    config = LLMConfig(model="synthetic-model")
    job = store.create_search(
        "client",
        "Anvesha",
        ["local", "wikipedia"],
        ranking="llm",
        pipeline_version=config.pipeline_version,
    )[0]
    process_one(
        store,
        wikipedia_search=lambda *a, **kw: retrieve([entry()]),
        reranker=LLMReranker(
            config,
            transport=httpx.MockTransport(
                lambda _: httpx.Response(
                    200, json={"choices": [{"message": {"content": "invented"}}]}
                )
            ),
        ),
    )
    status = store.get_job("client", job["id"])
    assert status["state"] == "completed_partial" and "llm:invalid_response" in status["warnings"]
    results = store.get_results("client", job["id"])["results"]
    assert next(x for x in results if x["display_source"] == "wikipedia")["license_url"]


def test_legacy_schema_migrates_without_changing_jobs_and_doctor_never_migrates(store):
    job = store.create_search("client", "Anvesha", ["local"])[0]
    with closing(sqlite3.connect(store.path)) as db:
        db.execute("DROP TABLE provider_backoff")
        db.commit()
    settings = Settings(database_path=store.path, api_keys=(KEY,))
    assert not diagnostics(settings)["ready"]
    with closing(sqlite3.connect(store.path)) as db:
        assert not db.execute(
            "SELECT 1 FROM sqlite_master WHERE name='provider_backoff'"
        ).fetchall()
    store.initialize()
    assert (
        diagnostics(settings)["ready"] and store.get_job("client", job["id"])["state"] == "queued"
    )


def test_saved_configuration_preserves_source_identity_and_legacy_defaults(tmp_path, capsys):
    path = tmp_path / "private.json"
    assert (
        main(
            [
                "--db",
                str(tmp_path / "data.db"),
                "setup",
                "--config",
                str(path),
                "--lexical-only",
                "--sources",
                "local",
                "wikipedia",
                "--wikipedia-user-agent",
                IDENTITY,
            ]
        )
        == 0
    )
    saved = load_settings(path)
    assert (
        saved.enabled_sources == ("local", "wikipedia") and saved.wikipedia_user_agent == IDENTITY
    )
    assert saved.api_keys[0] not in capsys.readouterr().out
    raw = json.loads(path.read_text())
    raw.pop("wikipedia_user_agent")
    raw["enabled_sources"] = ["local"]
    path.write_text(json.dumps(raw), encoding="utf-8")
    assert load_settings(path).wikipedia_user_agent == ""
    with pytest.raises(ValueError):
        replace(saved, wikipedia_user_agent="")


def test_mixed_source_llm_ranking_results_feedback_and_owner_isolation(store):
    settings = Settings(
        database_path=store.path,
        api_keys=(KEY,),
        enabled_sources=("local", "wikipedia"),
        wikipedia_user_agent=IDENTITY,
        llm=LLMConfig(model="synthetic-model"),
    )
    calls = []

    def model(request):
        body = json.loads(request.content)
        calls.append(body)
        data = json.loads(body["messages"][1]["content"])
        ids = [row["id"] for row in data["candidates"]]
        return httpx.Response(
            200,
            json={
                "choices": [
                    {
                        "finish_reason": "stop",
                        "message": {
                            "role": "assistant",
                            "content": json.dumps({"ranked_ids": ids[::-1]}),
                        },
                    }
                ]
            },
        )

    candidates = retrieve([entry()])
    with TestClient(create_app(settings), headers={"X-API-Key": KEY}) as api:
        response = api.post(
            "/v1/searches",
            json={"query": "Anvesha", "sources": ["local", "wikipedia"]},
            headers={"Idempotency-Key": "synthetic-retry"},
        )
        assert response.status_code == 202
        job = response.json()
        caps = api.get("/v1/capabilities").json()
        assert caps["source_privacy"]["wikipedia"] == "query_sent_to_wikimedia"
        process_one(
            store,
            wikipedia_search=lambda *a, **kw: candidates,
            reranker=LLMReranker(settings.llm, transport=httpx.MockTransport(model)),
        )
        results = api.get(f"/v1/searches/{job['id']}/results").json()
        assert len(calls) == 1 and results["total"] == 2
        assert all(row["ranking_method"] == "llm_rerank" for row in results["results"])
        assert "https://en.wikipedia.org" not in json.dumps(calls) and KEY not in json.dumps(calls)
        result = next(row for row in results["results"] if row["display_source"] == "wikipedia")
        assert result["license_url"] and result["provenance"][0]["source_modified_at"]
        receipt = api.post(
            f"/v1/searches/{job['id']}/feedback",
            json={"version": 1, "result_id": result["id"], "rating": 1},
        ).json()
        assert not receipt["learning_opt_in"]
        again = api.post(
            "/v1/searches",
            json={"query": "Anvesha", "sources": ["wikipedia", "local"]},
            headers={"Idempotency-Key": "synthetic-retry"},
        )
        assert again.status_code == 200 and again.json()["id"] == job["id"]
        assert store.get_results("another-client", job["id"]) is None
