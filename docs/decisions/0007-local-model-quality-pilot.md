# ADR 0007 Private tooling purpose and a real local-model pilot

Status: accepted for the ANV-023 initial slice, 2026-10-18.

Anvesha exists for people who want control over their data and internal tooling.
Its title is **Private Search for Your Own AI Tools**. The open-source engine can
be a building block for research, coding/development, personal IoT and asset tools,
or private AI agents/chat. Those are intended integrations; the current engine
searches imported documents and does not implement those applications or actions.
Keep paid providers and hosted inference optional, and disclose all external data
flows. Local ownership is the goal, not a blanket anonymity guarantee.

ANV-023 begins with real CPU inference using the exact artifacts in the
[model/runtime rights manifest](../../policies/models/qwen3-4b-instruct2507.json):
llama.cpp b11669 and Qwen3-4B-Instruct-2507 Q4_K_M. Acquisition is explicit, bounded
and checksum-verified; neither weights nor binaries enter Git/distributions.
The portable runtime reads a fixed local GGUF, binds loopback, disables web UI,
MCP proxy and prompt logs, uses offline mode and six CPU threads. No administrator,
account, hosted API or system installation is needed. Model/registry downloads
are observable network activity and are separate from local inference.

Freeze 4 development and 24 evaluation SciFact query IDs by hash before inference.
Use the complete reviewed corpus and the actual production worker for both paths.
Compare lexical limit-50 with the same candidates plus the existing bounded
top-20 reranker. The prompt, input truncation, 1,536-token generation cap and
candidate-ID validation remain unchanged. A 120-second per-call limit is the
existing supported maximum, chosen for this CPU pilot; it is not the API's
60-second default. Context is 8,192 tokens and the seed is fixed. No parameter or
prompt is selected from evaluation outcomes.

Development saves a private checkpoint. Explicit release/resume is required
before evaluation. Keep failures/fallbacks in paired scores; a timed-out model
does not disappear from the denominator. Publish ID rankings, aggregate metrics,
paired query-bootstrap intervals, failure counts, latency, source/model hashes and
hardware, with no raw prompts, responses, abstracts or private operational data.
An offline verifier recomputes scores, checks complete query coverage, candidate
membership/unchanged tail, frozen lexical control and artifact consistency. It
does not independently prove a model was run; runtime execution evidence remains
separately documented.

This is a small scientific pilot using inherited expert labels. It is not new
Anvesha human assessment, a Google/SearXNG comparison or evidence for the intended
coding/IoT/asset/agent domains. Public queries may have appeared in pretraining;
query bootstrap assumptions and incomplete judgments limit interpretation. The
independent ANV-020 study, actual Ollama/OmniRoute checks, further model/hardware
profiles and broader domain coverage remain open. Use observed failure categories
to plan improvements; never tune on the reserved evaluation outcomes.

Primary sources reviewed:

- [Pinned llama.cpp release](https://github.com/ggml-org/llama.cpp/releases/tag/b11669)
  and [MIT licence](https://github.com/ggml-org/llama.cpp/blob/620d2225cc436ab0b001e3200e590e3b286ef9ab/LICENSE).
- [Official model registry entry](https://ollama.com/library/qwen3:4b-instruct-2507-q4_K_M)
  and [Qwen licence](https://huggingface.co/Qwen/Qwen3-4B-Instruct-2507/blob/main/LICENSE).
- Existing [SciFact rights review](../../policies/sources/beir_scifact_evaluation.json)
  governs the public scientific text/annotations; no new discovery connector is added.
