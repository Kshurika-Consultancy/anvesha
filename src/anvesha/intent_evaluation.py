"""ANV-020: real local retrieval runs and blinded multilingual candidate pools."""

import argparse
import json
import statistics
import tempfile
from collections import Counter
from pathlib import Path

from anvesha.eval_data import digest, json_bytes, json_lines, read_json_lines
from anvesha.eval_metrics import METRICS, query_metrics
from anvesha.evaluation import ENGINES, overlap_ranking, ranking_fingerprint, tokens
from anvesha.review_data import DEFAULT_BENCHMARK, DEFAULT_DATA, load_documents, load_snapshot
from anvesha.store import PIPELINE_VERSION, Store
from anvesha.worker import process_one

DEFAULT_REPORT = Path("reports/evaluation/xquad-intents-v1")
RUBRIC = Path("docs/review/rubric-v1.json")
CODE_FILES = (
    "review_data.py",
    "intent_evaluation.py",
    "eval_metrics.py",
    "evaluation.py",
    "store.py",
    "worker.py",
    "ranking.py",
)


def summarize(snapshot, records):
    queries = {row["id"]: row for row in snapshot.queries}
    by_key = {}
    for row in records:
        key = row["query_id"], row["engine"]
        docs = row["documents"]
        if (
            key in by_key
            or key[0] not in queries
            or key[1] not in ENGINES
            or not isinstance(docs, list)
            or len(docs) > 50
            or len(docs) != len(set(docs))
            or not set(docs) <= snapshot.document_ids
        ):
            raise ValueError("Invalid, duplicate or unknown query/system/ranking")
        by_key[key] = row
    if len(by_key) != len(queries) * len(ENGINES):
        raise ValueError("Missing query/system runs")
    metrics = {}
    for split in ("development", "holdout"):
        metrics[split] = {}
        for lang in ("en", "es", "hi"):
            qids = sorted(
                qid
                for qid, q in queries.items()
                if q["split"] == split and q["language"] == lang and qid in snapshot.mappings
            )
            metrics[split][lang] = {}
            for engine in ENGINES:
                rows = [
                    query_metrics(by_key[qid, engine]["documents"], snapshot.mappings[qid])
                    for qid in qids
                ]
                metrics[split][lang][engine] = {
                    "mapped_queries": len(rows),
                    "means": {
                        name: round(statistics.fmean(r[name] for r in rows), 6) if rows else None
                        for name in METRICS
                    },
                }
    return {
        "coverage": {
            field: dict(sorted(Counter(q[field] for q in queries.values()).items()))
            for field in ("language", "domain", "stratum", "split", "origin")
        },
        "derived_context_retrieval_metrics": metrics,
        "draft_queries_excluded_from_metrics": sum(
            q["id"] not in snapshot.mappings for q in snapshot.queries
        ),
        "m1_bm25_parity": all(
            by_key[qid, ENGINES[1]]["documents"] == by_key[qid, ENGINES[2]]["documents"]
            for qid in queries
        ),
    }


def build_pool(snapshot, documents, records, manifest_hash, rubric):
    by_query = {}
    for row in records:
        by_query.setdefault(row["query_id"], set()).update(row["documents"][:10])
    pairs = []
    for query in snapshot.queries:
        qid = query["id"]
        for did in sorted(by_query[qid], key=lambda value: digest((qid + value).encode())):
            pairs.append(
                {
                    "pair_id": digest((manifest_hash + "\0" + qid + "\0" + did).encode())[:24],
                    "query": {
                        key: query[key]
                        for key in ("id", "text", "language", "constraints", "stratum", "split")
                    },
                    "document": documents[did],
                }
            )
    return {
        "schema_version": 1,
        "dataset": snapshot.manifest["id"],
        "snapshot_sha256": manifest_hash,
        "ranking_fingerprint": ranking_fingerprint(records),
        "rubric": rubric,
        "pool_depth": 10,
        "pairs": pairs,
        "query_count": len(snapshot.queries),
        "empty_query_ids": sorted(q["id"] for q in snapshot.queries if not by_query[q["id"]]),
        "rights_manifest": "policies/sources/xquad_evaluation.json",
    }


