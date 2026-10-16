# ANV-020 corpus and human-workflow implementation verification

Date: 2026-10-16. ANV-020 remains **in progress** because actual independent assessments, native-speaker review and permitted external comparisons have not happened. This report verifies the delivered implementation, not completed human research.

## Data and behavior

- Pinned XQuAD English/Spanish/Hindi sources: 720 real passages, 720 aligned published query instances and 720 derived answer-context mappings. Added 36 explicitly AI-authored, unjudged intent probes. Six topic groups; 585 published instances outside science/health.
- Article grouping keeps all translations and related draft queries together: 36 development and 12 holdout articles. The public holdout is reserved from project tuning, not a private or model-unseen set.
- Actual M1 worker, direct BM25 and token overlap execute 2,268 query/system runs. Public reports contain IDs, input/code hashes, coverage and descriptive context-mapping metrics, not passages or new human labels.
- A private 10,813-pair candidate pool produced a bounded English-query development pilot: 200 pairs across 52 queries, 42 double assigned, 242 total assignments. Placeholder pseudonyms have no enrolled people or submissions yet. No agreement value or human quality score is claimed.
- Local workflow freezes candidates/rubric, signs immutable packet contents, authenticates imports, stores revisions and attestation receipts, preserves abstentions, reports per-pair agreement and requires a separate adjudicator. Immutable exports stay private and never automatically train/publish.

See [dataset/attribution](../../../benchmarks/xquad-intents-v1/README.md), [rights manifest](../../../policies/sources/xquad_evaluation.json), [ADR 0004](../../decisions/0004-multilingual-corpus-and-human-review.md), [workflow/rubric](../../review/README.md), and [measured report](../../../reports/evaluation/xquad-intents-v1/README.md).

## Executed checks

| Command/review | Observed result |
| --- | --- |
| `uv run --extra dev python -m anvesha.review_data prepare --download --sources-dir .anvesha/evaluation/xquad-acquisition-check` | Three fixed revision-pinned downloads, hashes/answer alignment checked, versioned snapshot reproduced |
| `uv run --extra dev python -m anvesha.intent_evaluation run` | All 756 queries and three systems completed; fingerprint `2b7914b9dfa02982a6c7d0c185b254d3966ce32d106ab724b34ad2f8ff6e3d2a`; 0 new human judgments |
| `uv run --extra dev python -m anvesha.intent_evaluation verify` | All counts, ranks, hashes, derived metrics and rendered report verified offline |
| `uv run --extra dev python -m anvesha.review init --reviewers reviewer-a reviewer-b --adjudicator adjudicator --languages en`; export both reviewer packets | Prepared 200-pair local pilot and two offline forms; 0 labels, 0 receipts and all 200 pairs pending |
| `uv run --extra dev pytest -q` | Final run: 185 passed in 26.86 seconds; one existing Starlette/httpx warning under ANV-015 |
| `uv run --extra dev ruff check .`; `uv run --extra dev ruff format --check .` | Passed at final code verification |
| `uv run --extra dev python scripts/check_tracking.py` | Passed graph, links, source policy and tracked reminders at implementation checkpoint |
| `uv run --extra dev python scripts/smoke_mvp.py` | Offline actual HTTP/restart/worker/lifecycle/process and file cleanup passed |
| `uv build --out-dir .anvesha/dist` | Wheel and source distribution built successfully |
| `uv run --extra dev python -m anvesha.intent_evaluation run --output-dir .anvesha/evaluation/xquad-repeat --compare reports/evaluation/xquad-intents-v1/summary.json` | Fresh index; all 756 queries/three systems produced the identical ranking fingerprint |
| `uv run --extra dev python -m anvesha.intent_evaluation verify --output-dir .anvesha/evaluation/xquad-repeat` | Independent repeat artifacts verified offline |
| Installed wheel: `python -m anvesha.intent_evaluation verify` and `python -m anvesha.review status` using `uv run --isolated --no-project --with .anvesha/dist/anvesha_search-0.1.0-py3-none-any.whl` | Both passed with runtime dependencies only; final wheel reads the prepared pilot without changing its zero-submission state |
| Compare seven evaluated-code hashes; inspect wheel/source distribution members | Code hashes match the report; workflow modules included; ignored raw corpus and credentials excluded |
| `uv run --extra dev python -m anvesha.evaluation verify` | Existing SciFact report still verifies; no scientific baseline rewriting |
| Compare staged Git objects with input and evaluated-code hashes; inspect staged paths | All hashes match; private corpus, review workspace, credentials and responses excluded |

The 37 added tests cover group/translation isolation, modified input hashes/provenance, forbidden draft-label promotion, real worker fixtures, no implicit network, failed acquisition cleanup, HMAC/credential/attestation checks, malformed packet shapes, atomic invalid-packet rollback, idempotent labels, stale revisions/adjudication, abstentions, hand-calculated agreement/kappa, immutable exports and CLI packets. The optional Node test passed locally and executes Unicode display/navigation/attested JSON download in a simulated DOM; it is not a browser visual audit. All assessment grades in tests are explicitly synthetic and never count as human evidence.

Local code/data verification, the full-run repeat, installed-wheel and staged byte checks are complete. Publication/CI are pending at this checkpoint.

## Remaining acceptance and limits

Enroll consenting independent people, validate native-language queries/rubric, collect double labels, adjudicate disagreements and review actual agreement before claiming any human result. The pilot sample is not population representative. Plan further current-web/locale coverage and permitted external comparisons. SciFact's older flat pool still needs a versioned session adapter; do not silently import its blank or filled fields as new assessments. These are remaining ANV-020 work, not a completed ANV-007 study.

Keep private identities, credentials, responses, workspaces and raw passages out of Git. Local credentials and script attestation do not independently prove a person's identity or independence. No public deployment, paid dependency, model download, automatic learning or message to an assessor occurred.
