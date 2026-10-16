# Multilingual corpus and review readiness

Task ANV-020 (in progress).
756 queries; 720 real snapshot passages; 2268 query/system rankings.
Published QA answer-context mappings: 720. AI-authored unjudged drafts: 36.
New human assessments: **0**. No agreement or human quality score is claimed.

| Language | Published queries | Development nDCG@10 | Holdout nDCG@10 |
| --- | --- | --- | --- |
| en | 240 | 0.95235 | 0.987698 |
| es | 240 | 0.938166 | 0.979364 |
| hi | 240 | 0.78872 | 0.824585 |

Scores use the source answer-bearing paragraph as one known positive. They are not exhaustive judgments, QA answer scores or web-quality measurements. Translations share groups; no independence or confidence interval claim follows.
Article groups and all translations stay in the same split. The holdout is public and reserved from tuning, not guaranteed unseen by models. No parameters were tuned here.
Raw passages, candidate pools, credentials and assessor submissions remain local. The browser form and workflow require no paid APIs or hosted models.

[Summary](summary.json), [rankings](rankings.jsonl), [data/attribution](../../../benchmarks/xquad-intents-v1/README.md), [human workflow](../../../docs/review/README.md).
