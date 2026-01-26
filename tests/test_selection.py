from feedops.models import Candidate, Score
from feedops.pipeline.selection import (
    select_best_candidate,
    sanitize_candidate_content,
    _dedupe_product_types,
    _enforce_canonical_product_type,
)
from feedops.quality.scoring import CandidateHeuristicScore, HeuristicScore
import feedops.pipeline.selection as selection_module


def _make_candidate(
    *,
    google_title: str,
    google_description: str,
    bing_title: str | None = None,
    bing_description: str | None = None,
    shopify_title: str | None = None,
    shopify_description: str | None = None,
) -> Candidate:
    return Candidate(
        google_title=google_title,
        google_short_title="Short title",
        google_description=google_description,
        bing_title=bing_title or google_title,
        bing_description=bing_description or google_description,
        shopify_title=shopify_title or google_title,
        shopify_description=shopify_description or "<p>Default description</p>",
        claims=[],
        self_score=Score(
            specificity=5,
            benefit_coverage=5,
            keyword_inclusion=5,
            format_adherence=5,
            brand_voice=5,
            factual_accuracy=5,
        ),
    )


def test_select_best_candidate_prefers_higher_heuristic_score():
    weights = {"google": 1.0, "bing": 0.0, "shopify": 0.0}
    stronger = _make_candidate(
        google_title="18-Inch Wall Mount Towel Bar Solid Brass | Allied Brass",
        google_description=(
            "Add space-saving towel storage with this 18-inch wall mount towel bar crafted from solid brass.\n"
            "- 18-inch center-to-center towel bar\n"
            "- Solid brass construction\n"
            "- Concealed mounting hardware\n"
            "Specs:\n- Overall length: 20 in\n- Projection: 2.5 in\n- Warranty: Limited Lifetime Warranty\n"
        ),
        shopify_description="<p>Upgrade your bath.</p><ul><li>Solid brass</li></ul><p>Center-to-center: 18 in</p>",
    )
    weaker = _make_candidate(
        google_title="Nice Towel Bar",
        google_description="Towel bar.",
    )

    selected, _ranking = select_best_candidate([weaker, stronger], weights)

    assert selected.google_title == stronger.google_title


def test_select_best_candidate_prefers_citation_free():
    weights = {"google": 1.0, "bing": 0.0, "shopify": 0.0}
    leaked = _make_candidate(
        google_title="18-Inch Wall Mount Towel Bar (catalog_csv.Material)",
        google_description="Add storage with solid brass.",
    )
    clean = _make_candidate(
        google_title="18-Inch Wall Mount Towel Bar Solid Brass | Allied Brass",
        google_description="Add storage with solid brass.",
    )

    selected, _ranking = select_best_candidate([leaked, clean], weights)

    assert selected.google_title == clean.google_title


def test_select_best_candidate_sanitizes_when_all_leak():
    weights = {"google": 1.0, "bing": 0.0, "shopify": 0.0}
    leaked = _make_candidate(
        google_title="18-Inch Wall Mount Towel Bar (catalog_csv.Material)",
        google_description="Solid brass build catalog_csv.Material",
    )

    selected, _ranking = select_best_candidate([leaked], weights)

    assert "catalog_csv." not in selected.google_title
    assert "catalog_csv." not in selected.google_description


def test_select_best_candidate_uses_adjusted_score(monkeypatch):
    weights = {"google": 1.0, "bing": 0.0, "shopify": 0.0}
    # Use distinct short titles to identify which candidate was selected
    candidate_a = _make_candidate(
        google_title="18-Inch Wall Mount Towel Bar Solid Brass | Allied Brass",
        google_description="Upgrade your bathroom with solid brass storage. Candidate A marker.",
    )
    candidate_b = _make_candidate(
        google_title="18-Inch Wall Mount Towel Bar Solid Brass | Allied Brass",
        google_description="Upgrade your bathroom with solid brass storage. Candidate B marker.",
    )

    base_platform = HeuristicScore(ctr_proxy=5, cvr_proxy=5, brand_voice=5)

    score_a = CandidateHeuristicScore(
        google=base_platform,
        bing=base_platform,
        shopify=base_platform,
        weighted_composite=90.0,
        soft_gate_penalty=4.0,
        adjusted_weighted_composite=86.0,
        soft_gate_warnings=("Google: Missing structured bullets",),
        soft_gate_miss_counts={"google": 2, "bing": 0, "shopify": 0},
        notes=(),
    )
    score_b = CandidateHeuristicScore(
        google=base_platform,
        bing=base_platform,
        shopify=base_platform,
        weighted_composite=89.5,
        soft_gate_penalty=0.0,
        adjusted_weighted_composite=89.5,
        soft_gate_warnings=(),
        soft_gate_miss_counts={"google": 0, "bing": 0, "shopify": 0},
        notes=(),
    )

    def fake_score_candidate(candidate, *, weights):
        # Match by description content since candidates are now sanitized copies
        if "Candidate A marker" in candidate.google_description:
            return score_a
        return score_b

    monkeypatch.setattr(selection_module, "score_candidate", fake_score_candidate)

    selected, _ranking = select_best_candidate([candidate_a, candidate_b], weights)

    # Check that candidate_b was selected (has higher adjusted score)
    assert "Candidate B marker" in selected.google_description


# Fix 2.3: Short-title redundancy optimizer tests
def test_dedupe_product_types_removes_synonyms():
    """_dedupe_product_types removes redundant synonyms when canonical is present."""
    # Has both "towel bar" and "towel holder" - should remove "towel holder"
    title = "18-Inch Towel Bar Bath Towel Holder"
    result = _dedupe_product_types(title)
    assert "towel bar" in result.lower()
    assert "towel holder" not in result.lower()


def test_dedupe_product_types_preserves_single_type():
    """_dedupe_product_types preserves title when only canonical type present."""
    title = "18-Inch Towel Bar | Allied Brass"
    result = _dedupe_product_types(title)
    assert result == title


def test_dedupe_product_types_case_insensitive():
    """_dedupe_product_types works case-insensitively."""
    title = "18-Inch TOWEL BAR Towel Holder"
    result = _dedupe_product_types(title)
    assert "towel bar" in result.lower()
    assert "towel holder" not in result.lower()


# Fix 2.1: Canonical product type enforcement tests
def test_enforce_canonical_product_type_replaces_synonyms():
    """_enforce_canonical_product_type replaces synonyms with canonical form."""
    title = "18-Inch Towel Holder Wall Mount"
    result = _enforce_canonical_product_type(title, "Towel Bar")
    assert "Towel Bar" in result
    assert "Towel Holder" not in result


def test_enforce_canonical_product_type_case_insensitive():
    """_enforce_canonical_product_type is case-insensitive for matching."""
    title = "18-Inch TOWEL HOLDER Wall Mount"
    result = _enforce_canonical_product_type(title, "Towel Bar")
    assert "Towel Bar" in result


def test_enforce_canonical_product_type_no_change_when_none():
    """_enforce_canonical_product_type returns unchanged title when canonical is None."""
    title = "18-Inch Towel Holder"
    result = _enforce_canonical_product_type(title, None)
    assert result == title


def test_sanitize_candidate_content_with_category():
    """sanitize_candidate_content applies canonical enforcement with category."""
    candidate = _make_candidate(
        google_title="18-Inch towel holder wall mount | Allied Brass",
        google_description="A great towel holder for your bath.",
    )
    sanitized = sanitize_candidate_content(candidate, category="Towel Bars")
    # Check that synonym was replaced with canonical form in title
    assert "Towel Bar" in sanitized.google_title
    assert "towel holder" not in sanitized.google_title.lower()
