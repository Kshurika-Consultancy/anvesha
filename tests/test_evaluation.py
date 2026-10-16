"""ANV-019: analytical metric cases, provenance validation and real worker evaluation."""

import asyncio
import copy
import json
import math
from pathlib import Path

import httpx
import pytest

from anvesha import eval_data
from anvesha.eval_data import digest, json_bytes, json_lines, load_corpus, load_spec
from anvesha.eval_metrics import bootstrap_mean, query_metrics
from anvesha.evaluation import (
    ENGINES,
    main,
    render_report,
    run_benchmark,
    summarize,
    verify_report,
)


@pytest.fixture
def fixture_benchmark(tmp_path):
    """First-party synthetic fixtures exercise mechanics; never used as quality evidence."""
    benchmark, data = tmp_path / "benchmark", tmp_path / "data"
    benchmark.mkdir()
    data.mkdir()
    documents = [
        {"_id": "d1", "title": "Alpha repair", "text": "alpha cells repair tissue"},
        {"_id": "d2", "title": "Beta proteins", "text": "beta proteins and cells"},
        {"_id": "d3", "title": "Unrelated", "text": "volcanic rock geology"},
    ]
    queries = [
        {
            "id": "q1",
            "text": "alpha repair",
            "split": "development",
            "upstream_split": "train",
            "language": "en",
            "stratum": "scientific_claim_evidence",
            "judgment_origin": "published_scifact_expert_annotations",
        },
        {
            "id": "q2",
            "text": "beta proteins",
            "split": "evaluation",
            "upstream_split": "test",
            "language": "en",
            "stratum": "scientific_claim_evidence",
            "judgment_origin": "published_scifact_expert_annotations",
        },
    ]
    contents = {
        "queries.jsonl": json_lines(queries),
        "qrels.tsv": b"query_id\tdocument_id\trelevance\nq1\td1\t1\nq2\td2\t1\n",
        "document_ids.txt": b"d1\nd2\nd3\n",
    }
    corpus = json_lines(documents)
    manifest = {
        "schema_version": 1,
        "id": "scifact-v1",
        "query_count": 2,
        "document_count": 3,
        "splits": {"development": 1, "evaluation": 1},
        "qrel_count": 2,
        "archive_sha256": "fixture",
        "corpus_sha256": digest(corpus),
        "files": {name: {"sha256": digest(content)} for name, content in contents.items()},
    }
    for name, content in contents.items():
        (benchmark / name).write_bytes(content)
    (benchmark / "manifest.json").write_bytes(json_bytes(manifest))
    (data / "corpus.jsonl").write_bytes(corpus)
    return benchmark, data, tmp_path / "report"


def rewrite_file(benchmark, name, content):
    (benchmark / name).write_bytes(content)
    manifest = json.loads((benchmark / "manifest.json").read_bytes())
    manifest["files"][name]["sha256"] = digest(content)
    (benchmark / "manifest.json").write_bytes(json_bytes(manifest))


def test_hand_computed_binary_metrics():
    result = query_metrics(["unjudged", "a", "b"], {"a": 1, "b": 1, "c": 1})
    ideal = 1 + 1 / math.log2(3) + 1 / math.log2(4)
    assert result["ndcg@10"] == pytest.approx((1 / math.log2(3) + 0.5) / ideal)
    assert result["mrr@10"] == 0.5
    assert result["precision@10"] == 0.2
    assert result["recall@10"] == pytest.approx(2 / 3)
    assert result["recall@50"] == pytest.approx(2 / 3)
    assert result["success@10"] == 1


def test_empty_and_short_runs_are_not_dropped_or_inflated():
    assert all(value == 0 for value in query_metrics([], {"a": 1}).values())
    assert query_metrics(["a"], {"a": 1})["precision@10"] == 0.1
    assert query_metrics(["x"] * 0, {})["ndcg@10"] == 0
    assert query_metrics(["x"] * 0, {})["recall@50"] == 0
    assert query_metrics([str(n) for n in range(10)] + ["a"], {"a": 1})["mrr@10"] == 0


@pytest.mark.parametrize(
    "ranking,qrels",
    [(["a", "a"], {"a": 1}), (["a"], {"a": True}), (["a"], {"a": -1}), (["a"], {"a": 2})],
)
def test_invalid_ranking_and_grades_fail(ranking, qrels):
    with pytest.raises(ValueError):
        query_metrics(ranking, qrels)


