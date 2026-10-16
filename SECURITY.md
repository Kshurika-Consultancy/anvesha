# Security and privacy boundaries

This initial MVP is for a single-host local deployment. Keep the API bound to loopback. Public hosting needs ANV-008 quotas, retention, abuse controls, operational review, and transport/security configuration. The demo is not a production security certification.

- Every search endpoint requires `X-API-Key`. Use a randomly generated key of at least 24 ASCII characters; initialize generates a 32-byte random secret. Raw keys are not stored in job records. Each configured key defines a distinct owner; replacing a key does not migrate its old jobs.
- All clients of an instance share the operator-imported document corpus. Import only data intended for those clients. Job history and feedback are owner-scoped; document-level tenant isolation is not implemented.
- The database contains query text, snapshots, and feedback. Restrict filesystem access and backups. It is not encrypted by the application. API access logs may contain job IDs but must never log headers or request bodies.
- Learning opt-in defaults off; no training is performed. Search deletion cascades associated records in the active database but is not a forensic erasure guarantee for backups or disk pages. Automatic expiry/backup deletion policy is tracked in ANV-008.
- Only the fixed Wikidata endpoint is used for optional live retrieval; no arbitrary URL is fetched. Enabling it sends the submitted query to Wikimedia. Provide a real operator User-Agent/contact and review the source manifest.
- Rank scores are not truth probabilities. Wikidata results are metadata-only; the source webpages are not verified. Imported text is data, not executable instructions.
- SQLite files must be on local disk. Avoid network filesystems. Worker leases prevent stale publication but do not promise exactly-once external calls.

No public security mailbox or repository URL has been established yet. Report issues privately to the repository maintainer through an established company channel; do not publish secrets or exploit details in public issues. Establish a verified disclosure route before M6 public release (ANV-014).
