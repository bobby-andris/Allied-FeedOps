"""Tests for the feed alignment intent scoring engine.

Tests attribute extraction, TF-IDF specificity scoring, and composite scoring
using mock data (no live Supabase connection needed).
"""

import pytest

from feedops.scoring.attribute_extractor import AttributeExtractor, ExtractionResult
from feedops.scoring.tfidf_scorer import TfidfSpecificityScorer
from feedops.scoring.intent_scorer import IntentScorer


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

MOCK_PRODUCT_TYPES = {
    "Towel Bar",
    "Soap Dish",
    "Toilet Paper Holder",
    "Grab Bar",
    "Shower Rod",
    "Paper Towel Holder",
    "Vanity Mirror",
    "Robe Hook",
}

MOCK_CORPUS = [
    "Polished Chrome 18 Inch Towel Bar Allied Brass Prestige Regal Collection",
    "Oil Rubbed Bronze Soap Dish Waverly Place Collection",
    "Satin Nickel Toilet Paper Holder Montero Collection",
    "Antique Brass 24 Inch Grab Bar Dottingham Collection",
    "Polished Nickel Shower Rod Pacific Grove Collection",
    "Matte Black Paper Towel Holder Retro Dot Collection",
    "Unlacquered Brass Vanity Mirror SoHo Collection",
    "French Gold Robe Hook Continental Collection",
    "Polished Chrome Towel Ring Prestige Skyline Collection",
    "Venetian Bronze 30 Inch Towel Bar Mambo Collection",
]


@pytest.fixture
def extractor():
    """AttributeExtractor with mock product types."""
    return AttributeExtractor(product_types=MOCK_PRODUCT_TYPES)


@pytest.fixture
def tfidf_scorer():
    """TfidfSpecificityScorer fitted on mock corpus."""
    scorer = TfidfSpecificityScorer()
    scorer.fit(MOCK_CORPUS)
    return scorer


@pytest.fixture
def intent_scorer(extractor, tfidf_scorer):
    """IntentScorer combining both sub-scorers."""
    return IntentScorer(extractor, tfidf_scorer)


# ---------------------------------------------------------------------------
# Attribute Extraction Tests
# ---------------------------------------------------------------------------


class TestAttributeExtraction:
    """Tests for AttributeExtractor."""

    def test_empty_query(self, extractor):
        result = extractor.extract("")
        assert result.score() == 0.0
        assert result.matched_attributes == {}

    def test_single_char_query(self, extractor):
        result = extractor.extract("a")
        assert result.score() == 0.0

    def test_numeric_only_query(self, extractor):
        result = extractor.extract("12345")
        assert result.score() == 0.0

    def test_generic_query_no_attributes(self, extractor):
        """'bathroom accessories' has no catalog-specific attributes."""
        result = extractor.extract("bathroom accessories")
        assert result.score() == pytest.approx(0.0, abs=0.01)

    def test_product_type_only(self, extractor):
        """'towel bar' matches product_type (weight 0.15)."""
        result = extractor.extract("towel bar")
        assert "product_type" in result.matched_attributes
        assert result.score() == pytest.approx(0.15, abs=0.01)

    def test_finish_plus_product_type(self, extractor):
        """'polished nickel towel bar' matches finish (0.25) + product_type (0.15) = 0.40."""
        result = extractor.extract("polished nickel towel bar")
        assert "finish" in result.matched_attributes
        assert "product_type" in result.matched_attributes
        assert result.score() == pytest.approx(0.40, abs=0.01)

    def test_collection_dimension_product_type(self, extractor):
        """'prestige regal 18 inch towel bar' = collection(0.30) + dimension(0.25) + product_type(0.15) = 0.70."""
        result = extractor.extract("prestige regal 18 inch towel bar")
        assert "collection" in result.matched_attributes
        assert "dimension" in result.matched_attributes
        assert "product_type" in result.matched_attributes
        assert result.score() == pytest.approx(0.70, abs=0.01)

    def test_model_number_short_circuit(self, extractor):
        """Model number 'PR-41/18-ABR' should short-circuit to score 1.0."""
        result = extractor.extract("PR-41/18-ABR")
        assert result.has_model_number
        assert result.score() == 1.0

    def test_model_number_in_context(self, extractor):
        """Model number in larger query still short-circuits."""
        result = extractor.extract("looking for PR-41/18 towel bar")
        assert result.has_model_number
        assert result.score() == 1.0

    def test_finish_code_word_boundary(self, extractor):
        """Short finish codes like PB should match on word boundary only."""
        result = extractor.extract("PB towel bar")
        assert "finish" in result.matched_attributes
        assert result.matched_attributes["finish"] == "Polished Brass"

    def test_finish_code_not_in_word(self, extractor):
        """'capable' should NOT match 'PB' finish code (substring, not word)."""
        result = extractor.extract("capable holder")
        assert "finish" not in result.matched_attributes

    def test_brand_matching(self, extractor):
        """'allied towel bar' matches brand (0.10) + product_type (0.15) = 0.25."""
        result = extractor.extract("allied towel bar")
        assert "brand" in result.matched_attributes
        assert "product_type" in result.matched_attributes
        assert result.score() == pytest.approx(0.25, abs=0.01)

    def test_collection_fuzzy_match(self, extractor):
        """Fuzzy matching should find collections with minor variations."""
        result = extractor.extract("waverly place soap dish")
        assert "collection" in result.matched_attributes
        assert result.matched_attributes["collection"] == "Waverly Place"

    def test_dimension_various_formats(self, extractor):
        """Dimensions in various formats should be matched."""
        for query in ["18 inch bar", '24" bar', "30 in bar"]:
            result = extractor.extract(query)
            assert "dimension" in result.matched_attributes, f"Failed for: {query}"

    def test_score_capped_at_1(self, extractor):
        """Score should never exceed 1.0 even with many matches."""
        # This has brand + finish + product_type + collection + dimension
        query = "allied brass polished chrome prestige regal 18 inch towel bar"
        result = extractor.extract(query)
        assert result.score() <= 1.0


