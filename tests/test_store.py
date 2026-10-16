"""ANV-003 storage contracts, including recovery and cross-client failure paths."""

import sqlite3
from concurrent.futures import ThreadPoolExecutor

import pytest

from anvesha.store import FeedbackError, IdempotencyConflict, Store


@pytest.fixture
def store(tmp_path):
    result = Store(tmp_path / "anvesha.db")
    result.initialize()
    return result


@pytest.fixture
def clock(monkeypatch):
    current = [1000.0]
    monkeypatch.setattr("anvesha.store.time.time", lambda: current[0])
    return current


def search(store, owner="alice", **kwargs):
    return store.create_search(owner, "durable search", ["local"], **kwargs)[0]


def result(result_id="result-1"):
    return {
        "id": result_id,
        "url": f"https://example.test/{result_id}",
        "title": "Anvesha demonstration",
        "snippet": "Durable search demonstration material.",
        "sources": ["local"],
        "score": 1 / 61,
        "evidence_status": "local_document",
        "license": "Apache-2.0",
        "attribution": "Kshurika Consultancy",
    }


def complete(store, results=None):
    job = search(store)
    claim = store.claim_job("worker-a")
    assert claim["id"] == job["id"]
    assert store.finish_job(
        job["id"], claim["lease_token"], [result()] if results is None else results
    )
    return job


def test_acceptance_survives_new_store_and_uses_wal(store):
    job = search(store)
    independent = Store(store.path)
    independent.initialize()
    saved = independent.get_job("alice", job["id"])
    assert saved["state"] == "queued"
    assert saved["query"] == "durable search"
    assert saved["pipeline_version"] == "m1-rrf-v1"
    with sqlite3.connect(store.path) as connection:
        assert connection.execute("PRAGMA journal_mode").fetchone()[0] == "wal"


def test_idempotency_is_atomic_canonical_and_client_scoped(store):
    def submit(_):
        independent = Store(store.path)
        return independent.create_search(
            "alice", " Original query ", ["wikidata", "local"], idempotency_key="retry"
        )

    with ThreadPoolExecutor(max_workers=4) as pool:
        submissions = list(pool.map(submit, range(8)))
    assert sum(created for _, created in submissions) == 1
    assert len({job["id"] for job, _ in submissions}) == 1
    job, created = store.create_search(
        "alice", " Original query ", ["local", "wikidata"], idempotency_key="retry"
    )
    assert not created
    assert job["query"] == " Original query "
    other, created = store.create_search(
        "bob", " Original query ", ["local", "wikidata"], idempotency_key="retry"
    )
    assert created and other["id"] != job["id"]
    with pytest.raises(IdempotencyConflict):
        store.create_search("alice", "different", ["local"], idempotency_key="retry")
    with pytest.raises(IdempotencyConflict):
        store.create_search(
            "alice", " Original query ", ["local", "wikidata"], limit=5, idempotency_key="retry"
        )


def test_missing_and_foreign_jobs_are_indistinguishable(store):
    job = search(store)
    for job_id in (job["id"], "missing"):
        assert store.get_job("bob", job_id) is None
        assert store.get_results("bob", job_id, version=999) is None
        assert store.cancel_job("bob", job_id) is None
        assert not store.delete_job("bob", job_id)
    assert store.get_job("alice", job["id"])["state"] == "queued"


def test_concurrent_workers_cannot_claim_same_lease(store, clock):
    job = search(store)
    with ThreadPoolExecutor(max_workers=4) as pool:
        claims = list(pool.map(lambda i: Store(store.path).claim_job(f"worker-{i}"), range(4)))
    assert len([claim for claim in claims if claim]) == 1
    assert next(claim for claim in claims if claim)["id"] == job["id"]


def test_expired_claim_recovery_rejects_stale_worker(store, clock):
    job = search(store)
    first = store.claim_job("first", lease_seconds=10)
    second_store = Store(store.path)
    assert second_store.claim_job("second") is None
    clock[0] += 10
    assert not store.heartbeat(job["id"], first["lease_token"])
    assert not store.finish_job(job["id"], first["lease_token"], [result("stale")])
    second = second_store.claim_job("second")
    assert second["attempts"] == 2
    assert second["lease_token"] != first["lease_token"]
    assert not store.finish_job(job["id"], first["lease_token"], [result("stale")])
    assert second_store.finish_job(job["id"], second["lease_token"], [result("new")])
    assert store.get_results("alice", job["id"])["results"][0]["id"] == "new"


def test_heartbeat_extends_current_lease_and_phase(store, clock):
    job = search(store)
    claim = store.claim_job("worker", lease_seconds=10)
    clock[0] += 9
    assert not store.heartbeat(job["id"], "wrong-token", phase="bad")
    assert store.heartbeat(job["id"], claim["lease_token"], 20, phase="ranking")
    clock[0] += 2
    assert Store(store.path).claim_job("other") is None
    current = store.get_job("alice", job["id"])
    assert current["phase"] == "ranking"
    assert current["lease_until"] == 1029


