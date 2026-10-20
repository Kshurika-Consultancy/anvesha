"""ANV-026: synthetic operational data only; never inspect a real service/review DB."""

import json
import sqlite3
from concurrent.futures import ThreadPoolExecutor
from contextlib import closing
from dataclasses import replace

import pytest
from fastapi.testclient import TestClient

from anvesha.api import create_app
from anvesha.cli import DEMO_DOCUMENTS, diagnostics, main
from anvesha.config import Settings
from anvesha.llm import LLMConfig
from anvesha.retention import CLEANUP_BATCH, DEFAULT_SECONDS, MAX_SECONDS
from anvesha.runtime import load_settings, setup
from anvesha.store import _SCHEMA, FeedbackError, IdempotencyConflict, Store
from anvesha.worker import process_one

KEY = "synthetic-retention-key-" + "a" * 24
OTHER_KEY = "synthetic-other-key-" + "b" * 24


@pytest.fixture
def clock(monkeypatch):
    current = [1000.0]
    monkeypatch.setattr("anvesha.store.time.time", lambda: current[0])
    return current


@pytest.fixture
def store(tmp_path):
    value = Store(tmp_path / "synthetic.db")
    value.initialize()
    return value


def submit(store, **kwargs):
    return store.create_search("alice", "Synthetic retention test", ["local"], **kwargs)[0]


def finish(store, state="completed"):
    claim = store.claim_job("synthetic-worker", lease_seconds=100)
    assert claim is not None
    results = [{"id": "synthetic-result", "title": "Synthetic fixture"}]
    if state == "failed":
        assert store.finish_job(claim["id"], claim["lease_token"], [], error_code="synthetic")
    else:
        assert store.finish_job(
            claim["id"], claim["lease_token"], results, partial=state == "completed_partial"
        )
    return claim


def counts(store):
    with closing(sqlite3.connect(store.path)) as db:
        return {
            table: db.execute(f"SELECT count(*) FROM {table}").fetchone()[0]
            for table in ("jobs", "snapshots", "feedback", "documents")
        }


@pytest.mark.parametrize("value", [True, -1, MAX_SECONDS + 1, None, 1.5, "60", float("nan")])
def test_invalid_policy_fails_before_acceptance_or_setup(store, tmp_path, value):
    with pytest.raises(ValueError, match="retention_seconds"):
        submit(store, retention_seconds=value)
    with pytest.raises(ValueError, match="retention_seconds"):
        Settings(retention_seconds=value)
    with pytest.raises(ValueError, match="retention_seconds"):
        setup(tmp_path / "config", tmp_path / "other.db", LLMConfig(), retention_seconds=value)
    assert not (tmp_path / "other.db").exists()
    assert not (tmp_path / "config").exists()
    assert counts(store)["jobs"] == 0


@pytest.mark.parametrize(
    "state", ["queued", "running", "completed", "completed_partial", "failed", "cancelled"]
)
def test_exact_deadline_hides_every_state_without_needing_cleanup(store, clock, state):
    job = submit(store, retention_seconds=10)
    assert job["expires_at"] == 1010
    token = None
    if state == "running":
        token = store.claim_job("synthetic-worker", lease_seconds=100)["lease_token"]
    elif state == "cancelled":
        store.cancel_job("alice", job["id"])
    elif state != "queued":
        token = finish(store, state)["lease_token"]
    clock[0] = 1009.999
    assert store.get_job("alice", job["id"])["state"] == state
    clock[0] = 1010
    for owner in ("alice", "bob"):
        assert store.get_job(owner, job["id"]) is None
        assert store.get_results(owner, job["id"], version=999) is None
        assert store.cancel_job(owner, job["id"]) is None
        assert store.delete_job(owner, job["id"]) is False
        with pytest.raises(FeedbackError):
            store.submit_feedback(owner, job["id"], 1, None, 1)
    if token:
        assert not store.heartbeat(job["id"], token, lease_seconds=100)
        assert not store.finish_job(job["id"], token, [{"id": "late"}])
    assert counts(store)["jobs"] == 1  # Logical expiry works with the worker stopped.
    assert store.claim_job("new-worker") is None
    assert counts(store)["jobs"] == 0


