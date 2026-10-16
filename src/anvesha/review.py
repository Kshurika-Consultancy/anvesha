"""ANV-020: trusted local operator workflow for independent human assessment.

This is not a hosted multi-user security boundary. Keep the workspace and keys private.
"""

import argparse
import hashlib
import hmac
import itertools
import json
import math
import os
import re
import secrets
import sqlite3
from collections import defaultdict
from contextlib import contextmanager
from datetime import UTC, datetime
from pathlib import Path

from anvesha.eval_data import digest, json_bytes

DEFAULT_WORKSPACE = Path(".anvesha/reviews/xquad-intents-v1")
MAX_PACKET_BYTES = 128 * 1024 * 1024
MUTABLE = {"grade", "rationale", "abstain_reason"}
SCHEMA = """
CREATE TABLE meta (key TEXT PRIMARY KEY, value TEXT NOT NULL);
CREATE TABLE reviewers (id TEXT PRIMARY KEY, role TEXT NOT NULL, token_hash TEXT NOT NULL);
CREATE TABLE pairs (id TEXT PRIMARY KEY, query_json TEXT NOT NULL, document_json TEXT NOT NULL);
CREATE TABLE assignments (pair_id TEXT NOT NULL, reviewer TEXT NOT NULL,
    PRIMARY KEY(pair_id, reviewer));
CREATE TABLE labels (pair_id TEXT NOT NULL, reviewer TEXT NOT NULL, revision INTEGER NOT NULL,
    grade INTEGER, rationale TEXT NOT NULL, abstain_reason TEXT,
    submitted_at TEXT NOT NULL, PRIMARY KEY(pair_id, reviewer, revision));
CREATE TABLE decisions (pair_id TEXT NOT NULL, reviewer TEXT NOT NULL, revision INTEGER NOT NULL,
    grade INTEGER NOT NULL, rationale TEXT NOT NULL, versions_json TEXT NOT NULL,
    submitted_at TEXT NOT NULL, PRIMARY KEY(pair_id, revision));
CREATE TABLE imports (id TEXT PRIMARY KEY, reviewer TEXT NOT NULL, packet_sha256 TEXT NOT NULL,
    human_attestation INTEGER NOT NULL, received_at TEXT NOT NULL,
    accepted INTEGER NOT NULL, unchanged INTEGER NOT NULL);
"""


def read_object(path):
    if path.stat().st_size > MAX_PACKET_BYTES:
        raise ValueError("Review input exceeds byte limit")
    data = json.loads(path.read_bytes())
    if not isinstance(data, dict):
        raise ValueError("Review input must be a JSON object")
    return data


def _id(value):
    if not isinstance(value, str) or not re.fullmatch(r"[A-Za-z0-9_-]{1,80}", value):
        raise ValueError("Invalid review identifier")
    return value


@contextmanager
def connect(workspace):
    path = workspace / "review.db"
    if not path.is_file():
        raise ValueError("Review workspace does not exist; initialize it first")
    db = sqlite3.connect(path, timeout=10)
    db.row_factory = sqlite3.Row
    try:
        with db:
            yield db
    finally:
        db.close()


def _meta(db):
    return {row["key"]: json.loads(row["value"]) for row in db.execute("SELECT * FROM meta")}