def test_exhausted_attempts_fail_durably_without_snapshot(store, clock):
    job = search(store)
    first = store.claim_job("worker", lease_seconds=1, max_attempts=2)
    clock[0] += 1
    second = store.claim_job("worker", lease_seconds=1, max_attempts=2)
    clock[0] += 1
    assert store.claim_job("worker", max_attempts=2) is None
    saved = store.get_job("alice", job["id"])
    assert saved["state"] == "failed"
    assert saved["attempts"] == 2
    assert saved["error_code"] == "worker_attempts_exhausted"
    assert saved["lease_token"] is None
    assert not store.finish_job(job["id"], first["lease_token"], [result()])
    assert not store.finish_job(job["id"], second["lease_token"], [result()])
    assert store.get_results("alice", job["id"]) == {"version": 0, "results": [], "total": 0}


@pytest.mark.parametrize("running", [False, True])
def test_cancellation_invalidates_claim_and_stops_work(store, running):
    job = search(store)
    claim = store.claim_job("worker") if running else None
    cancelled = store.cancel_job("alice", job["id"])
    assert cancelled["state"] == "cancelled"
    assert store.cancel_job("alice", job["id"]) == cancelled
    assert store.claim_job("worker") is None
    if claim:
        assert not store.heartbeat(job["id"], claim["lease_token"])
        assert not store.finish_job(job["id"], claim["lease_token"], [result()])


def test_snapshot_is_immutable_and_paginated(store):
    job = search(store)
    claim = store.claim_job("worker")
    assert store.get_results("alice", job["id"]) == {"version": 0, "results": [], "total": 0}
    results = [result("first"), result("second")]
    assert store.finish_job(job["id"], claim["lease_token"], results)
    assert not store.finish_job(job["id"], claim["lease_token"], [result("changed")])
    assert store.cancel_job("alice", job["id"])["state"] == "completed"
    assert store.get_results("alice", job["id"], version=1, offset=1, limit=1) == {
        "version": 1,
        "results": [results[1]],
        "total": 2,
    }
    assert store.get_results("alice", job["id"], offset=10)["results"] == []
    with pytest.raises(ValueError):
        store.get_results("alice", job["id"], version=2)


@pytest.mark.parametrize("partial", [False, True])
def test_successful_empty_result_has_published_snapshot(store, partial):
    job = search(store)
    claim = store.claim_job("worker")
    assert store.finish_job(job["id"], claim["lease_token"], [], partial=partial)
    assert store.get_job("alice", job["id"])["state"] == (
        "completed_partial" if partial else "completed"
    )
    assert store.get_results("alice", job["id"]) == {"version": 1, "results": [], "total": 0}
    assert store.submit_feedback("alice", job["id"], 1, None, -1)["result_id"] is None


def test_failure_has_no_snapshot_and_warning_storage_is_bounded(store):
    job = search(store)
    claim = store.claim_job("worker")
    assert store.finish_job(
        job["id"],
        claim["lease_token"],
        [],
        warnings=["local:" + "x" * 300 + "\n"] * 30,
        error_code="all_sources_failed",
    )
    current = store.get_job("alice", job["id"])
    assert current["state"] == "failed" and current["results_version"] == 0
    assert len(current["warnings"]) == 20
    assert all(len(warning) == 200 and "\n" not in warning for warning in current["warnings"])
    with pytest.raises(FeedbackError):
        store.submit_feedback("alice", job["id"], 1, None, 1)


def test_invalid_publication_does_not_leave_partial_snapshot(store):
    job = search(store)
    claim = store.claim_job("worker")
    with pytest.raises(ValueError):
        store.finish_job(job["id"], claim["lease_token"], [result(), result()])
    assert store.get_job("alice", job["id"])["state"] == "running"
    assert store.get_results("alice", job["id"])["version"] == 0
    assert store.finish_job(job["id"], claim["lease_token"], [result()])


def test_database_failure_rolls_back_snapshot_and_terminal_transition(store):
    job = search(store)
    claim = store.claim_job("worker")
    with sqlite3.connect(store.path) as connection:
        connection.execute(
            """CREATE TRIGGER reject_publication BEFORE UPDATE OF state ON jobs
               WHEN new.state = 'completed' BEGIN
                   SELECT RAISE(ABORT, 'simulated publication failure');
               END"""
        )
    with pytest.raises(sqlite3.IntegrityError, match="simulated publication failure"):
        store.finish_job(job["id"], claim["lease_token"], [result()])
    assert Store(store.path).get_job("alice", job["id"])["state"] == "running"
    assert store.get_results("alice", job["id"])["version"] == 0
    with sqlite3.connect(store.path) as connection:
        assert connection.execute("SELECT COUNT(*) FROM snapshots").fetchone()[0] == 0
        connection.execute("DROP TRIGGER reject_publication")
    assert store.finish_job(job["id"], claim["lease_token"], [result()])


