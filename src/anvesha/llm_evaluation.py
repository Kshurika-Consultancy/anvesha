"""ANV-023: explicit local-model pilot, paired metrics and offline verification.

Uses public SciFact annotations, never private operational feedback/reviewer data.
Model failures retain their actual worker fallback; no failed query is dropped.
"""

import argparse
import json
import math
import platform
import re
import sqlite3
import statistics
import tempfile
import time
from collections import Counter
from datetime import UTC, datetime
from pathlib import Path

import httpx

from anvesha.eval_data import SOURCE_URL, digest, json_bytes, json_lines, load_corpus, load_spec
from anvesha.eval_metrics import aggregate, bootstrap_mean, percentile, query_metrics
from anvesha.evaluation import _revision
from anvesha.llm import PROMPT_VERSION, SYSTEM_PROMPT, LLMConfig, LLMReranker
from anvesha.store import Store
from anvesha.worker import process_one

ROOT = Path(__file__).resolve().parents[2]
EXPERIMENT = "local-llm-pilot-v3"
SELECTION_SEED = "local-llm-pilot-v1"
PROTOCOL = ROOT / "benchmarks" / EXPERIMENT / "protocol.json"
MODEL_POLICY = ROOT / "policies/models/qwen3-4b-instruct2507.json"
LEXICAL_REFERENCE = ROOT / "reports/evaluation/scifact-v1/per_query.jsonl"
CODE_FILES = (
    "llm_evaluation.py",
    "llm.py",
    "worker.py",
    "store.py",
    "ranking.py",
    "providers.py",
    "eval_data.py",
    "eval_metrics.py",
)


def planned_protocol(spec):
    counts = {"development": 4, "evaluation": 24}
    selected = {}
    for split, count in counts.items():
        ids = [query["id"] for query in spec.queries if query["split"] == split]
        selected[split] = sorted(
            ids, key=lambda qid: digest((SELECTION_SEED + "\0" + split + "\0" + qid).encode())
        )[:count]
        if len(selected[split]) != count:
            raise ValueError("Insufficient queries for the frozen pilot")
    return {
        "schema_version": 1,
        "id": EXPERIMENT,
        "task": "ANV-023",
        "benchmark": "scifact-v1",
        "selection_seed": SELECTION_SEED,
        "selection": "lowest SHA256(selection_seed + NUL + split + NUL + id); "
        "no labels or retrieval scores",
        "query_ids": selected,
        "retrieval_depth": 50,
        "candidate_limit": 20,
        "timeout_seconds": 120.0,
        "output_format": "json_schema",
        "prompt_version": PROMPT_VERSION,
        "prompt_sha256": digest(SYSTEM_PROMPT.encode()),
        "model_policy_sha256": digest(MODEL_POLICY.read_bytes()),
        "primary_metric": "ndcg@10",
        "bootstrap_samples": 1000,
        "bootstrap_seed": 20261016,
        "run_budget_seconds": 3600,
        "context_tokens": 8192,
        "cpu_threads": 6,
        "generation_seed": 20261018,
        "development_policy": "Protocol diagnostics only; do not tune from evaluation outcomes. "
        "Record any changed protocol as a separate experiment before evaluation.",
        "holdout_limit": "Project-reserved for this LLM run, not unseen by prior lexical "
        "evaluation or guaranteed absent from model training.",
    }


def read_protocol(path, spec):
    protocol = json.loads(path.read_bytes())
    if protocol != planned_protocol(spec):
        raise ValueError("Pilot protocol differs from its frozen, label-blind plan")
    return protocol


