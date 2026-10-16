import json

import httpx
import pytest

from anvesha import providers
from anvesha.providers import ProviderError, search_wikidata


@pytest.fixture(autouse=True)
def user_agent(monkeypatch):
    monkeypatch.setenv("ANVESHA_WIKIDATA_USER_AGENT", "AnveshaBot/0.1 (https://example.org)")


def json_response(payload, status=200):
    return httpx.Response(
        status,
        headers={"Content-Type": "application/json"},
        stream=httpx.ByteStream(json.dumps(payload).encode()),
    )


def test_fixed_endpoint_original_query_and_only_validated_entity_urls():
    requests = []

    def handle(request):
        requests.append(request)
        return json_response(
            {
                "search": [
                    {
                        "id": "Q42",
                        "label": "Douglas Adams",
                        "description": "English writer",
                        "url": "http://127.0.0.1/private",
                    }
                ]
            }
        )

    with httpx.Client(transport=httpx.MockTransport(handle)) as client:
        results = search_wikidata('"Douglas Adams" -movie', client=client)
        assert not client.is_closed
    assert len(requests) == 1
    assert requests[0].url.host == "www.wikidata.org"
    assert requests[0].url.path == "/w/api.php"
    assert requests[0].url.params["search"] == '"Douglas Adams" -movie'
    assert requests[0].url.params["type"] == "item"
    assert requests[0].headers["Accept-Encoding"] == "identity"
    assert requests[0].headers["User-Agent"].startswith("AnveshaBot/")
    assert results[0]["url"] == "https://www.wikidata.org/wiki/Q42"
    assert results[0]["evidence_status"] == "metadata_only"
    assert results[0]["license"] == "CC0-1.0"
    assert results[0]["rights_manifest_version"] == "wikidata-v1"


def test_redirect_rejected_even_when_injected_client_follows_redirects():
    requests = []

    def handle(request):
        requests.append(request)
        return httpx.Response(302, headers={"Location": "http://127.0.0.1/secret"})

    with httpx.Client(transport=httpx.MockTransport(handle), follow_redirects=True) as client:
        with pytest.raises(ProviderError, match="^redirect_rejected$"):
            search_wikidata("test", client=client)
    assert len(requests) == 1


@pytest.mark.parametrize(
    ("payload", "code"),
    [
        ({"search": [{"id": "Q42/../../secret"}]}, "invalid_entity_id"),
        ({"search": [{"id": "Q0"}]}, "invalid_entity_id"),
        ({"search": [{"id": "P31"}]}, "invalid_entity_id"),
        ({"search": [{"id": "Q42", "label": []}]}, "invalid_response"),
        ({"search": {}}, "invalid_response"),
        ({"error": {"code": "maxlag", "info": "private text"}}, "upstream_busy"),
        ({"error": {"code": "private text"}}, "upstream_api_error"),
        ([], "invalid_response"),
    ],
)
def test_malformed_upstream_is_a_sanitized_failure(payload, code):
    with httpx.Client(transport=httpx.MockTransport(lambda _: json_response(payload))) as client:
        with pytest.raises(ProviderError, match=f"^{code}$"):
            search_wikidata("secret query", client=client)


def test_empty_search_is_success():
    with httpx.Client(
        transport=httpx.MockTransport(lambda _: json_response({"search": []}))
    ) as client:
        assert search_wikidata("unmatched", client=client) == []


@pytest.mark.parametrize("declared_size", [None, "1048577"])
def test_oversized_body_rejected_with_or_without_content_length(declared_size):
    headers = {"Content-Type": "application/json"}
    if declared_size is not None:
        headers["Content-Length"] = declared_size
    response = httpx.Response(
        200, headers=headers, stream=httpx.ByteStream(b"x" * (providers.MAX_RESPONSE_BYTES + 1))
    )
    with httpx.Client(transport=httpx.MockTransport(lambda _: response)) as client:
        with pytest.raises(ProviderError, match="^response_too_large$"):
            search_wikidata("test", client=client)


def test_compressed_response_rejected_before_decoding():
    response = httpx.Response(
        200,
        headers={"Content-Type": "application/json", "Content-Encoding": "gzip"},
        stream=httpx.ByteStream(b"not read"),
    )
    with httpx.Client(transport=httpx.MockTransport(lambda _: response)) as client:
        with pytest.raises(ProviderError, match="^unexpected_encoding$"):
            search_wikidata("test", client=client)


def test_timeout_sanitized():
    def timeout(request):
        raise httpx.ReadTimeout("response contains private query", request=request)

    with httpx.Client(transport=httpx.MockTransport(timeout)) as client:
        with pytest.raises(ProviderError, match="^timeout$"):
            search_wikidata("secret", client=client)


def test_missing_user_agent_fails_without_network(monkeypatch):
    monkeypatch.delenv("ANVESHA_WIKIDATA_USER_AGENT")

    def unexpected_request(_):
        pytest.fail("missing operator contact must not make a request")

    with httpx.Client(transport=httpx.MockTransport(unexpected_request)) as client:
        with pytest.raises(ProviderError, match="^missing_user_agent$"):
            search_wikidata("test", client=client)


def test_rate_limited_is_sanitized_and_not_retried():
    calls = []

    def handle(request):
        calls.append(request)
        return json_response({"sensitive": "not exposed"}, 429)

    with httpx.Client(transport=httpx.MockTransport(handle)) as client:
        with pytest.raises(ProviderError, match="^rate_limited$"):
            search_wikidata("test", client=client)
    assert len(calls) == 1


def test_body_elapsed_budget_rejects_slow_stream(monkeypatch):
    clock = [0.0]
    monkeypatch.setattr("anvesha.providers.time.monotonic", lambda: clock[0])

    class SlowStream(httpx.SyncByteStream):
        def __iter__(self):
            yield b'{"search":'
            clock[0] = providers.RESPONSE_BUDGET_SECONDS + 1
            yield b"[]}"

    response = httpx.Response(
        200, headers={"Content-Type": "application/json"}, stream=SlowStream()
    )
    with httpx.Client(transport=httpx.MockTransport(lambda _: response)) as client:
        with pytest.raises(ProviderError, match="^timeout$"):
            search_wikidata("test", client=client)
