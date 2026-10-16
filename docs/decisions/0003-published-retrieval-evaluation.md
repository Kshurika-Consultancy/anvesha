# ADR 0003 Start M2 with a pinned published retrieval benchmark

Status: accepted for the first M2 slice, 2026-10-16. Tasks: ANV-007, ANV-019, ANV-020.

The synthetic demo verifies mechanics but cannot establish relevance. Start with the BEIR-formatted SciFact corpus and its published expert-derived evidence annotations. Evaluate 200 deterministically selected BEIR training queries as development data and all 300 BEIR test queries as evaluation data, against the full 5,183-document corpus. Do not tune on the evaluation split. The public benchmark is not guaranteed unseen by pretrained models.

This is English scientific claim-evidence retrieval. Relevant evidence can support or refute a claim; ranking it does not establish the claim's truth. It does not represent navigation, shopping, local, multilingual, freshness, or general-web coverage. The original ANV-007 multi-intent and independent pooled-judgment requirements stay open under ANV-020.

Keep upstream abstract text and imported SQLite indexes in ignored local storage. Commit only the CC-BY-4.0 claim/query subset and relevance annotations with attribution, source IDs, split provenance and checksums, plus code and measured reports. The corpus's published database licence is ODC-By-1.0; that does not relicense underlying articles or authorize a production source connector. Downloads are explicit, fixed-URL, bounded, and hash-checked; default tests/CI are offline and do not fetch third-party data.

Run a simple token-overlap floor, direct SQLite FTS5/BM25, and the actual M1 worker against identical documents and depth 50. The single local-source RRF stage should preserve the BM25 order; report equivalence rather than inventing an improvement. Use binary nDCG@10, MRR@10, precision@10 and known-relevant recall@10/@50, query-level metrics, deterministic bootstrap intervals, failures, input/code fingerprints, and separate development/evaluation summaries. Missing judgments are unknown, treated as zero only for standard metric calculation. Export a blinded pool for future assessors without creating fake human labels.

Primary references: [SciFact data/code licences](https://github.com/allenai/scifact/blob/master/LICENSE.md), [SciFact paper](https://aclanthology.org/2020.emnlp-main.609/), [BEIR download and published checksum](https://github.com/beir-cellar/beir), [ODC-By-1.0](https://opendatacommons.org/licenses/by/1-0/).
