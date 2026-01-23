"""Image fetching helpers for multimodal inputs."""
from __future__ import annotations

import logging
from urllib.parse import urlsplit, urlunsplit

import httpx

from feedops.providers.base import ImageInput

logger = logging.getLogger(__name__)

DEFAULT_TIMEOUT_SECONDS = 5.0
DEFAULT_MAX_BYTES = 5 * 1024 * 1024


def _sanitize_url(url: str) -> str:
    """Strip secrets from URLs for safe logging."""
    try:
        parts = urlsplit(url)
    except Exception:
        return "<invalid-url>"
    netloc = parts.netloc.rsplit("@", 1)[-1]
    return urlunsplit((parts.scheme, netloc, parts.path, "", ""))


async def fetch_image(
    url: str,
    *,
    timeout_seconds: float = DEFAULT_TIMEOUT_SECONDS,
    max_bytes: int = DEFAULT_MAX_BYTES,
) -> ImageInput | None:
    """Fetch an image from a URL and return ImageInput if valid."""
    if not url:
        return None
    safe_url = _sanitize_url(url)

    try:
        timeout = httpx.Timeout(timeout_seconds)
        async with httpx.AsyncClient(timeout=timeout, follow_redirects=True) as client:
            async with client.stream("GET", url) as response:
                if response.status_code >= 400:
                    logger.info(
                        "Image fetch rejected for %s: status %s",
                        safe_url,
                        response.status_code,
                    )
                    return None

                content_type = response.headers.get("Content-Type", "").split(";")[0].strip().lower()
                if not content_type.startswith("image/"):
                    logger.info(
                        "Image fetch rejected for %s: non-image content type %s",
                        safe_url,
                        content_type or "missing",
                    )
                    return None

                content_length = response.headers.get("Content-Length")
                if content_length:
                    try:
                        if int(content_length) > max_bytes:
                            logger.info(
                                "Image fetch rejected for %s: content-length %s exceeds max_bytes %s",
                                safe_url,
                                content_length,
                                max_bytes,
                            )
                            return None
                    except ValueError:
                        logger.debug(
                            "Image fetch warning for %s: invalid content-length %s",
                            safe_url,
                            content_length,
                        )

                data = bytearray()
                async for chunk in response.aiter_bytes():
                    if not chunk:
                        continue
                    data.extend(chunk)
                    if len(data) > max_bytes:
                        logger.info(
                            "Image fetch rejected for %s: streamed size exceeds max_bytes %s",
                            safe_url,
                            max_bytes,
                        )
                        return None

                if not data:
                    logger.info("Image fetch rejected for %s: empty body", safe_url)
                    return None

                return ImageInput(data=bytes(data), mime_type=content_type, source_url=url)
    except httpx.RequestError:
        logger.warning("Image fetch failed for %s: network error", safe_url, exc_info=True)
        return None
    except Exception:
        logger.warning("Image fetch failed for %s: unexpected error", safe_url, exc_info=True)
        return None
