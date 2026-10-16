"""ANV-020: real input contracts and synthetic offline retrieval workflow mechanics."""

import copy
import json
from pathlib import Path

import httpx
import pytest

from anvesha.eval_data import digest, json_bytes, json_lines
from anvesha.intent_evaluation import run, verify
from anvesha.review_data import INTENTS, ReviewSnapshot, load_documents, load_snapshot


@pytest.fixture
def intent_fixture(tmp_path):
    benchmark, data, output = (tmp_path / name for name in ("benchmark", "data", "report"))
    benchmark.mkdir()
    data.mkdir()
    queries, docs, mappings = [], [], []
    topics = [
        {"id": "Alpha", "domain": "history", "split": "development"},
        {"id": "Beta", "domain": "geography", "split": "holdout"},
    ]
    for topic in topics:
        for lang in ("en", "es", "hi"):
            did = f"{lang}-{topic['id']}"
            qid = "q-" + did
            docs.append(
                {
                    "id": did,
                    "title": topic["id"],
                    "text": topic["id"] + " passage",
                    "url": f"https://example.org/test#{did}",
                    "language": lang,
                    "group": topic["id"],
                    "domain": topic["domain"],
                    "license": "Apache-2.0",
                    "attribution": "Anvesha synthetic tests",
                }
            )
            queries.append(
                {
                    "id": qid,
                    "text": topic["id"] + " " + lang,
                    "language": lang,
                    "group": topic["id"],
                    "domain": topic["domain"],
                    "split": topic["split"],
                    "stratum": "factual" if lang == "en" else "multilingual",
                    "origin": "published_xquad_question",
                    "upstream_id": topic["id"],
                    "constraints": [],
                    "judgment_origin": "derived_answer_context_mapping",
                }
            )
            mappings.append({"query_id": qid, "document_id": did, "relevance": 1})
    draft = {
        **queries[0],
        "id": "draft-1",
        "text": "Compare Alpha eras",
        "stratum": "comparison",
        "origin": "ai_authored_draft",
        "judgment_origin": "unjudged",
    }
    draft.pop("upstream_id")
    queries.append(draft)
    contents = {
        "queries.jsonl": json_lines(queries),
        "answer_contexts.jsonl": json_lines(mappings),
        "topics.json": json_bytes(topics),
        "drafts.jsonl": json_lines([draft]),
        "document_ids.txt": ("\n".join(sorted(d["id"] for d in docs)) + "\n").encode(),
    }
    raw = json_lines(docs)
    manifest = {
        "schema_version": 1,
        "id": "xquad-intents-v1",
        "query_count": len(queries),
        "document_count": len(docs),
        "draft_count": 1,
        "answer_context_mappings": 6,
        "corpus_sha256": digest(raw),
        "files": {name: {"sha256": digest(value)} for name, value in contents.items()},
    }
    for name, value in contents.items():
        (benchmark / name).write_bytes(value)
    (benchmark / "manifest.json").write_bytes(json_bytes(manifest))
    (data / "corpus.jsonl").write_bytes(raw)
    return benchmark, data, output


def test_published_corpus_has_broader_topics_languages_and_disjoint_groups():
    snapshot = load_snapshot(Path("benchmarks/xquad-intents-v1"))
    assert len(snapshot.queries) == 756
    assert len(snapshot.document_ids) == len(snapshot.mappings) == 720
    assert {q["stratum"] for q in snapshot.queries if q["origin"] == "ai_authored_draft"} == INTENTS
    assert {q["language"] for q in snapshot.queries} == {"en", "es", "hi"}
    assert len({q["domain"] for q in snapshot.queries}) == 6
    for group in {q["group"] for q in snapshot.queries}:
        assert len({q["split"] for q in snapshot.queries if q["group"] == group}) == 1
    for source_id in {q["upstream_id"] for q in snapshot.queries if "upstream_id" in q}:
        aligned = [q for q in snapshot.queries if q.get("upstream_id") == source_id]
        assert len(aligned) == 3
        assert len({q["split"] for q in aligned}) == 1
    assert (
        sum(
            q["domain"] != "science_health" and q["origin"] == "published_xquad_question"
            for q in snapshot.queries
        )
        == 585
    )


@pytest.mark.parametrize("bad", ["hash", "split", "provenance", "boolean_grade"])
def test_modified_snapshot_is_rejected(intent_fixture, bad):
    benchmark, _, _ = intent_fixture
    filename = "answer_contexts.jsonl" if bad == "boolean_grade" else "queries.jsonl"
    rows = [json.loads(line) for line in (benchmark / filename).read_bytes().splitlines()]
    if bad == "split":
        rows[0]["split"] = "holdout"
    elif bad == "provenance":
        rows[-1]["judgment_origin"] = "new_human_judgment"
    elif bad == "boolean_grade":
        rows[0]["relevance"] = True
    else:
        rows[0]["text"] += "modified"
    raw = json_lines(rows)
    (benchmark / filename).write_bytes(raw)
    if bad != "hash":
        manifest = json.loads((benchmark / "manifest.json").read_bytes())
        manifest["files"][filename]["sha256"] = digest(raw)
        (benchmark / "manifest.json").write_bytes(json_bytes(manifest))
    with pytest.raises(ValueError):
        load_snapshot(benchmark)


def test_actual_worker_pool_and_report_are_offline_and_do_not_invent_draft_labels(
    intent_fixture, monkeypatch
):
    def forbid_network(*args, **kwargs):
        pytest.fail("Offline workflow attempted network")

    monkeypatch.setattr(httpx.Client, "send", forbid_network)
    monkeypatch.setattr(httpx.AsyncClient, "send", forbid_network)
    benchmark, data, output = intent_fixture
    summary = run(benchmark, data, output)
    assert summary["queries"] == 7 and summary["runs"] == 21
    assert summary["new_human_judgments"] == 0
    assert summary["draft_queries_excluded_from_metrics"] == 1
    assert verify(benchmark, output) == summary
    pool = json.loads((data / "candidate-pool.json").read_bytes())
    assert pool["pairs"] and pool["query_count"] == 7
    assert all("engine" not in row and "grade" not in row for row in pool["pairs"])
    original = (output / "summary.json").read_bytes()
    with pytest.raises(ValueError, match="preserved"):
        run(benchmark, data, output, expected="different")
    assert (output / "summary.json").read_bytes() == original
    changed = {**summary, "new_human_judgments": 500}
    (output / "summary.json").write_bytes(json_bytes(changed))
    with pytest.raises(ValueError, match="scope"):
        verify(benchmark, output)


def test_document_hash_mismatch_is_rejected(intent_fixture):
    benchmark, data, _ = intent_fixture
    snapshot = load_snapshot(benchmark)
    assert isinstance(snapshot, ReviewSnapshot)
    assert len(load_documents(snapshot, data)) == 6
    raw = copy.deepcopy((data / "corpus.jsonl").read_bytes())
    (data / "corpus.jsonl").write_bytes(raw + b" ")
    with pytest.raises(ValueError, match="checksum"):
        load_documents(snapshot, data)
