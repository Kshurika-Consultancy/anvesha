"""Operator commands. No network is required for local initialization (ANV-004)."""

import argparse
import json
import os
import secrets
import sqlite3
from dataclasses import replace
from pathlib import Path

from anvesha.config import Settings
from anvesha.ranking import canonicalize_url
from anvesha.retention import CLEANUP_BATCH, seconds_from_env
from anvesha.sqlite_runtime import inspect_runtime
from anvesha.store import Store

DEMO_DOCUMENTS = [
    {
        "id": "demo-async",
        "url": "https://example.org/anvesha-demo/async-search",
        "title": "Anvesha demonstration: asynchronous search jobs",
        "content": "Demonstration document. Submit a search query, receive a job ID, and poll "
        "for status and results. The separate worker processes persisted SQLite jobs. "
        "These examples demonstrate software behavior, not independent web research.",
        "license": "Apache-2.0",
        "attribution": "Kshurika Consultancy — synthetic demo corpus",
    },
    {
        "id": "demo-free",
        "url": "https://example.org/anvesha-demo/free-search",
        "title": "Anvesha demonstration: free local search",
        "content": "Demonstration document. Anvesha local search requires no paid API, no "
        "hosted LLM and no GPU. SQLite FTS5 indexes operator-supplied documents. "
        "Wikidata entity metadata is an optional live source, not full web search.",
        "license": "Apache-2.0",
        "attribution": "Kshurika Consultancy — synthetic demo corpus",
    },
    {
        "id": "demo-feedback",
        "url": "https://example.org/anvesha-demo/feedback",
        "title": "Anvesha demonstration: feedback and relevance",
        "content": "Demonstration document. Clients can give feedback on a result snapshot. "
        "Ratings are signals, not truth. Learning consent defaults off. The MVP stores "
        "feedback; reviewed training and benchmark evaluation are future milestones.",
        "license": "Apache-2.0",
        "attribution": "Kshurika Consultancy — synthetic demo corpus",
    },
]


def validate_document(document):
    required = {"id", "url", "title", "content", "license", "attribution"}
    if not isinstance(document, dict) or not required <= document.keys():
        raise ValueError("Each document needs id, url, title, content, license and attribution")
    if any(not isinstance(document[key], str) or not document[key].strip() for key in required):
        raise ValueError("Document fields must be nonblank strings")
    canonicalize_url(document["url"])
    if len(document["content"]) > 1_000_000:
        raise ValueError("Each document is limited to 1,000,000 characters")
    return {key: document[key] for key in required}


def diagnostics(settings):
    """ANV-021: offline/read-only diagnostics without printing any credentials."""
    sqlite = inspect_runtime()
    fts5 = sqlite["fts5_available"]
    count = None
    if settings.database_path.is_file():
        try:
            uri = settings.database_path.resolve().as_uri() + "?mode=ro"
            connection = sqlite3.connect(uri, uri=True)
            try:
                count = connection.execute("SELECT count(*) FROM documents").fetchone()[0]
                connection.execute("SELECT ranking, expires_at FROM jobs LIMIT 0")
            finally:
                connection.close()
        except sqlite3.Error:
            count = None
    return {
        "ready": bool(sqlite["supported"] and settings.api_keys and count is not None),
        "sqlite_runtime": sqlite,
        "fts5_available": fts5,
        "api_keys_configured": bool(settings.api_keys),
        "database_initialized": count is not None,
        "document_count": count,
        "enabled_sources": list(settings.enabled_sources),
        "retention_seconds": settings.retention_seconds,
        "retention_applies_to": "new_searches",
        "expiry_cleanup": "separate_worker_or_explicit_prune",
        "llm": {
            "configured": settings.llm.enabled,
            "endpoint_scope": settings.llm.endpoint_scope,
            "default_ranking": "llm",
            "explicit_lexical_baseline_available": True,
            "gateway_downstream_verified": False,
        },
        "network_checks_performed": False,
    }


