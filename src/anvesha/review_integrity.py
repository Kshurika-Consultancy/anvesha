"""ANV-025: append-only exposure and assignment history for trusted local reviews."""

import json
import secrets
from collections import defaultdict
from dataclasses import dataclass
from datetime import UTC, datetime

from anvesha.eval_data import digest, json_bytes

VERSION = 2
REASONS = ("coaching", "label_exposure", "conflict_of_interest")
SCHEMA = (
    """CREATE TABLE exclusions (
        reviewer TEXT NOT NULL, query_id TEXT NOT NULL, reason TEXT NOT NULL,
        recorded_at TEXT NOT NULL, PRIMARY KEY(reviewer, query_id))""",
    """CREATE TABLE replacements (
        pair_id TEXT NOT NULL, previous_reviewer TEXT NOT NULL, reviewer TEXT NOT NULL,
        independence_attested INTEGER NOT NULL, recorded_at TEXT NOT NULL,
        PRIMARY KEY(pair_id, previous_reviewer), UNIQUE(pair_id, reviewer))""",
    """CREATE TABLE enrollments (
        reviewer TEXT PRIMARY KEY, independence_attested INTEGER NOT NULL,
        recorded_at TEXT NOT NULL)""",
)


@dataclass
class AssignmentState:
    active: dict[str, list[str]]
    history: dict[str, set[str]]
    blocked: set[tuple[str, str]]
    query_ids: dict[str, str]
    exclusions: set[tuple[str, str]]


def assignment_state(db):
    query_ids = {
        row["id"]: json.loads(row["query_json"])["id"]
        for row in db.execute("SELECT id, query_json FROM pairs")
    }
    history = defaultdict(set)
    for row in db.execute("SELECT * FROM assignments"):
        history[row["pair_id"]].add(row["reviewer"])
    superseded = set()
    for row in db.execute("SELECT * FROM replacements"):
        history[row["pair_id"]].add(row["reviewer"])
        superseded.add((row["pair_id"], row["previous_reviewer"]))
    active = {
        pid: sorted(r for r in reviewers if (pid, r) not in superseded)
        for pid, reviewers in sorted(history.items())
    }
    exclusions = {
        (row["reviewer"], row["query_id"]) for row in db.execute("SELECT * FROM exclusions")
    }
    blocked = {
        (pid, r)
        for pid, reviewers in active.items()
        for r in reviewers
        if (r, query_ids[pid]) in exclusions
    }
    return AssignmentState(active, dict(history), blocked, query_ids, exclusions)


def eligible_labels(state, labels):
    return {
        key: row
        for key, row in labels.items()
        if key[1] in state.active[key[0]] and key not in state.blocked
    }


def audit(db):
    """Private pseudonymous events only; no credentials, passages or assessment text."""
    return {
        "schema_version": VERSION,
        "exclusions": [
            dict(row) for row in db.execute("SELECT * FROM exclusions ORDER BY reviewer, query_id")
        ],
        "replacements": [
            dict(row)
            for row in db.execute("SELECT * FROM replacements ORDER BY pair_id, previous_reviewer")
        ],
        "enrollments": [
            dict(row) for row in db.execute("SELECT * FROM enrollments ORDER BY reviewer")
        ],
    }


def exclude(db, reviewer, query_id, reason):
    who = db.execute("SELECT role FROM reviewers WHERE id=?", (reviewer,)).fetchone()
    if who is None or who["role"] != "reviewer":
        raise ValueError("Exclusions require an enrolled initial reviewer, not the adjudicator")
    if reason not in REASONS:
        raise ValueError("Unsupported exclusion reason")
    state = assignment_state(db)
    if query_id not in state.query_ids.values():
        raise ValueError("Unknown query in this frozen session")
    previous = db.execute(
        "SELECT reason FROM exclusions WHERE reviewer=? AND query_id=?", (reviewer, query_id)
    ).fetchone()
    if previous and previous["reason"] != reason:
        raise ValueError("Exclusions are permanent; refusing to change the recorded reason")
    if previous is None:
        db.execute(
            "INSERT INTO exclusions VALUES (?, ?, ?, ?)",
            (reviewer, query_id, reason, datetime.now(UTC).isoformat()),
        )
    return {
        "reviewer": reviewer,
        "query_id": query_id,
        "reason": reason,
        "recorded": previous is None,
        "affected_assignments": sum(
            reviewer in rs and state.query_ids[pid] == query_id for pid, rs in state.history.items()
        ),
    }


def enroll(db, reviewer, independence_attested):
    if independence_attested is not True:
        raise ValueError("Explicit operator --independence-attested is required")
    if any(
        row["id"].casefold() == reviewer.casefold()
        for row in db.execute("SELECT id FROM reviewers")
    ):
        raise ValueError("Reviewer already enrolled; refusing to reset identity or credential")
    if db.execute("SELECT COUNT(*) FROM reviewers").fetchone()[0] >= 101:
        raise ValueError("Session reviewer limit reached")
    token = secrets.token_urlsafe(32)
    db.execute(
        "INSERT INTO reviewers VALUES (?, 'reviewer', ?)", (reviewer, digest(token.encode()))
    )
    db.execute(
        "INSERT INTO enrollments VALUES (?, 1, ?)", (reviewer, datetime.now(UTC).isoformat())
    )
    return token


def replace(db, reviewer, replacement, query_id, independence_attested):
    if independence_attested is not True:
        raise ValueError("Explicit operator --independence-attested is required")
    state = assignment_state(db)
    if (reviewer, query_id) not in state.exclusions:
        raise ValueError("Record the query exclusion before replacing assignments")
    who = db.execute("SELECT role FROM reviewers WHERE id=?", (replacement,)).fetchone()
    if who is None or who["role"] != "reviewer":
        raise ValueError("Replacement must be an enrolled reviewer, not the adjudicator")
    if (replacement, query_id) in state.exclusions:
        raise ValueError("Replacement reviewer is excluded for this query")
    targets = sorted(
        pid
        for pid, rs in state.active.items()
        if reviewer in rs and state.query_ids[pid] == query_id
    )
    if not targets:
        raise ValueError("No active excluded assignments to replace; inspect the audit history")
    if any(replacement in state.history[pid] for pid in targets):
        raise ValueError("Replacement already held an assignment on this pair")
    now = datetime.now(UTC).isoformat()
    db.executemany(
        "INSERT INTO replacements VALUES (?, ?, ?, 1, ?)",
        [(pid, reviewer, replacement, now) for pid in targets],
    )
    return {
        "reviewer": reviewer,
        "replacement": replacement,
        "query_id": query_id,
        "replaced_assignments": len(targets),
        "audit_sha256": digest(json_bytes(audit(db))),
    }
