# Development changelog

Record material delivered changes with task IDs and verification references. This is an engineering log, not a list of future features.

## 2026-10-18

- ANV-024: added opt-in pointwise ordinal grading with lexical ties, whole-query
  fallback, one shared deadline, saved-config compatibility and structural failure
  diagnostics. Source/protocol 1793f3a preceded inference and passed all five source
  CI jobs. All 40 runs over 4 development / 16 fresh evaluation queries are retained.
  Evaluation nDCG@10 is 0.748850 lexical / 0.743299 listwise / 0.793284 pointwise;
  paired intervals include zero, so relevance improvement is not established.
  Pointwise has 16 valid rankings, listwise 13 plus three duplicate-ID fallbacks.
  Default stays listwise. Added public provenance/resources, stopped owned model
  tree, and offline CI report verification. [Evidence](verification/2026-10-18-ranking-contracts.md).

- ANV-023 initial slice: clarified private search for user-controlled AI tools in
  the main title/descriptions and GitHub About. Added explicit pinned free CPU
  model acquisition/serving, a frozen evaluation harness with fallback-inclusive
  paired metrics and offline report verification, retained development diagnostics,
  compact candidate aliases and optional schema output with stable public IDs.
  Frozen v3 accounts for all 4 development / 24 evaluation queries. Evaluation
  nDCG@10 is 0.616925 lexical / 0.674710 LLM, paired delta 95% interval
  [-0.030015,+0.157238]; improvement is not established. There are 19 applied
  rankings, five invalid-output fallbacks and zero worker failures. Added
  resource/provenance reports, offline CI verification and launcher PID-record
  cleanup, verified by a no-inference restart. Independent domain and actual
  gateway/backend gates remain open. Freeze `9905423` and result `c0fb6eb` are
  pushed to main; all five jobs passed in [run 39119704640](https://github.com/Kshurika-Consultancy/anvesha/actions/runs/39119704640).
  [Evidence](verification/2026-10-18-local-llm.md).

- ANV-021: published commit `83830bf` to main and verified remote equality plus all four Windows/Linux Python 3.12/3.14 jobs in [run 39109656383](https://github.com/Kshurika-Consultancy/anvesha/actions/runs/39109656383).
- ANV-022: delivered LLM-default API/browser requests with an explicit lexical baseline, missing-model guidance and visible runtime fallback. Added same-origin text-only browser rendering, memory-only keys, private saved configuration, supervised native services, and a pinned non-root Docker/Compose layout. Source commit `0193557` is on main. Local 252-test suite, process smokes, desktop/mobile browser and installed-wheel checks pass; all five jobs in [run 39111550834](https://github.com/Kshurika-Consultancy/anvesha/actions/runs/39111550834) passed, including a real container/private-network protocol/restart smoke. [Evidence](verification/2026-10-18-self-hosting.md) records completion. [ADR 0006](../decisions/0006-llm-default-and-self-hosted-browser.md) documents the default-mode upgrade. Actual model quality remains ANV-023.

- ANV-021: added an experimental private-research path with per-request local-corpus LLM reranking, Ollama/OmniRoute chat-protocol interoperability, bounded candidate-only output, total deadlines, lease/cancellation checks, explicit fallback and legacy job migration. Added offline setup diagnostics, authenticated capabilities, native setup/privacy guidance and model-processing policy. 240 local tests and both development/installed-wheel real-process smoke pass; both fresh lexical benchmark repeats retain their exact archived fingerprints. ANV-022/ANV-023 track container/client adoption and actual backend/model quality. See [evidence](verification/2026-10-18-private-research.md); no model quality or general-web claim follows.
- ANV-020: documented separation of coached calibration from independent labels, recorded the first three user-requested practice items privately without grades, and tracked the missing exclusion/reassignment mechanism. No review submission or import was performed; original packet/database hashes and zero-submission status were checked. This is operator guidance, not an implemented import guard.

## 2026-10-16

- ANV-001: added AGENTS, authoritative task ledger, context/handoff workflow, ADRs, source-policy checks, contribution/security guidance, Apache-2.0 licensing and CI.
- ANV-002: saved researched plan, dated primary sources, implementation milestones, and architecture boundaries.
- ANV-003: implemented durable SQLite jobs, owner isolation, idempotency, leases/recovery, atomic snapshots, feedback and FTS5 indexing.
- ANV-004: implemented authenticated API, operator CLI, demo/import path, conditional polling, cancellation/deletion and setup/API docs.
- ANV-005: added offline retrieval, optional Wikidata metadata connector, deterministic RRF with per-source provenance, and separate worker.
- ANV-006: completed 116 offline tests, independent review, real-process restart/worker smoke, package build and isolated-wheel smoke. Fixed blank-idempotency, malformed-import URL and Unicode destination issues. [Verification evidence](verification/2026-10-16-mvp.md).
- Recorded ANV-015 (test transport deprecation) and ANV-016 (optional live-source verification). Production hardening and quality evaluation remain later milestones.
- ANV-017: connected origin, switched to main, repeated checks (116 tests plus real-process smoke), and published initial commit c3fd2f6 to Kshurika-Consultancy/anvesha. Verified local/remote equality and upstream tracking. Device sign-in enabled local Git authentication; initial GitHub Actions run started. [Publication evidence](verification/2026-10-16-publication.md).
- ANV-018: fixed the Windows/Python 3.12 smoke cleanup failure with full process-tree shutdown and a real inherited-log-handle regression. Local checks pass with 118 tests. Fix commit 70216f3 passed all four remote matrix jobs in [run 38901376551](https://github.com/Kshurika-Consultancy/anvesha/actions/runs/38901376551).
- ANV-019: started M2 with a rights-reviewed, pinned SciFact evaluation snapshot (500 queries, 5,183 corpus IDs, 569 upstream evidence judgments), explicit bounded acquisition, actual M1/BM25/token-overlap baselines, per-query metrics and bootstrap reports, and an unlabelled local review pool. Raw abstracts stay out of Git. Local checks pass with 148 tests, real-process smoke and installed-wheel report verification; independent fresh-index repeat gives identical rankings. The 300-query evaluation baseline is 0.672633 nDCG@10 for M1/BM25; this scientific slice does not establish general-web quality. Source commit `9ae8b2f` is published on main; all four matrix jobs passed in [run 38910026463](https://github.com/Kshurika-Consultancy/anvesha/actions/runs/38910026463). ANV-020 tracks representative strata and independent review; ANV-007 remains open. [Evaluation evidence](verification/2026-10-16-evaluation.md).
- ANV-020 implementation slice: added a licensed, pinned English/Spanish/Hindi XQuAD snapshot with 720 published query instances/passages, 36 explicitly AI-authored intent probes, grouped holdout and honest QA-mapping metrics. Actual M1/BM25/token-overlap runs repeat identically. Added private blinded offline forms, credential/packet validation, atomic imports, retained revisions/attestation receipts, abstentions, pairwise agreement, separate adjudication and immutable exports. A local 200-pair/42-double-assignment pilot has zero human labels. All 185 local tests, smoke and installed-wheel checks pass. Source commit `ac48d2e` is on main and all four matrix jobs passed in [run 38936703068](https://github.com/Kshurika-Consultancy/anvesha/actions/runs/38936703068). Actual assessor work and remaining study acceptance stay open. [Evidence](verification/2026-10-16-human-review.md).
