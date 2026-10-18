# ADR 0006 LLM-default research and self-hosted browser

Status: accepted for ANV-022, 2026-10-18. Supersedes ADR 0005's default-mode
decision; its model/output/privacy boundaries continue to apply.

The user explicitly requested LLM processing as the default. New API requests
omitting `ranking` and the browser's initial selection request `llm`. Missing
configuration fails before acceptance with setup guidance. Keep an explicit free
lexical baseline, offline tests, and visible fallback for accepted model work that
fails. Never label lexical execution as successful model ranking. The model
remains operator-supplied; no paid API, weights or hosted account is mandatory.
Actual quality gains still require ANV-023 evidence.

This changes request meaning and processing disclosure. Document the upgrade:
operators review rights, old lexical clients/replays send the explicit mode,
and accepted jobs/snapshots stay stable. Direct Store/evaluation helpers retain
lexical defaults to preserve offline baselines.

Package a same-origin browser with no framework, CDN, analytics, cookies,
browser storage or service worker. Keys stay in tab memory; content is plain text
with safe links. CSP, no-store and no-referrer apply. Remove CDN-backed interactive
docs while retaining OpenAPI. Cover submission, hinted polling, cancellation,
stable pagination and version-bound feedback with learning disabled. This is not
a historical job manager or an independent human-assessment form.

Provide a private JSON configuration created exclusively with a random key and
matching settings, plus native supervision of separate API/worker processes. No
accepted job belongs solely to the supervisor. A child exit shuts down its sibling;
persisted jobs/leases allow recovery. Configuration is plaintext under filesystem
permissions, not a secrets vault. Do not log it; explicit `show-key` displays the
client key locally.

Run the same commands in a non-root multi-stage image with locked dependencies.
Compose separates API/worker, persists local SQLite, publishes host loopback and
offers an optional unexposed CPU Ollama service. No model is auto-downloaded.
Pin image digests and exclude private build context. Worker startup waits for API
health; liveness is not proof of worker/model health or search quality.

CI's private-network chat fixture proves transport, not actual model usefulness
or every gateway route. Native process and real-browser checks complement it.
ANV-023 owns actual backend acceptance and independent relevance comparisons;
ANV-008 owns hosted hardening. This slice does not complete all M3 gates.

Reviewed primary sources:

- [Docker build practices](https://docs.docker.com/build/building/best-practices/)
  cover multi-stage builds, non-root users and restricted build context.
- [Compose startup order](https://docs.docker.com/compose/how-tos/startup-order/)
  describes health-gated dependencies.
- [uv in Docker](https://docs.astral.sh/uv/guides/integration/docker/)
  describes fixed virtual environment paths and non-editable runtime installs.
- [Ollama Docker](https://docs.ollama.com/docker) documents the optional CPU runtime.
