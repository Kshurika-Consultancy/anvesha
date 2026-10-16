# Initial GitHub publication

Date: 2026-10-16. Task: ANV-017. The user explicitly authorized connecting this workspace, committing the plan/MVP, and pushing main.

## Published source

- Repository: [Kshurika-Consultancy/anvesha](https://github.com/Kshurika-Consultancy/anvesha).
- Local branch: main. Origin: `https://github.com/Kshurika-Consultancy/anvesha.git`.
- Initial source commit: [c3fd2f663f051a65c5ce3a39e702f94036850912](https://github.com/Kshurika-Consultancy/anvesha/commit/c3fd2f663f051a65c5ce3a39e702f94036850912).
- Commit message: Initial Anvesha plan and asynchronous search MVP.
- Reviewed scope: 45 files containing the plan, research, governance/tracking, source, tests, policies, examples, package lockfile, and CI configuration.
- Repository author identity uses the authenticated account's GitHub noreply address; no global Git identity was changed.

## Executed validation

| Check | Observed result |
| --- | --- |
| Locked environment sync | Passed after retrying a transient Windows editable-package file lock |
| Ruff lint and formatting | Passed |
| Full offline pytest suite | 116 tests passed in 12.54 seconds; the existing test-transport warning remains ANV-015 |
| Real-process offline smoke | Passed API restart, separate worker, results, idempotency, feedback, cancellation, and deletion |
| Tracking validation | Passed |
| Staged whitespace/content review | Passed after removing extra EOF blank lines in four foundation files |
| Staged credential-pattern check | No high-confidence credential patterns found; this is a focused check rather than a proof of absence |
| Ignored-artifact review | `.env`, database, virtual environment, and built wheel paths are ignored and excluded from the commit |
| `git push -u origin main` | Created remote main and configured upstream tracking; no force push |
| `git rev-parse HEAD` and `git ls-remote origin refs/heads/main` | Both returned c3fd2f663f051a65c5ce3a39e702f94036850912 immediately after the initial push |

## Authentication and CI

The initial CLI push had no credentials. GitHub connector writes separately returned `403 Resource not accessible by integration`; listing organization repositories through that connection returned none. Device sign-in through Git Credential Manager succeeded, and the authenticated CLI push completed. No credentials or device verification codes are stored in repository files. Future agents should use local Git for writes unless the connector's repository access has been independently corrected.

GitHub Actions started [Checks run 38900815551](https://github.com/Kshurika-Consultancy/anvesha/actions/runs/38900815551) for the initial source commit. Its observed state while recording this report was `in_progress`; this report does not claim a completed remote CI result. A documentation-only follow-up records publication evidence and task completion; it also receives its own CI run.

Source publication does not deploy the service or complete M6. Local hosting and quality limitations remain in README, SECURITY, and the task ledger.

## Initial CI result and follow-up

The first run subsequently completed: Windows/Python 3.14 and both Linux jobs passed; Windows/Python 3.12 passed all 116 tests and smoke assertions but failed removing server.log with WinError 32. The Windows virtual-environment launcher can outlive parent-only process termination through its API descendant.

ANV-018 adds full Windows process-tree shutdown, a real descendant/log-handle regression, and success output only after cleanup. Local validation: 118 tests passed in 12.86 seconds, Ruff and tracking passed, and the real-process smoke passed including cleanup. Remote verification of this fix is pending at this commit.
