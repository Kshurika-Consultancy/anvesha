# ADR 0005 Private research preview and optional model processing

Status: accepted for ANV-021, 2026-10-18.

The later user-directed LLM default and browser/self-hosting path are recorded in
[ADR 0006](0006-llm-default-and-self-hosted-browser.md). Its new default supersedes
this ADR's lexical-default decision; the bounded model contract still applies.

## Why this step

The user prioritizes open-source adoption, private home-server research and local
models, with optional OmniRoute compatibility. The current engine proves durable
search jobs but defaults to three demo documents. More benchmark administration
alone does not provide a useful first research experience. An LLM also cannot
recover documents that retrieval never found.

Deliver a narrow, usable private-corpus preview: documented import and native
self-hosting, read-only diagnostics, authenticated capability discovery and
explicitly requested candidate reranking. Keep the original lexical path. The
container/client path is ANV-022; actual backend/model quality is ANV-023. General
web discovery, safe extraction and the full hybrid/planning gate remain ANV-009,
ANV-010 and ANV-011. This scoped experiment does not declare M2 or M3 complete.

## Model boundary

Use an independently implemented HTTP chat-completion client. Ollama and OmniRoute
document `/v1/chat/completions`; neither their code nor any model weights are
bundled. Existing Apache-2.0 core licensing is unchanged. OmniRoute's reviewed
repository licence is MIT; backend models, provider terms and corpus rights remain
separate. A gateway or free account does not grant processing or training rights.

LLM configuration is absent by default. Each search additionally requests
`ranking: "llm"`; lexical remains the default even on a configured instance. The
preview accepts LLM processing only for the local source. API and worker must
agree on the model, endpoint, prompt and bounds. Store the resulting configuration
fingerprint in the accepted job's pipeline version, without credentials. Preserve
old job hashes, snapshots and feedback through an additive SQLite migration.

Send only the original query and bounded candidate IDs, titles, snippets and
evidence labels to the fixed operator-configured endpoint. The model receives no
result URLs, privileged tools, API-client credentials or full corpus. Its only
accepted output is a permutation of every supplied ID. Retain retrieved content,
rights, provenance and lexical scores; expose changed ordering separately. Prompt
injection can still harm ordering, so output confinement is not a relevance proof.

The HTTP operation has a total async deadline including response headers, a body
size limit, no redirects, no inherited environment proxies, no client retries and
periodic lease/cancellation checks. Fewer than two candidates need no call. Invalid
output, model outage or changed configuration produces lexical fallback with a
visible warning. A lost lease/cancelled/deleted job cannot publish. At-least-once
worker recovery can repeat an external call; already transmitted data cannot be
recalled. Upgrade all API/worker processes before enabling the new request mode.

## Privacy claims

Loopback transport is the default and non-loopback endpoints require explicit
operator opt-in. A local endpoint is not proof of local inference: OmniRoute or
another proxy can forward to external models. Anvesha does not audit that routing
or promise anonymous/untracked web access. Each upstream can observe the data it
receives. Local storage retains operational queries until deletion; backups,
retention and document-level access controls remain documented limits.

Do not auto-install a gateway, pull a model, contact people, import coached review
labels, retrain, publish or deploy as a side effect. Wire-contract fixtures are
synthetic implementation checks, not measured quality or live backend acceptance.

## Reviewed primary sources

- [Ollama compatibility documentation](https://docs.ollama.com/api/openai-compatibility)
  documents the local `/v1` chat endpoint and JSON response-format support.
- [OmniRoute README](https://github.com/diegosouzapw/OmniRoute) documents the
  `localhost:20128/v1` endpoint, gateway key and provider-dependent routing.
- [OmniRoute licence](https://github.com/diegosouzapw/OmniRoute/blob/main/LICENSE)
  is MIT as reviewed on 2026-10-18. This is not a review of every provider/model.

See [the private research guide](../PRIVATE_RESEARCH.md) and the authoritative
[task ledger](../tracking/tasks.json) for the implementation and remaining gates.
