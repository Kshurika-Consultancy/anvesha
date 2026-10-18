"""ANV-006: real HTTP/API restart/worker-process smoke test, entirely offline."""

import json
import os
import secrets
import socket
import subprocess
import sys
import tempfile
import time
from contextlib import contextmanager
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from threading import Thread

import httpx

ROOT = Path(__file__).resolve().parents[1]


@contextmanager
def model_stub(output_format="json_object"):
    """ANV-021: local synthetic protocol fixture, not an actual model/provider."""
    state = {"calls": 0, "fail": False, "ids": [], "key": secrets.token_urlsafe(32)}

    class Handler(BaseHTTPRequestHandler):
        def log_message(self, *args):
            pass

        def do_POST(self):
            size = int(self.headers.get("Content-Length", "0"))
            if not 0 < size <= 131072:
                self.send_error(413)
                return
            assert self.path == "/v1/chat/completions"
            assert self.headers.get("Authorization") == "Bearer " + state["key"]
            body = json.loads(self.rfile.read(size))
            assert body["model"] == "synthetic-smoke-model"
            supplied = json.loads(body["messages"][1]["content"])
            state["ids"] = [item["id"] for item in supplied["candidates"]]
            assert body["response_format"]["type"] == output_format
            if output_format == "json_schema":
                schema = body["response_format"]["json_schema"]["schema"]
                ranked = schema["properties"]["ranked_ids"]
                assert ranked["items"]["enum"] == state["ids"]
                assert ranked["minItems"] == ranked["maxItems"] == len(state["ids"])
            else:
                assert body["response_format"] == {"type": "json_object"}
            state["calls"] += 1
            payload = json.dumps(
                {
                    "choices": [
                        {
                            "finish_reason": "stop",
                            "message": {
                                "role": "assistant",
                                "content": json.dumps({"ranked_ids": state["ids"][::-1]}),
                            },
                        }
                    ]
                }
            ).encode()
            self.send_response(500 if state["fail"] else 200)
            self.send_header("Content-Type", "application/json")
            self.send_header("Content-Length", str(len(payload)))
            self.end_headers()
            self.wfile.write(payload)

    server = ThreadingHTTPServer(("127.0.0.1", 0), Handler)
    thread = Thread(target=server.serve_forever, kwargs={"poll_interval": 0.05}, daemon=True)
    thread.start()
    try:
        yield f"http://127.0.0.1:{server.server_port}/v1", state
    finally:
        server.shutdown()
        server.server_close()
        thread.join(timeout=5)
        if thread.is_alive():
            raise RuntimeError("Synthetic model server did not stop")


def stop_server(process):
    """Stop API descendants too: Windows venv launchers may wrap the real server.

    ANV-018. Waiting for the launcher alone does not release a child's inherited
    log handle or listening socket, and can make a restart test hit the old API.
    """
    if process is None or process.poll() is not None:
        return
    if sys.platform == "win32":
        stopped = subprocess.run(
            ["taskkill", "/PID", str(process.pid), "/T", "/F"],
            stdout=subprocess.DEVNULL,
            stderr=subprocess.PIPE,
            creationflags=subprocess.CREATE_NO_WINDOW,
            timeout=10,
        )
        if stopped.returncode != 0 and process.poll() is None:
            raise RuntimeError("Failed to stop the Windows smoke server process tree")
        process.wait(timeout=5)
        return
    process.terminate()
    try:
        process.wait(timeout=5)
    except subprocess.TimeoutExpired:
        process.kill()
        process.wait(timeout=5)


