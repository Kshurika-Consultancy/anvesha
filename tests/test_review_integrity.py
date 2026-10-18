"""ANV-025: synthetic assessments only; never read or submit the actual pilot."""

import copy
import json
import sqlite3
from contextlib import closing
from pathlib import Path

import pytest

import anvesha.review as review
from anvesha.eval_data import json_bytes


@pytest.fixture
def session(tmp_path):
    pairs = []
    for i, query_id in enumerate(("practice", "practice", "other", "third")):
        pairs.append(
            {
                "pair_id": f"pair-{i}",
                "query": {
                    "id": query_id,
                    "text": f"Synthetic question {query_id}",
                    "constraints": [],
                    "language": "en",
                    "stratum": "factual",
                    "split": "development",
                },
                "document": {
                    "id": f"doc-{i}",
                    "title": f"Synthetic document {i}",
                    "text": "First-party synthetic workflow passage, not a human assessment.",
                    "url": "https://example.org/synthetic",
                    "language": "en",
                    "license": "Apache-2.0",
                    "attribution": "Anvesha synthetic test",
                },
            }
        )
    pool = tmp_path / "synthetic-pool.json"
    pool.write_bytes(
        json_bytes(
            {
                "schema_version": 1,
                "dataset": "synthetic-integrity-test",
                "snapshot_sha256": "synthetic",
                "ranking_fingerprint": "synthetic",
                "rights_manifest": "first-party synthetic fixture",
                "rubric": {"id": "synthetic-binary", "grades": {"0": "No", "1": "Yes"}},
                "query_count": 3,
                "empty_query_ids": [],
                "pairs": pairs,
            }
        )
    )
    workspace = tmp_path / "synthetic-review"
    review.initialize(
        workspace, pool, ["alice", "bob"], "adjudicator", double_fraction=1, synthetic=True
    )
    keys = json.loads((workspace / "credentials.json").read_bytes())
    return workspace, keys


def filled(packet, grade=1):
    packet = copy.deepcopy(packet)
    packet["human_attestation"] = True  # Simulated only; fixture session is synthetic.
    for row in packet["items"]:
        row.update(grade=grade, rationale="Synthetic assessment for integrity testing")
    return packet


def submit(workspace, keys, reviewer, grade=1):
    return review.import_packet(
        workspace, filled(review.export_packet(workspace, reviewer), grade), keys[reviewer]
    )


def enrolled(workspace, keys, reviewer="replacement"):
    result = review.enroll_reviewer(workspace, reviewer, independence_attested=True)
    keys.update(json.loads(Path(result["credential_file"]).read_bytes()))
    return reviewer


def replace(workspace, reviewer="alice", replacement="replacement"):
    return review.replace_assignments(
        workspace, reviewer, replacement, "practice", independence_attested=True
    )


def raw_rows(workspace, table):
    with closing(sqlite3.connect(workspace / "review.db")) as db, db:
        return db.execute(f"SELECT * FROM {table} ORDER BY rowid").fetchall()


def legacy(workspace):
    with closing(sqlite3.connect(workspace / "review.db")) as db, db:
        for table in ("exclusions", "replacements", "enrollments"):
            db.execute(f"DROP TABLE {table}")
        db.execute("UPDATE meta SET value='1' WHERE key='schema_version'")


@pytest.mark.parametrize("kind", ["grade", "abstention", "rationale_only"])
def test_coached_query_rejects_all_completed_old_rows_atomically(session, kind):
    workspace, keys = session
    old = filled(review.export_packet(workspace, "alice"))
    target = old["items"][-1]
    query_id = target["query"]["id"]
    if kind == "abstention":
        target.update(grade=None, abstain_reason="Synthetic language abstention")
    elif kind == "rationale_only":
        target.update(grade=None)
    review.exclude_query(workspace, "alice", query_id, "coaching")
    for revise in (False, True):
        with pytest.raises(ValueError, match="Excluded or replaced"):
            review.import_packet(workspace, old, keys["alice"], allow_revisions=revise)
    assert review.status(workspace)["latest_submissions"] == 0
    assert raw_rows(workspace, "imports") == []
    assert all(
        row["query"]["id"] != query_id for row in review.export_packet(workspace, "alice")["items"]
    )