def validate_backend(backend, policy, protocol):
    fields = {
        "runtime",
        "runtime_version",
        "runtime_commit",
        "runtime_archive_sha256",
        "server_sha256",
        "model_sha256",
        "model_alias",
        "cpu_model",
        "physical_cores",
        "logical_processors",
        "memory_bytes",
        "threads",
        "context_tokens",
        "gpu_layers",
        "offline",
        "tools_enabled",
        "webui",
        "seed",
    }
    if not isinstance(backend, dict) or set(backend) != fields:
        raise ValueError("Only allowlisted non-private backend evidence is accepted")
    expected = {
        "runtime": "llama.cpp",
        "runtime_commit": policy["runtime"]["commit"],
        "runtime_archive_sha256": policy["runtime"]["sha256"],
        "model_sha256": policy["model"]["sha256"],
        "model_alias": policy["model"]["alias"],
        "threads": protocol["cpu_threads"],
        "context_tokens": protocol["context_tokens"],
        "gpu_layers": 0,
        "offline": True,
        "tools_enabled": False,
        "webui": False,
        "seed": protocol["generation_seed"],
    }
    if any(
        type(backend[key]) is not type(value) or backend[key] != value
        for key, value in expected.items()
    ):
        raise ValueError("Backend evidence differs from the local CPU/artifact plan")
    for key in ("physical_cores", "logical_processors", "memory_bytes"):
        if type(backend[key]) is not int or backend[key] <= 0:
            raise ValueError("Invalid hardware measurement")
    if not isinstance(backend["server_sha256"], str) or not re.fullmatch(
        r"[a-f0-9]{64}", backend["server_sha256"]
    ):
        raise ValueError("Missing runtime executable hash")
    for key in ("runtime_version", "cpu_model"):
        if not isinstance(backend[key], str) or not 1 <= len(backend[key]) <= 200:
            raise ValueError("Invalid non-private backend identifier")
    return backend


def validate_records(spec, protocol, records, *, complete=True):
    by_id = {query["id"]: query for query in spec.queries}
    expected_ids = [qid for group in protocol["query_ids"].values() for qid in group]
    if not complete:
        if len(records) > len(expected_ids):
            raise ValueError("Checkpoint exceeds planned query count")
        expected_ids = expected_ids[: len(records)]
    if [row["query_id"] for row in records] != expected_ids:
        raise ValueError("Missing, duplicate, out-of-order or unplanned query; never silently omit")
    for row in records:
        if set(row) != {"query_id", "split", "lexical", "llm"}:
            raise ValueError("Unexpected per-query fields; do not publish private payloads")
        qid = row["query_id"]
        if row["split"] != by_id[qid]["split"]:
            raise ValueError("Query split mismatch")
        baseline, model = row["lexical"], row["llm"]
        for result in (baseline, model):
            fields = {"documents", "metrics", "state", "warnings", "elapsed_ms"}
            if result is model:
                fields.add("applied")
            if set(result) != fields:
                raise ValueError("Unexpected result fields")
            ranking = result["documents"]
            if (
                not isinstance(ranking, list)
                or any(not isinstance(did, str) for did in ranking)
                or len(ranking) > protocol["retrieval_depth"]
                or len(set(ranking)) != len(ranking)
                or not set(ranking) <= spec.document_ids
            ):
                raise ValueError("Invalid ranking identifiers")
            if result["metrics"] != query_metrics(ranking, spec.qrels[qid]):
                raise ValueError("Metrics disagree with published annotations")
            if (
                type(result["elapsed_ms"]) not in {int, float}
                or not math.isfinite(result["elapsed_ms"])
                or result["elapsed_ms"] < 0
            ):
                raise ValueError("Invalid duration")
        if baseline["state"] != "completed" or baseline["warnings"]:
            raise ValueError("Lexical control did not complete cleanly")
        if model["state"] not in {"completed", "completed_partial", "failed"}:
            raise ValueError("Model run is not terminal")
        before, after = baseline["documents"], model["documents"]
        prefix = min(protocol["candidate_limit"], len(before))
        if model["state"] == "failed":
            if after or model["applied"]:
                raise ValueError("Failed execution must not claim applied ranking")
        elif set(before) != set(after) or before[prefix:] != after[prefix:]:
            raise ValueError("Reranking changed candidate membership or untouched tail")
        warnings = model["warnings"]
        if not isinstance(warnings, list) or any(
            value
            not in {
                "llm:" + code
                for code in (
                    "http_error",
                    "rate_limited",
                    "network_error",
                    "timeout",
                    "invalid_response",
                    "unexpected_encoding",
                    "redirect_rejected",
                    "response_too_large",
                    "not_configured",
                    "configuration_changed",
                    "rerank_failed",
                )
            }
            for value in warnings
        ):
            raise ValueError("Unrecognized failure diagnostic")
        if model["state"] == "completed_partial" and (not warnings or after != before):
            raise ValueError("Fallback must retain the lexical control")
        applied = model["state"] == "completed" and len(before) >= 2
        if type(model["applied"]) is not bool or model["applied"] != applied:
            raise ValueError("Applied-stage marker disagrees with execution")
        if model["state"] == "completed" and warnings:
            raise ValueError("Successful execution cannot hide stage warnings")
    return records


