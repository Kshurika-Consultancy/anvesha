"""ANV-023: explicit pinned Windows CPU server; no downloads, tools or cloud route.

For a different runtime/hardware profile, use a separately versioned experiment.
"""

import argparse
import hashlib
import json
import os
import subprocess
import time
import zipfile
from contextlib import suppress
from pathlib import Path

import httpx
from prepare_local_llm import MANIFEST, ROOT, file_digest

from anvesha.eval_data import json_bytes
from anvesha.runtime import stop_process


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--serve", action="store_true", required=True)
    parser.add_argument("--workspace", type=Path, default=ROOT / ".anvesha/local-llm/anv023")
    args = parser.parse_args()
    if os.name != "nt":
        parser.error(
            "This pinned runtime profile is Windows CPU; supply your own runtime on other hosts"
        )
    workspace = args.workspace.resolve()
    policy = json.loads(MANIFEST.read_bytes())
    for name, artifact in (("runtime.zip", "runtime"), ("model.gguf", "model")):
        if file_digest(workspace / name) != policy[artifact]["sha256"]:
            raise ValueError("Artifact checksum mismatch; nothing started")
    runtime = workspace / "runtime"
    with zipfile.ZipFile(workspace / "runtime.zip") as archive:
        expected = {item.filename for item in archive.infolist() if not item.is_dir()}
        actual = {
            path.relative_to(runtime).as_posix() for path in runtime.rglob("*") if path.is_file()
        }
        if expected != actual:
            raise ValueError("Runtime directory differs from the verified archive")
        for name in sorted(expected):
            with archive.open(name) as stream:
                checksum = hashlib.file_digest(stream, "sha256").hexdigest()
            if file_digest(runtime / name) != checksum:
                raise ValueError("Extracted runtime file differs from verified archive")
    hardware_script = """
$pilotCpu = Get-CimInstance Win32_Processor | Select-Object -First 1
$pilotMemory = Get-CimInstance Win32_ComputerSystem
@{cpu_model=$pilotCpu.Name;physical_cores=[int]$pilotCpu.NumberOfCores;
logical_processors=[int]$pilotCpu.NumberOfLogicalProcessors;
memory_bytes=[long]$pilotMemory.TotalPhysicalMemory} | ConvertTo-Json -Compress
"""
    hardware = json.loads(
        subprocess.check_output(
            ["powershell.exe", "-NoProfile", "-NonInteractive", "-Command", hardware_script],
            creationflags=subprocess.CREATE_NO_WINDOW,
        )
    )
    executable = runtime / "llama-server.exe"
    version = subprocess.check_output(
        [str(executable), "--version"],
        stderr=subprocess.STDOUT,
        text=True,
        creationflags=subprocess.CREATE_NO_WINDOW,
    )
    backend = {
        **hardware,
        "runtime": "llama.cpp",
        "runtime_version": version.splitlines()[0],
        "runtime_commit": policy["runtime"]["commit"],
        "runtime_archive_sha256": policy["runtime"]["sha256"],
        "server_sha256": file_digest(executable),
        "model_sha256": policy["model"]["sha256"],
        "model_alias": policy["model"]["alias"],
        "threads": 6,
        "context_tokens": 8192,
        "gpu_layers": 0,
        "offline": True,
        "tools_enabled": False,
        "webui": False,
        "seed": 20261018,
    }
    command = [
        str(executable),
        "--model",
        str(workspace / "model.gguf"),
        "--alias",
        policy["model"]["alias"],
        "--host",
        "127.0.0.1",
        "--port",
        "8135",
        "--threads",
        "6",
        "--threads-batch",
        "6",
        "--ctx-size",
        "8192",
        "--parallel",
        "1",
        "--batch-size",
        "512",
        "--gpu-layers",
        "0",
        "--seed",
        "20261018",
        "--prio",
        "-1",
        "--poll",
        "0",
        "--offline",
        "--no-webui",
        "--no-ui-mcp-proxy",
        "--no-context-shift",
        "--log-disable",
    ]
    # Ignore model/runtime/proxy overrides inherited from unrelated local projects.
    environment = {
        key: value
        for key, value in os.environ.items()
        if not key.startswith(("LLAMA_", "ANVESHA_", "OLLAMA_"))
        and key.upper() not in {"HTTP_PROXY", "HTTPS_PROXY", "ALL_PROXY"}
    }
    with (workspace / "server.log").open("wb") as log:
        process = subprocess.Popen(
            command,
            cwd=workspace,
            env=environment,
            stdout=log,
            stderr=log,
            creationflags=subprocess.CREATE_NO_WINDOW,
        )
        try:
            with httpx.Client(trust_env=False, follow_redirects=False, timeout=2) as client:
                deadline = time.monotonic() + 90
                while time.monotonic() < deadline:
                    if process.poll() is not None:
                        raise ValueError(
                            "Pinned runtime exited before readiness; inspect local log"
                        )
                    try:
                        if client.get("http://127.0.0.1:8135/health").status_code == 200:
                            break
                    except httpx.TransportError:
                        pass
                    time.sleep(0.25)
                else:
                    raise ValueError("Pinned runtime startup exceeded budget")
            (workspace / "backend-info.json").write_bytes(json_bytes(backend))
            (workspace / "owned-process.json").write_bytes(json_bytes({"pid": process.pid}))
            print(
                f"Local CPU model ready on loopback port 8135; owned PID {process.pid}", flush=True
            )
            while process.poll() is None:
                time.sleep(0.25)
        except KeyboardInterrupt:
            pass
        finally:
            stop_process(process)
            # ANV-023: a completed run must not leave an apparently owned live PID.
            with suppress(OSError, ValueError):
                owned = workspace / "owned-process.json"
                if json.loads(owned.read_bytes()) == {"pid": process.pid}:
                    owned.unlink()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
