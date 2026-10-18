# ADR 0008 Compact identifiers for local reranking

Status: accepted for ANV-023, 2026-10-18.

The four development queries in the initial
[v1 protocol](../../benchmarks/local-llm-pilot-v1/protocol.json) all reached the
existing 120-second deadline on the pinned CPU profile. No evaluation query was
released. These are execution failures, not evidence about relevance. Retain
the [development diagnostics](../../reports/evaluation/local-llm-development-v1/diagnostics.json).

Each original result ID contains a long hash. The actual pinned model tokenizer
needs 501 tokens for a JSON permutation of 20 such IDs and 96 for `c1` through
`c20`. This is a tokenizer measurement, not an inference speedup measurement.
Use short aliases scoped to each request, validate the exact complete permutation,
then map back to the original retrieved objects. Preserve all public result IDs,
URLs, text, source rights, scores and the untouched tail. Aliases are neither
authorization nor an anonymization claim. Query and snippets still reach the
operator's configured runtime.

Version this wire change as `candidate-rerank-v2-aliases`. The system instructions,
candidate count, input truncation, deadline and generation cap are unchanged.
The existing pipeline fingerprint includes the prompt version and therefore
changes. Upgrade API and workers together; previously accepted LLM jobs with a
different configuration fingerprint retain the documented visible lexical fallback
(`llm:configuration_changed`). Existing snapshots, feedback and explicit lexical
jobs keep their identities.

Freeze a [v2 protocol](../../benchmarks/local-llm-pilot-v2/protocol.json) before
new inference. Preserve the v1 query selection seed and every selected ID; do not
replace difficult cases. Run development first, then explicitly release evaluation
without changing code, weights, bounds or environment. Preserve both protocols and
all failures. This supersedes ADR 0007's unchanged candidate-ID wire format only;
its study limits and remaining ANV-020/ANV-023 gates still apply.
