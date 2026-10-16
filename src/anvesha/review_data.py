"""ANV-020: versioned multilingual inputs, separate from actual human judgments."""

import argparse
import asyncio
import json
import tempfile
from dataclasses import dataclass
from pathlib import Path

import httpx

from anvesha.eval_data import digest, json_bytes, json_lines, read_json_lines

REVISION = "7d30520c717524000f0d9d2f9c10a069acd9d285"
SOURCE_ROOT = f"https://raw.githubusercontent.com/google-deepmind/xquad/{REVISION}"
SOURCES = {
    "en": "e4c57d1c9143aaa1c5d265ba5987a65f4e69528d2a98f29d6e75019b10344f29",
    "es": "dcbae93ec3a9f4b9e78fd834a171d6f96c1a875e10e15b7530b7e4ef4971e37e",
    "hi": "df2cce3532b37e9beb8979704b5c9a4bf874358f105395a298b89427b43b9d24",
}
DATASET = "xquad-intents-v1"
DEFAULT_BENCHMARK = Path("benchmarks") / DATASET
DEFAULT_DATA = Path(".anvesha/evaluation") / DATASET
MAX_SOURCE_BYTES = 8 * 1024 * 1024
DOWNLOAD_SECONDS = 90
INTENTS = {"navigation", "ambiguity", "exact_constraint", "temporal", "comparison", "multilingual"}
DOMAINS = {
    "history": (
        "Normans",
        "Martin_Luther",
        "Huguenot",
        "Genghis_Khan",
        "Yuan_dynasty",
        "Black_Death",
        "French_and_Indian_War",
        "Imperialism",
    ),
    "geography": (
        "Warsaw",
        "Southern_California",
        "Victoria_(Australia)",
        "Amazon_rainforest",
        "Fresno,_California",
        "Newcastle_upon_Tyne",
        "Jacksonville,_Florida",
        "Kenya",
        "Rhine",
    ),
    "culture_sport_media": (
        "Super_Bowl_50",
        "Sky_(United_Kingdom)",
        "Victoria_and_Albert_Museum",
        "American_Broadcasting_Company",
        "Doctor_Who",
        "United_Methodist_Church",
    ),
    "civics_economics_education": (
        "Teacher",
        "1973_oil_crisis",
        "European_Union_law",
        "Civil_disobedience",
        "Private_school",
        "Harvard_University",
        "Economic_inequality",
        "University_of_Chicago",
        "Scottish_Parliament",
        "Islamism",
    ),
    "technology": (
        "Nikola_Tesla",
        "Computational_complexity_theory",
        "Steam_engine",
        "Apollo_program",
        "Packet_switching",
        "Construction",
    ),
    "science_health": (
        "Oxygen",
        "Ctenophora",
        "Geology",
        "Pharmacy",
        "Immune_system",
        "Intergovernmental_Panel_on_Climate_Change",
        "Chloroplast",
        "Prime_number",
        "Force",
    ),
}


async def download_sources(directory):
    """Fixed pinned URLs only. Failure never replaces an existing individual cache."""
    directory.mkdir(parents=True, exist_ok=True)
    async with (
        asyncio.timeout(DOWNLOAD_SECONDS),
        httpx.AsyncClient(follow_redirects=False, trust_env=False, timeout=15) as client,
    ):
        for language, expected in SOURCES.items():
            temporary = None
            try:
                async with client.stream(
                    "GET",
                    f"{SOURCE_ROOT}/xquad.{language}.json",
                    headers={"Accept-Encoding": "identity", "User-Agent": "AnveshaEvaluation/0.1"},
                ) as response:
                    if response.status_code != 200:
                        raise ValueError(f"Source download returned HTTP {response.status_code}")
                    if response.headers.get("content-encoding", "identity").lower() != "identity":
                        raise ValueError("Unexpected source encoding")
                    with tempfile.NamedTemporaryFile(dir=directory, delete=False) as stream:
                        temporary = Path(stream.name)
                        size = 0
                        async for chunk in response.aiter_raw():
                            size += len(chunk)
                            if size > MAX_SOURCE_BYTES:
                                raise ValueError("Source exceeds size limit")
                            stream.write(chunk)
                if digest(temporary.read_bytes()) != expected:
                    raise ValueError("XQuAD source checksum mismatch")
                temporary.replace(directory / f"xquad.{language}.json")
            finally:
                if temporary is not None:
                    temporary.unlink(missing_ok=True)


def _checked_json(path, expected):
    if path.stat().st_size > MAX_SOURCE_BYTES:
        raise ValueError("Input exceeds size limit")
    raw = path.read_bytes()
    if digest(raw) != expected:
        raise ValueError(f"Input checksum mismatch: {path.name}")
    return json.loads(raw)


