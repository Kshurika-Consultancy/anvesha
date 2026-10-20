# Reviewed Python and SQLite runtime

ANV-027, reviewed 2026-10-20. Anvesha uses separate API/worker processes against
SQLite WAL on local disk. SQLite's [WAL-reset advisory](https://www.sqlite.org/wal.html#walresetbug)
describes a rare concurrency race that can corrupt a database. Fixed upstream
releases are 3.51.3 and later, or the specific backport branches 3.44.6+ and 3.50.7+.
Anvesha requires one of those releases **and FTS5** before operational DB access.
An older version is reported as **unverified**, even if its vendor may have
backported the fix. There is no configuration bypass; supporting a vendor backport
requires explicit reviewed package/build evidence and a maintainer policy change.

The Python version alone does not identify its SQLite library. The previous local
Python 3.14.4 loaded SQLite 3.50.4 with source ID
`2025-07-30 19:33:53 4d8adfb30e03f9cf27f800a2c1ba3c48fb4ca1b08b0f5ed59a4d5ecbf45e20a3`.
Its vendor patch status was unverified; no corruption was observed.

## Install the reviewed runtime

With [uv](https://docs.astral.sh/uv/getting-started/installation/) installed, run
from this checkout (Windows PowerShell or a Linux shell):

```text
uv python install --python-downloads-json-url policies/runtimes/python-downloads.json --no-bin --no-registry
uv sync --extra dev --locked --managed-python
uv run --extra dev python scripts/check_sqlite_runtime.py --expected-sqlite 3.53.1
```

The first command explicitly downloads a Python runtime; it does not download
models. `.python-version` selects CPython 3.14.8. The manifest records exact PBS
20261013 URLs and SHA-256s, verified by uv. It does not replace global Python,
manually swap DLLs, change shell defaults or register Windows executable aliases.
Sync recreates the disposable project `.venv` if its interpreter differs; private
configuration/data is outside that directory. Omit `--extra dev` for runtime-only
installation. No paid API, account, hosted model or GPU is needed. Once acquired,
normal offline checks/searches do not contact runtime download hosts.

The [PBS dependency declaration](https://github.com/astral-sh/python-build-standalone/blob/20261013/pythonbuild/downloads.json)
specifies SQLite 3.53.1; its Windows build uses that declaration instead of the
stock CPython dependency. The [SQLite 3.53.1 release](https://www.sqlite.org/releaselog/3_53_1.html)
identifies source ID
`2026-05-05 10:34:17 c88b22011a54b4f6fbd149e9f8e4de77658ce58143a1af0e3785e4e6475127e9`.
Local verification matches that ID. CI checks Windows/Linux x86-64 with CPython
3.12.15 and 3.14.8 and actual Linux x86-64 Compose installation. Manifest entries
for macOS x86-64/ARM64 and Linux ARM64 are acquisition pins, **not acceptance
claims**; those platforms still need actual installation/process/container tests.
Windows ARM64 and musl are not in this manifest. Other maintained Python 3.12+
builds can work when their loaded SQLite release passes the same eligibility test.

Pinned uv 0.11.8 supports [custom Python download metadata](https://docs.astral.sh/uv/reference/environment/#uv_python_downloads_json_url).
Its built-in 20260414 runtime list used SQLite 3.50.4, so using its defaults would
not solve this issue. The checked-in manifest changes acquisition, without needing
a new installer or an unreviewed floating interpreter upgrade. This is one
reviewed build baseline; maintainers must periodically review Python, SQLite, uv,
Debian and optional model runtime updates under ANV-014.

## Inspect without changing data

```text
uv run anvesha doctor --config .anvesha/server.json
```

Doctor reports `sqlite_runtime` with actual Python/SQLite versions, source ID,
FTS5, `wal_reset_fix`, eligibility and the evidence basis. It does not print keys,
queries, document text or model responses, contact providers, create/migrate an
operational database or start services. It returns nonzero when readiness fails.
Its FTS5 probe uses an in-memory database. A missing/unmigrated DB can still make
readiness fail on an eligible runtime; inspect the separate fields.

Store checks eligibility before opening an operational DB, including existing
databases and read-only pruning. Setup fails before creating its database folder
or saving credentials. The native supervisor refuses before spawning either
child; independently launched API/workers also fail at initialization. The
in-memory diagnostic is cached per process. Start every service with the same
verified environment; an old process from an older checkout cannot enforce this
new gate. Review-workspace schema/data is unchanged by this task.

Recognition of an upstream version is not binary attestation, a complete
vulnerability audit, or proof of a vendor backport. Hashes bind acquisition to
reviewed release artifacts, not to a promise that a distributor is trustworthy
forever. Application concurrency/recovery tests establish compatibility, **not**
that the rare upstream race cannot happen.

## Update an existing instance

1. Stop **all** API/worker/supervisor processes. Retain private config and corpus
   import sources. Make a consistent private backup of the stopped database and
   configuration according to [backup guidance](PRIVATE_RESEARCH.md#browser-storage-and-upgrades).
   Do not copy a live main DB without its WAL or manually delete WAL/SHM files.
2. Acquire the reviewed runtime, sync the project environment and run the offline
   runtime check above. Nothing in this task migrates the database schema or
   changes its journal mode. Do not initialize or edit actual review studies as a
   runtime test.
3. Run the synthetic process checks below, then doctor with your existing private
   configuration. Doctor only inspects it; protect its local output if needed.
4. Restart every API/worker with the updated code and interpreter. Existing
   ownership, snapshot versions, feedback, idempotency and expiry remain intact.

For rollback, stop all processes again. Keep the original consistent backup,
code revision, environment and runtime identities together. Prefer a matching
verified patched runtime; never downgrade to an unverified SQLite build merely
to make a service start. A rollback requiring old database/code must use its
matching backup and privacy/retention review, as described in the private guide.
Restore may reinstate records deleted since the backup. Do not claim this
procedure is a fully tested backup/restore product; that remains ANV-008.

## Validate a runtime update

```text
uv run --extra dev pytest
uv run --extra dev python scripts/smoke_sqlite.py
uv run --extra dev python scripts/smoke_mvp.py
uv run --extra dev python scripts/smoke_selfhost.py
uv run --extra dev python scripts/smoke_retention.py
```

The SQLite smoke owns temporary synthetic state and four concurrent processes:
three writers and a checkpointer. It verifies 72 jobs, snapshots and feedback,
foreign-key/FTS/database integrity and committed/uncommitted recovery after an
abrupt child exit. All children and temporary data are cleaned. It is bounded and
uses no model/provider network. Existing process smokes verify actual HTTP
acceptance, supervision, restart and expiry. Required lint/tracking/report checks
remain in AGENTS.md/CI. Preserve archived evaluation artifacts; an interpreter
change is not a new relevance experiment.

Container builds install the reviewed PBS runtime on pinned Debian bookworm-slim,
preserving its runtime files/notices and the additional upstream notice aggregate.
They check eligibility while building; Compose acceptance verifies the actual
SQLite identity as UID 10001, model protocol fixtures, restart and feedback.
Run `uv run --extra dev python scripts/smoke_container.py` with Docker Compose v2,
or inspect its Linux CI job. A Dockerfile review does not establish acceptance.
Base image digests and runtime hashes are pinned; apt certificate package updates
still follow the Debian repository and this is not a bit-for-bit reproducible
OS image promise. No container or package is published by these checks.

See [ADR 0013](decisions/0013-reviewed-sqlite-runtime.md),
[runtime provenance](../policies/runtimes/README.md), and
[verification evidence](tracking/verification/2026-10-20-sqlite-runtime.md).
