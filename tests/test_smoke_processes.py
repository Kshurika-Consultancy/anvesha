"""ANV-018: Windows cleanup must release descendant-inherited log handles."""

import ctypes
import importlib.util
import subprocess
import sys
import time
from pathlib import Path

import pytest

SCRIPT = Path(__file__).resolve().parents[1] / "scripts/smoke_mvp.py"
SPEC = importlib.util.spec_from_file_location("smoke_mvp", SCRIPT)
smoke = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(smoke)


def test_stop_empty_or_completed_process():
    smoke.stop_server(None)
    ended = subprocess.Popen([sys.executable, "-c", "pass"])
    ended.wait(timeout=10)
    smoke.stop_server(ended)


@pytest.mark.skipif(sys.platform != "win32", reason="Windows inherited-handle regression")
def test_windows_shutdown_releases_child_log_handle_and_process(tmp_path):
    log_path = tmp_path / "server.log"
    child_ready = tmp_path / "child.pid"
    child_code = (
        "import os,sys,time; from pathlib import Path; "
        "Path(sys.argv[1]).write_text(str(os.getpid())); time.sleep(60)"
    )
    parent_code = (
        "import subprocess,sys,time; "
        "subprocess.Popen([sys.executable,'-c',sys.argv[2],sys.argv[1]]); time.sleep(60)"
    )
    with log_path.open("w", encoding="utf-8") as log:
        process = subprocess.Popen(
            [sys.executable, "-c", parent_code, str(child_ready), child_code],
            stdout=log,
            stderr=log,
            creationflags=subprocess.CREATE_NO_WINDOW,
        )
    child_pid = None
    handle = None
    kernel = None
    try:
        deadline = time.monotonic() + 10
        while time.monotonic() < deadline:
            try:
                child_pid = int(child_ready.read_text())
                break
            except (OSError, ValueError):
                pass
            time.sleep(0.05)
        assert child_pid is not None, "Child process did not start"
        # Wait on the real child, rather than trusting only the launcher status.
        kernel = ctypes.WinDLL("kernel32", use_last_error=True)
        kernel.OpenProcess.argtypes = [ctypes.c_uint32, ctypes.c_int, ctypes.c_uint32]
        kernel.OpenProcess.restype = ctypes.c_void_p
        kernel.WaitForSingleObject.argtypes = [ctypes.c_void_p, ctypes.c_uint32]
        kernel.WaitForSingleObject.restype = ctypes.c_uint32
        kernel.CloseHandle.argtypes = [ctypes.c_void_p]
        handle = kernel.OpenProcess(0x00100000, False, child_pid)
        assert handle, "Could not observe the actual child"
        smoke.stop_server(process)
        assert kernel.WaitForSingleObject(handle, 5000) == 0, "API descendant still running"
        log_path.unlink()  # WinError 32 reproduced here when a child still holds the log.
        assert not log_path.exists()
    finally:
        try:
            smoke.stop_server(process)
        finally:
            if handle:
                try:
                    if kernel.WaitForSingleObject(handle, 0) == 258:
                        subprocess.run(
                            ["taskkill", "/PID", str(child_pid), "/T", "/F"],
                            stdout=subprocess.DEVNULL,
                            stderr=subprocess.DEVNULL,
                            creationflags=subprocess.CREATE_NO_WINDOW,
                            check=False,
                            timeout=10,
                        )
                finally:
                    kernel.CloseHandle(handle)
