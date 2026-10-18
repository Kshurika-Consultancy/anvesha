# Compact-alias development diagnostics

ANV-023. All four development requests returned invalid output and retained the
actual lexical fallback. **No evaluation request was released.** This is not a
relevance comparison. See [diagnostics.json](diagnostics.json) for source/model pins,
public query IDs, sanitized warnings, timings and a separate development replay's
allowlisted response structure.

That replay returned valid JSON and 19 distinct known aliases, with a normal stop,
when 20 entries were required. There were no invented IDs or reasoning content.
The production validator correctly rejected it. This motivated the optional
schema mode in [ADR 0009](../../../docs/decisions/0009-opt-in-constrained-ranking-output.md)
and separately frozen v3 protocol, preserving the original query sample. No raw
model response, prompt, abstract or private review record is published.

See the [SciFact source notice](../../../benchmarks/scifact-v1/README.md) and
[model/runtime rights manifest](../../../policies/models/qwen3-4b-instruct2507.json).
