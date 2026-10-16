"""Validate task continuity and repository references for ANV-001. Offline, stdlib only."""

import io
import json
import re
import subprocess
import sys
import tokenize
from pathlib import Path
from urllib.parse import unquote

ROOT = Path(__file__).resolve().parents[1]
STATES = {"planned", "in_progress", "blocked", "done", "deferred"}
REQUIRED = {
    "AGENTS.md",
    "README.md",
    "LICENSE",
    "CONTRIBUTING.md",
    "SECURITY.md",
    "docs/PLAN.md",
    "docs/RESEARCH.md",
    "docs/MILESTONES.md",
    "docs/API.md",
    "docs/architecture/README.md",
    "docs/tracking/STATUS.md",
    "docs/tracking/HANDOFF.md",
    "docs/tracking/CHANGELOG.md",
    "docs/tracking/tasks.json",
    "policies/sources/local.json",
    "policies/sources/wikidata.json",
}


def repository_files(root):
    output = subprocess.check_output(
        ["git", "ls-files", "--cached", "--others", "--exclude-standard", "-z"], cwd=root
    )
    return sorted({Path(name) for name in output.decode().split("\0") if name})


def validate(root=ROOT):
    errors = []
    for name in sorted(REQUIRED):
        if not (root / name).is_file():
            errors.append(f"Missing required file: {name}")
    ledger_path = root / "docs/tracking/tasks.json"
    try:
        ledger = json.loads(ledger_path.read_text(encoding="utf-8"))
    except (OSError, ValueError) as exc:
        return [*errors, f"Cannot read task ledger: {exc}"]
    if ledger.get("schema_version") != 1:
        errors.append("Task ledger schema_version must be 1")
    if not re.fullmatch(r"\d{4}-\d{2}-\d{2}", ledger.get("updated_at", "")):
        errors.append("Task ledger updated_at must be an ISO date")
    tasks = ledger.get("tasks", [])
    if not isinstance(tasks, list) or not tasks:
        return [*errors, "Task ledger must contain a nonempty tasks list"]
    by_id = {}
    for task in tasks:
        if not isinstance(task, dict):
            errors.append("Every task must be an object")
            continue
        task_id = task.get("id", "")
        if not re.fullmatch(r"ANV-\d{3}", task_id):
            errors.append(f"Invalid task ID: {task_id!r}")
        if task_id in by_id:
            errors.append(f"Duplicate task ID: {task_id}")
        by_id[task_id] = task
        for field in ("title", "milestone", "owner", "status"):
            if not isinstance(task.get(field), str) or not task[field].strip():
                errors.append(f"{task_id}: nonblank {field} required")
        if task.get("status") not in STATES:
            errors.append(f"{task_id}: invalid status")
        if task.get("status") == "in_progress" and task.get("owner") == "unassigned":
            errors.append(f"{task_id}: active task needs an owner")
        for field in ("acceptance", "validation_plan"):
            value = task.get(field)
            if (
                not isinstance(value, list)
                or not value
                or any(not isinstance(item, str) or not item.strip() for item in value)
            ):
                errors.append(f"{task_id}: {field} must contain nonblank criteria")
        for field in ("depends_on", "references", "verification"):
            if not isinstance(task.get(field), list):
                errors.append(f"{task_id}: {field} must be a list")
        if task.get("status") in {"blocked", "deferred"} and not task.get("notes", "").strip():
            errors.append(f"{task_id}: blocked/deferred task needs explanatory notes")
        if task.get("status") == "done":
            evidence = task.get("verification", [])
            if not evidence:
                errors.append(f"{task_id}: done requires recorded verification")
            for item in evidence:
                if not isinstance(item, dict) or any(
                    not isinstance(item.get(field), str) or not item[field].strip()
                    for field in ("command", "result", "date")
                ):
                    errors.append(f"{task_id}: evidence needs command, result and date")
            if not task.get("references"):
                errors.append(f"{task_id}: done requires implementation/document references")
        for reference in task.get("references", []):
            path = (root / reference).resolve()
            if not path.is_relative_to(root.resolve()) or not path.is_file():
                errors.append(f"{task_id}: missing or external reference {reference}")
    for task_id, task in by_id.items():
        for dependency in task.get("depends_on", []):
            if dependency not in by_id:
                errors.append(f"{task_id}: unknown dependency {dependency}")
            elif task.get("status") == "done" and by_id[dependency].get("status") != "done":
                errors.append(f"{task_id}: done but dependency {dependency} is not done")
    visiting, visited = set(), set()

    def visit(task_id):
        if task_id in visiting:
            errors.append(f"Dependency cycle includes {task_id}")
            return
        if task_id in visited or task_id not in by_id:
            return
        visiting.add(task_id)
        for dependency in by_id[task_id].get("depends_on", []):
            visit(dependency)
        visiting.remove(task_id)
        visited.add(task_id)

    for task_id in by_id:
        visit(task_id)
    milestones_file = root / "docs/MILESTONES.md"
    milestones = (
        set(re.findall(r"\bM\d+\b", milestones_file.read_text(encoding="utf-8")))
        if milestones_file.exists()
        else set()
    )
    for task_id, task in by_id.items():
        if task.get("milestone") not in milestones:
            errors.append(f"{task_id}: milestone not defined in docs/MILESTONES.md")
    for manifest_path in sorted((root / "policies/sources").glob("*.json")):
        try:
            manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
            if not isinstance(manifest, dict):
                raise ValueError("manifest must be an object")
            for field in ("source", "manifest_version", "reviewed_at", "scope", "license"):
                if not isinstance(manifest.get(field), str) or not manifest[field].strip():
                    errors.append(f"{manifest_path.name}: missing source-policy {field}")
            if manifest.get("task") not in by_id:
                errors.append(f"{manifest_path.name}: source-policy task is untracked")
            rights = manifest.get("rights", {})
            for right in (
                "retrieval",
                "retention",
                "display",
                "redistribution",
                "evaluation",
                "training",
            ):
                if not isinstance(rights.get(right), str) or not rights[right].strip():
                    errors.append(f"{manifest_path.name}: undocumented source right {right}")
            if not manifest.get("references"):
                errors.append(f"{manifest_path.name}: source-policy evidence required")
        except (OSError, ValueError) as exc:
            errors.append(f"{manifest_path.name}: cannot read source policy: {exc}")
    for relative in repository_files(root):
        path = root / relative
        if not path.is_file() or path.suffix not in {".md", ".py", ".json", ".yml"}:
            continue
        text = path.read_text(encoding="utf-8")
        for referenced_id in set(re.findall(r"\bANV-\d{3}\b", text)) - by_id.keys():
            errors.append(f"{relative}: unknown task {referenced_id}")
        if path.suffix == ".py":
            try:
                tokens = tokenize.generate_tokens(io.StringIO(text).readline)
                for token in tokens:
                    if token.type == tokenize.COMMENT and re.search(
                        r"\b(?:TODO|FIXME|HACK)(?!\[ANV-\d{3}\])", token.string
                    ):
                        errors.append(f"{relative}:{token.start[0]}: untracked reminder")
            except tokenize.TokenError as exc:
                errors.append(f"{relative}: invalid Python tokens: {exc}")
        if path.suffix == ".md":
            for target in re.findall(r"\[[^\]]*\]\(([^)]+)\)", text):
                target = unquote(target.split("#", 1)[0].strip("<>"))
                if not target or re.match(r"[a-zA-Z][a-zA-Z0-9+.-]*:", target):
                    continue
                if not (path.parent / target).exists():
                    errors.append(f"{relative}: broken local link {target}")
    return sorted(set(errors))


def main():
    errors = validate()
    if errors:
        print("Tracking checks failed:\n" + "\n".join(f"- {error}" for error in errors))
        return 1
    print("Tracking checks passed: task graph, completion evidence, links, and code reminders.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
