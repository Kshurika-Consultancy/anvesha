"""ANV-024: label-blind selection, complete comparisons and resumable mechanics."""

import copy
import json

import httpx
import pytest

from anvesha import ranking_experiment as experiment
from anvesha.eval_data import EvaluationSpec, json_bytes, json_lines, load_spec
from anvesha.eval_metrics import query_metrics


def test_new_sample_is_label_blind_and_excludes_every_previous_pilot_query():
    spec = load_spec(experiment.ROOT / "benchmarks/scifact-v1")
    planned = experiment.read_protocol(spec)
    without_labels = EvaluationSpec(spec.manifest, spec.queries, {}, spec.document_ids)
    assert planned == experiment.planned_protocol(without_labels)
    old = json.loads(experiment.PREVIOUS.read_bytes())
    before = {qid for ids in old["query_ids"].values() for qid in ids}
    after = {qid for ids in planned["query_ids"].values() for qid in ids}
    assert len(after) == 20 and not before & after
    plan = experiment.schedule(planned)
    assert len(plan) == 40 and [s for _, s in plan[:4]] == [
        "listwise",
        "pointwise",
        "pointwise",
        "listwise",
    ]


@pytest.fixture
def fixture_data():
    spec = EvaluationSpec(
        {"corpus_sha256": "0" * 64, "files": {}},
        [
            {"id": "q1", "split": "development", "text": "alpha"},
            {"id": "q2", "split": "evaluation", "text": "alpha"},
        ],
        {"q1": {"b": 1}, "q2": {"b": 1}},
        frozenset({"a", "b", "c"}),
    )
    protocol = {
        "id": experiment.EXPERIMENT,
        "query_ids": {"development": ["q1"], "evaluation": ["q2"]},
        "retrieval_depth": 50,
        "candidate_limit": 2,
        "timeout_seconds": 1,
        "output_format": "json_schema",
        "bootstrap_samples": 1000,
        "run_budget_seconds": 60,
        "cpu_threads": 6,
        "context_tokens": 8192,
        "generation_seed": 20261018,
    }
    records = []
    for qid, strategy in experiment.schedule(protocol):
        lexical, ranked = ["a", "b", "c"], ["b", "a", "c"]
        records.append(
            {
                "strategy": strategy,
                "model_calls": 1 if strategy == "listwise" else 2,
                "measurement": {
                    "query_id": qid,
                    "split": "development" if qid == "q1" else "evaluation",
                    "lexical": {
                        "documents": lexical,
                        "metrics": query_metrics(lexical, {"b": 1}),
                        "state": "completed",
                        "warnings": [],
                        "elapsed_ms": 1,
                    },
                    "llm": {
                        "documents": ranked,
                        "metrics": query_metrics(ranked, {"b": 1}),
                        "state": "completed",
                        "warnings": [],
                        "elapsed_ms": 10,
                        "applied": True,
                    },
                },
            }
        )
    return spec, protocol, records


def test_paired_contract_comparison_and_call_counts(fixture_data):
    spec, protocol, records = fixture_data
    result = experiment.summarize_comparison(spec, protocol, records)
    assert result["paired_pointwise_minus_listwise_ndcg10"]["evaluation"]["mean"] == 0
    assert result["attempted_model_calls"] == {"listwise": 2, "pointwise": 4}
    assert result["profiles"]["pointwise"]["evaluation"]["model_applied"] == 1
    assert experiment.validate(spec, protocol, records[:1], complete=False)


@pytest.mark.parametrize(
    "corruption", ["missing", "duplicate", "order", "payload", "calls", "metrics"]
)
def test_invalid_comparisons_and_private_payload_fields_fail_closed(fixture_data, corruption):
    spec, protocol, original = fixture_data
    records = copy.deepcopy(original)
    if corruption == "missing":
        records.pop()
    elif corruption == "duplicate":
        records[-1] = copy.deepcopy(records[-2])
    elif corruption == "order":
        records.reverse()
    elif corruption == "payload":
        records[0]["raw_response"] = "private"
    elif corruption == "calls":
        records[0]["model_calls"] = 0
    else:
        records[0]["measurement"]["llm"]["metrics"]["ndcg@10"] = -1
    with pytest.raises(ValueError):
        experiment.summarize_comparison(spec, protocol, records)