def test_deadline_survives_restart_heartbeat_feedback_and_policy_changes(store, clock):
    job = submit(store, retention_seconds=10, idempotency_key="stable")
    claim = store.claim_job("synthetic-worker", lease_seconds=100)
    clock[0] += 2
    assert store.heartbeat(job["id"], claim["lease_token"], phase="reranking")
    assert store.finish_job(job["id"], claim["lease_token"], [{"id": "result"}])
    store.submit_feedback("alice", job["id"], 1, None, 1)
    independent = Store(store.path)
    independent.initialize()
    replay, created = independent.create_search(
        "alice",
        "Synthetic retention test",
        ["local"],
        idempotency_key="stable",
        retention_seconds=0,
    )
    assert not created and replay["expires_at"] == 1010
    assert independent.get_job("alice", job["id"])["expires_at"] == 1010
    clock[0] = 1010
    assert independent.get_results("alice", job["id"]) is None
    assert independent.prune_expired(apply=True)["deleted_jobs"] == 1
    assert counts(store) == {"jobs": 0, "snapshots": 0, "feedback": 0, "documents": 0}


def test_expired_key_is_reused_atomically_without_resurrection_or_foreign_deletion(store, clock):
    old = submit(store, retention_seconds=1, idempotency_key="reuse")
    finish(store)
    store.submit_feedback("alice", old["id"], 1, None, 1)
    bob, _ = store.create_search("bob", "Other synthetic query", ["local"], idempotency_key="reuse")
    clock[0] += 1

    def retry(_):
        return Store(store.path).create_search(
            "alice", "New synthetic query", ["local"], idempotency_key="reuse", retention_seconds=30
        )

    with ThreadPoolExecutor(max_workers=4) as executor:
        values = list(executor.map(retry, range(8)))
    assert sum(created for _, created in values) == 1
    assert len({job["id"] for job, _ in values}) == 1
    new = values[0][0]
    assert new["id"] != old["id"] and new["expires_at"] == 1031
    assert store.get_job("bob", bob["id"])["expires_at"] is None
    assert counts(store)["snapshots"] == counts(store)["feedback"] == 0
    with pytest.raises(IdempotencyConflict):
        store.create_search("alice", "Wrong request", ["local"], idempotency_key="reuse")


def test_worker_prunes_a_bounded_batch_and_skips_expired_backlog(store, clock):
    for _ in range(CLEANUP_BATCH + 3):
        submit(store, retention_seconds=1)
    live = submit(store)
    clock[0] += 1
    claim = store.claim_job("worker")
    assert claim["id"] == live["id"]
    assert counts(store)["jobs"] == 4
    assert store.prune_expired(apply=True)["deleted_jobs"] == 3
    assert counts(store)["jobs"] == 1


def test_idle_worker_cleans_dependents_but_preserves_corpus_and_unexpired_data(store, clock):
    store.upsert_document(DEMO_DOCUMENTS[0])
    expired = submit(store, retention_seconds=1)
    finish(store)
    store.submit_feedback("alice", expired["id"], 1, None, 1, learning_opt_in=True)
    forever = submit(store)
    finish(store)
    clock[0] += 1
    assert process_one(store) is False  # No queued job is necessary for cleanup.
    assert counts(store) == {"jobs": 1, "snapshots": 1, "feedback": 0, "documents": 1}
    assert store.get_results("alice", forever["id"])["version"] == 1


def test_expiry_during_retrieval_prevents_publication(store, clock, monkeypatch):
    job = submit(store, retention_seconds=1)

    def slow_retrieval(*args, **kwargs):
        clock[0] += 1
        return []

    monkeypatch.setattr(store, "search_local", slow_retrieval)
    assert process_one(store) is True
    assert store.get_job("alice", job["id"]) is None
    assert counts(store)["snapshots"] == 0
    assert process_one(store) is False
    assert counts(store)["jobs"] == 0


def test_expiry_during_model_ranking_does_not_publish_or_fall_back(store, clock):
    ranker_config = LLMConfig(model="synthetic-local")
    store.upsert_document(DEMO_DOCUMENTS[0])
    store.upsert_document(DEMO_DOCUMENTS[1])
    job = store.create_search(
        "alice",
        "Anvesha demonstration",
        ["local"],
        retention_seconds=1,
        ranking="llm",
        pipeline_version=ranker_config.pipeline_version,
    )[0]
    calls = []

    class SlowSyntheticRanker:
        config = ranker_config

        def rerank(self, query, candidates, checkpoint):
            calls.append(len(candidates))
            clock[0] += 1
            assert not checkpoint()
            return candidates

    assert process_one(store, reranker=SlowSyntheticRanker())
    assert calls == [2]
    assert store.get_job("alice", job["id"]) is None
    assert counts(store)["snapshots"] == 0


@pytest.mark.parametrize("batch", [True, 0, -1, 501, 1.5, "1"])
def test_operator_batch_limits_do_not_mutate(store, clock, batch):
    submit(store, retention_seconds=1)
    clock[0] += 1
    with pytest.raises(ValueError, match="prune limit"):
        store.prune_expired(limit=batch, apply=True)
    assert counts(store)["jobs"] == 1


