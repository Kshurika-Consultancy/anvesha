# Private research with Anvesha

Anvesha is **Private Search for Your Own AI Tools**: an open-source building block
for people running their own research, coding/development and personal tools.
IoT/asset operations and private agents/chat can use its search API; those
applications and control actions are not implemented by this preview. You choose
the corpus, model location and clients, without a mandatory hosted service that
collects search usage. Model/provider settings and local storage/backups remain
separate trust boundaries.

**LLM ranking is the default for new API and browser searches.** Use your own local
model; no paid API or hosted account is required. The explicit lexical baseline
works without a model. Anvesha never downloads model weights automatically.

This preview searches an imported collection. General-web discovery, query
planning, page inspection and embeddings remain future work. Reranking is
experimental: the first scientific CPU pilot has a higher mean score but does
not establish improvement; see [results](../reports/evaluation/local-llm-pilot-v3/ANALYSIS.md). A ranker
cannot recover a missing document or establish that a statement is true.

ANV-023 introduces compact per-request candidate aliases for inference. Original
public result IDs and feedback snapshots remain stable. Upgrade the API and
workers together: the new prompt/wire version changes the configuration
fingerprint, so accepted older LLM jobs can fall back visibly with
`llm:configuration_changed`. See [ADR 0008](decisions/0008-compact-reranking-identifiers.md).

## Native setup

