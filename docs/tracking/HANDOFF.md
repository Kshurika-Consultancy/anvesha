# Anvesha handoff

## Objective

2026-10-20 new turn: user authorized selecting the next useful improvement,
implementation/tests and main commit/push. Root selected ANV-027 from clean
95ac82a, following the concrete SQLite WAL-reset gap. Ledger marked in progress
before behavior changes. No subagents. Reviewed primary SQLite/PBS/uv sources;
previous local Python 3.14.4 loaded 3.50.4 with unverified backport status, no
observed corruption. Explicit hash-verified PBS 20261013 Python 3.14.8 acquisition
now loads SQLite 3.53.1/source c88b220; global Python/DLLs were not changed.
Project .venv was recreated by locked uv sync with the managed interpreter.

Implemented offline identity/FTS5 diagnostics, conservative upstream-fixed-release
policy and refusal before operational DB access/setup/supervisor children on an
unverified runtime. Older vendor backports have no bypass and need explicit review.
No schema/journal/ranking/review changes. Native/CI/container runtime pins, runtime
notices/provenance and ADR 0013/guide are added. Thirty focused synthetic runtime
tests (56 including CLI/selfhost) passed, as did initial 72-job multiprocess WAL/
checkpoint/crash acceptance. Full 431 tests passed in 75.33s, Ruff/format/tracking and four process smokes
passed, as did five archived report verifiers. A runtime-only installed wheel
(site-packages, pytest absent) passed actual SQLite multiprocess/crash and retention
HTTP/restart acceptance. Four changed runtime modules match the wheel; private
data/binaries are excluded. Newly owned scratch/venv/processes cleaned. Actual
Linux container/cross-platform CI acceptance and main publication are pending. Do not claim upstream race-fix
proof from application tests. Reference verification/2026-10-20-sqlite-runtime.md
for the final evidence, to be completed before handoff.

Actual service DB, private configuration/queries, review pilot/forms/credentials/
practice/labels and historical ignored ANV-025 scratch are untouched. No paid API,
provider/model call or public deployment. ANV-008 hosted/backup gates, ANV-020 human
study and ANV-014 release/update policy remain open. No owned services remain.

## Previous completed ANV-026 slice

ANV-026 added private search expiry, seven-day new-setup defaults with legacy
preservation, client/lease/publication guards and bounded cascading cleanup.
Implementation 93d14c2 and evidence follow-up 95ac82a are published on main;
all five CI jobs passed. Final 401 tests, three process smokes, report verifiers
and runtime-only installed-wheel acceptance passed. See
[retention evidence](verification/2026-10-20-retention.md) and ADR 0012. Actual
service/review data was untouched; broader ANV-008 hosted/backup gates remain open.

## Previous completed ANV-025 slice

