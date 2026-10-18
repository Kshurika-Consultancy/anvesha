"""ANV-024: explicit local contract comparison; offline planning/verification by default."""

import argparse
import json
import platform
import re
import sqlite3
import tempfile
import time
from collections import Counter
from datetime import UTC, datetime
from pathlib import Path

import httpx

from anvesha.eval_data import SOURCE_URL, digest, json_bytes, json_lines, load_corpus, load_spec
from anvesha.eval_metrics import bootstrap_mean, query_metrics
from anvesha.evaluation import _revision
from anvesha.llm import (
    POINTWISE_PROMPT,
    POINTWISE_VERSION,
    PROMPT_VERSION,
    SYSTEM_PROMPT,
    LLMConfig,
    LLMReranker,
)
from anvesha.llm_evaluation import (
    CODE_FILES,
    LEXICAL_REFERENCE,
    MODEL_POLICY,
    ROOT,
    measure_query,
    summarize,
    validate_backend,
    validate_records,
)
from anvesha.store import Store

EXPERIMENT = "local-llm-contracts-v1"
PROTOCOL = ROOT / "benchmarks" / EXPERIMENT / "protocol.json"
PREVIOUS = ROOT / "benchmarks/local-llm-pilot-v3/protocol.json"
STRATEGIES = ("listwise", "pointwise")
SOURCES = (*CODE_FILES, "ranking_experiment.py")


def planned_protocol(spec):
    previous = json.loads(PREVIOUS.read_bytes())
    excluded = {qid for ids in previous["query_ids"].values() for qid in ids}
    selected = {}
    for split, count in (("development", 4), ("evaluation", 16)):
        ids = [q["id"] for q in spec.queries if q["split"] == split and q["id"] not in excluded]
        selected[split] = sorted(
            ids, key=lambda qid: digest((EXPERIMENT + "\0" + split + "\0" + qid).encode())
        )[:count]
        if len(selected[split]) != count:
            raise ValueError("Insufficient fresh queries")
    return {
        "schema_version": 1,
        "id": EXPERIMENT,
        "task": "ANV-024",
        "benchmark": "scifact-v1",
        "query_ids": selected,
        "selection_seed": EXPERIMENT,
        "selection": "lowest SHA256(seed + NUL + split + NUL + id), excluding previous pilot IDs; "
        "no labels or retrieval scores",
        "excluded_protocol_sha256": digest(PREVIOUS.read_bytes()),
        "retrieval_depth": 50,
        "candidate_limit": 20,
        "timeout_seconds": 120.0,
        "output_format": "json_schema",
        "strategies": {
            "listwise": {
                "prompt_version": PROMPT_VERSION,
                "prompt_sha256": digest(SYSTEM_PROMPT.encode()),
                "max_tokens_per_call": 1536,
                "max_calls_per_query": 1,
            },
            "pointwise": {
                "prompt_version": POINTWISE_VERSION,
                "prompt_sha256": digest(POINTWISE_PROMPT.encode()),
                "max_tokens_per_call": 32,
                "max_calls_per_query": 20,
                "ties": "original lexical order; all grades required or full lexical fallback",
            },
        },
        "profile_order": "alternate listwise/pointwise then pointwise/listwise per query",
        "model_policy_sha256": digest(MODEL_POLICY.read_bytes()),
        "primary_metric": "ndcg@10",
        "bootstrap_samples": 1000,
        "bootstrap_seed": 20261016,
        "run_budget_seconds": 5400,
        "context_tokens": 8192,
        "cpu_threads": 6,
        "generation_seed": 20261018,
        "interpretation": "Reliability pilot, not a default-promotion gate. Fresh to this "
        "experiment, not unseen by earlier lexical evaluation or guaranteed absent from "
        "model training. No tuning on released evaluation scores or automatic promotion.",
    }