def test_dry_run_is_read_only_and_apply_is_one_recorded_deadline_batch(store, clock):
    for _ in range(3):
        submit(store, retention_seconds=1)
    submit(store)  # Null never becomes eligible by age.
    clock[0] += MAX_SECONDS * 2
    before = counts(store)
    assert store.prune_expired(limit=2) == {
        "apply": False,
        "batch_size": 2,
        "eligible_jobs": 2,
        "deleted_jobs": 0,
    }
    assert counts(store) == before
    assert store.prune_expired(limit=2, apply=True)["deleted_jobs"] == 2
    assert store.prune_expired(limit=2, apply=True)["deleted_jobs"] == 1
    assert counts(store)["jobs"] == 1


def test_concurrent_pruners_do_not_double_delete_or_leave_dependent_rows(store, clock):
    for _ in range(5):
        job = submit(store, retention_seconds=1)
        finish(store)
        store.submit_feedback("alice", job["id"], 1, None, 1)
    clock[0] += 1

    def prune(_):
        return Store(store.path).prune_expired(limit=2, apply=True)

    with ThreadPoolExecutor(max_workers=4) as executor:
        batches = list(executor.map(prune, range(4)))
    assert sum(batch["deleted_jobs"] for batch in batches) == 5
    assert all(batch["eligible_jobs"] == batch["deleted_jobs"] <= 2 for batch in batches)
    assert counts(store) == {"jobs": 0, "snapshots": 0, "feedback": 0, "documents": 0}


def test_missing_and_legacy_prune_refuse_implicit_creation_or_migration(tmp_path):
    store = Store(tmp_path / "legacy.db")
    for apply in (False, True):
        with pytest.raises(ValueError, match="Initialize/upgrade"):
            store.prune_expired(apply=apply)
    assert not store.path.exists()
    # The pre-ANV-026 schema lacks only the newly added nullable column/index.
    with closing(sqlite3.connect(store.path)) as db, db:
        db.executescript(_SCHEMA.replace("    expires_at REAL,\n", ""))
        assert "expires_at" not in {r[1] for r in db.execute("PRAGMA table_info(jobs)")}
        db.execute(
            """INSERT INTO jobs (id,owner,query,sources_json,result_limit,request_hash,
               idempotency_key,state,phase,pipeline_version,created_at,updated_at)
               VALUES ('legacy','alice','Synthetic retention test','["local"]',10,
               'legacy-hash','legacy-key','completed','completed','m1-rrf-v1',1,1)"""
        )
        db.execute("INSERT INTO snapshots VALUES ('legacy',1,'[]',0)")
        db.execute("UPDATE jobs SET results_version=1 WHERE id='legacy'")
        db.execute(
            """INSERT INTO feedback VALUES ('f','alice','legacy',1,'',1,NULL,NULL,0,
               'm1-rrf-v1',1,1)"""
        )
    original = store.path.read_bytes()
    settings = Settings(database_path=store.path, api_keys=(KEY,))
    assert diagnostics(settings)["ready"] is False
    for apply in (False, True):
        with pytest.raises(ValueError, match="Initialize/upgrade"):
            store.prune_expired(apply=apply)
    assert store.path.read_bytes() == original
    store.initialize()
    store.initialize()
    assert diagnostics(settings)["ready"] is True
    assert store.get_job("alice", "legacy")["expires_at"] is None
    assert store.get_results("alice", "legacy")["version"] == 1
    assert counts(store)["feedback"] == 1
    assert store.prune_expired(apply=True)["deleted_jobs"] == 0
    with closing(sqlite3.connect(store.path)) as db:
        assert db.execute("SELECT request_hash FROM jobs").fetchone()[0] == "legacy-hash"
        indexes = {
            row[0] for row in db.execute("SELECT name FROM sqlite_master WHERE type='index'")
        }
        assert {"jobs_expiry", "feedback_job_snapshot"} <= indexes


def test_api_expiry_overrides_etag_pagination_feedback_cancel_and_delete(tmp_path, clock):
    settings = Settings(
        database_path=tmp_path / "api.db", api_keys=(KEY, OTHER_KEY), retention_seconds=2
    )
    app = create_app(settings)
    with TestClient(app, headers={"X-API-Key": KEY}) as client:
        caps = client.get("/v1/capabilities").json()
        assert caps["retention_seconds"] == 2
        response = client.post("/v1/searches", json={"query": "Synthetic", "ranking": "lexical"})
        job = response.json()
        path = response.headers["location"]
        assert job["expires_at"] == 1002
        finish(app.state.store)
        assert client.get(path + "/results").json()["expires_at"] == 1002
        status = client.get(path)
        assert (
            client.get(path, headers={"If-None-Match": status.headers["etag"]}).status_code == 304
        )
        clock[0] = 1002
        for headers in ({}, {"X-API-Key": OTHER_KEY}):
            assert (
                client.get(
                    path, headers={**headers, "If-None-Match": status.headers["etag"]}
                ).status_code
                == 404
            )
            assert (
                client.get(path + "/results?version=1&offset=0", headers=headers).status_code == 404
            )
            assert (
                client.post(
                    path + "/feedback", json={"version": 1, "rating": 1}, headers=headers
                ).status_code
                == 404
            )
            assert client.post(path + "/cancel", headers=headers).status_code == 404
            assert client.delete(path, headers=headers).status_code == 404
        assert counts(app.state.store)["jobs"] == 1
        assert process_one(app.state.store) is False
        assert counts(app.state.store)["jobs"] == 0


