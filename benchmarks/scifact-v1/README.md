# SciFact evaluation snapshot

Task ANV-019. This is real published scientific claim/evidence retrieval data, not Anvesha's synthetic demo. The corpus is the full **5,183-document BEIR SciFact** snapshot. The checked-in subset has **500 queries and 569 binary relevance judgments**: 200 development queries selected from BEIR train and all 300 BEIR test queries reserved for evaluation.

The query/relevance labels originate from the upstream expert-annotated SciFact collection. They are not new Anvesha assessor judgments. A relevant document may support or refute the claim. Unlisted pairs are unjudged; they are not certified irrelevant. These statements are search inputs and must not be treated as medical advice or verified facts.

## Contents and licences

- `queries.jsonl`: query ID/text, development/evaluation and upstream split, language, stratum and annotation provenance. CC-BY-4.0.
- `qrels.tsv`: selected upstream document relevance annotations. CC-BY-4.0.
- `document_ids.txt`: identifiers of the full corpus, allowing offline report validation without abstract text.
- `manifest.json`: archive/member/subset SHA-256 hashes, upstream published MD5, exact counts and selection method.

**Attribution:** SciFact, by David Wadden, Shanchuan Lin, Kyle Lo, Lucy Lu Wang, Madeleine van Zuylen, Arman Cohan and Hannaneh Hajishirzi, [Fact or Fiction: Verifying Scientific Claims, EMNLP 2020](https://aclanthology.org/2020.emnlp-main.609/). The [upstream licence](https://github.com/allenai/scifact/blob/master/LICENSE.md) releases claims/evidence annotations under [CC-BY-4.0](https://creativecommons.org/licenses/by/4.0/). Anvesha selects/reformats those records, adds split/provenance metadata and hashes, and leaves the original query wording and relevance grades intact. Copyright/attribution remains with the original contributors; repository Apache licensing does not replace this data licence.

**BEIR attribution:** Nandan Thakur, Nils Reimers, Andreas Rucklé, Abhishek Srivastava and Iryna Gurevych, [BEIR: A Heterogeneous Benchmark for Zero-shot Evaluation of Information Retrieval Models](https://arxiv.org/abs/2104.08663). The [official source](https://github.com/beir-cellar/beir) provides the formatted snapshot and MD5. BEIR explicitly leaves dataset licensing with original owners.

**Corpus:** raw abstracts are **not included in Git**. They derive from S2ORC, attributed to Kyle Lo, Lucy Lu Wang, Mark Neumann, Rodney Kinney and Daniel S. Weld. The upstream dataset notice identifies [ODC-By-1.0](https://opendatacommons.org/licenses/by/1-0/) for this database. Database rights do not grant every underlying article right. Preparing the benchmark does not add it to the production API or approve full-text redistribution or training. See the [rights manifest](../../policies/sources/beir_scifact_evaluation.json).

## Reproduce

From the repository root, using the locked environment:

```text
uv run --extra dev python -m anvesha.evaluation prepare --download
uv run --extra dev python -m anvesha.evaluation run --export-pool
uv run --extra dev python -m anvesha.evaluation verify
```

Only `prepare --download` uses the network: a fixed, hash-checked, approximately 2.8 MB university archive, without an account or paid API. `prepare` without that flag uses the cached archive or an explicit `--archive` path. The corpus goes to ignored `.anvesha/evaluation/scifact-v1/`. No model download, LLM, GPU or search-provider API is required.

The seed string `anvesha-scifact-v1` deterministically selects the 200 lowest SHA-256-ranked train IDs, excluding exact normalized evaluation-query duplicates. No parameter tuning was performed on the evaluation split. Published data is not a private holdout and may be familiar to pretrained models. Do not merge development and evaluation scores into a product-quality claim.

See [methodology](../../docs/EVALUATION.md), [measured report](../../reports/evaluation/scifact-v1/README.md), and [ADR 0003](../../docs/decisions/0003-published-retrieval-evaluation.md). General-web, navigation, time-sensitive and multilingual coverage plus independent pool review remain ANV-020.