def summarize(spec, protocol, records):
    validate_records(spec, protocol, records)
    output = {}
    for split in protocol["query_ids"]:
        rows = [row for row in records if row["split"] == split]
        differences = [
            row["llm"]["metrics"]["ndcg@10"] - row["lexical"]["metrics"]["ndcg@10"] for row in rows
        ]
        paired = bootstrap_mean(differences, protocol["bootstrap_samples"])
        ceiling = []
        for row in rows:
            before = row["lexical"]["documents"]
            count = protocol["candidate_limit"]
            # Post-hoc diagnostic only: gold labels never enter model/retrieval input.
            best = sorted(before[:count], key=lambda did: -spec.qrels[row["query_id"]].get(did, 0))
            ceiling.append(
                query_metrics(best + before[count:], spec.qrels[row["query_id"]])["ndcg@10"]
            )
        output[split] = {
            "queries": len(rows),
            "metrics": {
                engine: aggregate(
                    [row[engine]["metrics"] for row in rows], protocol["bootstrap_samples"]
                )
                for engine in ("lexical", "llm")
            },
            "paired_ndcg10_delta": paired,
            "ndcg10_wins_ties_losses": {
                "wins": sum(value > 1e-12 for value in differences),
                "ties": sum(abs(value) <= 1e-12 for value in differences),
                "losses": sum(value < -1e-12 for value in differences),
            },
            "model_applied": sum(row["llm"]["applied"] for row in rows),
            "model_fallbacks": sum(row["llm"]["state"] == "completed_partial" for row in rows),
            "worker_failures": sum(row["llm"]["state"] == "failed" for row in rows),
            "warnings": dict(
                sorted(Counter(w for row in rows for w in row["llm"]["warnings"]).items())
            ),
            "mean_oracle_prefix_ndcg10": round(statistics.fmean(ceiling), 6),
            "latency_ms": {
                engine: {
                    "median": round(
                        statistics.median(row[engine]["elapsed_ms"] for row in rows), 3
                    ),
                    "p95": round(percentile([row[engine]["elapsed_ms"] for row in rows], 0.95), 3),
                    "total": round(sum(row[engine]["elapsed_ms"] for row in rows), 3),
                }
                for engine in ("lexical", "llm")
            },
            "inference": (
                "positive paired interval on this small scientific sample"
                if paired["ci95"][0] > 0
                else "negative paired interval on this small scientific sample"
                if paired["ci95"][1] < 0
                else "interval includes zero; improvement not established"
            ),
        }
    return output


def measure_query(store, query, url_to_id, config, reranker):
    runs = {}
    for engine in ("lexical", "llm"):
        tick = time.perf_counter()
        job, _ = store.create_search(
            "local-llm-evaluation",
            query["text"],
            ["local"],
            50,
            ranking=engine,
            pipeline_version=config.pipeline_version if engine == "llm" else None,
        )
        try:
            if not process_one(store, reranker=reranker, enabled_sources=("local",)):
                raise ValueError("Worker did not claim the measured job")
            state = store.get_job("local-llm-evaluation", job["id"])
            if state["state"] not in {"completed", "completed_partial", "failed"}:
                raise ValueError("Measured worker did not reach a terminal state")
            snapshot = store.get_results("local-llm-evaluation", job["id"], None, 0, 50)
            results = snapshot["results"] if snapshot else []
            runs[engine] = {
                "documents": [url_to_id[item["url"]] for item in results],
                "state": state["state"],
                "warnings": state["warnings"],
                "elapsed_ms": round((time.perf_counter() - tick) * 1000, 6),
            }
            if engine == "llm":
                runs[engine]["applied"] = any(
                    item.get("ranking_method") == "llm_rerank" for item in results
                )
        finally:
            store.delete_job("local-llm-evaluation", job["id"])
    return {"query_id": query["id"], "split": query["split"], **runs}