def test_query_exclusion_covers_other_candidates_and_preserves_unaffected_packet(session):
    workspace, keys = session
    packet = filled(review.export_packet(workspace, "alice"))
    signature = packet["signature"]
    result = review.exclude_query(workspace, "alice", "practice", "coaching")
    assert result["affected_assignments"] == 2
    assert review.exclude_query(workspace, "alice", "practice", "coaching")["recorded"] is False
    for row in packet["items"]:
        if row["query"]["id"] == "practice":
            row.update(grade=None, rationale="", abstain_reason=None)
    assert review.import_packet(workspace, packet, keys["alice"])["accepted"] == 2
    assert packet["signature"] == signature  # No editing signed assignments or immutable fields.
    current = review.status(workspace)
    assert current["integrity"]["replacement_pending"] == 2
    assert current["double_assigned_pairs"] == 4
    with pytest.raises(ValueError, match="incomplete"):
        review.export_qrels(workspace, workspace / "export")


def test_post_submission_exclusion_quarantines_without_deleting_or_rewriting_exports(session):
    workspace, keys = session
    for who in ("alice", "bob"):
        submit(workspace, keys, who)
    original = review.export_qrels(workspace, workspace / "export")
    directory = Path(original["export_directory"])
    frozen = {p.name: p.read_bytes() for p in directory.iterdir()}
    labels, receipts = raw_rows(workspace, "labels"), raw_rows(workspace, "imports")
    review.exclude_query(workspace, "alice", "practice", "coaching")
    progress = review.status(workspace)
    assert progress["latest_submissions"] == 6
    assert progress["retained_latest_submissions"] == progress["revisions_retained"] == 8
    assert progress["integrity"]["quarantined_latest_submissions"] == 2
    assert progress["resolution"]["pending"] == 2
    assert progress["resolution"]["agreement"] == 2
    assert progress["pairwise_agreement"][0]["paired_nonabstained"] == 2
    assert progress["new_human_judgments"] == 0
    assert raw_rows(workspace, "labels") == labels
    assert raw_rows(workspace, "imports") == receipts
    partial = review.export_qrels(workspace, workspace / "export", allow_partial=True)
    assert partial["exported_pairs"] == 2
    assert partial["revision_fingerprint"] != original["revision_fingerprint"]
    assert "practice\t" not in (Path(partial["export_directory"]) / "qrels.tsv").read_text()
    assert review.verify_export(workspace, Path(partial["export_directory"]))["partial"] is True
    with pytest.raises(ValueError, match="stale"):
        review.verify_export(workspace, directory)
    assert {p.name: p.read_bytes() for p in directory.iterdir()} == frozen


def test_excluded_identical_replay_is_not_accepted_as_unchanged(session):
    workspace, keys = session
    packet = filled(review.export_packet(workspace, "alice"))
    review.import_packet(workspace, packet, keys["alice"])
    review.exclude_query(workspace, "alice", "practice", "coaching")
    with pytest.raises(ValueError, match="Excluded or replaced"):
        review.import_packet(workspace, packet, keys["alice"])
    assert review.status(workspace)["import_receipts"] == 1


def test_replacement_is_blind_preserves_slots_and_requires_new_judgments(session):
    workspace, keys = session
    submit(workspace, keys, "bob", grade=0)
    original_assignments = raw_rows(workspace, "assignments")
    original_keys = (workspace / "credentials.json").read_bytes()
    review.exclude_query(workspace, "alice", "practice", "coaching")
    enrolled(workspace, keys)
    result = replace(workspace)
    assert result["replaced_assignments"] == 2
    assert raw_rows(workspace, "assignments") == original_assignments
    assert (workspace / "credentials.json").read_bytes() == original_keys
    packet = review.export_packet(workspace, "replacement")
    assert len(packet["items"]) == 2
    assert all(row["grade"] is None and row["rationale"] == "" for row in packet["items"])
    assert all(row["query"]["id"] == "practice" for row in packet["items"])
    for hidden in ("alice", "bob", "coaching", "review_labels", "exclusions", "replacements"):
        assert hidden not in json.dumps(packet)
    assert review.status(workspace)["integrity"]["replacement_pending"] == 0
    assert review.status(workspace)["resolution"]["pending"] == 4
    submit(workspace, keys, "replacement", grade=0)
    submit(workspace, keys, "alice", grade=0)
    progress = review.status(workspace)
    assert progress["double_assigned_pairs"] == 4
    assert progress["resolution"]["agreement"] == 4
    assert {tuple(p["reviewers"]) for p in progress["pairwise_agreement"]} == {
        ("alice", "bob"),
        ("bob", "replacement"),
    }
    result = review.export_qrels(workspace, workspace / "export")
    assert result["partial"] is False and result["exported_pairs"] == 4
    assert review.verify_export(workspace, Path(result["export_directory"]))["verified_current"]


