# HTTP API

Tasks ANV-004, ANV-021, ANV-022 and ANV-026. Base URL: `http://127.0.0.1:8000`. The self-hosted browser is at `/`; OpenAPI is at `/openapi.json`. CDN-backed `/docs` and `/redoc` are disabled. JSON is the API input/output format. Timestamps are UTC Unix seconds. Browser assets, health and OpenAPI are public; all search/capability operations require `X-API-Key`.

## Authentication and ownership

Native/Compose `setup` saves keys and model/database settings in a private file
used by `start`, `run-api` and `run-worker`. Legacy environment launches use the
variables below. See [setup and permissions](PRIVATE_RESEARCH.md).

Configure one or more strong secrets with `ANVESHA_API_KEYS`. Every key identifies a separate owner. Raw secrets are not stored in job records or returned. Invalid/missing credentials return 401; another owner's job returns the same 404 as a nonexistent job. Key rotation does not transfer old jobs; multi-key tenant identities are future work. Restrict access to the local database, which contains operational query and feedback records.

## Submit and poll

`POST /v1/searches` body:

```json
{"query":"free local search","sources":["local"],"limit":10}
```

`query` is required, trimmed and limited to 1–2000 nonblank characters. `sources` defaults to `["local"]` and may contain only configured `local`/`wikidata` sources. `limit` is an integer from 1–50. `ranking` is experimental `"llm"` (default) or explicit `"lexical"`. Unknown fields are rejected; language/region/date filters and query planning are not implemented. Local matching OR-combines safe query tokens; exact-phrase, negation, domain/date filters and sophisticated intent handling are future work.

LLM mode requires operator model configuration and `sources: ["local"]`; otherwise submission returns 422 (`llm_not_configured` or `llm_local_source_only`) before acceptance. Explicit lexical mode works without a model. `GET /v1/capabilities` reports `sources`, `ranking_modes`, `default_ranking: "llm"`, `llm_configured`, `document_count`, `llm_source_scope`, `llm_endpoint_scope` and `gateway_downstream_verified: false` without credentials or addresses. The bounded stage preserves the original query; it does not generate queries or guarantee exact constraints. See [the private research guide](PRIVATE_RESEARCH.md).

**ANV-022 upgrade:** new omitted-mode requests now use LLM processing. Existing accepted jobs/snapshots are unchanged. Old lexical clients, Wikidata requests and old lexical idempotency replays must explicitly send `"ranking":"lexical"`; otherwise the input meaning changes and replay can conflict. Operators must review processing rights before using the default with external endpoints. The lexical job JSON below illustrates that explicit baseline.

Optional `Idempotency-Key` is 1–128 nonblank characters. The same owner/key and canonical query/sources/limit/ranking returns the existing job (200 with `Idempotency-Replayed: true`); different input returns 409. Model configuration changes do not rewrite a previously accepted job on replay. New jobs return 202 only after durable commit, with `Location`, `Retry-After: 1`, and `Idempotency-Replayed: false`. Old lexical request hashes remain valid after the additive database migration. Deleting a job removes its idempotency record, so reusing that key after deletion creates new work.

ANV-026 also bounds idempotency by retention. Replay before expiry keeps the original
`expires_at`, even if operator policy changed. At expiry, the same owner's key can
accept a **new** search (202/new ID), even with different input; the old job and its
dependent rows are removed in that transaction. No permanent tombstone or replay
guarantee survives expiry/deletion. Client request bodies cannot set retention.

`GET /v1/searches/{id}` returns the public job state:

```json
{
  "id": "srch_example",
  "query": "free local search",
  "sources": ["local"],
  "limit": 10,
  "state": "queued",
  "phase": "queued",
  "attempts": 0,
  "results_version": 0,
  "pipeline_version": "m1-rrf-v1",
  "ranking": "lexical",
  "warnings": [],
  "error_code": null,
  "created_at": 1792137600.0,
  "updated_at": 1792137600.0,
  "expires_at": 1792742400.0,
  "next_poll_after_ms": 1000,
  "results_available": false,
  "results_url": "/v1/searches/srch_example/results",
  "coverage": "configured_sources_only"
}
```

IDs/timestamps above are illustrative. State is separate from phase. Internal owner hashes, worker identifiers and lease tokens are omitted. `ETag` supports `If-None-Match` and 304 polling; clients should remember the last ETag without persisting private responses in shared caches. Responses use `Cache-Control: no-store`.

