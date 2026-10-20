"""ANV-022: real Compose install/restart/model-connectivity smoke; no paid APIs.

Requires Docker Compose v2. Uses an isolated project, generated temporary keys,
synthetic corpus and protocol fixture. Never prints the captured key or payloads.
"""

import json
import os
import socket
import subprocess
import sys
import tempfile
import time
import uuid
from pathlib import Path
from urllib.error import HTTPError, URLError
from urllib.request import ProxyHandler, Request, build_opener

ROOT = Path(__file__).resolve().parents[1]


def main():
    project = "anvesha-smoke-" + uuid.uuid4().hex[:12]
    with socket.socket() as listener:
        listener.bind(("127.0.0.1", 0))
        port = listener.getsockname()[1]
    environment = {**os.environ, "ANVESHA_PORT": str(port)}
    with tempfile.TemporaryDirectory(prefix="anvesha-compose-") as temporary:
        override = Path(temporary) / "fixture.json"
        override.write_text(
            json.dumps(
                {
                    "services": {
                        "setup": {"environment": {"ANVESHA_LLM_TIMEOUT_SECONDS": "3"}},
                        "model-fixture": {
                            "image": "anvesha-local:dev",
                            "entrypoint": ["python", "/fixture.py"],
                            "read_only": True,
                            "cap_drop": ["ALL"],
                            "security_opt": ["no-new-privileges:true"],
                            "volumes": [
                                {
                                    "type": "bind",
                                    "source": str(ROOT / "scripts/container_model_fixture.py"),
                                    "target": "/fixture.py",
                                    "read_only": True,
                                }
                            ],
                            "networks": {"default": {"aliases": ["ollama"]}},
                        },
                    }
                }
            ),
            encoding="utf-8",
        )
        base = [
            "docker",
            "compose",
            "--project-name",
            project,
            "-f",
            str(ROOT / "compose.yaml"),
            "-f",
            str(override),
        ]

        def compose(*args, timeout=180):
            result = subprocess.run(
                [*base, *args],
                cwd=ROOT,
                env=environment,
                capture_output=True,
                text=True,
                timeout=timeout,
            )
            if result.returncode:
                # The allowlisted build context has no runtime data or credentials.
                # Keep service output private, including the explicit show-key command.
                if args[0] == "build":
                    print(result.stderr[-5000:], file=sys.stderr)
                raise RuntimeError(f"Compose {args[0]} failed with exit {result.returncode}")
            return result.stdout.strip()

        opener = build_opener(ProxyHandler({}))
        key = ""

        def request(path, body=None):
            req = Request(
                f"http://127.0.0.1:{port}{path}",
                data=json.dumps(body).encode() if body is not None else None,
                headers={"X-API-Key": key, "Content-Type": "application/json"},
            )
            with opener.open(req, timeout=5) as response:
                return json.load(response)

        def wait_for(path, predicate, seconds=45):
            deadline = time.monotonic() + seconds
            while time.monotonic() < deadline:
                try:
                    value = request(path)
                    if predicate(value):
                        return value
                except (URLError, HTTPError, TimeoutError, OSError):
                    pass
                time.sleep(0.25)
            raise RuntimeError("Container HTTP readiness or completion timed out")

        try:
            compose("build", "api", timeout=600)
            compose(
                "run",
                "--rm",
                "setup",
                "setup",
                "--model",
                "synthetic-ci-fixture",
                "--model-url",
                "http://ollama:11434/v1",
                "--allow-model-network",
                "--seed-demo",
            )
            key = compose("run", "--rm", "setup", "show-key")
            assert 24 <= len(key) <= 256 and "\n" not in key
            runtime = json.loads(
                compose("run", "--rm", "setup", "doctor", "--config", "/data/server.json")
            )["sqlite_runtime"]
            assert runtime["sqlite_version"] == "3.53.1" and runtime["supported"]
            print("Container runtime: " + json.dumps(runtime, sort_keys=True))
            compose("up", "-d", "model-fixture", "api", "worker")
            wait_for("/healthz", lambda value: value["status"] == "ok")
            caps = request("/v1/capabilities")
            assert caps["llm_configured"] and caps["default_ranking"] == "llm"
            assert compose("exec", "-T", "api", "id", "-u") == "10001"
            active = json.loads(
                compose("exec", "-T", "api", "anvesha", "doctor", "--config", "/data/server.json")
            )
            assert active["sqlite_runtime"] == runtime and active["ready"]
            with opener.open(f"http://127.0.0.1:{port}/", timeout=5) as response:
                assert b"/assets/app.js" in response.read()
            job = request("/v1/searches", {"query": "Anvesha"})
            location = "/v1/searches/" + job["id"]
            assert job["ranking"] == "llm"
            wait_for(location, lambda value: value["state"] == "completed")
            results = request(location + "/results")
            assert results["total"] == 3
            assert results["results"][0]["ranking_method"] == "llm_rerank"
            receipt = request(location + "/feedback", {"version": 1, "rating": 1})
            assert not receipt["learning_opt_in"]
            compose("stop", "worker")
            pending = request("/v1/searches", {"query": "Anvesha"})
            assert pending["state"] == "queued"
            compose("restart", "api")
            wait_for("/healthz", lambda value: value["status"] == "ok")
            assert request("/v1/searches/" + pending["id"])["state"] == "queued"
            assert request(location + "/results")["results"] == results["results"]
            compose("start", "worker")
            wait_for("/v1/searches/" + pending["id"], lambda value: value["state"] == "completed")
            compose("stop", "model-fixture")
            fallback = request("/v1/searches", {"query": "Anvesha"})
            status = wait_for(
                "/v1/searches/" + fallback["id"],
                lambda value: value["state"] == "completed_partial",
            )
            assert any(value.startswith("llm:") for value in status["warnings"])
        finally:
            compose("down", "--volumes", "--remove-orphans")
    print(
        "Container smoke passed: non-root, private model network, LLM default, "
        "durable restart, feedback, visible fallback, scoped cleanup."
    )


if __name__ == "__main__":
    main()
