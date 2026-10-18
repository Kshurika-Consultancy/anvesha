# Anvesha — Private Search for Your Own AI Tools

Anvesha is Kshurika Consultancy's open-source search engine for people who want control over their data and the tools that use it. Run it on your own computer or home server, use a local LLM, and build internal tools without a mandatory service that collects your queries or usage. **No mandatory paid API, hosted LLM, GPU, or database service.**

It is a search building block for your own research, coding and development projects, personal IoT operations, asset-management tools, and private AI agents or chat systems. Those are intended integration uses: the current preview searches documents you import; it does not control devices/assets, provide a chat agent, or ship those integrations. You choose what is indexed, where models run, who can access the instance, and whether an optional external provider receives anything. Local storage, backups and model-server settings still need your care.

Submit a query, receive an ID, poll its status, inspect stable sources and give feedback. Separate API/worker processes persist jobs, ownership, results and feedback in SQLite. **LLM-assisted ranking is the default**, using your configured local or compatible gateway model after FTS5/BM25 retrieval. An explicit lexical baseline runs without any model.

**Start here:** [native and Docker self-hosting guide](docs/PRIVATE_RESEARCH.md). Import permitted documents, connect your local model and use the bundled browser. No paid API is mandatory. A local gateway can still forward data to cloud providers; verify its routing.

**Scope:** the default seeded corpus contains three visibly synthetic demonstration documents at example.org URLs. This is a private-corpus search preview, not a general-web search engine, a factual-verification system, or evidence of Google-level quality. LLM reranking remains experimental; broader backend and domain validation remains open. Query planning, page inspection, embeddings, automatic retention and feedback learning remain future work.

The [first real local-model pilot](reports/evaluation/local-llm-pilot-v3/ANALYSIS.md)
used Qwen3-4B on CPU. On 24 reserved scientific queries, nDCG@10 was 0.6169 for
lexical search and 0.6747 with LLM reranking, including five invalid-output
fallbacks. The paired 95% interval includes zero, so **improvement is not
established**. This is a measured starting point, not a general quality claim.

## Repository navigation

- [Agent instructions](AGENTS.md): required workflow for coding agents and contributors.
- [Saved plan](docs/PLAN.md), [research and source rights](docs/RESEARCH.md), and [milestones](docs/MILESTONES.md).
- [Authoritative task ledger](docs/tracking/tasks.json), [status](docs/tracking/STATUS.md), and [handoff](docs/tracking/HANDOFF.md).
- [Architecture](docs/architecture/README.md), [MVP contract](docs/architecture/MVP_CONTRACT.md), [API reference](docs/API.md), and [security boundaries](SECURITY.md).

## Quick start