def initialize(
    workspace,
    pool_path,
    reviewers,
    adjudicator,
    *,
    double_fraction=0.2,
    split="development",
    release_holdout=False,
    synthetic=False,
    max_pairs=200,
    languages=None,
):
    if workspace.exists():
        raise ValueError("Refusing to overwrite an existing review workspace")
    if len(reviewers) < 2 or len(reviewers) > 20 or len(set(reviewers)) != len(reviewers):
        raise ValueError("Use 2..20 distinct reviewer pseudonyms")
    for value in [*reviewers, adjudicator]:
        _id(value)
    if adjudicator in reviewers:
        raise ValueError("Adjudicator must be separate from all initial reviewers")
    if not 0 < double_fraction <= 1 or split not in {"development", "holdout", "all"}:
        raise ValueError("Invalid review fraction or split")
    if split != "development" and not release_holdout:
        raise ValueError("Explicit --release-holdout required; reserve holdout from tuning")
    pool = read_object(pool_path)
    if pool.get("schema_version") != 1 or not isinstance(pool.get("rubric"), dict):
        raise ValueError("Unsupported pool or missing frozen rubric")
    for key in ("dataset", "snapshot_sha256", "ranking_fingerprint", "rights_manifest"):
        if not isinstance(pool.get(key), str) or not pool[key]:
            raise ValueError("Pool needs dataset, rights and ranking provenance")
    if type(max_pairs) is not int or max_pairs < 0:
        raise ValueError("max_pairs must be a nonnegative integer; zero means all")
    pairs, seen, seen_pairs, buckets = [], set(), set(), defaultdict(list)
    query_versions, document_versions = {}, {}
    for pair in pool["pairs"]:
        pid = _id(pair["pair_id"])
        query, doc = pair["query"], pair["document"]
        if pid in seen or query["split"] not in {"development", "holdout"}:
            raise ValueError("Duplicate pair or unsupported split")
        seen.add(pid)
        _id(query["id"])
        _id(doc["id"])
        identity = query["id"], doc["id"]
        if identity in seen_pairs:
            raise ValueError("Duplicate query/document pair")
        seen_pairs.add(identity)
        for versions, record in ((query_versions, query), (document_versions, doc)):
            if record["id"] in versions and versions[record["id"]] != record:
                raise ValueError("Conflicting query or document snapshots")
            versions[record["id"]] = record
        if (
            not all(
                isinstance(query.get(k), str) and query[k] for k in ("text", "language", "stratum")
            )
            or not isinstance(query.get("constraints"), list)
            or not all(isinstance(c, str) for c in query["constraints"])
            or not all(
                isinstance(doc.get(k), str) and doc[k]
                for k in ("title", "text", "url", "language", "license", "attribution")
            )
        ):
            raise ValueError("Malformed pool query or document")
        if (split == "all" or query["split"] == split) and (
            languages is None or query["language"] in languages
        ):
            pairs.append(pair)
            buckets[query["language"], query["stratum"]].append(pid)
    if not pairs:
        raise ValueError("No candidate pairs in the requested split")
    eligible_pairs = len(pairs)
    if max_pairs and max_pairs < len(pairs):
        if max_pairs < len(buckets):
            raise ValueError("Pilot size must cover every language/stratum bucket")
        ordered = [
            sorted(buckets[key], key=lambda pid: digest(pid.encode())) for key in sorted(buckets)
        ]
        selected = [
            pid for row in itertools.zip_longest(*ordered) for pid in row if pid is not None
        ][:max_pairs]
        selected = set(selected)
        pairs = [pair for pair in pairs if pair["pair_id"] in selected]
        buckets = {key: [pid for pid in ids if pid in selected] for key, ids in buckets.items()}
    assignments = []
    for bucket in sorted(buckets):
        ids = sorted(
            buckets[bucket], key=lambda pid: digest((pool["snapshot_sha256"] + pid).encode())
        )
        doubled = math.ceil(len(ids) * double_fraction)
        for index, pid in enumerate(ids):
            assignments.append((pid, reviewers[index % len(reviewers)]))
            if index < doubled:
                assignments.append((pid, reviewers[(index + 1) % len(reviewers)]))
    keys = {reviewer: secrets.token_urlsafe(32) for reviewer in [*reviewers, adjudicator]}
    metadata = {
        "schema_version": 1,
        "session": secrets.token_hex(16),
        "signing_key": secrets.token_hex(32),
        "dataset": pool["dataset"],
        "snapshot_sha256": pool["snapshot_sha256"],
        "pool_sha256": digest(pool_path.read_bytes()),
        "ranking_fingerprint": pool["ranking_fingerprint"],
        "rights_manifest": pool["rights_manifest"],
        "rubric": pool["rubric"],
        "split": split,
        "holdout_released": release_holdout,
        "double_fraction": double_fraction,
        "assessment_origin": "synthetic_test" if synthetic else "human_attested",
        "created_at": datetime.now(UTC).isoformat(),
        "eligible_pairs": eligible_pairs,
        "languages": sorted({p["query"]["language"] for p in pairs}),
        "pool_queries": pool.get("query_count"),
        "pool_empty_queries": pool.get("empty_query_ids", []),
    }
    workspace.mkdir(parents=True)
    db = sqlite3.connect(workspace / "review.db")
    try:
        db.executescript(SCHEMA)
        with db:
            db.executemany(
                "INSERT INTO meta VALUES (?, ?)", [(k, json.dumps(v)) for k, v in metadata.items()]
            )
            db.executemany(
                "INSERT INTO reviewers VALUES (?, ?, ?)",
                [
                    (r, "adjudicator" if r == adjudicator else "reviewer", digest(key.encode()))
                    for r, key in keys.items()
                ],
            )
            db.executemany(
                "INSERT INTO pairs VALUES (?, ?, ?)",
                [(p["pair_id"], json.dumps(p["query"]), json.dumps(p["document"])) for p in pairs],
            )
            db.executemany("INSERT INTO assignments VALUES (?, ?)", assignments)
    finally:
        db.close()
    credentials = workspace / "credentials.json"
    credentials.write_bytes(json_bytes(keys))
    credentials.chmod(0o600)
    return status(workspace)


