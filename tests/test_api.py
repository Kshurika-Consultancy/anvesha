"""ANV-004/ANV-006: observable API semantics and cross-client boundaries."""

import pytest
from fastapi.testclient import TestClient

from anvesha.api import create_app
from anvesha.cli import DEMO_DOCUMENTS
from anvesha.config import Settings
from anvesha.store import Store
from anvesha.worker import process_one

KEY_A = "client-a-" + "a" * 32
KEY_B = "client-b-" + "b" * 32


@pytest.fixture
def api(tmp_path):
    settings = Settings(database_path=tmp_path / "test.db", api_keys=(KEY_A, KEY_B))
    app = create_app(settings)
    with TestClient(app, headers={"X-API-Key": KEY_A}) as client:
        for document in DEMO_DOCUMENTS:
            app.state.store.upsert_document(document)
        yield client, app.state.store, settings


def submit(client, **body):
    return client.post("/v1/searches", json={"query": "Anvesha", "ranking": "lexical", **body})


def test_offline_lifecycle_snapshot_feedback_delete(api):
    client, store, _ = api
    response = submit(client)
    assert response.status_code == 202
    job = response.json()
    assert job["state"] == "queued"
    assert response.headers["location"].endswith(job["id"])
    assert client.get(job["results_url"]).status_code == 409
    assert process_one(store)
    status = client.get(response.headers["location"]).json()
    assert status["state"] == "completed"
    assert status["results_version"] == 1
    assert status["pipeline_version"] == "m1-rrf-v1"
    assert "owner" not in status and "lease_token" not in status
    results = client.get(job["results_url"], params={"version": 1, "limit": 1}).json()
    assert results["pipeline_version"] == "m1-rrf-v1"
    assert results["total"] == 3 and results["next_offset"] == 1
    result = results["results"][0]
    assert result["evidence_status"] == "local_document"
    assert "demonstration" in result["title"]
    assert result["provenance"][0]["license"] == "Apache-2.0"
    body = {"version": 1, "result_id": result["id"], "rating": 1}
    feedback_url = f"/v1/searches/{job['id']}/feedback"
    first = client.post(feedback_url, json=body).json()
    assert first["learning_opt_in"] is False
    assert "owner" not in first
    second = client.post(feedback_url, json={**body, "rating": -1}).json()
    assert first["id"] == second["id"] and second["rating"] == -1
    assert client.delete(f"/v1/searches/{job['id']}").status_code == 204
    assert client.get(job["results_url"]).status_code == 404


def test_idempotency_and_conflicting_reuse(api):
    client, _, _ = api
    headers = {"Idempotency-Key": "one-request"}
    body = {"query": "search", "ranking": "lexical"}
    first = client.post("/v1/searches", headers=headers, json=body)
    second = client.post("/v1/searches", headers=headers, json=body)
    assert first.status_code == 202 and second.status_code == 200
    assert first.json()["id"] == second.json()["id"]
    assert second.headers["idempotency-replayed"] == "true"
    assert (
        client.post("/v1/searches", headers=headers, json={**body, "query": "other"}).status_code
        == 409
    )


@pytest.mark.parametrize("key", ["", "wrong-key"])
def test_authentication_required(api, key):
    client, _, _ = api
    assert (
        client.post("/v1/searches", headers={"X-API-Key": key}, json={"query": "x"}).status_code
        == 401
    )
    assert client.get("/healthz", headers={"X-API-Key": key}).status_code == 200


def test_cross_client_isolation_on_all_routes(api):
    client, store, _ = api
    job = submit(client).json()
    process_one(store)
    base = f"/v1/searches/{job['id']}"
    headers = {"X-API-Key": KEY_B}
    assert client.get(base, headers=headers).status_code == 404
    assert client.get(base + "/results", headers=headers).status_code == 404
    assert client.post(base + "/cancel", headers=headers).status_code == 404
    assert (
        client.post(
            base + "/feedback", headers=headers, json={"version": 1, "rating": 1}
        ).status_code
        == 404
    )
    assert client.delete(base, headers=headers).status_code == 404
    assert client.get(base).json()["state"] == "completed"


@pytest.mark.parametrize(
    "body",
    [
        {"query": "   "},
        {"query": "x" * 2001},
        {"query": "x", "limit": 0},
        {"query": "x", "limit": True},
        {"query": "x", "limit": 51},
        {"query": "x", "sources": []},
        {"query": "x", "sources": ["wikidata"]},
        {"query": "x", "sources": ["arbitrary-http"]},
        {"query": "x", "unknown": True},
    ],
)
def test_input_validation_and_no_silent_paid_or_unconfigured_source(api, body):
    client, _, _ = api
    assert client.post("/v1/searches", json={"ranking": "lexical", **body}).status_code == 422


def test_blank_idempotency_key_is_validation_error(api):
    client, _, _ = api
    response = client.post(
        "/v1/searches",
        headers={"Idempotency-Key": "   "},
        json={"query": "x", "ranking": "lexical"},
    )
    assert response.status_code == 422


def test_cancel_before_worker_and_conditional_polling(api):
    client, store, _ = api
    job = submit(client).json()
    path = f"/v1/searches/{job['id']}"
    first = client.get(path)
    assert client.get(path, headers={"If-None-Match": first.headers["etag"]}).status_code == 304
    assert client.post(path + "/cancel").json()["state"] == "cancelled"
    assert not process_one(store)
    assert client.get(path, headers={"If-None-Match": first.headers["etag"]}).status_code == 200


def test_feedback_rejects_unknown_snapshot_and_result_and_strict_consent(api):
    client, store, _ = api
    job = submit(client).json()
    path = f"/v1/searches/{job['id']}/feedback"
    assert client.post(path, json={"version": 1, "rating": 1}).status_code == 409
    process_one(store)
    for body in [{"version": 2, "rating": 1}, {"version": 1, "rating": 1, "result_id": "invented"}]:
        assert client.post(path, json=body).status_code == 409
    for body in [
        {"version": 1, "rating": True},
        {"version": 1, "rating": 0},
        {"version": 1, "rating": 1, "learning_opt_in": "true"},
    ]:
        assert client.post(path, json=body).status_code == 422


def test_results_are_stable_across_pagination_and_api_restart(api):
    client, _, settings = api
    job = submit(client).json()
    # A separately instantiated worker/store observes the committed HTTP job.
    assert process_one(Store(settings.database_path))
    whole = client.get(job["results_url"]).json()
    with TestClient(create_app(settings), headers={"X-API-Key": KEY_A}) as restarted:
        pages = [
            restarted.get(
                job["results_url"], params={"version": 1, "offset": n, "limit": 1}
            ).json()["results"][0]
            for n in range(3)
        ]
        assert pages == whole["results"]
        assert restarted.get(job["results_url"], params={"version": 2}).status_code == 409


def test_empty_success_is_not_failed(api):
    client, store, _ = api
    job = submit(client, query="unfindabletokenthatdoesnotexist").json()
    process_one(store)
    assert client.get(f"/v1/searches/{job['id']}").json()["state"] == "completed"
    assert client.get(job["results_url"]).json()["results"] == []


def test_startup_refuses_no_auth_keys(tmp_path):
    with pytest.raises(RuntimeError, match="ANVESHA_API_KEYS"):
        with TestClient(create_app(Settings(database_path=tmp_path / "test.db"))):
            pass
