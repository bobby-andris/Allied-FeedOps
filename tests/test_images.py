import httpx
import pytest
from unittest.mock import patch

from feedops.pipeline.images import fetch_image
from feedops.providers.base import ImageInput


class _MockStream:
    def __init__(self, response):
        self._response = response

    async def __aenter__(self):
        return self._response

    async def __aexit__(self, exc_type, exc, tb):
        return None


class _StreamingResponse:
    def __init__(self, status_code: int, headers: dict[str, str], chunks: list[bytes]):
        self.status_code = status_code
        self.headers = headers
        self._chunks = chunks
        self.iterated_chunks = 0

    async def aiter_bytes(self, *args, **kwargs):
        for chunk in self._chunks:
            self.iterated_chunks += 1
            yield chunk


def _client_factory(response):
    class MockAsyncClient:
        def __init__(self, *args, **kwargs):
            self._response = response

        async def __aenter__(self):
            return self

        async def __aexit__(self, exc_type, exc, tb):
            return None

        async def get(self, url: str):
            return self._response

        def stream(self, method: str, url: str):
            return _MockStream(self._response)

    return MockAsyncClient


@pytest.mark.asyncio
async def test_fetch_image_returns_image_input():
    response = _StreamingResponse(
        200,
        headers={"Content-Type": "image/png", "Content-Length": "11"},
        chunks=[b"image-bytes"],
    )

    with patch("feedops.pipeline.images.httpx.AsyncClient", _client_factory(response)):
        result = await fetch_image("https://example.com/image.png")

    assert isinstance(result, ImageInput)
    assert result.data == b"image-bytes"
    assert result.mime_type == "image/png"
    assert result.source_url == "https://example.com/image.png"


@pytest.mark.asyncio
async def test_fetch_image_rejects_non_image_content():
    response = _StreamingResponse(
        200,
        headers={"Content-Type": "text/plain"},
        chunks=[b"not-image"],
    )

    with patch("feedops.pipeline.images.httpx.AsyncClient", _client_factory(response)):
        result = await fetch_image("https://example.com/file.txt")

    assert result is None


@pytest.mark.asyncio
async def test_fetch_image_rejects_large_payload():
    response = _StreamingResponse(
        200,
        headers={"Content-Type": "image/png", "Content-Length": "5"},
        chunks=[b"small"],
    )

    with patch("feedops.pipeline.images.httpx.AsyncClient", _client_factory(response)):
        result = await fetch_image("https://example.com/image.png", max_bytes=4)

    assert result is None


@pytest.mark.asyncio
async def test_fetch_image_stream_rejects_large_payload_without_content_length():
    response = _StreamingResponse(
        200,
        headers={"Content-Type": "image/png"},
        chunks=[b"aaa", b"bb", b"cc"],
    )

    with patch("feedops.pipeline.images.httpx.AsyncClient", _client_factory(response)):
        result = await fetch_image("https://example.com/image.png", max_bytes=4)

    assert result is None
    assert response.iterated_chunks == 2
