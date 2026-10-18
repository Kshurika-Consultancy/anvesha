# Local ranking contracts: listwise versus pointwise

ANV-024. Public SciFact expert labels; zero new human judgments. CPU-only local inference.

| Split | Contract | Queries | Lexical nDCG@10 | Model nDCG@10 | Applied / fallback / failed |
| --- | --- | ---: | ---: | ---: | --- |
| development | listwise | 4 | 0.750000 | 0.578866 | 4 / 0 / 0 |
| evaluation | listwise | 16 | 0.748850 | 0.743299 | 13 / 3 / 0 |
| development | pointwise | 4 | 0.750000 | 0.750000 | 4 / 0 / 0 |
| evaluation | pointwise | 16 | 0.748850 | 0.793284 | 16 / 0 / 0 |

Evaluation paired pointwise minus listwise nDCG@10: +0.049984, 95% query-bootstrap interval [-0.069250, +0.203888].

All failures retain lexical fallback and remain in the comparison. Reliability is not relevance or truth. This small scientific sample does not establish general-web, coding, IoT, asset or agent quality. Public data may have appeared in pretraining; unjudged pairs count as zero and query intervals do not correct topic dependence. No automatic default promotion follows. See summary.json and rankings.jsonl for paired metrics, calls, deadlines, sanitized failures and provenance.

[Method](../../../docs/LOCAL_LLM_EVALUATION.md); [data rights](../../../benchmarks/scifact-v1/README.md); [model/runtime rights](../../../policies/models/qwen3-4b-instruct2507.json). No raw text, model outputs/reasoning, private queries, weights or binaries are bundled.