def read_protocol(spec):
    protocol = json.loads(PROTOCOL.read_bytes())
    if protocol != planned_protocol(spec):
        raise ValueError("Contract protocol differs from its frozen label-blind plan")
    return protocol


def configurations(protocol, backend):
    return {
        strategy: LLMConfig(
            model=backend["model_alias"],
            base_url="http://127.0.0.1:8135/v1",
            candidate_limit=protocol["candidate_limit"],
            timeout_seconds=protocol["timeout_seconds"],
            output_format=protocol["output_format"],
            strategy=strategy,
        )
        for strategy in STRATEGIES
    }


def schedule(protocol):
    return [
        (qid, strategy)
        for index, qid in enumerate(qid for ids in protocol["query_ids"].values() for qid in ids)
        for strategy in (STRATEGIES if index % 2 == 0 else STRATEGIES[::-1])
    ]


def measurements(records, strategy):
    return [row["measurement"] for row in records if row["strategy"] == strategy]


def validate(spec, protocol, records, *, complete=True):
    plan = schedule(protocol)
    if complete and len(records) != len(plan) or len(records) > len(plan):
        raise ValueError("Every planned query/profile must be accounted for")
    observed = []
    controls = {}
    for row in records:
        if set(row) != {"strategy", "model_calls", "measurement"}:
            raise ValueError("Unexpected diagnostic fields; never save raw model payloads")
        strategy, measured = row["strategy"], row["measurement"]
        if strategy not in STRATEGIES:
            raise ValueError("Unknown strategy")
        observed.append((measured["query_id"], strategy))
        maximum = 1 if strategy == "listwise" else protocol["candidate_limit"]
        if type(row["model_calls"]) is not int or not 0 <= row["model_calls"] <= maximum:
            raise ValueError("Invalid bounded model-call count")
        control = measured["lexical"]["documents"]
        prior = controls.setdefault(measured["query_id"], control)
        if prior != control:
            raise ValueError("Profiles used different lexical candidates")
        if measured["llm"]["applied"] and row["model_calls"] != (
            1 if strategy == "listwise" else min(len(control), protocol["candidate_limit"])
        ):
            raise ValueError("Applied profile lacks all required model calls")
    if observed != plan[: len(records)]:
        raise ValueError("Unexpected, duplicated or missing query/profile")
    for strategy in STRATEGIES:
        validate_records(spec, protocol, measurements(records, strategy), complete=complete)
    return records


def summarize_comparison(spec, protocol, records):
    validate(spec, protocol, records)
    profiles = {
        strategy: summarize(spec, protocol, measurements(records, strategy))
        for strategy in STRATEGIES
    }
    paired = {}
    for split in protocol["query_ids"]:
        scores = {
            strategy: {
                row["query_id"]: row["llm"]["metrics"]["ndcg@10"]
                for row in measurements(records, strategy)
                if row["split"] == split
            }
            for strategy in STRATEGIES
        }
        paired[split] = bootstrap_mean(
            [scores["pointwise"][qid] - scores["listwise"][qid] for qid in scores["listwise"]],
            protocol["bootstrap_samples"],
        )
    return {
        "profiles": profiles,
        "paired_pointwise_minus_listwise_ndcg10": paired,
        "attempted_model_calls": {
            strategy: sum(row["model_calls"] for row in records if row["strategy"] == strategy)
            for strategy in STRATEGIES
        },
        "contract_failures": {
            strategy: dict(
                sorted(
                    Counter(
                        warning
                        for row in measurements(records, strategy)
                        for warning in row["llm"]["warnings"]
                        if warning.startswith("llm_contract:")
                    ).items()
                )
            )
            for strategy in STRATEGIES
        },
    }


