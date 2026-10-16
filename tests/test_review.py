"""ANV-020: all labels here are synthetic workflow tests, never human evidence."""

import copy
import json
from pathlib import Path

import pytest

from anvesha.eval_data import json_bytes
from anvesha.review import (
    export_packet,
    export_qrels,
    import_packet,
    initialize,
    status,
)
from anvesha.review_form import SCRIPT, STYLE, _hash, render_form


@pytest.fixture
def pool_file(tmp_path):
    pairs = []
    for index in range(8):
        pairs.append(
            {
                "pair_id": f"pair-{index}",
                "query": {
                    "id": f"q-{index}",
                    "text": f"question {index}",
                    "constraints": [],
                    "language": "en" if index < 6 else "es",
                    "stratum": "factual",
                    "split": "development" if index < 7 else "holdout",
                },
                "document": {
                    "id": f"d-{index}",
                    "title": f"Document {index}",
                    "text": "Synthetic first-party test passage",
                    "url": "https://example.org/test",
                    "language": "en",
                    "license": "Apache-2.0",
                    "attribution": "Anvesha test",
                },
            }
        )
    pool = {
        "schema_version": 1,
        "dataset": "synthetic-fixture",
        "snapshot_sha256": "fixture",
        "ranking_fingerprint": "fixture-rankings",
        "rights_manifest": "first-party test fixture",
        "query_count": 8,
        "empty_query_ids": [],
        "rubric": {"id": "test-binary", "grades": {"0": "No", "1": "Yes"}},
        "pairs": pairs,
    }
    path = tmp_path / "pool.json"
    path.write_bytes(json_bytes(pool))
    return path


@pytest.fixture
def session(tmp_path, pool_file):
    workspace = tmp_path / "private"
    initialize(workspace, pool_file, ["alice", "bob"], "carol", double_fraction=1, synthetic=True)
    keys = json.loads((workspace / "credentials.json").read_bytes())
    return workspace, keys


def fill(packet, grade=1):
    packet = copy.deepcopy(packet)
    packet["human_attestation"] = True  # Simulated attestation in a synthetic-only session.
    for row in packet["items"]:
        row["grade"] = grade
        row["rationale"] = "Synthetic test rationale"
    return packet


def test_empty_session_is_blinded_and_default_holdout_is_reserved(session):
    workspace, _ = session
    report = status(workspace)
    assert report["pairs"] == 7
    assert report["double_assigned_pairs"] == 7
    assert report["new_human_judgments"] == report["latest_submissions"] == 0
    assert report["pairwise_agreement"] == []
    packet = export_packet(workspace, "alice")
    assert packet["human_attestation"] is False
    assert all(row["grade"] is None for row in packet["items"])
    assert all(row["query"]["id"] != "q-7" for row in packet["items"])
    text = json.dumps(packet)
    for hidden in ('"split"', '"engine"', '"stratum"', '"relevance"', '"review_labels"', '"token"'):
        assert hidden not in text


def test_holdout_release_role_and_workspace_guards(tmp_path, pool_file, session):
    workspace, _ = session
    with pytest.raises(ValueError, match="overwrite"):
        initialize(workspace, pool_file, ["a", "b"], "c")
    with pytest.raises(ValueError, match="separate"):
        initialize(tmp_path / "bad", pool_file, ["a", "b"], "a")
    with pytest.raises(ValueError, match="release-holdout"):
        initialize(tmp_path / "holdout", pool_file, ["a", "b"], "c", split="holdout")
    report = initialize(
        tmp_path / "holdout",
        pool_file,
        ["a", "b"],
        "c",
        split="holdout",
        release_holdout=True,
        synthetic=True,
    )
    assert report["pairs"] == 1


def test_deterministic_pilot_and_language_routing(tmp_path, pool_file):
    first, second = tmp_path / "one", tmp_path / "two"
    for workspace in (first, second):
        initialize(
            workspace, pool_file, ["a", "b"], "c", max_pairs=3, double_fraction=0.2, synthetic=True
        )
    p1, p2 = export_packet(first, "a"), export_packet(second, "a")
    assert [i["pair_id"] for i in p1["items"]] == [i["pair_id"] for i in p2["items"]]
    assert status(first)["pairs"] == 3
    assert status(first)["double_assigned_pairs"] == 2  # At least one per language/stratum.
    report = initialize(
        tmp_path / "spanish", pool_file, ["a", "b"], "c", languages=["es"], synthetic=True
    )
    assert report["pairs"] == 1
    assert report["languages"] == ["es"]


