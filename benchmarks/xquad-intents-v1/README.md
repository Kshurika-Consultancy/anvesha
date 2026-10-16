# Multilingual and intent evaluation snapshot

Task ANV-020. **756 queries, 720 real passages, three languages, six topic groups.** This extends the scientific baseline with history, geography, culture/sports/media, civics/economics/education, technology, and science/health. Of the 720 published query instances, 585 are outside the science/health group. The domain taxonomy is project metadata, not a human-reviewed classification.

The pinned [XQuAD revision](https://github.com/google-deepmind/xquad/tree/7d30520c717524000f0d9d2f9c10a069acd9d285) has 48 articles and five passages per article in each of English, Spanish and Hindi. We retain all 720 passages locally and choose the minimum original question ID in each English paragraph, then align that question across translations: 240 question groups, 720 translated query instances. The source describes professional translations of SQuAD crowdworker questions; these are not sampled production search logs.

`drafts.jsonl` adds **36 AI-authored, unjudged intent probes**, six each for navigation, ambiguity, exact constraints, historical time constraints, comparisons and multilingual requests. Draft translations/wording need native-speaker and domain review. They do not demonstrate user demand, current knowledge or representative coverage. Original query wording and constraints are preserved. No relevance grades are invented for drafts.

## Files and split

- `manifest.json`: pinned source revision/hashes, output hashes, counts and transformation method.
- `queries.jsonl`: query text, language, article group, topic, intent, split and explicit provenance.
- `answer_contexts.jsonl`: 720 derived mappings to the original answer-bearing paragraph. These are **QA context mappings**, not exhaustive retrieval relevance judgments or new human review.
- `document_ids.txt`: full collection identifiers for offline report verification.
- `topics.json`: project topic taxonomy and deterministic article split.
- `drafts.jsonl`: AI-authored intent probes with no judgments.

Twelve articles with lowest `SHA256(dataset_id + article_title)` form the holdout; the remaining 36 are development. All passages, selected queries, translations and article-associated drafts stay with their article. This prevents translation/paragraph overlap across the project split, not every possible semantic overlap between topics. The holdout is public and reserved from project tuning; it is not guaranteed unseen by pretrained models. Candidate indexing includes the full collection, as in ordinary fixed-corpus retrieval.

## Licence and attribution

**All adapted data files in this directory retain [CC-BY-SA-4.0](https://creativecommons.org/licenses/by-sa/4.0/).** The independently written engine/workflow code is Apache-2.0. This directory's licence is separate from the repository code licence; no extra downstream data restrictions are added.

XQuAD: **Mikel Artetxe, Sebastian Ruder and Dani Yogatama**, [On the Cross-lingual Transferability of Monolingual Representations](https://arxiv.org/abs/1910.11856), 2020. [Official data description and licence](https://github.com/google-deepmind/xquad).

SQuAD: **Pranav Rajpurkar, Jian Zhang, Konstantin Lopyrev and Percy Liang**, [SQuAD: 100,000+ Questions for Machine Comprehension of Text](https://aclanthology.org/D16-1264/), 2016. [Official dataset licence](https://rajpurkar.github.io/SQuAD-explorer/) is CC-BY-SA-4.0; the explorer software's MIT licence does not replace the data licence. Original article passages are attributed to **Wikipedia contributors**; translations to **XQuAD contributors**.

Changes: select aligned question instances, reformat records, derive parent-context mappings, add IDs/taxonomy/constraints/splits/hashes and separately identified AI-authored drafts. Raw passages are not bundled in Git, served by the search API, or published by preparing the benchmark. New human labels and identity mappings stay private. See [source rights](../../policies/sources/xquad_evaluation.json).

## Reproduce

```text
uv run --extra dev python -m anvesha.review_data prepare --download
uv run --extra dev python -m anvesha.intent_evaluation run
uv run --extra dev python -m anvesha.intent_evaluation verify
```

Only explicit `prepare --download` uses the network: three fixed commit-pinned files, no redirects, byte/total-time limits and SHA-256 checks. No account, paid API, LLM, model download or GPU is required. Existing source caches survive failed individual downloads. Prepared corpus and candidate pools stay in ignored `.anvesha/evaluation/xquad-intents-v1`.

See [human-review workflow](../../docs/review/README.md) and [measured retrieval/readiness report](../../reports/evaluation/xquad-intents-v1/README.md). This is a historical Wikipedia-derived sample. It does not establish live-web navigation, current freshness, source authority, multilingual parity or Google/SearXNG quality.