def test_api_feedback_expiring_between_owner_check_and_write_returns_not_found(
    tmp_path, clock, monkeypatch
):
    app = create_app(
        Settings(database_path=tmp_path / "api.db", api_keys=(KEY,), retention_seconds=1)
    )
    with TestClient(app, headers={"X-API-Key": KEY}) as client:
        job = client.post("/v1/searches", json={"query": "Synthetic", "ranking": "lexical"}).json()
        finish(app.state.store)
        original = app.state.store.submit_feedback

        def expire_before_write(*args, **kwargs):
            clock[0] += 1
            return original(*args, **kwargs)

        monkeypatch.setattr(app.state.store, "submit_feedback", expire_before_write)
        result = client.post(f"/v1/searches/{job['id']}/feedback", json={"version": 1, "rating": 1})
        assert result.status_code == 404 and result.json()["detail"] == "search_not_found"
        assert counts(app.state.store)["feedback"] == 0


def test_saved_policy_upgrade_and_environment_are_deliberate(tmp_path, monkeypatch):
    path = tmp_path / "config"
    settings = setup(path, tmp_path / "db", LLMConfig())
    assert settings.retention_seconds == DEFAULT_SECONDS
    assert load_settings(path).retention_seconds == DEFAULT_SECONDS
    monkeypatch.setenv("ANVESHA_RETENTION_SECONDS", "9")
    assert Settings.from_env().retention_seconds == 9
    assert load_settings(path).retention_seconds == DEFAULT_SECONDS
    old = json.loads(path.read_bytes())
    old.pop("retention_seconds")
    path.write_text(json.dumps(old), encoding="utf-8")
    before = path.read_bytes()
    assert load_settings(path).retention_seconds == 0
    assert path.read_bytes() == before
    # Loading old settings must not borrow a new environment default.
    changed = replace(settings, retention_seconds=0)
    assert changed.retention_seconds == 0


@pytest.mark.parametrize("value", [True, -1, MAX_SECONDS + 1, "8", None])
def test_invalid_saved_policy_fails_without_echoing_private_config(tmp_path, value):
    path = tmp_path / "config"
    settings = setup(path, tmp_path / "db", LLMConfig())
    data = json.loads(path.read_bytes())
    data["retention_seconds"] = value
    path.write_text(json.dumps(data), encoding="utf-8")
    with pytest.raises(ValueError, match="Invalid private configuration") as problem:
        load_settings(path)
    assert settings.api_keys[0] not in str(problem.value)


def test_malformed_environment_does_not_echo_the_value(monkeypatch):
    monkeypatch.setenv("ANVESHA_RETENTION_SECONDS", "synthetic-sensitive-value")
    with pytest.raises(ValueError, match="must be an integer") as problem:
        Settings.from_env()
    assert "synthetic-sensitive-value" not in str(problem.value)


def test_cli_setup_opt_out_and_prune_are_explicit_secret_free(tmp_path, clock, capsys):
    path = tmp_path / "config"
    assert (
        main(
            [
                "--db",
                str(tmp_path / "db"),
                "setup",
                "--config",
                str(path),
                "--lexical-only",
                "--retention-seconds",
                "0",
            ]
        )
        == 0
    )
    settings = load_settings(path)
    assert settings.retention_seconds == 0
    assert settings.api_keys[0] not in capsys.readouterr().out
    store = Store(settings.database_path)
    submit(store, retention_seconds=1)
    clock[0] += 1
    assert main(["prune", "--config", str(path)]) == 0
    assert json.loads(capsys.readouterr().out)["deleted_jobs"] == 0
    assert counts(store)["jobs"] == 1
    assert main(["prune", "--config", str(path), "--apply", "--batch-size", "1"]) == 0
    output = capsys.readouterr().out
    assert json.loads(output)["deleted_jobs"] == 1
    assert settings.api_keys[0] not in output and "Synthetic retention test" not in output
    assert counts(store)["jobs"] == 0