# ---------------------------------------------------------------------------
# TF-IDF Scorer Tests
# ---------------------------------------------------------------------------


class TestTfidfScorer:
    """Tests for TfidfSpecificityScorer."""

    def test_unfitted_returns_zero(self):
        scorer = TfidfSpecificityScorer()
        assert scorer.score("anything") == 0.0

    def test_empty_query_returns_zero(self, tfidf_scorer):
        assert tfidf_scorer.score("") == 0.0

    def test_common_terms_lower_score(self, tfidf_scorer):
        """Common catalog terms should have lower specificity."""
        common_score = tfidf_scorer.score("towel bar collection")
        assert 0.0 <= common_score <= 1.0

    def test_rare_terms_higher_score(self, tfidf_scorer):
        """Rare/unknown terms should have higher specificity."""
        rare_score = tfidf_scorer.score("xylophone reconditioned")
        common_score = tfidf_scorer.score("polished chrome towel bar")
        assert rare_score > common_score

    def test_unknown_terms_get_high_idf(self, tfidf_scorer):
        """Terms not in vocabulary get 80% of max IDF."""
        score = tfidf_scorer.score("zzzzunknownterm")
        assert score > 0.5  # Should be relatively high

    def test_score_in_range(self, tfidf_scorer):
        """All scores should be in [0, 1]."""
        for query in ["", "towel", "very specific rare term", "chrome 18 inch"]:
            score = tfidf_scorer.score(query)
            assert 0.0 <= score <= 1.0, f"Score out of range for: {query}"

    def test_empty_corpus_returns_zero(self):
        """Scorer fitted on empty corpus should return 0.0."""
        scorer = TfidfSpecificityScorer()
        scorer.fit([])
        assert scorer.score("anything") == 0.0


# ---------------------------------------------------------------------------
# Composite Scoring Tests
# ---------------------------------------------------------------------------


class TestIntentScorer:
    """Tests for IntentScorer composite scoring."""

    def test_composite_weighting(self, intent_scorer):
        """Composite = 0.60 * attribute + 0.40 * specificity."""
        result = intent_scorer.score_term("towel bar")
        # towel bar should have product_type match (attribute_score ~ 0.15)
        assert result["attribute_score"] == pytest.approx(0.15, abs=0.01)
        expected = 0.60 * result["attribute_score"] + 0.40 * result["specificity_score"]
        assert result["feed_alignment_score"] == pytest.approx(expected, abs=0.01)

    def test_model_number_dominates(self, intent_scorer):
        """Model number short-circuits attribute to 1.0."""
        result = intent_scorer.score_term("PR-41/18-ABR")
        assert result["attribute_score"] == 1.0
        assert result["feed_alignment_score"] >= 0.60

    def test_batch_scoring(self, intent_scorer):
        """score_terms returns results for all queries."""
        queries = ["towel bar", "PR-41/18-ABR", "bathroom"]
        results = intent_scorer.score_terms(queries)
        assert len(results) == 3
        assert all("feed_alignment_score" in r for r in results)

    def test_include_details(self, intent_scorer):
        """include_details=True adds matched_attributes."""
        result = intent_scorer.score_term("polished nickel towel bar", include_details=True)
        assert "matched_attributes" in result
        assert "finish" in result["matched_attributes"]

    def test_exclude_details_by_default(self, intent_scorer):
        """matched_attributes not included by default."""
        result = intent_scorer.score_term("polished nickel towel bar")
        assert "matched_attributes" not in result

    def test_empty_query(self, intent_scorer):
        """Empty query should return zero scores."""
        result = intent_scorer.score_term("")
        assert result["attribute_score"] == 0.0
        assert result["specificity_score"] == 0.0
        assert result["feed_alignment_score"] == 0.0

    def test_feed_alignment_capped(self, intent_scorer):
        """Feed alignment score should never exceed 1.0."""
        result = intent_scorer.score_term("PR-41/18-ABR very rare specific model")
        assert result["feed_alignment_score"] <= 1.0

    def test_scoring_gradient(self, intent_scorer):
        """More specific queries should score higher than generic ones."""
        generic = intent_scorer.score_term("bathroom")
        product = intent_scorer.score_term("towel bar")
        specific = intent_scorer.score_term("polished nickel towel bar")
        model = intent_scorer.score_term("PR-41/18-ABR")

        assert generic["feed_alignment_score"] <= product["feed_alignment_score"]
        assert product["feed_alignment_score"] <= specific["feed_alignment_score"]
        assert specific["feed_alignment_score"] <= model["feed_alignment_score"]