def render_report(summary):
    table = []
    for lang in ("en", "es", "hi"):
        dev = summary["derived_context_retrieval_metrics"]["development"][lang][ENGINES[2]]
        holdout = summary["derived_context_retrieval_metrics"]["holdout"][lang][ENGINES[2]]
        count = dev["mapped_queries"] + holdout["mapped_queries"]
        table.append(
            f"| {lang} | {count} | {dev['means']['ndcg@10']} | {holdout['means']['ndcg@10']} |"
        )
    return "\n".join(
        [
            "# Multilingual corpus and review readiness",
            "",
            "Task ANV-020 (in progress).",
            f"{summary['queries']} queries; {summary['documents']} real snapshot passages; "
            f"{summary['runs']} query/system rankings.",
            f"Published QA answer-context mappings: {summary['answer_context_mappings']}. "
            f"AI-authored unjudged drafts: {summary['draft_queries_excluded_from_metrics']}.",
            "New human assessments: **0**. No agreement or human quality score is claimed.",
            "",
            "| Language | Published queries | Development nDCG@10 | Holdout nDCG@10 |",
            "| --- | --- | --- | --- |",
            *table,
            "",
            "Scores use the source answer-bearing paragraph as one known positive. "
            "They are not exhaustive judgments, QA answer scores or web-quality measurements. "
            "Translations share groups; no independence or confidence interval claim follows.",
            "Article groups and all translations stay in the same split. The holdout is public and "
            "reserved from tuning, not guaranteed unseen by models. No parameters were tuned here.",
            "Raw passages, candidate pools, credentials and assessor submissions remain local. "
            "The browser form and workflow require no paid APIs or hosted models.",
            "",
            "[Summary](summary.json), [rankings](rankings.jsonl), "
            "[data/attribution](../../../benchmarks/xquad-intents-v1/README.md), "
            "[human workflow](../../../docs/review/README.md).",
            "",
        ]
    )


def run(benchmark, data_dir, output, *, expected=None):
    snapshot = load_snapshot(benchmark)
    documents = load_documents(snapshot, data_dir)
    records = []
    token_sets = {did: tokens(d["title"] + " " + d["text"]) for did, d in documents.items()}
    url_ids = {d["url"]: did for did, d in documents.items()}
    with tempfile.TemporaryDirectory(prefix="anvesha-intent-evaluation-") as temp:
        store = Store(Path(temp) / "index.db")
        store.initialize()
        for doc in documents.values():
            store.upsert_document(
                {
                    "id": doc["id"],
                    "url": doc["url"],
                    "title": doc["title"],
                    "content": doc["text"],
                    "license": doc["license"],
                    "attribution": doc["attribution"],
                }
            )
        for number, query in enumerate(snapshot.queries, 1):
            text = query["text"]
            for engine in ENGINES:
                if engine == ENGINES[0]:
                    ranking = overlap_ranking(text, token_sets)
                elif engine == ENGINES[1]:
                    ranking = [url_ids[d["url"]] for d in store.search_local(text, 50)]
                else:
                    job, _ = store.create_search("evaluation", text, ["local"], 50)
                    process_one(store, enabled_sources=("local",))
                    if store.get_job("evaluation", job["id"])["state"] != "completed":
                        raise ValueError("Worker failed; no queries may be silently omitted")
                    ranking = [
                        url_ids[d["url"]]
                        for d in store.get_results("evaluation", job["id"], 1, 0, 50)["results"]
                    ]
                    store.delete_job("evaluation", job["id"])
                records.append({"query_id": query["id"], "engine": engine, "documents": ranking})
            if number % 100 == 0:
                print(
                    f"Evaluated {number}/{len(snapshot.queries)} multilingual/intent queries",
                    flush=True,
                )
    manifest_hash = digest((benchmark / "manifest.json").read_bytes())
    summary = {
        "schema_version": 1,
        "dataset": snapshot.manifest["id"],
        "task": "ANV-020",
        "snapshot_sha256": manifest_hash,
        "corpus_sha256": snapshot.manifest["corpus_sha256"],
        "code_sha256": {
            name: digest((Path(__file__).parent / name).read_bytes()) for name in CODE_FILES
        },
        "queries": len(snapshot.queries),
        "documents": len(documents),
        "runs": len(records),
        "answer_context_mappings": len(snapshot.mappings),
        "new_human_judgments": 0,
        "pipeline_version": PIPELINE_VERSION,
        "ranking_fingerprint": ranking_fingerprint(records),
        **summarize(snapshot, records),
    }
    if expected is not None and expected != summary["ranking_fingerprint"]:
        raise ValueError("Rankings differ; prior reports preserved")
    rubric = json.loads(RUBRIC.read_bytes())
    pool = build_pool(snapshot, documents, records, manifest_hash, rubric)
    output.mkdir(parents=True, exist_ok=True)
    (output / "rankings.jsonl").write_bytes(json_lines(records))
    (output / "summary.json").write_bytes(json_bytes(summary))
    (output / "README.md").write_text(render_report(summary), encoding="utf-8", newline="\n")
    (data_dir / "candidate-pool.json").write_bytes(json_bytes(pool))
    return summary


