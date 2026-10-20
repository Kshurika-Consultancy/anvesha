# ANV-026 private-search retention verification

## Decision and delivered behavior

Root selected this scoped ANV-008 privacy improvement from clean main `8e0c283` on
2026-10-20. Local ownership needs an explicit operational-data lifetime as well as
local inference. [ADR 0012](../../decisions/0012-private-search-retention.md) records
the design; [the operator guide](../../PRIVATE_RESEARCH.md#search-history-retention)
and [API contract](../../API.md#operational-retention) document actual behavior.

New setup/environment defaults persist a seven-day deadline at acceptance. Operators
can choose integer seconds 0..31536000, with zero explicitly indefinite. Saved
configuration takes precedence; old files missing the field load as zero. Additive
migration leaves old jobs' deadlines null, preserving their snapshots, feedback and
request hashes. No legacy history is deleted or backfilled automatically.

The individual deadline survives restart, polling, heartbeat, feedback, idempotent
replay and configuration changes. At expiry, all job states are hidden from valid
authenticated API operations, including conditional polling, pagination and
feedback. Worker eligibility/heartbeat/publication checks reject expired work.
In-flight processing and already returned data cannot be recalled. Expiry can end
queued or running work; it does not add a new terminal state or revive a job.

Before every claim, including idle/restart passes, a worker removes at most 100
expired jobs and cascades snapshots/feedback. An added feedback-key index supports
the cascade. Access checks work independently of cleanup, which can lag while a
worker is stopped or busy. Expired idempotency keys can accept new work under a new
ID, with atomic deletion/reuse scoped to the client. No perpetual tombstone is kept.

The local `prune` CLI defaults to a read-only URI preview; `--apply` deletes one
batch of 1..500 jobs using recorded deadlines only. Missing/legacy databases are
not created or migrated by either mode. Output contains counts, never queries,
feedback or credentials. Corpus documents, configuration, model assets and the
independent-review store are outside the deletion scope.

This is logical active-database deletion, not forensic erasure or backup/log
management. No model stage, retrieval ranking, source/data licence or free/local
inference requirement changes. Other ANV-008 hosted-hardening gates remain open.
All new data and assessments in verification are synthetic; no actual private
service database, review pilot, credentials, coaching note or labels were accessed.
No paid API, real model call or external search request was used in testing.

## Checks

```text
uv sync --extra dev --locked
uv run --extra dev ruff check .
uv run --extra dev ruff format --check .
uv run --extra dev pytest
uv run --extra dev python scripts/check_tracking.py
uv run --extra dev python scripts/smoke_mvp.py
uv run --extra dev python scripts/smoke_selfhost.py
uv run --extra dev python scripts/smoke_retention.py
uv run --extra dev python -m anvesha.evaluation verify
uv run --extra dev python -m anvesha.review_data verify
uv run --extra dev python -m anvesha.intent_evaluation verify
uv run --extra dev python -m anvesha.llm_evaluation verify
uv run --extra dev python -m anvesha.ranking_experiment verify
uv build --out-dir .anvesha/dist/anv026
git diff --check
```

Checkpoints: 92 prior Store/API/CLI/setup/worker tests passed; 37 new retention
cases passed in 10.29s. Full checkpoint: **400 passed in 68.88s**, with the existing
ANV-015 Starlette/httpx deprecation warning only. All five archived data/report
verifiers passed; published lexical fingerprints remain unchanged. After adding
the concurrent-pruner case, **401 passed in 67.42s**. Final review also made doctor
reject a database missing the new expiry column without migrating it; the focused
retention/CLI/setup suite passed 64 cases in 12.54s. Final full checks for that
correction, installed-package and publication evidence follow below after execution.

Final full suite after that correction: **401 passed in 84.09s**, including 38 new
retention cases. Ruff lint/format and tracking passed; final MVP process smoke also
passed. The self-hosting and retention process smokes passed earlier at the same
runtime behavior; installed-wheel retention acceptance below additionally exercises
the final CLI/configuration and HTTP/worker paths. No tests were skipped or real
review labels imported. The existing ANV-015 deprecation warning remains tracked.

Wheel/sdist built and inspected: six changed runtime modules match the checkout;
the new retention module and smoke script are included where appropriate. Private
workspaces, credentials, databases, model weights and executables are excluded.
A fresh venv installed the wheel with locked runtime requirements only; imports
came from site-packages and pytest was absent. The actual retention process smoke
passed from that installation, including separate HTTP/API/worker restarts,
expiry/cascade/key reuse/pruning. The venv/synthetic scratch directory was cleaned
successfully after all connections/processes closed. No owned services remain.
All 24 changed/new files are classified under ANV-026; discovery notes for ANV-027
and ANV-008 continuity are in the same ledger.

## Publication and cross-platform acceptance

`git push origin main` published
`93d14c2ef625216e1047742fc793645caf3ef0dd`; local HEAD and
`git ls-remote origin refs/heads/main` matched and Git status was clean. All five
jobs passed in [run 39427201666](https://github.com/Kshurika-Consultancy/anvesha/actions/runs/39427201666):
Windows/Linux Python 3.12/3.14 plus actual container acceptance. Each matrix job
includes the new retention smoke, full tests, archived verifiers, existing process
smokes and tracking. No real LLM, paid API or private pilot data is used. This
documentation-only evidence/rollback clarification has its own commit/run; inspect
current HEAD. No public deployment or package publication follows.

The new actual-process smoke already passed once: a saved eight-second policy,
separate real worker completion, HTTP feedback, API stop/restart with the worker
stopped, 404 for completed and queued jobs after their actual wall-clock deadlines,
ETag invalidation, unchanged retained rows before cleanup, read-only preview,
idle-worker cascading deletion, new-ID key reuse, explicit apply, preserved corpus
and owned API/worker process cleanup. It uses a temporary first-party synthetic
database and model-free lexical execution. CI now runs it in each platform matrix.

Unit regressions additionally cover all six states at the exact deadline, TTL and
batch type/range rejection, saved/environment precedence and legacy behavior,
feedback expiry between ownership/read and write, expiry during retrieval/ranking,
stale leases, bounded backlog skipping, concurrent expired-key reuse, concurrent
pruning, cascading dependent rows, unrelated corpus preservation, and
repeatable migration without changed request hashes or lost snapshots/feedback.

## Tracked follow-ups

The [storage reference review](../../RESEARCH.md#anv-026-storage-review-2026-10-20)
also identified a separate SQLite WAL-reset patch-verification gap. Local Python
reports SQLite 3.50.4; vendor patch status is unverified. ANV-027 tracks maintained
runtime/vendor evidence and remediation, not a claimed application-level fix. No
corruption was observed; passing these tests does not certify the upstream fix.

ANV-008 stays open for quotas, backup/restore retention, explicit legacy-history
backfill, identities/key rotation, metrics and other hosted controls. ANV-020 human
labels remain pending and entirely separate. The historical ignored ANV-025 scratch
folder was neither inspected nor cleaned by this task. No public service is deployed.
