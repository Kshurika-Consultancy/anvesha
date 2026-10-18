# M1 implementation contract

ANV-021/ANV-022 extension: new HTTP requests default to `ranking: "llm"`, requiring
operator model configuration and the local source. Explicit lexical requests,
legacy stored jobs and evaluation helpers preserve M1 semantics. The current
contract is in [API](../API.md) and [ADR 0006](../decisions/0006-llm-default-and-self-hosted-browser.md).

This is the shared implementation interface for ANV-003 through ANV-006. Architectural intent is in README.md in this directory. Concrete API behavior is documented in `docs/API.md` once implemented.

## Storage

`src/anvesha/store.py` exports `Store(path)`, `IdempotencyConflict`, and `FeedbackError`. Store opens short-lived SQLite connections, initializes WAL/FTS5, and uses transactions for claims, cancellation, publication, and feedback. API and worker share one database file on a local disk. Tests may instantiate independent Store objects for the same file.

Store public methods:

```python
initialize() -> None
create_search(owner, query, sources, limit=10, idempotency_key=None) -> tuple[dict, bool]
get_job(owner, job_id) -> dict | None
claim_job(worker_id, lease_seconds=60, max_attempts=3) -> dict | None
heartbeat(job_id, lease_token, lease_seconds=60, phase=None) -> bool
finish_job(job_id, lease_token, results, warnings=None, partial=False, error_code=None) -> bool
cancel_job(owner, job_id) -> dict | None
delete_job(owner, job_id) -> bool
get_results(owner, job_id, version=None, offset=0, limit=10) -> dict | None
submit_feedback(owner, job_id, version, result_id, rating, reason=None, comment=None, learning_opt_in=False) -> dict
upsert_document(document: dict) -> None
search_local(query, limit=20) -> list[dict]
```

Job dictionaries contain `id`, `owner`, `query`, `sources` (list), `limit`, `state`, `phase`, `attempts`, `results_version`, `warnings` (list), `error_code`, `created_at`, `updated_at`, plus internal `lease_token`, `lease_until` when claimed. Timestamps are UTC epoch seconds internally. Idempotency scopes to owner and hashes canonical query/sources/limit; reused keys with different requests raise IdempotencyConflict. Same request/key returns existing job and `created=False`.

States: queued, running, completed, completed_partial, failed, cancelled. Completed with zero results is valid. Failed means no result snapshot; completed/partial publish version 1 even for an empty list. Cancellation immediately changes queued/running to cancelled and invalidates the lease. Published terminal snapshots never change. Deletion cascades snapshots and feedback and invalidates any running worker publication.

Claims recover expired running jobs up to max_attempts, after which they become failed with `worker_attempts_exhausted`. Each claim uses a fresh lease token. Heartbeat and finish require current token, running state, and unexpired lease; stale workers must not publish. External work occurs outside transactions. `finish_job(error_code=...)` marks failed; otherwise publishes results and terminal state atomically. Preserve bounded warning strings, never raw upstream exception payloads.

`get_results` returns `{version, results, total}` for a published snapshot; returns `{version: 0, results: [], total: 0}` if no snapshot, and None for missing/unowned job. Invalid noncurrent requested version raises ValueError. API uses an explicit offset and version for stable pagination.

Result dicts: `id`, `url`, `title`, `snippet`, `sources` (list), `score` (ranking value, not confidence), `evidence_status`, `license`, `attribution`, optional `source_rank`. Worker assigns deterministic IDs from canonical URLs and writes final ranks. Evidence states: `local_document` or `metadata_only`. No arbitrary page fetch or factual verification is claimed.

Feedback is one current rating per owner/job/version/result (result_id=None means overall search). Repeated submission replaces the previous rating rather than adding votes. Ratings are -1 or 1. Reason/comment/learning_opt_in stored; opt-in defaults false. Validate owner, published version, and result membership; raise FeedbackError on invalid feedback. Return feedback ID and its stored fields. Deleting a search removes its feedback.

Documents: `id`, `url`, `title`, `content`, `license`, `attribution`. SQLite FTS5 indexes title/content. Natural-language query tokens are escaped and OR-combined; raw FTS operators are not passed through. Empty/tokenless queries return no matches. Local candidate dictionaries have `url`, `title`, `snippet`, `source`='local', `source_rank`, `evidence_status`='local_document', `license`, `attribution`.

## Retrieval and worker

`src/anvesha/providers.py`: `search_wikidata(query, limit=20, client=None) -> list[dict]` uses httpx with a fixed `https://www.wikidata.org/w/api.php` endpoint, bounded response body, timeouts, redirect rejection, and a clear User-Agent. It queries `wbsearchentities` with language en for M1, returns label/description/entity URL metadata with `source`='wikidata', `evidence_status`='metadata_only', `license`='CC0-1.0', and attribution. Do not fetch entity URLs or use API-supplied arbitrary URLs. Validate Q identifiers and construct the canonical fixed-host entity URL. Exceptions expose sanitized provider failure codes through worker handling.

`src/anvesha/ranking.py`: `rank_candidates(candidates, limit=10) -> list[dict]` canonicalizes URLs conservatively, fuses provider ranks by RRF, deduplicates, and assigns stable result IDs. Preserve source and licence provenance; unlike content cannot be relicensed. Candidate input order must not cause nondeterministic final ties. Label scores as rank scores, never probabilities.

`src/anvesha/worker.py`: `process_one(store, worker_id='worker', lease_seconds=60, wikidata_search=search_wikidata) -> bool` claims one job, invokes only the requested connectors, isolates connector failures, renews its lease between bounded stages, ranks, publishes once, returns whether a job was claimed. At least one successful source plus source failures produces completed_partial; all requested sources failing produces failed. A successful empty source counts as success. Publication must fail safely if cancelled, deleted, reclaimed, or expired. CLI `python -m anvesha.worker --once` or continuous polling reads shared Settings; handles Ctrl-C and bounded sleep. Unexpected processing exceptions become a sanitized failed state or recover by lease expiry.

## Configuration and API

Root owns `src/anvesha/config.py`, `api.py`, `cli.py`, package scaffolding, tests/test_api.py and tests/test_cli.py. Config provides `Settings` dataclass with `database_path`, `api_keys` (tuple of strings), `enabled_sources` (tuple, default local), and `worker_poll_seconds`; `Settings.from_env()` reads ANVESHA_DB_PATH, ANVESHA_API_KEYS, ANVESHA_ENABLED_SOURCES, ANVESHA_WORKER_POLL_SECONDS. Defaults use `.anvesha/anvesha.db`. API requires at least one configured secret and fails startup if absent; CLI `anvesha init` prints a new random key and initializes/optionally seeds the store. Clients send `X-API-Key`. Store owner is a cryptographic digest, never the raw secret. Unauthorized callers cannot distinguish another owner's jobs from missing jobs.

POST /v1/searches body: query (1..2000 characters, nonblank), sources (optional; default local), limit (1..50). Only configured sources may be requested. Idempotency-Key is optional, bounded. GET status hides internal owner and lease fields. GET results accepts version, offset>=0, limit 1..50. Feedback body requires version>=1, rating in {-1,1}, optional result_id/reason/comment, learning_opt_in=false. GET /healthz is public and returns a small liveness response; remaining search endpoints require auth. Docs must make clear this is a localhost development baseline; hosted abuse controls are tracked for M2.

Demo seed documents are first-party, synthetic descriptions of Anvesha features under Apache-2.0, visibly marked as demonstration data. Default installation searches only this corpus after seed; it does not promise full-web search. CLI can ingest a JSON document list whose rights the operator has reviewed. No paid API, network, or LLM is required for local operation.