def test_replacement_discovery_invalidates_old_adjudication_even_at_same_revisions(session):
    workspace, keys = session
    submit(workspace, keys, "alice", grade=1)
    submit(workspace, keys, "bob", grade=0)
    adjudication = filled(review.export_packet(workspace, "adjudicator"))
    review.import_packet(workspace, adjudication, keys["adjudicator"])
    assert review.status(workspace)["resolution"]["adjudicated"] == 4
    review.exclude_query(workspace, "alice", "practice", "label_exposure")
    assert review.export_packet(workspace, "adjudicator")["items"] == []
    enrolled(workspace, keys)
    replace(workspace)
    submit(workspace, keys, "replacement", grade=1)
    assert review.status(workspace)["resolution"]["needs_adjudication"] == 2
    with pytest.raises(ValueError, match="stale"):
        review.import_packet(workspace, adjudication, keys["adjudicator"], allow_revisions=True)
    assert len(raw_rows(workspace, "decisions")) == 4
    current = filled(review.export_packet(workspace, "adjudicator"))
    assert len(current["items"]) == 2
    assert all(
        {r["reviewer"] for r in row["review_labels"]} == {"bob", "replacement"}
        for row in current["items"]
    )
    review.import_packet(workspace, current, keys["adjudicator"], allow_revisions=True)
    assert len(raw_rows(workspace, "decisions")) == 6
    assert review.export_qrels(workspace, workspace / "export")["partial"] is False


@pytest.mark.parametrize(
    ("replacement", "attested", "error"),
    [
        ("bob", True, "already held"),
        ("adjudicator", True, "not the adjudicator"),
        ("unknown", True, "enrolled"),
        ("alice", True, "excluded"),
        ("replacement", False, "independence-attested"),
    ],
)
def test_ineligible_replacements_fail_without_any_assignment_change(
    session, replacement, attested, error
):
    workspace, keys = session
    enrolled(workspace, keys)
    review.exclude_query(workspace, "alice", "practice", "coaching")
    with pytest.raises(ValueError, match=error):
        review.replace_assignments(
            workspace, "alice", replacement, "practice", independence_attested=attested
        )
    assert raw_rows(workspace, "replacements") == []
    assert review.status(workspace)["integrity"]["replacement_pending"] == 2


def test_replacement_requires_exclusion_and_rejects_known_exposed_unassigned_person(session):
    workspace, keys = session
    enrolled(workspace, keys)
    with pytest.raises(ValueError, match="exclusion before"):
        replace(workspace)
    review.exclude_query(workspace, "replacement", "practice", "label_exposure")
    review.exclude_query(workspace, "alice", "practice", "coaching")
    with pytest.raises(ValueError, match="excluded"):
        replace(workspace)
    assert raw_rows(workspace, "replacements") == []


def test_replacement_chain_cannot_restore_excluded_source_or_reset_credential(session):
    workspace, keys = session
    review.exclude_query(workspace, "alice", "practice", "coaching")
    enrolled(workspace, keys)
    replace(workspace)
    submit(workspace, keys, "replacement")
    review.exclude_query(workspace, "replacement", "practice", "label_exposure")
    enrolled(workspace, keys, "next")
    replace(workspace, "replacement", "next")
    assert raw_rows(workspace, "labels")  # Exposed replacement history remains.
    assert review.status(workspace)["latest_submissions"] == 0
    assert review.status(workspace)["integrity"]["replacement_assignments"] == 4
    assert len(review.export_packet(workspace, "next")["items"]) == 2
    assert review.export_packet(workspace, "replacement")["items"] == []
    with pytest.raises(ValueError, match="No active"):
        replace(workspace, "alice", "next")
    with pytest.raises(ValueError, match="excluded"):
        review.replace_assignments(
            workspace, "replacement", "alice", "practice", independence_attested=True
        )
    with pytest.raises(ValueError, match="already enrolled"):
        review.enroll_reviewer(workspace, "alice", independence_attested=True)


def test_replacement_database_failure_rolls_back_whole_query(session):
    workspace, keys = session
    review.exclude_query(workspace, "alice", "practice", "coaching")
    enrolled(workspace, keys)
    with closing(sqlite3.connect(workspace / "review.db")) as db, db:
        db.execute(
            """CREATE TRIGGER synthetic_failure BEFORE INSERT ON replacements
               WHEN NEW.pair_id='pair-1' BEGIN SELECT RAISE(ABORT, 'synthetic rollback'); END"""
        )
    with pytest.raises(sqlite3.IntegrityError, match="synthetic rollback"):
        replace(workspace)
    assert raw_rows(workspace, "replacements") == []


