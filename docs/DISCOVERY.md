# Optional live discovery with your own model

ANV-028 adds English Wikipedia article discovery alongside local documents and
Wikidata entity metadata. Your configured local/compatible LLM can rank candidates
from these approved sources. **Local is the only default source.** Live sources
send the original query, server address and identifying User-Agent to Wikimedia.
Local inference does not make those requests offline or anonymous.

This expands where links can be discovered. It does not establish a relevance
gain, inspect articles, answer from verified evidence or provide general-web
coverage. Wikipedia candidates contain titles/links and observed metadata;
Wikidata candidates contain entity labels/descriptions. Their evidence label is
`metadata_only`. The model sees bounded supplied text/evidence labels and can
only reorder those candidates; it receives no URL fields, client keys or tools.

## New native installation

Follow the [runtime/self-hosting setup](PRIVATE_RESEARCH.md#native-setup), install
your chosen local model separately, then use your **real operator contact URL**:

```text
uv run anvesha setup --model YOUR_INSTALLED_MODEL --sources local wikipedia --wikipedia-user-agent "AnveshaBot/0.1 (YOUR_REAL_CONTACT_URL)"
uv run anvesha show-key
uv run anvesha start
```

Replace both placeholders. The contact must be an actual HTTP(S) URL or email,
with a descriptive ASCII Anvesha client/version identifier. Do not impersonate a
browser or supply a guessed company contact. Setup requires it when Wikipedia is
enabled, saves it with the source allowlist in private configuration and refuses
overwrite. No paid API/key/account or automatic model download is required.
For no model processing, set up with `--lexical-only` and choose the explicit
lexical baseline in the browser/request. Ranking otherwise defaults to LLM.

For a fresh Docker volume, use the same options after `docker compose run --rm
setup setup`, along with the model URL/network options in the private guide.
Keep the core host port on loopback. No extra public model/source port is needed.

## Existing saved configuration

Stop all API/worker processes and make the consistent private backup described
in [upgrade guidance](PRIVATE_RESEARCH.md#browser-storage-and-upgrades). Merge
these fields into your existing private JSON; **do not replace its other fields
or credentials**:

```json
{
  "enabled_sources": ["local", "wikipedia"],
  "wikipedia_user_agent": "AnveshaBot/0.1 (YOUR_REAL_CONTACT_URL)"
}
```

Restart every API/worker using the updated code. Initialization adds a small
`provider_backoff` table; it does not rewrite old jobs, snapshots, feedback or
documents. Doctor checks the table read-only, so an older not-yet-initialized DB
reports unready until initialization. Run `anvesha doctor --config YOUR_CONFIG`
after startup. Old saved files default to empty Wikipedia identity and keep their
existing source selection; ambient environment does not override saved settings.
Configuration remains plaintext/private. Keep backups and Windows ACLs restricted.

For environment-based launches, set matching `ANVESHA_ENABLED_SOURCES` and
`ANVESHA_WIKIPEDIA_USER_AGENT` in API/worker shells. Wikidata still uses
`ANVESHA_WIKIDATA_USER_AGENT`; it has no saved contact field in this slice.
Keep local enabled for query-only clients: requests with omitted sources always
choose local, even if an operator enables only live sources.

## Choose sources per search

Connect to the bundled browser. It lists only operator-enabled sources, with
**Your collection** checked and live sources unchecked. Selecting a live source
displays the query-transmission notice. Search is disabled with no source selected;
controls are fixed during an active search. Reload/disconnect clears the key,
query/results and source choices; reconnect never silently restores a live source.
Provider identity, attribution, metadata limitations and source licence links are
visible in results. No external fonts, analytics or automatic source-page loads.

An API request can use Wikipedia alone or combine approved sources:

```json
{"query":"SQLite write ahead logging","sources":["local","wikipedia"],"ranking":"llm","limit":10}
```

Explicit `"ranking":"lexical"` uses source order/fusion without a model call.
Disabled sources reject before acceptance. A missing model rejects default LLM
requests. Existing ownership, idempotency, leases, cancellation, expiry, immutable
snapshots, pagination and feedback rules still apply. See [API](API.md).

## Coverage and rights

Wikipedia uses the fixed English Action API, main namespace only. It requests
page IDs, unmodified titles, word count and last-edit timestamps. URLs are built
only from validated positive IDs. API-provided URLs/snippets are ignored. The
summary is a labelled first-party description of metadata, offered under the
result's CC-BY-SA-4.0 context with Wikipedia contributor/Wikimedia attribution,
article attribution URL and licence link. Page-specific prose/media permissions,
imported attribution requirements and training are outside this scope. Source
terms do not relicense the Apache core or local documents. The
[rights manifest](../policies/sources/wikipedia.json) records the boundaries.

The [MediaWiki search API](https://www.mediawiki.org/wiki/API:Search) supports
article discovery. [Wikimedia reuse terms](https://foundation.wikimedia.org/wiki/Policy:Terms_of_Use)
require appropriate attribution/licensing and preserve content-specific exceptions.
The [API guidelines](https://foundation.wikimedia.org/wiki/Policy:Wikimedia_Foundation_API_Usage_Guidelines)
require throttling compliance and identification of the upstream provider; Anvesha
does not sublicense or guarantee Wikimedia's API. No new third-party source code
is copied. [Privacy policy](https://foundation.wikimedia.org/wiki/Policy:Privacy_policy)
and your model/gateway policies are separate from Anvesha's local retention.

`source_modified_at` means the API-observed last edit, **not** a publication date
or factual freshness. `observed_at` records when discovery ran. Both persist with
the appropriate provenance. A local display candidate keeps its own licence when
deduplicated with a Wikipedia candidate. Snippets/evidence are never promoted to
verified facts by model ranking. Search syntax is source-specific; local natural
language remains token OR matching, not complete Google query syntax.

## Failure and privacy limits

Each requested source gets one bounded call, with no internal retry loop.
Responses reject redirects, unexpected compression/types, malformed metadata and
oversized bodies. Default clients ignore environment proxies. Size/inactivity/body
budgets do not establish a strict total trickling-header deadline; ANV-008 retains
that gate alongside hosted quotas, admission/concurrency limits and abuse controls.

On Wikimedia 429/503/maxlag, Retry-After seconds/HTTP dates establish a durable
shared waiting period for both live sources. New workers/restarts consult it and
skip requests until eligible. In-flight calls cannot be recalled. Missing/invalid
headers use 60 seconds (maxlag 5 seconds); valid waits have a minimum one second.
Extremely large waits conservatively pause for an operationally indefinite period:
investigate upstream instructions rather than bypassing limits. There is no public
reset endpoint. Single-host cooldown is not a multi-host rate/quota guarantee.

Paused/failed sources create visible partial results when another source succeeds,
or explicit total failure. A successful empty result is different. Model outage,
invalid output or configuration drift preserves the existing visible fusion
fallback; it never changes providers or adds model-created links. No automatic
training or learning from a vote. Operational data follows existing retention;
upstream/model/browser copies and backups have separate controls.

Default tests and `scripts/smoke_discovery.py` use synthetic data, injected discovery
transport and a loopback model protocol fixture. They prove workflow/contract
behavior, not relevance or actual-model quality. The private human-review pilot is
not used. See [ADR 0014](decisions/0014-opt-in-wikipedia-discovery.md) and
[verification](tracking/verification/2026-10-20-discovery.md).