def render(summary):
    lines = [
        "# Local ranking contracts: listwise versus pointwise",
        "",
        "ANV-024. Public SciFact expert labels; zero new human judgments. "
        "CPU-only local inference.",
        "",
        "| Split | Contract | Queries | Lexical nDCG@10 | Model nDCG@10 | "
        "Applied / fallback / failed |",
        "| --- | --- | ---: | ---: | ---: | --- |",
    ]
    for strategy, splits in summary["results"]["profiles"].items():
        for split, row in splits.items():
            lines.append(
                f"| {split} | {strategy} | {row['queries']} | "
                f"{row['metrics']['lexical']['ndcg@10']['mean']:.6f} | "
                f"{row['metrics']['llm']['ndcg@10']['mean']:.6f} | "
                f"{row['model_applied']} / {row['model_fallbacks']} / {row['worker_failures']} |"
            )
    delta = summary["results"]["paired_pointwise_minus_listwise_ndcg10"]["evaluation"]
    lines += [
        "",
        f"Evaluation paired pointwise minus listwise nDCG@10: {delta['mean']:+.6f}, "
        f"95% query-bootstrap interval [{delta['ci95'][0]:+.6f}, {delta['ci95'][1]:+.6f}].",
        "",
        "All failures retain lexical fallback and remain in the comparison. Reliability is "
        "not relevance or truth. This small scientific sample does not establish general-web, "
        "coding, IoT, asset or agent quality. Public data may have appeared in pretraining; "
        "unjudged pairs count as zero and query intervals do not correct topic dependence. "
        "No automatic default promotion follows. See summary.json and rankings.jsonl for "
        "paired metrics, calls, deadlines, sanitized failures and provenance.",
        "",
        "[Method](../../../docs/LOCAL_LLM_EVALUATION.md); "
        "[data rights](../../../benchmarks/scifact-v1/README.md); "
        "[model/runtime rights](../../../policies/models/qwen3-4b-instruct2507.json). "
        "No raw text, model outputs/reasoning, private queries, weights or binaries are bundled.",
    ]
    return "\n".join(lines) + "\n"


class CountingReranker(LLMReranker):
    """Count attempted candidate requests without recording their input or output."""

    calls = 0

    async def _request(self, query, candidates):
        self.calls += 1
        return await super()._request(query, candidates)