@pytest.mark.parametrize(
    ("reviewer", "query_id", "reason", "error"),
    [
        ("unknown", "practice", "coaching", "enrolled"),
        ("adjudicator", "practice", "coaching", "not the adjudicator"),
        ("alice", "missing", "coaching", "Unknown query"),
        ("alice", "practice", "unknown", "Unsupported exclusion"),
        ("alice", "../practice", "coaching", "Invalid review identifier"),
    ],
)
def test_invalid_exclusions_do_not_write(session, reviewer, query_id, reason, error):
    workspace, _ = session
    with pytest.raises(ValueError, match=error):
        review.exclude_query(workspace, reviewer, query_id, reason)
    assert raw_rows(workspace, "exclusions") == []


def test_exclusion_is_permanent_and_audit_has_no_labels_or_secrets(session):
    workspace, keys = session
    review.exclude_query(workspace, "alice", "practice", "coaching")
    original = review.audit_history(workspace)
    with pytest.raises(ValueError, match="permanent"):
        review.exclude_query(workspace, "alice", "practice", "label_exposure")
    assert review.audit_history(workspace) == original
    text = json.dumps(original)
    assert "practice" in text and "coaching" in text
    assert not any(key in text for key in keys.values())
    assert all(hidden not in text for hidden in ("rationale", "grade", "signing_key"))


def test_explicit_migration_preserves_history_credentials_and_old_packet_signatures(session):
    workspace, keys = session
    submit(workspace, keys, "alice")
    submit(workspace, keys, "bob", grade=0)
    old = filled(review.export_packet(workspace, "adjudicator"))
    preserved = {t: raw_rows(workspace, t) for t in ("assignments", "labels", "imports", "pairs")}
    credentials = (workspace / "credentials.json").read_bytes()
    legacy(workspace)
    original_db = (workspace / "review.db").read_bytes()
    with pytest.raises(ValueError, match="migrate first"):
        review.status(workspace)
    assert (workspace / "review.db").read_bytes() == original_db
    assert review.migrate_workspace(workspace) == {"schema_version": 2, "migrated": True}
    assert review.migrate_workspace(workspace)["migrated"] is False
    assert (workspace / "credentials.json").read_bytes() == credentials
    assert all(raw_rows(workspace, t) == records for t, records in preserved.items())
    assert review.import_packet(workspace, old, keys["adjudicator"])["accepted"] == 4
    assert review.status(workspace)["resolution"]["adjudicated"] == 4


def test_failed_migration_rolls_back_new_tables_and_version(session):
    workspace, _ = session
    legacy(workspace)
    with closing(sqlite3.connect(workspace / "review.db")) as db, db:
        db.execute("CREATE TABLE replacements (collision TEXT)")
    with pytest.raises(sqlite3.OperationalError, match="already exists"):
        review.migrate_workspace(workspace)
    with closing(sqlite3.connect(workspace / "review.db")) as db, db:
        assert db.execute("SELECT value FROM meta WHERE key='schema_version'").fetchone()[0] == "1"
        assert db.execute("SELECT 1 FROM sqlite_master WHERE name='exclusions'").fetchone() is None


@pytest.mark.parametrize("version", [0, 3, "2", True, None])
def test_unknown_workspace_versions_fail_closed_without_writes(session, version):
    workspace, _ = session
    with closing(sqlite3.connect(workspace / "review.db")) as db, db:
        db.execute("UPDATE meta SET value=? WHERE key='schema_version'", (json.dumps(version),))
    original = (workspace / "review.db").read_bytes()
    for operation in (review.status, review.migrate_workspace):
        with pytest.raises(ValueError, match="Unsupported"):
            operation(workspace)
    assert (workspace / "review.db").read_bytes() == original


def test_enrollment_requires_attestation_valid_id_and_exclusive_private_file(session):
    workspace, keys = session
    with pytest.raises(ValueError, match="independence-attested"):
        review.enroll_reviewer(workspace, "replacement")
    assert not (workspace / "credentials").exists()
    with pytest.raises(ValueError, match="Invalid review identifier"):
        review.enroll_reviewer(workspace, "../escape", independence_attested=True)
    with pytest.raises(ValueError, match="already enrolled"):
        review.enroll_reviewer(workspace, "ALICE", independence_attested=True)
    path = workspace / "credentials" / "replacement.json"
    path.parent.mkdir()
    path.write_text("Synthetic existing file must survive")
    with pytest.raises(FileExistsError):
        enrolled(workspace, keys)
    assert path.read_text() == "Synthetic existing file must survive"
    assert not raw_rows(workspace, "enrollments")
    assert all(row[0] != "replacement" for row in raw_rows(workspace, "reviewers"))


