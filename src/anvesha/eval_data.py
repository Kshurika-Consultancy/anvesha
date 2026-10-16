"""ANV-019: pinned, explicit acquisition and validation of evaluation data."""

import asyncio
import csv
import hashlib
import io
import json
import re
import tempfile
import zipfile
from dataclasses import dataclass
from pathlib import Path

import httpx

SOURCE_URL = "https://public.ukp.informatik.tu-darmstadt.de/thakur/BEIR/datasets/scifact.zip"
ARCHIVE_SHA256 = "536e14446a0ba56ed1398ab1055f39fe852686ecad24a6306c80c490fa8e0165"
UPSTREAM_MD5 = "5f7d1de60b170fc8027bb7898e2efca1"
MEMBER_HASHES = {
    "scifact/corpus.jsonl": "dec31c8182f3d744c7d2c09423756fd1d17cbef75808db13ba01cc0aab4d1ac6",
    "scifact/queries.jsonl": "8ff84a7c903f722981cd8d595c022660140c51867b27608a6d4910db86080313",
    "scifact/qrels/train.tsv": "a53f2114831916c096b6c37d9e54da68cef4efdcdbd5ed46533601af972acf1d",
    "scifact/qrels/test.tsv": "0864bb985e0ca2367ba217977e72004d549054b2b06666ed9d4825ac7c21284c",
}
MAX_ARCHIVE_BYTES = 32 * 1024 * 1024
MAX_MEMBER_BYTES = 16 * 1024 * 1024
DOWNLOAD_BUDGET_SECONDS = 90
SPLITS = ("development", "evaluation")


