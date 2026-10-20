# ADR 0013 Reviewed SQLite runtime for WAL storage

Accepted 2026-10-20, ANV-027. Supersedes ADR 0001's implicit assumption that any
Python 3.12+ SQLite/FTS5 build is suitable; the single-host architecture is unchanged.

SQLite documents a rare concurrent WAL-reset corruption race, fixed in 3.51.3
and later, with branch-specific backports 3.44.6 and 3.50.7. The previous local
Python 3.14.4 loaded 3.50.4; neither its source identity nor the old CI runtime
manifest established a vendor backport. No corruption was observed.

Use standard-library sqlite3 with maintained python-build-standalone (PBS)
20261013 builds, which declare SQLite 3.53.1. Independently recorded archive
URLs/SHA-256s in `policies/runtimes/python-downloads.json` let existing pinned uv
0.11.8 verify acquisition without custom extraction, replacing DLLs, or changing
the user's global interpreter. `.python-version` selects 3.14.8; CI also exercises
3.12.15. Install commands explicitly use the reviewed manifest and avoid installing
global executable aliases/Windows registry entries. Normal offline tests never
download runtimes. Alternate Python builds are eligible when their actual SQLite
release includes the documented fix and FTS5 is available.

Before opening an operational DB, Store requires a fixed upstream SQLite release
and FTS5. Startup supervision checks before spawning children; doctor remains an
offline diagnostic and reports readiness, Python/SQLite identity, source ID and
the evidence basis. Unknown/older versions are **unverified**, including possible
vendor backports. No environment flag or blanket version exception bypasses the
check. Supporting such a backport requires reviewed vendor package/build evidence
and a deliberate policy change. Release recognition does not authenticate an
arbitrary binary or prove every SQLite bug fixed.

Containers use the same reviewed PBS build on pinned Debian bookworm-slim;
they no longer depend on the OS SQLite version. Keep Python's bundled notices
with the runtime. PBS's build scripts are not copied into the Apache core.
Version/digest pins require periodic maintainer review, not indefinite support.

Tests cover release/backport boundaries, fail-closed setup/access, non-mutating
diagnostics and real multiprocess WAL/checkpoint/crash integrity on synthetic
data. CI checks the expected SQLite release and actual container runtime. These
are application acceptance checks; the upstream race fix rests on upstream
release/build evidence, **not** failure to reproduce corruption in a smoke test.

No schema, journaling, search ranking, source rights or review workflow changes.
Stop all API/workers, back up private state consistently, recreate the environment
with the reviewed interpreter, and verify before restarting every process.
Do not remove live WAL files, mix runtime versions or downgrade blindly. Detailed
update, verification and rollback boundaries: [runtime guide](../SQLITE_RUNTIME.md).
