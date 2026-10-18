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
The source/protocol commit must precede inference. Real execution is pending at
this freeze, so no new validity, relevance or latency measurement is claimed here.

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
