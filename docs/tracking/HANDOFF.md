# Anvesha handoff

## Objective

The user selected Anvesha, asked to save the researched plan in this repository, break it into milestones, create agent guidance, and begin an MVP with no mandatory paid APIs. The user subsequently created https://github.com/Kshurika-Consultancy/anvesha and explicitly authorized connecting this workspace, committing the plan/MVP, and pushing main (ANV-017).

Current request: start ANV-020, expand beyond scientific evaluation and build the human-review workflow, keep tracking current, and commit/push main with no mandatory paid APIs. ANV-020 is in progress and owned by root; actual independent assessments cannot be manufactured by implementation. ANV-007 also remains in progress. No delegation is active in this turn.

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

ANV-019 adds evaluation modules only; production retrieval is unchanged. `benchmarks/scifact-v1` contains 500 real scientific queries (200 development, 300 evaluation), 569 published evidence judgments and the full corpus's 5,183 IDs. Explicit `python -m anvesha.evaluation prepare --download` pins the reviewed BEIR archive and leaves raw abstracts in ignored `.anvesha/evaluation/scifact-v1`. `run --export-pool` compares token overlap, direct FTS5/BM25 and the actual M1 local worker, writes public metrics/ID rankings under `reports/evaluation/scifact-v1`, and creates an ignored blinded pool with blank assessor fields. `verify` needs no raw abstracts or network. See [methodology](../EVALUATION.md), [ADR 0003](../decisions/0003-published-retrieval-evaluation.md), and [evaluation verification](verification/2026-10-16-evaluation.md). Byte-hashed fixtures use explicit Git LF attributes.

ANV-020 implementation: `review_data.py` prepares pinned XQuAD sources, 720 translated query instances/passages (en/es/hi) plus 36 unjudged AI-authored intent probes. All article translations share development/holdout assignment. `intent_evaluation.py` runs actual M1/BM25/token overlap, keeps QA answer-context mappings separate from human labels, publishes ID-only reports and writes an ignored versioned candidate pool. `review.py` manages private SQLite assignments, credentials, attestation/packet checks, atomic revision-safe labels, import receipts, abstentions, per-reviewer-pair agreement and separate adjudication. `review_form.py` exports a standalone text-only offline form. It neither changes production search/feedback nor trains a model. See [ADR 0004](../decisions/0004-multilingual-corpus-and-human-review.md), [review workflow](../review/README.md) and [implementation evidence](verification/2026-10-16-human-review.md).

Local pilot at `.anvesha/reviews/xquad-intents-v1` has 200 development pairs across 52 English queries, 42 double-assigned pairs, and 242 assignments split between placeholder pseudonyms. Two reviewer forms are exported. No people have been enrolled/contacted; zero labels or import receipts exist. Verify consent/identity/language competence privately before distributing packets and separate credentials. Never copy credentials, reviewer identity mappings, raw passages or responses into Git or handoff notes. Old SciFact `review-pool.jsonl` is not silently converted into the new session format.

