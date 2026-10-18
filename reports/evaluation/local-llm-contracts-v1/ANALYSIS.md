# Smaller local-model contracts: what changed and what remains uncertain

ANV-024's CPU experiment observed **16/16 valid pointwise rankings**, versus
**13/16 valid listwise rankings and three exact lexical fallbacks**. The smaller
contract is usable on this profile. Its mean relevance score is higher, but
**improvement is not established** by the paired intervals. Keep pointwise opt-in;
listwise remains the existing default. No mandatory paid API or hosted inference
is introduced.

| Reserved evaluation, 16 queries | Lexical | Listwise with fallback | Pointwise with fallback |
| --- | ---: | ---: | ---: |
| nDCG@10 | 0.748850 | 0.743299 | 0.793284 |
| MRR@10 | 0.709375 | 0.718750 | 0.765625 |
| Recall@10 | 0.875000 | 0.812500 | 0.875000 |
| Recall@50 | 0.937500 | 0.937500 | 0.937500 |
| Valid / fallback / worker failure | control | 13 / 3 / 0 | 16 / 0 / 0 |
| nDCG wins / ties / losses against lexical | control | 3 / 11 / 2 | 2 / 14 / 0 |

Pointwise minus lexical nDCG@10 is **+0.044433**, 95% query-bootstrap interval
**[0.000000, +0.124450]**. The lower bound touches zero, so this does not establish
a positive effect. Pointwise minus listwise is **+0.049984**, interval
**[-0.069250, +0.203888]**. Listwise minus lexical is -0.005551, interval
[-0.175027, +0.140673]. All three listwise failures stay in these measurements.
Two queries account for pointwise's nDCG gains; tied nDCG does not mean identical
rankings. This is too small and narrow a sample for promotion or generalization.

The new structural diagnostic identifies all three listwise failures as duplicate
IDs. No raw response, reasoning or guessed repair is retained. A failed contract
publishes the complete original lexical ordering. Pointwise requires every grade,
uses lexical tie-breaking and never adds/removes a result or generates a URL.
Its observed validity coverage here is not a guarantee about other queries,
models, runtimes or relevance. Mocked hostile-snippet tests establish contract and
tool boundaries, not resistance to semantic prompt injection.

## What was frozen and measured

Source and [protocol](../../../benchmarks/local-llm-contracts-v1/protocol.json)
were committed as `1793f3a41ecb5555cf67ab0dd0f5ec4fec1ffb2b` before inference.
All nine measured source files match that commit, the checkpoint and the public
summary. Four development and 16 reserved evaluation queries were selected by
hash without labels/scores, excluding every ANV-023 pilot ID. Development finished
before explicit evaluation release; no prompt, model, budget or source change
followed its scores or the evaluation outcomes. Both profiles use the production
worker over the complete 5,183-document SciFact corpus and exactly match the
archived lexical controls. Every one of the 40 query/profile runs is retained.

The four development queries had valid output under both profiles. Pointwise
matched lexical nDCG on them; listwise's paired mean delta was -0.171134. They
remain separate from evaluation. Do not pool them or compare this population's
0.748850 lexical score with ANV-023's different 24-query population as model gain.

Actual inference used the same pinned Qwen3-4B-Instruct-2507 Q4_K_M and llama.cpp
b11669 CPU profile as ANV-023: six threads, no GPU layers, 8,192-token context,
seed 20261018, fixed verified local files, loopback/offline and no model tools.
Both contracts share a 120-second total stage deadline and the same top-20 prefix
of up to 50 retrieved candidates. Pointwise sends one candidate per request and
asks for one ordinal integer; listwise sends the whole prefix and requests a
complete permutation. Their prompts, input context, number of calls and output
bounds differ deliberately. This is a contract comparison, not an isolated
ablation or reproduction of a paper's scoring method. Profile order alternates
per query to reduce systematic order/cache bias.

## Cost, privacy and limits

Evaluation median/p95 worker elapsed time is 90.510/100.319 seconds for listwise
and 80.983/84.712 seconds for pointwise. Across development and evaluation there
were **20 listwise and 400 pointwise attempted model calls** (320 pointwise calls
in evaluation). Per-query grades share the deadline; it is not multiplied by 20.
The normal service default is 60 seconds; selecting this measured CPU profile
requires explicitly choosing its 120-second budget. Latency is descriptive, not
the quality criterion or evidence of comparative cost on other hardware.

On this shared Ryzen 5 4600G/nominal 32-GB PC, the observed main server lifetime
peak working set was 13,190,733,824 bytes, about 12.29 GiB, including development.
The evaluation resource window spans 2,931.320 wall seconds and 15,380.641 main
process CPU seconds, including indexing/bookkeeping time in the wall window.
Runtime children, the Python worker/indexer and OS costs are excluded. These are
neither total resource/energy measurements nor minimum hardware requirements.
See [execution evidence](execution.json); metadata/pins are in [summary](summary.json)
and the complete ID rankings are in [rankings](rankings.jsonl).

Four sampled main-process observations found only loopback listeners and zero
non-loopback established connections. This is not whole-tree packet capture,
a firewall test or an anonymity attestation. The owned model process tree is
stopped, its PID record is removed and port 8135 is closed. Verified artifact
caches/checkpoints remain ignored locally. No new model download was needed.

These are inherited public expert scientific annotations, **zero new human
judgments**, not private queries, operational feedback or coached reviewer work.
Public data may have appeared in pretraining; unjudged pairs count as zero,
overlapping topics weaken query independence and the intervals do not adjust
for model selection or multiple comparisons. No result establishes Google-level,
general-web, coding, IoT, asset or private-agent quality. Reranking cannot recover
missing candidates; the top-20 gold oracle is 0.875000 nDCG@10 and is diagnostic
only, never model input. Recall@50 cannot rise through this stage alone.

Next evidence belongs to ANV-020's independent domain judgments, ANV-023's actual
backend/hardware profiles and ANV-010's controlled retrieval/ranking work. Future
experiments need a fresh frozen reserve; these released scores are not an unseen
tuning set. [Method](../../../docs/LOCAL_LLM_EVALUATION.md),
[ADR 0010](../../../docs/decisions/0010-pointwise-local-ranking-experiment.md),
[data rights](../../../benchmarks/scifact-v1/README.md) and
[model/runtime rights](../../../policies/models/qwen3-4b-instruct2507.json) remain
separate from Anvesha's Apache-2.0 code licence. No weights, binaries, raw abstracts,
prompts, responses, hidden reasoning or private review records are published.