def test_feedback_replaces_vote_and_is_bound_to_pipeline_and_result(store):
    job = complete(store)
    original = store.submit_feedback("alice", job["id"], 1, "result-1", -1, "irrelevant")
    replacement = store.submit_feedback(
        "alice", job["id"], 1, "result-1", 1, comment="Useful", learning_opt_in=True
    )
    assert original["id"] == replacement["id"]
    assert original["learning_opt_in"] is False
    assert replacement["rating"] == 1
    assert replacement["learning_opt_in"] is True
    assert replacement["pipeline_version"] == "m1-rrf-v1"
    overall = store.submit_feedback("alice", job["id"], 1, None, 1)
    assert overall["id"] != original["id"]
    with sqlite3.connect(store.path) as connection:
        assert connection.execute("SELECT COUNT(*) FROM feedback").fetchone()[0] == 2


@pytest.mark.parametrize(
    "owner,version,result_id,rating",
    [
        ("bob", 1, "result-1", 1),
        ("alice", 2, "result-1", 1),
        ("alice", 0, None, 1),
        ("alice", 1, "foreign-result", 1),
        ("alice", 1, "", 1),
        ("alice", 1, "result-1", 0),
        ("alice", 1, "result-1", True),
    ],
)
def test_feedback_rejects_foreign_versions_results_and_invalid_votes(
    store, owner, version, result_id, rating
):
    job = complete(store)
    with pytest.raises(FeedbackError):
        store.submit_feedback(owner, job["id"], version, result_id, rating)


def test_deletion_cascades_results_feedback_and_allows_new_key(store):
    job = search(store, idempotency_key="reusable-after-deletion")
    claim = store.claim_job("worker")
    assert store.finish_job(job["id"], claim["lease_token"], [result()])
    store.submit_feedback("alice", job["id"], 1, "result-1", 1)
    assert store.delete_job("alice", job["id"])
    assert not store.delete_job("alice", job["id"])
    assert store.get_job("alice", job["id"]) is None
    assert store.get_results("alice", job["id"]) is None
    with sqlite3.connect(store.path) as connection:
        for table in ("jobs", "snapshots", "feedback"):
            assert connection.execute(f"SELECT COUNT(*) FROM {table}").fetchone()[0] == 0
    replacement = search(store, idempotency_key="reusable-after-deletion")
    assert replacement["id"] != job["id"]


def test_deleting_running_job_prevents_worker_resurrection(store):
    job = search(store)
    claim = store.claim_job("worker")
    assert store.delete_job("alice", job["id"])
    assert not store.heartbeat(job["id"], claim["lease_token"])
    assert not store.finish_job(job["id"], claim["lease_token"], [result()])


@pytest.fixture
def document():
    return {
        "id": "demo",
        "url": "https://example.test/demo",
        "title": "Anvesha demonstration",
        "content": "An asynchronous search API with durable jobs.",
        "license": "Apache-2.0",
        "attribution": "Kshurika Consultancy",
    }


def test_local_index_upsert_replaces_old_terms_and_preserves_rights(store, document):
    store.upsert_document(document)
    results = Store(store.path).search_local("asynchronous")
    assert len(results) == 1
    assert results[0]["url"] == document["url"]
    assert results[0]["license"] == "Apache-2.0"
    assert results[0]["attribution"] == "Kshurika Consultancy"
    assert results[0]["evidence_status"] == "local_document"
    assert results[0]["source"] == "local" and results[0]["source_rank"] == 1
    assert "asynchronous" in results[0]["snippet"]
    document["content"] = "Fresh documentation for indexing."
    store.upsert_document(document)
    assert store.search_local("asynchronous") == []
    assert len(store.search_local("indexing")) == 1


@pytest.mark.parametrize(
    "query",
    [
        '"asynchronous" OR title:missing',
        "asynchronous -missing",
        "NEAR(asynchronous)",
        "asynchronous; DROP TABLE jobs;",
        "asynchronous AND (",
    ],
)
def test_local_query_operators_are_escaped_as_natural_language(store, document, query):
    store.upsert_document(document)
    assert store.search_local(query)[0]["url"] == document["url"]
    assert search(store)["state"] == "queued"


@pytest.mark.parametrize("query", ["", " ", '"*()::!!!', "😀"])
def test_empty_or_tokenless_search_returns_no_matches(store, document, query):
    store.upsert_document(document)
    assert store.search_local(query) == []


def test_index_supports_unicode_and_stable_ties(store, document):
    document["content"] = "Search documentation café खोज"
    store.upsert_document({**document, "id": "b", "url": "https://example.test/b"})
    store.upsert_document({**document, "id": "a", "url": "https://example.test/a"})
    assert [entry["url"] for entry in store.search_local("café")] == [
        "https://example.test/a",
        "https://example.test/b",
    ]
    assert len(store.search_local("खोज")) == 2


def test_documents_require_explicit_rights_fields(store, document):
    del document["license"]
    with pytest.raises(ValueError, match="license"):
        store.upsert_document(document)


def test_in_memory_database_rejected_for_durable_store():
    with pytest.raises(ValueError, match="persistent"):
        Store(":memory:")
