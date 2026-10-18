"""ANV-023: synthetic mechanics only, never evidence of model quality."""

import copy
import json
from pathlib import Path

import httpx
import pytest

from anvesha.eval_data import EvaluationSpec, load_spec
from anvesha.eval_metrics import query_metrics
from anvesha.llm import LLMConfig, LLMReranker
from anvesha.llm_evaluation import (
    MODEL_POLICY,
    PROTOCOL,
    measure_query,
    planned_protocol,
    read_protocol,
    summarize,
    validate_backend,
    validate_records,
)
from anvesha.store import Store


@pytest.fixture
def synthetic():
    spec = EvaluationSpec(
        {},
        [{"id": "q1", "split": "development"}, {"id": "q2", "split": "evaluation"}],
        {"q1": {"b": 1}, "q2": {"b": 1}},
        frozenset({"a", "b", "c"}),
    )
    protocol = {
        "query_ids": {"development": ["q1"], "evaluation": ["q2"]},
        "candidate_limit": 2,
        "retrieval_depth": 50,
        "bootstrap_samples": 1000,
    }
    rows = []
    for query in spec.queries:
        before, after = ["a", "b", "c"], ["b", "a", "c"]
        rows.append(
            {
                "query_id": query["id"],
                "split": query["split"],
                "lexical": {
                    "documents": before,
                    "metrics": query_metrics(before, {"b": 1}),
                    "state": "completed",
                    "warnings": [],
                    "elapsed_ms": 1.0,
                },
                "llm": {
                    "documents": after,
                    "metrics": query_metrics(after, {"b": 1}),
                    "state": "completed",
                    "warnings": [],
                    "elapsed_ms": 100.0,
                    "applied": True,
                },
            }
        )
    return spec, protocol, rows


def test_paired_scores_and_oracle_are_analytically_correct(synthetic):
    spec, protocol, rows = synthetic
    result = summarize(spec, protocol, rows)["evaluation"]
    assert result["paired_ndcg10_delta"]["mean"] == pytest.approx(0.36907, abs=1e-6)
    assert result["mean_oracle_prefix_ndcg10"] == 1
    assert result["ndcg10_wins_ties_losses"] == {"wins": 1, "ties": 0, "losses": 0}
    assert result["model_applied"] == 1 and result["model_fallbacks"] == 0
    assert result["metrics"]["llm"]["recall@50"] == result["metrics"]["lexical"]["recall@50"]


@pytest.mark.parametrize("failure", ["fallback", "worker_failed"])
def test_failures_are_included_not_filtered_out(synthetic, failure):
    spec, protocol, rows = synthetic
    item = rows[-1]["llm"]
    if failure == "fallback":
        item.update(
            state="completed_partial",
            warnings=["llm:timeout"],
            applied=False,
            documents=["a", "b", "c"],
        )
    else:
        item.update(state="failed", applied=False, documents=[])
    item["metrics"] = query_metrics(item["documents"], {"b": 1})
    result = summarize(spec, protocol, rows)["evaluation"]
    assert result["queries"] == 1 and result["model_applied"] == 0
    if failure == "fallback":
        assert result["model_fallbacks"] == 1 and result["paired_ndcg10_delta"]["mean"] == 0
    else:
        assert result["worker_failures"] == 1 and result["paired_ndcg10_delta"]["mean"] < 0


@pytest.mark.parametrize(
    "change",
    [
        "missing",
        "duplicate",
        "wrong_split",
        "wrong_metrics",
        "unknown_id",
        "duplicate_id",
        "changed_tail",
        "invented_applied",
        "nan_time",
        "unsanitized_warning",
        "partial_changed",
    ],
)
def test_corruption_and_unfair_comparisons_fail_closed(synthetic, change):
    spec, protocol, rows = synthetic
    item = rows[-1]["llm"]
    if change == "missing":
        rows.pop()
    elif change == "duplicate":
        rows.append(copy.deepcopy(rows[-1]))
    elif change == "wrong_split":
        rows[-1]["split"] = "development"
    elif change == "wrong_metrics":
        item["metrics"]["ndcg@10"] = 0
    elif change == "unknown_id":
        item["documents"] = ["unknown"]
    elif change == "duplicate_id":
        item["documents"] = ["b", "b", "c"]
    elif change == "changed_tail":
        item["documents"] = ["b", "c", "a"]
        item["metrics"] = query_metrics(item["documents"], {"b": 1})
    elif change == "invented_applied":
        item["applied"] = False
    elif change == "nan_time":
        item["elapsed_ms"] = float("nan")
    elif change == "unsanitized_warning":
        item["warnings"] = ["private response body"]
    elif change == "partial_changed":
        item.update(state="completed_partial", warnings=["llm:timeout"], applied=False)
    with pytest.raises(ValueError):
        summarize(spec, protocol, rows)


