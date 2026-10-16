"""Operator commands. No network is required for local initialization (ANV-004)."""

import argparse
import json
import secrets
from pathlib import Path

from anvesha.config import Settings
from anvesha.ranking import canonicalize_url
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


def main(argv=None):
    parser = argparse.ArgumentParser(prog="anvesha")
    parser.add_argument("--db", type=Path, help="SQLite file (default ANVESHA_DB_PATH)")
    sub = parser.add_subparsers(dest="command", required=True)
    init_parser = sub.add_parser("init", help="Initialize database and generate an API key")
    init_parser.add_argument("--seed", action="store_true", help="Load clearly labelled demo data")
    ingest_parser = sub.add_parser("ingest", help="Index a reviewed JSON list of local documents")
    ingest_parser.add_argument("file", type=Path)
    ingest_parser.add_argument(
        "--rights-reviewed",
        action="store_true",
        required=True,
        help="Confirm rights to index, store, and display this content to all instance clients",
    )
    serve_parser = sub.add_parser("serve", help="Run the API (start a separate worker too)")
    serve_parser.add_argument("--host", default="127.0.0.1")
    serve_parser.add_argument("--port", type=int, default=8000)
    args = parser.parse_args(argv)
    try:
        settings = Settings.from_env()
        path = args.db or settings.database_path
        if args.command == "serve":
            import uvicorn

            from anvesha.api import create_app

            settings = Settings(
                database_path=path,
                api_keys=settings.api_keys,
                enabled_sources=settings.enabled_sources,
                worker_poll_seconds=settings.worker_poll_seconds,
            )
            if not settings.api_keys:
                raise ValueError("Set ANVESHA_API_KEYS to a key from 'anvesha init'")
            uvicorn.run(create_app(settings), host=args.host, port=args.port)
            return 0
        store = Store(path)
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
