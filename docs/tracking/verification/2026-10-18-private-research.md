# ANV-021 private research preview verification

Date: 2026-10-18. Local Windows, Python 3.14.4. Starting main: `123f678`.
Existing ANV-020 coaching-guidance changes were preserved; three coached examples
remain private practice, with zero submitted labels. This turn is local development,
not a release, public deployment or new independent assessment.

## Delivered slice

The user prioritizes a useful open-source service for private home-server research,
primarily local models, with optional OmniRoute interoperability. The scoped
[decision](../../decisions/0005-private-research-and-optional-llm.md) and
[native guide](../../PRIVATE_RESEARCH.md) explain why to start with useful private
corpora, explicit model processing and a reproducible first-run path. This does not
close the general-web acquisition or measured quality gates.

The new `llm.py` implements a fixed-endpoint chat client with strict JSON candidate
permutations, bounded payloads, no tools/URL discovery, a total async deadline,
redirect/proxy controls, and periodic job lease/cancellation checks. Configuration
defaults off and each request additionally opts in. Default lexical runs do not
call a configured model. Models/gateway code are not bundled or downloaded.

An additive job-column migration retains legacy lexical hashes, snapshots and
feedback. Accepted model configuration is fingerprinted without credentials.
Model outage, invalid output or changed configuration produces a warning and
lexical fallback; original URLs, content and rights remain intact. Capability
discovery is authenticated. `anvesha doctor` checks setup offline without creating
a database or printing secrets. The CLI preserves model configuration and disables
API access logs; independent gateway/proxy logs remain outside its control.

## Actual checks

- `uv sync --extra dev --locked`: passed, pinned development environment.
- `uv run --extra dev pytest`: **240 passed in 39.50 seconds** (55 new checks).
  One pre-existing Starlette/httpx deprecation remains ANV-015. New cases cover
  invalid/malicious/duplicate output, header/body deadlines, cancellation before and
  during dispatch, lease renewal, prefix/tail ranking, fallback, default no-call,
  capability/auth boundaries, legacy migration/idempotency/feedback and diagnostics.
  Final review moved heartbeat calls off the async event loop; a regression proves
  a blocked database checkpoint cannot prevent HTTP deadline cancellation.
- `uv run --extra dev ruff check .`, `ruff format --check .`,
  `python scripts/check_tracking.py` and `git diff --check`: passed at the
  implementation checkpoint; tracking is repeated after this evidence update.
- `uv run --extra dev python scripts/smoke_mvp.py`: passed real API/worker processes,
  restart persistence, snapshots, idempotency, feedback, cancellation and deletion.
  The extended smoke also checks diagnostics and opt-in model reranking/fallback
  over real loopback HTTP with an explicitly synthetic model server. Both API and
  synthetic server stop before success is printed.
- `uv build --out-dir .anvesha/dist-anv021`: wheel/source distribution built.
  Installed the wheel offline into `.anvesha/wheel-anv021` with runtime dependencies
  only; isolated import confirmed the installed module location. The same real
  process smoke passed under that installed interpreter. Distribution inspection
  confirmed the new module is included and private workspaces/credentials are not.
- Review pilot status: zero submissions/imports/new human judgments; original
  packet and review database SHA-256 values still match the pre-change checks.

Fresh lexical benchmark repeats completed against both archived reports without
changing any published rankings or metrics:

- `python -m anvesha.evaluation run --output-dir .anvesha/evaluation/anv021-scifact
  --compare reports/evaluation/scifact-v1/summary.json`: all 500 queries / three
  systems; exact fingerprint
  `6098bc1981e868bc5b7f0cf055f27b42ba717c5a185889caeb628b20b5ef65ef`,
  with M1/BM25 parity retained.
- `python -m anvesha.intent_evaluation run --output-dir .anvesha/evaluation/anv021-xquad
  --compare reports/evaluation/xquad-intents-v1/summary.json`: all 756 queries /
  three systems; exact fingerprint
  `2b7914b9dfa02982a6c7d0c185b254d3966ce32d106ab724b34ad2f8ff6e3d2a`,
  with zero new human labels.
- Offline verification of both archived reports and the multilingual dataset also
  passed. These checks show unchanged lexical behavior, not new model quality.

## Limits and next gates

Protocol fixtures and the synthetic HTTP smoke do not prove actual Ollama model
behavior, every OmniRoute provider combination, or a retrieval-quality improvement.
No actual model, external gateway or paid API was contacted. ANV-023 owns live
backend acceptance, pinned model/hardware/route identities and independent quality
measurements. A local gateway can forward externally; Anvesha cannot audit that.
Document processing rights and downstream retention/training terms remain separate.

Docker is not installed here; no container build/runtime claim is made. ANV-022
owns verified container deployment and an accessible client without CDN assets.
Existing FastAPI interactive documentation uses CDNs, documented as a privacy
limit. ANV-009/ANV-011 own broader approved discovery and safe acquisition;
ANV-010 retains the full hybrid/planning quality gate. ANV-008 still owns hosted
hardening/automatic retention. Coached judgments remain excluded by operator
instruction, pending ANV-020's enforced exclusion/reassignment implementation.
