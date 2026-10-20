# Anvesha development status

ANV-027 is in progress (root, 2026-10-20) from clean 95ac82a: reviewed PBS
runtime acquisition and conservative SQLite WAL/FTS5 eligibility. Local Python
3.14.8 now loads SQLite 3.53.1 with its published source identity; global Python
is unchanged. Runtime diagnostics, unsupported-runtime refusal and synthetic
multiprocess WAL/crash checks are implemented. [ADR 0013](../decisions/0013-reviewed-sqlite-runtime.md)
and [guide](../SQLITE_RUNTIME.md) document acquisition, vendor-backport and
upgrade boundaries. Local 431 tests, four process smokes,
five archived verifiers and runtime-only installed-wheel acceptance passed. Actual
cross-platform/container CI and main publication are pending; do not mark complete
from a local version probe. Actual service/review data is untouched.

ANV-026 is done and published as `93d14c2` (2026-10-20): configurable expiry for private search
jobs, snapshots and feedback, bounded worker cleanup and explicit dry-run/apply
operator pruning. New setups default to seven days; legacy saved settings/jobs
retain their existing lifetime. [ADR 0012](../decisions/0012-private-search-retention.md)
defines access, idempotency, migration and deletion boundaries. Final 401 tests,
Ruff/tracking, three process smokes, five archived artifact verifiers and isolated
runtime-only installed-wheel acceptance passed. [Evidence](verification/2026-10-20-retention.md)
records commands/limits. Local/remote main matched and all five jobs passed in
[implementation CI](https://github.com/Kshurika-Consultancy/anvesha/actions/runs/39427201666),
including the new retention process smoke and actual container acceptance. All new checks use
synthetic databases; no actual service or independent-review data is used. No owned
test services remain; new scratch cleaned. ANV-008 hosted controls remain open;
ANV-027 separately tracks SQLite runtime/vendor WAL-reset patch verification.

ANV-025's scoped safeguards are done and published as `7764642` (2026-10-18):
query-scoped coaching/exposure exclusions, blinded replacement assignments, explicit
legacy migration and current-export verification. Final full suite: 363 passed
(38 new synthetic cases), plus Ruff/tracking, both process smokes, five report
verifiers and runtime-only installed-wheel CLI acceptance. Local/remote main matched;
all five jobs passed in [implementation CI](https://github.com/Kshurika-Consultancy/anvesha/actions/runs/39142333841),
including actual container acceptance. Actual private pilot, forms, keys and labels
are untouched; ANV-020's human
study remains open. See
[ADR 0011](../decisions/0011-independent-review-exposure-and-replacement.md) and
[evidence/workflow](verification/2026-10-18-review-integrity.md). No paid API, model
call or new human judgment. No owned services; ignored synthetic package-check
scratch remains after policy-blocked cleanup, separately recorded in the evidence.

ANV-024's scoped CPU comparison is done and published (2026-10-18). Source freeze
1793f3a and results 8db584e are on main; all five jobs passed for both, including
the new offline verifier and actual container acceptance in [result CI](https://github.com/Kshurika-Consultancy/anvesha/actions/runs/39126844802).
On 16 fresh scientific queries, nDCG@10 is 0.748850 lexical / 0.743299 listwise /
0.793284 pointwise. Pointwise applies 16/16; listwise applies 13/16 with three
explicit duplicate-ID fallbacks. Paired intervals include zero: improved relevance
is not established. Pointwise stays opt-in. All 40 development/evaluation profile
runs are retained; model tree stopped, PID record removed and port closed.
325 tests and report verifiers pass. See [analysis](../../reports/evaluation/local-llm-contracts-v1/ANALYSIS.md),
[verification](verification/2026-10-18-ranking-contracts.md) and [ADR 0010](../decisions/0010-pointwise-local-ranking-experiment.md).

ANV-023's initial real local-model pilot is measured and verified (2026-10-18).
Title/descriptions identify private search for user-controlled AI tools. Free
Qwen3-4B/llama.cpp CPU inference on 24 reserved scientific queries scores 0.616925
lexical / 0.674710 LLM nDCG@10; paired 95% delta interval [-0.030015,+0.157238]
includes zero, so improvement is not established. All outcomes are retained:
19 applied / 5 invalid-output fallbacks / 0 worker failures. See [analysis](../../reports/evaluation/local-llm-pilot-v3/ANALYSIS.md)
and [verification](verification/2026-10-18-local-llm.md). Source/protocol were frozen
as 9905423 before evaluation. Owned model/preview are stopped; caches stay ignored.
Final local checks passed: 286 tests (35.81s), lint/format/tracking, process smokes,
report verifiers and package inspection. Freeze 9905423 and result c0fb6eb are pushed to main with matching remote hash;
all five jobs passed in [CI run 39119704640](https://github.com/Kshurika-Consultancy/anvesha/actions/runs/39119704640), including actual container acceptance. ANV-024 tracks reliability with fresh evaluation. ANV-023
stays in progress for actual Ollama/OmniRoute/other profiles and ANV-020 independent
domain evidence. No mandatory paid API or hosted inference.

Current direction, 2026-10-18: LLM-default private home-server research with no mandatory paid APIs. ANV-021 is published on main as `83830bf`; all four Windows/Linux CI jobs passed in [run 39109656383](https://github.com/Kshurika-Consultancy/anvesha/actions/runs/39109656383). Its bounded reranking protocol and frozen lexical fingerprints remain documented in [ANV-021 evidence](verification/2026-10-18-private-research.md).

ANV-022 is complete for its scoped browser/self-hosting slice, published as `0193557`: LLM-default API/browser requests, explicit lexical baseline, same-origin assets, private setup/configuration, native supervision and non-root Compose. The 252-test suite, Ruff/tracking, process smokes, desktop/mobile browser and isolated installed-wheel checks pass. All five CI jobs passed in [run 39111550834](https://github.com/Kshurika-Consultancy/anvesha/actions/runs/39111550834), including the actual Linux container build/restart/private-network protocol fixture. All local test services are stopped. See [guide](../PRIVATE_RESEARCH.md), [ADR 0006](../decisions/0006-llm-default-and-self-hosted-browser.md) and [evidence](verification/2026-10-18-self-hosting.md). Actual model quality/live backend acceptance remains ANV-023. M2/M3 overall gates stay open; a local gateway does not establish local downstream inference.

Current objective delivered: auditable development foundations and the first runnable, no-paid-API MVP. See [verification evidence](verification/2026-10-16-mvp.md).

Completed authorized follow-up: this workspace is connected to [Kshurika-Consultancy/anvesha](https://github.com/Kshurika-Consultancy/anvesha), and the initial plan/MVP is published on main (ANV-017). Origin tracking and the remote commit were verified; the M6 service pilot remains planned. See [publication evidence](verification/2026-10-16-publication.md).

The authoritative task state is [tasks.json](tasks.json). Milestone scope and gates are in [MILESTONES.md](../MILESTONES.md). Read [HANDOFF.md](HANDOFF.md) for operational continuity.

M0 foundations and M1 local-first asynchronous search are implemented and verified. M2 has started; ANV-019 is complete with a real SciFact corpus, inherited expert relevance annotations, and an offline evaluation harness. The 500-query scientific slice does not complete ANV-007's multi-intent and independent pool-review requirements; ANV-020 tracks those. No general-web or Google-level quality claim follows.

Implementation uses Python/FastAPI, SQLite WAL/FTS5, a separate durable worker, a locally indexed first-party demonstration corpus, and an optional Wikidata metadata connector. It needs no paid API or LLM key. Demo content is visibly identified as demonstration material. A real-process smoke test passed for both the development installation and isolated built wheel.

The first remote CI run exposed a Windows/Python 3.12 smoke cleanup failure after all assertions passed. ANV-018 fixes shutdown to stop the server process tree and adds a real descendant-process regression. All 118 tests and the smoke pass locally; all four jobs passed in [GitHub Actions run 38901376551](https://github.com/Kshurika-Consultancy/anvesha/actions/runs/38901376551) for fix commit 70216f3 (Windows/Linux, Python 3.12/3.14).

The full-corpus baseline and independent fresh-index repeat have identical rankings for all 500 queries across three systems. On the 300-query evaluation split, M1/BM25 score 0.672633 nDCG@10 and 0.866056 recall@50. All 148 local tests, Ruff checks, tracking and real-process smoke pass; installed-wheel report verification passes. Baseline commit `9ae8b2f` is published on main; all four Windows/Linux Python 3.12/3.14 jobs passed in [run 38910026463](https://github.com/Kshurika-Consultancy/anvesha/actions/runs/38910026463). See [evaluation evidence](verification/2026-10-16-evaluation.md) and [methodology](../EVALUATION.md). No paid API, hosted LLM or model download is required; only explicit dataset preparation uses the network.

The published ANV-020 slice adds 756 multilingual/intent queries, 720 real XQuAD passages in three languages, a grouped holdout, derived QA context mappings, and a private human-review workflow. Thirty-six queries are explicitly AI-authored drafts; none have fabricated relevance grades. The actual worker and lexical baselines completed all 2,268 runs, with identical fresh-index repeat rankings. A local 200-pair pilot with 42 double assignments and offline forms is prepared, with **zero new human assessments**. All 185 local tests, Ruff, tracking, real-process smoke and installed-wheel checks pass. Source commit `ac48d2e` is on main; all four Windows/Linux Python 3.12/3.14 jobs passed in [run 38936703068](https://github.com/Kshurika-Consultancy/anvesha/actions/runs/38936703068). See [workflow](../review/README.md) and [implementation evidence](verification/2026-10-16-human-review.md).

ANV-020/ANV-007 remain open for consenting independent assessors, native-speaker review, adjudicated labels, additional representative coverage, the legacy SciFact pool adapter and permitted external comparisons. Other priorities are hosted hardening/retention (ANV-008), test transport maintenance (ANV-015), and optional live Wikidata verification with a real operator contact (ANV-016). No live search-provider test has run. The runner also reports nonblocking Node action deprecations; review action versions during release maintenance (ANV-014).

Quality claims require measured evidence. Runtime failures, unsupported features, and uncovered search categories must be exposed rather than silently described as complete coverage.