def render(summary):
    lines = [
        "# Local LLM pilot: Qwen3-4B versus lexical search",
        "",
        "ANV-023. Public SciFact expert labels; zero new Anvesha human judgments.",
        "",
        "| Split | Queries | Lexical nDCG@10 | LLM nDCG@10 | Paired delta (95% CI) | "
        "Applied / fallback / failed |",
        "| --- | ---: | ---: | ---: | --- | --- |",
    ]
    for split, data in summary["splits"].items():
        delta = data["paired_ndcg10_delta"]
        lines.append(
            f"| {split} | {data['queries']} | "
            f"{data['metrics']['lexical']['ndcg@10']['mean']:.6f} | "
            f"{data['metrics']['llm']['ndcg@10']['mean']:.6f} | "
            f"{delta['mean']:+.6f} [{delta['ci95'][0]:+.6f}, {delta['ci95'][1]:+.6f}] | "
            f"{data['model_applied']} / {data['model_fallbacks']} / {data['worker_failures']} |"
        )
    lines.extend(
        [
            "",
            "Evaluation conclusion: " + summary["splits"]["evaluation"]["inference"] + ".",
            "",
            "This fixed small sample is not a release gate, a general-web comparison, "
            "or evidence for coding/IoT/asset/private-agent query quality. Public data may "
            "have appeared in model training. Unjudged pairs count as zero. Query bootstrap "
            "intervals do not correct for shared topics or model-selection uncertainty.",
            "",
            "Only the original candidate prefix is reordered; the corpus and recall "
            "ceiling do not expand. Failure fallback remains in the paired measurements. "
            "See summary.json and rankings.jsonl for IDs, latency, warnings, "
            "provenance and bounds.",
            "",
            "Source attribution and reuse conditions: [SciFact dataset notice]"
            "(../../../benchmarks/scifact-v1/README.md) and "
            "[model/runtime rights manifest]"
            "(../../../policies/models/qwen3-4b-instruct2507.json). "
            "Model weights, runtime binaries and raw text are not bundled.",
        ]
    )
    return "\n".join(lines) + "\n"


