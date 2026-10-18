# Anvesha implementation milestones

Task status and evidence live only in [the task ledger](tracking/tasks.json). This document defines scope and gates; it does not duplicate completion statuses. The [plan](PLAN.md) explains the product and [ADRs](decisions/0001-local-first-mvp.md) record implementation choices.

| Milestone | Tasks | Deliverable | Gate |
| --- | --- | --- | --- |
| M0 Foundations | ANV-001, ANV-002, ANV-017 | Agent instructions, research plan, ADRs, task ledger, contribution and licence policies, CI, authorized initial GitHub publication | Another agent can identify scope, ownership, decisions, validation, and next work; tracking checks pass; remote commit is verified |
| M1 Runnable local MVP | ANV-003, ANV-004, ANV-005, ANV-006, ANV-018 | Authenticated async API, SQLite job/feedback store, separate worker, local FTS5 retrieval, optional Wikidata metadata, deterministic rank fusion, cross-platform smoke process cleanup | Offline end-to-end and failure-path tests pass; fresh setup and real API/worker smoke verified; no paid API required |
| M2 Evaluation and hosted hardening | ANV-007, ANV-008, ANV-015, ANV-016, ANV-019, ANV-020 | Published real-data retrieval baseline, representative human evaluation corpus, quotas, resource limits, retention/deletion automation, test-transport maintenance, optional live-source verification | Reproducible scoped baseline first; broader judgments and hosted controls remain separate gates |
| M3 Document understanding and retrieval quality | ANV-009, ANV-010, ANV-011, ANV-021, ANV-022, ANV-023 | Approved sources, safe fetching, section extraction, hybrid retrieval; scoped private research, LLM-default ranking with an explicit lexical baseline, browser/self-hosting and measured backend quality | The local-corpus experiment may precede general fetching; full quality gates still require independent held-out gains and source-rights enforcement |
| M4 Adaptive search and reviewed learning | ANV-012 | Bounded gap investigation, consented/reviewed labels, controlled ranking experiments | Measurable improvement, poisoning controls, stable holdout, rollback |
| M5 Scaling when justified | ANV-013 | Measured migration to production storage/index/workflow infrastructure | Recovery, isolation, latency/cost and throughput evidence; preserve API semantics |
| M6 Public pilot | ANV-014 | Supported-scope quality/cost report, reviewed terms/privacy, release process and deployment | Explicit publication/deployment authorization and documented evidence; no unsupported Google-quality claim |

## M1 acceptance scenarios

- Initialize and seed without a network connection, submit a query, stop/restart a worker, poll, and read a stable result snapshot.
- A replayed idempotency key returns the same job; reuse with different input conflicts. One API client cannot read, modify, or delete another client's jobs.
- Expired worker leases are recovered with bounded attempts. A stale or cancelled worker cannot publish results.
- Optional source failure is visible. A successful empty search, partial source outage, and complete source failure are distinct.
- Feedback points to an existing snapshot/result, repeated votes replace earlier votes, and learning consent defaults off.
- Deletion removes the search's retained snapshots and feedback. Automatic expiry remains M2 and must not be claimed as implemented.
- Every result comes from a configured source and carries provenance. Demo results are visibly synthetic; Wikidata returns entity metadata, not verified webpage contents.

## Boundaries and planning estimates

M1 deliberately omits general crawling, web-page verification, semantic embeddings, LLM planning, learned ranking, automated feedback training, public multi-tenant quotas, automatic retention expiry, and Google-scale coverage. These are explicit later tasks rather than hidden promises.

The researched 13–16 week public-pilot schedule is a staffing-dependent estimate for two experienced engineers with retrieval/evaluation support, not a committed delivery date. Advance on acceptance gates; prioritize a measured failure over adding complexity to meet an arbitrary calendar.

## Task update format

Each ledger entry contains ID, milestone, title, status, owner, dependencies, acceptance criteria, validation plan, verification evidence, references, and notes. Verification evidence records an actual command or review, observed result, and date. Blocked/deferred work includes a reason and actionable next step. Root coordinates shared ledger edits during parallel work.
