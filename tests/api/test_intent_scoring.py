"""Unit tests for intent_scoring service module."""
from unittest.mock import patch, MagicMock
import pytest


def test_intent_scoring_importable_without_main():
    """Module imports without triggering main.py startup."""
    from feedops.api.intent_scoring import _get_intent_scorer, router
    assert callable(_get_intent_scorer)
    assert router is not None


def test_get_intent_scorer_singleton_double_check():
    """Singleton initializes exactly once even under repeated calls."""
    import feedops.api.intent_scoring as mod
    # Reset module state to force re-initialization
    original = mod._intent_scorer
    mod._intent_scorer = None
    try:
        mock_instance = MagicMock()
        mock_scorer_cls = MagicMock()
        mock_scorer_cls.from_supabase.return_value = mock_instance

        with patch.dict(
            "sys.modules",
            {"feedops.scoring.intent_scorer": MagicMock(IntentScorer=mock_scorer_cls)},
        ):
            result1 = mod._get_intent_scorer()
            result2 = mod._get_intent_scorer()

        # Second call must return cached instance (singleton)
        assert result1 is result2
        # from_supabase called exactly once
        assert mock_scorer_cls.from_supabase.call_count == 1
    finally:
        mod._intent_scorer = original


def test_extract_query_intent_generation_diagnostics_with_intent():
    """Extracts intent data from generation output dict."""
    from feedops.api.intent_scoring import _extract_query_intent_generation_diagnostics
    generated = {"query_intent_diagnostics": {"primary": "product", "confidence": 0.9}}
    result = _extract_query_intent_generation_diagnostics(generated)
    assert isinstance(result, dict)
    assert result.get("primary") == "product"


def test_extract_query_intent_generation_diagnostics_none_input():
    """Returns empty dict for None input."""
    from feedops.api.intent_scoring import _extract_query_intent_generation_diagnostics
    result = _extract_query_intent_generation_diagnostics(None)
    assert isinstance(result, dict)
    assert result == {}


def test_extract_query_intent_generation_diagnostics_missing_key():
    """Returns empty dict when query_intent_diagnostics key absent."""
    from feedops.api.intent_scoring import _extract_query_intent_generation_diagnostics
    result = _extract_query_intent_generation_diagnostics({"other_key": "value"})
    assert isinstance(result, dict)
    assert result == {}


def test_intent_scoring_router_has_score_intent_route():
    """Router exposes the /score-intent POST route."""
    from feedops.api.intent_scoring import router
    paths = [route.path for route in router.routes]
    assert "/score-intent" in paths
