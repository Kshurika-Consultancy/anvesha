"""ANV-022: private native setup and supervision of separate API/worker processes."""

import json
import os
import secrets
import signal
import subprocess
import sys
import time
from dataclasses import asdict
from pathlib import Path

from anvesha.config import Settings
from anvesha.llm import LLMConfig
from anvesha.retention import DEFAULT_SECONDS
from anvesha.store import Store


def setup(path, database, llm, *, demo=False, retention_seconds=DEFAULT_SECONDS):
    path = Path(path).expanduser().resolve()
    database = Path(database).expanduser().resolve()
    if path.exists():
        raise ValueError("Configuration already exists; refusing to overwrite credentials")
    if path == database:
        raise ValueError("Configuration and database must be different files")
    settings = Settings(
        database_path=database,
        api_keys=(secrets.token_urlsafe(32),),
        llm=llm,
        retention_seconds=retention_seconds,
    )
    model = asdict(llm)
    model.pop("endpoint_scope")
    data = {
        "schema_version": 1,
        "database_path": str(database),
        "api_keys": list(settings.api_keys),
        "enabled_sources": list(settings.enabled_sources),
        "worker_poll_seconds": settings.worker_poll_seconds,
        "retention_seconds": settings.retention_seconds,
        "llm": model,
    }
    store = Store(database)
    store.initialize()
    if demo:
        from anvesha.cli import DEMO_DOCUMENTS

        for document in DEMO_DOCUMENTS:
            store.upsert_document(document)
    path.parent.mkdir(parents=True, exist_ok=True)
    descriptor = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
    with os.fdopen(descriptor, "w", encoding="utf-8", newline="\n") as output:
        json.dump(data, output, indent=2)
        output.write("\n")
    return settings


def load_settings(path):
    try:
        path = Path(path).expanduser().resolve()
        with path.open("rb") as source:
            raw = source.read(65537)
        if len(raw) > 65536:
            raise ValueError
        data = json.loads(raw)
        expected = {
            "schema_version",
            "database_path",
            "api_keys",
            "enabled_sources",
            "worker_poll_seconds",
            "llm",
        }
        if (
            not isinstance(data, dict)
            or set(data) - {"retention_seconds"} != expected
            or data["schema_version"] != 1
        ):
            raise ValueError
        if (
            not isinstance(data["api_keys"], list)
            or not data["api_keys"]
            or any(not isinstance(key, str) for key in data["api_keys"])
            or not isinstance(data["enabled_sources"], list)
            or any(not isinstance(item, str) for item in data["enabled_sources"])
            or type(data["worker_poll_seconds"]) not in {int, float}
            or not isinstance(data["database_path"], str)
        ):
            raise ValueError
        database = Path(data["database_path"])
        if not database.is_absolute():
            raise ValueError
        return Settings(
            database_path=database,
            api_keys=tuple(data["api_keys"]),
            enabled_sources=tuple(data["enabled_sources"]),
            worker_poll_seconds=data["worker_poll_seconds"],
            llm=LLMConfig(**data["llm"]),
            # ANV-026: missing saved policy preserves legacy indefinite retention.
            retention_seconds=data.get("retention_seconds", 0),
        )
    except (OSError, ValueError, TypeError, KeyError):
        raise ValueError(
            "Invalid private configuration; run setup or check the file locally"
        ) from None


def stop_process(process):
    if process.poll() is not None:
        return
    if os.name == "nt":
        result = subprocess.run(
            ["taskkill", "/PID", str(process.pid), "/T", "/F"],
            capture_output=True,
            timeout=10,
            creationflags=subprocess.CREATE_NO_WINDOW,
        )
        if result.returncode and process.poll() is None:
            raise RuntimeError("Could not stop an owned service process")
    else:
        try:
            os.killpg(process.pid, signal.SIGTERM)
        except ProcessLookupError:
            pass
    try:
        process.wait(timeout=10)
    except subprocess.TimeoutExpired:
        if os.name != "nt":
            try:
                os.killpg(process.pid, signal.SIGKILL)
            except ProcessLookupError:
                pass
        else:
            process.kill()
        process.wait(timeout=5)


def start(path, host, port):
    load_settings(path)  # Fail before starting either child; never log its secrets.
    children = []
    previous = signal.getsignal(signal.SIGTERM)

    def shutdown(signum, frame):
        raise KeyboardInterrupt

    signal.signal(signal.SIGTERM, shutdown)
    try:
        for component in ("run-api", "run-worker"):
            command = [sys.executable, "-m", "anvesha.cli", component, "--config", str(path)]
            if component == "run-api":
                command.extend(["--host", host, "--port", str(port)])
            children.append(
                subprocess.Popen(
                    command,
                    creationflags=subprocess.CREATE_NO_WINDOW if os.name == "nt" else 0,
                    start_new_session=os.name != "nt",
                )
            )
        print(f"Anvesha browser: http://{host}:{port}/", flush=True)
        print(f"API PID {children[0].pid}; worker PID {children[1].pid}", flush=True)
        print("API and worker are separate processes. Press Ctrl+C to stop both.", flush=True)
        while all(process.poll() is None for process in children):
            time.sleep(0.25)
        return 1
    except KeyboardInterrupt:
        return 0
    finally:
        signal.signal(signal.SIGTERM, previous)
        for process in reversed(children):
            stop_process(process)
