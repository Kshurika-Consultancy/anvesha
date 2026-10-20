# ADR 0012 Private search retention

Status: accepted for ANV-026, 2026-10-20. Scoped delivery under ANV-008; other hosted
hardening remains open. Builds on [ADR 0001](0001-local-first-mvp.md) and
[ADR 0006](0006-llm-default-and-self-hosted-browser.md).

Private self-hosting requires control over retained operational data as well as
inference. Queries, snapshots and feedback currently live until explicit deletion.
Implement a finite, visible lifetime for new searches before adding more retained
private data. This changes operational storage, not search ranking or human review.

New Settings/environment installations and setup files default to 604800 seconds
(seven days) from durable acceptance. The operator may choose an integer from 0 to
31536000 seconds; zero explicitly means indefinite. Add a nullable `expires_at`
column to jobs and an expiry index through serialized additive migration. Legacy
jobs stay null, as do newly accepted jobs from old saved files missing the retention
field (effective setting zero). Do not infer consent to delete existing history or
backfill deadlines. New setup saves the field; configuration changes affect future
acceptance only. Preserve source/model configuration identities and old request hashes.

Expiry is persisted once. Reads, feedback, cancellation and deletion treat an expired
job like an unknown/unowned one; conditional polling cannot return 304 after expiry.
Workers cannot claim, heartbeat or publish expired work, including work that expires
during a model call. In-flight external processing cannot be recalled; existing
checkpoints stop further work. Every state, including queued/running, is subject to
the deadline. A result remains stable only for its retained lifetime.

Idempotent replay before expiry returns the original deadline even if policy changed.
At expiry, acceptance can transactionally delete the old job and its dependents,
freeing that client's key for a new job. The key has no perpetual guarantee beyond
retention/deletion. No expired job is resurrected. No expiry tombstone containing
query/owner history is added; access remains 404 without revealing existence.

Before each claim, the separate worker deletes at most 100 expired jobs, cascading
snapshots and feedback. The same pass runs when idle and after restart; it does not
depend on new requests. SQL eligibility guards apply even if cleanup lags or all
workers are stopped. Index the feedback foreign key to avoid repeated full scans
during cascade. Bound deletion by job count, not a promised wall-clock latency.

Add a private local `prune` operator command: read-only dry-run by default, explicit
`--apply` to delete one bounded batch. Neither mode creates/upgrades a missing or
legacy database silently. Apply must use recorded deadlines only. Never remove
imported documents, saved credentials, review workspaces, model files or benchmarks.

This is logical deletion from the active database, not forensic erasure. SQLite
pages/WAL, backups, browser/client copies and model/runtime logs can retain data.
Do not silently change journaling or vacuum a live service as part of cleanup.
Operators must manage storage/backups separately and verify external model routes.
Wall-clock changes can alter effective expiry timing; persisted timestamps use UTC.
Upgrade API and workers together before enabling retention on an existing instance.

Default verification uses synthetic temporary databases and protocol fixtures only.
No actual service/review data is inspected or migrated. No paid API, hosted LLM,
new source or automatic feedback learning is introduced. Backup/restore policy,
legacy-history backfill, quotas, identity/key rotation and hosted audits remain
ANV-008, not implied by completion of this slice.

Primary SQLite references: [foreign-key cascades](https://www.sqlite.org/foreignkeys.html#fk_actions),
[secure-delete limits](https://www.sqlite.org/pragma.html#pragma_secure_delete),
[WAL lifecycle](https://www.sqlite.org/wal.html). These support deletion boundaries,
not a claim that a deployment's disks or backups are erased.