def _latest(db):
    labels = {}
    for row in db.execute("SELECT * FROM labels ORDER BY revision"):
        labels[row["pair_id"], row["reviewer"]] = dict(row)
    decisions = {}
    for row in db.execute("SELECT * FROM decisions ORDER BY revision"):
        decisions[row["pair_id"]] = dict(row)
    return labels, decisions


def _assignments(db):
    result = defaultdict(list)
    for row in db.execute("SELECT * FROM assignments ORDER BY pair_id, reviewer"):
        result[row["pair_id"]].append(row["reviewer"])
    return result


def _versions(pid, assigned, labels):
    return {r: labels[pid, r]["revision"] for r in assigned if (pid, r) in labels}


def _resolution(pid, assigned, labels, decisions):
    rows = [labels.get((pid, reviewer)) for reviewer in assigned]
    if any(row is None for row in rows):
        return None, "pending"
    decision = decisions.get(pid)
    if decision and json.loads(decision["versions_json"]) == _versions(pid, assigned, labels):
        return decision["grade"], "adjudicated"
    grades = [row["grade"] for row in rows]
    if None in grades or len(set(grades)) != 1:
        return None, "needs_adjudication"
    return grades[0], "agreement" if len(rows) == 2 else "single_review"


def _core(packet):
    if set(packet) != {
        "schema_version",
        "session",
        "reviewer",
        "role",
        "rubric",
        "items",
        "signature",
        "human_attestation",
    }:
        raise ValueError("Unexpected packet fields")
    if (
        type(packet["schema_version"]) is not int
        or packet["schema_version"] != 1
        or not isinstance(packet["items"], list)
        or not isinstance(packet["rubric"], dict)
        or packet["role"] not in {"reviewer", "adjudicator"}
    ):
        raise ValueError("Invalid packet schema or item collection")
    fields = {"pair_id", "query", "document", "revision", "grade", "rationale", "abstain_reason"}
    if packet["role"] == "adjudicator":
        fields.add("review_labels")
    if any(not isinstance(row, dict) or set(row) != fields for row in packet["items"]):
        raise ValueError("Invalid packet item schema")
    return {
        key: (
            [{k: v for k, v in row.items() if k not in MUTABLE} for row in value]
            if key == "items"
            else value
        )
        for key, value in packet.items()
        if key not in {"signature", "human_attestation"}
    }


def _signature(metadata, packet):
    return hmac.new(
        bytes.fromhex(metadata["signing_key"]), json_bytes(_core(packet)), hashlib.sha256
    ).hexdigest()


def export_packet(workspace, reviewer):
    with connect(workspace) as db:
        who = db.execute("SELECT * FROM reviewers WHERE id=?", (reviewer,)).fetchone()
        if who is None:
            raise ValueError("Unknown reviewer")
        metadata = _meta(db)
        labels, decisions = _latest(db)
        assigned = _assignments(db)
        items = []
        for pair in db.execute("SELECT * FROM pairs ORDER BY id"):
            pid = pair["id"]
            if who["role"] == "reviewer":
                if reviewer not in assigned[pid]:
                    continue
                previous = labels.get((pid, reviewer))
            else:
                if _resolution(pid, assigned[pid], labels, decisions)[1] != "needs_adjudication":
                    continue
                previous = decisions.get(pid)
            query, doc = json.loads(pair["query_json"]), json.loads(pair["document_json"])
            item = {
                "pair_id": pid,
                "query": {key: query[key] for key in ("id", "text", "language", "constraints")},
                "document": {
                    key: doc[key]
                    for key in ("id", "title", "text", "url", "language", "license", "attribution")
                },
                "revision": previous["revision"] if previous else 0,
                "grade": previous["grade"] if previous else None,
                "rationale": previous["rationale"] if previous else "",
                "abstain_reason": previous.get("abstain_reason") if previous else None,
            }
            if who["role"] == "adjudicator":
                item["review_labels"] = [
                    {
                        key: labels[pid, r][key]
                        for key in ("reviewer", "revision", "grade", "rationale", "abstain_reason")
                    }
                    for r in assigned[pid]
                ]
            items.append(item)
        # Pair order is independent of source ranking; split, engine and gold labels are absent.
        items.sort(key=lambda item: digest((reviewer + item["pair_id"]).encode()))
        packet = {
            "schema_version": 1,
            "session": metadata["session"],
            "reviewer": reviewer,
            "role": who["role"],
            "rubric": metadata["rubric"],
            "items": items,
            "signature": "",
            "human_attestation": False,
        }
        packet["signature"] = _signature(metadata, packet)
        return packet


