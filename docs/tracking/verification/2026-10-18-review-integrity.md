# ANV-025 independent-review integrity verification

## Decision and scope

The ANV-023/024 scientific pilots do not establish a relevance improvement. Broader
independent evidence remains ANV-020, whose pilot has three known coached Reviewer A
items recorded privately. The CLI previously could import them as independent
assessments. Closing that gap is the next useful quality step before collecting
more judgments. [ADR 0011](../../decisions/0011-independent-review-exposure-and-replacement.md)
records the decision; [the operator guide](../../review/README.md) gives commands.

Root worked from clean main `ad024d5`, without delegation. All new assessments and
attestations used in verification are explicitly synthetic. The real pilot, forms,
credentials, practice notes and labels were not read, migrated, imported or changed.
Zero new human judgments; no model call, paid API, network search, new dataset,
ranking change or production feedback write. Existing data/software licences stay
separate and unchanged. No general-domain improvement is claimed.

## Behavior verified

- Query-wide exclusions reject completed old signed rows, even unchanged replays,
  revisions and abstentions. All candidates for the reviewer/query are covered.
  Unfinished rows remain unjudged. Unaffected packet signatures continue to work.
- Existing affected labels are quarantined from current resolution, agreement,
  judgment counts and qrels; immutable label revisions/import receipts remain.
  Exclusions are permanent and idempotent for the same reason.
- Explicit new enrollment writes a separate exclusive credential file, refuses
  identity/credential reset and case aliases, and rolls back on write failure.
  Credentials are absent from command output and packets. Case aliases are also
  refused in new session initialization to avoid shared Windows packet directories.
- Recorded replacement covers all active excluded slots for the query atomically.
  Original assignments and double-review denominators remain. Adjudicators,
  excluded recipients and prior/current assignees on that pair are rejected.
  Replacement chains work; exposed people cannot return through the same pseudonym.
- Replacement packets reveal no prior reviewers' labels or exclusion history.
  A separate adjudicator must resolve current disagreement; old decisions/packets
  become stale when reviewer/revision maps change, even at equal revision numbers.
- Explicit v1-to-v2 migration preserves original pool/assignment/label/receipt rows,
  credentials and signed packets. Read commands do not silently migrate. Unknown
  versions fail closed; a migration SQL failure rolls back schema and version.
- Export coverage/qrels/audit use one read snapshot. A WAL concurrent-write test
  confirms that an intervening exclusion cannot mix old coverage with new labels.
  Historical files stay intact. The verifier rejects stale or edited exports;
  identical-label import receipts also receive a new immutable fingerprint.

These are protocol and integrity checks, not proof of real assessor independence,
identity, language competence or representative search quality. The operator must
declare exposure, including aliases/other sessions, enroll actual consenting people
and replace derived evaluations when an earlier export becomes obsolete. A verifier
reports the state of its read snapshot; future writes can make it stale again.

## Local checks, 2026-10-18

```text
uv sync --extra dev --locked
uv run --extra dev ruff check .
uv run --extra dev ruff format --check .
uv run --extra dev pytest
uv run --extra dev python scripts/check_tracking.py
uv run --extra dev python scripts/smoke_mvp.py
uv run --extra dev python scripts/smoke_selfhost.py
uv run --extra dev python -m anvesha.evaluation verify
uv run --extra dev python -m anvesha.review_data verify
uv run --extra dev python -m anvesha.intent_evaluation verify
uv run --extra dev python -m anvesha.llm_evaluation verify
uv run --extra dev python -m anvesha.ranking_experiment verify
uv build --out-dir .anvesha/dist/anv025
git diff --check
```

Checkpoint: 363 tests passed in 53.74s, including 38 new synthetic integrity cases.
After explicitly closing synthetic fixture connections, all 38 new cases passed
again in 8.74s. Existing ANV-015 Starlette/httpx transport deprecation is the sole
suite warning. Final full suite after fixture-handle cleanup: **363 passed in
56.73s**. Lint/format/tracking, both offline real-process smokes and all five
archived artifact verifiers passed. Model/report fingerprints stay unchanged.
Diff inspection classifies all 14 changed/new files under ANV-025 (ANV-020 notes
updated for continuity); no unrelated changes were present. Publication and CI
are verified after the implementation commit.

Both wheel and source distribution built. Inspection confirms `review.py` and the
new `review_integrity.py` in the wheel match source; no private workspace, database,
credential, weights or runtime executable is in the wheel. A separate runtime-only
venv was installed from that wheel plus the locked exported runtime requirements,
without development packages. Imports came from site-packages, not the checkout.
Actual `python -m anvesha.review` subprocesses exercised synthetic initialization,
blinded export/import, excluded old-packet rollback, enrollment/replacement, full and
partial finalization, current/stale verification and explicit repeatable legacy
migration with unchanged packet bytes.

The initial installed-wheel harness passed those functional checks but its
TemporaryDirectory cleanup failed on Windows because the harness retained a SQLite
connection. Fixture/harness connections now close explicitly. Automatic approval
review subsequently rejected cleanup of the exact disposable directory as
"blocked by policy". The ignored `.anvesha/verification/anv025-installed-1f6qt3gu`
scratch directory is retained, containing only the runtime venv and synthetic
fixtures/credentials/exports. It is excluded from Git and packages. Do not confuse
it with the real review pilot. The corrected actual-CLI rerun is checked separately;
no review/API/worker/model service is left running by this verification. The
corrected installed-wheel actual-CLI rerun exited 0 after repeating the complete
synthetic exclusion/replacement/export workflow and explicit legacy migration;
all its database connections and subprocesses closed. Cleanup is the sole retained
scratch limitation, separately recorded in ANV-025.

## Remaining human work

ANV-020 remains in progress. A trusted operator must back up and explicitly migrate
the real legacy pilot, map the three practice item IDs in its private note to query
IDs, record Reviewer A's permanent query exclusions, enroll an unexposed consenting
replacement, distribute only that person's packet/token and collect actual labels.
Then collect remaining independent labels, adjudicate, verify current final exports,
review language/rubric quality and consent, and design broader held-out relevance
comparisons. This implementation does none of those human actions automatically.