def run(workspace, output_dir, backend_path, *, release=False, resume=False, transport=None):
    spec = load_spec(ROOT / "benchmarks/scifact-v1")
    protocol = read_protocol(spec)
    backend = json.loads(backend_path.read_bytes())
    validate_backend(backend, json.loads(MODEL_POLICY.read_bytes()), protocol)
    configs = configurations(protocol, backend)
    metadata = {
        "experiment": EXPERIMENT,
        "task": "ANV-024",
        "protocol_sha256": digest(PROTOCOL.read_bytes()),
        "model_policy_sha256": digest(MODEL_POLICY.read_bytes()),
        "corpus_sha256": spec.manifest["corpus_sha256"],
        "benchmark_sha256": {name: item["sha256"] for name, item in spec.manifest["files"].items()},
        "lexical_reference_sha256": digest(LEXICAL_REFERENCE.read_bytes()),
        "code_sha256": {
            name: digest((Path(__file__).parent / name).read_bytes()) for name in SOURCES
        },
        "pipelines": {strategy: config.pipeline_version for strategy, config in configs.items()},
        "backend": backend,
        "environment": {
            "python": platform.python_version(),
            "sqlite": sqlite3.sqlite_version,
            "platform": platform.system(),
        },
    }
    if output_dir.exists():
        raise ValueError("Output exists; refusing to overwrite evidence")
    workspace.mkdir(parents=True, exist_ok=True)
    checkpoint = workspace / "checkpoint.json"
    records = []
    origin = {"started_at": datetime.now(UTC).isoformat(), "source_revision": _revision()}
    if checkpoint.exists():
        if not resume:
            raise ValueError("Checkpoint exists; explicit unchanged resume required")
        saved = json.loads(checkpoint.read_bytes())
        if saved["metadata"] != metadata:
            raise ValueError("Source, protocol, model or environment drift; do not mix runs")
        records, origin = saved["records"], saved["origin"]
        validate(spec, protocol, records, complete=False)
    development_count = 2 * len(protocol["query_ids"]["development"])
    if release and len(records) < development_count:
        raise ValueError("Complete development before explicitly releasing evaluation")
    corpus = load_corpus(spec, ROOT / ".anvesha/evaluation/scifact-v1")
    url_to_id = {f"{SOURCE_URL}#document_id={did}": did for did in corpus}
    queries = {query["id"]: query for query in spec.queries}
    plan = schedule(protocol)
    pending = plan[len(records) :] if release else plan[len(records) : development_count]
    with httpx.Client(trust_env=False, timeout=5, transport=transport) as client:
        response = client.get("http://127.0.0.1:8135/v1/models")
        response.raise_for_status()
        if backend["model_alias"] not in [item["id"] for item in response.json()["data"]]:
            raise ValueError("Pinned model alias is not served")
    started = time.monotonic()
    with tempfile.TemporaryDirectory(prefix="index-", dir=workspace) as temporary:
        store = Store(Path(temporary) / "contracts.db")
        store.initialize()
        for url, did in url_to_id.items():
            store.upsert_document(
                {
                    "id": did,
                    "url": url,
                    "title": corpus[did]["title"],
                    "content": corpus[did]["text"],
                    "license": "ODC-By-1.0 (database)",
                    "attribution": "SciFact/S2ORC; underlying content rights separate",
                }
            )
        for qid, strategy in pending:
            if time.monotonic() - started > protocol["run_budget_seconds"]:
                raise ValueError("Run budget exhausted; explicit resume required")
            config = configs[strategy]
            ranker = CountingReranker(config, transport=transport)
            measured = measure_query(store, queries[qid], url_to_id, config, ranker)
            for engine in ("lexical", "llm"):
                measured[engine]["metrics"] = query_metrics(
                    measured[engine]["documents"], spec.qrels[qid]
                )
            records.append(
                {"strategy": strategy, "model_calls": ranker.calls, "measurement": measured}
            )
            validate(spec, protocol, records, complete=False)
            temporary_checkpoint = checkpoint.with_suffix(".tmp")
            temporary_checkpoint.write_bytes(
                json_bytes({"metadata": metadata, "origin": origin, "records": records})
            )
            temporary_checkpoint.replace(checkpoint)
            print(
                f"Measured {len(records)}/{len(plan)} {measured['split']} {strategy}: "
                f"{measured['llm']['state']} ({measured['llm']['elapsed_ms'] / 1000:.1f}s), "
                f"{ranker.calls} calls",
                flush=True,
            )
    if not release:
        print("Development saved; evaluation requires --release-evaluation --resume", flush=True)
        return None
    summary = {
        **metadata,
        **origin,
        "generated_at": datetime.now(UTC).isoformat(),
        "new_human_judgments": 0,
        "records_sha256": digest(json_lines(records)),
        "results": summarize_comparison(spec, protocol, records),
    }
    output_dir.mkdir(parents=True)
    (output_dir / "rankings.jsonl").write_bytes(json_lines(records))
    (output_dir / "summary.json").write_bytes(json_bytes(summary))
    (output_dir / "README.md").write_text(render(summary), encoding="utf-8", newline="\n")
    return summary


