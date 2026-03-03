"""Query intent scoring service and /score-intent route handler."""

from __future__ import annotations

import logging
import threading

from fastapi import APIRouter, HTTPException
from feedops.api.schemas import ScoreIntentItem, ScoreIntentRequest, ScoreIntentResponse

logger = logging.getLogger(__name__)

# Lazy-loaded scorer with initialization lock
_intent_scorer = None
_intent_scorer_lock = threading.Lock()

router = APIRouter()


def _get_intent_scorer():
    """Get or lazily initialize the IntentScorer singleton."""
    global _intent_scorer
    if _intent_scorer is not None:
        return _intent_scorer

    with _intent_scorer_lock:
        # Double-check after acquiring lock
        if _intent_scorer is not None:
            return _intent_scorer

        from feedops.scoring.intent_scorer import IntentScorer
        logger.info("Initializing IntentScorer (first request)...")
        _intent_scorer = IntentScorer.from_supabase()
        logger.info("IntentScorer ready")
        return _intent_scorer


def _extract_query_intent_generation_diagnostics(
    generated: dict[str, object] | None,
) -> dict[str, object]:
    if not isinstance(generated, dict):
        return {}
    diagnostics = generated.get("query_intent_diagnostics")
    return dict(diagnostics) if isinstance(diagnostics, dict) else {}


@router.post("/score-intent", response_model=ScoreIntentResponse)
async def api_score_intent(request: ScoreIntentRequest):
    """Score search queries for feed alignment.

    Combines attribute extraction (finishes, collections, product types,
    dimensions, model numbers) with TF-IDF specificity scoring.

    Feed alignment = 0.60 * attribute_score + 0.40 * specificity_score
    """
    from datetime import datetime, timezone

    try:
        scorer = _get_intent_scorer()
        results = scorer.score_terms(
            request.queries, include_details=request.include_details
        )

        scores = []
        for r in results:
            item = ScoreIntentItem(
                query=r["query"],
                feed_alignment_score=r["feed_alignment_score"],
                attribute_score=r["attribute_score"],
                specificity_score=r["specificity_score"],
                matched_attributes=r.get("matched_attributes"),
            )
            scores.append(item)

        return ScoreIntentResponse(
            scores=scores,
            model_version="v1.0",
            scored_at=datetime.now(timezone.utc).isoformat(),
        )
    except Exception as e:
        logger.error("Intent scoring failed: %s", e)
        raise HTTPException(status_code=500, detail=f"Scoring error: {e}")