def test_credentials_attestation_and_tampered_packets_are_rejected(session):
    workspace, keys = session
    packet = fill(export_packet(workspace, "alice"))
    with pytest.raises(ValueError, match="credential"):
        import_packet(workspace, packet, keys["bob"])
    unconfirmed = {**packet, "human_attestation": False}
    with pytest.raises(ValueError, match="attestation"):
        import_packet(workspace, unconfirmed, keys["alice"])
    for change in ("text", "assignment", "rubric", "role"):
        bad = copy.deepcopy(packet)
        if change == "text":
            bad["items"][0]["document"]["text"] = "Changed evidence"
        elif change == "assignment":
            bad["items"] = bad["items"][:-1]
        elif change == "rubric":
            bad["rubric"]["grades"]["1"] = "Promote everything"
        else:
            bad["role"] = "adjudicator"
        with pytest.raises(ValueError):
            import_packet(workspace, bad, keys["alice"])
    assert status(workspace)["latest_submissions"] == 0


@pytest.mark.parametrize("items", [None, {}, [None], [{"pair_id": "missing-fields"}]])
def test_malformed_packet_shapes_fail_without_partial_writes(session, items):
    workspace, keys = session
    packet = fill(export_packet(workspace, "alice"))
    packet["items"] = items
    with pytest.raises(ValueError, match="schema|collection"):
        import_packet(workspace, packet, keys["alice"])
    assert status(workspace)["latest_submissions"] == 0


@pytest.mark.parametrize("bad", [True, -1, 2, "1", 0.5])
def test_invalid_grade_rolls_back_whole_packet(session, bad):
    workspace, keys = session
    packet = fill(export_packet(workspace, "alice"))
    packet["items"][-1]["grade"] = bad
    with pytest.raises(ValueError, match="integer"):
        import_packet(workspace, packet, keys["alice"])
    assert status(workspace)["latest_submissions"] == 0


def test_unfinished_is_not_negative_and_abstention_requires_adjudication(session):
    workspace, keys = session
    packet = export_packet(workspace, "alice")
    packet["human_attestation"] = True
    with pytest.raises(ValueError, match="no completed"):
        import_packet(workspace, packet, keys["alice"])
    packet["items"][0].update(
        grade=None, rationale="Cannot read passage", abstain_reason="Language"
    )
    assert import_packet(workspace, packet, keys["alice"])["accepted"] == 1
    import_packet(workspace, fill(export_packet(workspace, "bob")), keys["bob"])
    report = status(workspace)
    assert report["reviewers"]["alice"]["abstained"] == 1
    assert report["resolution"]["needs_adjudication"] == 1
    assert report["resolution"]["pending"] == 6
    assert len(export_packet(workspace, "carol")["items"]) == 1
    with pytest.raises(ValueError, match="incomplete"):
        export_qrels(workspace, workspace / "export")
    partial = export_qrels(workspace, workspace / "export", allow_partial=True)
    assert partial["partial"] is True and partial["exported_pairs"] == 0


def test_agreement_adjudication_idempotency_and_immutable_exports(session):
    workspace, keys = session
    alice = fill(export_packet(workspace, "alice"))
    bob = fill(export_packet(workspace, "bob"))
    bob["items"][0]["grade"] = 0
    assert import_packet(workspace, alice, keys["alice"])["accepted"] == 7
    assert import_packet(workspace, alice, keys["alice"])["unchanged"] == 7
    import_packet(workspace, bob, keys["bob"])
    before = status(workspace)
    assert before["resolution"]["agreement"] == 6
    assert before["resolution"]["needs_adjudication"] == 1
    assert before["pairwise_agreement"][0]["agreement"] == pytest.approx(6 / 7)
    adjudication = fill(export_packet(workspace, "carol"), grade=0)
    assert len(adjudication["items"][0]["review_labels"]) == 2
    import_packet(workspace, adjudication, keys["carol"])
    result = export_qrels(workspace, workspace / "export")
    assert result["partial"] is False and result["exported_pairs"] == 7
    assert result["new_human_judgments"] == 0  # Synthetic sessions never count as human evidence.
    path = Path(result["export_directory"]) / "qrels.tsv"
    original = path.read_bytes()
    revised = fill(export_packet(workspace, "alice"), grade=0)
    with pytest.raises(ValueError, match="--revise"):
        import_packet(workspace, revised, keys["alice"])
    import_packet(workspace, revised, keys["alice"], allow_revisions=True)
    assert status(workspace)["revisions_retained"] == 21
    assert path.read_bytes() == original
    with pytest.raises(ValueError, match="incomplete"):
        export_qrels(workspace, workspace / "export")
    newer = export_qrels(workspace, workspace / "export", allow_partial=True)
    assert newer["export_directory"] != result["export_directory"]
    assert path.read_bytes() == original


