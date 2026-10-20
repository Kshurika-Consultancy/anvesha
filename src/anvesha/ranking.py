"""Deterministic reciprocal rank fusion, without a model or paid service."""

from __future__ import annotations

import hashlib
import json
from urllib.parse import urlsplit, urlunsplit

import idna

RRF_CONSTANT = 60
PIPELINE_VERSION = "m1-rrf-v1"
DISCOVERY_FIELDS = (
    "license_url",
    "attribution_url",
    "source_modified_at",
    "observed_at",
    "content_transformation",
)


def canonicalize_url(url: str) -> str:
    """Normalize host/default ports only; preserve query order, paths and fragments."""
    if not isinstance(url, str) or any(c.isspace() or ord(c) < 32 for c in url):
        raise ValueError("invalid candidate URL")
    parts = urlsplit(url)
    if (
        parts.scheme.lower() not in {"http", "https"}
        or not parts.hostname
        or parts.username is not None
        or parts.password is not None
    ):
        raise ValueError("invalid candidate URL")
    scheme = parts.scheme.lower()
    hostname = parts.hostname.lower()
    try:
        host = (
            f"[{hostname}]"
            if ":" in hostname
            else idna.encode(hostname, uts46=True, transitional=False).decode("ascii")
        )
    except idna.IDNAError:
        raise ValueError("invalid candidate URL") from None
    port = parts.port
    if port is not None and (scheme, port) not in {("http", 80), ("https", 443)}:
        host += f":{port}"
    return urlunsplit((scheme, host, parts.path or "/", parts.query, parts.fragment))


def _selection_key(candidate: dict) -> tuple:
    return (
        candidate["evidence_status"] != "local_document",
        candidate["source_rank"],
        candidate["source"],
        candidate["url"],
        candidate["title"],
        candidate["snippet"],
        candidate["license"],
        candidate["attribution"],
        candidate.get("rights_manifest_version", ""),
        json.dumps(
            {key: candidate[key] for key in DISCOVERY_FIELDS if key in candidate}, sort_keys=True
        ),
    )


def rank_candidates(candidates: list[dict], limit: int = 10) -> list[dict]:
    """Fuse one best rank per source/URL, retaining each candidate's own rights.

    The displayed title and snippet come from a single selected candidate. Its
    licence is never assigned to content from a different provider.
    """
    if isinstance(limit, bool) or not isinstance(limit, int) or not 1 <= limit <= 50:
        raise ValueError("limit must be between 1 and 50")
    groups: dict[str, list[dict]] = {}
    for candidate in candidates:
        source_rank = candidate["source_rank"]
        if isinstance(source_rank, bool) or not isinstance(source_rank, int) or source_rank < 1:
            raise ValueError("source_rank must be a positive integer")
        url = canonicalize_url(candidate["url"])
        groups.setdefault(url, []).append(candidate)

    results = []
    for url, group in groups.items():
        ordered = sorted(group, key=_selection_key)
        display = ordered[0]
        ranks: dict[str, int] = {}
        provenance = {}
        for candidate in ordered:
            source = candidate["source"]
            ranks[source] = min(
                ranks.get(source, candidate["source_rank"]), candidate["source_rank"]
            )
            record = {
                key: candidate[key]
                for key in (
                    "source",
                    "url",
                    "source_rank",
                    "license",
                    "attribution",
                    "evidence_status",
                )
            }
            record["rights_manifest_version"] = candidate.get(
                "rights_manifest_version", f"{source}-v1"
            )
            record.update({key: candidate[key] for key in DISCOVERY_FIELDS if key in candidate})
            provenance[json.dumps(record, sort_keys=True)] = record
        results.append(
            {
                "id": "res_" + hashlib.sha256(url.encode()).hexdigest()[:24],
                "url": url,
                "title": display["title"],
                "snippet": display["snippet"],
                "sources": sorted(ranks),
                "score": sum(1 / (RRF_CONSTANT + ranks[source]) for source in sorted(ranks)),
                "evidence_status": display["evidence_status"],
                "license": display["license"],
                "attribution": display["attribution"],
                "display_source": display["source"],
                "provenance": [provenance[key] for key in sorted(provenance)],
                **{key: display[key] for key in DISCOVERY_FIELDS if key in display},
            }
        )
    results.sort(key=lambda result: (-result["score"], result["url"]))
    for rank, result in enumerate(results[:limit], 1):
        result["rank"] = rank
    return results[:limit]