def test_bootstrap_is_reproducible_and_constant_intervals_are_exact():
    assert bootstrap_mean([0.25, 0.25], 100) == {"mean": 0.25, "ci95": [0.25, 0.25]}
    assert bootstrap_mean([0, 1, 0.5], 100) == bootstrap_mean([0, 1, 0.5], 100)
    assert bootstrap_mean([0, 0], 100)["ci95"] == [0, 0]
    with pytest.raises(ValueError):
        bootstrap_mean([], 100)


def test_snapshot_loading_and_corrupt_corpus(fixture_benchmark):
    benchmark, data, _ = fixture_benchmark
    spec = load_spec(benchmark)
    assert len(load_corpus(spec, data)) == 3
    (data / "corpus.jsonl").write_bytes(b"tampered")
    with pytest.raises(ValueError, match="checksum"):
        load_corpus(spec, data)


def test_hash_mismatch_is_not_silently_accepted(fixture_benchmark):
    benchmark, _, _ = fixture_benchmark
    with (benchmark / "queries.jsonl").open("ab") as stream:
        stream.write(b" ")
    with pytest.raises(ValueError, match="checksum"):
        load_spec(benchmark)


@pytest.mark.parametrize(
    "bad",
    [
        "duplicate_text",
        "language",
        "stratum",
        "judgment_origin",
        "upstream_split",
        "unknown_document",
        "missing_query",
        "bad_grade",
        "bad_columns",
    ],
)
def test_semantic_data_errors_are_rejected_even_with_updated_hash(fixture_benchmark, bad):
    benchmark, _, _ = fixture_benchmark
    if bad in {"duplicate_text", "language", "stratum", "judgment_origin", "upstream_split"}:
        rows = eval_data.read_json_lines((benchmark / "queries.jsonl").read_bytes())
        if bad == "duplicate_text":
            rows[1]["text"] = rows[0]["text"].upper()
        else:
            rows[1][bad] = "wrong"
        rewrite_file(benchmark, "queries.jsonl", json_lines(rows))
    else:
        data = (benchmark / "qrels.tsv").read_bytes()
        if bad == "unknown_document":
            data = data.replace(b"d2", b"xx")
        elif bad == "missing_query":
            data = data.replace(b"q2", b"qx")
        elif bad == "bad_grade":
            data = data.replace(b"\t1\n", b"\t2\n")
        else:
            data = data.replace(b"q2\td2\t1", b"q2\td2\t1\textra")
        rewrite_file(benchmark, "qrels.tsv", data)
    with pytest.raises(ValueError):
        load_spec(benchmark)


def test_real_worker_baseline_and_published_report_roundtrip(fixture_benchmark, monkeypatch):
    benchmark, data, output = fixture_benchmark

    def forbid_network(*args, **kwargs):
        pytest.fail("Offline evaluation attempted network access")

    monkeypatch.setattr(httpx.Client, "send", forbid_network)
    monkeypatch.setattr(httpx.AsyncClient, "send", forbid_network)
    summary = run_benchmark(benchmark, data, output, samples=100, export_pool=True)
    assert summary["queries"] == 2
    assert summary["m1_and_fts5_rankings_identical"]
    assert summary["splits"]["evaluation"][ENGINES[2]]["metrics"]["ndcg@10"]["mean"] == 1
    assert verify_report(benchmark, output)["ranking_fingerprint"] == summary["ranking_fingerprint"]
    assert render_report(json.loads(json_bytes(summary))) == render_report(summary)
    pool = eval_data.read_json_lines((data / "review-pool.jsonl").read_bytes())
    assert pool and all(row["reviewer"] is None and row["grade"] is None for row in pool)
    assert all("engine" not in row and "metrics" not in row for row in pool)


def test_compare_failure_preserves_prior_report(fixture_benchmark):
    benchmark, data, output = fixture_benchmark
    output.mkdir()
    sentinel = output / "summary.json"
    sentinel.write_bytes(b"previous report")
    with pytest.raises(ValueError, match="prior report preserved"):
        run_benchmark(
            benchmark, data, output, samples=100, expected_ranking_fingerprint="different"
        )
    assert sentinel.read_bytes() == b"previous report"


