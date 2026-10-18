# What this pilot establishes

ANV-023. Actual Qwen3-4B-Instruct-2507 Q4_K_M CPU inference with llama.cpp, using
the production worker and complete 5,183-document SciFact corpus. All four
development and 24 reserved evaluation queries are accounted for. The code and
protocol were committed as `9905423` before evaluation release; all eight measured
source files match that commit. No model/parameter/protocol changes used evaluation
outcomes. See [metrics](summary.json), [ID rankings](rankings.jsonl),
[execution/resources](execution.json) and [method](../../../docs/LOCAL_LLM_EVALUATION.md).

| Evaluation metric | Lexical control | LLM with actual fallback |
| --- | ---: | ---: |
| nDCG@10 | 0.616925 | 0.674710 |
| MRR@10 | 0.625000 | 0.675000 |
| Recall@10 | 0.666667 | 0.750000 |
| Recall@50 | 0.812500 | 0.812500 |

The primary paired nDCG@10 difference is **+0.057786**, with a query-bootstrap
95% interval **[-0.030015, +0.157238]**. The interval includes zero: improvement is
**not established** by this sample. There are three nDCG wins, one regression and
20 ties. Tied nDCG does not imply identical full rankings. The selected subset's
baseline differs from the archived 300-query baseline because it is a smaller
fixed sample; do not compare those different populations as a model gain.

The model applied valid permutations on **19/24** evaluation queries. Five
invalid responses retained the exact lexical rankings (`completed_partial`);
there were zero worker failures. All 24 outcomes remain in the comparison. The
development split had three applied rankings and one invalid-output fallback.
Earlier [v1](../local-llm-development-v1/README.md) and
[v2](../local-llm-development-v2/README.md) failures are preserved separately;
neither released evaluation queries. Schema mode improves output constraints but
does not replace validation or establish relevance gains by itself.

Evaluation median/p95 elapsed time is 95.330/107.900 seconds for the LLM path and
0.205/0.477 seconds for lexical. Quality, rather than speed, is the decision
criterion; latency/resource measurements describe the cost of this profile.
The shared PC has a Ryzen 5 4600G, six physical cores and nominal 32 GB RAM
(33,684,578,304 usable bytes reported), with no GPU layers.
The main model-server process reached about **11.40 GiB** peak working
set across its lifetime, including development. That is an observation, not a
minimum-RAM or energy estimate. The server/preview are stopped; the ignored
2.497-GB GGUF and runtime cache remain local for reproduction.

The post-hoc gold-label oracle within the same top-20 prefix scores 0.775548
nDCG@10. This is a diagnostic ceiling, never model input or a deployable ranker.
Reranking cannot recover missing candidates, and cannot raise recall@50. There
is both ranking headroom and a retrieval-coverage limit in this sample.

The next tracked step is ANV-024: improve small-model contract reliability and
compare bounded per-candidate classification/ranking alternatives using development
data, then a **fresh frozen evaluation**. Broader approved sources/hybrid retrieval
remain ANV-009/ANV-010/ANV-011. ANV-020 must supply independent, non-coached domain
review; actual Ollama/OmniRoute and other hardware/model checks remain ANV-023.
Do not use these released evaluation scores for tuning and call a repeat unseen.

These are inherited public expert annotations, with **zero new Anvesha human
judgments**. Scientific relevance is not factual verification or evidence for
coding, IoT, assets, private chat, Google-level or general-web quality. Incomplete
judgments, possible training exposure, shared topics and this small sample limit
interpretation. Raw abstracts, prompts, responses, reasoning, private queries and
reviewer data are absent. Source/model/runtime licences retain their own terms;
see the [SciFact notice](../../../benchmarks/scifact-v1/README.md) and
[model manifest](../../../policies/models/qwen3-4b-instruct2507.json).
