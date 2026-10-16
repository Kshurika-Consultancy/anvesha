"""Bounded, optional retrieval of Wikidata's CC0 structured entity metadata."""

from __future__ import annotations

import json
import os
import re
import time
from contextlib import nullcontext

import httpx

WIKIDATA_ENDPOINT = "https://www.wikidata.org/w/api.php"
MAX_RESPONSE_BYTES = 1_048_576
RESPONSE_BUDGET_SECONDS = 15
REQUEST_TIMEOUT_SECONDS = 5
RIGHTS_MANIFEST_VERSION = "wikidata-v1"


class ProviderError(Exception):
    """A public-safe failure code; never include the request or response body."""

    def __init__(self, code: str):
        self.code = code
        super().__init__(code)


def _user_agent() -> str:
    value = os.environ.get("ANVESHA_WIKIDATA_USER_AGENT", "").strip()
    if not value:
        raise ProviderError("missing_user_agent")
    if (
        len(value) > 512
        or not value.isascii()
        or any(ord(character) < 32 or ord(character) == 127 for character in value)
        or "Anvesha" not in value
        or not re.search(r"https?://[^\s)]+|[^\s()]+@[^\s()]+", value)
    ):
        raise ProviderError("invalid_user_agent")
    return value


def _read_response(client: httpx.Client, query: str, limit: int, user_agent: str) -> dict:
    started = time.monotonic()
    with client.stream(
        "GET",
        WIKIDATA_ENDPOINT,
        params={
            "action": "wbsearchentities",
            "search": query,
            "language": "en",
            "uselang": "en",
            "type": "item",
            "limit": limit,
            "format": "json",
            "maxlag": 5,
        },
        headers={
            "User-Agent": user_agent,
            "Accept": "application/json",
            "Accept-Encoding": "identity",
        },
        timeout=httpx.Timeout(REQUEST_TIMEOUT_SECONDS),
        follow_redirects=False,
    ) as response:
        if response.is_redirect:
            raise ProviderError("redirect_rejected")
        if response.status_code == 429:
            raise ProviderError("rate_limited")
        if response.status_code != 200:
            raise ProviderError("upstream_http_error")
        if response.headers.get("content-encoding", "identity").lower() != "identity":
            raise ProviderError("unexpected_encoding")
        content_type = response.headers.get("content-type", "").split(";", 1)[0].lower()
        if content_type != "application/json":
            raise ProviderError("invalid_response")
        content_length = response.headers.get("content-length")
        if content_length is not None:
            try:
                size = int(content_length)
            except ValueError as exc:
                raise ProviderError("invalid_response") from exc
            if size < 0 or size > MAX_RESPONSE_BYTES:
                raise ProviderError("response_too_large")
        body = bytearray()
        # Identity encoding prevents compressed data from expanding before the bound.
        for chunk in response.iter_raw():
            if time.monotonic() - started > RESPONSE_BUDGET_SECONDS:
                raise ProviderError("timeout")
            if len(body) + len(chunk) > MAX_RESPONSE_BYTES:
                raise ProviderError("response_too_large")
            body.extend(chunk)
        if time.monotonic() - started > RESPONSE_BUDGET_SECONDS:
            raise ProviderError("timeout")
    try:
        payload = json.loads(body)
    except (ValueError, UnicodeError, RecursionError) as exc:
        raise ProviderError("invalid_response") from exc
    if not isinstance(payload, dict):
        raise ProviderError("invalid_response")
    if "error" in payload:
        error = payload["error"]
        code = error.get("code") if isinstance(error, dict) else None
        raise ProviderError("upstream_busy" if code == "maxlag" else "upstream_api_error")
    return payload


def search_wikidata(query: str, limit: int = 20, client: httpx.Client | None = None) -> list[dict]:
    """Search entity labels/aliases, with no API key and no arbitrary URL fetches.

    The operator must configure an identifying User-Agent with contact information.
    Injected clients remain owned by the caller; redirect rejection applies to both.
    """
    if not isinstance(query, str) or not query.strip() or len(query) > 2000:
        raise ProviderError("invalid_query")
    if isinstance(limit, bool) or not isinstance(limit, int) or not 1 <= limit <= 50:
        raise ProviderError("invalid_limit")
    user_agent = _user_agent()
    context = (
        nullcontext(client)
        if client is not None
        else httpx.Client(trust_env=False, follow_redirects=False)
    )
    try:
        with context as active_client:
            payload = _read_response(active_client, query, limit, user_agent)
    except httpx.TimeoutException as exc:
        raise ProviderError("timeout") from exc
    except httpx.HTTPError as exc:
        raise ProviderError("network_error") from exc

    entries = payload.get("search")
    if not isinstance(entries, list) or len(entries) > limit:
        raise ProviderError("invalid_response")
    candidates = []
    for rank, entry in enumerate(entries, 1):
        if not isinstance(entry, dict):
            raise ProviderError("invalid_response")
        entity_id = entry.get("id")
        if not isinstance(entity_id, str) or not re.fullmatch(r"Q[1-9][0-9]{0,19}", entity_id):
            raise ProviderError("invalid_entity_id")
        title = entry.get("label", entity_id)
        snippet = entry.get("description", "")
        if not isinstance(title, str) or not isinstance(snippet, str):
            raise ProviderError("invalid_response")
        candidates.append(
            {
                "url": f"https://www.wikidata.org/wiki/{entity_id}",
                "title": title[:500],
                "snippet": snippet[:2000],
                "source": "wikidata",
                "source_rank": rank,
                "evidence_status": "metadata_only",
                "license": "CC0-1.0",
                "attribution": f"Wikidata contributors ({entity_id})",
                "rights_manifest_version": RIGHTS_MANIFEST_VERSION,
            }
        )
    return candidates
