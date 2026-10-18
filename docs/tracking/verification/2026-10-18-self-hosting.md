# ANV-022 self-hosting and browser verification

Date: 2026-10-18. Scope: LLM-default private-corpus research, browser client,
native configuration/supervision, and container installation. Root owns this slice.
Implementation commit `0193557c109939b032fafbc28eaddc60aac19d5b` is published on
main; local/remote equality and a clean tracked tree were verified after pushing.

ANV-021 was committed/pushed as `83830bf4ace6df5702a5921f17ef3d37f991fa91`.
Local/remote main equality was checked. Its four Windows/Linux Python 3.12/3.14
jobs passed in [Actions run 39109656383](https://github.com/Kshurika-Consultancy/anvesha/actions/runs/39109656383).

## Observed local checks

- Pinned Windows/Python 3.14.4: 252 tests passed; final repeat took 32.18 seconds. The existing
  Starlette/httpx warning remains ANV-015.
- Ruff lint/format, tracking and `git diff --check` pass (70 Python files).
- `uv run --extra dev python scripts/smoke_mvp.py` passed: real HTTP acceptance,
  API restart, separate worker, stable snapshots, idempotency, feedback, cancellation,
  default LLM transport through a synthetic loopback fixture, visible fallback and cleanup.
- `uv run --extra dev python scripts/smoke_selfhost.py` passed: exclusive private
  setup, saved keys/config, packaged browser routes, supervised separate processes,
  default model mode, stable restart, sibling shutdown after a child exit and
  secret-free service output. Temporary services/files were cleaned up.

## Browser checks

Used the computer-use skill's browser controls against a separate loopback
synthetic collection and protocol fixture. This never used the independent human
review form/database or actual user queries. Verified default LLM selection,
connection, successful model-reordered results, visible invalid-response fallback,
10-to-20-result pagination, snapshot feedback with learning off, plain-text hostile
markup, and reload disconnection. Also verified terminal cancellation, HTTP-error
fallback, Disconnect clearing displayed queries/results, desktop visuals and a
390-pixel mobile viewport (375-pixel content area with no horizontal overflow).
Browser console reported no warnings/errors. The temporary viewport was reset,
the tab closed, and the fixture API/worker/model services stopped. These were
synthetic operational feedback votes only, never independent review judgments.

The first custom browser fixture omitted the required assistant role; Anvesha
correctly exposed `llm:invalid_response`. The fixture was corrected, and a fresh
search completed with `LLM reordered` results. No model quality claim follows.

## Distribution

`uv build --out-dir .anvesha/dist-anv022` passed. Wheel inspection found all three
browser assets; wheel/source distribution exclude private configuration/workspaces.
An isolated runtime-only environment was installed offline using exported locked
dependencies. Its imported package resolves under site-packages, and its
`scripts/smoke_selfhost.py` run passed, including restart and complete cleanup.

## Container gate

Docker is unavailable on this workstation. The actual Linux container job passed
in [Actions run 39111550834](https://github.com/Kshurika-Consultancy/anvesha/actions/runs/39111550834)
for implementation commit `0193557`. It built and ran `scripts/smoke_container.py`,
including non-root UID 10001, local persistence, private chat connectivity,
default LLM jobs, feedback, queued-job/API restart, stable snapshots, model outage
and project-scoped cleanup. **All five jobs passed:** the container job and the
four Windows/Linux Python 3.12/3.14 matrix jobs. The container log explicitly
reports successful model connectivity, persistence/fallback and cleanup. This
closes ANV-022's scoped acceptance; actual model/backend quality remains ANV-023.

Offline report checks passed locally: 500 SciFact queries retain fingerprint
`6098bc1981e868bc5b7f0cf055f27b42ba717c5a185889caeb628b20b5ef65ef`;
756 multilingual/intent queries retain fingerprint
`2b7914b9dfa02982a6c7d0c185b254d3966ce32d106ab724b34ad2f8ff6e3d2a`.
There are zero new human judgments. This validates archived reports, not a new
full-corpus quality experiment or measured LLM improvement.

Python, uv and optional Ollama image manifest digests were retrieved from their
official registries on this date. Runtime dependencies remain locked; the optional
model runtime/model weights have separate licences. No paid API or model download
was used by verification. Source discovery/general web coverage, actual model or
OmniRoute acceptance and independent relevance gains remain ANV-009/ANV-011/ANV-023.
Public hosting remains gated by ANV-008. The coached ANV-020 practice rows remain
excluded from independent review; no new human assessments were created.
