# ANV-027 SQLite runtime verification

## Scope and primary evidence

Selected from clean main `95ac82a` on client date 2026-10-20. Root owns the slice;
no delegation. This closes the concrete runtime gap discovered during ANV-026,
before adding more retrieval behavior on the durable WAL queue. It does not
claim improved relevance or public-service readiness.

- [SQLite WAL-reset advisory](https://www.sqlite.org/wal.html#walresetbug): narrow
  concurrent reset/checkpoint race; fixed upstream 3.51.3+, backports 3.44.6/3.50.7.
- [PBS 20260414 declaration](https://github.com/astral-sh/python-build-standalone/blob/20260414/pythonbuild/downloads.py):
  the old pinned uv runtime list declared SQLite 3.50.4. A Python minor label
  alone did not establish a fix.
- [PBS 20261013 dependency declaration](https://github.com/astral-sh/python-build-standalone/blob/20261013/pythonbuild/downloads.json),
  [Windows builder](https://github.com/astral-sh/python-build-standalone/blob/20261013/cpython-windows/build.py)
  and [release artifacts](https://github.com/astral-sh/python-build-standalone/releases/tag/20261013):
  maintained Python builds with SQLite 3.53.1; public archive SHA-256s recorded
  independently in the checked-in uv metadata. No build script/binary vendored.
- [SQLite 3.53.1 source identity](https://www.sqlite.org/releaselog/3_53_1.html):
  exact published source ID matches the loaded local library below.
- [uv custom metadata](https://docs.astral.sh/uv/reference/environment/#uv_python_downloads_json_url):
  supported by pinned uv 0.11.8; explicit hash-checked acquisition, without manual
  DLL swaps/global Python replacement. No paid API, model or account needed.

## Runtime inventory

| Environment | Actual identity / observed evidence | Outcome |
| --- | --- | --- |
| Original Windows global interpreter, retained | CPython 3.14.4, SQLite 3.50.4; source `2025-07-30 19:33:53 4d8adfb30e03f9cf27f800a2c1ba3c48fb4ca1b08b0f5ed59a4d5ecbf45e20a3`; FTS5 present | Vendor fix unverified; actual negative probe refuses Store initialization before directory/file creation. No corruption observed. |
| New Windows project environment | Managed PBS 20261013 CPython 3.14.8, SQLite 3.53.1; source `2026-05-05 10:34:17 c88b22011a54b4f6fbd149e9f8e4de77658ce58143a1af0e3785e4e6475127e9`; FTS5 present | Matches upstream fixed release/source and reviewed archive; acceptance below. |
| Windows/Linux CI x86-64 3.12.15 / 3.14.8 | Explicit PBS manifest and expected SQLite identity check added | Pending source push/actual CI execution. |
| New Linux x86-64 container | Pinned Debian bookworm-slim + same PBS 3.14.8 runtime, build-time eligibility and actual doctor identity assertion | Pending Linux Compose CI; Docker is not installed locally. |
| Old pinned stock Python/bookworm container | Debian SQLite/vendor backport status was not established by archived functional tests | No assertion that it is unpatched. Replaced runtime selection; not an accepted runtime based on tests alone. |
| Manifest macOS x86-64/ARM64 and Linux ARM64 | Public archive IDs/hashes, not executed here | Acquisition pins only. Platform acceptance remains a release gate (ANV-014). |

No vendor backport exception is approved in this slice. Older SQLite builds
remain **unverified**, even if vendor-fixed. Supporting them requires deliberate
review of package/build evidence, not an environment bypass or Python patch-number
assumption. Version/source diagnostics do not authenticate arbitrary binaries.

## Implemented boundaries

[ADR 0013](../../decisions/0013-reviewed-sqlite-runtime.md) and
[runtime guide](../../SQLITE_RUNTIME.md) document the contract. A per-process,
in-memory SQLite/FTS5 probe reports Python/SQLite/source identity offline. Store
checks eligibility before all operational connections and before initial directory
creation. Native supervision checks before child creation. Setup/API/worker fail
closed; doctor remains read-only, secret-free and nonzero for unready instances.

No schema, journal policy, ranking protocol, feedback meaning, source connector or
review study changes. The global interpreter remains untouched. uv recreated only
the disposable `.venv`. Every real service process must be stopped/upgraded
together; old already-running code cannot enforce the new gate.

The runtime manifest contains ten GIL-enabled archive pins, both Python versions
across five OS/architecture targets. The unmodified upstream notice aggregate is
105875 bytes, SHA-256
`e43fb936c6655d7996dba480d7ebdea492d6040ec388eb8ed9d1000f72de8cab`.
Its byte identity is preserved by a specific Git attribute; third-party terms
remain separate from Apache core. Container builds retain runtime files and
additional notice/provenance materials. Debian digest was obtained from the
official Docker registry manifest. Apt certificate package updates still follow
the Debian repository; a bit-for-bit OS rebuild is not promised.

## Local validation

- `uv python install ... --python-downloads-json-url policies/runtimes/python-downloads.json --no-bin --no-registry`
  explicitly acquired and hash-checked the maintained Windows runtime. Locked
  managed `uv sync --extra dev --locked --managed-python` installed 25 packages.
- `scripts/check_sqlite_runtime.py --expected-sqlite 3.53.1` passed and printed
  the actual source identity above without an operational DB/network/model call.
- Focused runtime/CLI/self-host suite: **56 passed in 8.40s**; 30 new runtime
  regressions cover branch boundaries/malformed versions, unavailable FTS5,
  setup/API/worker/supervisor refusal, existing DB access and non-mutating doctor.
- Full suite: **431 passed in 75.33s**, no skips. Only the existing ANV-015
  Starlette/httpx TestClient deprecation warning. Ruff lint and all 107 files'
  format check passed.
- Four offline real-process smokes passed: MVP HTTP/API/worker durability and
  lifecycle; self-host saved configuration/supervision/restart; retention expiry,
  cascade and idempotent reuse; new multiprocess SQLite/checkpoint/crash integrity.
- SQLite smoke runs three writers plus a ready checkpointer over temporary
  synthetic state, retains 72 jobs/snapshots/feedback, verifies database/foreign
  key/FTS integrity, abruptly exits a child after committed and uncommitted writes,
  then checks recovery through a fresh connection. Owned children/temp data clean.
- All five archived data/report verifiers passed, with unchanged published
  fingerprints; these verify archived artifacts, not a fresh quality experiment.
- Actual original global Python/SQLite negative probe passed: unverified 3.50.4
  refuses before creating the synthetic database folder. Original runtime remains
  installed; no actual service/review DB is opened.
- Wheel/sdist built successfully. Wheel has 31 entries / 306816 uncompressed
  bytes, all four changed runtime modules match source, private data/binaries are
  absent; sdist has 161 entries including guide, runtime manifest and notices.
- A fresh runtime-only venv installed locked dependencies and the built wheel.
  Imports came from site-packages with pytest absent. Actual SQLite multiprocess/
  crash and retention HTTP/API/worker/restart/cascade acceptance passed from that
  installation. All newly owned installed-wheel scratch/venv/processes cleaned.
- Tracking and diff checks passed. Actual Linux container/cross-platform CI and
  publication are pending; the task remains in progress until those gates pass.

## Limits and next gates

Application integrity tests cannot prove the rare upstream race fixed; that
conclusion uses reviewed release/build evidence. They do not certify hardware,
filesystem, backups or every possible concurrency pattern. No real private search,
feedback, configuration, review-pilot/form/key/coaching/label file was read or
changed. Synthetic fixtures do not become independent human judgments. Historical
ignored ANV-025 scratch remains untouched.

ANV-008 retains hosted controls and actual backup/restore/retention acceptance;
ANV-014 retains runtime update/release policy and untested-platform gates. General
discovery, model relevance gains, independent domain reviews and actual alternate
backends remain their existing tasks. This slice installs no model, calls no paid
service, deploys no public endpoint and publishes no binary package/container.