`expires_at` is the persisted UTC Unix deadline, or null for indefinite/legacy jobs.
Authenticated capabilities additionally report `retention_seconds`,
`retention_applies_to: "new_searches"`, and
`expiry_cleanup: "separate_worker_or_explicit_prune"`. These describe the current
policy for future submissions; the individual job's deadline is authoritative.

| State | Meaning |
| --- | --- |
| queued | Persisted, waiting for worker |
| running | Claimed under a lease; retrieving or ranking |
| completed | All requested sources completed; results can still be empty or narrow |
| completed_partial | At least one source succeeded and a source or requested optional model stage failed/was disabled |
| failed | All sources failed, processing failed, or worker attempts were exhausted |
| cancelled | Owner cancelled before terminal publication |

There is no percentage-complete claim. M1 publishes one final snapshot, version 1; it does not publish intermediate snapshots. Execution completion is not exhaustive web coverage or factual verification. Stale leases are reclaimed by an active worker up to three attempts. If all workers are stopped, queued/expired-running jobs remain pending until a worker resumes.

## Results and feedback

`GET /v1/searches/{id}/results?version=1&offset=0&limit=10` returns `search_id`, `pipeline_version`, requested `ranking`, `expires_at`, `version`, `results`, `total`, `offset`, `next_offset`, and coverage. Version may be omitted for the current snapshot. Offset is nonnegative; page limit is 1–50. Results-unavailable or nonexistent version returns 409. Failed/cancelled jobs without snapshots have no results. Stable final snapshots make pagination repeatable during the retained lifetime; no new results are added after completion.

Each result includes `id`, `rank`, `url`, `title`, `snippet`, `sources`, `score`, `display_source`, `evidence_status`, `license`, `attribution`, and `provenance`. The score is RRF ordering, not a probability of truth. The displayed text retains the licence of its selected source, while provenance records all contributors. `local_document` means operator-imported text was available; `metadata_only` means only Wikidata label/description metadata was retrieved. Neither claims factual verification. Clients must render titles/snippets as untrusted plain text, not executable HTML.

Successful model reranking adds `lexical_rank` and `ranking_method` (`llm_rerank` within the assessed prefix, `rrf` for the untouched tail). Final `rank` reflects the new order, while `score` remains the original lexical RRF value and need not be monotonic. Fewer than two candidates need no model call and retain the lexical result shape. A model failure or configuration mismatch retains lexical results, exposes an `llm:*` warning and marks the job partial. The accepted pipeline fingerprint identifies requested configuration, not proof of applied reranking, model weights or gateway routing; inspect warnings and result methods. Feedback retains that accepted pipeline version.

ANV-024 adds operator-only `ANVESHA_LLM_STRATEGY=pointwise`; the client still sends
`ranking=llm`. It grades each original prefix candidate 0–3 internally and sorts
with lexical ties. Every grade is required: one failure discards all grades.
Existing configurations remain listwise. Both use `llm_rerank`; the accepted
pipeline distinguishes the configured contract. No grades are published as
confidence or evidence scores. Invalid output keeps `llm:invalid_response` and
may add a sanitized `llm_contract:` warning: `malformed_json`, `invalid_envelope`,
`truncated_output`, `unexpected_fields`, `invalid_ids`, `unknown_ids`,
`duplicate_ids`, `incomplete_ids` or `invalid_grade`. Consumers should accept
additional warning strings and use state/methods to identify lexical fallback.

`POST /v1/searches/{id}/feedback` body:

```json
{"version":1,"result_id":null,"rating":1,"reason":"relevant","comment":"Useful","learning_opt_in":false}
```

Omit/null `result_id` for overall search feedback, or pass an ID in the referenced snapshot. `rating` must be integer -1 or 1 (booleans rejected). Optional reason: relevant, irrelevant, outdated, incorrect, wrong_locale, duplicate, inaccessible, promotional, missing_information. Comment is at most 2000 characters. Learning opt-in is a strict boolean and defaults false.

Feedback requires a published snapshot and valid result membership; invalid references return 409. There is one current rating per owner/search/version/result. Repeated submissions replace it, keeping its feedback ID. A response includes stored rating context, pipeline version and consent, never owner secrets. No training, instant boosting or blacklisting occurs. Anonymous public crowdsourced voting is not part of this MVP.