def test_initialization_refuses_case_aliases_that_would_share_packet_directory(session, tmp_path):
    workspace, _ = session
    pool = workspace.parent / "synthetic-pool.json"
    for reviewers, adjudicator in ((["a", "A"], "b"), (["a", "b"], "B")):
        with pytest.raises(ValueError, match="distinct ignoring case"):
            review.initialize(tmp_path / "bad-case", pool, reviewers, adjudicator, synthetic=True)


def test_failed_credential_write_rolls_back_enrollment_and_removes_only_new_file(
    session, monkeypatch
):
    workspace, _ = session

    def fail(*args):
        raise OSError("Synthetic credential permission failure")

    monkeypatch.setattr(Path, "chmod", fail)
    with pytest.raises(OSError, match="permission failure"):
        review.enroll_reviewer(workspace, "replacement", independence_attested=True)
    assert not (workspace / "credentials" / "replacement.json").exists()
    assert not raw_rows(workspace, "enrollments")
    assert all(row[0] != "replacement" for row in raw_rows(workspace, "reviewers"))


def test_identical_import_receipt_gets_new_immutable_export_and_stales_old_snapshot(session):
    workspace, keys = session
    for who in ("alice", "bob"):
        submit(workspace, keys, who)
    first = review.export_qrels(workspace, workspace / "export")
    assert review.export_qrels(workspace, workspace / "export") == first
    old = Path(first["export_directory"])
    raw = (old / "qrels.tsv").read_bytes()
    assert submit(workspace, keys, "alice")["unchanged"] == 4
    second = review.export_qrels(workspace, workspace / "export")
    assert second["revision_fingerprint"] != first["revision_fingerprint"]
    assert (old / "qrels.tsv").read_bytes() == raw
    assert (Path(second["export_directory"]) / "qrels.tsv").read_bytes() == raw
    with pytest.raises(ValueError, match="stale"):
        review.verify_export(workspace, old)


@pytest.mark.parametrize("name", ["qrels.tsv", "integrity.json", "coverage.json"])
def test_export_verifier_rejects_tampering(session, name):
    workspace, _ = session
    result = review.export_qrels(workspace, workspace / "export", allow_partial=True)
    directory = Path(result["export_directory"])
    target = directory / name
    target.write_text("{}" if name.endswith(".json") else "changed\n")
    with pytest.raises(ValueError, match="stale|contents"):
        review.verify_export(workspace, directory)


def test_export_uses_consistent_read_snapshot_during_concurrent_exclusion(session, monkeypatch):
    workspace, keys = session
    for who in ("alice", "bob"):
        submit(workspace, keys, who)
    with closing(sqlite3.connect(workspace / "review.db")) as db, db:
        db.execute("PRAGMA journal_mode=WAL")
    original_status = review._status

    def overlapping_write(db):
        progress = original_status(db)
        review.exclude_query(workspace, "alice", "practice", "coaching")
        return progress

    monkeypatch.setattr(review, "_status", overlapping_write)
    old = review.export_qrels(workspace, workspace / "export")
    directory = Path(old["export_directory"])
    assert old["partial"] is False and old["exported_pairs"] == 4
    assert old["integrity"]["query_exclusions"] == 0
    assert json.loads((directory / "integrity.json").read_bytes())["exclusions"] == []
    monkeypatch.setattr(review, "_status", original_status)
    assert review.status(workspace)["resolution"]["pending"] == 2
    with pytest.raises(ValueError, match="stale"):
        review.verify_export(workspace, directory)


def test_cli_workflow_keeps_credentials_out_of_stdout_and_packets(session, capsys):
    workspace, keys = session

    def command(*args):
        assert review.main([*args, "--workspace", str(workspace)]) == 0
        return json.loads(capsys.readouterr().out)

    assert command("migrate")["migrated"] is False
    command("exclude", "--reviewer", "alice", "--query-id", "practice", "--reason", "coaching")
    result = command("enroll", "--reviewer", "replacement", "--independence-attested")
    key = json.loads(Path(result["credential_file"]).read_bytes())["replacement"]
    assert key not in json.dumps(result)
    command(
        "replace",
        "--reviewer",
        "alice",
        "--replacement",
        "replacement",
        "--query-id",
        "practice",
        "--independence-attested",
    )
    result = command("export", "--reviewer", "replacement")
    packet_file = Path(result["directory"]) / "packet.json"
    assert key not in packet_file.read_text()
    assert not any(token in packet_file.read_text() for token in keys.values())
    result = command("finalize", "--allow-partial")
    verified = command("verify-export", "--export-directory", result["export_directory"])
    assert verified["verified_current"] is True
    assert command("audit")["exclusions"][0]["reason"] == "coaching"
    assert command("status")["new_human_judgments"] == 0