2026-10-18 current turn: user again authorized choosing the next useful step,
implementation, tests, commit and push. Root delivered scoped ANV-025 from clean
ad024d5: enforce the known ANV-020 coaching-exclusion gap before collecting broader
domain evidence. [ADR 0011](../decisions/0011-independent-review-exposure-and-replacement.md)
records query-level exclusions, preserved assignment slots, blinded replacement,
explicit transactional migration and consistent immutable exports/current verifier.
Final full suite: 363 passed in 56.73s (38 new synthetic cases, existing ANV-015
warning only). Ruff/format/tracking, both real-process smokes, all five artifact
verifiers and runtime-only installed-wheel actual CLI workflow pass. See
[verification](verification/2026-10-18-review-integrity.md). No actual pilot file,
form, credential, label or private practice note was read/changed. All owned test
processes ended. No model call, delegation or mandatory paid API. Ignored synthetic
installed-wheel scratch remains after automatic approval rejected cleanup as
"blocked by policy"; it contains no real pilot data and is excluded from Git/packages.
Implementation is published as `7764642a7f13ddf68adaadd02d1327eceeecdb3d` with
matching local/remote main and clean Git state. All five jobs passed in
[CI run 39142333841](https://github.com/Kshurika-Consultancy/anvesha/actions/runs/39142333841),
including Windows/Linux Python 3.12/3.14 and actual container acceptance. Root
ownership of this completed scoped slice is released. This documentation-only
evidence follow-up has its own commit/CI; inspect current HEAD. Keep ANV-020 open:
operator must explicitly migrate the actual pilot, record known
query-wide practice exclusions, enroll eligible replacements and collect real
labels. No credentials/attestation can prove actual human independence.

## Previous completed ANV-024 slice

2026-10-18: user authorized selecting the next useful step, implementation, tests,
commit and push. Root implemented ANV-024 from clean main 536fc75. Source/protocol
freeze `1793f3a41ecb5555cf67ab0dd0f5ec4fec1ffb2b` is pushed to main; all five jobs
passed in [source CI](https://github.com/Kshurika-Consultancy/anvesha/actions/runs/39122584748).
Results/evidence commit `8db584e125bc2e0ffb362153a56ddaf3471829b9` is also pushed;
local/remote hashes matched and worktree was clean. All five jobs passed in
[result CI](https://github.com/Kshurika-Consultancy/anvesha/actions/runs/39126844802),
including the new offline comparison verifier and actual container acceptance.
This scoped task is complete; root ownership is released at this handoff.
No subagents or mandatory paid APIs/hosted inference were used.

The actual Qwen3/llama.cpp CPU comparison completed all 4 development + 16 fresh
evaluation queries under both contracts (40 query/profile runs). Source/protocol
were frozen before inference; all nine measured files still match the freeze.
Evaluation nDCG@10: 0.748850 lexical, 0.743299 listwise, 0.793284 pointwise.
Pointwise: 16 applied, zero fallback/failure; listwise: 13 applied, three duplicate-ID
fallbacks, zero worker failures. Pointwise-minus-lexical delta is +0.044433 with
95% interval [0.000000,+0.124450]; pointwise-minus-listwise +0.049984 with interval
[-0.069250,+0.203888]. Improvement is not established. Pointwise stays opt-in;
existing listwise configurations/fingerprints remain stable. No private queries,
feedback or independent-review workspaces were used; zero new human judgments.

[Analysis](../../reports/evaluation/local-llm-contracts-v1/ANALYSIS.md), summary,
complete ID rankings and allowlisted execution/resources are public artifacts.
[ADR 0010](../decisions/0010-pointwise-local-ranking-experiment.md) records limits.
Do not tune on released ANV-023/024 samples and call another run unseen. Follow-ups
are ANV-010 controlled retrieval/ranking and semantic robustness, ANV-020 independent
domain judgments, and ANV-023 actual other backends/hardware; no default promotion.

All model/development/evaluation sessions are complete. The verified owned model
tree was stopped, matching PID record removed, port 8135 closed. Historical PIDs
1108/25156 must not be reused. Runtime/weights and resource/checkpoint files remain
ignored under `.anvesha/local-llm/anv023` and `.anvesha/evaluation/local-llm-contracts-v1`.
Reproduce into fresh ignored paths using docs/LOCAL_LLM_EVALUATION.md; public output
refuses overwrite. No model download or inference is needed for ordinary checks.

Final pytest: 325 passed in 38.49s (existing ANV-015 warning). Lint/format and all
archived/new report verifiers pass with the model stopped. Before inference both
process smokes and the runtime-only isolated installed-wheel schema/pointwise
smoke passed. Both final process smokes and package/archive inspection also pass;
all nine measured wheel Python files match source, three browser assets are
included and private caches/config/data/weights/binaries excluded. ANV-024 is done
for this scoped comparison; new follow-ups are recorded in ANV-010. New CI step
verifies the comparison offline. No model/test services or review submissions
remain. This documentation-only evidence follow-up can have its own CI run;
inspect current HEAD. Next work is the existing ANV-010/020/023 scope above.
See [verification](verification/2026-10-18-ranking-contracts.md).

## Previous completed ANV-023 slice

2026-10-18: user authorized ANV-023 real local-model comparison, private/user-owned
tooling title/description and commit/push to main. This scoped pilot is delivered/published; root ownership is released at handoff. No
subagents used. Starting HEAD a7eb810 was clean. README/API/browser/package and
GitHub About identify Private Search for Your Own AI Tools; research, coding,
IoT/assets and private agents/chat are intended integrations, not implemented apps.

The actual frozen v3 pilot is complete: 4 development + 24 reserved evaluation
queries over all 5,183 SciFact documents. Results are under
`reports/evaluation/local-llm-pilot-v3` (ANALYSIS, summary, rankings, execution).
Evaluation nDCG@10: 0.616925 lexical / 0.674710 LLM; paired delta +0.057786 with
95% interval [-0.030015,+0.157238]. Improvement is not established. All queries
retained: 19 applied, 5 invalid-output lexical fallbacks, 0 worker failures;
3 wins / 20 ties / 1 regression. Recall@50 stays 0.812500. These are inherited
expert scientific labels, zero new Anvesha human judgments. Never tune on the
released sample and call another run unseen. ANV-024 is planned from development
contract failures; use fresh evaluation. ANV-020 broader independent evidence and
actual Ollama/OmniRoute/other model/hardware profiles remain open under ANV-023.

Model: Qwen3-4B-Instruct-2507 Q4_K_M, verified official registry GGUF; runtime MIT
llama.cpp b11669, CPU-only, 6 threads, context 8192, seed 20261018, loopback/offline,
no tools/web UI/MCP proxy or prompt logs. Exact pins/rights: policies/models.
Source/protocol committed as `9905423457d0ed3e9395948aa286d6c74afc3332` before
evaluation release. All eight measured source files still match that commit.
v1/v2 development failures and protocols are retained; neither released evaluation.
The source base revision captured before development was a7eb810; per-file hashes
identify actual evaluated code. No inference used private queries or review data.

All evaluation/supervisor sessions are finished. Model PID 21908/tree stopped;
preview PID 21268 stopped/tab closed. A no-inference launcher restart/cleanup check
also passed (owned PID 22212 stopped): launcher now removes its matching PID record.
Ports 8135/8140 are closed. Do not act on historic PIDs. Verified binaries/weights
remain ignored under `.anvesha/local-llm/anv023`; no system install/public service.
Checkpoint is under `.anvesha/evaluation/local-llm-pilot-v3`; public reports refuse
overwrite. Reproduce into fresh ignored paths using docs/LOCAL_LLM_EVALUATION.md.

Pre-release: 286 tests (47.60s), Ruff/tracking/diff, MVP/native schema smokes,
focused browser copy, build/archive exclusions, unchanged archived lexical
verifiers and runtime-only isolated installed-wheel native/schema smoke passed.
New offline model-report verifier passed with the actual model stopped. See
`docs/tracking/verification/2026-10-18-local-llm.md` for resource/quality evidence.
Screenshot `.anvesha/anv023-branding-desktop.png` is ignored, no viewport override.
Final local checks also pass: 286 tests (35.81s), Ruff/tracking/diff, all artifact
verifiers, both process smokes and rebuilt package/archive inspection. Result commit c0fb6ebf2dc077c6713324db96c599b840cd9bb9 and freeze 9905423 are
pushed to main; local/remote hashes matched and the worktree was clean. All five jobs in CI run
39119704640 passed (Windows/Linux 3.12/3.14 plus actual container build/private
fixture/restart/cleanup). New offline report checks passed without model weights.
This documentation follow-up has its own workflow; inspect final HEAD as needed.
The working objective is complete for this initial pilot/publication slice. Next
is ANV-024 reliability/fresh evaluation and the remaining ANV-020/ANV-023 gates.
No active services, pending inference or independent review submissions remain.

The user selected Anvesha, asked to save the researched plan in this repository, break it into milestones, create agent guidance, and begin an MVP with no mandatory paid APIs. The user subsequently created https://github.com/Kshurika-Consultancy/anvesha and explicitly authorized connecting this workspace, committing the plan/MVP, and pushing main (ANV-017).

Current request delivered, 2026-10-18: publish ANV-021, build ANV-022 browser/easy self-hosting and make LLM default. ANV-021 is on main as `83830bf4ace6df5702a5921f17ef3d37f991fa91`, with four CI jobs passed. ANV-022 is on main as `0193557c109939b032fafbc28eaddc60aac19d5b`, with all five jobs in Actions run 39111550834 passed, including real Docker installation/restart/private chat connectivity. Local/remote hashes matched after each push. A documentation follow-up records completion; check its own Actions run separately if assessing current HEAD. ANV-023 owns actual backend/model quality. No delegation or public service is active. ANV-020 independent review remains open and separate.

## Starting state

The repository was empty apart from `.git`, on an unborn `master` branch. No inherited repository instructions were found in the initially checked user directories. No implementation or benchmark claims existed.

## Decisions

- Independently written Apache-2.0 core; no copied SearXNG code.
- Local-first SQLite WAL/FTS5 durable jobs for the first executable slice. PostgreSQL/distributed workflow remains a later scaling decision.
- Separate API and worker processes. Authenticated job ownership, idempotency, stable results, explicit failures/cancellation, and versioned feedback are in the first slice.
- Offline local retrieval is mandatory; Wikidata CC0 metadata is an optional, bounded live source. No paid services or LLM downloads are required.
- No arbitrary webpage fetching or automatic feedback training in M1.

## Implemented state

ANV-022 completed state: new API requests default to LLM; missing model configuration
rejects before acceptance and explicit lexical still works offline. Existing
accepted jobs/evaluation helper defaults remain lexical. Packaged browser assets
at `/` cover authentication, submit/poll/cancel, stable pagination and feedback
with learning off. No external assets or browser storage are used; interactive
CDN docs are disabled while OpenAPI remains. `setup` writes exclusive private
JSON, `show-key` displays the client key locally, `start` supervises separate
API/worker processes, and individual service commands support containers.
See [ADR 0006](../decisions/0006-llm-default-and-self-hosted-browser.md) and
[self-hosting evidence](verification/2026-10-18-self-hosting.md). Local 252-test
suite, Ruff/tracking/diff checks and both process smokes pass. Browser checks,
wheel/sdist inspection and isolated runtime-only installed-wheel native smoke
also pass. All preview/smoke services are stopped and browser viewport restored.
Linux Docker CI and all four matrix jobs passed. Never serve the separate
private review form or treat synthetic operational feedback as human assessment.

ANV-021 is published and verified for its scoped preview: bounded Ollama/OmniRoute chat wire contract, strict candidate permutations, total deadlines, lease/cancellation checks and visible lexical fallback. Heartbeat I/O does not block the async deadline. The additive ranking column retains old jobs/snapshots/feedback. Accepted fingerprints bind configured identifiers/prompt/bounds, not verified weights or routes. Its original opt-in default is superseded by ANV-022/ADR 0006. Historic ANV-021 checks: 240 tests, Ruff/tracking, development/installed-wheel process smoke and both full fresh lexical benchmark repeats with unchanged fingerprints. See [evidence](verification/2026-10-18-private-research.md). Coaching guidance/private practice records remain intact.

M0/M1 are delivered. The API supports authenticated submit/poll/results/feedback/cancel/delete, client-scoped idempotency and ETag polling. A separate worker uses SQLite leases with recovery/fencing and publishes one immutable final snapshot. The local corpus uses FTS5/BM25; optional Wikidata metadata is fused by deterministic RRF. Pipeline version is `m1-rrf-v1`. Feedback defaults out of learning and never automatically changes ranking.

ANV-019 adds evaluation modules only; production retrieval is unchanged. `benchmarks/scifact-v1` contains 500 real scientific queries (200 development, 300 evaluation), 569 published evidence judgments and the full corpus's 5,183 IDs. Explicit `python -m anvesha.evaluation prepare --download` pins the reviewed BEIR archive and leaves raw abstracts in ignored `.anvesha/evaluation/scifact-v1`. `run --export-pool` compares token overlap, direct FTS5/BM25 and the actual M1 local worker, writes public metrics/ID rankings under `reports/evaluation/scifact-v1`, and creates an ignored blinded pool with blank assessor fields. `verify` needs no raw abstracts or network. See [methodology](../EVALUATION.md), [ADR 0003](../decisions/0003-published-retrieval-evaluation.md), and [evaluation verification](verification/2026-10-16-evaluation.md). Byte-hashed fixtures use explicit Git LF attributes.

ANV-020 implementation: `review_data.py` prepares pinned XQuAD sources, 720 translated query instances/passages (en/es/hi) plus 36 unjudged AI-authored intent probes. All article translations share development/holdout assignment. `intent_evaluation.py` runs actual M1/BM25/token overlap, keeps QA answer-context mappings separate from human labels, publishes ID-only reports and writes an ignored versioned candidate pool. `review.py` manages private SQLite assignments, credentials, attestation/packet checks, atomic revision-safe labels, import receipts, abstentions, per-reviewer-pair agreement and separate adjudication. `review_form.py` exports a standalone text-only offline form. It neither changes production search/feedback nor trains a model. See [ADR 0004](../decisions/0004-multilingual-corpus-and-human-review.md), [review workflow](../review/README.md) and [implementation evidence](verification/2026-10-16-human-review.md).

Local pilot at `.anvesha/reviews/xquad-intents-v1` has 200 development pairs across 52 English queries, 42 double-assigned pairs, and 242 assignments split between placeholder pseudonyms. Two reviewer forms are exported. No people have been enrolled/contacted; zero labels or import receipts exist. Verify consent/identity/language competence privately before distributing packets and separate credentials. Never copy credentials, reviewer identity mappings, raw passages or responses into Git or handoff notes. Old SciFact `review-pool.jsonl` is not silently converted into the new session format.

2026-10-18 follow-up: the user opened Reviewer A's form and requested coaching on its first three items without submission. Their private practice-only records are in `.anvesha/reviews/xquad-intents-v1/practice/coaching-exclusions.json`; they contain identifiers and disposition, no grade or copied passage. Do not count those assessor/items as independent or import an assistant's suggested rationale. The original packet and review database remain unchanged, with zero submissions; SHA-256 comparisons confirmed this after recording the third practice item. ANV-025 implements enforced exclusions/replacement, but does not migrate or read this real pilot/operator note as a development side effect. A trusted operator must explicitly migrate, map those item IDs to query IDs, record Reviewer A's query-wide exclusions and arrange an unexposed assessor before finalizing independent results. Leave affected rows pending. No actual form submission or import follows from implementing the safeguards.

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

For ANV-020, use `python -m anvesha.review_data prepare --download`, `python -m anvesha.intent_evaluation run`, and the commands in [the review workflow](../review/README.md). The local pilot above already exists; `review init` correctly refuses overwrite. Under ANV-025 its v1 workspace needs explicit `review migrate` and declared coaching exclusions before resuming independent work. Then use `review status` and `review export --reviewer reviewer-a` (or reviewer-b); obtain eligible replacement judgments for excluded slots and verify exports before use. New study batches use a different `--workspace`. Explicit `--split holdout --release-holdout` is required to assign held-out queries. Only corpus preparation downloads the fixed public files; report verification/default tests are offline.

Use `uv sync --extra dev --locked`, then `uv run anvesha setup --model YOUR_INSTALLED_MODEL --seed-demo`, `uv run anvesha show-key` privately, and `uv run anvesha start`. Open the browser at loopback port 8000. `setup --lexical-only` plus an explicit lexical request/select is the model-free path. Full native/Compose/import/upgrade instructions are in [the guide](../PRIVATE_RESEARCH.md), [README](../../README.md) and [API](../API.md).

The source defaults to local, but the HTTP ranking default is now LLM and needs model configuration. Explicit lexical mode works offline. Demo URLs are synthetic example.org identifiers. Imports require rights review and are shared by every client. Optional Wikidata needs explicit enablement, a real identifying User-Agent and explicit lexical ranking; it returns English entity metadata only.

## Next work and known limits

Next is ANV-024 ranking reliability/fresh evaluation and the remaining ANV-023 backend/model profiles. ANV-022's actual Linux container CI passed despite Docker being unavailable locally; no real Ollama/OmniRoute or model weights were exercised. Broader source coverage needs ANV-009/ANV-011. A local gateway does not establish local inference. The browser is self-hosted; CDN-backed docs are disabled. ANV-021/ANV-022 do not complete M2/M3 overall quality gates. Refresh pinned image digests and action versions during ANV-014 release maintenance.

1. Continue ANV-020 with native-speaker review, real consenting independent assessments, adjudication/agreement, permitted external baselines, more representative current-web/locale inputs and a legacy SciFact pool adapter. The existing pilot is ready for private enrollment and packet distribution by an authorized operator. Existing SciFact/XQuAD annotations are not new Anvesha human judgments. Retain source baselines and do not tune on holdout data.
2. ANV-008: quotas, automated retention, source-wide rate limits, strict total upstream deadlines, operational monitoring and key/tenant decisions. Current HTTP inactivity limits do not provide a strict deadline for trickling headers. Keep the deployment local.
3. ANV-015: migrate the test transport using upstream guidance; do not merely hide the warning.
4. ANV-016: run a bounded live Wikidata check only with actual operator contact; it is unnecessary for local operation.
5. M3+ tasks cover general fetching, hybrid models, query planning, corpus growth and controlled learning. No paid provider may become mandatory.

Before a significant follow-up, reread AGENTS, STATUS, this handoff, the relevant task, and the applicable ADR. Update the ledger and evidence rather than creating an untracked parallel checklist.
