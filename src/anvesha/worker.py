"""Separate, restartable worker for durable search jobs."""

from __future__ import annotations

import argparse
import time
import uuid
from collections.abc import Callable

from anvesha.llm import LLMError, LLMReranker, RerankCancelled
from anvesha.providers import ProviderError, search_wikidata
from anvesha.ranking import rank_candidates
from anvesha.store import Store


def process_one(
    store: Store,
    worker_id: str = "worker",
    lease_seconds: int = 60,
    wikidata_search: Callable = search_wikidata,
    enabled_sources: tuple[str, ...] | None = None,
    reranker: LLMReranker | None = None,
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
        ranking_limit = candidate_limit if job["ranking"] == "llm" else job["limit"]
        results = rank_candidates(candidates, limit=ranking_limit)
        if job["ranking"] == "llm" and len(results) >= 2:
            if reranker is None or not reranker.config.enabled:
                warnings.append("llm:not_configured")
            elif reranker.config.pipeline_version != job["pipeline_version"]:
                warnings.append("llm:configuration_changed")
            else:
                try:
                    results = reranker.rerank(
                        job["query"], results, lambda: checkpoint("llm_reranking")
                    )
                except RerankCancelled:
                    return True
                except LLMError as exc:
                    warnings.append("llm:" + exc.code)
                except Exception:
                    warnings.append("llm:rerank_failed")
        results = results[: job["limit"]]
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


def main(argv=None, settings=None) -> None:
    parser = argparse.ArgumentParser(description="Process Anvesha's persisted search queue")
    parser.add_argument("--once", action="store_true", help="Process at most one job and exit")
    args = parser.parse_args(argv)
    from anvesha.config import Settings

    settings = settings or Settings.from_env()
    store = Store(settings.database_path)
    store.initialize()
    worker_id = "worker_" + uuid.uuid4().hex
    reranker = LLMReranker(settings.llm) if settings.llm.enabled else None
    try:
        while True:
            processed = process_one(
                store,
                worker_id=worker_id,
                enabled_sources=settings.enabled_sources,
                reranker=reranker,
            )
            if args.once:
                return
            if not processed:
                time.sleep(settings.worker_poll_seconds)
    except KeyboardInterrupt:
        return


if __name__ == "__main__":
    main()