def prepare(sources, benchmark, data_dir):
    upstream = {
        lang: _checked_json(sources / f"xquad.{lang}.json", sha) for lang, sha in SOURCES.items()
    }
    english = upstream["en"]["data"]
    domain_by_title = {title: domain for domain, titles in DOMAINS.items() for title in titles}
    if {a["title"] for a in english} != domain_by_title.keys():
        raise ValueError("Reviewed topic taxonomy does not match source articles")
    groups = sorted(domain_by_title, key=lambda title: digest((DATASET + title).encode()))
    heldout = set(groups[:12])
    topics = [
        {
            "id": title,
            "domain": domain_by_title[title],
            "split": "holdout" if title in heldout else "development",
        }
        for title in sorted(groups)
    ]
    by_title = {t["id"]: t for t in topics}
    corpus, queries, mappings = [], [], []
    for lang in SOURCES:
        articles = upstream[lang]["data"]
        if [a["title"] for a in articles] != [a["title"] for a in english]:
            raise ValueError("Parallel article identities differ")
        for article_index, article in enumerate(articles):
            title = article["title"]
            paragraphs = article["paragraphs"]
            if len(paragraphs) != 5:
                raise ValueError("Pinned paragraph count changed")
            for number, paragraph in enumerate(paragraphs):
                original = english[article_index]["paragraphs"][number]
                qa_id = min(q["id"] for q in original["qas"])
                # Selection is independent of retrieval scores and annotation content.
                qa = next(q for q in paragraph["qas"] if q["id"] == qa_id)
                for answer in qa["answers"]:
                    start, text = answer["answer_start"], answer["text"]
                    if paragraph["context"][start : start + len(text)] != text:
                        raise ValueError("Upstream answer/context alignment mismatch")
                did = lang + "-" + digest((title + "\0" + str(number)).encode())[:20]
                qid = lang + "-" + qa_id
                topic = by_title[title]
                corpus.append(
                    {
                        "id": did,
                        "title": title.replace("_", " "),
                        "text": paragraph["context"],
                        "url": f"{SOURCE_ROOT}/xquad.{lang}.json#paragraph={did}",
                        "language": lang,
                        "group": title,
                        "domain": topic["domain"],
                        "license": "CC-BY-SA-4.0",
                        "attribution": "Wikipedia contributors; SQuAD and XQuAD contributors",
                    }
                )
                queries.append(
                    {
                        "id": qid,
                        "text": qa["question"],
                        "language": lang,
                        "group": title,
                        "domain": topic["domain"],
                        "split": topic["split"],
                        "stratum": "factual" if lang == "en" else "multilingual",
                        "origin": "published_xquad_question",
                        "upstream_id": qa_id,
                        "constraints": [],
                        "judgment_origin": "derived_answer_context_mapping",
                    }
                )
                mappings.append({"query_id": qid, "document_id": did, "relevance": 1})
    drafts = read_json_lines((benchmark / "drafts.jsonl").read_bytes())
    for draft in drafts:
        topic = by_title[draft["group"]]
        queries.append(
            {
                **draft,
                "domain": topic["domain"],
                "split": topic["split"],
                "origin": "ai_authored_draft",
                "judgment_origin": "unjudged",
            }
        )
    contents = {
        "queries.jsonl": json_lines(queries),
        "answer_contexts.jsonl": json_lines(mappings),
        "document_ids.txt": ("\n".join(sorted(d["id"] for d in corpus)) + "\n").encode(),
        "topics.json": json_bytes(topics),
        "drafts.jsonl": (benchmark / "drafts.jsonl").read_bytes(),
    }
    corpus_bytes = json_lines(corpus)
    manifest = {
        "schema_version": 1,
        "id": DATASET,
        "task": "ANV-020",
        "revision": REVISION,
        "source_sha256": SOURCES,
        "source_root": SOURCE_ROOT,
        "license": "CC-BY-SA-4.0",
        "query_count": len(queries),
        "document_count": len(corpus),
        "answer_context_mappings": len(mappings),
        "draft_count": len(drafts),
        "corpus_sha256": digest(corpus_bytes),
        "corpus_redistributed": False,
        "selection": "One minimum-ID English question per paragraph, aligned in es/hi; "
        "all passages",
        "split_method": "Lowest 12 SHA256(dataset_id + article_title) articles reserved as holdout",
        "files": {name: {"sha256": digest(raw)} for name, raw in contents.items()},
    }
    contents["manifest.json"] = json_bytes(manifest)
    for name, raw in contents.items():
        path = benchmark / name
        if path.exists() and path.read_bytes() != raw:
            raise ValueError(f"Refusing to change versioned snapshot: {name}")
    data_dir.mkdir(parents=True, exist_ok=True)
    for name, raw in contents.items():
        (benchmark / name).write_bytes(raw)
    (data_dir / "corpus.jsonl").write_bytes(corpus_bytes)
    return load_snapshot(benchmark)


@dataclass(frozen=True)
class ReviewSnapshot:
    manifest: dict
    queries: list[dict]
    document_ids: frozenset[str]
    mappings: dict[str, dict[str, int]]


