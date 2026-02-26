"""TF-IDF specificity scoring for feed alignment.

Measures how specific/rare query terms are relative to the product catalog.
High-specificity queries (rare terms) suggest strong purchase intent.
"""

from __future__ import annotations

import logging
from typing import Sequence

import numpy as np
from sklearn.feature_extraction.text import TfidfVectorizer

logger = logging.getLogger(__name__)


class TfidfSpecificityScorer:
    """Scores search queries by term specificity using TF-IDF.

    Higher scores indicate more specific/rare terms relative to the
    product catalog corpus. Unknown terms (not in vocabulary) receive
    80% of max IDF to encourage novel but specific queries.
    """

    def __init__(self) -> None:
        self._vectorizer: TfidfVectorizer | None = None
        self._min_idf: float = 0.0
        self._max_idf: float = 1.0
        self._idf_map: dict[str, float] = {}
        self._is_fitted: bool = False

    def fit(self, documents: Sequence[str]) -> "TfidfSpecificityScorer":
        """Fit the TF-IDF model on product catalog documents.

        Args:
            documents: List of product titles + descriptions.

        Returns:
            Self for chaining.
        """
        if not documents:
            logger.warning("Empty document corpus; TF-IDF scorer will return 0.0")
            self._is_fitted = True
            return self

        self._vectorizer = TfidfVectorizer(
            lowercase=True,
            max_features=50000,
            sublinear_tf=True,
        )
        self._vectorizer.fit(documents)

        # Build IDF lookup map
        vocab = self._vectorizer.vocabulary_
        idf_values = self._vectorizer.idf_
        self._idf_map = {
            term: float(idf_values[idx]) for term, idx in vocab.items()
        }

        if self._idf_map:
            self._min_idf = min(self._idf_map.values())
            self._max_idf = max(self._idf_map.values())
        else:
            self._min_idf = 0.0
            self._max_idf = 1.0

        self._is_fitted = True
        logger.info(
            "TF-IDF fitted on %d documents, vocabulary size: %d, IDF range: [%.2f, %.2f]",
            len(documents),
            len(self._idf_map),
            self._min_idf,
            self._max_idf,
        )
        return self

    def score(self, query: str) -> float:
        """Compute specificity score for a query (0-1).

        Unknown terms receive 80% of max IDF. Score is the normalized
        average IDF across all query tokens.

        Args:
            query: The search query text.

        Returns:
            Float between 0.0 and 1.0. Higher = more specific.
        """
        if not self._is_fitted or not query or not query.strip():
            return 0.0

        # Tokenize same way as vectorizer
        tokens = query.lower().split()
        if not tokens:
            return 0.0

        # Unknown term IDF: 80% of max
        unknown_idf = self._max_idf * 0.80

        idf_values = []
        for token in tokens:
            idf = self._idf_map.get(token, unknown_idf)
            idf_values.append(idf)

        avg_idf = float(np.mean(idf_values))

        # Normalize to 0-1
        idf_range = self._max_idf - self._min_idf
        if idf_range <= 0:
            return 0.0

        normalized = (avg_idf - self._min_idf) / idf_range
        return max(0.0, min(1.0, normalized))

    @classmethod
    def from_supabase(cls, client=None) -> "TfidfSpecificityScorer":
        """Load product catalog from Supabase and fit TF-IDF model.

        Args:
            client: Supabase client. If None, uses get_client().

        Returns:
            Fitted TfidfSpecificityScorer.
        """
        if client is None:
            from feedops.db.supabase_client import get_client
            client = get_client()

        scorer = cls()

        try:
            # Load product titles and descriptions
            result = client.table("product_catalog").select(
                "title, description"
            ).execute()

            documents = []
            for row in result.data or []:
                parts = []
                if row.get("title"):
                    parts.append(str(row["title"]))
                if row.get("description"):
                    parts.append(str(row["description"]))
                if parts:
                    documents.append(" ".join(parts))

            logger.info("Loaded %d documents from product_catalog for TF-IDF", len(documents))
            scorer.fit(documents)

        except Exception as e:
            logger.warning("Failed to load product catalog from Supabase: %s", e)
            scorer._is_fitted = True  # Mark as fitted so it returns 0.0 gracefully

        return scorer
