"""Unit tests for generation service module."""
from unittest.mock import patch, MagicMock, AsyncMock
import pytest


def test_generation_importable_without_main():
    """Module imports without triggering main.py startup."""
    from feedops.api.generation import (
        _build_generation_user_prompt,
        _execute_regeneration_request,
    )
    assert callable(_build_generation_user_prompt)
    assert callable(_execute_regeneration_request)


def test_build_generation_user_prompt_returns_string():
    """Thin wrapper returns a string prompt via build_core_prompt + apply_feedback_layer."""
    from feedops.api.generation import _build_generation_user_prompt

    mock_sku = MagicMock()
    with patch("feedops.api.generation.build_core_prompt", return_value="core prompt") as mock_core, \
         patch("feedops.api.generation.apply_feedback_layer", return_value="final prompt") as mock_feedback:
        result = _build_generation_user_prompt(
            parent_sku=mock_sku,
            evidence_markdown="# Evidence",
            platform="google",
            content_type="title",
            feedback="Make it catchy",
        )

    assert isinstance(result, str)
    assert result == "final prompt"
    mock_core.assert_called_once()
    mock_feedback.assert_called_once_with("core prompt", corrections=[], session_feedback="Make it catchy")


def test_build_generation_user_prompt_no_feedback():
    """Thin wrapper passes None feedback when not supplied."""
    from feedops.api.generation import _build_generation_user_prompt

    mock_sku = MagicMock()
    with patch("feedops.api.generation.build_core_prompt", return_value="core"), \
         patch("feedops.api.generation.apply_feedback_layer", return_value="result") as mock_feedback:
        _build_generation_user_prompt(
            parent_sku=mock_sku,
            evidence_markdown="",
            platform="bing",
            content_type="description",
        )

    mock_feedback.assert_called_once_with("core", corrections=[], session_feedback=None)


def test_build_generation_user_prompt_passes_finish_code():
    """Thin wrapper passes finish_code and evidence to build_core_prompt."""
    from feedops.api.generation import _build_generation_user_prompt

    mock_sku = MagicMock()
    evidence_list = [{"key": "value"}]
    with patch("feedops.api.generation.build_core_prompt", return_value="core") as mock_core, \
         patch("feedops.api.generation.apply_feedback_layer", return_value="result"):
        _build_generation_user_prompt(
            parent_sku=mock_sku,
            evidence_markdown="",
            platform="shopify",
            content_type="title",
            finish_code="ABR",
            evidence=evidence_list,
        )

    call_kwargs = mock_core.call_args.kwargs
    assert call_kwargs["finish_code"] == "ABR"
    assert call_kwargs["evidence"] == evidence_list


@pytest.mark.asyncio
async def test_execute_regeneration_request_missing_sku_raises_404():
    """Returns 404 HTTPException when SKU not found in Supabase."""
    from fastapi import HTTPException
    from feedops.api.generation import _execute_regeneration_request

    mock_request = MagicMock()
    mock_request.master_sku = "NONEXISTENT-SKU"
    mock_request.platform = "google"
    mock_request.content_type = "title"
    mock_request.tone_style = None
    mock_request.emphasis = None
    mock_request.length_preference = None
    mock_request.feedback = None
    mock_request.save_as_correction = False

    mock_supabase = MagicMock()
    mock_supabase.table.return_value.select.return_value.eq.return_value.in_.return_value.in_.return_value.eq.return_value.execute.return_value.data = []

    with patch("feedops.api.generation.get_client", return_value=mock_supabase), \
         patch("feedops.api.generation.resolve_canonical_master_sku", return_value="NONEXISTENT-SKU"), \
         patch("feedops.api.generation._regeneration_idempotency_key", return_value="key-123"), \
         patch("feedops.api.generation.load_parent_sku_from_supabase", return_value=None), \
         patch("feedops.api.generation.log_event"), \
         patch("feedobs.api.generation.get_provider", MagicMock()) if False else patch("feedops.api.generation.get_provider", MagicMock()):
        with pytest.raises(HTTPException) as exc_info:
            await _execute_regeneration_request(
                request=mock_request,
                request_id="req-test-001",
            )

    assert exc_info.value.status_code == 404
    assert "NONEXISTENT-SKU" in str(exc_info.value.detail)