def import_packet(workspace, packet, token, *, allow_revisions=False):
    if packet.get("human_attestation") is not True:
        raise ValueError("Explicit personal human-assessor attestation is required")
    with connect(workspace) as db:
        db.execute("BEGIN IMMEDIATE")
        metadata = _meta(db)
        reviewer = packet.get("reviewer")
        who = db.execute("SELECT * FROM reviewers WHERE id=?", (reviewer,)).fetchone()
        if (
            who is None
            or not isinstance(token, str)
            or not hmac.compare_digest(who["token_hash"], digest(token.encode()))
        ):
            raise ValueError("Invalid reviewer credential")
        if packet.get("session") != metadata["session"] or packet.get("role") != who["role"]:
            raise ValueError("Packet session or reviewer role mismatch")
        if not hmac.compare_digest(packet.get("signature", ""), _signature(metadata, packet)):
            raise ValueError("Packet contents or assignments changed")
        labels, decisions = _latest(db)
        assignments = _assignments(db)
        seen, accepted, unchanged = set(), 0, 0
        for item in packet["items"]:
            pid = item["pair_id"]
            if pid in seen or pid not in assignments:
                raise ValueError("Duplicate or unknown assignment")
            seen.add(pid)
            grade, rationale, abstain = item["grade"], item["rationale"], item["abstain_reason"]
            if grade is None and not abstain and not rationale:
                continue  # Unfinished rows never become negative judgments.
            if grade is not None and (type(grade) is not int or grade not in (0, 1)):
                raise ValueError("Grade must be integer 0/1 or an explicit abstention")
            if not isinstance(rationale, str) or not 1 <= len(rationale.strip()) <= 4000:
                raise ValueError("A nonempty rationale of at most 4000 characters is required")
            if grade is None:
                if (
                    not isinstance(abstain, str)
                    or not 1 <= len(abstain.strip()) <= 1000
                    or who["role"] == "adjudicator"
                ):
                    raise ValueError(
                        "Review abstentions need a reason; adjudicators must resolve 0/1"
                    )
            elif abstain is not None:
                raise ValueError("A graded judgment cannot also abstain")
            if who["role"] == "reviewer":
                if reviewer not in assignments[pid]:
                    raise ValueError("Pair not assigned to this reviewer")
                previous = labels.get((pid, reviewer))
            else:
                versions = {r["reviewer"]: r["revision"] for r in item["review_labels"]}
                if versions != _versions(pid, assignments[pid], labels) or len(versions) != len(
                    assignments[pid]
                ):
                    raise ValueError("Adjudication is stale or missing independent reviews")
                previous = decisions.get(pid)
            same = (
                previous
                and previous["grade"] == grade
                and previous["rationale"] == rationale
                and previous.get("abstain_reason") == abstain
            )
            # A stale adjudication must be resubmitted against current label versions.
            if same and (
                who["role"] == "reviewer" or json.loads(previous["versions_json"]) == versions
            ):
                unchanged += 1
                continue
            revision = previous["revision"] if previous else 0
            if type(item["revision"]) is not int or item["revision"] != revision:
                raise ValueError("Stale packet revision; export a fresh packet")
            if previous and not allow_revisions:
                raise ValueError("Existing assessment requires explicit --revise")
            now = datetime.now(UTC).isoformat()
            if who["role"] == "reviewer":
                db.execute(
                    "INSERT INTO labels VALUES (?, ?, ?, ?, ?, ?, ?)",
                    (pid, reviewer, revision + 1, grade, rationale, abstain, now),
                )
            else:
                db.execute(
                    "INSERT INTO decisions VALUES (?, ?, ?, ?, ?, ?, ?)",
                    (
                        pid,
                        reviewer,
                        revision + 1,
                        grade,
                        rationale,
                        json.dumps(versions, sort_keys=True),
                        now,
                    ),
                )
            accepted += 1
        if accepted + unchanged == 0:
            raise ValueError("Packet contains no completed assessments")
        db.execute(
            "INSERT INTO imports VALUES (?, ?, ?, ?, ?, ?, ?)",
            (
                secrets.token_hex(16),
                reviewer,
                digest(json_bytes(packet)),
                1,
                datetime.now(UTC).isoformat(),
                accepted,
                unchanged,
            ),
        )
        return {"accepted": accepted, "unchanged": unchanged}


