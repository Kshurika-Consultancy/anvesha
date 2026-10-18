# ANV-024 ranking-contract evidence, 2026-10-18

The user authorized analysis, implementation, tests and commit/push to main.
Starting tree: clean main `536fc75`. Root owns this slice; no subagents.

## Decision and implemented boundary

The first pilot exposed unusable listwise output and uncertain relevance gain.
Before source/model/agent expansion, compare smaller ordinal outputs with the
existing contract. [ADR 0010](../../decisions/0010-pointwise-local-ranking-experiment.md)
records the alternatives and limits. The production client supports opt-in
pointwise grading with stable lexical ties, all-or-nothing fallback, one shared
deadline, inter-candidate cancellation and closed-vocabulary structural warnings.
Saved configuration round-trips strategy; old listwise fingerprints stay stable.
The native smoke exercises actual separate processes, loopback schema transport,
restart persistence, strategy-bound feedback and cleanup using synthetic data.

## Source/protocol freeze

[Protocol](../../../benchmarks/local-llm-contracts-v1/protocol.json) fixes four
development and 16 evaluation queries with no prior pilot IDs, selected by hash
without labels/scores. Original corpus/rights/model/runtime are unchanged. Both
contracts use the same candidates and 120-second total deadline. Pointwise uses
at most 20 sequential calls with 32 output tokens each; listwise one with 1,536.
Profile order alternates per query. These differences form the contract treatment.
Source/protocol `1793f3a41ecb5555cf67ab0dd0f5ec4fec1ffb2b` preceded inference and
was pushed with remote equality. All five jobs passed in [source CI run 39122584748](https://github.com/Kshurika-Consultancy/anvesha/actions/runs/39122584748).
The measurements below were collected afterwards without changing measured code,
model, prompts, settings or selected IDs. All nine source hashes match the freeze.

## Verification before inference

- `uv sync --extra dev --locked`: pinned environment current.
- `uv run --extra dev ruff check .`: passed.
- `uv run --extra dev ruff format --check .`: 88 files formatted.
- `uv run --extra dev pytest`: 325 passed in 49.31s; existing ANV-015 transport warning.
- After a small experiment-verifier helper change, its nine focused tests passed.
- `uv run --extra dev python scripts/check_tracking.py`: passed.
- `uv run --extra dev python scripts/smoke_mvp.py`: passed, offline listwise/lifecycle.
- `uv run --extra dev python scripts/smoke_selfhost.py`: passed, offline saved
  schema/pointwise native processes, stable snapshot, feedback and cleanup.
- Archived SciFact, intent and ANV-023 model report verification: passed. The two
  lexical ranking fingerprints remain unchanged. `git diff --check`: passed.

Tests include invalid/noninteger/extra/truncated outputs, ignored/unsupported
schemas, hostile snippets, no tools/URL or ID fields, total rather than per-call
deadlines, cancellation/deletion/lease replacement, lease renewal across calls,
configuration drift, exact lexical fallback, source/tail preservation, fresh
label-blind selection, complete profile accounting and checkpoint drift/resume.
Mocked hostile content does not establish model immunity to semantic injection.

## Continue without losing context

Start `scripts/serve_local_llm_pilot.py --serve` explicitly using the existing
verified cache. Run `python -m anvesha.ranking_experiment run --run-local-model
--backend-info .anvesha/local-llm/anv023/backend-info.json` for development only,
then the same command with `--release-evaluation --resume` without tuning.
The checkpoint is ignored under `.anvesha/evaluation/local-llm-contracts-v1`.
Public output belongs in `reports/evaluation/local-llm-contracts-v1`; it must not
contain raw snippets, model outputs/reasoning, private user/reviewer information.
Retain all fallbacks, verify offline, document uncertainty and stop the owned
model process tree. No mandatory paid API, provider change or new model download.

## Completed real-model comparison

All 40 planned query/profile runs completed: four development and 16 reserved
evaluation queries under both contracts, complete 5,183-document corpus. Four
development listwise calls and 80 pointwise calls all validated. Evaluation was
explicitly released only afterwards with the same source/profile. No human-review
workspace, coached practice, private user query or production feedback was used.
There are zero new human judgments; labels are inherited public expert annotations.

Evaluation nDCG@10: lexical 0.748850, listwise with actual fallback 0.743299,
pointwise 0.793284. Pointwise-minus-lexical delta +0.044433, 95% interval
[0.000000,+0.124450]; pointwise-minus-listwise +0.049984, interval
[-0.069250,+0.203888]. Neither establishes improved relevance. Pointwise has two
wins, 14 ties, zero nDCG losses against lexical; ties need not mean identical
rankings. Listwise has three wins, 11 ties and two losses. Keep the default unchanged.

Pointwise applies 16/16, listwise 13/16 plus three `duplicate_ids` fallbacks; no
worker failures. All failed listwise cases retain exact lexical results. The
experiment made 20 listwise / 400 pointwise calls including development. Median/
p95 evaluation worker time is 90.510/100.319s listwise, 80.983/84.712s pointwise.
Full results, caveats and rights are in [analysis](../../../reports/evaluation/local-llm-contracts-v1/ANALYSIS.md),
[summary](../../../reports/evaluation/local-llm-contracts-v1/summary.json),
[rankings](../../../reports/evaluation/local-llm-contracts-v1/rankings.jsonl) and
[execution](../../../reports/evaluation/local-llm-contracts-v1/execution.json).

Main-server process lifetime peak: 13,190,733,824 bytes (~12.29 GiB), including
development. Evaluation window: 2,931.320 wall seconds / 15,380.641 main-process CPU
seconds. Runtime children, worker/indexer and OS excluded; shared machine, not total
resource, minimum-hardware or energy measurement. Four main-process observations
found loopback listeners and zero non-loopback established connections; this is not
whole-tree packet capture or an anonymity attestation. Cached verified model/runtime
were reused: no new download, paid API, hosted inference or route/provider fallback.

After report verification, the exact owned executable/PID was checked and its
process tree stopped. Launcher exited successfully, matching PID record removed
and port 8135 closed. Historical PIDs must not be reused. All real-model sessions
finished; ignored caches/checkpoints remain available for explicit reproduction.

Final `pytest`: 325 passed in 38.49s, existing ANV-015 warning only. Ruff lint/format
and archived/new report verifiers pass with the model stopped. Final process
smokes also passed: real MVP listwise HTTP/lifecycle and native saved-schema/
pointwise/restart/feedback/cleanup. Runtime-only installed-wheel native smoke
passed with imports from site-packages and 18 locked runtime packages; no dev
dependencies or real model were needed. Final build/archive inspection passed:
93,649-byte wheel, 862,759-byte sdist at that checkpoint, all nine measured Python
files identical to source, three browser assets present, source report included,
private caches/configuration/databases/weights/binaries excluded. Tracking and
`git diff --check` passed. Publication/remote CI evidence follows after push.

Follow-ups remain in existing tasks: ANV-010 controlled ranking/retrieval and
semantic injection/calibration studies, ANV-020 independent domain judgments,
ANV-023 actual other model/backend/hardware profiles. Fresh studies must exclude
the released ANV-023/024 samples when claiming a new project reserve. No default
promotion or cross-domain quality claim follows from this pilot.