ANV-023 uses short per-request aliases for model output and maps them back to the
same public result IDs. Operators can select schema-constrained output in private
configuration; clients cannot choose its format or endpoint. Alias/prompt and
format changes affect the accepted fingerprint. Upgrade API/workers together;
older accepted LLM configurations can fall back with `llm:configuration_changed`.
Existing result snapshots and feedback remain stable. See [ADR 0008](decisions/0008-compact-reranking-identifiers.md)
and [ADR 0009](decisions/0009-opt-in-constrained-ranking-output.md).

## Cancellation and deletion

`POST /v1/searches/{id}/cancel` immediately cancels queued/running work and invalidates publication by a worker still doing external I/O. It returns status. Cancelling a terminal job is an idempotent no-op; already published results remain. It cannot recall data already sent to Wikimedia or a model endpoint. The model stage checks cancellation and renews its lease while waiting.

`DELETE /v1/searches/{id}` returns 204 and cascades the active database's job, snapshot, and feedback records. It invalidates a running worker's later publication. Missing/unowned/expired jobs return 404.

## Operational retention

New environment-based installations and setup files default to 604800 seconds
(seven days) from durable acceptance. The operator may choose an integer from 0 to
31536000 seconds; zero means indefinite. Existing jobs migrate with a null deadline.
Old saved configurations missing `retention_seconds` load as zero, regardless of
ambient environment. Policy edits affect only future searches, including when
switching back to zero. Upgrade API and workers together. See
[operator commands](PRIVATE_RESEARCH.md#search-history-retention) and
[ADR 0012](decisions/0012-private-search-retention.md).

At `now >= expires_at`, every job state becomes inaccessible, including queued or
running work. Authenticated status/results/feedback/cancel/delete return the same
404 as unknown/unowned IDs; stale `If-None-Match` cannot produce 304. Invalid request
syntax/authentication still returns its usual 422/401. Workers cannot reclaim,
renew or publish expired work. Expiry does not recall data already sent, client
copies or an in-flight model request; checkpoints stop remaining work.

The separate worker removes at most 100 expired jobs before each claim, including
idle iterations and after restart, cascading snapshots/feedback. Deletion can lag
during a long-running job or when workers are stopped; SQL access guards remain
effective. Explicit local `anvesha prune` previews one batch; `--apply` deletes it.
No extra scheduler or hosted API is required. Imported documents, configurations,
review data and model files are unaffected. Retention does not authorize training.

This is logical deletion in the active database. SQLite pages/WAL, backups and
other copies are outside that guarantee; backup cleanup and forensic erasure are
not implemented. See [SQLite's deletion limits](https://www.sqlite.org/pragma.html#pragma_secure_delete).

## Provider configuration and operational bounds

The API and worker source allowlists must agree. Enable `wikidata` explicitly and set a real `ANVESHA_WIKIDATA_USER_AGENT`. No paid keys are required. The connector makes one bounded-result English entity metadata query to a fixed host, does not follow redirects, and never fetches arbitrary result URLs. Source failures are sanitized codes such as `wikidata:missing_user_agent`, not raw response bodies.

Current live networking limits include inactivity timeouts, response-size limits, and body elapsed checks. A strict total deadline including trickling headers remains tracked in ANV-008. This is another reason not to expose the M1 worker as a public unlimited service. Default offline tests mock this connector; no live availability guarantee is implied.

The model client enforces a total async deadline including header/body waits
(default 60, maximum 120 seconds), a 64 KiB response limit per response, no redirects
and no environment proxies. It sends the original query and bounded titles/
snippets/evidence labels to a fixed operator endpoint. Listwise additionally sends
compact aliases and accepts only a complete permutation. Pointwise sends one
candidate without an ID per sequential call, accepting only an integer grade
0–3. Its at most 20 calls share one total deadline. No client can choose endpoints,
models, strategy or tools through a search request. Network destinations require
operator opt-in; a local proxy can still forward externally. Model keys are never
persisted in jobs. See [the processing policy](../policies/llm-processing.json).

Local files are a shared operator corpus, not a per-client private document store. Request lengths and result counts are bounded, but hosted quotas, backup/restore retention, production metrics and source-rights policy enforcement beyond the approved built-in connectors remain tracked work. Use loopback for the current deployment.
