# Anvesha handoff

## Objective

The user selected Anvesha, asked to save the researched plan in this repository, break it into milestones, create agent guidance, and begin an MVP with no mandatory paid APIs. The user subsequently created https://github.com/Kshurika-Consultancy/anvesha and explicitly authorized connecting this workspace, committing the plan/MVP, and pushing main (ANV-017).

## Starting state

The repository was empty apart from `.git`, on an unborn `master` branch. No inherited repository instructions were found in the initially checked user directories. No implementation or benchmark claims existed.

## Decisions

- Independently written Apache-2.0 core; no copied SearXNG code.
- Local-first SQLite WAL/FTS5 durable jobs for the first executable slice. PostgreSQL/distributed workflow remains a later scaling decision.
- Separate API and worker processes. Authenticated job ownership, idempotency, stable results, explicit failures/cancellation, and versioned feedback are in the first slice.
- Offline local retrieval is mandatory; Wikidata CC0 metadata is an optional, bounded live source. No paid services or LLM downloads are required.
- No arbitrary webpage fetching or automatic feedback training in M1.

## Implemented state

M0/M1 are delivered. The API supports authenticated submit/poll/results/feedback/cancel/delete, client-scoped idempotency and ETag polling. A separate worker uses SQLite leases with recovery/fencing and publishes one immutable final snapshot. The local corpus uses FTS5/BM25; optional Wikidata metadata is fused by deterministic RRF. Pipeline version is `m1-rrf-v1`. Feedback defaults out of learning and never automatically changes ranking.

Root integrated documentation/API/CLI/tracking, a storage agent owned SQLite/tests, a retrieval agent owned provider/ranking/worker/tests/manifests, and the documentation agent saved the research and independently reviewed code. All subagent ownership is released at this handoff; a new agent should claim its task and file scope explicitly.

Initial repository content includes root project/governance files, docs, source, tests, scripts, examples, policies, CI, and lockfile. ANV-017 published commit `c3fd2f663f051a65c5ce3a39e702f94036850912` to origin/main after the user explicitly authorized it. Local main tracks `https://github.com/Kshurika-Consultancy/anvesha.git`; local/remote commit equality was verified. A documentation follow-up records this publication. No service deployment is authorized by the publication request. `.venv`, `.anvesha` build output, temporary databases, and caches are ignored. Smoke processes were shut down.

Local Git authentication now works through Git Credential Manager after user device sign-in. Repository-scoped author configuration uses Bitthal Ladiwal's GitHub noreply identity. The separate GitHub connector still returned write 403 and an empty organization-repository list; do not assume its metadata permission flags prove connector write access. Use authenticated local Git for publication unless that connection is corrected.

## Verification

See [the verification report](verification/2026-10-16-mvp.md) for exact commands and limitations. Local Windows/Python 3.14.4 run: 116 tests passed, Ruff lint/format and tracking passed, package build passed. Real HTTP/API restart/separate worker smoke passed in both development and isolated wheel installations. Default tests do not contact network providers.

The test run emits one Starlette/httpx deprecation warning, tracked as ANV-015. Repeat pre-publication checks passed: 116 tests in 12.54 seconds, Ruff, tracking and real-process smoke. [Publication evidence](verification/2026-10-16-publication.md) records initial push verification and the first GitHub Actions run, observed in progress when the report was written. CI targets Windows/Linux and Python 3.12/3.14. No live Wikidata request was made (ANV-016); no real operator contact was provided. No quality benchmark or full-web result claim exists.

## Run locally

Use `uv sync --extra dev --locked`, then `uv run --extra dev anvesha init --seed`. Set the generated key in `ANVESHA_API_KEYS` and run `uv run --extra dev anvesha serve`. In another terminal with the same DB/source configuration, run `uv run --extra dev python -m anvesha.worker`. Full instructions are in [README](../../README.md) and [API](../API.md).

An empty environment defaults to local retrieval. The demo URLs are synthetic example.org identifiers. Imports require rights review and are visible to every client of the instance. Optional Wikidata needs explicit enablement and a real identifying User-Agent; it returns English entity metadata only.

## Next work and known limits

1. ANV-007: collect a rights-reviewed 500-query evaluation set and report coverage/relevance against baselines before adding quality claims.
2. ANV-008: quotas, automated retention, source-wide rate limits, strict total upstream deadlines, operational monitoring and key/tenant decisions. Current HTTP inactivity limits do not provide a strict deadline for trickling headers. Keep the deployment local.
3. ANV-015: migrate the test transport using upstream guidance; do not merely hide the warning.
4. ANV-016: run a bounded live Wikidata check only with actual operator contact; it is unnecessary for local operation.
5. M3+ tasks cover general fetching, hybrid models, query planning, corpus growth and controlled learning. No paid provider may become mandatory.

Before a significant follow-up, reread AGENTS, STATUS, this handoff, the relevant task, and the applicable ADR. Update the ledger and evidence rather than creating an untracked parallel checklist.
