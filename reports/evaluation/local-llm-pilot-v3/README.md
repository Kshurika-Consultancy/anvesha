# Local LLM pilot: Qwen3-4B versus lexical search

ANV-023. Public SciFact expert labels; zero new Anvesha human judgments.

| Split | Queries | Lexical nDCG@10 | LLM nDCG@10 | Paired delta (95% CI) | Applied / fallback / failed |
| --- | ---: | ---: | ---: | --- | --- |
| development | 4 | 0.695287 | 0.777405 | +0.082118 [+0.000000, +0.246355] | 3 / 1 / 0 |
| evaluation | 24 | 0.616925 | 0.674710 | +0.057786 [-0.030015, +0.157238] | 19 / 5 / 0 |

Evaluation conclusion: interval includes zero; improvement not established.

This fixed small sample is not a release gate, a general-web comparison, or evidence for coding/IoT/asset/private-agent query quality. Public data may have appeared in model training. Unjudged pairs count as zero. Query bootstrap intervals do not correct for shared topics or model-selection uncertainty.

Only the original candidate prefix is reordered; the corpus and recall ceiling do not expand. Failure fallback remains in the paired measurements. See summary.json and rankings.jsonl for IDs, latency, warnings, provenance and bounds.

Source attribution and reuse conditions: [SciFact dataset notice](../../../benchmarks/scifact-v1/README.md) and [model/runtime rights manifest](../../../policies/models/qwen3-4b-instruct2507.json). Model weights, runtime binaries and raw text are not bundled.
