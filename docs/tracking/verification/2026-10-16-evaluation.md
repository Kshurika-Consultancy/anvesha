# M2 scientific retrieval baseline verification

Date: 2026-10-16. Task ANV-019; partial delivery toward ANV-007. Broader representative strata and independent pooled review remain ANV-020.

## Scope and provenance

The real published BEIR SciFact corpus has 5,183 documents. The versioned snapshot selects 200 development queries deterministically from BEIR train and preserves all 300 BEIR test queries as evaluation data, with 569 inherited binary evidence judgments. These are published expert-derived annotations; zero new Anvesha human assessments were made. Supporting and refuting evidence both count as relevant.

Primary-source licence review, attribution, transformations and exact data hashes are in the [snapshot](../../../benchmarks/scifact-v1/README.md), [rights manifest](../../../policies/sources/beir_scifact_evaluation.json), and [ADR 0003](../../decisions/0003-published-retrieval-evaluation.md). Raw abstracts, review-pool text and indexes stay in ignored local storage. No production connector or corpus import is enabled by evaluation preparation.

Windows/Python 3.14.4, SQLite 3.50.4, uv 0.11.8; locked runtime/dev dependencies. No additional package, paid API, hosted model, GPU or LLM is required. Explicit dataset preparation is the only network operation in the benchmark workflow; default tests and artifact verification are offline.

## Executed checks

| Command or inspection | Observed result |
| --- | --- |
| `uv run --extra dev python -m anvesha.evaluation prepare --download --archive .anvesha/evaluation/acquisition-check.zip` | Downloaded the fixed university archive, verified SHA-256 and four member hashes; reproduced the versioned 500-query snapshot |
| `uv run --extra dev pytest tests/test_evaluation.py -q` | 30 passed; analytical metric cases, real worker fixtures, semantic/hash corruption, report provenance, comparison preservation, bounded download failure/cleanup |
| `uv run --extra dev ruff check .` | Passed |
| `uv run --extra dev ruff format --check .` | Passed; 43 Python files formatted |
| `uv run --extra dev pytest -q` | 148 passed in 22.40 seconds; one existing Starlette/httpx deprecation tracked as ANV-015 |
| `uv run --extra dev python scripts/check_tracking.py` | Passed task graph, references, completion evidence, source-policy fields and code reminders |
| `uv run --extra dev python scripts/smoke_mvp.py` | Passed real local HTTP/API restart, separate worker, lifecycle and process/file cleanup; two demo results |
| `uv run --extra dev python -m anvesha.evaluation run --export-pool` | All 500 queries and three systems completed in 250.830 seconds; no tuning; 8,051 unlabelled pooled pairs stay local |
| `uv run --extra dev python -m anvesha.evaluation verify` | Passed every input hash, all 1,500 query/system records, metrics, bootstrap intervals, ranking fingerprint and rendered report |
| Compare `summary.code_sha256` with the six evaluated source files | All matched the frozen code used for the final run |
| Compare evaluated-code and benchmark file hashes with staged Git objects | All matched; staged byte content preserves the measured source/input fingerprints |
| `uv run --extra dev python -m anvesha.evaluation run --output-dir .anvesha/evaluation/repeat --compare reports/evaluation/scifact-v1/summary.json` | Fresh index, all 500 queries and three systems passed; identical full ranking fingerprint |
| `uv run --extra dev python -m anvesha.evaluation verify --output-dir .anvesha/evaluation/repeat` | Repeat report verified independently; source hashes and paired comparisons match the published baseline |
| `uv build --out-dir .anvesha/dist` | Source distribution and wheel built; wheel contains all evaluation modules; raw corpus and review pools absent from source distribution |
| `uv run --isolated --no-project --with .anvesha/dist/anvesha_search-0.1.0-py3-none-any.whl python -m anvesha.evaluation verify` | Installed wheel verified the report using runtime dependencies only |
| `git check-attr text eol -- benchmarks/scifact-v1/queries.jsonl benchmarks/scifact-v1/qrels.tsv benchmarks/scifact-v1/document_ids.txt reports/evaluation/scifact-v1/per_query.jsonl` | All explicitly use LF; cross-platform checkout must preserve byte-hashed inputs |
| `git diff --check` | Passed |

Publication and remote CI results are pending at this local verification checkpoint. The final report comes from the frozen evaluation code; the fresh-index repeat and earlier exploratory run used the same untuned retrieval parameters and produced the same rankings.

## Measured baseline

On the 300-query evaluation split, M1 and direct BM25 both score nDCG@10 **0.672633** (95% query bootstrap interval **[0.628640, 0.722937]**) and known-relevant recall@50 **0.866056**. The token-overlap floor scores nDCG@10 **0.482984** and recall@50 **0.725944**. M1 preserves direct BM25 rankings for every query, as expected for a single-source RRF pipeline. This establishes a starting point, not a new ranking improvement.

The ranking fingerprint is `6098bc1981e868bc5b7f0cf055f27b42ba717c5a185889caeb628b20b5ef65ef`. Full development/evaluation metrics and provenance are in the [measured report](../../../reports/evaluation/scifact-v1/README.md); timings and timestamps are descriptive and excluded from that ranking fingerprint.

## What the evidence does and does not establish

The harness creates an isolated temporary index, retrieves every query with token overlap, actual Store BM25 and the actual M1 durable worker, then computes metrics from the original judgments. Worker failures abort rather than silently removing queries. The shipped report can be recomputed from its query rankings and annotations without raw abstracts or network access; this checks artifact consistency rather than independently rerunning retrieval.

The optional review pool contains the union of the systems' top ten results, shuffled by a deterministic hash without rank/system/qrel fields. Grade, reviewer and rationale remain null. It provides work for real assessors and does not manufacture new labels.

This measures English scientific evidence retrieval in a fixed corpus. It does not establish general-web discovery, freshness, source authority, factual truth, multilingual coverage, Google/SearXNG parity, or readiness for public hosting. Public benchmark data may have appeared in pretrained models. ANV-007 remains in progress, ANV-020 is planned, and hosted hardening remains ANV-008.
