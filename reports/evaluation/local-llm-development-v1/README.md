# Original local-model development diagnostics

ANV-023. All four development requests hit the 120-second LLM deadline and
published the actual lexical fallback. **No evaluation request was released.**
This is not a quality comparison. The model/runtime pins, source hashes, original
protocol fingerprint, query IDs, sanitized warnings and timings are retained in
[diagnostics.json](diagnostics.json).

A tokenizer-only check of a 20-candidate output found 501 tokens for the original
hash IDs and 96 for short aliases. This motivated [ADR 0008](../../../docs/decisions/0008-compact-reranking-identifiers.md)
and the separately frozen v2 protocol, which preserves the same query sample.
No prompts, model responses, abstracts or private review records are published.
The development failures are retained rather than silently replaced by successful
runs. See the [SciFact source notice](../../../benchmarks/scifact-v1/README.md)
and [model/runtime rights manifest](../../../policies/models/qwen3-4b-instruct2507.json).
