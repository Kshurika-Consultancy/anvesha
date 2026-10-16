"""ANV-006: real HTTP/API restart/worker-process smoke test, entirely offline."""

import json
import os
import secrets
import socket
import subprocess
import sys
import tempfile
import time
from pathlib import Path

import httpx

ROOT = Path(__file__).resolve().parents[1]


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
    with tempfile.TemporaryDirectory(prefix="anvesha-smoke-") as temporary:
        directory = Path(temporary)
        environment = {
            key: value for key, value in os.environ.items() if not key.startswith("ANVESHA_")
        }
        environment.update(
            ANVESHA_DB_PATH=str(directory / "smoke.db"),
            ANVESHA_API_KEYS=secrets.token_urlsafe(32),
            ANVESHA_ENABLED_SOURCES="local",
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
                request = {"query": "free local search", "sources": ["local"], "limit": 10}
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
                        "server process and temporary-file cleanup",
                    ],
                    "result_count": len(results),
                }
            finally:
                stop_server(server)
    print(json.dumps(summary, indent=2))


if __name__ == "__main__":
    main()
