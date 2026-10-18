# Contributing to Anvesha

Read [AGENTS.md](AGENTS.md) and [development status](docs/tracking/STATUS.md) before changing code. The same scope and verification rules apply to human and AI-assisted contributions. Tie work to a ledger task; add new work before implementing it. Coordinate file ownership when working concurrently.

Install the locked development environment with `uv sync --extra dev --locked`. Run Ruff, pytest, and `scripts/check_tracking.py` as documented in AGENTS.md. All default tests must run offline and without paid accounts. Changes to API semantics need integration tests; changes to retrieval need measured comparisons before quality claims.

ANV-022 adds `scripts/smoke_selfhost.py` for native first-run/restart/supervision.
The separate `scripts/smoke_container.py` requires Docker Compose v2 and is checked
in Linux CI; it uses an isolated project and synthetic model fixture, then removes
only that test project's volumes. Browser checks use synthetic collections and
never count as independent human judgments. See [self-hosting](docs/PRIVATE_RESEARCH.md)
and [verification](docs/tracking/verification/2026-10-18-self-hosting.md).

Submit small, reviewable changes explaining the observable problem, resulting behavior, validation evidence, and limitations. Update affected docs and handoff. Record significant architecture changes as numbered ADRs. New sources require a rights manifest; new model dependencies require their own license and resource review.

Only contribute code/data you have rights to contribute. Independently written code is Apache-2.0; preserve third-party notices. Never submit API keys, private search records, provider payloads without export permission, or AGPL code presented as Apache-2.0. Apache-2.0 section 5 governs intentionally submitted contributions unless explicitly stated otherwise; no separate CLA or copyright assignment is introduced here.

Publication, release, and deployment are separate decisions. Local completion does not authorize them.