def verify(benchmark, output):
    snapshot = load_snapshot(benchmark)
    summary = json.loads((output / "summary.json").read_bytes())
    records = read_json_lines((output / "rankings.jsonl").read_bytes())
    if (
        summary.get("schema_version") != 1
        or summary["dataset"] != snapshot.manifest["id"]
        or summary["snapshot_sha256"] != digest((benchmark / "manifest.json").read_bytes())
        or summary["corpus_sha256"] != snapshot.manifest["corpus_sha256"]
        or summary["new_human_judgments"] != 0
        or summary["answer_context_mappings"] != len(snapshot.mappings)
        or summary["queries"] != len(snapshot.queries)
        or summary["documents"] != len(snapshot.document_ids)
        or summary["runs"] != len(records)
        or summary["ranking_fingerprint"] != ranking_fingerprint(records)
    ):
        raise ValueError("Report provenance, count or scope mismatch")
    calculated = summarize(snapshot, records)
    if any(summary[key] != value for key, value in calculated.items()):
        raise ValueError("Report metrics/coverage mismatch")
    if (output / "README.md").read_text(encoding="utf-8") != render_report(summary):
        raise ValueError("Rendered report mismatch")
    return summary


def main(argv=None):
    parser = argparse.ArgumentParser(
        description="Offline multilingual retrieval and review pooling"
    )
    parser.add_argument("command", choices=("run", "verify"))
    parser.add_argument("--benchmark-dir", type=Path, default=DEFAULT_BENCHMARK)
    parser.add_argument("--data-dir", type=Path, default=DEFAULT_DATA)
    parser.add_argument("--output-dir", type=Path, default=DEFAULT_REPORT)
    parser.add_argument("--compare", type=Path)
    args = parser.parse_args(argv)
    try:
        expected = (
            json.loads(args.compare.read_bytes())["ranking_fingerprint"] if args.compare else None
        )
        summary = (
            run(args.benchmark_dir, args.data_dir, args.output_dir, expected=expected)
            if args.command == "run"
            else verify(args.benchmark_dir, args.output_dir)
        )
        print(
            json.dumps(
                {
                    "queries": summary["queries"],
                    "ranking_fingerprint": summary["ranking_fingerprint"],
                    "new_human_judgments": 0,
                }
            )
        )
        return 0
    except (OSError, ValueError, KeyError) as exc:
        parser.error(str(exc))


if __name__ == "__main__":
    raise SystemExit(main())
