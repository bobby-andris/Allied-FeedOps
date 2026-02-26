"""Intent scoring orchestrator for feed alignment.

Combines attribute extraction (Domain A - Layer 1) and TF-IDF specificity
scoring (Domain A - Layer 2) into a composite feed alignment score.

Composite: 0.60 * attribute_score + 0.40 * specificity_score
"""

from __future__ import annotations

import logging
from typing import Any

from feedops.scoring.attribute_extractor import AttributeExtractor
from feedops.scoring.tfidf_scorer import TfidfSpecificityScorer

logger = logging.getLogger(__name__)

# Composite score weights
ATTRIBUTE_WEIGHT = 0.60
SPECIFICITY_WEIGHT = 0.40


class IntentScorer:
    """Orchestrates feed alignment scoring using attribute extraction and TF-IDF.

    Combines two scoring layers:
    - Layer 1: Attribute extraction (finishes, collections, product types, etc.)
    - Layer 2: TF-IDF specificity (how rare/specific are the query terms)

    Feed alignment composite = 0.60 * attribute_score + 0.40 * specificity_score
    """

    def __init__(
        self,
        attribute_extractor: AttributeExtractor,
        tfidf_scorer: TfidfSpecificityScorer,
    ) -> None:
        self.attribute_extractor = attribute_extractor
        self.tfidf_scorer = tfidf_scorer

    def score_term(self, query: str, include_details: bool = False) -> dict[str, Any]:
        """Score a single search query for feed alignment.

        Args:
            query: The search query text.
            include_details: If True, include matched_attributes in response.

        Returns:
            Dict with query, attribute_score, specificity_score,
            feed_alignment_score, and optionally matched_attributes.
        """
        extraction = self.attribute_extractor.extract(query)
        attribute_score = extraction.score()
        specificity_score = self.tfidf_scorer.score(query)

        feed_alignment_score = (
            ATTRIBUTE_WEIGHT * attribute_score
            + SPECIFICITY_WEIGHT * specificity_score
        )
        # Cap at 1.0
        feed_alignment_score = min(feed_alignment_score, 1.0)

        result: dict[str, Any] = {
            "query": query,
            "attribute_score": round(attribute_score, 4),
            "specificity_score": round(specificity_score, 4),
            "feed_alignment_score": round(feed_alignment_score, 4),
        }

        if include_details:
            result["matched_attributes"] = extraction.matched_attributes

        return result

    def score_terms(
        self, queries: list[str], include_details: bool = False
    ) -> list[dict[str, Any]]:
        """Score a batch of search queries for feed alignment.

        Args:
            queries: List of search query texts.
            include_details: If True, include matched_attributes per query.

        Returns:
            List of scoring result dicts.
        """
        return [self.score_term(q, include_details=include_details) for q in queries]

    @classmethod
    def from_supabase(cls, client=None) -> "IntentScorer":
        """Initialize both sub-scorers from Supabase product_catalog.

        Args:
            client: Supabase client. If None, uses get_client().

        Returns:
            Initialized IntentScorer ready for scoring.
        """
        if client is None:
            from feedops.db.supabase_client import get_client
            client = get_client()

        logger.info("Initializing IntentScorer from Supabase...")
        attribute_extractor = AttributeExtractor.from_supabase(client)
        tfidf_scorer = TfidfSpecificityScorer.from_supabase(client)
        logger.info("IntentScorer initialization complete")

        return cls(attribute_extractor, tfidf_scorer)
