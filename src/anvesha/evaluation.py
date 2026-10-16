"""ANV-019: offline retrieval baselines, auditable reports, and review pools.

Run from the repository root with python -m anvesha.evaluation --help.
"""

import argparse
import asyncio
import json
import math
import platform
import re
import sqlite3
import statistics
import subprocess
import tempfile
import time
from datetime import UTC, datetime
from pathlib import Path

import httpx

from anvesha.eval_data import (
    SOURCE_URL,
    digest,
    download_archive,
    json_bytes,
    json_lines,
    load_corpus,
    load_spec,
    prepare,
    read_json_lines,
)
from anvesha.eval_metrics import aggregate, bootstrap_mean, query_metrics
from anvesha.store import PIPELINE_VERSION, Store
from anvesha.worker import process_one

ENGINES = ("token_overlap_v1", "fts5_bm25_title2_body1", "anvesha_m1_local")
DEPTH = 50
ROOT = Path(__file__).resolve().parents[2]
CODE_FILES = (
    "eval_data.py",
    "eval_metrics.py",
    "evaluation.py",
    "store.py",
    "worker.py",
    "ranking.py",
)


def tokens(text):
    return set(re.findall(r"[^\W_]+", text.casefold()))


def overlap_ranking(query, token_sets):
    query_tokens = tokens(query)
    scores = [(len(query_tokens & values), did) for did, values in token_sets.items()]
    return [did for score, did in sorted(scores, key=lambda item: (-item[0], item[1])) if score][
        :DEPTH
    ]


def ranking_fingerprint(records):
    return digest(
        json_lines(
            [
                {
                    "query_id": row["query_id"],
                    "engine": row["engine"],
                    "documents": row["documents"],
                }
                for row in records
            ]
        )
    )


def summarize(spec, records, samples=1000):
    query_by_id = {query["id"]: query for query in spec.queries}
    by_key = {}
    for row in records:
        key = row["query_id"], row["engine"]
        if key in by_key or key[0] not in query_by_id or key[1] not in ENGINES:
            raise ValueError("Duplicate or unknown query/engine run record")
        ranking = row["documents"]
        if (
            not isinstance(ranking, list)
            or len(ranking) > DEPTH
            or not set(ranking) <= spec.document_ids
        ):
            raise ValueError("Invalid ranked documents")
        expected = query_metrics(ranking, spec.qrels[key[0]])
        if row["split"] != query_by_id[key[0]]["split"] or row["metrics"] != expected:
            raise ValueError("Stored per-query metrics or split disagree with judgments")
        if (
            type(row.get("elapsed_ms")) not in (float, int)
            or not math.isfinite(row["elapsed_ms"])
            or row["elapsed_ms"] < 0
        ):
            raise ValueError("Invalid recorded duration")
        by_key[key] = row
    if len(by_key) != len(spec.queries) * len(ENGINES):
        raise ValueError("Missing queries/engines in run; never silently skip failures")
    results, comparisons = {}, {}
    for split in spec.manifest["splits"]:
        qids = sorted(query["id"] for query in spec.queries if query["split"] == split)
        results[split] = {}
        comparisons[split] = {}
        for engine in ENGINES:
            rows = [by_key[qid, engine] for qid in qids]
            results[split][engine] = {
                "queries": len(qids),
                "metrics": aggregate([row["metrics"] for row in rows], samples),
                "empty_results": sum(not row["documents"] for row in rows),
                "mean_returned": round(statistics.fmean(len(row["documents"]) for row in rows), 3),
                "mean_elapsed_ms": round(statistics.fmean(row["elapsed_ms"] for row in rows), 3),
            }
            differences = [
                by_key[qid, engine]["metrics"]["ndcg@10"]
                - by_key[qid, ENGINES[1]]["metrics"]["ndcg@10"]
                for qid in qids
            ]
            comparisons[split][engine] = bootstrap_mean(differences, samples)
    parity = all(
        by_key[q["id"], ENGINES[1]]["documents"] == by_key[q["id"], ENGINES[2]]["documents"]
        for q in spec.queries
    )
    return {
        "splits": results,
        "paired_ndcg10_delta_vs_fts5": comparisons,
        "m1_and_fts5_rankings_identical": parity,
    }


def _revision():
    result = subprocess.run(
        ["git", "rev-parse", "HEAD"], cwd=ROOT, capture_output=True, text=True, check=False
    )
    return result.stdout.strip() if result.returncode == 0 else None