def verify(output_dir):
    spec = load_spec(ROOT / "benchmarks/scifact-v1")
    protocol = read_protocol(spec)
    summary = json.loads((output_dir / "summary.json").read_bytes())
    raw = (output_dir / "rankings.jsonl").read_bytes()
    records = [json.loads(line) for line in raw.splitlines()]
    if set(summary) != {
        "experiment",
        "task",
        "protocol_sha256",
        "model_policy_sha256",
        "corpus_sha256",
        "benchmark_sha256",
        "lexical_reference_sha256",
        "code_sha256",
        "pipelines",
        "backend",
        "environment",
        "started_at",
        "source_revision",
        "generated_at",
        "new_human_judgments",
        "records_sha256",
        "results",
    }:
        raise ValueError("Unexpected report fields")
    validate_backend(summary["backend"], json.loads(MODEL_POLICY.read_bytes()), protocol)
    references = {
        row["query_id"]: row["documents"]
        for row in (json.loads(line) for line in LEXICAL_REFERENCE.read_bytes().splitlines())
        if row["engine"] == "anvesha_m1_local"
    }
    if (
        summary["experiment"] != EXPERIMENT
        or summary["task"] != "ANV-024"
        or summary["new_human_judgments"] != 0
        or summary["protocol_sha256"] != digest(PROTOCOL.read_bytes())
        or summary["model_policy_sha256"] != digest(MODEL_POLICY.read_bytes())
        or summary["records_sha256"] != digest(raw)
        or summary["corpus_sha256"] != spec.manifest["corpus_sha256"]
        or summary["benchmark_sha256"]
        != {name: item["sha256"] for name, item in spec.manifest["files"].items()}
        or summary["lexical_reference_sha256"] != digest(LEXICAL_REFERENCE.read_bytes())
        or any(
            row["measurement"]["lexical"]["documents"] != references[row["measurement"]["query_id"]]
            for row in records
        )
        or summary["results"] != summarize_comparison(spec, protocol, records)
        or (output_dir / "README.md").read_text(encoding="utf-8") != render(summary)
        or set(summary["code_sha256"]) != set(SOURCES)
        or any(
            not re.fullmatch(r"[a-f0-9]{64}", value) for value in summary["code_sha256"].values()
        )
        or set(summary["pipelines"]) != set(STRATEGIES)
        or summary["pipelines"]
        != {
            strategy: config.pipeline_version
            for strategy, config in configurations(protocol, summary["backend"]).items()
        }
        or any(
            not re.fullmatch(r"m3-llm-rerank-v1-[a-f0-9]{16}", value)
            for value in summary["pipelines"].values()
        )
    ):
        raise ValueError("Report integrity, baseline, accounting or metrics differ")
    return summary


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    commands = parser.add_subparsers(dest="command", required=True)
    commands.add_parser("plan")
    execute = commands.add_parser("run")
    execute.add_argument("--run-local-model", action="store_true", required=True)
    execute.add_argument("--backend-info", type=Path, required=True)
    execute.add_argument(
        "--workspace", type=Path, default=ROOT / ".anvesha/evaluation" / EXPERIMENT
    )
    execute.add_argument("--resume", action="store_true")
    execute.add_argument("--release-evaluation", action="store_true")
    for command in (execute, commands.add_parser("verify")):
        command.add_argument(
            "--output-dir", type=Path, default=ROOT / "reports/evaluation" / EXPERIMENT
        )
    args = parser.parse_args(argv)
    try:
        if args.command == "plan":
            data = json_bytes(planned_protocol(load_spec(ROOT / "benchmarks/scifact-v1")))
            if PROTOCOL.exists() and PROTOCOL.read_bytes() != data:
                raise ValueError("Protocol exists; version the experiment rather than overwrite")
            PROTOCOL.parent.mkdir(parents=True, exist_ok=True)
            PROTOCOL.write_bytes(data)
            print(
                "Frozen: 4 development + 16 fresh evaluation queries, two contracts; "
                "no model called"
            )
        elif args.command == "verify":
            verify(args.output_dir)
            print("Contract report verification passed; zero new human judgments")
        else:
            run(
                args.workspace,
                args.output_dir,
                args.backend_info,
                release=args.release_evaluation,
                resume=args.resume,
            )
    except (OSError, ValueError, KeyError, TypeError, httpx.HTTPError):
        parser.exit(
            1, "Experiment failed; inspect local protocol/checkpoint, no raw payload logged\n"
        )


if __name__ == "__main__":
    main()
