"""ANV-027: release evidence boundaries and unsupported runtime failure paths."""

import hashlib
import json
import sqlite3

import pytest
from fastapi.testclient import TestClient

from anvesha import cli, runtime, sqlite_runtime
from anvesha.api import create_app
from anvesha.config import Settings
from anvesha.llm import LLMConfig
from anvesha.store import Store
from anvesha.worker import main as worker_main


@pytest.mark.parametrize(
    ("version", "fixed"),
    [
        ("3.44.5", False),
        ("3.44.6", True),
        ("3.44.7", True),
        ("3.45.7", False),
        ("3.49.9", False),
        ("3.50.4", False),
        ("3.50.6", False),
        ("3.50.7", True),
        ("3.50.8", True),
        ("3.51.0", False),
        ("3.51.2", False),
        ("3.51.3", True),
        ("3.52.0", True),
        ("3.53.1", True),
        ("3.9.99", False),
        ("3.51.3-vendor", False),
        ("3.51", False),
        ("3.51.3.0", False),
        ("3.51.-3", False),
        ("3.51.３", False),
        ("unverified", False),
    ],
)
def test_upstream_fix_does_not_misclassify_adjacent_backport_branches(version, fixed):
    assert sqlite_runtime.upstream_wal_fix(version) is fixed


def unsupported(monkeypatch):
    report = {
        **sqlite_runtime.inspect_runtime(),
        "sqlite_version": "3.50.4",
        "wal_reset_fix": "unverified",
        "supported": False,
    }
    monkeypatch.setattr(sqlite_runtime, "inspect_runtime", lambda: report)
    monkeypatch.setattr(cli, "inspect_runtime", lambda: report)


def test_actual_runtime_reports_loaded_library_not_python_patch_assumptions():
    report = sqlite_runtime.inspect_runtime()
    assert report["sqlite_version"] == sqlite3.sqlite_version
    assert report["supported"] and report["fts5_available"]
    assert report["sqlite_source_id"]
    assert "not_binary_attestation_or_race_test" in report["evidence_basis"]


def test_fts5_probe_failure_is_closed_and_does_not_open_disk(monkeypatch):
    class Probe:
        closed = False

        def execute(self, sql):
            if sql.startswith("SELECT"):
                return self
            raise sqlite3.OperationalError("synthetic FTS5 unavailable")

        def fetchone(self):
            return "3.53.1", "synthetic-source"

        def close(self):
            self.closed = True

    probe = Probe()

    def connect(path):
        assert path == ":memory:"
        return probe

    monkeypatch.setattr(sqlite_runtime.sqlite3, "connect", connect)
    sqlite_runtime.inspect_runtime.cache_clear()
    try:
        report = sqlite_runtime.inspect_runtime()
        assert report["wal_reset_fix"] == "upstream_fixed_release"
        assert not report["supported"] and not report["fts5_available"]
        assert probe.closed
        with pytest.raises(ValueError, match="FTS5 available: False"):
            sqlite_runtime.require_runtime()
    finally:
        sqlite_runtime.inspect_runtime.cache_clear()


@pytest.mark.parametrize("entry", ["setup", "api", "worker", "initialize"])
def test_unsupported_runtime_refuses_before_new_database_or_credentials(
    tmp_path, monkeypatch, entry
):
    unsupported(monkeypatch)
    path = tmp_path / "not-created" / "private.db"
    config = tmp_path / "private.json"
    settings = Settings(database_path=path, api_keys=("synthetic-client-" + "a" * 32,))
    with pytest.raises(ValueError, match="WAL-reset fix: unverified"):
        if entry == "setup":
            runtime.setup(config, path, LLMConfig())
        elif entry == "api":
            with TestClient(create_app(settings)):
                pytest.fail("Unsupported API started")
        elif entry == "worker":
            worker_main(["--once"], settings=settings)
        else:
            Store(path).initialize()
    assert not path.parent.exists() and not config.exists()


def test_existing_database_access_blocked_but_doctor_remains_read_only(
    tmp_path, monkeypatch, capsys
):
    path = tmp_path / "private.db"
    store = Store(path)
    store.initialize()
    store.upsert_document(cli.DEMO_DOCUMENTS[0])
    before = hashlib.sha256(path.read_bytes()).hexdigest()
    unsupported(monkeypatch)
    monkeypatch.setenv("ANVESHA_API_KEYS", "synthetic-secret-" + "z" * 32)
    for operation in [store.document_count, lambda: store.prune_expired(apply=True)]:
        with pytest.raises(ValueError, match="Older vendor backports require"):
            operation()
    assert cli.main(["--db", str(path), "doctor"]) == 1
    output = capsys.readouterr().out
    report = json.loads(output)
    assert not report["ready"] and report["database_initialized"]
    assert report["document_count"] == 1
    assert report["sqlite_runtime"]["wal_reset_fix"] == "unverified"
    assert "synthetic-secret" not in output and "Demonstration document" not in output
    assert hashlib.sha256(path.read_bytes()).hexdigest() == before


def test_supervisor_refuses_before_spawning_children(tmp_path, monkeypatch):
    config = tmp_path / "private.json"
    runtime.setup(config, tmp_path / "data.db", LLMConfig())
    unsupported(monkeypatch)
    monkeypatch.setattr(runtime.subprocess, "Popen", lambda *a, **kw: pytest.fail("Child spawned"))
    with pytest.raises(ValueError, match="not supported"):
        runtime.start(config, "127.0.0.1", 8000)


def test_doctor_without_database_never_creates_one(tmp_path):
    path = tmp_path / "not-created" / "data.db"
    report = cli.diagnostics(Settings(database_path=path))
    assert not report["ready"] and report["sqlite_runtime"]["supported"]
    assert not path.parent.exists()