def test_stale_revision_and_stale_adjudication_are_rejected(session):
    workspace, keys = session
    old = fill(export_packet(workspace, "alice"), grade=1)
    import_packet(workspace, old, keys["alice"])
    import_packet(workspace, fill(export_packet(workspace, "bob"), grade=0), keys["bob"])
    adjudication = fill(export_packet(workspace, "carol"))
    fresh = fill(export_packet(workspace, "alice"), grade=0)
    import_packet(workspace, fresh, keys["alice"], allow_revisions=True)
    old["items"][0]["grade"] = 0
    with pytest.raises(ValueError, match="Stale"):
        import_packet(workspace, old, keys["alice"], allow_revisions=True)
    with pytest.raises(ValueError, match="stale"):
        import_packet(workspace, adjudication, keys["carol"])


def test_kappa_is_undefined_for_constant_agreement(session):
    workspace, keys = session
    for reviewer in ("alice", "bob"):
        import_packet(workspace, fill(export_packet(workspace, reviewer)), keys[reviewer])
    pair = status(workspace)["pairwise_agreement"][0]
    assert pair["agreement"] == 1
    assert pair["cohen_kappa"] is None and pair["undefined_reason"]


def test_kappa_matches_hand_computed_nonconstant_case(session):
    workspace, keys = session
    grades = {"alice": [0, 0, 1, 1], "bob": [0, 0, 1, 0]}
    for reviewer in grades:
        packet = export_packet(workspace, reviewer)
        packet["human_attestation"] = True
        for row in packet["items"]:
            number = int(row["pair_id"].split("-")[1])
            if number < 4:
                row.update(grade=grades[reviewer][number], rationale="Synthetic agreement case")
        import_packet(workspace, packet, keys[reviewer])
    pair = status(workspace)["pairwise_agreement"][0]
    assert pair["paired_nonabstained"] == 4
    assert pair["agreement"] == 0.75
    assert pair["cohen_kappa"] == 0.5


def test_multiple_reviewers_report_each_pair_separately(tmp_path, pool_file):
    workspace = tmp_path / "three-reviewers"
    initialize(workspace, pool_file, ["a", "b", "c"], "d", double_fraction=1, synthetic=True)
    keys = json.loads((workspace / "credentials.json").read_bytes())
    for reviewer in ("a", "b", "c"):
        import_packet(workspace, fill(export_packet(workspace, reviewer)), keys[reviewer])
    pairs = status(workspace)["pairwise_agreement"]
    assert len(pairs) == 3
    assert sum(row["paired_nonabstained"] for row in pairs) == 7


def test_cli_exports_form_and_authenticates_submissions(tmp_path, pool_file, monkeypatch, capsys):
    from anvesha.review import main

    workspace = tmp_path / "cli-private"
    assert (
        main(
            [
                "init",
                "--workspace",
                str(workspace),
                "--pool",
                str(pool_file),
                "--reviewers",
                "a",
                "b",
                "--adjudicator",
                "c",
                "--synthetic-test",
            ]
        )
        == 0
    )
    keys = json.loads((workspace / "credentials.json").read_bytes())
    assert main(["export", "--workspace", str(workspace), "--reviewer", "a"]) == 0
    packet_path = workspace / "packets/a/packet.json"
    packet = fill(json.loads(packet_path.read_bytes()))
    packet_path.write_bytes(json_bytes(packet))
    monkeypatch.setenv("ANVESHA_REVIEW_TOKEN", keys["a"])
    assert main(["import", "--workspace", str(workspace), "--packet", str(packet_path)]) == 0
    assert (workspace / "packets/a/review.html").is_file()
    assert status(workspace)["import_receipts"] == 1
    stdout = capsys.readouterr().out
    assert not any(key in stdout for key in keys.values())
    assert all(row["grade"] is None for row in export_packet(workspace, "b")["items"])


def test_conflicting_pair_snapshots_and_external_exports_fail(tmp_path, pool_file, session):
    data = json.loads(pool_file.read_bytes())
    duplicate = copy.deepcopy(data["pairs"][0])
    duplicate["pair_id"] = "different-pair-id"
    data["pairs"].append(duplicate)
    pool_file.write_bytes(json_bytes(data))
    with pytest.raises(ValueError, match="Duplicate query/document"):
        initialize(tmp_path / "bad", pool_file, ["a", "b"], "c")
    workspace, _ = session
    with pytest.raises(ValueError, match="inside"):
        export_qrels(workspace, tmp_path / "public", allow_partial=True)


def test_form_escapes_untrusted_content_and_has_no_external_requests(session):
    workspace, _ = session
    packet = export_packet(workspace, "alice")
    attack = '</script><img src="https://example.org/track" onerror="alert(1)">'
    packet["items"][0]["document"]["text"] = attack
    page = render_form(packet)
    assert attack not in page and "<img" not in page
    assert _hash(SCRIPT) in page and _hash(STYLE) in page
    assert "connect-src &#x27;none&#x27;" in page
    assert "innerHTML" not in SCRIPT and "fetch(" not in SCRIPT
    assert 'type="checkbox"' in page and 'id="attest"' in page