def _agreement(assignments, labels):
    groups = defaultdict(list)
    for pid, reviewers in assignments.items():
        if len(reviewers) != 2:
            continue
        rows = [labels.get((pid, r)) for r in reviewers]
        if all(row is not None and row["grade"] is not None for row in rows):
            groups[tuple(reviewers)].append(tuple(row["grade"] for row in rows))
    report = []
    for reviewers, values in sorted(groups.items()):
        count = len(values)
        observed = sum(a == b for a, b in values) / count
        left = sum(a for a, _ in values) / count
        right = sum(b for _, b in values) / count
        expected = left * right + (1 - left) * (1 - right)
        report.append(
            {
                "reviewers": list(reviewers),
                "paired_nonabstained": count,
                "agreement": observed,
                "cohen_kappa": (observed - expected) / (1 - expected) if expected < 1 else None,
                "undefined_reason": "No marginal label variation" if expected == 1 else None,
            }
        )
    return report


def status(workspace):
    with connect(workspace) as db:
        metadata = _meta(db)
        assigned = _assignments(db)
        labels, decisions = _latest(db)
        counts = defaultdict(int)
        for pid, reviewers in assigned.items():
            counts[_resolution(pid, reviewers, labels, decisions)[1]] += 1
        by_reviewer = {}
        for reviewer in sorted({r for rs in assigned.values() for r in rs}):
            ids = [pid for pid, rs in assigned.items() if reviewer in rs]
            completed = [labels[pid, reviewer] for pid in ids if (pid, reviewer) in labels]
            by_reviewer[reviewer] = {
                "assigned": len(ids),
                "submitted": len(completed),
                "abstained": sum(r["grade"] is None for r in completed),
                "pending": len(ids) - len(completed),
            }
        return {
            "session": metadata["session"],
            "dataset": metadata["dataset"],
            "pool_sha256": metadata["pool_sha256"],
            "snapshot_sha256": metadata["snapshot_sha256"],
            "rubric_id": metadata["rubric"]["id"],
            "split": metadata["split"],
            "assessment_origin": metadata["assessment_origin"],
            "pairs": len(assigned),
            "eligible_pool_pairs": metadata["eligible_pairs"],
            "languages": metadata["languages"],
            "queries_with_pairs": db.execute(
                "SELECT COUNT(DISTINCT json_extract(query_json, '$.id')) FROM pairs"
            ).fetchone()[0],
            "pool_queries": metadata["pool_queries"],
            "pool_empty_queries": metadata["pool_empty_queries"],
            "double_assigned_pairs": sum(len(rs) == 2 for rs in assigned.values()),
            "latest_submissions": len(labels),
            "new_human_judgments": sum(row["grade"] is not None for row in labels.values())
            if metadata["assessment_origin"] == "human_attested"
            else 0,
            "revisions_retained": db.execute("SELECT COUNT(*) FROM labels").fetchone()[0],
            "import_receipts": db.execute("SELECT COUNT(*) FROM imports").fetchone()[0],
            "resolution": {
                key: counts[key]
                for key in (
                    "pending",
                    "needs_adjudication",
                    "single_review",
                    "agreement",
                    "adjudicated",
                )
            },
            "reviewers": by_reviewer,
            "pairwise_agreement": _agreement(assigned, labels),
        }


