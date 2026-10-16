# Development changelog

Record material delivered changes with task IDs and verification references. This is an engineering log, not a list of future features.

## 2026-10-16

- ANV-001: added AGENTS, authoritative task ledger, context/handoff workflow, ADRs, source-policy checks, contribution/security guidance, Apache-2.0 licensing and CI.
- ANV-002: saved researched plan, dated primary sources, implementation milestones, and architecture boundaries.
- ANV-003: implemented durable SQLite jobs, owner isolation, idempotency, leases/recovery, atomic snapshots, feedback and FTS5 indexing.
- ANV-004: implemented authenticated API, operator CLI, demo/import path, conditional polling, cancellation/deletion and setup/API docs.
- ANV-005: added offline retrieval, optional Wikidata metadata connector, deterministic RRF with per-source provenance, and separate worker.
- ANV-006: completed 116 offline tests, independent review, real-process restart/worker smoke, package build and isolated-wheel smoke. Fixed blank-idempotency, malformed-import URL and Unicode destination issues. [Verification evidence](verification/2026-10-16-mvp.md).
- Recorded ANV-015 (test transport deprecation) and ANV-016 (optional live-source verification). Production hardening and quality evaluation remain later milestones.
- ANV-017: connected origin, switched to main, repeated checks (116 tests plus real-process smoke), and published initial commit c3fd2f6 to Kshurika-Consultancy/anvesha. Verified local/remote equality and upstream tracking. Device sign-in enabled local Git authentication; initial GitHub Actions run started. [Publication evidence](verification/2026-10-16-publication.md).
