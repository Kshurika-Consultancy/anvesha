# ADR 0014 Opt-in Wikipedia discovery and approved-source ranking

Accepted 2026-10-20, ANV-028. This is a scoped ANV-011 discovery slice; broader
corpus/evaluation/hosted gates remain open.

Existing local-model experiments do not establish relevance gains. Coverage is
also limited: a ranker cannot recover documents absent from retrieval. Add an
explicitly selected English Wikipedia article-discovery source through the fixed
`https://en.wikipedia.org/w/api.php` Action API search operation. No API key/payment
or model download is required. Keep default sources/selection local.

Request main-namespace page IDs, titles, word counts and last-edit timestamps.
Do not request/copy API article snippets or article prose: page-specific imported
attribution/fair-use and content inspection need further review under ANV-009.
Only validated positive page IDs construct fixed-host result/history URLs.
Displayed summaries are first-party descriptions of observed metadata, not article
excerpts or evidence. Preserve source identity, licence URL, modification disclosure,
observed time and metadata-only evidence through fusion, model ordering and snapshots.
Wikimedia is visibly identified; do not white-label or guarantee its API availability.
The source-rights manifest defines the precise conditional scope.

The existing tool-free model contract can rank supplied local/Wikidata/Wikipedia
candidates. It still receives only original query, title/snippet prefixes and
evidence labels, never URLs, credentials or discovery tools. Invalid/outage/drift
outputs retain visible fusion fallback; no claim of measured relevance improvement.
Existing local-only prompt/configuration identities remain unchanged. New sources
are invalid in older releases; upgrade all API/worker processes together.

Operators enable sources and supply a descriptive User-Agent with real contact.
Persist Wikipedia's identity in private native settings; legacy saved files retain
empty identity/local-only behavior. No guessed operator contact or automatic source
enabling. Clients/browser choose live sources per request, with disclosure of query/
server-address transmission. Local model inference does not make live discovery
offline or anonymous. Browser keys/selections remain in tab memory.

Reuse bounded transport protections: fixed endpoints, no redirects/proxies,
identity encoding, 1 MiB limit, 5s operation and 15s elapsed body budget, validated
JSON and sanitized failures. Add durable shared Wikimedia cooldown after 429,
503 or maxlag, honoring Retry-After, so workers/restarts do not immediately repeat
throttled requests. A paused source yields a visible partial/failed job; no hidden
retry loop. This is not the broader ANV-008 quota/rate/strict-header-deadline gate.
No arbitrary fetching, full-web coverage, cross-worker admission quota or training.

Validate rights/transport failures, malformed/hostile metadata, mixed-source
provenance and immutable feedback, restart/cancellation/expiry, saved-config
compatibility, synthetic real-process and browser flows. Default checks are offline
and model-free. Explicit live acceptance uses a small public query and real project
URL identification; archive only aggregate/status evidence, not payloads/private data.