Requirements: Python 3.12+ with SQLite FTS5, and [uv](https://docs.astral.sh/uv/getting-started/installation/). The lockfile pins dependencies. Windows and Linux CI configurations are included; local verification evidence is recorded in the handoff.

From the repository directory:

```text
uv sync --extra dev --locked
uv run --extra dev anvesha setup --model YOUR_INSTALLED_MODEL --seed-demo
uv run --extra dev anvesha show-key
uv run --extra dev anvesha start
```

Choose an already installed model after reviewing its licence and hardware needs. The endpoint defaults to `http://127.0.0.1:11434/v1` (Ollama). Setup saves a random client key and matching settings in ignored `.anvesha/server.json`; it refuses overwrite. `--seed-demo` loads three synthetic records. No model is downloaded.

Open [the browser](http://127.0.0.1:8000/), paste the key shown locally, and search. The browser loads no external assets and keeps its key in tab memory. `start` supervises separate API/worker processes; Ctrl+C stops both. Restarting preserves jobs/results. The API stays on loopback; public hosting remains a later gate.

For a model-free preview, use `setup --lexical-only --seed-demo`, then explicitly select **Lexical baseline** in the browser/API. Missing model configuration produces setup guidance, not silent model-free execution. Docker Compose, private configuration, imports, OmniRoute and upgrades are covered in [the self-hosting guide](docs/PRIVATE_RESEARCH.md). `/openapi.json` remains available; CDN-backed interactive docs are disabled.

## Submit, poll and give feedback

In an API-client PowerShell terminal, set the key locally with `$env:ANVESHA_API_KEYS = uv run anvesha show-key`. This explicit example uses the lexical baseline; omit `ranking` for default LLM processing:

```powershell
$headers = @{ 'X-API-Key' = $env:ANVESHA_API_KEYS; 'Idempotency-Key' = 'first-demo-search' }
$job = Invoke-RestMethod -Method Post -Uri 'http://127.0.0.1:8000/v1/searches' -Headers $headers -ContentType 'application/json' -Body '{"query":"free local search","sources":["local"],"limit":10,"ranking":"lexical"}'
$status = Invoke-RestMethod -Uri "http://127.0.0.1:8000/v1/searches/$($job.id)" -Headers $headers
$status
```

Poll until `completed` or `completed_partial` before requesting results. Respect the server's polling hint. If the worker has not run yet, result retrieval returns HTTP 409.

```powershell
$results = Invoke-RestMethod -Uri "http://127.0.0.1:8000/v1/searches/$($job.id)/results?version=1" -Headers $headers
$results.results
$feedback = @{ version = 1; rating = 1; result_id = $results.results[0].id; learning_opt_in = $false } | ConvertTo-Json
Invoke-RestMethod -Method Post -Uri "http://127.0.0.1:8000/v1/searches/$($job.id)/feedback" -Headers $headers -ContentType 'application/json' -Body $feedback
```

Reuse an idempotency key only for the same query/sources/limit/ranking; a different request with that key returns 409. Delete a retained job with `DELETE /v1/searches/{id}`. Automatic expiry is not implemented yet. Feedback is stored, not used to automatically train or change ranking.

New requests default to `ranking: "llm"`; explicitly sending that field is also supported. The model only reorders retrieved candidates. Invalid output/outage keeps lexical results with visible warnings. **Upgrade change:** old model-free clients and old lexical idempotency replays must send `"ranking":"lexical"`. Existing accepted jobs stay unchanged. See [processing limits and upgrade guidance](docs/PRIVATE_RESEARCH.md).

## Search your own permitted content

Prepare a JSON list with `id`, `url`, `title`, `content`, `license`, and `attribution` for each document. See [the demonstration import](examples/documents.json). URLs are identifiers displayed in results; ingestion does not download them.

```text
uv run --extra dev anvesha ingest examples/documents.json --config .anvesha/server.json --rights-reviewed
```

The flag acknowledges your review of rights to store, index, and display that content. It is not an automated legal clearance. **All configured API clients share this document corpus**; job history is owner-isolated, but document-level tenant permissions are not implemented.

Imports upsert by document ID. Keep IDs stable. Import validation runs before writes; a database failure during the import may still leave earlier documents applied, so rerunning the same IDs is safe. Data import is an operator CLI operation, not a public upload endpoint.

## Optional free live Wikidata search

The optional connector needs no paid account or API key. It searches English Wikidata labels/descriptions and returns metadata-only results. It is not full-web search, does not fetch entity pages, and sends the query to Wikimedia.

Set these in **both API and worker terminals** and restart both processes:

```powershell
$env:ANVESHA_ENABLED_SOURCES = 'local,wikidata'
$env:ANVESHA_WIKIDATA_USER_AGENT = 'Anvesha/0.1 (mailto:your-real-contact@example.org)'
```

Replace the contact with your actual operator contact before use. On Bash use `export NAME='value'`. Then submit `sources: ["local", "wikidata"]`. Default requests still search only local documents. Network access is optional; failures are visible as partial/failed jobs. See the [Wikidata policy manifest](policies/sources/wikidata.json).

## Real search evaluation

The first M2 evaluation uses 500 published scientific queries (200 development, 300 evaluation) and the full 5,183-document SciFact corpus. It runs an independent token-overlap floor, direct BM25, and the actual local M1 worker. No paid API, LLM, or new model is required.

```text
uv run --extra dev python -m anvesha.evaluation prepare --download
uv run --extra dev python -m anvesha.evaluation run --export-pool
uv run --extra dev python -m anvesha.evaluation verify
```

Only the explicit prepare download uses the network; raw abstracts stay in ignored local storage. The licensed query/annotation subset and measured reports are in the repository. These are upstream expert annotations, with zero new Anvesha human judgments. This scientific slice does not establish general-web coverage. See [methodology](docs/EVALUATION.md), [data and attribution](benchmarks/scifact-v1/README.md), and [baseline report](reports/evaluation/scifact-v1/README.md).

ANV-020 adds a [multilingual corpus](benchmarks/xquad-intents-v1/README.md) beyond scientific claims: 720 published English/Spanish/Hindi query instances and 36 explicitly AI-authored intent probes. The [human-review workflow](docs/review/README.md) provides local blinded browser forms, separate credentials, revision-safe imports, agreement and adjudication. Human assessments remain pending; no paid API or hosted model is required. See the [expanded report](reports/evaluation/xquad-intents-v1/README.md).

## Configuration and development

| Variable | Default | Purpose |
| --- | --- | --- |
| `ANVESHA_DB_PATH` | `.anvesha/anvesha.db` | Shared local SQLite file; API and worker must agree |
| `ANVESHA_API_KEYS` | unset | Required API secrets, comma separated; each key defines a separate owner |
| `ANVESHA_ENABLED_SOURCES` | `local` | Allowlist of `local` and optionally `wikidata` |
| `ANVESHA_WORKER_POLL_SECONDS` | `1` | Idle queue polling, 0.1–60 seconds |
| `ANVESHA_WIKIDATA_USER_AGENT` | unset | Identifying operator contact for optional live calls |
| `ANVESHA_LLM_MODEL` | unset | Enables explicitly requested local-source reranking with your selected model |
| `ANVESHA_LLM_BASE_URL` | `http://127.0.0.1:11434/v1` | Fixed chat endpoint; OmniRoute can use port 20128 |
| `ANVESHA_LLM_API_KEY` | unset | Optional runtime/gateway secret; never stored in jobs |
| `ANVESHA_LLM_ALLOW_NETWORK` | `false` | Explicitly allow a non-loopback model endpoint; does not audit gateway egress |
| `ANVESHA_LLM_TIMEOUT_SECONDS` | `60` | Total model-call deadline, 0.1–120 seconds |
| `ANVESHA_LLM_CANDIDATE_LIMIT` | `20` | Rerank at most 2–20 retrieved candidates |

[.env.example](.env.example) documents configuration; files named `.env` are **not automatically loaded**. Set environment variables in your shell. Keys, databases, and virtual environments are git-ignored. Do not store private corpora in the repository.

```text
uv run --extra dev ruff check .
uv run --extra dev ruff format --check .
uv run --extra dev pytest
uv run --extra dev python scripts/smoke_mvp.py
uv run --extra dev python scripts/check_tracking.py
```

Default tests are offline and mock Wikimedia. Live source behavior requires a separate operator-configured smoke test. The tracking check validates task IDs/dependencies, completion evidence, local Markdown links, and task-linked code reminders. It makes gaps visible; it cannot prove that every requirement was remembered or that a recorded human review occurred.

Independently written code is [Apache-2.0](LICENSE). Source data retains its own rights; see [NOTICE](NOTICE), [CONTRIBUTING.md](CONTRIBUTING.md), and [source manifests](policies/sources/local.json).