def run(
    benchmark_dir,
    data_dir,
    protocol_path,
    workspace,
    output_dir,
    backend_path,
    base_url,
    *,
    resume=False,
    development_only=True,
    transport=None,
):
    spec = load_spec(benchmark_dir)
    protocol = read_protocol(protocol_path, spec)
    policy = json.loads(MODEL_POLICY.read_bytes())
    config = LLMConfig(
        model=policy["model"]["alias"],
        base_url=base_url,
        candidate_limit=protocol["candidate_limit"],
        timeout_seconds=protocol["timeout_seconds"],
        output_format=protocol["output_format"],
    )
    backend = json.loads(backend_path.read_bytes())
    validate_backend(backend, policy, protocol)
    if output_dir.exists():
        raise ValueError("Output directory exists; refusing to overwrite public evidence")
    with httpx.Client(
        trust_env=False, follow_redirects=False, timeout=5, transport=transport
    ) as client:
        response = client.get(config.base_url + "/models")
        response.raise_for_status()
        if config.model not in [item["id"] for item in response.json()["data"]]:
            raise ValueError("The pinned model alias is not served")
    metadata = {
        "schema_version": 1,
        "experiment": protocol["id"],
        "task": "ANV-023",
        "protocol_sha256": digest(protocol_path.read_bytes()),
        "model_policy_sha256": digest(MODEL_POLICY.read_bytes()),
        "code_sha256": {
            name: digest((Path(__file__).parent / name).read_bytes()) for name in CODE_FILES
        },
        "benchmark_sha256": {name: item["sha256"] for name, item in spec.manifest["files"].items()},
        "corpus_sha256": spec.manifest["corpus_sha256"],
        "lexical_reference_sha256": digest(LEXICAL_REFERENCE.read_bytes()),
        "model_profile": {
            "pipeline_version": config.pipeline_version,
            "prompt_version": PROMPT_VERSION,
            "candidate_limit": config.candidate_limit,
            "timeout_seconds": config.timeout_seconds,
            "output_format": config.output_format,
            "endpoint_scope": "loopback",
        },
        "backend": backend,
        "environment": {
            "python": platform.python_version(),
            "sqlite": sqlite3.sqlite_version,
            "platform": platform.system(),
        },
    }
    workspace.mkdir(parents=True, exist_ok=True)
    checkpoint = workspace / "checkpoint.json"
    records = []
    origin = {"started_at": datetime.now(UTC).isoformat(), "code_revision_before_run": _revision()}
    if checkpoint.exists():
        if not resume:
            raise ValueError(
                "Checkpoint exists; use --resume with unchanged artifacts/configuration"
            )
        saved = json.loads(checkpoint.read_bytes())
        if saved["metadata"] != metadata:
            raise ValueError("Cannot mix model, protocol, code or environment across a resumed run")
        records = saved["records"]
        origin = saved["origin"]
        validate_records(spec, protocol, records, complete=False)
    if not development_only and len(records) < len(protocol["query_ids"]["development"]):
        raise ValueError("Complete a development checkpoint before releasing evaluation")
    corpus = load_corpus(spec, data_dir)
    url_to_id = {f"{SOURCE_URL}#document_id={did}": did for did in corpus}
    selected = [qid for group in protocol["query_ids"].values() for qid in group]
    query_by_id = {query["id"]: query for query in spec.queries}
    if [row["query_id"] for row in records] != selected[: len(records)]:
        raise ValueError("Checkpoint has duplicated or unexpected queries")
    started = time.monotonic()
    reranker = LLMReranker(config, transport=transport)
    with tempfile.TemporaryDirectory(prefix="index-", dir=workspace) as temporary:
        store = Store(Path(temporary) / "pilot.db")
        store.initialize()
        for url, did in url_to_id.items():
            row = corpus[did]
            store.upsert_document(
                {
                    "id": did,
                    "url": url,
                    "title": row["title"],
                    "content": row["text"],
                    "license": "ODC-By-1.0 (database)",
                    "attribution": "SciFact/S2ORC; underlying content rights separate",
                }
            )
        pending = selected[len(records) :]
        if development_only:
            pending = [qid for qid in pending if query_by_id[qid]["split"] == "development"]
        for number, qid in enumerate(pending, len(records) + 1):
            if time.monotonic() - started > protocol["run_budget_seconds"]:
                raise ValueError("Run budget exhausted; checkpoint retained for explicit resume")
            row = measure_query(store, query_by_id[qid], url_to_id, config, reranker)
            for engine in ("lexical", "llm"):
                row[engine]["metrics"] = query_metrics(row[engine]["documents"], spec.qrels[qid])
            records.append(row)
            with tempfile.NamedTemporaryFile(dir=workspace, delete=False) as stream:
                target = Path(stream.name)
                stream.write(
                    json_bytes({"metadata": metadata, "records": records, "origin": origin})
                )
            target.replace(checkpoint)
            print(
                f"Measured {number}/{len(selected)} {row['split']}: {row['llm']['state']} "
                f"({row['llm']['elapsed_ms'] / 1000:.1f}s)",
                flush=True,
            )
    if development_only:
        print("Development checkpoint saved; evaluation requires --release-evaluation --resume.")
        return None
    splits = summarize(spec, protocol, records)
    summary = {
        **metadata,
        "generated_at": datetime.now(UTC).isoformat(),
        "code_revision_before_run": origin["code_revision_before_run"],
        "started_at": origin["started_at"],
        "splits": splits,
        "records_sha256": digest(json_lines(records)),
        "new_human_judgments": 0,
    }
    output_dir.mkdir(parents=True)
    (output_dir / "rankings.jsonl").write_bytes(json_lines(records))
    (output_dir / "summary.json").write_bytes(json_bytes(summary))
    (output_dir / "README.md").write_text(render(summary), encoding="utf-8", newline="\n")
    return summary