def test_tampered_results_and_missing_runs_fail(fixture_benchmark):
    benchmark, data, output = fixture_benchmark
    run_benchmark(benchmark, data, output, samples=100)
    records = eval_data.read_json_lines((output / "per_query.jsonl").read_bytes())
    spec = load_spec(benchmark)
    with pytest.raises(ValueError, match="Missing queries"):
        summarize(spec, records[:-1], 100)
    bad = copy.deepcopy(records)
    bad[0]["documents"] = ["not-in-corpus"]
    with pytest.raises(ValueError, match="Invalid ranked"):
        summarize(spec, bad, 100)
    bad = copy.deepcopy(records)
    bad[0]["metrics"]["ndcg@10"] = 0.12345
    with pytest.raises(ValueError, match="disagree"):
        summarize(spec, bad, 100)
    records[0]["elapsed_ms"] = float("nan")
    with pytest.raises(ValueError, match="duration"):
        summarize(spec, records, 100)


def test_shipped_real_query_snapshot_is_disjoint_and_attributed():
    spec = load_spec(Path("benchmarks/scifact-v1"))
    assert len(spec.queries) == 500
    assert len(spec.document_ids) == 5183
    assert spec.manifest["splits"] == {"development": 200, "evaluation": 300}
    assert spec.manifest["qrel_count"] == 569
    assert spec.manifest["query_qrel_license"] == "CC-BY-4.0"
    assert spec.manifest["corpus_redistributed"] is False


def test_cli_requires_explicit_network_intent(tmp_path):
    with pytest.raises(SystemExit) as error:
        main(["prepare", "--archive", str(tmp_path / "missing.zip")])
    assert error.value.code == 2
    with pytest.raises(SystemExit):
        main(["run", "--download"])


def test_wrong_archive_is_rejected_before_extraction(tmp_path):
    path = tmp_path / "bad.zip"
    path.write_bytes(b"not the pinned archive")
    with pytest.raises(ValueError, match="SHA-256"):
        eval_data.prepare(path, tmp_path / "bench", tmp_path / "data")
    assert not (tmp_path / "bench").exists()


def test_report_rejects_unsupported_coverage_and_provenance(fixture_benchmark):
    benchmark, data, output = fixture_benchmark
    original = run_benchmark(benchmark, data, output, samples=100)
    changes = [
        ("schema_version", 2),
        ("coverage", {"scientific_claim_evidence": 2, "other_strata": 500}),
        ("judgment_origin", "new human assessments"),
        ("bootstrap", {**original["bootstrap"], "seed": 7}),
        ("bootstrap", {**original["bootstrap"], "unit": "document"}),
    ]
    for key, value in changes:
        altered = {**original, key: value}
        (output / "summary.json").write_bytes(json_bytes(altered))
        with pytest.raises(ValueError):
            verify_report(benchmark, output)


@pytest.mark.parametrize("failure", ["redirect", "oversize", "checksum", "timeout", "encoding"])
def test_failed_acquisition_preserves_cache_and_cleans_temp_files(tmp_path, monkeypatch, failure):
    class Chunks(httpx.AsyncByteStream):
        async def __aiter__(self):
            yield b"not the pinned archive"

    async def handle(request):
        assert str(request.url) == eval_data.SOURCE_URL
        if failure == "timeout":
            await asyncio.sleep(1)
        if failure == "redirect":
            return httpx.Response(302, headers={"Location": "https://example.org/other"})
        headers = {"Content-Encoding": "gzip"} if failure == "encoding" else {}
        return httpx.Response(200, headers=headers, stream=Chunks())

    original_client = httpx.AsyncClient
    monkeypatch.setattr(
        httpx,
        "AsyncClient",
        lambda **kwargs: original_client(transport=httpx.MockTransport(handle), **kwargs),
    )
    if failure == "oversize":
        monkeypatch.setattr(eval_data, "MAX_ARCHIVE_BYTES", 1)
    if failure == "timeout":
        monkeypatch.setattr(eval_data, "DOWNLOAD_BUDGET_SECONDS", 0.01)
    target = tmp_path / "cached.zip"
    target.write_bytes(b"previous cache")
    with pytest.raises((ValueError, TimeoutError)):
        asyncio.run(eval_data.download_archive(target))
    assert target.read_bytes() == b"previous cache"
    assert list(tmp_path.iterdir()) == [target]