def main(argv=None):
    parser = argparse.ArgumentParser(prog="anvesha")
    parser.add_argument("--db", type=Path, help="SQLite file (default ANVESHA_DB_PATH)")
    sub = parser.add_subparsers(dest="command", required=True)
    init_parser = sub.add_parser("init", help="Initialize database and generate an API key")
    init_parser.add_argument("--seed", action="store_true", help="Load clearly labelled demo data")
    doctor_parser = sub.add_parser(
        "doctor", help="Check local readiness without network or secrets"
    )
    doctor_parser.add_argument("--config", type=Path)
    ingest_parser = sub.add_parser("ingest", help="Index a reviewed JSON list of local documents")
    ingest_parser.add_argument("file", type=Path)
    ingest_parser.add_argument("--config", type=Path)
    ingest_parser.add_argument(
        "--rights-reviewed",
        action="store_true",
        required=True,
        help="Confirm rights to index, store, and display this content to all instance clients",
    )
    prune_parser = sub.add_parser(
        "prune", help="Preview expired search deletion; --apply deletes one bounded batch"
    )
    prune_parser.add_argument("--config", type=Path)
    prune_parser.add_argument("--apply", action="store_true")
    prune_parser.add_argument("--batch-size", type=int, default=CLEANUP_BATCH)
    serve_parser = sub.add_parser("serve", help="Run the API (start a separate worker too)")
    serve_parser.add_argument("--host", default="127.0.0.1")
    serve_parser.add_argument("--port", type=int, default=8000)
    default_config = Path(os.getenv("ANVESHA_CONFIG_PATH", ".anvesha/server.json"))
    setup_parser = sub.add_parser("setup", help="Save a private configuration; no model downloads")
    setup_parser.add_argument("--config", type=Path, default=default_config)
    modes = setup_parser.add_mutually_exclusive_group(required=True)
    modes.add_argument("--model", help="Name of a model installed in your runtime")
    modes.add_argument("--lexical-only", action="store_true", help="Explicit model-free baseline")
    setup_parser.add_argument("--model-url", help="Chat endpoint ending in /v1")
    setup_parser.add_argument("--allow-model-network", action="store_true")
    setup_parser.add_argument("--seed-demo", action="store_true")
    setup_parser.add_argument(
        "--retention-seconds",
        type=int,
        help="New search lifetime; default seven days, 0 explicitly keeps history indefinitely",
    )
    for name in ("start", "run-api", "run-worker", "show-key"):
        service = sub.add_parser(
            name,
            help={
                "start": "Run API and worker together as separate supervised processes",
                "run-api": "Run the API from private configuration",
                "run-worker": "Run the worker from private configuration",
                "show-key": "Print your client key locally; keep the output private",
            }[name],
        )
        service.add_argument("--config", type=Path, default=default_config)
        if name in {"start", "run-api"}:
            service.add_argument("--host", default="127.0.0.1")
            service.add_argument("--port", type=int, default=8000)
    args = parser.parse_args(argv)
    try:
        if args.command in {"setup", "start", "run-api", "run-worker", "show-key"}:
            from anvesha import runtime

            if args.command == "setup":
                from anvesha.llm import LLMConfig

                overrides = {"model": args.model or ""}
                if args.model_url:
                    overrides["base_url"] = args.model_url
                if args.allow_model_network:
                    overrides["allow_network"] = True
                llm = LLMConfig.from_env(**overrides)
                saved = runtime.setup(
                    args.config,
                    args.db or Path(os.getenv("ANVESHA_DB_PATH", ".anvesha/anvesha.db")),
                    llm,
                    demo=args.seed_demo,
                    retention_seconds=(
                        args.retention_seconds
                        if args.retention_seconds is not None
                        else seconds_from_env()
                    ),
                )
                print(f"Private configuration saved: {args.config.resolve()}")
                print(
                    f"New search retention: {saved.retention_seconds} seconds "
                    "from acceptance (0 means indefinite)."
                )
                print(
                    "Run 'anvesha show-key' locally to copy the client key, then 'anvesha start'."
                )
                return 0
            if args.command == "start":
                return runtime.start(args.config.resolve(), args.host, args.port)
            configured = runtime.load_settings(args.config)
            if args.command == "show-key":
                print(configured.api_keys[0])
            elif args.command == "run-api":
                import uvicorn

                from anvesha.api import create_app

                uvicorn.run(
                    create_app(configured), host=args.host, port=args.port, access_log=False
                )
            else:
                from anvesha.worker import main as worker_main

                worker_main([], settings=configured)
            return 0
        if getattr(args, "config", None):
            from anvesha.runtime import load_settings

            settings = load_settings(args.config)
        else:
            settings = Settings.from_env()
        path = args.db or settings.database_path
        settings = replace(settings, database_path=path)
        if args.command == "doctor":
            report = diagnostics(settings)
            print(json.dumps(report, indent=2))
            return 0 if report["ready"] else 1
        if args.command == "serve":
            import uvicorn

            from anvesha.api import create_app

            if not settings.api_keys:
                raise ValueError("Set ANVESHA_API_KEYS to a key from 'anvesha init'")
            uvicorn.run(create_app(settings), host=args.host, port=args.port, access_log=False)
            return 0
        store = Store(path)
        if args.command == "prune":
            print(
                json.dumps(store.prune_expired(limit=args.batch_size, apply=args.apply), indent=2)
            )
            return 0
        if args.command == "init":
            store.initialize()
            if args.seed:
                for document in DEMO_DOCUMENTS:
                    store.upsert_document(document)
            print(f"Database ready: {path.resolve()}")
            print("Set ANVESHA_API_KEYS in the API shell to this new secret:")
            print(secrets.token_urlsafe(32))
            print("This key is not saved. Re-running init does not rotate configured keys.")
            if args.seed:
                print("Loaded 3 synthetic demo documents. No web pages were fetched.")
            return 0
        if args.file.stat().st_size > 10_000_000:
            raise ValueError("Import file must be at most 10 MB")
        documents = json.loads(args.file.read_text(encoding="utf-8"))
        if not isinstance(documents, list) or len(documents) > 10_000:
            raise ValueError("Import must be a JSON list of at most 10,000 documents")
        validated = [validate_document(document) for document in documents]
        store.initialize()
        for document in validated:
            store.upsert_document(document)
        print(f"Indexed {len(validated)} documents. No URLs were fetched.")
        return 0
    except (OSError, ValueError) as exc:
        parser.error(str(exc))


if __name__ == "__main__":
    raise SystemExit(main())
