"""ANV-021: durable opt-in, isolation, cancellation, migration and fallback."""

import asyncio
import hashlib
import json
import sqlite3

import httpx
import pytest
from fastapi.testclient import TestClient

from anvesha.api import create_app
from anvesha.cli import DEMO_DOCUMENTS, diagnostics, main
from anvesha.config import Settings
from anvesha.llm import LLMConfig, LLMReranker
from anvesha.store import _SCHEMA, PIPELINE_VERSION, Store
from anvesha.worker import process_one

KEY = "private-research-" + "a" * 32


@pytest.fixture
def research(tmp_path):
    model = LLMConfig(model="local-test", api_key="llm-private-key")
    settings = Settings(database_path=tmp_path / "research.db", api_keys=(KEY,), llm=model)
    app = create_app(settings)
    with TestClient(app, headers={"X-API-Key": KEY}) as client:
        for document in DEMO_DOCUMENTS:
            app.state.store.upsert_document(document)
        yield client, app.state.store, settings


def reverse_candidates(request):
    body = json.loads(request.content)
    candidates = json.loads(body["messages"][1]["content"])["candidates"]
    return httpx.Response(
        200,
        json={
            "choices": [
                {
                    "finish_reason": "stop",
                    "message": {
                        "role": "assistant",
                        "content": json.dumps(
                            {"ranked_ids": [item["id"] for item in reversed(candidates)]}
                        ),
                    },
                }
            ]
        },
    )


def test_explicit_opt_in_is_durable_reranks_before_truncation_and_versions_feedback(research):
    client, store, settings = research
    lexical = client.post(
        "/v1/searches", json={"query": "Anvesha", "limit": 3, "ranking": "lexical"}
    ).json()
    process_one(store)
    old = client.get(lexical["results_url"]).json()["results"]
    headers = {"Idempotency-Key": "llm-query"}
    body = {"query": "Anvesha", "ranking": "llm", "limit": 1}
    response = client.post("/v1/searches", json=body, headers=headers)
    job = response.json()
    assert response.status_code == 202 and job["ranking"] == "llm"
    assert job["pipeline_version"] == settings.llm.pipeline_version
    assert client.post("/v1/searches", json=body, headers=headers).json()["id"] == job["id"]
    assert (
        client.post(
            "/v1/searches", json={**body, "ranking": "lexical"}, headers=headers
        ).status_code
        == 409
    )
    restarted = Store(store.path)
    restarted.initialize()
    reranker = LLMReranker(settings.llm, transport=httpx.MockTransport(reverse_candidates))
    process_one(restarted, reranker=reranker)
    results = client.get(job["results_url"]).json()
    assert results["ranking"] == "llm"
    assert results["results"][0]["id"] == old[-1]["id"]
    assert results["results"][0]["ranking_method"] == "llm_rerank"
    assert results["results"][0]["provenance"] == old[-1]["provenance"]
    feedback = client.post(f"/v1/searches/{job['id']}/feedback", json={"version": 1, "rating": 1})
    assert feedback.json()["pipeline_version"] == settings.llm.pipeline_version
    assert feedback.json()["learning_opt_in"] is False
    assert client.get(job["results_url"], headers={"X-API-Key": "wrong"}).status_code == 401
    assert client.get(job["results_url"]).json() == results
    assert "llm-private-key" not in json.dumps(results)


@pytest.mark.parametrize("failure", ["missing", "changed", "invalid", "http"])
def test_optional_stage_failure_publishes_lexical_with_visible_warning(research, failure):
    client, store, settings = research
    job = client.post("/v1/searches", json={"query": "Anvesha", "ranking": "llm"}).json()
    calls = []

    def respond(request):
        calls.append(request)
        return (
            httpx.Response(500, text="private upstream body")
            if failure == "http"
            else httpx.Response(200, json={})
        )

    config = LLMConfig(model="different") if failure == "changed" else settings.llm
    ranker = (
        None
        if failure == "missing"
        else LLMReranker(config, transport=httpx.MockTransport(respond))
    )
    process_one(store, reranker=ranker)
    status = client.get(f"/v1/searches/{job['id']}").json()
    expected = {
        "missing": "not_configured",
        "changed": "configuration_changed",
        "invalid": "invalid_response",
        "http": "http_error",
    }
    assert status["state"] == "completed_partial"
    assert status["warnings"] == ["llm:" + expected[failure]] + (
        ["llm_contract:invalid_envelope"] if failure == "invalid" else []
    )
    assert len(calls) == (0 if failure in {"missing", "changed"} else 1)
    results = client.get(job["results_url"]).json()["results"]
    assert len(results) == 3 and all("ranking_method" not in item for item in results)


def test_explicit_lexical_mode_does_not_call_model_and_capabilities_exclude_secrets(research):
    client, store, settings = research

    def forbidden(request):
        pytest.fail("Lexical requests must not send data to an LLM")

    job = client.post("/v1/searches", json={"query": "Anvesha", "ranking": "lexical"}).json()
    process_one(store, reranker=LLMReranker(settings.llm, transport=httpx.MockTransport(forbidden)))
    assert client.get(f"/v1/searches/{job['id']}").json()["state"] == "completed"
    assert job["pipeline_version"] == PIPELINE_VERSION
    capabilities = client.get("/v1/capabilities")
    assert capabilities.json()["ranking_modes"] == ["llm", "lexical"]
    assert "llm-private-key" not in capabilities.text and "11434" not in capabilities.text
    assert client.get("/v1/capabilities", headers={"X-API-Key": "wrong"}).status_code == 401