def run_benchmark(
    benchmark_dir,
    data_dir,
    output_dir,
    samples=1000,
    export_pool=False,
    expected_ranking_fingerprint=None,
):
    spec = load_spec(benchmark_dir)
    corpus = load_corpus(spec, data_dir)
    if not 100 <= samples <= 10000:
        raise ValueError("Bootstrap samples must be 100..10000")
    records = []
    url_to_id = {f"{SOURCE_URL}#document_id={did}": did for did in corpus}
    token_sets = {did: tokens(row["title"] + " " + row["text"]) for did, row in corpus.items()}
    started = time.perf_counter()
    with tempfile.TemporaryDirectory(prefix="anvesha-evaluation-") as temporary:
        store = Store(Path(temporary) / "evaluation.db")
        store.initialize()
        for count, (url, did) in enumerate(url_to_id.items(), 1):
            row = corpus[did]
            store.upsert_document(
                {
                    "id": did,
                    "url": url,
                    "title": row["title"],
                    "content": row["text"],
                    "license": "ODC-By-1.0 (database)",
                    "attribution": "SciFact / S2ORC authors; underlying content rights separate",
                }
            )
            if count % 1000 == 0:
                print(f"Indexed {count}/{len(corpus)} real benchmark documents", flush=True)
        for number, query in enumerate(spec.queries, 1):
            qid, text = query["id"], query["text"]
            for engine in ENGINES:
                tick = time.perf_counter()
                if engine == ENGINES[0]:
                    ranking = overlap_ranking(text, token_sets)
                elif engine == ENGINES[1]:
                    ranking = [url_to_id[row["url"]] for row in store.search_local(text, DEPTH)]
                else:
                    job, _ = store.create_search("evaluation", text, ["local"], DEPTH)
                    if not process_one(store, enabled_sources=("local",)):
                        raise ValueError("Worker did not claim the evaluation job")
                    state = store.get_job("evaluation", job["id"])
                    if state["state"] != "completed":
                        raise ValueError(
                            "Evaluation worker failed; do not score it as missing data"
                        )
                    snapshot = store.get_results("evaluation", job["id"], 1, 0, DEPTH)
                    ranking = [url_to_id[row["url"]] for row in snapshot["results"]]
                    store.delete_job("evaluation", job["id"])
                elapsed = (time.perf_counter() - tick) * 1000
                records.append(
                    {
                        "query_id": qid,
                        "split": query["split"],
                        "engine": engine,
                        "documents": ranking,
                        "metrics": query_metrics(ranking, spec.qrels[qid]),
                        "elapsed_ms": round(elapsed, 6),
                    }
                )
            if number % 50 == 0:
                print(
                    f"Evaluated {number}/{len(spec.queries)} queries with {len(ENGINES)} systems",
                    flush=True,
                )
    aggregates = summarize(spec, records, samples)
    summary = {
        "schema_version": 1,
        "benchmark": spec.manifest["id"],
        "task": "ANV-019",
        "generated_at": datetime.now(UTC).isoformat(),
        "code_revision_before_run": _revision(),
        "code_sha256": {
            name: digest((Path(__file__).parent / name).read_bytes()) for name in CODE_FILES
        },
        "input_sha256": {name: item["sha256"] for name, item in spec.manifest["files"].items()},
        "archive_sha256": spec.manifest["archive_sha256"],
        "corpus_sha256": spec.manifest["corpus_sha256"],
        "corpus_documents": len(corpus),
        "queries": len(spec.queries),
        "qrels": spec.manifest["qrel_count"],
        "retrieval_depth": DEPTH,
        "pipeline_version": PIPELINE_VERSION,
        "environment": {
            "python": platform.python_version(),
            "platform": platform.system(),
            "sqlite": sqlite3.sqlite_version,
        },
        "engines": {
            ENGINES[0]: "Unique lowercase token-intersection count; ties by document ID",
            ENGINES[1]: "Store.search_local, title/body BM25 weights 2/1, escaped OR query",
            ENGINES[2]: "Store -> process_one -> actual M1 RRF, local source only, limit 50",
        },
        "bootstrap": {
            "samples": samples,
            "seed": 20261016,
            "unit": "query",
            "interval": "95% percentile; descriptive, no multiple-comparison correction",
        },
        "total_seconds": round(time.perf_counter() - started, 3),
        "ranking_fingerprint": ranking_fingerprint(records),
        "judgment_origin": "Published SciFact expert-derived document evidence annotations",
        "new_anvesha_human_judgments": 0,
        "coverage": {"scientific_claim_evidence": len(spec.queries), "other_strata": 0},
        "scope": (
            "Fixed-corpus retrieval; HTTP, live discovery, freshness, "
            "fact verification and paid services excluded"
        ),
        **aggregates,
    }
    if (
        expected_ranking_fingerprint is not None
        and expected_ranking_fingerprint != summary["ranking_fingerprint"]
    ):
        raise ValueError("Rankings differ from comparison baseline; prior report preserved")
    output_dir.mkdir(parents=True, exist_ok=True)
    (output_dir / "per_query.jsonl").write_bytes(json_lines(records))
    (output_dir / "summary.json").write_bytes(json_bytes(summary))
    (output_dir / "README.md").write_text(render_report(summary), encoding="utf-8", newline="\n")
    if export_pool:
        export_review_pool(spec, corpus, records, data_dir / "review-pool.jsonl")
    return summary


