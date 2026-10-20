"""ANV-028: offline synthetic discovery/model/process acceptance and UI preview.

All external-provider traffic uses an injected transport; no real model/labels.
Preview writes an ephemeral synthetic key to the explicit ignored ready file.
Create READY_FILE.stop to stop a preview gracefully. Never pass actual configs.
"""

import argparse
import json
import os
import socket
import subprocess
import sys
import tempfile
import time
from pathlib import Path

import httpx
from smoke_mvp import model_stub, stop_server

from anvesha.llm import LLMConfig, LLMReranker
from anvesha.providers import search_wikipedia
from anvesha.runtime import load_settings, setup
from anvesha.store import Store
from anvesha.worker import process_one

ROOT = Path(__file__).resolve().parents[1]
IDENTITY = "AnveshaBot/0.1 (https://example.test/synthetic-operator)"


def synthetic_worker(config, throttle=False):
    directory = config.resolve().parent
    if (
        not directory.name.startswith("anvesha-discovery-synthetic-")
        or not (directory / "SYNTHETIC_ONLY").is_file()
    ):
        raise ValueError("Only an explicitly synthetic discovery workspace is allowed")
    settings = load_settings(config)
    if settings.database_path != directory / "synthetic.db":
        raise ValueError("Synthetic database must stay inside its owned workspace")
    store = Store(settings.database_path)
    store.initialize()
    calls = []

    def transport(request):
        calls.append(1)
        assert request.url.host == "en.wikipedia.org" and request.url.path == "/w/api.php"
        if throttle:
            return httpx.Response(429, headers={"Retry-After": "120"})
        return httpx.Response(
            200,
            headers={"Content-Type": "application/json"},
            stream=httpx.ByteStream(
                json.dumps(
                    {
                        "query": {
                            "search": [
                                {
                                    "ns": 0,
                                    "pageid": 999999991,
                                    "title": "Synthetic Wikipedia article <img src=x>",
                                    "wordcount": 42,
                                    "timestamp": "2026-10-20T00:00:00Z",
                                    "snippet": "MUST NOT BE COPIED",
                                },
                                {
                                    "ns": 0,
                                    "pageid": 999999992,
                                    "title": "Synthetic discovery reference",
                                    "wordcount": 80,
                                    "timestamp": "2026-10-19T00:00:00Z",
                                },
                            ]
                        }
                    }
                ).encode()
            ),
        )

    def discovery(query, limit, user_agent):
        with httpx.Client(transport=httpx.MockTransport(transport)) as client:
            return search_wikipedia(query, limit, client, user_agent=user_agent)

    processed = process_one(
        store,
        enabled_sources=settings.enabled_sources,
        wikipedia_search=discovery,
        wikipedia_user_agent=settings.wikipedia_user_agent,
        reranker=LLMReranker(settings.llm),
    )
    return {"processed": processed, "discovery_calls": len(calls)}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--worker-config", type=Path)
    parser.add_argument("--throttle", action="store_true")
    parser.add_argument("--preview-ready", type=Path)
    args = parser.parse_args()
    if args.worker_config:
        print(json.dumps(synthetic_worker(args.worker_config, args.throttle)))
        return
    ready = args.preview_ready.resolve() if args.preview_ready else None
    if ready and (ready.exists() or ready.with_suffix(".stop").exists()):
        raise ValueError("Refusing to replace an existing preview file")
    with (
        tempfile.TemporaryDirectory(prefix="anvesha-discovery-synthetic-") as temporary,
        model_stub() as model,
    ):
        directory = Path(temporary).resolve()
        assert directory.parent == Path(tempfile.gettempdir()).resolve()
        (directory / "SYNTHETIC_ONLY").touch()
        endpoint, model_state = model
        config = directory / "private.json"
        settings = setup(
            config,
            directory / "synthetic.db",
            LLMConfig(model="synthetic-smoke-model", base_url=endpoint, api_key=model_state["key"]),
            demo=True,
            enabled_sources=("local", "wikipedia"),
            wikipedia_user_agent=IDENTITY,
        )
        with socket.socket() as listener:
            listener.bind(("127.0.0.1", 0))
            port = listener.getsockname()[1]
        env = {k: v for k, v in os.environ.items() if not k.startswith("ANVESHA_")}
        flags = subprocess.CREATE_NO_WINDOW if os.name == "nt" else 0
        process = None
        ready_written = False
        with (
            (directory / "api.log").open("w", encoding="utf-8") as log,
            httpx.Client(
                base_url=f"http://127.0.0.1:{port}",
                headers={"X-API-Key": settings.api_keys[0]},
                timeout=5,
                trust_env=False,
            ) as api,
        ):

            def start():
                child = subprocess.Popen(
                    [
                        sys.executable,
                        "-m",
                        "anvesha.cli",
                        "run-api",
                        "--config",
                        str(config),
                        "--port",
                        str(port),
                    ],
                    cwd=ROOT,
                    env=env,
                    stdout=log,
                    stderr=log,
                    creationflags=flags,
                )
                try:
                    deadline = time.monotonic() + 20
                    while time.monotonic() < deadline:
                        assert child.poll() is None, "Synthetic API exited"
                        try:
                            if api.get("/healthz").status_code == 200:
                                return child
                        except httpx.TransportError:
                            pass
                        time.sleep(0.1)
                    raise RuntimeError("Synthetic API readiness timed out")
                except BaseException:
                    stop_server(child)
                    raise

            def work(throttle=False):
                cmd = [
                    sys.executable,
                    str(Path(__file__).resolve()),
                    "--worker-config",
                    str(config),
                ]
                if throttle:
                    cmd.append("--throttle")
                result = subprocess.run(
                    cmd, cwd=ROOT, env=env, capture_output=True, timeout=30, creationflags=flags
                )
                assert result.returncode == 0, "Synthetic discovery worker failed"
                return json.loads(result.stdout)

            try:
                process = start()
                if ready:
                    ready.parent.mkdir(parents=True, exist_ok=True)
                    descriptor = os.open(ready, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
                    ready_written = True
                    with os.fdopen(descriptor, "w", encoding="utf-8") as out:
                        json.dump(
                            {
                                "url": str(api.base_url),
                                "key": settings.api_keys[0],
                                "synthetic_only": True,
                            },
                            out,
                        )
                    print(
                        "Synthetic browser preview ready; no live provider/model calls.", flush=True
                    )
                    while not ready.with_suffix(".stop").exists():
                        synthetic_worker(config)
                        time.sleep(0.1)
                    return
                assert (
                    api.get("/v1/capabilities").json()["source_privacy"]["wikipedia"]
                    == "query_sent_to_wikimedia"
                )
                local = api.post("/v1/searches", json={"query": "Anvesha"}).json()
                assert local["sources"] == ["local"] and work()["discovery_calls"] == 0
                body = {"query": "Anvesha", "sources": ["local", "wikipedia"]}
                headers = {"Idempotency-Key": "synthetic-discovery"}
                created = api.post("/v1/searches", json=body, headers=headers)
                assert created.status_code == 202
                job = created.json()
                assert work()["discovery_calls"] == 1
                path = "/v1/searches/" + job["id"]
                assert api.get(path).json()["state"] == "completed"
                results = api.get(path + "/results").json()
                assert results["total"] == 5
                assert all(x["ranking_method"] == "llm_rerank" for x in results["results"])
                wiki = next(x for x in results["results"] if x["display_source"] == "wikipedia")
                assert (
                    wiki["license_url"]
                    and wiki["source_modified_at"]
                    and wiki["evidence_status"] == "metadata_only"
                )
                assert "MUST NOT BE COPIED" not in json.dumps(results)
                receipt = api.post(
                    path + "/feedback", json={"version": 1, "result_id": wiki["id"], "rating": 1}
                )
                assert receipt.status_code == 200 and not receipt.json()["learning_opt_in"]
                stop_server(process)
                process = None
                process = start()
                assert api.get(path + "/results").json() == results
                assert (
                    api.post("/v1/searches", json=body, headers=headers).json()["id"] == job["id"]
                )
                throttled = api.post("/v1/searches", json=body).json()
                assert work(True)["discovery_calls"] == 1
                assert (
                    "wikipedia:rate_limited"
                    in api.get("/v1/searches/" + throttled["id"]).json()["warnings"]
                )
                stop_server(process)
                process = None
                process = start()
                paused = api.post("/v1/searches", json=body).json()
                assert work()["discovery_calls"] == 0
                status = api.get("/v1/searches/" + paused["id"]).json()
                assert (
                    status["state"] == "completed_partial"
                    and "wikipedia:cooldown_active" in status["warnings"]
                )
            finally:
                stop_server(process)
                if ready_written:
                    ready.unlink(missing_ok=True)
                    ready.with_suffix(".stop").unlink(missing_ok=True)
    print(
        "Discovery smoke passed: synthetic fixed-endpoint transport, local-only default, "
        "mixed-source LLM protocol, rights/metadata, feedback, restart/snapshots/idempotency, "
        "durable shared cooldown and owned-process/data cleanup. No live provider/model call."
    )


if __name__ == "__main__":
    main()
