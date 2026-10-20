"""ANV-026: actual offline API/worker restart and retention, synthetic data only."""

import json
import os
import socket
import sqlite3
import subprocess
import sys
import tempfile
import time
from contextlib import closing
from pathlib import Path

import httpx
from smoke_mvp import stop_server

from anvesha.runtime import load_settings

ROOT = Path(__file__).resolve().parents[1]


def main():
    with tempfile.TemporaryDirectory(prefix="anvesha-retention-") as temporary:
        directory = Path(temporary).resolve()
        assert directory.parent == Path(tempfile.gettempdir()).resolve()
        assert directory.name.startswith("anvesha-retention-")
        config, database = directory / "server.json", directory / "synthetic.db"
        env = {k: v for k, v in os.environ.items() if not k.startswith("ANVESHA_")}
        # Worker policy differs deliberately: recorded deadlines must remain binding.
        env.update(ANVESHA_DB_PATH=str(database), ANVESHA_RETENTION_SECONDS="0")
        flags = subprocess.CREATE_NO_WINDOW if os.name == "nt" else 0

        def run(module, *args):
            result = subprocess.run(
                [sys.executable, "-m", module, *args],
                cwd=ROOT,
                env=env,
                capture_output=True,
                timeout=30,
                creationflags=flags,
            )
            assert result.returncode == 0, "Synthetic retention subprocess failed"
            return result.stdout

        run(
            "anvesha.cli",
            "--db",
            str(database),
            "setup",
            "--config",
            str(config),
            "--lexical-only",
            "--seed-demo",
            "--retention-seconds",
            "8",
        )
        settings = load_settings(config)
        assert settings.retention_seconds == 8
        key = settings.api_keys[0]
        with socket.socket() as listener:
            listener.bind(("127.0.0.1", 0))
            port = listener.getsockname()[1]
        process = None

        def counts():
            with closing(sqlite3.connect(database)) as db:
                return {
                    name: db.execute(f"SELECT count(*) FROM {name}").fetchone()[0]
                    for name in ("jobs", "snapshots", "feedback", "documents")
                }

        with (
            (directory / "api.log").open("w", encoding="utf-8") as log,
            httpx.Client(
                base_url=f"http://127.0.0.1:{port}",
                headers={"X-API-Key": key},
                timeout=3,
                trust_env=False,
            ) as client,
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
                deadline = time.monotonic() + 20
                try:
                    while time.monotonic() < deadline:
                        assert child.poll() is None, "Synthetic retention API exited"
                        try:
                            if client.get("/healthz").status_code == 200:
                                return child
                        except httpx.TransportError:
                            pass
                        time.sleep(0.1)
                    raise AssertionError("Synthetic retention API did not start")
                except BaseException:
                    stop_server(child)
                    raise

            try:
                process = start()
                assert client.get("/v1/capabilities").json()["retention_seconds"] == 8
                body = {"query": "Anvesha demonstration", "ranking": "lexical"}
                headers = {"Idempotency-Key": "synthetic-retention"}
                response = client.post("/v1/searches", json=body, headers=headers)
                assert response.status_code == 202
                job = response.json()
                assert job["expires_at"] == job["created_at"] + 8
                location = response.headers["location"]
                run("anvesha.worker", "--once")
                assert client.get(location).json()["state"] == "completed"
                assert client.get(location + "/results").json()["expires_at"] == job["expires_at"]
                assert (
                    client.post(
                        location + "/feedback", json={"version": 1, "rating": 1}
                    ).status_code
                    == 200
                )
                etag = client.get(location).headers["etag"]
                queued = client.post("/v1/searches", json=body).json()
                assert queued["state"] == "queued"
                stop_server(process)
                process = None
                deadline = time.monotonic() + 15
                expires = max(job["expires_at"], queued["expires_at"])
                while time.time() < expires:
                    assert time.monotonic() < deadline, "Synthetic expiry wait exceeded budget"
                    time.sleep(0.1)
                assert counts() == {"jobs": 2, "snapshots": 1, "feedback": 1, "documents": 3}
                preview = json.loads(run("anvesha.cli", "prune", "--config", str(config)))
                assert preview["eligible_jobs"] == 2 and preview["deleted_jobs"] == 0
                assert counts()["jobs"] == 2
                process = start()  # API restart must not reset or physically prune deadlines.
                for path in (location, f"/v1/searches/{queued['id']}"):
                    assert client.get(path, headers={"If-None-Match": etag}).status_code == 404
                    assert client.get(path + "/results").status_code == 404
                    assert (
                        client.post(
                            path + "/feedback", json={"version": 1, "rating": 1}
                        ).status_code
                        == 404
                    )
                    assert client.post(path + "/cancel").status_code == 404
                    assert client.delete(path).status_code == 404
                assert counts()["jobs"] == 2  # Worker has remained stopped since acceptance.
                run("anvesha.worker", "--once")
                assert counts() == {"jobs": 0, "snapshots": 0, "feedback": 0, "documents": 3}
                new = client.post("/v1/searches", json=body, headers=headers)
                assert new.status_code == 202 and new.json()["id"] != job["id"]
                assert new.json()["expires_at"] == new.json()["created_at"] + 8
                applied = json.loads(
                    run("anvesha.cli", "prune", "--config", str(config), "--apply")
                )
                assert applied["apply"] is True and applied["deleted_jobs"] == 0
            finally:
                stop_server(process)
        assert key not in (directory / "api.log").read_text(encoding="utf-8")
    print(
        json.dumps(
            {
                "status": "passed",
                "mode": "offline synthetic retention",
                "checks": [
                    "saved deadline",
                    "separate worker",
                    "restart without renewal",
                    "expired 404 before cleanup",
                    "ETag expiry",
                    "read-only prune preview",
                    "idle-worker cascade",
                    "client-scoped key reuse",
                    "explicit apply",
                    "corpus preservation",
                    "owned-process cleanup",
                ],
            },
            indent=2,
        )
    )


if __name__ == "__main__":
    main()
