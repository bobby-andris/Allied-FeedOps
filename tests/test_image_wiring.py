"""Tests for image wiring through execute_generation_bundle.

Verifies the 4 behaviors described in plan 10-01:
1. SKU with main_image_url gets image forwarded to provider for content tasks.
2. SKU without main_image_url completes normally with image=None.
3. Finish tasks never receive image data regardless of image availability.
4. Image fetch failure does not prevent content generation.
"""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from feedops.generation.executor import execute_generation_bundle
from feedops.models.parent_sku import ParentSKU
from feedops.models.variant import Variant
from feedops.providers.base import ImageInput


# ---------------------------------------------------------------------------
# Shared fixtures
# ---------------------------------------------------------------------------

FAKE_IMAGE = ImageInput(
    data=b"fake-image-bytes",
    mime_type="image/jpeg",
    source_url="https://example.com/product.jpg",
)

_GOOGLE_TITLE_PAYLOAD = {
    "google_title": "{FINISH_NAME} Allied Brass Towel Bar",
    "google_short_title": "Allied Brass Towel Bar",
}
_GOOGLE_DESC_PAYLOAD = {
    "google_description": "Modern towel bar. {FINISH_SENTENCE} Built for daily use.",
}
_BING_TITLE_PAYLOAD = {
    "bing_title": "{FINISH_NAME} Allied Brass Towel Bar",
}
_BING_DESC_PAYLOAD = {
    "bing_description": "Modern towel bar. {FINISH_SENTENCE} Built for daily use.",
}
_SHOPIFY_TITLE_PAYLOAD = {
    "shopify_title": "Allied Brass Towel Bar",
}
_SHOPIFY_DESC_PAYLOAD = {
    "shopify_description": "Modern towel bar in available finishes.",
    "shopify_meta_description": "Buy Allied Brass towel bar.",
}
_FINISH_PAYLOAD = {
    "finish_sentences": {
        "ORB": "Oil Rubbed Bronze finish adds warmth.",
        "SN": "Satin Nickel offers a modern look.",
    },
}


def _make_provider_mock() -> AsyncMock:
    """Create a provider AsyncMock that returns appropriate payloads by schema keys."""

    async def _generate(**kwargs):
        schema = kwargs.get("schema", {})
        properties = schema.get("properties", {})
        if "google_title" in properties:
            return _GOOGLE_TITLE_PAYLOAD
        if "google_description" in properties:
            return _GOOGLE_DESC_PAYLOAD
        if "bing_title" in properties:
            return _BING_TITLE_PAYLOAD
        if "bing_description" in properties:
            return _BING_DESC_PAYLOAD
        if "shopify_title" in properties:
            return _SHOPIFY_TITLE_PAYLOAD
        if "shopify_description" in properties:
            return _SHOPIFY_DESC_PAYLOAD
        if "finish_sentences" in properties:
            return _FINISH_PAYLOAD
        # Fallback: return empty dict with all common keys
        return {
            "google_title": "",
            "google_short_title": "",
            "google_description": "",
            "bing_title": "",
            "bing_description": "",
            "shopify_title": "",
            "shopify_description": "",
            "shopify_meta_description": "",
            "finish_sentences": {},
        }

    provider = MagicMock()
    provider.generate = AsyncMock(side_effect=_generate)
    provider.last_usage = {}
    provider.last_parse_details = {}
    provider.last_retry_counts = {}
    # Make inspect.signature work on AsyncMock by exposing the real sig
    import inspect
    provider.generate.__signature__ = inspect.signature(
        lambda prompt, schema, system_prompt=None,
        reasoning_effort=None, max_completion_tokens=None,
        image=None: None
    )
    return provider


def _make_parent_sku(main_image_url: str | None = None) -> ParentSKU:
    """Build a minimal ParentSKU for testing."""
    variants = []
    if main_image_url is not None:
        variants = [
            Variant(
                option_sku="WP-2/16-ORB",
                finish="Oil Rubbed Bronze",
                finish_code="ORB",
                gmc_id="shopify_US_123456_789012",
                main_image_url=main_image_url,
            )
        ]
    return ParentSKU(
        master_sku="WP-2/16",
        category="Towel Bars",
        current_title="Skyline Collection 18 Inch Towel Bar",
        current_description="Current towel bar description.",
        variants=variants,
    )