def export_review_pool(spec, corpus, records, path):
    """System-blinded pool. Grades/reviewers stay null until a real assessor labels it."""
    grouped = {}
    for row in records:
        grouped.setdefault(row["query_id"], set()).update(row["documents"][:10])
    pool = []
    for query in spec.queries:
        qid = query["id"]
        ids = sorted(grouped[qid], key=lambda did: digest((qid + "\0" + did).encode()))
        for did in ids:
            pool.append(
                {
                    "pool_id": digest((qid + "\0" + did).encode())[:24],
                    "query_id": qid,
                    "query": query["text"],
                    "document_id": did,
                    "title": corpus[did]["title"],
                    "text": corpus[did]["text"],
                    "grade": None,
                    "reviewer": None,
                    "rationale": None,
                }
            )
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(json_lines(pool))


def render_report(summary):
    lines = [
        "# SciFact retrieval baseline",
        "",
        "Task: ANV-019. Fixed English scientific corpus; published upstream evidence judgments.",
        "",
        f"{summary['queries']} queries (200 development, 300 evaluation), "
        f"{summary['corpus_documents']} documents, depth {DEPTH}.",
        "No new Anvesha human labels or model training. "
        "Relevant evidence may support or refute the query claim.",
        "",
        "| Split | System | nDCG@10 (95% query bootstrap CI) | MRR@10 | Recall@50 |",
        "| --- | --- | --- | --- | --- |",
    ]
    for split in ("development", "evaluation"):
        for engine in ENGINES:
            result = summary["splits"][split][engine]
            metrics = result["metrics"]
            ndcg = metrics["ndcg@10"]
            lines.append(
                f"| {split} | {engine} | {ndcg['mean']:.4f} "
                f"[{ndcg['ci95'][0]:.4f}, {ndcg['ci95'][1]:.4f}] | "
                f"{metrics['mrr@10']['mean']:.4f} | {metrics['recall@50']['mean']:.4f} |"
            )
    lines.extend(
        [
            "",
            f"M1 and direct BM25 rankings identical: {summary['m1_and_fts5_rankings_identical']}.",
            "One-source RRF preserves BM25 ordering; equivalence is expected, "
            "not an improvement claim.",
            "",
            "Unlisted query/document pairs are unjudged, treated as zero for standard metrics. "
            "Recall is relative to known relevant documents, not the whole web.",
            "No navigation, comparison, locale, multilingual or freshness claims follow. "
            "Timings describe this local run and include different orchestration overheads.",
            "",
            "[Summary and provenance](summary.json), "
            "[per-query rankings and metrics](per_query.jsonl), "
            "[methodology](../../../docs/EVALUATION.md).",
            "",
        ]
    )
    return "\n".join(lines)