def main():
    with (
        tempfile.TemporaryDirectory(prefix="anvesha-smoke-") as temporary,
        model_stub() as (model_endpoint, model_state),
    ):
        directory = Path(temporary)
        environment = {
            key: value for key, value in os.environ.items() if not key.startswith("ANVESHA_")
        }
        environment.update(
            ANVESHA_DB_PATH=str(directory / "smoke.db"),
            ANVESHA_API_KEYS=secrets.token_urlsafe(32),
            ANVESHA_ENABLED_SOURCES="local",
            ANVESHA_LLM_MODEL="synthetic-smoke-model",
            ANVESHA_LLM_BASE_URL=model_endpoint,
            ANVESHA_LLM_API_KEY=model_state["key"],
            ANVESHA_LLM_TIMEOUT_SECONDS="5",
        )
        creationflags = subprocess.CREATE_NO_WINDOW if sys.platform == "win32" else 0

        def run_module(module, *args):
            return subprocess.run(
                [sys.executable, "-m", module, *args],
                cwd=ROOT,
                env=environment,
                capture_output=True,
                text=True,
                check=True,
                timeout=30,
                creationflags=creationflags,
            )

        # Initialization prints a suggested key; capture it, do not expose it in logs.
        run_module("anvesha.cli", "init", "--seed")
        with socket.socket() as listener:
            listener.bind(("127.0.0.1", 0))
            port = listener.getsockname()[1]
        base_url = f"http://127.0.0.1:{port}"
        server = None
        with (
            (directory / "server.log").open("w", encoding="utf-8") as log,
            httpx.Client(
                base_url=base_url,
                headers={"X-API-Key": environment["ANVESHA_API_KEYS"]},
                timeout=5,
                trust_env=False,
            ) as client,
        ):

            def start():
                process = subprocess.Popen(
                    [sys.executable, "-m", "anvesha.cli", "serve", "--port", str(port)],
                    cwd=ROOT,
                    env=environment,
                    stdout=log,
                    stderr=log,
                    creationflags=creationflags,
                )
                deadline = time.monotonic() + 15
                while time.monotonic() < deadline:
                    if process.poll() is not None:
                        process.wait(timeout=5)
                        raise RuntimeError("API process exited during startup")
                    try:
                        if client.get("/healthz").status_code == 200:
                            return process
                    except httpx.TransportError:
                        pass
                    time.sleep(0.1)
                stop_server(process)
                raise RuntimeError("API startup timed out")

            try:
                server = start()
                request = {
                    "query": "free local search",
                    "sources": ["local"],
                    "limit": 10,
                    "ranking": "lexical",
                }
                response = client.post(
                    "/v1/searches", json=request, headers={"Idempotency-Key": "smoke-one"}
                )
                assert response.status_code == 202, response.text
                job_id = response.json()["id"]
                location = f"/v1/searches/{job_id}"
                assert client.get(location).json()["state"] == "queued"
                stop_server(server)
                server = start()
                assert client.get(location).json()["state"] == "queued"
                run_module("anvesha.worker", "--once")
                status = client.get(location).json()
                assert status["state"] == "completed", status
                response = client.get(location + "/results", params={"version": 1})
                response.raise_for_status()
                results = response.json()["results"]
                assert results and all(
                    item["evidence_status"] == "local_document" for item in results
                )
                replay = client.post(
                    "/v1/searches", json=request, headers={"Idempotency-Key": "smoke-one"}
                )
                assert replay.status_code == 200 and replay.json()["id"] == job_id
                feedback = client.post(
                    location + "/feedback",
                    json={
                        "version": 1,
                        "rating": 1,
                        "result_id": results[0]["id"],
                    },
                )
                assert feedback.status_code == 200, feedback.text
                assert feedback.json()["learning_opt_in"] is False
                assert client.delete(location).status_code == 204
                assert client.get(location).status_code == 404
                second = client.post("/v1/searches", json=request).json()
                cancelled = f"/v1/searches/{second['id']}"
                assert client.post(cancelled + "/cancel").json()["state"] == "cancelled"
                run_module("anvesha.worker", "--once")
                assert client.get(cancelled).json()["state"] == "cancelled"
                assert model_state["calls"] == 0
                assert json.loads(run_module("anvesha.cli", "doctor").stdout)["ready"]
                intelligent = client.post(
                    "/v1/searches", json={"query": "Anvesha", "limit": 1}
                ).json()
                intelligent_url = f"/v1/searches/{intelligent['id']}"
                run_module("anvesha.worker", "--once")
                assert client.get(intelligent_url).json()["state"] == "completed"
                intelligent_result = client.get(intelligent_url + "/results").json()["results"][0]
                assert intelligent_result["lexical_rank"] == len(model_state["ids"])
                assert intelligent_result["id"].startswith("res_")
                assert intelligent_result["id"] not in model_state["ids"]
                assert intelligent_result["ranking_method"] == "llm_rerank"
                receipt = client.post(
                    intelligent_url + "/feedback", json={"version": 1, "rating": 1}
                )
                assert receipt.json()["pipeline_version"] == intelligent["pipeline_version"]
                model_state["fail"] = True
                fallback = client.post(
                    "/v1/searches", json={"query": "Anvesha", "ranking": "llm"}
                ).json()
                run_module("anvesha.worker", "--once")
                fallback_status = client.get(f"/v1/searches/{fallback['id']}").json()
                assert fallback_status["state"] == "completed_partial"
                assert fallback_status["warnings"] == ["llm:http_error"]
                assert model_state["calls"] == 2
                summary = {
                    "status": "passed",
                    "mode": "offline",
                    "checks": [
                        "CLI initialization",
                        "HTTP submission",
                        "API restart persistence",
                        "separate worker",
                        "stable results",
                        "idempotency",
                        "feedback",
                        "deletion",
                        "cancellation",
                        "offline setup diagnostics",
                        "LLM default over real loopback HTTP with synthetic fixture",
                        "candidate-only reranking before truncation",
                        "model pipeline-bound feedback and lexical fallback",
                        "server process and temporary-file cleanup",
                    ],
                    "result_count": len(results),
                }
            finally:
                stop_server(server)
    print(json.dumps(summary, indent=2))


if __name__ == "__main__":
    main()