def export_qrels(workspace, output, *, allow_partial=False):
    if not output.resolve().is_relative_to(workspace.resolve()):
        raise ValueError("Assessment exports must stay inside the private workspace")
    progress = status(workspace)
    if (
        progress["resolution"]["pending"] or progress["resolution"]["needs_adjudication"]
    ) and not allow_partial:
        raise ValueError(
            "Review is incomplete or unresolved; use explicit --allow-partial for progress only"
        )
    rows = []
    with connect(workspace) as db:
        labels, decisions = _latest(db)
        assigned = _assignments(db)
        for pair in db.execute("SELECT * FROM pairs ORDER BY id"):
            grade, resolution = _resolution(pair["id"], assigned[pair["id"]], labels, decisions)
            if grade is not None:
                query, doc = json.loads(pair["query_json"]), json.loads(pair["document_json"])
                rows.append((query["id"], doc["id"], grade))
        metadata = _meta(db)
    versions = {
        "labels": sorted((pid, r, row["revision"]) for (pid, r), row in labels.items()),
        "decisions": sorted((pid, row["revision"]) for pid, row in decisions.items()),
    }
    fingerprint = digest(
        json_bytes({"rows": rows, "versions": versions, "pool": progress["pool_sha256"]})
    )
    destination = output / fingerprint[:20]
    destination.mkdir(parents=True, exist_ok=True)
    text = "query_id\tdocument_id\trelevance\n" + "".join(f"{q}\t{d}\t{g}\n" for q, d, g in rows)
    result = {
        **progress,
        "partial": bool(
            progress["resolution"]["pending"] or progress["resolution"]["needs_adjudication"]
        ),
        "exported_pairs": len(rows),
        "qrels_sha256": digest(text.encode()),
        "rubric_sha256": digest(json_bytes(metadata["rubric"])),
        "revision_fingerprint": fingerprint,
        "export_directory": str(destination),
        "training_authorized": False,
        "quality_metrics_calculated": False,
    }
    for name, raw in {"qrels.tsv": text.encode(), "coverage.json": json_bytes(result)}.items():
        path = destination / name
        if path.exists() and path.read_bytes() != raw:
            raise ValueError("Refusing to overwrite a frozen assessment export")
        path.write_bytes(raw)
    return result


def main(argv=None):
    parser = argparse.ArgumentParser(
        description="Private local human-review workflow; no paid services"
    )
    parser.add_argument("command", choices=("init", "export", "import", "status", "finalize"))
    parser.add_argument("--workspace", type=Path, default=DEFAULT_WORKSPACE)
    parser.add_argument(
        "--pool",
        type=Path,
        default=Path(".anvesha/evaluation/xquad-intents-v1/candidate-pool.json"),
    )
    parser.add_argument("--reviewers", nargs="+", default=["reviewer-a", "reviewer-b"])
    parser.add_argument("--adjudicator", default="adjudicator")
    parser.add_argument("--double-fraction", type=float, default=0.2)
    parser.add_argument(
        "--max-pairs", type=int, default=200, help="Pilot cap; zero selects every eligible pair"
    )
    parser.add_argument("--split", choices=("development", "holdout", "all"), default="development")
    parser.add_argument("--release-holdout", action="store_true")
    parser.add_argument("--languages", nargs="+", choices=("en", "es", "hi"))
    parser.add_argument(
        "--synthetic-test", action="store_true", help="Label all session output as synthetic tests"
    )
    parser.add_argument("--reviewer")
    parser.add_argument("--packet", type=Path)
    parser.add_argument("--revise", action="store_true")
    parser.add_argument("--allow-partial", action="store_true")
    args = parser.parse_args(argv)
    try:
        if args.command == "init":
            result = initialize(
                args.workspace,
                args.pool,
                args.reviewers,
                args.adjudicator,
                double_fraction=args.double_fraction,
                split=args.split,
                release_holdout=args.release_holdout,
                synthetic=args.synthetic_test,
                max_pairs=args.max_pairs,
                languages=args.languages,
            )
        elif args.command == "export":
            from anvesha.review_form import render_form

            packet = export_packet(args.workspace, args.reviewer)
            directory = args.workspace / "packets" / packet["reviewer"]
            directory.mkdir(parents=True, exist_ok=True)
            (directory / "packet.json").write_bytes(json_bytes(packet))
            (directory / "review.html").write_text(
                render_form(packet), encoding="utf-8", newline="\n"
            )
            result = {
                "reviewer": packet["reviewer"],
                "items": len(packet["items"]),
                "directory": str(directory),
            }
        elif args.command == "import":
            if args.packet is None:
                raise ValueError("--packet is required")
            result = import_packet(
                args.workspace,
                read_object(args.packet),
                os.environ.get("ANVESHA_REVIEW_TOKEN"),
                allow_revisions=args.revise,
            )
        elif args.command == "status":
            result = status(args.workspace)
        else:
            result = export_qrels(
                args.workspace, args.workspace / "export", allow_partial=args.allow_partial
            )
        print(json.dumps(result, ensure_ascii=True, indent=2))
        return 0
    except (OSError, ValueError, KeyError, TypeError, sqlite3.Error) as exc:
        parser.error(str(exc))


if __name__ == "__main__":
    raise SystemExit(main())
