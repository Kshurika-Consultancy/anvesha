"""ANV-001: tracking checks must reject real continuity failures."""

import importlib.util
import json
import subprocess
from pathlib import Path

import pytest

CHECKER_PATH = Path(__file__).resolve().parents[1] / "scripts/check_tracking.py"
SPEC = importlib.util.spec_from_file_location("tracking_checker", CHECKER_PATH)
checker = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(checker)


@pytest.fixture
def repository(tmp_path):
    subprocess.run(["git", "init", "-q", str(tmp_path)], check=True, capture_output=True)
    for name in checker.REQUIRED:
        path = tmp_path / name
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text("M0\n", encoding="utf-8")
        if name.startswith("policies/sources/"):
            manifest = {
                "source": path.stem,
                "manifest_version": "v1",
                "reviewed_at": "2026-10-16",
                "scope": "fixture",
                "license": "Apache-2.0",
                "task": "ANV-001",
                "rights": {
                    key: "reviewed"
                    for key in (
                        "retrieval",
                        "retention",
                        "display",
                        "redistribution",
                        "evaluation",
                        "training",
                    )
                },
                "references": ["https://example.org/terms"],
            }
            path.write_text(json.dumps(manifest), encoding="utf-8")
    ledger = {
        "schema_version": 1,
        "updated_at": "2026-10-16",
        "tasks": [
            {
                "id": "ANV-001",
                "title": "Foundation",
                "milestone": "M0",
                "owner": "root",
                "status": "in_progress",
                "depends_on": [],
                "acceptance": ["Checks work"],
                "validation_plan": ["Test validation"],
                "verification": [],
                "references": [],
                "notes": "",
            }
        ],
    }
    return tmp_path, ledger


def check(repository):
    root, ledger = repository
    (root / "docs/tracking/tasks.json").write_text(json.dumps(ledger), encoding="utf-8")
    return checker.validate(root)


def test_valid_active_task(repository):
    assert check(repository) == []


def test_done_needs_evidence_and_references(repository):
    _, ledger = repository
    ledger["tasks"][0]["status"] = "done"
    errors = check(repository)
    assert any("done requires recorded verification" in error for error in errors)
    assert any("done requires implementation/document references" in error for error in errors)


def test_unknown_dependencies_and_cycles(repository):
    _, ledger = repository
    ledger["tasks"][0]["depends_on"] = ["ANV-001", "ANV-" + "999"]
    errors = check(repository)
    assert any("Dependency cycle" in error for error in errors)
    assert any("unknown dependency" in error for error in errors)


def test_untracked_code_reminders_and_broken_links(repository):
    root, _ = repository
    (root / "problem.py").write_text("# TODO: repair this\n", encoding="utf-8")
    (root / "README.md").write_text("[missing](does-not-exist.md)\n", encoding="utf-8")
    errors = check(repository)
    assert any("untracked reminder" in error for error in errors)
    assert any("broken local link" in error for error in errors)


def test_references_and_done_dependencies_must_exist(repository):
    _, ledger = repository
    task = ledger["tasks"][0]
    task.update(
        status="done",
        references=["missing.py"],
        verification=[
            {
                "command": "pytest",
                "result": "passed",
                "date": "2026-10-16",
            }
        ],
    )
    ledger["tasks"].append({**task, "id": "ANV-002", "status": "planned", "references": []})
    task["depends_on"] = ["ANV-002"]
    errors = check(repository)
    assert any("missing or external reference" in error for error in errors)
    assert any("dependency ANV-002 is not done" in error for error in errors)


def test_source_rights_cannot_be_omitted(repository):
    root, _ = repository
    path = root / "policies/sources/local.json"
    manifest = json.loads(path.read_text(encoding="utf-8"))
    del manifest["rights"]["training"]
    path.write_text(json.dumps(manifest), encoding="utf-8")
    assert any("undocumented source right training" in error for error in check(repository))
