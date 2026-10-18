# Private research with Anvesha

ANV-021 builds toward a private research search service for home-server users,
developers and small research teams. Start with documents you can legally process
and share within your instance. Local lexical search needs no model, paid API,
GPU or hosted account. Optional model reranking uses the same asynchronous API.

The useful first outcome is: import real research material, submit a question,
wait for its durable job and inspect stable results with original source rights.
This preview searches an operator-supplied corpus. It is not a full-web index or
evidence of Google-level search quality. Reranking is experimental until measured
against independent labels under ANV-023.

## Native setup

Use Python 3.12+ with SQLite FTS5 and uv. From the repository:

```text
uv sync --locked
uv run anvesha init
```

Save the generated API key privately. `init` does not save it. Import a reviewed
JSON list containing `id`, `url`, `title`, `content`, `license` and `attribution`:

```text
uv run anvesha ingest /path/to/permitted-documents.json --rights-reviewed
```

Use an actual path on your system; [the example file](../examples/documents.json)
shows the format with synthetic content. URLs identify records and are never
fetched. All API clients of the instance share this document corpus; their job
history is owner-isolated. Per-user private document libraries are future work.

Set the API key, then check readiness and start the API. PowerShell:

```powershell
$env:ANVESHA_API_KEYS = 'your-generated-key'
uv run anvesha doctor
uv run anvesha serve
```

Bash:

```bash
export ANVESHA_API_KEYS='your-generated-key'
uv run anvesha doctor
uv run anvesha serve
```

`doctor` reports FTS5, initialized database, document count and whether optional
model configuration exists. It makes no network requests, prints no credentials,
does not create a database and returns exit code 1 when setup is incomplete. It
does not prove that an API, worker, model or gateway is reachable.

In a second terminal with the same database and model configuration:

```text
uv run python -m anvesha.worker
```

Both processes must remain running. They share a SQLite file on local disk.
Keep the API on its default loopback address. Remote/public exposure needs the
authentication, transport and hosted-hardening review described in
[SECURITY.md](../SECURITY.md). Container deployment and an accessible browser
client are tracked under ANV-022; no tested Docker support is claimed here.

## Optional local LLM: Ollama

Install/configure your preferred model runtime separately and review the exact
model's licence and hardware needs. For Ollama, choose an already installed local
model (`ollama list`). Anvesha never automatically downloads or starts a model.
Set these in both API and worker terminals, then restart both processes:

```powershell
$env:ANVESHA_LLM_BASE_URL = 'http://127.0.0.1:11434/v1'
$env:ANVESHA_LLM_MODEL = 'your-installed-model-name'
```

```bash
export ANVESHA_LLM_BASE_URL='http://127.0.0.1:11434/v1'
export ANVESHA_LLM_MODEL='your-installed-model-name'
```