def load_snapshot(directory):
    manifest = json.loads((directory / "manifest.json").read_bytes())
    if manifest.get("schema_version") != 1 or manifest.get("id") != DATASET:
        raise ValueError("Unsupported review dataset")
    contents = {}
    for name in (
        "queries.jsonl",
        "answer_contexts.jsonl",
        "document_ids.txt",
        "topics.json",
        "drafts.jsonl",
    ):
        raw = (directory / name).read_bytes()
        if digest(raw) != manifest["files"][name]["sha256"]:
            raise ValueError(f"Snapshot checksum mismatch: {name}")
        contents[name] = raw
    topics = json.loads(contents["topics.json"])
    by_group = {row["id"]: row for row in topics}
    ids = contents["document_ids.txt"].decode().splitlines()
    document_ids = frozenset(ids)
    if len(document_ids) != len(ids) or len(ids) != manifest["document_count"]:
        raise ValueError("Duplicate or missing document IDs")
    queries = read_json_lines(contents["queries.jsonl"])
    seen, texts, mappings = set(), set(), {}
    for query in queries:
        key = query["language"], " ".join(query["text"].casefold().split())
        topic = by_group.get(query["group"])
        if (
            query["id"] in seen
            or key in texts
            or query["language"] not in SOURCES
            or not 1 <= len(query["text"].strip()) <= 2000
            or topic is None
            or query["split"] != topic["split"]
            or query["domain"] != topic["domain"]
            or query["split"] not in {"development", "holdout"}
            or not isinstance(query["constraints"], list)
            or not all(isinstance(c, str) for c in query["constraints"])
        ):
            raise ValueError("Invalid query, duplicate or group split leakage")
        if query["origin"] == "ai_authored_draft":
            if query["stratum"] not in INTENTS or query["judgment_origin"] != "unjudged":
                raise ValueError("Draft intent queries must remain unjudged")
        elif (
            query["origin"] != "published_xquad_question"
            or query["judgment_origin"] != "derived_answer_context_mapping"
        ):
            raise ValueError("Unknown query/judgment provenance")
        seen.add(query["id"])
        texts.add(key)
    for row in read_json_lines(contents["answer_contexts.jsonl"]):
        qid, did = row["query_id"], row["document_id"]
        if (
            qid not in seen
            or did not in document_ids
            or type(row["relevance"]) is not int
            or row["relevance"] != 1
            or qid in mappings
        ):
            raise ValueError("Invalid answer-context mapping")
        mappings[qid] = {did: 1}
    if (
        len(queries) != manifest["query_count"]
        or len(mappings) != manifest["answer_context_mappings"]
        or {q["id"] for q in queries if q["origin"] == "published_xquad_question"}
        != mappings.keys()
        or sum(q["origin"] == "ai_authored_draft" for q in queries) != manifest["draft_count"]
    ):
        raise ValueError("Snapshot counts/provenance mismatch")
    return ReviewSnapshot(manifest, queries, document_ids, mappings)


def load_documents(snapshot, data_dir):
    raw = (data_dir / "corpus.jsonl").read_bytes()
    if digest(raw) != snapshot.manifest["corpus_sha256"]:
        raise ValueError("Local corpus checksum mismatch")
    rows = read_json_lines(raw)
    documents = {row["id"]: row for row in rows}
    if len(documents) != len(rows) or set(documents) != snapshot.document_ids:
        raise ValueError("Local corpus IDs differ from snapshot")
    for doc in documents.values():
        if not isinstance(doc["text"], str) or doc["language"] not in SOURCES:
            raise ValueError("Malformed local corpus")
    return documents


def main(argv=None):
    parser = argparse.ArgumentParser(description="Explicit no-key multilingual corpus preparation")
    parser.add_argument("command", choices=("prepare", "verify"))
    parser.add_argument("--benchmark-dir", type=Path, default=DEFAULT_BENCHMARK)
    parser.add_argument("--data-dir", type=Path, default=DEFAULT_DATA)
    parser.add_argument(
        "--sources-dir", type=Path, default=Path(".anvesha/evaluation/xquad-sources")
    )
    parser.add_argument("--download", action="store_true")
    args = parser.parse_args(argv)
    try:
        if args.download and args.command != "prepare":
            raise ValueError("Only prepare --download may use the network")
        if args.command == "prepare":
            if args.download:
                asyncio.run(download_sources(args.sources_dir))
            snapshot = prepare(args.sources_dir, args.benchmark_dir, args.data_dir)
        else:
            snapshot = load_snapshot(args.benchmark_dir)
        print(
            json.dumps(
                {
                    "queries": len(snapshot.queries),
                    "documents": len(snapshot.document_ids),
                    "answer_context_mappings": len(snapshot.mappings),
                    "new_human_judgments": 0,
                }
            )
        )
        return 0
    except (OSError, ValueError, KeyError, StopIteration, TimeoutError, httpx.HTTPError) as exc:
        parser.error(str(exc))


if __name__ == "__main__":
    raise SystemExit(main())