Install Python 3.12+ with SQLite FTS5 and [uv](https://docs.astral.sh/uv/getting-started/installation/).
Install your model runtime separately, review the model licence/hardware needs,
and choose an already installed local model (`ollama list` for Ollama). From the repo:

```text
uv sync --locked
uv run anvesha setup --model YOUR_INSTALLED_MODEL --seed-demo
uv run anvesha show-key
uv run anvesha start
```

Replace the model identifier. The default endpoint is `http://127.0.0.1:11434/v1`.
A fresh package install needs download access; subsequent local search needs no
external service. Setup saves a generated key and matching API/worker settings in
ignored `.anvesha/server.json`, initializes `.anvesha/anvesha.db`, and refuses to
overwrite credentials. `--seed-demo` explicitly loads three synthetic records;
omit it for an empty collection. Keep `show-key` output private.

Open [Anvesha](http://127.0.0.1:8000/), enter the client key, and search. `start`
supervises separate API and durable worker processes; Ctrl+C stops both. A child
exit shuts down its sibling and returns nonzero. Restarting preserves jobs and
snapshots. The browser covers polling, cancellation, stable pagination, sources
and Useful/Not useful feedback. Feedback stays out of learning.

For a model-free installation, use `uv run anvesha setup --lexical-only --seed-demo`
instead, then choose **Lexical baseline** in the browser or send
`"ranking":"lexical"`. Default LLM submission returns 422 without a configured
model; it does not silently skip the model.

Custom paths use `anvesha --db /absolute/path/collection.db setup --config
/absolute/path/server.json --model YOUR_MODEL`. Pass the same `--config` to
`show-key`, `start`, `doctor`, `run-api`, `run-worker` and `ingest`.
`ANVESHA_CONFIG_PATH` selects the default file for setup/service commands; doctor
and ingest use a file only when `--config` is supplied. Saved service settings
take precedence over environment variables. Edit the private JSON locally and
restart both services to change models, keys or timeouts.

Configuration is plaintext and can include the model key. Creation requests mode
0600 on POSIX; on Windows restrict the parent directory's inherited ACLs. Never
commit or upload it. `show-key` explicitly displays the client key locally.

## Import your permitted documents

Prepare a JSON list of `id`, `url`, `title`, `content`, `license`, `attribution`.
[The example](../examples/documents.json) is synthetic. Use actual paths:

```text
uv run anvesha ingest /absolute/path/permitted-documents.json --config .anvesha/server.json --rights-reviewed
uv run anvesha doctor --config .anvesha/server.json
```

Ingestion never fetches the URLs. Review indexing, retention, display and model
processing rights; a licence string is not blanket permission. All clients share
the imported corpus; job history and feedback are owner-isolated. Per-user private
libraries remain future work. Doctor checks configuration, FTS5, database and
document count offline without printing keys or creating a database. It does not
prove API/worker/model reachability or quality.

## Docker Compose

Use Docker Engine/Desktop with Compose v2 on one host and local disk. The core
image runs as UID/GID 10001, with locked runtime dependencies and packaged browser
assets. The build context excludes private workspaces and credentials. Separate
API/worker containers share a persistent volume, with read-only root filesystems,
dropped capabilities and a host-loopback API port. Image digests are pinned.
A fresh build needs image/package downloads.

For a model runtime already accepting private Docker-network connections on the host:

```text
docker compose build
docker compose run --rm setup setup --model YOUR_INSTALLED_MODEL --model-url http://host.docker.internal:11434/v1 --allow-model-network --seed-demo
docker compose run --rm setup show-key
docker compose up -d api worker
```

A host runtime bound only to loopback may not accept Docker connections. Configure
its intended private interface/firewall yourself; Anvesha does not change these.
Use HTTPS for remote named/public endpoints. Do not expose an unauthenticated model port.

Alternatively, start the optional CPU Ollama service and explicitly install a
chosen model before setup:

```text
docker compose --profile local-model up -d ollama
docker compose exec ollama ollama pull YOUR_CHOSEN_MODEL
docker compose exec ollama ollama list
docker compose run --rm setup setup --model YOUR_CHOSEN_MODEL --model-url http://ollama:11434/v1 --allow-model-network --seed-demo
docker compose run --rm setup show-key
docker compose up -d api worker
```

Choose one setup path; existing configuration is never overwritten by setup.
The explicit pull downloads weights under the model's own licence; no automatic
model download occurs. The optional runtime publishes no host model port. GPU
configuration is an operator-specific addition; the API needs no GPU.
[Ollama documents its Docker options](https://docs.ollama.com/docker).

For a model-free container preview use `docker compose run --rm setup setup
--lexical-only --seed-demo`, then start API/worker and explicitly select lexical.
Open `http://127.0.0.1:8000/`; `ANVESHA_PORT` changes the host port. Keep SQLite on
local disk. Network filesystems/multi-host workers are unsupported.

Import by mounting your reviewed file read-only; on Linux, for example:

```text
docker compose run --rm -v /absolute/path/documents.json:/import/documents.json:ro setup ingest /import/documents.json --config /data/server.json --rights-reviewed
docker compose run --rm setup doctor --config /data/server.json
docker compose logs --tail 50 api worker
docker compose stop api worker
docker compose up -d api worker
```

`docker compose down` preserves volumes. `down --volumes` deletes the collection,
operational records and saved keys; it is not a restart. Keep the Compose project
name stable so an existing volume is selected.

Container CI exercises a real build, non-root runtime, private-network synthetic
chat endpoint, default LLM execution, feedback, queued-job/API restart, stable
snapshots, fallback and cleanup. It does not prove actual Ollama/OmniRoute or model
quality. See [verification](tracking/verification/2026-10-18-self-hosting.md) for the
observed run and outstanding acceptance work.

## Model runtime and OmniRoute

The endpoint must support non-streaming `/v1/chat/completions`, JSON-object output
and an assistant message. [Ollama documents the interface](https://docs.ollama.com/api/openai-compatibility).
No key is required for an unauthenticated local runtime. Set `ANVESHA_LLM_API_KEY`
privately before setup for an authenticated endpoint; setup saves it in the
private file. Avoid secrets in command arguments or endpoint URLs.

For a runtime that supports schema-constrained output, set
`ANVESHA_LLM_OUTPUT_FORMAT=json_schema` before setup. In PowerShell, use
`$env:ANVESHA_LLM_OUTPUT_FORMAT = 'json_schema'`; in a POSIX shell, use
`export ANVESHA_LLM_OUTPUT_FORMAT=json_schema`.
Setup saves it in the private configuration. Existing files
without `output_format` keep `json_object`, the compatibility default. A saved
file takes precedence over later environment changes. Use the same configuration
for the API and worker. Schema mode asks for exactly the known candidate IDs;
client validation still rejects omissions/duplicates if a backend ignores it.
Unsupported formats fall back visibly, with no automatic provider/format retry.
[ADR 0009](decisions/0009-opt-in-constrained-ranking-output.md) explains the local
development evidence and compatibility boundary.

Run [OmniRoute](https://github.com/diegosouzapw/OmniRoute) separately if desired.
Its documented endpoint is `http://127.0.0.1:20128/v1`; pass that `--model-url` and
an explicit configured route/model to setup. Gateway/downstream terms and its
[MIT licence](https://github.com/diegosouzapw/OmniRoute/blob/main/LICENSE) remain
separate from the Apache-2.0 core and document/model licences. No gateway code,
weights, cloud account or paid route is bundled or required.

**A local gateway can forward queries/snippets to cloud providers.** Verify its
local-only route, external fallbacks and logs. A route label or localhost address
does not establish local inference. Anvesha reports downstream routing as unverified.
For another machine/container pass `--allow-model-network`; private LAN IPs and
`ollama`, `omniroute`, `host.docker.internal` permit HTTP. Other named/public
endpoints require HTTPS. Clients cannot select endpoints through a search request.

Legacy environment-based `anvesha serve` and `python -m anvesha.worker` still work.
Set matching database/source/model settings in both processes; client keys are
needed only by the API. Saved-file commands reduce configuration mismatches.

## Ranking behavior

Send `{"query":"your research question"}` with `X-API-Key` for default LLM ranking,
then poll the ID and read the snapshot. Explicit `"ranking":"lexical"` selects
the baseline. [API documentation](API.md) covers the contract. Authenticated
capabilities expose modes, default, model configuration and document count, never
endpoint addresses or credentials. LLM currently supports only the local source;
optional Wikidata requests must explicitly select lexical ranking.

The worker retrieves with BM25/RRF, then sends at most 20 candidate IDs, titles
(240 characters each), snippets (1,200 each), evidence labels and the original
query to the configured model. No URL field, client key, corpus, feedback, reviewer
label or tool is supplied. Source text can contain URLs or sensitive data; review
it before enabling external processing.

Only a complete permutation of supplied IDs is accepted. Reranking precedes the
requested result limit. Unassessed candidates retain lexical order; fewer than two
candidates need no call. `ranking_method`/`lexical_rank` identify changed ordering;
`score` remains the original RRF value, never a truth probability. Source text,
URLs and rights stay intact. Prompt injection can still damage relevance.

Configuration fingerprints bind endpoint/model identifiers, prompt and bounds,
not verified weights or routes. API/worker settings must match. Model errors or
configuration drift publish lexical results as `completed_partial` with sanitized
`llm:*` warnings. The total model deadline defaults to 60 seconds (maximum 120),
without application retries; worker recovery can repeat a call. Cancellation
prevents publication but cannot recall content already sent.

## Browser, storage and upgrades

The `/` browser loads no CDNs/fonts, has no built-in analytics or persistent
key/history store, uses same-origin requests and renders untrusted content as
plain text. CSP/no-store/no-referrer headers apply. Reload disconnects; Disconnect
also clears displayed query/results. Opening source links, extensions and the OS
are separate trust boundaries. OpenAPI remains at `/openapi.json`; CDN-backed
`/docs` and `/redoc` are disabled.

Operational queries, snapshots and feedback stay in the unencrypted local database
until deletion. Reload/disconnect do not delete server records. Automatic expiry
and backup deletion remain ANV-008. CLI API commands disable access logs; proxies
and gateways log independently. There is no anonymous/untracked web-search promise.
See [security](../SECURITY.md) and [model processing](../policies/llm-processing.json).

Before upgrading stop API and worker, back up private configuration and the whole
data directory/volume without running writers, record the source/image revision,
then install/build and restart both services together. Preserve container UID
10001 ownership. SQLite startup migration is additive; never run an older worker
against new LLM jobs. Roll back with matching backup and code/image, rather than
assuming a backwards migration.

**Default change from ANV-021:** new requests omitting ranking now use LLM
processing. Existing accepted jobs and snapshots are unchanged. Old clients
intending model-free work, Wikidata, or old lexical idempotency replay must send
`"ranking":"lexical"`. Otherwise replay may conflict because it describes a
different request. Review processing rights before upgrading an external endpoint;
the new default can transmit new queries/snippets.

## Quality gates

ANV-021 establishes the bounded model protocol. ANV-022 adds the browser, LLM-default
experience and self-hosting. ANV-023 owns actual backend/model tests, pinned hardware
and independent quality comparisons. ANV-009/ANV-011 own permitted source expansion;
ANV-010 owns evidence-led hybrid/planning work. Scientific/multilingual lexical
reports remain frozen baselines. Synthetic UI/protocol fixtures are not independent
labels; the three coached pilot items remain practice only under ANV-020.

See [real local-model evaluation](LOCAL_LLM_EVALUATION.md) for the explicit
ANV-023 CPU pilot. Downloading/testing a model is separate from ordinary setup;
no model or paid API becomes mandatory.