def test_unconfigured_model_rejected_and_enabled_metadata_source_accepted(tmp_path):
    settings = Settings(database_path=tmp_path / "db", api_keys=(KEY,))
    with TestClient(create_app(settings), headers={"X-API-Key": KEY}) as client:
        assert (
            client.post("/v1/searches", json={"query": "x", "ranking": "llm"}).json()["detail"]
            == "llm_not_configured"
        )
    enabled = Settings(
        database_path=tmp_path / "other",
        api_keys=(KEY,),
        enabled_sources=("local", "wikidata"),
        llm=LLMConfig(model="test"),
    )
    with TestClient(create_app(enabled), headers={"X-API-Key": KEY}) as client:
        response = client.post(
            "/v1/searches", json={"query": "x", "ranking": "llm", "sources": ["wikidata"]}
        )
        assert response.status_code == 202 and response.json()["sources"] == ["wikidata"]


@pytest.mark.parametrize("action", ["cancel", "delete"])
def test_interrupted_model_work_cannot_publish(research, action):
    client, store, settings = research
    job = client.post("/v1/searches", json={"query": "Anvesha", "ranking": "llm"}).json()

    async def respond(request):
        if action == "cancel":
            store.cancel_job(hashlib.sha256(KEY.encode()).hexdigest(), job["id"])
        else:
            store.delete_job(hashlib.sha256(KEY.encode()).hexdigest(), job["id"])
        await asyncio.sleep(0.3)
        return reverse_candidates(request)

    process_one(store, reranker=LLMReranker(settings.llm, transport=httpx.MockTransport(respond)))
    response = client.get(f"/v1/searches/{job['id']}")
    if action == "cancel":
        assert response.json()["state"] == "cancelled" and response.json()["results_version"] == 0
    else:
        assert response.status_code == 404


def test_lease_is_renewed_while_waiting_for_a_local_model(research):
    client, store, settings = research
    job = client.post("/v1/searches", json={"query": "Anvesha", "ranking": "llm"}).json()

    async def respond(request):
        await asyncio.sleep(1.25)
        return reverse_candidates(request)

    process_one(
        store,
        lease_seconds=1,
        reranker=LLMReranker(settings.llm, transport=httpx.MockTransport(respond)),
    )
    assert client.get(f"/v1/searches/{job['id']}").json()["state"] == "completed"


def test_legacy_database_migrates_without_losing_idempotency_snapshots_or_feedback(tmp_path):
    path = tmp_path / "legacy.db"
    with sqlite3.connect(path) as db:
        db.executescript(_SCHEMA.replace("    ranking TEXT NOT NULL DEFAULT 'lexical',\n", ""))
        request_hash = hashlib.sha256(
            json.dumps(["query", ["local"], 10], sort_keys=True).encode()
        ).hexdigest()
        db.execute(
            """INSERT INTO jobs
               (id, owner, query, sources_json, result_limit, request_hash,
                idempotency_key, state, phase, pipeline_version, created_at, updated_at)
               VALUES ('old', 'owner', 'query', '["local"]', 10, ?,
                       'legacy-key', 'queued', 'queued', ?, 1, 1)""",
            (request_hash, PIPELINE_VERSION),
        )
    store = Store(path)
    claimed = store.claim_job("old-worker")
    assert store.finish_job("old", claimed["lease_token"], [{"id": "old-result"}])
    store.submit_feedback("owner", "old", version=1, result_id=None, rating=1)
    store.initialize()
    store.initialize()
    replay, created = store.create_search("owner", "query", ["local"], idempotency_key="legacy-key")
    assert not created and replay["id"] == "old" and replay["ranking"] == "lexical"
    assert store.get_results("owner", "old")["results"] == [{"id": "old-result"}]
    with sqlite3.connect(path) as db:
        assert db.execute("SELECT pipeline_version FROM feedback").fetchone()[0] == PIPELINE_VERSION


def test_doctor_is_offline_does_not_create_database_or_print_secrets(tmp_path, monkeypatch, capsys):
    path = tmp_path / "missing.db"
    monkeypatch.setenv("ANVESHA_API_KEYS", KEY)
    monkeypatch.setenv("ANVESHA_LLM_MODEL", "test")
    monkeypatch.setenv("ANVESHA_LLM_API_KEY", "llm-private-key")
    assert main(["--db", str(path), "doctor"]) == 1
    text = capsys.readouterr().out
    assert "llm-private-key" not in text and KEY not in text
    assert not path.exists() and json.loads(text)["network_checks_performed"] is False
    store = Store(path)
    store.initialize()
    before = path.read_bytes()
    assert diagnostics(Settings(database_path=path, api_keys=(KEY,)))["ready"] is True
    assert path.read_bytes() == before


def test_serve_preserves_model_config_and_disables_access_logging(tmp_path, monkeypatch):
    import uvicorn

    called = []
    monkeypatch.setenv("ANVESHA_API_KEYS", KEY)
    monkeypatch.setenv("ANVESHA_LLM_MODEL", "local-test")
    monkeypatch.setattr(uvicorn, "run", lambda app, **kwargs: called.append((app, kwargs)))
    assert main(["--db", str(tmp_path / "override.db"), "serve"]) == 0
    app, options = called[0]
    with TestClient(app, headers={"X-API-Key": KEY}) as client:
        assert client.get("/v1/capabilities").json()["ranking_modes"] == ["llm", "lexical"]
    assert options["access_log"] is False