No LLM API key is required by Anvesha for an unauthenticated local endpoint.
For a separately authenticated runtime, set `ANVESHA_LLM_API_KEY` privately.
An endpoint must support non-streaming chat completions with JSON-object output.
[Ollama's documentation](https://docs.ollama.com/api/openai-compatibility)
describes that wire contract. Actual installed-model behavior still needs testing.

An endpoint on another machine/container requires
`ANVESHA_LLM_ALLOW_NETWORK=true`. Use HTTPS for named/public endpoints. Explicitly
approved private LAN IPs and the container names `ollama`, `omniroute` and
`host.docker.internal` also permit HTTP. This is trusted operator configuration,
not a browser-controlled URL or a general-purpose web fetcher.

## Optional gateway: OmniRoute

Run and configure OmniRoute separately. Its
[documented endpoint](https://github.com/diegosouzapw/OmniRoute) is
`http://127.0.0.1:20128/v1`. Point `ANVESHA_LLM_BASE_URL` there, set the gateway key
in `ANVESHA_LLM_API_KEY` and set `ANVESHA_LLM_MODEL` to an explicit configured
route/model identifier. Review the gateway and downstream model/provider terms.
No gateway account, paid route or cloud provider is mandatory for Anvesha.

**A gateway running locally can still send your query and snippets to the cloud.**
Use a verified local-only route with external fallbacks disabled for private
inference. Do not infer local inference from a routing label such as `auto` or
`auto/offline`; inspect the actual configured destination. Anvesha does not inspect
OmniRoute's internals, guarantee its provider eligibility, or verify its egress.

The integration is an independently written HTTP client, with no bundled or copied
OmniRoute code. Its [MIT licence](https://github.com/diegosouzapw/OmniRoute/blob/main/LICENSE)
is separate from Anvesha's Apache-2.0 code and from model/data licences.

## Request intelligent reranking

Existing requests stay lexical. To request the optional stage, submit:

```json
{"query":"your research question","sources":["local"],"limit":10,"ranking":"llm"}
```

Use `X-API-Key`, poll the returned search ID and retrieve its snapshot as shown in
[the API guide](API.md). `GET /v1/capabilities` is authenticated and reports available
ranking modes without exposing model credentials or endpoint addresses. LLM mode
is accepted only when configured and only with the local source. Missing model
configuration returns 422 before accepting a job. Enabling a model never silently
opts existing/default requests into processing.

The worker first retrieves with BM25/RRF, then sends at most 20 candidate IDs,
titles (240 characters each), snippets (1,200 characters each), evidence labels
and the original query to the configured model. It supplies no result URLs,
client API keys, full corpus or tools. The model can only reorder the supplied
IDs. It cannot add a result or modify source text/rights. A ranker cannot discover
a missing document, and a short snippet can miss relevant evidence.

The bounded candidate prefix is reranked before the requested result limit is
applied; any remaining candidates keep lexical order. Successful reordered results
include `ranking_method` and `lexical_rank`. `score` remains the original RRF score,
so it need not decrease with final rank and is never a truth probability. Fewer
than two retrieved candidates require no model call.

The accepted job's pipeline version fingerprints the endpoint/model identifier,
prompt and bounds, not a verified model-weight or resolved gateway-route digest.
All processes must use matching settings. If settings change or the model fails,
the worker publishes lexical results as `completed_partial` with a sanitized
`llm:*` warning. Model requests have no application retries and a total deadline
(default 60 seconds, maximum 120); worker recovery can still repeat a call.
Cancellation stops waiting and prevents publication, but cannot recall content
already sent to a model. Snapshots and feedback remain stable and version-bound.

## Data flow and privacy

| Configuration/use | Data transmitted by Anvesha |
| --- | --- |
| Local source, lexical ranking | No outbound source/model request |
| Local source, explicit LLM ranking | Original query and bounded candidate text to the configured endpoint |
| OmniRoute or another proxy | Same payload to the gateway; further routing depends on its configuration |
| Explicit Wikidata source | Query to Wikimedia; this preview uses lexical ranking for that source |

There is no built-in analytics or automatic feedback training. Queries, results
and feedback remain operational data in the unencrypted local database until
deleted. Filesystem administrators, backups, model-server logs and selected
upstreams are separate trust boundaries. Automatic expiry and backup deletion
remain ANV-008. Access logging is disabled by the `anvesha serve` command; reverse
proxies and other launch commands may log independently. FastAPI's existing
interactive `/docs` and `/redoc` pages use CDN assets; avoid them for a browser
session requiring zero external asset requests and use the API directly.

Review rights before sending document excerpts to any model, especially external
services. Anvesha does not train a model, but cannot control downstream retention
or training. See the [model processing policy](../policies/llm-processing.json).
This is a private deployment option, not a promise of anonymous or untracked web
search. No new human-review labels are created by this feature; the three coached
pilot items remain practice only under ANV-020.

## Adoption sequence and evidence gates

The [ledger](tracking/tasks.json) owns statuses and acceptance criteria:

1. ANV-021: usable native private-corpus setup, opt-in model protocol and safe fallback.
2. ANV-022: tested container installation, accessible client and documented upgrades.
3. ANV-023: actual backend acceptance, pinned model/hardware and independent quality comparisons.
4. ANV-009/ANV-011: rights-reviewed research sources and safe acquisition to close coverage gaps.
5. ANV-010: add constrained query planning, hybrid retrieval and further reranking only when evidence supports them.

The existing scientific and multilingual lexical reports remain reference
baselines. Synthetic protocol tests do not demonstrate a model quality improvement.
