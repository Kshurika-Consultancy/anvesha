"""ANV-022: native setup/start/restart and owned-process cleanup; offline fixture."""

import json
import os
import re
import signal
import socket
import subprocess
import sys
import tempfile
import time
from pathlib import Path

import httpx
from smoke_mvp import model_stub

from anvesha.runtime import load_settings, stop_process

ROOT = Path(__file__).resolve().parents[1]


def main():
    with tempfile.TemporaryDirectory(prefix="anvesha-native-") as temporary, model_stub() as model:
        directory = Path(temporary)
        endpoint, model_state = model
        config = directory / "server.json"
        environment = {
            key: value for key, value in os.environ.items() if not key.startswith("ANVESHA_")
        }
        environment.update(ANVESHA_LLM_API_KEY=model_state["key"])
        flags = subprocess.CREATE_NO_WINDOW if os.name == "nt" else 0
        setup = subprocess.run(
            [
                sys.executable,
                "-m",
                "anvesha.cli",
                "--db",
                str(directory / "db"),
                "setup",
                "--config",
                str(config),
                "--model",
                "synthetic-smoke-model",
                "--model-url",
                endpoint,
                "--seed-demo",
            ],
            cwd=ROOT,
            env=environment,
            capture_output=True,
            timeout=20,
            creationflags=flags,
        )
        assert setup.returncode == 0, "Native setup failed"
        key = load_settings(config).api_keys[0]
        assert key.encode() not in setup.stdout
        with socket.socket() as listener:
            listener.bind(("127.0.0.1", 0))
            port = listener.getsockname()[1]
        process = None
        with (
            (directory / "services.log").open("w", encoding="utf-8") as log,
            httpx.Client(
                base_url=f"http://127.0.0.1:{port}",
                headers={"X-API-Key": key},
                timeout=3,
                trust_env=False,
            ) as client,
        ):

            def wait_for(path, predicate):
                deadline = time.monotonic() + 20
                while time.monotonic() < deadline:
                    if process.poll() is not None:
                        raise RuntimeError("Native services exited before readiness")
                    try:
                        value = client.get(path).json()
                        if predicate(value):
                            return value
                    except (httpx.TransportError, ValueError):
                        pass
                    time.sleep(0.1)
                raise RuntimeError("Native readiness or completion timed out")

            def start():
                return subprocess.Popen(
                    [
                        sys.executable,
                        "-m",
                        "anvesha.cli",
                        "start",
                        "--config",
                        str(config),
                        "--port",
                        str(port),
                    ],
                    cwd=ROOT,
                    env=environment,
                    stdout=log,
                    stderr=log,
                    creationflags=flags,
                    start_new_session=os.name != "nt",
                )

            def stop_owned_api():
                text = (directory / "services.log").read_text(encoding="utf-8")
                api_pid = int(re.findall(r"API PID (\d+); worker PID \d+", text)[-1])
                if os.name == "nt":
                    subprocess.run(
                        ["taskkill", "/PID", str(api_pid), "/T", "/F"],
                        capture_output=True,
                        timeout=10,
                        creationflags=flags,
                        check=True,
                    )
                else:
                    os.kill(api_pid, signal.SIGTERM)
                assert process.wait(timeout=20) == 1

            try:
                process = start()
                wait_for("/healthz", lambda value: value["status"] == "ok")
                assert client.get("/").status_code == 200
                assert client.get("/assets/app.js").status_code == 200
                job = client.post("/v1/searches", json={"query": "Anvesha"}).json()
                location = "/v1/searches/" + job["id"]
                assert job["ranking"] == "llm"
                wait_for(location, lambda value: value["state"] == "completed")
                results = client.get(location + "/results").json()
                assert results["total"] == 3
                assert results["results"][0]["ranking_method"] == "llm_rerank"
                stop_owned_api()  # Child exit must shut down the sibling worker too.
                process = start()
                wait_for("/healthz", lambda value: value["status"] == "ok")
                assert client.get(location + "/results").json() == results
                if os.name == "nt":
                    stop_owned_api()
                else:
                    process.send_signal(signal.SIGTERM)
                    assert process.wait(timeout=20) == 0
                try:
                    client.get("/healthz")
                except httpx.TransportError:
                    pass
                else:
                    raise AssertionError("Native API remains after shutdown")
            finally:
                if process is not None:
                    stop_process(process)
        text = (directory / "services.log").read_text(encoding="utf-8")
        assert key not in text and model_state["key"] not in text
    print(
        json.dumps(
            {
                "status": "passed",
                "mode": "offline native self-hosting",
                "checks": [
                    "private setup",
                    "LLM default",
                    "packaged browser assets",
                    "separate supervised API/worker",
                    "restart persistence",
                    "child-exit cleanup",
                    "secret-free service output",
                ],
            },
            indent=2,
        )
    )


if __name__ == "__main__":
    main()
