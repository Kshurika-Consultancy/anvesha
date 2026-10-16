from itertools import permutations

import pytest

from anvesha.ranking import canonicalize_url, rank_candidates


def candidate(url, source="local", rank=1, license="Apache-2.0"):
    return {
        "url": url,
        "title": f"Title from {source}",
        "snippet": f"Snippet from {source}",
        "source": source,
        "source_rank": rank,
        "evidence_status": "local_document" if source == "local" else "metadata_only",
        "license": license,
        "attribution": f"Contributors to {source}",
    }


def test_fusion_credits_each_source_once_and_keeps_content_rights():
    local = candidate("https://www.wikidata.org/wiki/Q42", rank=2)
    wikidata = candidate("https://WWW.WIKIDATA.ORG:443/wiki/Q42", "wikidata", 1, "CC0-1.0")
    duplicate = candidate(local["url"], rank=8)
    result = rank_candidates([local, wikidata, duplicate])[0]
    assert result["score"] == pytest.approx(1 / 62 + 1 / 61)
    assert result["sources"] == ["local", "wikidata"]
    assert result["license"] == "Apache-2.0"
    assert result["snippet"] == "Snippet from local"
    assert result["display_source"] == "local"
    assert {item["license"] for item in result["provenance"]} == {"Apache-2.0", "CC0-1.0"}
    assert result["rank"] == 1


def test_permutations_do_not_change_order_content_or_ids():
    candidates = [
        candidate("https://example.org/b"),
        candidate("https://example.org/a"),
        candidate("https://EXAMPLE.org:443/a"),
    ]
    expected = rank_candidates(candidates)
    for order in permutations(candidates):
        assert rank_candidates(list(order)) == expected
    assert expected[0]["url"] == "https://example.org/a"
    assert expected[0]["id"] != expected[1]["id"]


def test_canonicalization_preserves_potentially_meaningful_variants():
    urls = [
        "http://example.org/a",
        "https://example.org/a",
        "https://example.org/a/",
        "https://example.org/a?x=1&y=2",
        "https://example.org/a?y=2&x=1",
        "https://example.org/a#section",
    ]
    assert len(rank_candidates([candidate(url) for url in urls])) == len(urls)
    assert canonicalize_url("https://EXAMPLE.org:443") == "https://example.org/"


def test_idna_deduplicates_same_host_without_changing_sharp_s_destination():
    unicode_url = "https://faß.de/page"
    ascii_url = "https://xn--fa-hia.de/page"
    different_url = "https://fass.de/page"
    results = rank_candidates(
        [candidate(unicode_url), candidate(ascii_url), candidate(different_url)]
    )
    assert canonicalize_url(unicode_url) == ascii_url
    assert {result["url"] for result in results} == {ascii_url, different_url}
    merged = next(result for result in results if result["url"] == ascii_url)
    assert {record["url"] for record in merged["provenance"]} == {unicode_url, ascii_url}


@pytest.mark.parametrize(
    ("url", "expected"),
    [
        ("https://[2001:DB8::1]:443/page", "https://[2001:db8::1]/page"),
        ("http://[2001:db8::1]:80/page", "http://[2001:db8::1]/page"),
        ("https://[2001:db8::1]:8443/page", "https://[2001:db8::1]:8443/page"),
    ],
)
def test_ipv6_and_default_ports_preserved(url, expected):
    assert canonicalize_url(url) == expected


def test_invalid_idna_is_a_sanitized_value_error():
    with pytest.raises(ValueError, match="^invalid candidate URL$"):
        canonicalize_url("https://\u200d.de/page")


@pytest.mark.parametrize(
    "url",
    [
        "javascript:alert(1)",
        "file:///etc/passwd",
        "https://user:pass@example.org/",
        "https://example.org/a\n",
    ],
)
def test_invalid_url_rejected(url):
    with pytest.raises(ValueError):
        rank_candidates([candidate(url)])


def test_empty_results_are_valid():
    assert rank_candidates([]) == []
