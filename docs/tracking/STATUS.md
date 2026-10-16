# Anvesha development status

Current objective delivered: auditable development foundations and the first runnable, no-paid-API MVP. See [verification evidence](verification/2026-10-16-mvp.md).

Current authorized follow-up: connect this workspace to [Kshurika-Consultancy/anvesha](https://github.com/Kshurika-Consultancy/anvesha), commit the plan/MVP, and push to main (ANV-017). Publication verification is in progress; the M6 service pilot remains planned.

The authoritative task state is [tasks.json](tasks.json). Milestone scope and gates are in [MILESTONES.md](../MILESTONES.md). Read [HANDOFF.md](HANDOFF.md) for operational continuity.

M0 foundations and M1 local-first asynchronous search are implemented and verified locally. M2+ remains planned. The first slice is not a general-web search replacement or a claim of Google-level quality.

Implementation uses Python/FastAPI, SQLite WAL/FTS5, a separate durable worker, a locally indexed first-party demonstration corpus, and an optional Wikidata metadata connector. It needs no paid API or LLM key. Demo content is visibly identified as demonstration material. A real-process smoke test passed for both the development installation and isolated built wheel.

Next priorities: representative quality evaluation (ANV-007), hosted hardening/retention (ANV-008), test transport maintenance (ANV-015), and optional live Wikidata verification with a real operator contact (ANV-016). No live provider test or remote CI run has been claimed.

Quality claims require measured evidence. Runtime failures, unsupported features, and uncovered search categories must be exposed rather than silently described as complete coverage.
