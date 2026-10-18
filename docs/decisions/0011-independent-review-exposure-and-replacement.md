# ADR 0011 Independent review exposure and replacement

Status: accepted for ANV-025, 2026-10-18. Extends [ADR 0004](0004-multilingual-corpus-and-human-review.md).

The next quality gate after ANV-024 is credible independent evidence beyond scientific
queries. The current ANV-020 pilot contains known coached practice, recorded only in
private operator notes. Do not collect more labels against that known integrity gap.
Implement enforced exclusions and a deliberate replacement workflow before the study
can count affected judgments as independent. Actual people and labels remain ANV-020.

An operator records an append-only exclusion for an enrolled initial reviewer and
query ID, using a bounded reason category. It covers all selected candidates for that
query, including future replacement assignments. It cannot be cleared by abstention,
revision, a fresh packet, or re-enrollment of the same pseudonym. It rejects completed
rows from old signed packets, removes already submitted affected labels from current
agreement/resolution/qrels, and retains their revisions and receipts for audit. Query
aliases, other workspaces and undeclared exposure still need operator review.

Preserve the original frozen assignment table and pool. Add replacement events for
excluded active slots; never silently drop the slot or reduce double review. An
eligible, separately enrolled reviewer receives a fresh blinded packet containing
their own assessments only. Reject an existing reviewer on the same pair, a previous
holder of that slot/pair, an excluded recipient and the adjudicator. Require explicit
operator attestation of an unexposed, distinct, consenting, language-qualified person.
Credentials authenticate submissions; software cannot prove identity or independence.
Replacement chains remain possible if another exposure is discovered later.

Use an explicit transactional v1-to-v2 workspace migration. Preserve signing keys,
session IDs, credentials, original assignments, labels, decisions and packet schema;
unaffected signed v1 packets continue to work. Read commands must not silently migrate
or rewrite old workspaces. Unknown versions fail closed. All development and migration
checks use synthetic workspaces; the real pilot is not read, migrated or submitted as
a side effect of this implementation.

Use one consistent database snapshot for coverage, agreement, qrels and audit evidence.
Exclusions and replacement identities invalidate old adjudications through their
underlying reviewer/revision map. Immutable private exports identify the integrity
state as well as label revisions; a verification command rejects historical exports
whose state no longer matches the workspace. Previous exports remain audit artifacts,
not current independent evidence. No credentials, prior reviewers' labels or exposure
history appear in replacement packets. Audit records and credentials remain private.

No retrieval/ranking change, new data acquisition, legal/licensing change, hosted
service, model call, paid API, human label, automatic training or public study result
follows. Default verification stays offline. ANV-020 stays open until people actually
provide independent judgments and the remaining study requirements are satisfied.
