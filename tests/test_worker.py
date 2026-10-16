import pytest

from anvesha.providers import ProviderError
from anvesha.store import Store
from anvesha.worker import process_one


@pytest.fixture
def store(tmp_path):
    instance = Store(tmp_path / "worker.db")
    instance.initialize()
    instance.upsert_document(
        {
            "id": "doc_1",
            "url": "https://example.org/search",
            "title": "Search demonstration",
            "content": "Anvesha supports asynchronous search jobs.",
            "license": "Apache-2.0",
            "attribution": "Kshurika Consultancy demonstration",
        }
    )
    return instance


def job(store, sources=None, query="search"):
    created, _ = store.create_search("client", query, sources or ["local"], limit=10)
    return created["id"]


def test_local_job_completes_offline_with_stable_snapshot(store):
    identifier = job(store)

    def forbidden_network(*args, **kwargs):
        pytest.fail("local job must not call network")

    assert process_one(store, wikidata_search=forbidden_network)
    status = store.get_job("client", identifier)
    results = store.get_results("client", identifier)
    assert status["state"] == "completed"
    assert status["results_version"] == 1
    assert results["total"] == 1
    assert results["results"][0]["evidence_status"] == "local_document"
    assert not process_one(store, wikidata_search=forbidden_network)
    assert store.get_results("client", identifier) == results


def test_successful_empty_and_partial_empty_are_distinct_from_failure(store):
    complete = job(store, query="unmatchablezz")
    process_one(store)
    assert store.get_job("client", complete)["state"] == "completed"
    assert store.get_results("client", complete) == {"version": 1, "results": [], "total": 0}

    def failure(*args, **kwargs):
        raise ProviderError("timeout")

    partial = job(store, ["local", "wikidata"], "unmatchablezz")
    process_one(store, wikidata_search=failure)
    assert store.get_job("client", partial)["state"] == "completed_partial"
    assert store.get_job("client", partial)["warnings"] == ["wikidata:timeout"]
    assert store.get_results("client", partial)["version"] == 1

    failed = job(store, ["wikidata"])
    process_one(store, wikidata_search=failure)
    assert store.get_job("client", failed)["state"] == "failed"
    assert store.get_job("client", failed)["error_code"] == "all_sources_failed"
    assert store.get_results("client", failed)["version"] == 0


def test_unexpected_provider_failure_does_not_expose_exception_or_discard_local(store):
    identifier = job(store, ["wikidata", "local"])

    def failure(*args, **kwargs):
        raise RuntimeError("private query, secret key, upstream body")

    process_one(store, wikidata_search=failure)
    status = store.get_job("client", identifier)
    assert status["state"] == "completed_partial"
    assert status["warnings"] == ["wikidata:source_failed"]
    assert store.get_results("client", identifier)["total"] == 1


@pytest.mark.parametrize("action", ["cancel", "delete"])
def test_cancellation_or_deletion_during_retrieval_prevents_publication(store, action):
    identifier = job(store, ["local", "wikidata"])

    def interrupted(*args, **kwargs):
        if action == "cancel":
            store.cancel_job("client", identifier)
        else:
            store.delete_job("client", identifier)
        return []

    assert process_one(store, wikidata_search=interrupted)
    status = store.get_job("client", identifier)
    if action == "cancel":
        assert status["state"] == "cancelled"
        assert status["results_version"] == 0
    else:
        assert status is None


def test_configuration_change_disables_pending_connector_without_calling_it(store):
    identifier = job(store, ["wikidata"])

    def forbidden_network(*args, **kwargs):
        pytest.fail("disabled connector must not run")

    process_one(store, wikidata_search=forbidden_network, enabled_sources=("local",))
    status = store.get_job("client", identifier)
    assert status["state"] == "failed"
    assert status["warnings"] == ["wikidata:disabled_source"]


def test_successful_empty_live_source_completes(store):
    identifier = job(store, ["wikidata"])
    process_one(store, wikidata_search=lambda *args, **kwargs: [])
    assert store.get_job("client", identifier)["state"] == "completed"
    assert store.get_results("client", identifier)["version"] == 1


def test_reclaimed_lease_during_connector_work_cannot_publish(store, monkeypatch):
    clock = [1_000_000.0]
    monkeypatch.setattr("anvesha.store.time.time", lambda: clock[0])
    identifier = job(store, ["wikidata"])
    new_owner = []

    def delayed_provider(*args, **kwargs):
        clock[0] += 61
        other_store = Store(store.path)
        new_owner.append(other_store.claim_job("replacement", lease_seconds=60))
        return []

    assert process_one(store, worker_id="old", wikidata_search=delayed_provider)
    status = store.get_job("client", identifier)
    assert status["state"] == "running"
    assert status["worker_id"] == "replacement"
    assert status["attempts"] == 2
    assert status["results_version"] == 0
    assert store.finish_job(identifier, new_owner[0]["lease_token"], [])
    assert store.get_job("client", identifier)["state"] == "completed"