def verify(benchmark_dir, protocol_path, output_dir):
    spec = load_spec(benchmark_dir)
    protocol = read_protocol(protocol_path, spec)
    summary = json.loads((output_dir / "summary.json").read_bytes())
    raw = (output_dir / "rankings.jsonl").read_bytes()
    records = [json.loads(line) for line in raw.splitlines()]
    policy = json.loads(MODEL_POLICY.read_bytes())
    validate_backend(summary["backend"], policy, protocol)
    expected_fields = {
        "schema_version",
        "experiment",
        "task",
        "protocol_sha256",
        "model_policy_sha256",
        "code_sha256",
        "benchmark_sha256",
        "corpus_sha256",
        "lexical_reference_sha256",
        "model_profile",
        "backend",
        "environment",
        "generated_at",
        "code_revision_before_run",
        "started_at",
        "splits",
        "records_sha256",
        "new_human_judgments",
    }
    if set(summary) != expected_fields:
        raise ValueError("Unexpected summary fields")
    profile = summary["model_profile"]
    expected_profile = {
        "prompt_version": protocol["prompt_version"],
        "candidate_limit": protocol["candidate_limit"],
        "timeout_seconds": protocol["timeout_seconds"],
        "output_format": protocol["output_format"],
        "endpoint_scope": "loopback",
    }
    if (
        set(profile) != {*expected_profile, "pipeline_version"}
        or any(profile.get(key) != value for key, value in expected_profile.items())
        or not re.fullmatch(r"m3-llm-rerank-v1-[a-f0-9]{16}", profile["pipeline_version"])
    ):
        raise ValueError("Model profile disagrees with the protocol")
    hashes = summary["code_sha256"]
    if set(hashes) != set(CODE_FILES) or any(
        not isinstance(value, str) or not re.fullmatch(r"[a-f0-9]{64}", value)
        for value in hashes.values()
    ):
        raise ValueError("Missing evaluated source fingerprints")
    reference = {
        row["query_id"]: row["documents"]
        for row in (json.loads(line) for line in LEXICAL_REFERENCE.read_bytes().splitlines())
        if row["engine"] == "anvesha_m1_local"
    }
    if (
        summary["protocol_sha256"] != digest(protocol_path.read_bytes())
        or summary["model_policy_sha256"] != digest(MODEL_POLICY.read_bytes())
        or summary["records_sha256"] != digest(raw)
        or summary["lexical_reference_sha256"] != digest(LEXICAL_REFERENCE.read_bytes())
        or any(row["lexical"]["documents"] != reference[row["query_id"]] for row in records)
        or summary["benchmark_sha256"]
        != {name: item["sha256"] for name, item in spec.manifest["files"].items()}
        or summary["corpus_sha256"] != spec.manifest["corpus_sha256"]
        or summary["task"] != "ANV-023"
        or summary["experiment"] != protocol["id"]
        or summary["new_human_judgments"] != 0
        or summary["splits"] != summarize(spec, protocol, records)
        or (output_dir / "README.md").read_text(encoding="utf-8") != render(summary)
    ):
        raise ValueError("Pilot report hashes, metrics or rendering differ")
    return summary


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest="command", required=True)
    sub.add_parser("plan", help="Freeze label-blind selection before live inference")
    execute = sub.add_parser("run", help="Explicit loopback inference on public benchmark data")
    execute.add_argument("--run-local-model", action="store_true", required=True)
    execute.add_argument("--backend-info", type=Path, required=True)
    execute.add_argument("--base-url", default="http://127.0.0.1:8135/v1")
    execute.add_argument("--resume", action="store_true")
    execute.add_argument(
        "--release-evaluation",
        action="store_true",
        help="Explicitly release the frozen evaluation queries after development",
    )
    sub.add_parser("verify", help="Offline artifact consistency; not proof of inference")
    for command in (execute, sub.choices["verify"]):
        command.add_argument(
            "--output-dir", type=Path, default=ROOT / "reports/evaluation" / EXPERIMENT
        )
    execute.add_argument(
        "--workspace", type=Path, default=ROOT / ".anvesha/evaluation" / EXPERIMENT
    )
    args = parser.parse_args(argv)
    benchmark_dir = ROOT / "benchmarks/scifact-v1"
    try:
        if args.command == "plan":
            data = json_bytes(planned_protocol(load_spec(benchmark_dir)))
            if PROTOCOL.exists() and PROTOCOL.read_bytes() != data:
                raise ValueError(
                    "A different protocol already exists; version it rather than overwrite"
                )
            PROTOCOL.parent.mkdir(parents=True, exist_ok=True)
            PROTOCOL.write_bytes(data)
            print("Frozen pilot: 4 development + 24 evaluation queries; no model called")
        elif args.command == "verify":
            summary = verify(benchmark_dir, PROTOCOL, args.output_dir)
            print(
                json.dumps(
                    {
                        "status": "passed",
                        "splits": list(summary["splits"]),
                        "new_human_judgments": 0,
                    }
                )
            )
        else:
            run(
                benchmark_dir,
                ROOT / ".anvesha/evaluation/scifact-v1",
                PROTOCOL,
                args.workspace,
                args.output_dir,
                args.backend_info,
                args.base_url,
                resume=args.resume,
                development_only=not args.release_evaluation,
            )
    except (OSError, ValueError, KeyError, httpx.HTTPError) as error:
        parser.exit(
            1,
            f"Local evaluation did not complete ({type(error).__name__}); "
            "inspect pins/configuration locally; no private payload is logged.\n",
        )


if __name__ == "__main__":
    main()