def test_run_requires_development_rejects_source_drift_and_resumes_without_repeating_calls(
    tmp_path, monkeypatch, fixture_data
):
    spec, protocol, _ = fixture_data
    monkeypatch.setattr(experiment, "load_spec", lambda path: spec)
    monkeypatch.setattr(experiment, "read_protocol", lambda unused: protocol)
    monkeypatch.setattr(
        experiment,
        "load_corpus",
        lambda *args: {
            did: {"title": "alpha " + did, "text": "alpha fixture"} for did in ("a", "b", "c")
        },
    )
    # Reuse allowlisted public hardware/artifact evidence, never claim this synthetic run is real.
    public = json.loads(
        (experiment.ROOT / "reports/evaluation/local-llm-pilot-v3/summary.json").read_bytes()
    )
    backend = tmp_path / "backend.json"
    backend.write_bytes(json_bytes(public["backend"]))
    calls = []

    def respond(request):
        if request.method == "GET":
            return httpx.Response(200, json={"data": [{"id": public["backend"]["model_alias"]}]})
        calls.append(True)
        payload = json.loads(json.loads(request.content)["messages"][1]["content"])
        result = {"grade": 3} if "candidate" in payload else {"ranked_ids": ["c2", "c1"]}
        return httpx.Response(
            200,
            json={
                "choices": [
                    {
                        "finish_reason": "stop",
                        "message": {"role": "assistant", "content": json.dumps(result)},
                    }
                ]
            },
        )

    workspace, output = tmp_path / "workspace", tmp_path / "report"
    transport = httpx.MockTransport(respond)
    with pytest.raises(ValueError, match="Complete development"):
        experiment.run(workspace, output, backend, release=True, transport=transport)
    assert calls == []
    experiment.run(workspace, output, backend, transport=transport)
    assert len(calls) == 3 and not output.exists()
    checkpoint = workspace / "checkpoint.json"
    saved = json.loads(checkpoint.read_bytes())
    saved["metadata"]["environment"]["python"] = "changed"
    original = checkpoint.read_bytes()
    checkpoint.write_bytes(json_bytes(saved))
    with pytest.raises(ValueError, match="drift"):
        experiment.run(workspace, output, backend, resume=True, release=True, transport=transport)
    checkpoint.write_bytes(original)
    summary = experiment.run(
        workspace, output, backend, resume=True, release=True, transport=transport
    )
    assert len(calls) == 6 and summary["new_human_judgments"] == 0
    # Build an explicitly synthetic lexical reference for the offline verifier.
    reference = tmp_path / "reference.jsonl"
    rows = [json.loads(line) for line in (output / "rankings.jsonl").read_bytes().splitlines()]
    reference.write_bytes(
        json_lines(
            [
                {
                    "query_id": qid,
                    "engine": "anvesha_m1_local",
                    "documents": next(
                        r["measurement"]["lexical"]["documents"]
                        for r in rows
                        if r["measurement"]["query_id"] == qid
                    ),
                }
                for qid in ("q1", "q2")
            ]
        )
    )
    monkeypatch.setattr(experiment, "LEXICAL_REFERENCE", reference)
    summary["lexical_reference_sha256"] = experiment.digest(reference.read_bytes())
    (output / "summary.json").write_bytes(json_bytes(summary))
    assert experiment.verify(output)["results"] == summary["results"]
    with pytest.raises(ValueError, match="refusing to overwrite"):
        experiment.run(workspace, output, backend, resume=True, release=True, transport=transport)
    assert len(calls) == 6