This ANV-020 implementation slice is committed/pushed as `ac48d2e6c3897a34cc2e9516358acc77d663d93f`; local/remote main equality was checked. All four Windows/Linux Python 3.12/3.14 jobs passed in [run 38936703068](https://github.com/Kshurika-Consultancy/anvesha/actions/runs/38936703068). Local verification: 185 tests (37 new), Ruff, tracking, offline smoke, installed-wheel workflow/report checks and identical fresh-index repeat rankings. No smoke servers remain. A documentation follow-up records this evidence and has its own Actions run. ANV-020 stays in progress because implementation is not the same as actual independent assessment.

Root integrated documentation/API/CLI/tracking, a storage agent owned SQLite/tests, a retrieval agent owned provider/ranking/worker/tests/manifests, and the documentation agent saved the research and independently reviewed code. All subagent ownership is released at this handoff; a new agent should claim its task and file scope explicitly.

Initial repository content includes root project/governance files, docs, source, tests, scripts, examples, policies, CI, and lockfile. ANV-017 published commit `c3fd2f663f051a65c5ce3a39e702f94036850912` to origin/main after the user explicitly authorized it. Local main tracks `https://github.com/Kshurika-Consultancy/anvesha.git`; local/remote commit equality was verified. A documentation follow-up records this publication. No service deployment is authorized by the publication request. `.venv`, `.anvesha` build output, temporary databases, and caches are ignored. Smoke processes were shut down.

Local Git authentication now works through Git Credential Manager after user device sign-in. Repository-scoped author configuration uses Bitthal Ladiwal's GitHub noreply identity. The separate GitHub connector still returned write 403 and an empty organization-repository list; do not assume its metadata permission flags prove connector write access. Use authenticated local Git for publication unless that connection is corrected.

## Verification

See [the verification report](verification/2026-10-16-mvp.md) for exact commands and limitations. Local Windows/Python 3.14.4 run: 116 tests passed, Ruff lint/format and tracking passed, package build passed. Real HTTP/API restart/separate worker smoke passed in both development and isolated wheel installations. Default tests do not contact network providers.

The test run emits one Starlette/httpx deprecation warning, tracked as ANV-015. Repeat pre-publication checks passed: 116 tests in 12.54 seconds, Ruff, tracking and real-process smoke. [Publication evidence](verification/2026-10-16-publication.md) records initial push verification and the first GitHub Actions run, observed in progress when the report was written. CI targets Windows/Linux and Python 3.12/3.14. No live Wikidata request was made (ANV-016); no real operator contact was provided. No quality benchmark existed at that earlier M1 checkpoint; the scoped ANV-019 evaluation is described above. No full-web result claim exists.

Subsequent initial CI result: three matrix jobs passed; Windows/Python 3.12 smoke cleanup failed with a log sharing violation. ANV-018 fixes parent-only Windows termination by stopping the process tree. A real Windows child-process/log-handle regression and full local checks pass (118 tests, one existing warning). Smoke success output now occurs after cleanup. Fix commit `70216f31502ab3f60741cbd91997ada2fb8d859f` passed all four Windows/Linux and Python 3.12/3.14 jobs in [run 38901376551](https://github.com/Kshurika-Consultancy/anvesha/actions/runs/38901376551). Later documentation-only commits may have their own Actions runs; check current main before claiming their state.

ANV-019 is complete: 30 evaluation tests and 148 full-suite tests pass; Ruff lint/format, tracking, `git diff --check` and real-process smoke pass. The frozen-code full-corpus run and an independent fresh-index repeat have identical rankings for all 500 queries and three systems (fingerprint `6098bc1981e868bc5b7f0cf055f27b42ba717c5a185889caeb628b20b5ef65ef`). M1/direct BM25 evaluation nDCG@10 is 0.672633 and recall@50 is 0.866056. Package build and installed-wheel artifact verification pass. Source commit `9ae8b2f7fa3141f9727e0477dd32379f4e7dc356` is pushed to main and its local/remote hashes matched. All four Windows/Linux Python 3.12/3.14 jobs passed in [run 38910026463](https://github.com/Kshurika-Consultancy/anvesha/actions/runs/38910026463), including offline artifact verification. A documentation follow-up records this evidence; check that commit's separate Actions run before claiming current-HEAD CI. No smoke servers remain running.

## Run locally

For ANV-020, use `python -m anvesha.review_data prepare --download`, `python -m anvesha.intent_evaluation run`, and the commands in [the review workflow](../review/README.md). The local pilot above already exists; `review init` correctly refuses overwrite. Use `review status` and `review export --reviewer reviewer-a` (or reviewer-b) to resume without labels. New study batches use a different `--workspace`. Explicit `--split holdout --release-holdout` is required to assign held-out queries. Only corpus preparation downloads the fixed public files; report verification/default tests are offline.

Use `uv sync --extra dev --locked`, then `uv run --extra dev anvesha init --seed`. Set the generated key in `ANVESHA_API_KEYS` and run `uv run --extra dev anvesha serve`. In another terminal with the same DB/source configuration, run `uv run --extra dev python -m anvesha.worker`. Full instructions are in [README](../../README.md) and [API](../API.md).

An empty environment defaults to local retrieval. The demo URLs are synthetic example.org identifiers. Imports require rights review and are visible to every client of the instance. Optional Wikidata needs explicit enablement and a real identifying User-Agent; it returns English entity metadata only.

## Next work and known limits

1. Continue ANV-020 with native-speaker review, real consenting independent assessments, adjudication/agreement, permitted external baselines, more representative current-web/locale inputs and a legacy SciFact pool adapter. The existing pilot is ready for private enrollment and packet distribution by an authorized operator. Existing SciFact/XQuAD annotations are not new Anvesha human judgments. Retain source baselines and do not tune on holdout data.
2. ANV-008: quotas, automated retention, source-wide rate limits, strict total upstream deadlines, operational monitoring and key/tenant decisions. Current HTTP inactivity limits do not provide a strict deadline for trickling headers. Keep the deployment local.
3. ANV-015: migrate the test transport using upstream guidance; do not merely hide the warning.
4. ANV-016: run a bounded live Wikidata check only with actual operator contact; it is unnecessary for local operation.
5. M3+ tasks cover general fetching, hybrid models, query planning, corpus growth and controlled learning. No paid provider may become mandatory.

Before a significant follow-up, reread AGENTS, STATUS, this handoff, the relevant task, and the applicable ADR. Update the ledger and evidence rather than creating an untracked parallel checklist.
