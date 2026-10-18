# ADR 0009 Opt-in schema-constrained ranking output

Status: accepted for ANV-023, 2026-10-18.

The [v2 development diagnostics](../../reports/evaluation/local-llm-development-v2/diagnostics.json)
retain four invalid-output fallbacks and zero evaluation calls. One additional
bounded replay of the first development query returned a stopped JSON object
with 19 distinct known IDs instead of the required 20. Only allowlisted structural
counts and token usage were recorded; no prompts, responses or reasoning were
persisted. This identifies an output-contract failure, not a relevance judgment.

Add the operator setting `ANVESHA_LLM_OUTPUT_FORMAT=json_schema`. It requests a
single `ranked_ids` array, exactly the candidate count, using only the per-request
aliases, with no extra properties. Keep `json_object` as the compatibility default
for existing deployments. Saved private configuration retains the chosen format;
older files without the field retain object mode. Include the format in the
accepted configuration fingerprint. No public search request can change it.

Schema support depends on the runtime/backend. Client-side complete-permutation,
uniqueness, finish-state and tool-call checks still apply even if a backend ignores
the schema. Unsupported formats, duplicate IDs and truncated outputs retain the
visible lexical fallback. Do not silently downgrade the format, retry against a
different provider or send data to a hosted service.

Freeze [protocol v3](../../benchmarks/local-llm-pilot-v3/protocol.json) before new
inference. It selects schema mode and preserves every v1/v2 query ID, weights,
prompt, prefix/deadline/context bounds and hardware. Run development first, then
release evaluation without tuning on its outcomes. Keep earlier failures and
protocols available; they are not omitted evaluation observations. This is a
development-led protocol revision, not a post-hoc selection by evaluation gain.

The pinned llama.cpp [server documentation](https://github.com/ggml-org/llama.cpp/blob/620d2225cc436ab0b001e3200e590e3b286ef9ab/tools/server/README.md)
and [request parser](https://github.com/ggml-org/llama.cpp/blob/620d2225cc436ab0b001e3200e590e3b286ef9ab/tools/server/server-common.cpp)
support the nested `response_format.json_schema.schema` request used here.
This API feature does not itself establish better rankings, provider compatibility
or a model's factual reliability. Actual Ollama/OmniRoute checks remain open.