# ---------------------------------------------------------------------------
# Test 1: Image is fetched and forwarded to provider for content tasks
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_image_is_fetched_and_forwarded_to_provider() -> None:
    """When parent_sku has variants[0].main_image_url set, fetch_image is called
    once and provider.generate receives the ImageInput for google platform tasks."""
    parent_sku = _make_parent_sku(main_image_url="https://example.com/product.jpg")
    provider = _make_provider_mock()

    with patch(
        "feedops.generation.executor.fetch_image",
        new=AsyncMock(return_value=FAKE_IMAGE),
    ) as mock_fetch:
        bundle = await execute_generation_bundle(
            parent_sku=parent_sku,
            provider=provider,
            selected_platforms=("google",),
            selected_content_types=("title", "description"),
        )

    # fetch_image called exactly once with the main_image_url
    mock_fetch.assert_awaited_once_with("https://example.com/product.jpg")

    # All provider.generate calls for google should receive image=FAKE_IMAGE
    assert provider.generate.await_count > 0
    for call in provider.generate.call_args_list:
        assert call.kwargs.get("image") == FAKE_IMAGE, (
            f"Expected image=FAKE_IMAGE in call kwargs, got: {call.kwargs}"
        )

    # Bundle should have results
    assert len(bundle.results) > 0


# ---------------------------------------------------------------------------
# Test 2: No image URL — generation completes normally with image=None
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_no_image_url_completes_normally() -> None:
    """When parent_sku has no main_image_url, fetch_image is NOT called and
    provider.generate is called with image=None (or image not in kwargs)."""
    parent_sku = _make_parent_sku(main_image_url=None)
    # Ensure no variants at all
    parent_sku = ParentSKU(
        master_sku="WP-2/16",
        category="Towel Bars",
        current_title="Skyline Collection 18 Inch Towel Bar",
        current_description="Current towel bar description.",
        variants=[],
    )
    provider = _make_provider_mock()

    with patch(
        "feedops.generation.executor.fetch_image",
        new=AsyncMock(return_value=FAKE_IMAGE),
    ) as mock_fetch:
        bundle = await execute_generation_bundle(
            parent_sku=parent_sku,
            provider=provider,
            selected_platforms=("google",),
            selected_content_types=("title",),
        )

    # fetch_image should NOT be called when no variants or no main_image_url
    mock_fetch.assert_not_awaited()

    # provider.generate should be called with image=None (or no image kwarg)
    assert provider.generate.await_count > 0
    for call in provider.generate.call_args_list:
        image_kwarg = call.kwargs.get("image", None)
        assert image_kwarg is None, (
            f"Expected image=None in call kwargs, got: {image_kwarg}"
        )

    assert len(bundle.results) > 0


# ---------------------------------------------------------------------------
# Test 3: Finish tasks do not receive image even when image was fetched
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_finish_task_does_not_receive_image() -> None:
    """When a finish task runs, provider.generate is called with image=None
    even when a product image was successfully fetched for the SKU."""
    parent_sku = _make_parent_sku(main_image_url="https://example.com/product.jpg")
    provider = _make_provider_mock()

    with patch(
        "feedops.generation.executor.fetch_image",
        new=AsyncMock(return_value=FAKE_IMAGE),
    ):
        bundle = await execute_generation_bundle(
            parent_sku=parent_sku,
            provider=provider,
            selected_platforms=("google", "finish"),
            selected_content_types=("description",),
        )

    # Should have both google and finish tasks
    platforms_executed = {r.platform for r in bundle.results}
    assert "google" in platforms_executed, "Expected google task in results"
    assert "finish" in platforms_executed, "Expected finish task in results"

    # Verify: google task got FAKE_IMAGE, finish task got None
    # We check provider.generate calls by correlating schema with platform
    for call in provider.generate.call_args_list:
        schema = call.kwargs.get("schema", {})
        properties = schema.get("properties", {})
        if "finish_sentences" in properties:
            # This is the finish task call
            image_kwarg = call.kwargs.get("image", None)
            assert image_kwarg is None, (
                f"Finish task should receive image=None, got: {image_kwarg}"
            )
        else:
            # This is a content task (google description)
            image_kwarg = call.kwargs.get("image", None)
            assert image_kwarg == FAKE_IMAGE, (
                f"Google task should receive FAKE_IMAGE, got: {image_kwarg}"
            )


# ---------------------------------------------------------------------------
# Test 4: Fetch failure does not break generation
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_fetch_failure_does_not_break_generation() -> None:
    """When fetch_image returns None (simulating network error), generation
    proceeds normally with image=None passed to all provider.generate calls."""
    parent_sku = _make_parent_sku(main_image_url="https://example.com/product.jpg")
    provider = _make_provider_mock()

    with patch(
        "feedops.generation.executor.fetch_image",
        new=AsyncMock(return_value=None),  # Simulate fetch failure
    ) as mock_fetch:
        bundle = await execute_generation_bundle(
            parent_sku=parent_sku,
            provider=provider,
            selected_platforms=("google",),
            selected_content_types=("title",),
        )

    # fetch_image was called (URL was present)
    mock_fetch.assert_awaited_once_with("https://example.com/product.jpg")

    # Generation completed without error
    assert len(bundle.results) > 0

    # All provider.generate calls should receive image=None
    assert provider.generate.await_count > 0
    for call in provider.generate.call_args_list:
        image_kwarg = call.kwargs.get("image", None)
        assert image_kwarg is None, (
            f"After fetch failure, image should be None, got: {image_kwarg}"
        )