def digest(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def json_bytes(value) -> bytes:
    return (
        json.dumps(value, ensure_ascii=False, sort_keys=True, indent=2, allow_nan=False) + "\n"
    ).encode()


def json_lines(rows) -> bytes:
    return b"".join(
        (json.dumps(row, ensure_ascii=False, sort_keys=True, allow_nan=False) + "\n").encode()
        for row in rows
    )


def read_json_lines(data: bytes) -> list[dict]:
    rows = [json.loads(line) for line in data.decode("utf-8").splitlines() if line.strip()]
    if not all(isinstance(row, dict) for row in rows):
        raise ValueError("JSONL records must be objects")
    return rows


def _identifier(value):
    if not isinstance(value, str) or not re.fullmatch(r"[A-Za-z0-9_-]{1,100}", value):
        raise ValueError("Invalid evaluation identifier")
    return value


def _read_qrels(data, fields):
    reader = csv.DictReader(io.StringIO(data.decode("utf-8")), delimiter="\t")
    if reader.fieldnames != list(fields):
        raise ValueError("Unexpected qrels header")
    qrels = {}
    for row in reader:
        if None in row or any(row[field] is None for field in fields):
            raise ValueError("Malformed qrels row")
        query_id, document_id = (_identifier(row[field]) for field in fields[:2])
        if row[fields[2]] not in {"0", "1"}:
            raise ValueError("This benchmark requires binary relevance labels")
        group = qrels.setdefault(query_id, {})
        if document_id in group:
            raise ValueError("Duplicate query/document judgment")
        group[document_id] = int(row[fields[2]])
    return qrels


async def download_archive(target: Path):
    """One fixed endpoint, strict total timeout, bounded stream, atomic replacement."""
    target.parent.mkdir(parents=True, exist_ok=True)
    temporary = None
    try:
        async with (
            asyncio.timeout(DOWNLOAD_BUDGET_SECONDS),
            httpx.AsyncClient(follow_redirects=False, trust_env=False, timeout=15) as client,
        ):
            async with client.stream(
                "GET",
                SOURCE_URL,
                headers={
                    "User-Agent": "AnveshaEvaluation/0.1 (https://github.com/Kshurika-Consultancy/anvesha)",
                    "Accept-Encoding": "identity",
                },
            ) as response:
                if response.status_code != 200:
                    raise ValueError(f"Dataset download returned HTTP {response.status_code}")
                if response.headers.get("content-encoding", "identity") != "identity":
                    raise ValueError("Unexpected archive encoding")
                with tempfile.NamedTemporaryFile(dir=target.parent, delete=False) as stream:
                    temporary = Path(stream.name)
                    count = 0
                    async for block in response.aiter_raw():
                        count += len(block)
                        if count > MAX_ARCHIVE_BYTES:
                            raise ValueError("Archive exceeds download limit")
                        stream.write(block)
        validate_archive(temporary)
        temporary.replace(target)
    finally:
        if temporary is not None:
            temporary.unlink(missing_ok=True)


def validate_archive(path):
    path = Path(path)
    if path.stat().st_size > MAX_ARCHIVE_BYTES:
        raise ValueError("Archive exceeds size limit")
    data = path.read_bytes()
    if digest(data) != ARCHIVE_SHA256:
        raise ValueError("Dataset archive SHA-256 mismatch; do not silently accept a new snapshot")
    return data


def prepare(archive_path: Path, benchmark_dir: Path, data_dir: Path):
    """Derive public query/qrel files; raw corpus remains only in local data_dir."""
    data = validate_archive(archive_path)
    with zipfile.ZipFile(io.BytesIO(data)) as archive:
        names = archive.namelist()
        if len(names) != len(set(names)):
            raise ValueError("Duplicate archive members")
        members = {}
        for name, expected in MEMBER_HASHES.items():
            info = archive.getinfo(name)
            if info.file_size > MAX_MEMBER_BYTES or info.is_dir():
                raise ValueError("Invalid archive member size/type")
            # Read only fixed named members. Never extract paths from a ZIP.
            content = archive.read(info)
            if digest(content) != expected:
                raise ValueError(f"Dataset member checksum mismatch: {name}")
            members[name] = content
    corpus = read_json_lines(members["scifact/corpus.jsonl"])
    queries = {row["_id"]: row["text"] for row in read_json_lines(members["scifact/queries.jsonl"])}
    upstream_fields = ("query-id", "corpus-id", "score")
    train = _read_qrels(members["scifact/qrels/train.tsv"], upstream_fields)
    test = _read_qrels(members["scifact/qrels/test.tsv"], upstream_fields)
    if len(corpus) != 5183 or len(queries) != 1109 or len(train) != 809 or len(test) != 300:
        raise ValueError("Pinned SciFact dataset counts changed")
    if set(train) & set(test):
        raise ValueError("Upstream query splits overlap")
    test_texts = {" ".join(queries[qid].casefold().split()) for qid in test}
    eligible = [qid for qid in train if " ".join(queries[qid].casefold().split()) not in test_texts]
    selected = sorted(eligible, key=lambda qid: digest(("anvesha-scifact-v1\0" + qid).encode()))[
        :200
    ]
    rows, judgments = [], []
    for split, ids, qrels in (("development", selected, train), ("evaluation", sorted(test), test)):
        for qid in sorted(ids):
            rows.append(
                {
                    "id": qid,
                    "text": queries[qid],
                    "split": split,
                    "upstream_split": "train" if split == "development" else "test",
                    "language": "en",
                    "stratum": "scientific_claim_evidence",
                    "judgment_origin": "published_scifact_expert_annotations",
                }
            )
            judgments.extend((qid, did, grade) for did, grade in sorted(qrels[qid].items()))
    output = io.StringIO(newline="")
    writer = csv.writer(output, delimiter="\t", lineterminator="\n")
    writer.writerow(("query_id", "document_id", "relevance"))
    writer.writerows(judgments)
    files = {
        "queries.jsonl": json_lines(rows),
        "qrels.tsv": output.getvalue().encode(),
        "document_ids.txt": ("\n".join(sorted(row["_id"] for row in corpus)) + "\n").encode(),
    }
    manifest = {
        "schema_version": 1,
        "id": "scifact-v1",
        "task": "ANV-019",
        "reviewed_at": "2026-10-16",
        "source_url": SOURCE_URL,
        "archive_sha256": ARCHIVE_SHA256,
        "upstream_published_md5": UPSTREAM_MD5,
        "upstream_member_sha256": MEMBER_HASHES,
        "query_count": 500,
        "document_count": 5183,
        "qrel_count": len(judgments),
        "splits": {"development": 200, "evaluation": 300},
        "selection": (
            "All BEIR test queries; lowest 200 SHA256(anvesha-scifact-v1 + NUL + train_id), "
            "excluding exact normalized evaluation-query duplicates"
        ),
        "query_qrel_license": "CC-BY-4.0",
        "corpus_database_license": "ODC-By-1.0",
        "corpus_redistributed": False,
        "judgment_origin": "published_scifact_expert_annotations",
        "files": {name: {"sha256": digest(content)} for name, content in files.items()},
        "corpus_sha256": MEMBER_HASHES["scifact/corpus.jsonl"],
    }
    benchmark_dir.mkdir(parents=True, exist_ok=True)
    data_dir.mkdir(parents=True, exist_ok=True)
    # Existing manifests/fixtures are immutable unless regenerated byte-for-byte.
    files["manifest.json"] = json_bytes(manifest)
    for name, content in files.items():
        path = benchmark_dir / name
        if path.exists() and path.read_bytes() != content:
            raise ValueError(f"Refusing to change an existing benchmark snapshot: {name}")
    for name, content in files.items():
        (benchmark_dir / name).write_bytes(content)
    (data_dir / "corpus.jsonl").write_bytes(members["scifact/corpus.jsonl"])
    return load_spec(benchmark_dir)


@dataclass(frozen=True)
class EvaluationSpec:
    manifest: dict
    queries: list[dict]
    qrels: dict[str, dict[str, int]]
    document_ids: frozenset[str]


def load_spec(directory: Path) -> EvaluationSpec:
    manifest = json.loads((directory / "manifest.json").read_bytes())
    if manifest.get("schema_version") != 1 or manifest.get("id") != "scifact-v1":
        raise ValueError("Unsupported benchmark manifest")
    contents = {}
    for name in ("queries.jsonl", "qrels.tsv", "document_ids.txt"):
        content = (directory / name).read_bytes()
        if digest(content) != manifest["files"][name]["sha256"]:
            raise ValueError(f"Benchmark checksum mismatch: {name}")
        contents[name] = content
    queries = read_json_lines(contents["queries.jsonl"])
    ids, normalized, counts = set(), set(), dict.fromkeys(SPLITS, 0)
    for query in queries:
        qid = _identifier(query["id"])
        text, split = query["text"], query["split"]
        if not isinstance(text, str) or not 1 <= len(text.strip()) <= 2000 or split not in SPLITS:
            raise ValueError("Invalid query or split")
        key = " ".join(text.casefold().split())
        if qid in ids or key in normalized:
            raise ValueError("Duplicate query ID/text across benchmark")
        if query.get("judgment_origin") != "published_scifact_expert_annotations":
            raise ValueError("Unexpected judgment provenance")
        if query.get("language") != "en" or query.get("stratum") != "scientific_claim_evidence":
            raise ValueError("Unexpected query language or stratum")
        if query.get("upstream_split") != ("train" if split == "development" else "test"):
            raise ValueError("Upstream split does not match development/evaluation mapping")
        ids.add(qid)
        normalized.add(key)
        counts[split] += 1
    doc_rows = contents["document_ids.txt"].decode().splitlines()
    document_ids = frozenset(_identifier(value) for value in doc_rows)
    if len(document_ids) != len(doc_rows) or len(document_ids) != manifest["document_count"]:
        raise ValueError("Invalid corpus ID count")
    qrels = _read_qrels(contents["qrels.tsv"], ("query_id", "document_id", "relevance"))
    if ids != set(qrels) or len(queries) != manifest["query_count"] or counts != manifest["splits"]:
        raise ValueError("Query count, split, or judgment references do not match manifest")
    if sum(map(len, qrels.values())) != manifest["qrel_count"]:
        raise ValueError("Judgment count differs from manifest")
    for judged in qrels.values():
        if not set(judged) <= document_ids or not any(judged.values()):
            raise ValueError("Each query needs known positive judgments from the corpus")
    return EvaluationSpec(manifest, queries, qrels, document_ids)


def load_corpus(spec: EvaluationSpec, data_dir: Path) -> dict[str, dict]:
    path = data_dir / "corpus.jsonl"
    if path.stat().st_size > MAX_MEMBER_BYTES:
        raise ValueError("Corpus exceeds size limit")
    content = path.read_bytes()
    if digest(content) != spec.manifest["corpus_sha256"]:
        raise ValueError("Corpus checksum mismatch; rerun explicit dataset preparation")
    rows = read_json_lines(content)
    corpus = {}
    for row in rows:
        did = _identifier(row["_id"])
        if did in corpus or any(not isinstance(row.get(key), str) for key in ("title", "text")):
            raise ValueError("Duplicate or malformed corpus document")
        corpus[did] = row
    if set(corpus) != spec.document_ids:
        raise ValueError("Corpus identifiers do not match reviewed snapshot")
    return corpus