@pytest.mark.asyncio
async def test_execute_regeneration_request_missing_content_field_raises_502():
    """Returns 502 HTTPException when provider returns empty content for the requested field."""
    from fastapi import HTTPException
    from feedops.api.generation import _execute_regeneration_request

    mock_request = MagicMock()
    mock_request.master_sku = "920D-6"
    mock_request.platform = "google"
    mock_request.content_type = "title"
    mock_request.tone_style = None
    mock_request.emphasis = None
    mock_request.length_preference = None
    mock_request.feedback = None
    mock_request.save_as_correction = False

    mock_parent_sku = MagicMock()
    mock_supabase = MagicMock()
    # sku_corrections query returns no corrections
    mock_supabase.table.return_value.select.return_value.eq.return_value.in_.return_value.in_.return_value.eq.return_value.execute.return_value.data = []

    # generate_per_platform returns dict WITHOUT the google_title field
    generated_result = {"prompt_hashes": {}, "system_prompts": {}, "user_prompts": {}}

    mock_provider = MagicMock()

    with patch("feedops.api.generation.get_client", return_value=mock_supabase), \
         patch("feedops.api.generation.resolve_canonical_master_sku", return_value="920D-6"), \
         patch("feedops.api.generation._regeneration_idempotency_key", return_value="key-abc"), \
         patch("feedops.api.generation.load_parent_sku_from_supabase", return_value=mock_parent_sku), \
         patch("feedops.api.generation.get_provider", return_value=mock_provider), \
         patch("feedops.api.generation.get_platform_system_prompt_hash", return_value="hash-001"), \
         patch("feedops.api.generation.finish_sentence_regeneration_enabled", return_value=False), \
         patch("feedops.api.generation.generate_per_platform", new_callable=AsyncMock, return_value=generated_result), \
         patch("feedops.api.generation.close_provider", new_callable=AsyncMock), \
         patch("feedops.api.generation.log_event"):
        with pytest.raises(HTTPException) as exc_info:
            await _execute_regeneration_request(
                request=mock_request,
                request_id="req-test-002",
            )

    assert exc_info.value.status_code == 502
    assert exc_info.value.detail["code"] == "regenerate_missing_required_platform_field"


@pytest.mark.asyncio
async def test_execute_regeneration_request_calls_persist_and_returns_response():
    """Happy path: provider returns content, persistence is called, response is returned."""
    from feedops.api.generation import _execute_regeneration_request

    mock_request = MagicMock()
    mock_request.master_sku = "920D-6"
    mock_request.platform = "google"
    mock_request.content_type = "title"
    mock_request.tone_style = None
    mock_request.emphasis = None
    mock_request.length_preference = None
    mock_request.feedback = None
    mock_request.save_as_correction = False

    mock_parent_sku = MagicMock()
    mock_supabase = MagicMock()
    mock_supabase.table.return_value.select.return_value.eq.return_value.in_.return_value.in_.return_value.eq.return_value.execute.return_value.data = []

    generated_result = {
        "google_title": "Polished Chrome 6 Inch Grab Bar",
        "prompt_hashes": {"google": "hash-001"},
        "system_prompts": {"google": "system prompt text"},
        "user_prompts": {"google": "user prompt text"},
        "usage_by_platform": {},
        "latency_by_platform": {"google": 1500},
        "retry_by_platform": {},
        "parse_by_platform": {},
        "finish_sentences": None,
        "diagnostic_mode": False,
        "finish_subcall_executed": False,
        "budget_stop_triggered": False,
    }

    persistence_result = {
        "state": "completed",
        "generated_content_id": "gc-001",
        "version": 1,
        "idempotent": False,
    }

    mock_provider = MagicMock()
    mock_provider.name = "openai"

    with patch("feedops.api.generation.get_client", return_value=mock_supabase), \
         patch("feedops.api.generation.resolve_canonical_master_sku", return_value="920D-6"), \
         patch("feedops.api.generation._regeneration_idempotency_key", return_value="key-xyz"), \
         patch("feedops.api.generation.load_parent_sku_from_supabase", return_value=mock_parent_sku), \
         patch("feedops.api.generation.get_provider", return_value=mock_provider), \
         patch("feedops.api.generation.get_platform_system_prompt_hash", return_value="hash-001"), \
         patch("feedops.api.generation.finish_sentence_regeneration_enabled", return_value=False), \
         patch("feedops.api.generation.generate_per_platform", new_callable=AsyncMock, return_value=generated_result), \
         patch("feedops.api.generation.close_provider", new_callable=AsyncMock), \
         patch("feedops.api.generation._persist_regeneration_result", return_value=persistence_result) as mock_persist, \
         patch("feedops.api.generation._persist_finish_prompt_lineage"), \
         patch("feedops.api.generation._emit_generation_summary"), \
         patch("feedops.api.generation._extract_query_intent_generation_diagnostics", return_value={}), \
         patch("feedops.api.generation.log_event"):
        result = await _execute_regeneration_request(
            request=mock_request,
            request_id="req-test-003",
        )

    assert result.success is True
    assert result.master_sku == "920D-6"
    assert result.content == "Polished Chrome 6 Inch Grab Bar"
    assert result.platform == "google"
    assert result.content_type == "title"
    assert result.state == "completed"
    assert result.generated_content_id == "gc-001"
    mock_persist.assert_called_once()
