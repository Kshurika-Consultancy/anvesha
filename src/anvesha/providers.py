"""Bounded opt-in discovery at fixed Wikimedia endpoints; no arbitrary fetching."""

from __future__ import annotations

import json
import os
import re
import time
from contextlib import nullcontext
from datetime import UTC, datetime
from email.utils import parsedate_to_datetime

import httpx

WIKIDATA_ENDPOINT = "https://www.wikidata.org/w/api.php"
WIKIPEDIA_ENDPOINT = "https://en.wikipedia.org/w/api.php"
WIKIPEDIA_RIGHTS_VERSION = "wikipedia-discovery-v1"
MAX_RESPONSE_BYTES = 1_048_576
RESPONSE_BUDGET_SECONDS = 15
REQUEST_TIMEOUT_SECONDS = 5
RIGHTS_MANIFEST_VERSION = "wikidata-v1"


class ProviderError(Exception):
    """A public-safe failure code; never include the request or response body."""

    def __init__(self, code: str, retry_after_seconds: int | None = None):
        self.code = code
        self.retry_after_seconds = retry_after_seconds
        super().__init__(code)


def _user_agent(name="ANVESHA_WIKIDATA_USER_AGENT", value=None) -> str:
    value = os.environ.get(name, "") if value is None else value
    if not isinstance(value, str):
        raise ProviderError("invalid_user_agent")
    value = value.strip()
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


def _retry_delay(value: str | None, default=60) -> int:
    """Honor seconds/HTTP dates; oversized delays conservatively pause for years."""
    value = value.strip() if value else value
    if value and value.isascii() and value.isdecimal():
        # Bound parsing/storage without cutting realistic valid waiting periods.
        return max(1, min(int(value[:16]), 2**53)) if len(value) <= 16 else 2**53
    if value:
        try:
            date = parsedate_to_datetime(value)
            if date.tzinfo is None:
                date = date.replace(tzinfo=UTC)
            return max(1, int(date.timestamp() - time.time()) + 1)
        except (ValueError, TypeError, OverflowError):
            pass
    return default


def _read_json(client, endpoint, params, user_agent):
    started = time.monotonic()
    with client.stream(
        "GET",
        endpoint,
        params=params,
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
            raise ProviderError("rate_limited", _retry_delay(response.headers.get("retry-after")))
        if response.status_code == 503:
            raise ProviderError(
                "upstream_http_error", _retry_delay(response.headers.get("retry-after"))
            )
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
        raise ProviderError(
            "upstream_busy" if code == "maxlag" else "upstream_api_error",
            _retry_delay(response.headers.get("retry-after"), default=5)
            if code == "maxlag"
            else None,
        )
    return payload


def _read_response(client: httpx.Client, query: str, limit: int, user_agent: str) -> dict:
    return _read_json(
        client,
        WIKIDATA_ENDPOINT,
        {
            "action": "wbsearchentities",
            "search": query,
            "language": "en",
            "uselang": "en",
            "type": "item",
            "limit": limit,
            "format": "json",
            "maxlag": 5,
        },
        user_agent,
    )


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


def search_wikipedia(query, limit=20, client=None, *, user_agent=None):
    """ANV-028: English main-namespace discovery, never API snippets/article text."""
    if not isinstance(query, str) or not query.strip() or len(query) > 2000:
        raise ProviderError("invalid_query")
    if type(limit) is not int or not 1 <= limit <= 50:
        raise ProviderError("invalid_limit")
    identity = _user_agent("ANVESHA_WIKIPEDIA_USER_AGENT", user_agent)
    context = (
        nullcontext(client)
        if client is not None
        else httpx.Client(trust_env=False, follow_redirects=False)
    )
    try:
        with context as active_client:
            payload = _read_json(
                active_client,
                WIKIPEDIA_ENDPOINT,
                {
                    "action": "query",
                    "list": "search",
                    "srsearch": query,
                    "srnamespace": 0,
                    "srprop": "timestamp|wordcount",
                    "srlimit": limit,
                    "srinfo": "",
                    "format": "json",
                    "formatversion": 2,
                    "maxlag": 5,
                },
                identity,
            )
    except httpx.TimeoutException as exc:
        raise ProviderError("timeout") from exc
    except httpx.HTTPError as exc:
        raise ProviderError("network_error") from exc
    query_data = payload.get("query")
    entries = query_data.get("search") if isinstance(query_data, dict) else None
    if not isinstance(entries, list) or len(entries) > limit:
        raise ProviderError("invalid_response")
    candidates, seen = [], set()
    observed = time.time()
    for rank, entry in enumerate(entries, 1):
        if not isinstance(entry, dict):
            raise ProviderError("invalid_response")
        page_id, title = entry.get("pageid"), entry.get("title")
        count, modified = entry.get("wordcount"), entry.get("timestamp")
        if (
            type(page_id) is not int
            or not 1 <= page_id <= 2**63 - 1
            or page_id in seen
            or type(entry.get("ns")) is not int
            or entry["ns"] != 0
            or not isinstance(title, str)
            or not title.strip()
            or len(title) > 500
            or any(ord(c) < 32 or ord(c) == 127 for c in title)
            or type(count) is not int
            or not 0 <= count <= 1_000_000_000
            or not isinstance(modified, str)
            or not re.fullmatch(r"[0-9]{4}-[0-9]{2}-[0-9]{2}T[0-9]{2}:[0-9]{2}:[0-9]{2}Z", modified)
        ):
            raise ProviderError("invalid_response")
        try:
            datetime.strptime(modified, "%Y-%m-%dT%H:%M:%SZ")
        except ValueError as exc:
            raise ProviderError("invalid_response") from exc
        seen.add(page_id)
        url = f"https://en.wikipedia.org/?curid={page_id}"
        candidates.append(
            {
                "url": url,
                "title": title,
                "snippet": f"Wikipedia article discovery metadata: {count} words; last edited "
                f"{modified}. Article text has not been inspected.",
                "source": "wikipedia",
                "source_rank": rank,
                "evidence_status": "metadata_only",
                "license": "CC-BY-SA-4.0",
                "license_url": "https://creativecommons.org/licenses/by-sa/4.0/",
                "attribution": f"Wikipedia contributors; Wikimedia Foundation ({url})",
                "attribution_url": url,
                "source_modified_at": modified,
                "observed_at": observed,
                "content_transformation": "Metadata summary; no article excerpt copied.",
                "rights_manifest_version": WIKIPEDIA_RIGHTS_VERSION,
            }
        )
    return candidates
