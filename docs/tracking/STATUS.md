# Anvesha development status

Current objective delivered: auditable development foundations and the first runnable, no-paid-API MVP. See [verification evidence](verification/2026-10-16-mvp.md).

Completed authorized follow-up: this workspace is connected to [Kshurika-Consultancy/anvesha](https://github.com/Kshurika-Consultancy/anvesha), and the initial plan/MVP is published on main (ANV-017). Origin tracking and the remote commit were verified; the M6 service pilot remains planned. See [publication evidence](verification/2026-10-16-publication.md).

The authoritative task state is [tasks.json](tasks.json). Milestone scope and gates are in [MILESTONES.md](../MILESTONES.md). Read [HANDOFF.md](HANDOFF.md) for operational continuity.

M0 foundations and M1 local-first asynchronous search are implemented and verified locally. M2+ remains planned. The first slice is not a general-web search replacement or a claim of Google-level quality.

Implementation uses Python/FastAPI, SQLite WAL/FTS5, a separate durable worker, a locally indexed first-party demonstration corpus, and an optional Wikidata metadata connector. It needs no paid API or LLM key. Demo content is visibly identified as demonstration material. A real-process smoke test passed for both the development installation and isolated built wheel.

The first remote CI run exposed a Windows/Python 3.12 smoke cleanup failure after all assertions passed. ANV-018 fixes shutdown to stop the server process tree and adds a real descendant-process regression. All 118 tests and the smoke pass locally; all four jobs passed in [GitHub Actions run 38901376551](https://github.com/Kshurika-Consultancy/anvesha/actions/runs/38901376551) for fix commit 70216f3 (Windows/Linux, Python 3.12/3.14).

Next priorities: representative quality evaluation (ANV-007), hosted hardening/retention (ANV-008), test transport maintenance (ANV-015), and optional live Wikidata verification with a real operator contact (ANV-016). No live provider test has run. The runner also reports nonblocking Node action deprecations; review action versions during release maintenance (ANV-014).

Quality claims require measured evidence. Runtime failures, unsupported features, and uncovered search categories must be exposed rather than silently described as complete coverage.
