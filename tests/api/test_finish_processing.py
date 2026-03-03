"""Unit tests for finish_processing service module."""
from unittest.mock import patch, MagicMock, AsyncMock
import pytest

FINISH_NAMES = ["Antique Brass", "Matte Black", "Polished Chrome"]


def test_finish_processing_importable_without_main():
    """Module imports without triggering main.py startup."""
    from feedops.api.finish_processing import (
        _build_finish_sentences_user_prompt,
        _validate_finish_sentences_payload,
        _enforce_finish_sentence_parity,
    )
    assert callable(_build_finish_sentences_user_prompt)
    assert callable(_validate_finish_sentences_payload)
    assert callable(_enforce_finish_sentence_parity)


def test_build_finish_sentences_user_prompt_contains_sku():
    """Prompt includes master_sku and platform."""
    from feedops.api.finish_processing import _build_finish_sentences_user_prompt
    with patch("feedops.api.finish_processing.get_finish_list", return_value=FINISH_NAMES):
        result = _build_finish_sentences_user_prompt(
            base_description="A sturdy grab bar.",
            master_sku="920D-6",
            platform="google",
        )
    assert "920D-6" in result
    assert "google" in result
    assert "Antique Brass" in result
    assert "finish_sentences" in result


def test_build_finish_sentences_user_prompt_lists_all_finishes():
    """Prompt enumerates every finish in the canonical list."""
    from feedops.api.finish_processing import _build_finish_sentences_user_prompt
    with patch("feedops.api.finish_processing.get_finish_list", return_value=FINISH_NAMES):
        result = _build_finish_sentences_user_prompt(
            base_description="A grab bar.",
            master_sku="TEST-SKU",
            platform="bing",
        )
    for finish in FINISH_NAMES:
        assert finish in result


def test_validate_finish_sentences_payload_accepts_valid():
    """Valid payload returns accepted dict."""
    from feedops.api.finish_processing import _validate_finish_sentences_payload
    with patch("feedops.api.finish_processing.get_finish_list", return_value=FINISH_NAMES), \
         patch("feedops.api.finish_processing.normalize_and_validate_finish_sentences") as mock_nv:
        mock_nv.return_value = ({"Antique Brass": "AB sentence."}, [])
        result = _validate_finish_sentences_payload(
            {"Antique Brass": "AB sentence."},
            base_description="A grab bar.",
            master_sku="920D-6",
            platform="google",
        )
    assert "Antique Brass" in result


def test_validate_finish_sentences_payload_handles_rejection():
    """Rejection increments metrics counter."""
    from feedops.api.finish_processing import _validate_finish_sentences_payload
    with patch("feedops.api.finish_processing.get_finish_list", return_value=FINISH_NAMES), \
         patch("feedops.api.finish_processing.normalize_and_validate_finish_sentences") as mock_nv, \
         patch("feedops.api.finish_processing.metrics_registry") as mock_metrics:
        mock_nv.return_value = ({}, ["Antique Brass", "Matte Black", "Polished Chrome"])
        _validate_finish_sentences_payload(
            {},
            base_description="A grab bar.",
            master_sku="920D-6",
            platform="google",
        )
    mock_metrics.increment.assert_called()


def test_validate_finish_sentences_payload_incomplete_increments_metric():
    """Incomplete coverage (accepted < expected) increments metric."""
    from feedops.api.finish_processing import _validate_finish_sentences_payload
    with patch("feedops.api.finish_processing.get_finish_list", return_value=FINISH_NAMES), \
         patch("feedops.api.finish_processing.normalize_and_validate_finish_sentences") as mock_nv, \
         patch("feedops.api.finish_processing.metrics_registry") as mock_metrics:
        # Only 1 of 3 accepted — should trigger incomplete metric
        mock_nv.return_value = ({"Antique Brass": "AB sentence."}, [])
        _validate_finish_sentences_payload(
            {"Antique Brass": "AB sentence."},
            base_description="A grab bar.",
            master_sku="920D-6",
            platform="google",
        )
    mock_metrics.increment.assert_called()


@pytest.mark.asyncio
async def test_enforce_finish_sentence_parity_kill_switch():
    """When kill switch is active, returns fallback sentences without calling provider."""
    from feedops.api.finish_processing import _enforce_finish_sentence_parity
    mock_provider = MagicMock()
    fallback = {f: f"Fallback for {f}" for f in FINISH_NAMES}

    with patch("feedops.api.finish_processing.get_finish_list", return_value=FINISH_NAMES), \
         patch("feedops.api.finish_processing.finish_sentence_regeneration_enabled", return_value=False), \
         patch("feedops.api.finish_processing.build_fallback_finish_sentences", return_value=fallback), \
         patch("feedops.api.finish_processing.strip_hardcoded_finish_names", return_value="clean content"), \
         patch("feedops.api.finish_processing.strip_generic_finish_count_claims", return_value="clean content"), \
         patch("feedops.api.finish_processing.normalize_base_description_with_finish_placeholder", return_value="normalized content"), \
         patch("feedops.api.finish_processing.metrics_registry") as mock_metrics, \
         patch("feedops.api.finish_processing.log_event"):
        content, sentences = await _enforce_finish_sentence_parity(
            provider=mock_provider,
            content="Some description.",
            master_sku="920D-6",
            platform="google",
            endpoint="/test",
        )

    assert sentences == fallback
    assert content == "normalized content"
    mock_metrics.increment.assert_called()