def verify_report(benchmark_dir, output_dir):
    spec = load_spec(benchmark_dir)
    summary = json.loads((output_dir / "summary.json").read_bytes())
    records = read_json_lines((output_dir / "per_query.jsonl").read_bytes())
    if summary.get("schema_version") != 1:
        raise ValueError("Unsupported report schema")
    if summary["benchmark"] != spec.manifest["id"] or summary["queries"] != len(spec.queries):
        raise ValueError("Report benchmark or query count mismatch")
    expected_inputs = {name: item["sha256"] for name, item in spec.manifest["files"].items()}
    if (
        summary["input_sha256"] != expected_inputs
        or summary["archive_sha256"] != spec.manifest["archive_sha256"]
    ):
        raise ValueError("Report data provenance mismatch")
    if summary["corpus_sha256"] != spec.manifest["corpus_sha256"] or summary[
        "corpus_documents"
    ] != len(spec.document_ids):
        raise ValueError("Report corpus provenance mismatch")
    if summary["ranking_fingerprint"] != ranking_fingerprint(records):
        raise ValueError("Ranking fingerprint mismatch")
    if summary["retrieval_depth"] != DEPTH or summary["new_anvesha_human_judgments"] != 0:
        raise ValueError("Incorrect report scope or judgment provenance")
    if summary["coverage"] != {"scientific_claim_evidence": len(spec.queries), "other_strata": 0}:
        raise ValueError("Incorrect report coverage")
    if (
        summary["judgment_origin"]
        != "Published SciFact expert-derived document evidence annotations"
    ):
        raise ValueError("Incorrect report judgment provenance")
    if summary["bootstrap"]["seed"] != 20261016 or summary["bootstrap"]["unit"] != "query":
        raise ValueError("Unsupported bootstrap configuration")
    if summary["qrels"] != spec.manifest["qrel_count"]:
        raise ValueError("Report judgment count mismatch")
    calculated = summarize(spec, records, summary["bootstrap"]["samples"])
    if any(summary[key] != value for key, value in calculated.items()):
        raise ValueError("Report aggregate metrics differ from stored rankings/judgments")
    if (output_dir / "README.md").read_text(encoding="utf-8") != render_report(summary):
        raise ValueError("Rendered report differs from machine-readable results")
    return summary


def main(argv=None):
    parser = argparse.ArgumentParser(description="No-paid-service retrieval evaluation")
    parser.add_argument("command", choices=("prepare", "run", "verify"))
    parser.add_argument("--benchmark-dir", type=Path, default=Path("benchmarks/scifact-v1"))
    parser.add_argument("--data-dir", type=Path, default=Path(".anvesha/evaluation/scifact-v1"))
    parser.add_argument("--archive", type=Path, default=Path(".anvesha/evaluation/scifact.zip"))
    parser.add_argument("--output-dir", type=Path, default=Path("reports/evaluation/scifact-v1"))
    parser.add_argument(
        "--download", action="store_true", help="Explicitly fetch pinned upstream archive"
    )
    parser.add_argument(
        "--export-pool",
        action="store_true",
        help="Write unlabelled review pool only into local data-dir",
    )
    parser.add_argument("--bootstrap-samples", type=int, default=1000)
    parser.add_argument(
        "--compare", type=Path, help="Fail if ranking fingerprint differs from a prior summary"
    )
    args = parser.parse_args(argv)
    try:
        if args.download and args.command != "prepare":
            raise ValueError("Only prepare --download may use the network")
        if args.command == "prepare":
            if args.download:
                asyncio.run(download_archive(args.archive))
            elif not args.archive.exists():
                raise ValueError(
                    "Archive missing; use prepare --download explicitly or supply --archive"
                )
            spec = prepare(args.archive, args.benchmark_dir, args.data_dir)
            print(
                json.dumps(
                    {
                        "queries": len(spec.queries),
                        "documents": len(spec.document_ids),
                        "splits": spec.manifest["splits"],
                    }
                )
            )
            return 0
        if args.command == "run":
            prior = json.loads(args.compare.read_bytes()) if args.compare else None
            summary = run_benchmark(
                args.benchmark_dir,
                args.data_dir,
                args.output_dir,
                args.bootstrap_samples,
                args.export_pool,
                expected_ranking_fingerprint=prior["ranking_fingerprint"] if prior else None,
            )
        else:
            summary = verify_report(args.benchmark_dir, args.output_dir)
        print(
            json.dumps(
                {
                    "status": "passed",
                    "queries": summary["queries"],
                    "ranking_fingerprint": summary["ranking_fingerprint"],
                    "m1_bm25_parity": summary["m1_and_fts5_rankings_identical"],
                }
            )
        )
        return 0
    except (OSError, ValueError, KeyError, TimeoutError, httpx.HTTPError) as exc:
        parser.error(str(exc))


if __name__ == "__main__":
    raise SystemExit(main())