def test_checkpoint_prefix_is_validated_before_resuming(synthetic):
    spec, protocol, rows = synthetic
    assert validate_records(spec, protocol, rows[:1], complete=False)
    with pytest.raises(ValueError):
        validate_records(spec, protocol, rows[1:], complete=False)
    rows[0]["llm"]["metrics"]["ndcg@10"] = 0
    with pytest.raises(ValueError):
        validate_records(spec, protocol, rows[:1], complete=False)


def test_frozen_real_query_selection_does_not_consult_labels():
    spec = load_spec(Path(__file__).resolve().parents[1] / "benchmarks/scifact-v1")
    protocol = read_protocol(PROTOCOL, spec)
    changed = EvaluationSpec(spec.manifest, spec.queries, {}, spec.document_ids)
    assert planned_protocol(changed) == protocol
    assert len(protocol["query_ids"]["development"]) == 4
    assert len(protocol["query_ids"]["evaluation"]) == 24
    assert not set(protocol["query_ids"]["development"]) & set(protocol["query_ids"]["evaluation"])


@pytest.mark.parametrize("invalid", [False, True])
def test_actual_worker_measurement_uses_candidate_only_output_and_visible_fallback(
    tmp_path, invalid
):
    store = Store(tmp_path / "fixture.db")
    store.initialize()
    url_to_id = {}
    for did in ("a", "b", "c"):
        url = "https://example.org/synthetic/" + did
        url_to_id[url] = did
        store.upsert_document(
            {
                "id": did,
                "url": url,
                "title": "alpha " + did,
                "content": "alpha synthetic fixture",
                "license": "Apache-2.0",
                "attribution": "synthetic test, not quality evidence",
            }
        )
    calls = []

    def respond(request):
        body = json.loads(request.content)
        supplied = json.loads(body["messages"][1]["content"])
        assert set(supplied) == {"original_query", "candidates"}
        assert (
            "qrels" not in request.content.decode() and "https://" not in request.content.decode()
        )
        ids = [row["id"] for row in supplied["candidates"]]
        calls.append(ids)
        return httpx.Response(
            200,
            json={
                "choices": [
                    {
                        "finish_reason": "stop",
                        "message": {
                            "role": "assistant",
                            "content": json.dumps(
                                {"ranked_ids": ["invented"] if invalid else ids[::-1]}
                            ),
                        },
                    }
                ]
            },
        )

    config = LLMConfig(model="synthetic", candidate_limit=2)
    row = measure_query(
        store,
        {"id": "q", "split": "development", "text": "alpha"},
        url_to_id,
        config,
        LLMReranker(config, transport=httpx.MockTransport(respond)),
    )
    assert len(calls) == 1  # Lexical control never calls the model.
    assert set(row["lexical"]["documents"]) == set(row["llm"]["documents"])
    if invalid:
        assert row["llm"]["state"] == "completed_partial" and not row["llm"]["applied"]
        assert row["llm"]["warnings"] == ["llm:invalid_response"]
        assert row["llm"]["documents"] == row["lexical"]["documents"]
    else:
        assert row["llm"]["applied"]
        assert row["llm"]["documents"][:2] == row["lexical"]["documents"][:2][::-1]
        assert row["llm"]["documents"][2:] == row["lexical"]["documents"][2:]


def test_backend_metadata_must_not_smuggle_private_fields():
    with pytest.raises(ValueError, match="allowlisted"):
        validate_backend(
            {"raw_query": "private", "api_key": "private"},
            json.loads(MODEL_POLICY.read_bytes()),
            {},
        )
