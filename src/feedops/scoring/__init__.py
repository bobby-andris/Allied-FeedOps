"""Feed alignment scoring engine for zero-conversion intent scoring.

Provides attribute extraction and TF-IDF specificity scoring to measure
how closely search queries match the Allied Brass product catalog.
"""

from feedops.scoring.attribute_extractor import AttributeExtractor
from feedops.scoring.tfidf_scorer import TfidfSpecificityScorer
from feedops.scoring.intent_scorer import IntentScorer

__all__ = ["AttributeExtractor", "TfidfSpecificityScorer", "IntentScorer"]
