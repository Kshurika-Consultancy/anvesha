"""Separate, restartable worker for durable search jobs."""

from __future__ import annotations

import argparse
import time
import uuid
from collections.abc import Callable

from anvesha.providers import ProviderError, search_wikidata
from anvesha.ranking import rank_candidates
from anvesha.store import Store


def process_one(
    store: Store,
    worker_id: str = "worker",
    lease_seconds: int = 60,
    wikidata_search: Callable = search_wikidata,
    enabled_sources: tuple[str, ...] | None = None,
) -> bool:
    """Claim one job and publish only while its current lease remains valid."""
    job = store.claim_job(worker_id, lease_seconds=lease_seconds, max_attempts=3)
    if job is None:
        return False
    token = job["lease_token"]

    def checkpoint(phase: str) -> bool:
        return store.heartbeat(job["id"], token, lease_seconds=lease_seconds, phase=phase)

    try:
        candidates = []
        warnings = []
        successes = 0
        candidate_limit = min(50, max(20, job["limit"] * 3))
        for source in dict.fromkeys(job["sources"]):
            if not checkpoint("retrieving_" + source):
                return True
            try:
                if enabled_sources is not None and source not in enabled_sources:
                    raise ProviderError("disabled_source")
                if source == "local":
                    retrieved = store.search_local(job["query"], limit=candidate_limit)
                elif source == "wikidata":
                    retrieved = wikidata_search(job["query"], limit=candidate_limit)
                else:
                    raise ProviderError("unsupported_source")
                candidates.extend(retrieved)
                successes += 1
            except ProviderError as exc:
                warnings.append(f"{source}:{exc.code}")
            except Exception:
                warnings.append(f"{source}:source_failed")
            if not checkpoint("retrieved_" + source):
                return True
        if not successes:
            store.finish_job(
                job["id"], token, [], warnings=warnings, error_code="all_sources_failed"
            )
            return True
        if not checkpoint("ranking"):
            return True
        results = rank_candidates(candidates, limit=job["limit"])
        if not checkpoint("publishing"):
            return True
        store.finish_job(job["id"], token, results, warnings=warnings, partial=bool(warnings))
    except Exception:
        # Store failures can leave the lease to expire; a later worker recovers it.
        # Never persist raw exception text that might contain a query or upstream body.
        try:
            store.finish_job(job["id"], token, [], error_code="processing_failed")
        except Exception:
            pass
    return True


def main() -> None:
    parser = argparse.ArgumentParser(description="Process Anvesha's persisted search queue")
    parser.add_argument("--once", action="store_true", help="Process at most one job and exit")
    args = parser.parse_args()
    from anvesha.config import Settings

    settings = Settings.from_env()
    store = Store(settings.database_path)
    store.initialize()
    worker_id = "worker_" + uuid.uuid4().hex
    try:
        while True:
            processed = process_one(
                store, worker_id=worker_id, enabled_sources=settings.enabled_sources
            )
            if args.once:
                return
            if not processed:
                time.sleep(settings.worker_poll_seconds)
    except KeyboardInterrupt:
        return


if __name__ == "__main__":
    main()
