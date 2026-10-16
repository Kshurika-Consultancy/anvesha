"""ANV-020: explicit fixed-source acquisition and cache-preserving failures."""

import asyncio

import httpx
import pytest

from anvesha import review_data
from anvesha.eval_data import digest


@pytest.mark.parametrize("failure", ["redirect", "checksum", "oversize", "encoding", "timeout"])
def test_acquisition_failures_are_bounded_and_preserve_cache(tmp_path, monkeypatch, failure):
    class Stream(httpx.AsyncByteStream):
        async def __aiter__(self):
            yield b"fixture"

    async def handle(request):
        assert str(request.url) == review_data.SOURCE_ROOT + "/xquad.en.json"
        if failure == "timeout":
            await asyncio.sleep(1)
        if failure == "redirect":
            return httpx.Response(302, headers={"Location": "https://example.org/other"})
        return httpx.Response(
            200,
            stream=Stream(),
            headers={"Content-Encoding": "gzip"} if failure == "encoding" else {},
        )

    original = httpx.AsyncClient
    monkeypatch.setattr(
        httpx, "AsyncClient", lambda **kw: original(transport=httpx.MockTransport(handle), **kw)
    )
    if failure == "oversize":
        monkeypatch.setattr(review_data, "MAX_SOURCE_BYTES", 1)
    if failure == "timeout":
        monkeypatch.setattr(review_data, "DOWNLOAD_SECONDS", 0.01)
    target = tmp_path / "xquad.en.json"
    target.write_bytes(b"previous cache")
    with pytest.raises((ValueError, TimeoutError)):
        asyncio.run(review_data.download_sources(tmp_path))
    assert target.read_bytes() == b"previous cache"
    assert list(tmp_path.iterdir()) == [target]


def test_successful_download_checks_all_three_sources_without_redirects(tmp_path, monkeypatch):
    content = b"verified fixture"

    class Stream(httpx.AsyncByteStream):
        async def __aiter__(self):
            yield content

    seen = []

    async def handle(request):
        assert str(request.url).startswith(review_data.SOURCE_ROOT + "/xquad.")
        seen.append(str(request.url))
        return httpx.Response(200, stream=Stream())

    original = httpx.AsyncClient
    monkeypatch.setattr(
        httpx, "AsyncClient", lambda **kw: original(transport=httpx.MockTransport(handle), **kw)
    )
    monkeypatch.setattr(review_data, "SOURCES", dict.fromkeys(("en", "es", "hi"), digest(content)))
    asyncio.run(review_data.download_sources(tmp_path))
    assert len(seen) == 3
    assert all(path.read_bytes() == content for path in tmp_path.iterdir())


def test_verify_never_downloads_without_explicit_intent(tmp_path, monkeypatch):
    def forbid(*args, **kwargs):
        pytest.fail("Unexpected acquisition")

    monkeypatch.setattr(review_data, "download_sources", forbid)
    with pytest.raises(SystemExit):
        review_data.main(["verify", "--download"])
    with pytest.raises(SystemExit):
        review_data.main(["prepare", "--sources-dir", str(tmp_path / "missing")])
