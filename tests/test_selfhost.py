"""ANV-022: native first-run, private browser assets and LLM-default acceptance."""

import hashlib
import json
import os
import stat

import pytest
from fastapi.testclient import TestClient

from anvesha.api import create_app
from anvesha.cli import main
from anvesha.llm import LLMConfig
from anvesha.runtime import load_settings, setup
from anvesha.store import Store


def test_setup_config_survives_restart_and_refuses_overwrite(tmp_path, capsys):
    config, database = tmp_path / "private.json", tmp_path / "collection.db"
    args = [
        "--db",
        str(database),
        "setup",
        "--config",
        str(config),
        "--model",
        "already-installed",
        "--seed-demo",
    ]
    assert main(args) == 0
    settings = load_settings(config)
    assert settings.database_path == database
    assert settings.llm.model == "already-installed"
    assert settings.api_keys[0] not in capsys.readouterr().out
    if os.name != "nt":
        assert stat.S_IMODE(config.stat().st_mode) == 0o600
    original = config.read_bytes()
    with pytest.raises(SystemExit):
        main(args)
    assert config.read_bytes() == original
    assert Store(database).document_count() == 3
    assert main(["show-key", "--config", str(config)]) == 0
    assert capsys.readouterr().out.strip() == settings.api_keys[0]
    assert main(["doctor", "--config", str(config)]) == 0
    report = json.loads(capsys.readouterr().out)
    assert report["ready"] and report["llm"]["default_ranking"] == "llm"


def test_setup_flags_validate_effective_endpoint_once(tmp_path, monkeypatch):
    monkeypatch.setenv("ANVESHA_LLM_BASE_URL", "http://ollama:11434/v1")
    config = tmp_path / "private.json"
    assert (
        main(
            [
                "--db",
                str(tmp_path / "db"),
                "setup",
                "--config",
                str(config),
                "--model",
                "local",
                "--allow-model-network",
            ]
        )
        == 0
    )
    assert load_settings(config).llm.endpoint_scope == "network"


def test_schema_output_is_saved_and_old_configuration_keeps_object_mode(tmp_path, monkeypatch):
    monkeypatch.setenv("ANVESHA_LLM_OUTPUT_FORMAT", "json_schema")
    monkeypatch.setenv("ANVESHA_LLM_STRATEGY", "pointwise")
    path = tmp_path / "private.json"
    setup(path, tmp_path / "collection.db", LLMConfig.from_env(model="local"))
    assert load_settings(path).llm.output_format == "json_schema"
    assert load_settings(path).llm.strategy == "pointwise"
    old = json.loads(path.read_bytes())
    old["llm"].pop("output_format")
    old["llm"].pop("strategy")
    path.write_text(json.dumps(old), encoding="utf-8")
    # Saved configurations take precedence over ambient environment variables.
    assert load_settings(path).llm.output_format == "json_object"
    assert load_settings(path).llm.strategy == "listwise"


@pytest.mark.parametrize(
    "field,value",
    [
        ("api_keys", [42]),
        ("api_keys", []),
        ("enabled_sources", [False]),
        ("worker_poll_seconds", "1"),
        ("database_path", "relative.db"),
        ("llm", {"api_key": "secret-value", "base_url": "invalid"}),
        ("unknown", "secret-value"),
    ],
)
def test_private_config_rejects_malformed_data_without_secret_diagnostics(tmp_path, field, value):
    path = tmp_path / "private.json"
    setup(path, tmp_path / "db", LLMConfig())
    data = json.loads(path.read_bytes())
    data[field] = value
    path.write_text(json.dumps(data), encoding="utf-8")
    with pytest.raises(ValueError, match="Invalid private configuration") as problem:
        load_settings(path)
    assert "secret-value" not in str(problem.value)


def test_default_requires_model_but_explicit_baseline_is_free(tmp_path):
    settings = setup(tmp_path / "config", tmp_path / "db", LLMConfig(), demo=True)
    with TestClient(create_app(settings), headers={"X-API-Key": settings.api_keys[0]}) as client:
        response = client.post("/v1/searches", json={"query": "Anvesha"})
        assert response.status_code == 422 and response.json()["detail"] == "llm_not_configured"
        response = client.post("/v1/searches", json={"query": "Anvesha", "ranking": "lexical"})
        assert response.status_code == 202 and response.json()["ranking"] == "lexical"
        capabilities = client.get("/v1/capabilities").json()
        assert capabilities["default_ranking"] == "llm"
        assert not capabilities["llm_configured"] and capabilities["document_count"] == 3


def test_omitted_ranking_accepts_durable_model_job(tmp_path):
    settings = setup(tmp_path / "config", tmp_path / "db", LLMConfig(model="local"))
    with TestClient(create_app(settings), headers={"X-API-Key": settings.api_keys[0]}) as client:
        job = client.post("/v1/searches", json={"query": "research"}).json()
        assert job["ranking"] == "llm"
        assert job["pipeline_version"] == settings.llm.pipeline_version
        owner = hashlib.sha256(settings.api_keys[0].encode()).hexdigest()
        assert Store(settings.database_path).get_job(owner, job["id"])["ranking"] == "llm"


def test_browser_assets_are_packaged_private_and_fixed_allowlist(tmp_path):
    settings = setup(tmp_path / "config", tmp_path / "db", LLMConfig())
    with TestClient(create_app(settings)) as client:
        page = client.get("/")
        assert page.status_code == 200 and 'value="llm" selected' in page.text
        assert '<script src="/assets/app.js"' in page.text
        assert settings.api_keys[0] not in page.text
        assert "frame-ancestors 'none'" in page.headers["Content-Security-Policy"]
        assert page.headers["Referrer-Policy"] == "no-referrer"
        assert page.headers["Cache-Control"] == "no-store"
        assert client.get("/assets/app.js").status_code == 200
        assert client.get("/assets/styles.css").headers["content-type"].startswith("text/css")
        assert client.get("/assets/server.json").status_code == 404
        assert client.get("/docs").status_code == 404
        assert client.get("/redoc").status_code == 404
        assert client.get("/openapi.json").status_code == 200
