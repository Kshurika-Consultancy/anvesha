"""ANV-004: local setup, reviewed ingestion, and invalid input handling."""

import json

import pytest

from anvesha.cli import DEMO_DOCUMENTS, main
from anvesha.config import Settings
from anvesha.store import Store


def test_init_seed_and_restart(tmp_path, capsys):
    path = tmp_path / "local.db"
    assert main(["--db", str(path), "init", "--seed"]) == 0
    output = capsys.readouterr().out
    assert "synthetic demo" in output
    store = Store(path)
    assert len(store.search_local("Anvesha")) == 3
    assert main(["--db", str(path), "init"]) == 0
    assert len(store.search_local("Anvesha")) == 3


def test_import_validated_before_writes(tmp_path, capsys):
    path = tmp_path / "test.db"
    source = tmp_path / "documents.json"
    source.write_text(json.dumps([DEMO_DOCUMENTS[0], {"id": "bad"}]), encoding="utf-8")
    with pytest.raises(SystemExit) as error:
        main(["--db", str(path), "ingest", str(source), "--rights-reviewed"])
    assert error.value.code == 2
    assert not path.exists()
    assert "Each document needs" in capsys.readouterr().err
    source.write_text(json.dumps([DEMO_DOCUMENTS[0]]), encoding="utf-8")
    assert main(["--db", str(path), "ingest", str(source), "--rights-reviewed"]) == 0
    assert len(Store(path).search_local("asynchronous")) == 1


def test_import_requires_explicit_operator_rights_attestation(tmp_path):
    with pytest.raises(SystemExit) as error:
        main(["ingest", str(tmp_path / "documents.json")])
    assert error.value.code == 2


@pytest.mark.parametrize(
    "url", ["file:///secret", "javascript:alert(1)", "https://x:999999/a", "https://a b/x"]
)
def test_import_rejects_unusable_result_urls(tmp_path, url):
    source = tmp_path / "documents.json"
    source.write_text(json.dumps([{**DEMO_DOCUMENTS[0], "url": url}]), encoding="utf-8")
    with pytest.raises(SystemExit):
        main(["--db", str(tmp_path / "test.db"), "ingest", str(source), "--rights-reviewed"])


@pytest.mark.parametrize(
    "kwargs",
    [
        {"api_keys": ("short",)},
        {"api_keys": (" " * 30,)},
        {"enabled_sources": ("unknown",)},
        {"worker_poll_seconds": 0},
        {"worker_poll_seconds": float("nan")},
    ],
)
def test_invalid_configuration_fails_early(kwargs):
    with pytest.raises(ValueError):
        Settings(**kwargs)


def test_environment_configuration(monkeypatch, tmp_path):
    monkeypatch.setenv("ANVESHA_DB_PATH", str(tmp_path / "different.db"))
    monkeypatch.setenv("ANVESHA_API_KEYS", "a" * 32 + "," + "b" * 32)
    monkeypatch.setenv("ANVESHA_ENABLED_SOURCES", "local,wikidata,local")
    settings = Settings.from_env()
    assert settings.database_path.name == "different.db"
    assert len(settings.api_keys) == 2
    assert settings.enabled_sources == ("local", "wikidata")
