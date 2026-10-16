# ADR 0004 Multilingual evaluation and local independent review

Status: accepted for the ANV-020 implementation slice, 2026-10-16.

Use pinned English, Spanish and Hindi XQuAD files: real Wikipedia-derived passages, crowdworker questions and professional translations. Keep the full 720-passage collection locally and select one aligned question per paragraph (720 translated query instances). Add a small, explicitly AI-authored draft set covering navigation, ambiguity, exact constraints, historical dates, comparisons and multilingual requests. Drafts have no gold grades and are not observations of real user demand. Do not call this a population-representative web benchmark.

Assign articles, all their passages, translations and draft queries to the same deterministic development/holdout partition. Reserve the holdout from tuning. Public, previously published data is not a private or model-unseen test set. Preserve the original scientific baseline separately.

XQuAD data and adapted query/mapping files retain CC-BY-SA-4.0; Anvesha's code remains Apache-2.0. Upstream answer spans identify known answer-bearing contexts, not independently pooled retrieval judgments. Never mix these mappings, synthetic test labels or draft queries with new human assessments. Source hashes, attribution and transformations accompany the public metadata. Raw passages and assessment workspaces remain ignored local data.

The review workflow is a trusted local operator tool, separate from the production API and its feedback store. It freezes the candidate pool and rubric, issues separate pseudonymous reviewer credentials, exports system/gold-blinded packets and an offline form, validates authenticated imports atomically, retains revisions, reports missing/abstained work and pairwise agreement, and requires a separate adjudicator for disagreements. Credentials authenticate packet submission, not a person's identity or independence; the operator must verify consent, identities and language competence privately. No automatic training, publication, paid service or hosted model is involved.

Human labels require explicit assessor attestation. Default final export refuses incomplete work. Partial exports identify their coverage and cannot masquerade as final benchmark truth. Real double assessment, adjudication and permitted external comparisons remain open ANV-020 acceptance criteria until people supply them. Automated tests use visibly synthetic labels only.

Sources: [XQuAD data description and licence](https://github.com/google-deepmind/xquad), [SQuAD dataset licence and origin](https://rajpurkar.github.io/SQuAD-explorer/), [CC-BY-SA-4.0](https://creativecommons.org/licenses/by-sa/4.0/).
