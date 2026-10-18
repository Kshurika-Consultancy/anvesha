# ADR 0010 Bounded pointwise relevance as an opt-in experiment

Status: accepted for ANV-024's comparison slice, 2026-10-18.

The first CPU pilot retained five unusable permutations among 24 evaluation
queries; relevance improvement was not established. Development had already
identified complete-permutation generation as a reliability problem. Before
adding models, sources or agent loops, isolate this contract problem and measure
whether a smaller contract also preserves useful rankings.

Add operator-only `ANVESHA_LLM_STRATEGY=pointwise`. Each original prefix candidate
receives one tool-free request for an ordinal grade 0–3. Stable descending sorting
retains lexical ties. Grades stay internal: they are neither truth probabilities
nor replacements for lexical scores, evidence status or source rights. No IDs or
URLs are requested from the model. Result membership, identities, content,
provenance, untouched tail, immutable snapshots and versioned feedback stay stable.

Require every grade. One invalid/truncated response, unsupported format, timeout
or transport failure discards all tentative grades and publishes exact lexical
fallback with a visible warning. At most 20 sequential calls share one total
deadline (default 60s, maximum 120s). Heartbeats cover the stage, with cancellation
checks before each dispatch. No format/provider downgrade, automatic retry,
parallel fan-out or hosted inference is introduced. This can cost more calls and
lose listwise comparative context.

Existing configurations/jobs stay listwise. Setup saves the optional strategy;
missing fields retain listwise, whose previous fingerprint stays unchanged.
Pointwise identity includes strategy/prompt/output bounds. API and worker must
agree or publish `llm:configuration_changed` fallback. Keep client `ranking=llm`
and result marker `llm_rerank`; the pipeline identifies the configured strategy.

Keep `llm:invalid_response` and add one closed-vocabulary `llm_contract:` diagnostic
for malformed JSON, invalid envelopes, truncation, extra fields, invalid/unknown/
duplicate/missing IDs or invalid grades. Never retain raw outputs, reasoning or
exception bodies. Mocked hostile-snippet tests establish contract/tool boundaries,
not immunity to semantic prompt injection.

The [frozen protocol](../../benchmarks/local-llm-contracts-v1/protocol.json) selects
four development and 16 evaluation queries by hash without labels/scores, excluding
every ANV-023 pilot ID. Both contracts use the same Qwen weights, llama.cpp runtime,
CPU settings, top-20 prefix and 120-second total deadline. Alternate profile order
per query. Pointwise's 32-token versus listwise's 1,536-token bound is part of this
contract comparison, not an isolated prompt ablation. Freeze source/protocol before
inference and explicitly release evaluation after unchanged development.

Checkpoints reject source/environment/model drift and retain every fallback and
failure. Compare both profiles with exact archived lexical rankings and each
other, reporting paired nDCG intervals, valid coverage, latency, calls and failure
categories. This small scientific reliability pilot is not a default-promotion
gate or independent personal-tooling evidence. Public data may be in pretraining;
topic dependence and incomplete judgments limit interpretation. Existing human
review workspaces are untouched; no automatic learning is introduced.

The hypothesis is informed by [fine-grained pointwise relevance research](https://research.google/pubs/beyond-yes-and-no-improving-zero-shot-pointwise-llm-rankers-via-scoring-fine-grained-relevance-labels/)
and the [comparative setwise study](https://arxiv.org/abs/2310.09497v2), reviewed
2026-10-18. These papers support comparing alternatives, not this Qwen profile's
effectiveness. This independently written hard-ordinal chat implementation does
not reproduce their scoring APIs/weights/code. No dependency or licence is added.
