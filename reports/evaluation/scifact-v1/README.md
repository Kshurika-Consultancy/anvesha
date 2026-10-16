# SciFact retrieval baseline

Task: ANV-019. Fixed English scientific corpus; published upstream evidence judgments.

500 queries (200 development, 300 evaluation), 5183 documents, depth 50.
No new Anvesha human labels or model training. Relevant evidence may support or refute the query claim.

| Split | System | nDCG@10 (95% query bootstrap CI) | MRR@10 | Recall@50 |
| --- | --- | --- | --- | --- |
| development | token_overlap_v1 | 0.4883 [0.4259, 0.5477] | 0.4624 | 0.7422 |
| development | fts5_bm25_title2_body1 | 0.6735 [0.6185, 0.7218] | 0.6402 | 0.8965 |
| development | anvesha_m1_local | 0.6735 [0.6185, 0.7218] | 0.6402 | 0.8965 |
| evaluation | token_overlap_v1 | 0.4830 [0.4347, 0.5393] | 0.4569 | 0.7259 |
| evaluation | fts5_bm25_title2_body1 | 0.6726 [0.6286, 0.7229] | 0.6401 | 0.8661 |
| evaluation | anvesha_m1_local | 0.6726 [0.6286, 0.7229] | 0.6401 | 0.8661 |

M1 and direct BM25 rankings identical: True.
One-source RRF preserves BM25 ordering; equivalence is expected, not an improvement claim.

Unlisted query/document pairs are unjudged, treated as zero for standard metrics. Recall is relative to known relevant documents, not the whole web.
No navigation, comparison, locale, multilingual or freshness claims follow. Timings describe this local run and include different orchestration overheads.

[Summary and provenance](summary.json), [per-query rankings and metrics](per_query.jsonl), [methodology](../../../docs/EVALUATION.md).
