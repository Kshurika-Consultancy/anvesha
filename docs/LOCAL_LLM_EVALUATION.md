# Real local-model evaluation

ANV-023's first pilot tests private CPU inference against the lexical control.
It uses public scientific data, never your queries, feedback or the independent
review workspace. This is an explicit repository experiment, not part of normal
search, setup, CI model downloads or automatic learning.

The [frozen protocol](../benchmarks/local-llm-pilot-v3/protocol.json) selects four
development and 24 evaluation queries before inference. The original candidate
prefix is reordered by the production worker. See [ADR 0007](decisions/0007-local-model-quality-pilot.md)
for method, bounds and interpretation; [evaluation](EVALUATION.md) explains the
inherited expert labels. The broader private-tooling audience needs independent
coding, development, IoT, asset and agent-oriented relevance studies under ANV-020.

The [original development run](../reports/evaluation/local-llm-development-v1/README.md)
timed out on all four requests before any evaluation was released. [ADR 0008](decisions/0008-compact-reranking-identifiers.md)
records the compact candidate aliases introduced from those execution diagnostics.
The [v2 development run](../reports/evaluation/local-llm-development-v2/README.md)
returned four invalid outputs; a structural replay identified a missing ID.
[ADR 0009](decisions/0009-opt-in-constrained-ranking-output.md) adds optional
schema-constrained output. The v3 protocol uses it with the same query IDs and all
other model/ranking bounds. No earlier evaluation queries were released.

## Reproduce this Windows CPU profile

Run from a checkout of this repository. Python 3.12+, SQLite FTS5, uv, sufficient
RAM and about 3 GB of free disk are needed for the selected artifact cache/runtime
(plus the development environment). This measured profile uses 32 GB RAM and six
physical CPU cores. Faster/more capable hardware can give different timings.

```text
uv sync --extra dev --locked
uv run --extra dev python scripts/prepare_local_llm.py --download
uv run --extra dev python -m anvesha.evaluation prepare --download
uv run --extra dev python scripts/serve_local_llm_pilot.py --serve
```

The first explicit bootstrap downloads about 2.52 GB from the official runtime
release/model registry and checks exact byte counts and SHA-256 pins. It never
runs a model. The source dataset preparation is separate and verifies its own
reviewed archive. Existing caches are reused only after integrity checks; a
mismatch is preserved and rejected. No account, paid key, installer, service or
system-wide setting is needed. Model/runtime licences stay separate from Anvesha.
The pins are in [the rights manifest](../policies/models/qwen3-4b-instruct2507.json).

The serve command independently verifies archive, extracted files and GGUF, then
starts a CPU process on `127.0.0.1:8135`. It writes allowlisted backend evidence
under ignored `.anvesha/local-llm/anv023/backend-info.json`. It uses a fixed local
model, offline mode, disabled prompt logging/web UI/MCP proxy, no model tools,
six threads and an 8,192-token context. Ctrl+C stops the owned process. Use another
terminal for the benchmark:

```text
uv run --extra dev python -m anvesha.llm_evaluation run --run-local-model --backend-info .anvesha/local-llm/anv023/backend-info.json
```

This measures development only and writes a private checkpoint, not a partial
public quality report. Inspect execution diagnostics without touching evaluation
labels or changing the protocol based on evaluation outcomes. Then explicitly
release the reserved queries using the same code, environment, backend and settings:

```text
uv run --extra dev python -m anvesha.llm_evaluation run --run-local-model --backend-info .anvesha/local-llm/anv023/backend-info.json --release-evaluation --resume
uv run --extra dev python -m anvesha.llm_evaluation verify
```

Existing output directories are not overwritten. For another execution use a
different `--workspace` and `--output-dir` after `run`; for verification pass
`--output-dir` after `verify`. Interrupted runs preserve completed queries and
require explicit resume. Model/config/source/environment drift rejects resume.
Do not edit an existing protocol/model manifest to make new results fit it;
version a materially changed experiment. Every planned query must be accounted for.

Other hosts can run their own compatible model server for Anvesha's normal API;
this pinned acquisition/server profile is specifically Windows CPU. Actual local
Ollama and OmniRoute acceptance are still separate ANV-023 work, not implied by
llama.cpp interoperability. No model download or serving is needed for ordinary
offline tests or report verification.

## Read the results carefully

The public report contains benchmark IDs/rankings, model/runtime/source hashes,
hardware, aggregate nDCG/MRR/recall, paired nDCG intervals, wins/ties/losses,
latency and failure counts. Raw abstracts, prompts, model responses and operational
jobs are excluded. Model failures publish the worker's lexical fallback and stay
in the comparison. A worker failure scores as an empty model result; it is not
omitted. Lexical control must match the frozen published baseline exactly.

The current report location is `reports/evaluation/local-llm-pilot-v3`. Source
hashes identify evaluated code, including local changes before publication. The
offline verifier checks artifact consistency and recomputed metrics; it does not
attest that inference occurred or require the runtime/model to be installed.

Only the top 20 of at most 50 retrieved candidates can move. No document can be
added, so recall@50 cannot improve through valid reranking alone. An oracle prefix
score uses gold labels after inference solely to diagnose the ranking ceiling;
no label reaches retrieval or the model. Scores measure retrieval relevance to
published evidence annotations, not whether the scientific claim is true.

The 24-query evaluation pilot has limited precision. The query-level bootstrap
does not account for all topic dependence or model-selection uncertainty. Public
scientific data may have appeared in pretraining, and unjudged pairs count as zero.
This cannot establish general-web quality or relevance for coding/IoT/assets/chat.
Do not treat a positive mean alone, an interval spanning zero, or a compatibility
success as proof of improvement. The model was warmed by a separate synthetic
compatibility check; recorded timings are not cold-start or energy measurements.

Local downloads are visible to artifact hosts. Offline runtime configuration,
loopback process ownership and sampled connections provide bounded evidence about
this run, not a firewall/packet-capture proof or anonymity promise. Normal use
still depends on filesystem/backups and the model runtime you choose. A gateway
can forward data elsewhere; never infer local inference from its address alone.
