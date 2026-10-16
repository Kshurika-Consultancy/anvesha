# ADR 0001 Local-first durable MVP

Status: accepted for M1, 2026-10-16. Tasks: ANV-001, ANV-003, ANV-004.

The researched target architecture suggested PostgreSQL and a durable workflow service. The first implementation needs an easy, no-paid-service setup while proving request acceptance, worker recovery, result snapshots, and feedback semantics.

Use Python/FastAPI, a local SQLite database with WAL and FTS5, and a separate worker. SQLite is the authoritative job store and local lexical index. Use short write transactions, lease tokens, idempotency, and atomic final publication. Keep external operations outside transactions. A small single-host deployment is the supported topology; network-mounted database files and multi-host workers are not supported.

Tradeoffs: minimal setup and offline tests, but serialized SQLite writes, no distributed scheduler, and lexical retrieval only. Scale through measured migration to PostgreSQL and a production search index/workflow service under ANV-013, not by claiming SQLite is the final architecture. M1 does not implement semantic embeddings, deep search, or Google-level coverage.
