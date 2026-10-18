# Retrieval evaluation

Tasks ANV-007, ANV-019, ANV-020. The first M2 slice establishes a reproducible baseline on real published data. It does not complete the planned multi-intent user study or the rest of M2.

ANV-023 adds a separately versioned [real local-model pilot](LOCAL_LLM_EVALUATION.md)
using these existing expert annotations. Its selection/protocol are frozen before
inference. Operational fallbacks remain in paired metrics; raw prompts/abstracts
stay local. A small scientific sample does not establish quality for Anvesha's
intended coding, personal IoT/assets or private-agent integrations. Independent
multi-intent assessment remains ANV-020. The original lexical reports are unchanged.

## Data and scope

The [SciFact snapshot](../benchmarks/scifact-v1/README.md) has 5,183 scientific abstracts and 500 scientific claim queries. Development uses 200 deterministic samples from BEIR train; evaluation uses all 300 BEIR test queries. The shipped claim wording and document relevance grades come from published SciFact evidence annotations, with licences and transformations documented. **New Anvesha human assessments: zero.**

The public benchmark measures finding annotated evidence in a fixed English corpus. Supporting and refuting evidence are both relevant. It does not score truth, source authority, snippet support, freshness, browsing, latency over the network, or general-web discovery. All other intended query strata currently have zero evaluated queries. The original ANV-007 acceptance remains open until representative strata and independent reviewed judgments are available under ANV-020.

Raw abstracts, temporary indexes and review pools stay in ignored local storage. Only licensed query/annotation records, identifiers, metadata and metrics are committed. The source-specific [rights review](../policies/sources/beir_scifact_evaluation.json) separates CC-BY-4.0 annotations from the ODC-By-1.0 database and underlying article rights.

## Baselines and fairness

All three systems receive identical queries and the entire 5,183-document collection. They retrieve up to **50** documents; metrics do not pretend the current API retrieves 100.

| System | Definition |
| --- | --- |
| `token_overlap_v1` | Lowercase unique token intersection count over title and text; ties by document ID. A simple independent floor |
| `fts5_bm25_title2_body1` | Actual Store.search_local method, escaped OR tokens, SQLite FTS5 BM25 with title/body weights 2/1 |
| `anvesha_m1_local` | Actual job creation, process_one worker, production rank fusion, persisted final snapshot, then read/delete in an isolated temporary benchmark DB |

The M1 baseline exercises real worker/storage/ranking code, not a copied approximation or a label-informed ranking. It excludes the HTTP layer and all remote connectors. Benchmark document URLs identify records within the pinned upstream archive (`archive URL#document_id=...`); they are not fabricated paper landing pages and are never fetched. Relevant-document labels are used only after retrieval, not to build the index or order candidates.

With one local source, RRF preserves source ordering. Direct BM25 and M1 equality is an expected baseline finding; it is not a measured improvement. No hyperparameters were tuned or new models trained. Timings include different orchestration costs and are descriptive CPU/local I/O measurements, not an HTTP latency comparison.

## Metrics and uncertainty

Every selected query is scored. A worker failure aborts the run; it is never silently omitted. Empty results score zero. Duplicate/unknown document IDs, missing query/system runs, mismatched qrels, corrupt files, NaN timings and invalid report metrics fail validation.

- **nDCG@10:** binary discounted gain divided by ideal discounted gain over all known relevant documents; discount is `1 / log2(rank + 1)` for one-based ranks.
- **MRR@10:** reciprocal rank of the first known relevant result in the top ten, or zero.
- **Precision@10:** known relevant hits divided by ten, including short/empty lists.
- **Recall@10/@50:** retrieved known relevant documents divided by all known positives for that query.
- **Success@10:** whether at least one known relevant document appears in the first ten.

Unjudged pairs are treated as zero for these conventional metrics. Incomplete judgments can underestimate usefulness; recall is relative to known annotations, not all relevant documents or the web. Confidence intervals are descriptive 95% percentile bootstraps over query units (1,000 samples, seed 20261016). Paired nDCG deltas use aligned query IDs. No multiple-comparison correction or broad superiority claim is made.

Development/evaluation summaries remain separate. Per-query rankings and metrics allow investigation of failures. The report records input/corpus hashes, production pipeline version, exact source-file hashes, environment, bootstrap settings and the pre-run Git revision. Source-file hashes identify the evaluated code when files were not yet committed; do not treat the pre-run revision alone as an exact implementation pin. Historical baselines retain their code fingerprints when later code changes.

## Commands

```text
uv run --extra dev python -m anvesha.evaluation prepare --download
uv run --extra dev python -m anvesha.evaluation run --export-pool
uv run --extra dev python -m anvesha.evaluation verify
```

Only the explicit download step uses the network. It rejects redirects, caps bytes, sets a total timeout and verifies SHA-256 before processing fixed ZIP members. No archive paths are extracted. The downloader preserves an existing cache when acquisition fails. Snapshot preparation refuses to change existing versioned query/annotation files.

To independently rerun and compare rankings, write to a separate ignored report directory:

```text
uv run --extra dev python -m anvesha.evaluation run --output-dir .anvesha/evaluation/repeat --compare reports/evaluation/scifact-v1/summary.json
```

`--compare` checks the prior ranking fingerprint and preserves its prior report on mismatch. It compares rankings; measured durations and generation timestamps naturally vary. `verify` checks all shipped hashes, all query/document references, each per-query metric, aggregate metrics/bootstrap intervals, ranking fingerprint and rendered report. It needs neither the raw abstracts nor network access, so it runs in default CI. Verification establishes artifact consistency; it does not independently repeat retrieval without the corpus.

## Independent review workflow

`run --export-pool` writes `.anvesha/evaluation/scifact-v1/review-pool.jsonl`. It pools the top ten candidates from each system, removes duplicate pairs, and orders by a deterministic hash independent of system rank. System identities, existing qrels and scores are absent. **Grade, reviewer and rationale remain null** until a real person supplies them. Full local abstract text makes the pool unsuitable for automatic publication; it stays ignored.

For ANV-020, have consenting assessors judge relevance to finding evidence about the original query, allowing both support and refutation. Use null for abstention and document a binary grading rubric before collection. Double-label a subset, record reviewer pseudonyms, adjudicate disagreements and measure agreement. Keep the mapping of identities private. Do not feed the evaluation split into ranking training. Extend the pool schema/rubric under tracking before claiming graded or new human results.

Representative product evaluation still needs navigation, exact constraints, ambiguity, comparisons, locale/date, multilingual and adversarial queries, along with permitted SearXNG/external comparisons. Neither benchmark size nor a high scientific score substitutes for those missing measurements.

## ANV-020 implementation slice

The [expanded snapshot](../benchmarks/xquad-intents-v1/README.md) adds 720 published XQuAD query instances and 720 passages in English, Spanish and Hindi, plus 36 explicitly AI-authored, unjudged intent probes. It covers six topic groups and reserves article groups, including translations, together in a project holdout. Historical QA context mappings remain separate from independent relevance judgments. Cross-benchmark scores are not comparable: the collection size, task and positive-label definitions differ.

The [review workflow](review/README.md) supplies a frozen rubric, system/gold-blinded packets and offline browser forms, separate reviewer credentials, atomic/revision-safe imports, abstentions, pairwise agreement and a separate adjudicator. A bounded pilot is prepared locally with no submitted human labels. No synthetic test labels enter it or its public report. ANV-020 and ANV-007 remain in progress until actual assessors, reviewed representative strata and permitted comparisons satisfy their acceptance criteria. The scientific report above remains a historical baseline; its legacy flat pool is not silently migrated into human results.
