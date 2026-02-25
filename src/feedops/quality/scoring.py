"""Heuristic (offline) content scoring for CTR/CVR/brand voice proxies.

This is not a substitute for real performance data. It is intended to help
compare prompt variants and catch obvious regressions without calling an LLM.

Title Zone Strategy:
- Mobile Zone (1-30 chars): Most critical - must contain keyword anchor
- Desktop Zone (31-70 chars): Critical - determines clicks, should have key specs
- Extended Zone (71-150 chars): High - expands query eligibility
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Any, Optional

from feedops.models import Candidate
from feedops.pipeline.keyword_placement import (
    KeywordPlacementPlan,
    validate_candidate_keyword_placement,
)

_URL_RE = re.compile(r"https?://", re.IGNORECASE)
_CITATION_RE = re.compile(r"catalog_csv\.|\(\s*catalog_csv\.[^)]+\)", re.IGNORECASE)
_ALL_CAPS_WORD_RE = re.compile(r"\b[A-Z]{4,}\b")

# Examples: "18-inch", "18 in", "1-1/2 in", '18"', "0.5 in"
_INCH_RE = re.compile(
    r"(\d+\s*-\s*\d+/\d+|\d+/\d+|\d+(?:\.\d+)?)\s*(?:-\s*)?(?:in\b|inch(?:es)?\b|\")",
    re.IGNORECASE,
)

# Title zone boundaries (based on Google Shopping research)
MOBILE_ZONE_END = 30  # First 30 chars visible on mobile
DESKTOP_ZONE_END = 70  # First 70 chars visible on desktop
MAX_TITLE_LENGTH = 150  # Google Shopping max title length

_PRODUCT_TYPE_PHRASES = [
    "towel bar",
    "towel rail",
    "cabinet knob",
    "grab bar",
    "toilet paper holder",
    "toilet paper stand",
    "toilet tissue",
    "tissue stand",
    "towel ring",
    "robe hook",
    "guest towel",
    "towel holder",
    "towel shelf",
    "soap dish",
    "soap dispenser",
    "glass shelf",
    "wood shelf",
    "wall mirror",
    "vanity mirror",
    "make-up mirror",
    "makeup mirror",
    "shower door",
    "shower curtain",
    "paper towel",
    "wall hook",
    "coat rack",
    "coat stand",
    "retractable",
    "garment rod",
    "squeegee",
    "vanity tray",
    "tissue holder",
    "toothbrush holder",
    "tumbler holder",
    "tumbler toothbrush",
    "basket",
    "towel stand",
    "towel valet",
    "cabinet pull",
    "cabinet handle",
    "drawer pull",
]

_MATERIAL_WORDS = [
    "brass",
    "solid brass",
    "stainless",
    "steel",
    "glass",
    "wood",
    "zinc",
]

_FUNCTIONAL_MODIFIERS = [
    "wall mount",
    "wall-mounted",
    "freestanding",
    "free standing",
    "countertop",
    "vanity top",
    "concealed",
    "ada",
    "pivot",
    "tilt",
    "tilting",
    "retractable",
    "quick",
    "double-sided",
]

_PREMIUM_CUES = [
    "crafted",
    "engineered",
    "precision",
    "enduring",
    "solid brass",
    "lifetime warranty",
    "limited lifetime warranty",
]

_OPENING_ENGAGEMENT_CUES = [
    # Outcome / action verbs (original benefit verbs + broader set)
    "upgrade",
    "add",
    "refresh",
    "protect",
    "keep",
    "organize",
    "maximize",
    "transform",
    "eliminate",
    "create",
    "ensure",
    "simplify",
    "streamline",
    "enjoy",
    "free up",
    "bring",
    "make",
    "turn",
    "feel",
    # Problem-first / question cues
    "need",
    "tired of",
    "looking for",
    "want",
    "struggling",
    "no more",
    "stop",
    "never",
    "imagine",
    "every morning",
    "when guests",
    "running out of",
]

_BANNED_MARKETING = [
    "best",
    "amazing",
    "incredible",
    "perfect",
    "cheap",
    "bargain",
    "free shipping",
    "sale",
    # Hollow marketing words (added for content quality)
    "finest",
    "luxurious",
    "exclusive",
    "exceptional",
    "unparalleled",
    "superior",
    "exquisite",
    "ultimate",
]


@dataclass(frozen=True)
class TitleZoneAnalysis:
    """Analysis of title content placement across visibility zones.

    Google Shopping shows different portions of titles based on device:
    - Mobile: First ~30 characters are most visible
    - Desktop: First ~70 characters determine clicks
    - Extended: 71-150 characters help with algorithm matching
    """

    # Zone content
    mobile_zone: str  # First 30 chars
    desktop_zone: str  # Chars 31-70
    extended_zone: str  # Chars 71+

    # Zone checks
    has_product_type_in_mobile: bool  # Product type in first 30 chars
    has_product_type_in_desktop: bool  # Product type in first 70 chars
    has_dimension_in_mobile: bool  # Dimension in first 30 chars
    has_dimension_in_desktop: bool  # Dimension in first 70 chars
    has_material_in_desktop: bool  # Material in first 70 chars
    has_brand_at_end: bool  # Brand in last segment

    # Score impact
    zone_score: int  # 0-10 score based on zone optimization
    zone_notes: tuple[str, ...]  # Notes about zone issues

    @property
    def is_well_optimized(self) -> bool:
        """Check if title zones are well-optimized for search."""
        return (
            self.has_product_type_in_mobile
            and self.has_dimension_in_desktop
            and self.zone_score >= 6
        )


def analyze_title_zones(title: str) -> TitleZoneAnalysis:
    """Analyze title content placement across visibility zones.

    Google Shopping research shows:
    - First 30 chars are critical for mobile visibility (highest priority)
    - First 70 chars determine desktop clicks (very high priority)
    - 71-150 chars expand query eligibility (high priority)

    Args:
        title: The product title to analyze

    Returns:
        TitleZoneAnalysis with zone breakdown and scoring
    """
    # Extract zones
    mobile_zone = title[:MOBILE_ZONE_END]
    desktop_zone = title[MOBILE_ZONE_END:DESKTOP_ZONE_END]
    extended_zone = title[DESKTOP_ZONE_END:]

    # Combined zones for easier checking
    first_70 = title[:DESKTOP_ZONE_END]

    # Check product type presence
    has_product_type_in_mobile = _contains_any(mobile_zone, _PRODUCT_TYPE_PHRASES)
    has_product_type_in_desktop = _contains_any(first_70, _PRODUCT_TYPE_PHRASES)

    # Check dimension presence
    has_dimension_in_mobile = bool(_INCH_RE.search(mobile_zone))
    has_dimension_in_desktop = bool(_INCH_RE.search(first_70))

    # Check material presence
    has_material_in_desktop = _contains_any(first_70, _MATERIAL_WORDS)

    # Check brand placement (should be at end for lesser-known brands)
    lower_title = title.lower()
    has_brand = "allied brass" in lower_title
    has_brand_at_end = False
    if has_brand:
        # Brand should be in last 20 characters or after last pipe
        brand_pos = lower_title.rfind("allied brass")
        has_brand_at_end = (
            brand_pos >= len(title) - 20 or " | " in title[brand_pos - 5 : brand_pos]
        )

    # Calculate zone score
    score = 0
    notes: list[str] = []

    # Product type in mobile zone (+3 points, critical)
    if has_product_type_in_mobile:
        score += 3
    elif has_product_type_in_desktop:
        score += 1
        notes.append("Product type not in mobile zone (first 30 chars)")
    else:
        notes.append("Product type missing from first 70 chars")

    # Dimension in desktop zone (+2 points, very important)
    if has_dimension_in_mobile:
        score += 2
    elif has_dimension_in_desktop:
        score += 1
        notes.append("Dimension not in mobile zone (first 30 chars)")
    else:
        notes.append("No dimension in first 70 chars")

    # Material in desktop zone (+1 point)
    if has_material_in_desktop:
        score += 1
    else:
        notes.append("Material keyword not in first 70 chars")

    # Functional modifier bonus (+1 point)
    if _contains_any(first_70, _FUNCTIONAL_MODIFIERS):
        score += 1

    # Brand placement (+2 points for correct end placement)
    if has_brand_at_end:
        score += 2
    elif has_brand:
        score += 1
        notes.append("Brand not at end of title (should be last segment)")
    else:
        notes.append("Brand missing from title")

    # Title length penalty
    if len(title) > MAX_TITLE_LENGTH:
        score -= 1
        notes.append(f"Title exceeds {MAX_TITLE_LENGTH} characters")
    elif len(title) < 50:
        notes.append("Title under 50 characters - may miss search coverage")

    return TitleZoneAnalysis(
        mobile_zone=mobile_zone,
        desktop_zone=desktop_zone,
        extended_zone=extended_zone,
        has_product_type_in_mobile=has_product_type_in_mobile,
        has_product_type_in_desktop=has_product_type_in_desktop,
        has_dimension_in_mobile=has_dimension_in_mobile,
        has_dimension_in_desktop=has_dimension_in_desktop,
        has_material_in_desktop=has_material_in_desktop,
        has_brand_at_end=has_brand_at_end,
        zone_score=_clamp_0_10(score),
        zone_notes=tuple(notes),
    )


@dataclass(frozen=True)
class HeuristicScore:
    ctr_proxy: int
    cvr_proxy: int
    brand_voice: int
    readability: int = 10  # Default to max for backwards compatibility
    notes: tuple[str, ...] = ()
    title_zone_analysis: Optional[TitleZoneAnalysis] = None

    @property
    def composite(self) -> float:
        # Include readability in composite (weighted 25% of total)
        return round(
            (self.ctr_proxy + self.cvr_proxy + self.brand_voice + self.readability)
            / 40
            * 100,
            2,
        )


@dataclass(frozen=True)
class SoftGateAssessment:
    miss_count: int
    warnings: tuple[str, ...]
    passes: dict[str, bool]


def _clamp_0_10(value: int) -> int:
    return max(0, min(10, value))


def _clamp_0_100(value: int | float) -> int:
    return max(0, min(100, int(round(value))))


def _contains_any(text: str, phrases: list[str]) -> bool:
    t = text.lower()
    return any(p in t for p in phrases)


def score_title(
    title: str,
    *,
    require_brand: bool = True,
    include_zone_analysis: bool = True,
    platform: str = "google",
) -> tuple[int, list[str], Optional[TitleZoneAnalysis]]:
    """CTR proxy score for a title (0-10).

    Scoring considers:
    - Title zone optimization (mobile, desktop, extended zones)
    - Product type and dimension placement
    - Material and functional modifier presence
    - Brand placement (should be at end for lesser-known brands)
    - Prohibited content (URLs, citations, ALL CAPS, marketing language)
    - Minimum length for Google/Bing (60 chars)

    Args:
        title: The title to score
        require_brand: Whether brand presence is required
        include_zone_analysis: Whether to include detailed zone analysis
        platform: Target platform (google, bing, shopify)

    Returns:
        Tuple of (score, notes, zone_analysis)
    """
    notes: list[str] = []
    score = 0
    zone_analysis = None

    # Hard failures - return immediately
    if _CITATION_RE.search(title):
        notes.append("Citation leakage detected in title")
        return 0, notes, None
    if _URL_RE.search(title):
        notes.append("URL detected in title")
        return 0, notes, None

    # Perform zone analysis
    if include_zone_analysis:
        zone_analysis = analyze_title_zones(title)
        # Add zone notes to overall notes
        notes.extend(zone_analysis.zone_notes)

    length = len(title)
    if length > MAX_TITLE_LENGTH:
        notes.append(f"Title exceeds {MAX_TITLE_LENGTH} characters")
    if 50 <= length <= MAX_TITLE_LENGTH:
        score += 1
    if 70 <= length <= MAX_TITLE_LENGTH:
        score += 1

    # Google/Bing minimum title length penalty
    if platform in ("google", "bing") and length < 60:
        notes.append(f"Title under 60 chars ({length}) -- missing search coverage")
        score -= 1

    # Product type scoring - zone-aware
    if zone_analysis:
        if zone_analysis.has_product_type_in_mobile:
            score += 2  # Best: product type in mobile zone
        elif zone_analysis.has_product_type_in_desktop:
            score += 1  # OK: product type in desktop zone
        else:
            notes.append("No recognized product-type phrase detected")
    else:
        if _contains_any(title, _PRODUCT_TYPE_PHRASES):
            score += 2
        else:
            notes.append("No recognized product-type phrase detected")

    # Dimension scoring - zone-aware
    if zone_analysis:
        if zone_analysis.has_dimension_in_mobile:
            score += 2  # Best: dimension in mobile zone
        elif zone_analysis.has_dimension_in_desktop:
            score += 1  # OK: dimension in desktop zone
        else:
            notes.append("No primary dimension detected in first 70 chars")
    else:
        if _INCH_RE.search(title[:DESKTOP_ZONE_END]):
            score += 2
        else:
            notes.append("No primary dimension detected in first 70 chars")

    # Material scoring
    if zone_analysis:
        if zone_analysis.has_material_in_desktop:
            score += 1
        else:
            notes.append("No material keyword detected")
    else:
        if _contains_any(title, _MATERIAL_WORDS):
            score += 1
        else:
            notes.append("No material keyword detected")

    # Functional modifier bonus
    if _contains_any(title, _FUNCTIONAL_MODIFIERS):
        score += 1

    # Brand scoring - position matters for lesser-known brands
    if require_brand:
        if zone_analysis and zone_analysis.has_brand_at_end:
            score += 1  # Brand properly at end
        elif "allied brass" in title.lower():
            score += 1  # Brand present but not at end
            if not (zone_analysis and zone_analysis.has_brand_at_end):
                # Already noted in zone analysis
                pass
        else:
            notes.append("Brand missing: Allied Brass")

    # Penalties
    if _ALL_CAPS_WORD_RE.search(title):
        notes.append("ALL CAPS word detected")
        score -= 1

    if any(bad in title.lower() for bad in _BANNED_MARKETING):
        notes.append("Promotional/budget language detected")
        score -= 2

    return _clamp_0_10(score), notes, zone_analysis


_TRUST_SIGNAL_PHRASES = [
    "lifetime warranty",
    "limited lifetime warranty",
    "virginia",
    "assembled in",
    "28 designer finishes",
    "28 finishes",
    "designer finishes",
    "42+ collection",
    "42 collection",
    "matching accessories",
    "matching pieces",
]

_ATTRIBUTE_DENSITY_CUES = [
    # Product type cues
    "towel bar",
    "towel rail",
    "grab bar",
    "toilet paper",
    "tissue stand",
    "robe hook",
    "glass shelf",
    "soap dish",
    "soap dispenser",
    "towel ring",
    "cabinet knob",
    "paper towel",
    "wall mirror",
    "makeup mirror",
    "make-up mirror",
    "vanity mirror",
    "coat rack",
    "toothbrush holder",
    "tumbler",
    "towel holder",
    "towel shelf",
    "wall hook",
    "towel stand",
    "towel valet",
    "cabinet pull",
    "cabinet handle",
    "drawer pull",
    # Material/mount cues
    "solid brass",
    "brass construction",
    "wall mount",
    "wall-mounted",
    "freestanding",
    "free standing",
    "countertop",
    "vanity top",
    # Dimension cues are handled by _INCH_RE
]


_PRODUCT_TYPE_SYNONYM_GROUPS = {
    "towel bar": ["towel rack", "towel holder", "towel rail"],
    "grab bar": ["safety bar", "support bar", "bathroom grab bar"],
    "toilet paper holder": ["tissue holder", "toilet roll holder", "tp holder"],
    "robe hook": ["towel hook", "bathroom hook", "wall hook"],
    "glass shelf": ["bathroom shelf", "wall shelf", "floating shelf"],
    "paper towel holder": ["paper towel stand", "kitchen towel holder"],
    "cabinet knob": ["drawer knob", "cabinet pull"],
    "towel ring": ["towel loop", "hand towel holder"],
    "soap dish": ["soap holder", "soap tray"],
    "wall mirror": ["bath mirror", "vanity mirror"],
}

_ROOM_CONTEXT_PHRASES = (
    "bathroom",
    "kitchen",
    "bath ",
    "powder room",
    "laundry",
    "mudroom",
)


def _count_synonym_coverage(text_lower: str) -> int:
    """Count how many product-type synonym groups have 2+ hits in text."""
    for canonical, synonyms in _PRODUCT_TYPE_SYNONYM_GROUPS.items():
        all_terms = [canonical] + synonyms
        hits = sum(1 for term in all_terms if term in text_lower)
        if hits >= 2:
            return hits
    return 0


def score_description(
    description: str, *, html: bool = False, platform: str = "google"
) -> tuple[int, list[str]]:
    """CVR proxy score for a description (0-10).

    Platform-aware: Google/Bing reward attribute density in the opening;
    Shopify rewards engagement hooks and trust signals.
    """
    notes: list[str] = []
    score = 0

    if _CITATION_RE.search(description):
        notes.append("Citation leakage detected in description")
        return 0, notes
    if _URL_RE.search(description):
        notes.append("URL detected in description")
        return 0, notes

    text = description
    if html:
        # Very lightweight HTML stripping for scoring.
        text = re.sub(r"<[^>]+>", " ", description)
        text = re.sub(r"\s+", " ", text).strip()
        if "<p" in description.lower():
            score += 1
        if "<ul" in description.lower() and "<li" in description.lower():
            score += 1
        else:
            notes.append("Missing <ul><li> highlights block")

    text_len = len(text)
    if platform == "google":
        if 600 <= text_len <= 800:
            score += 2
        elif 500 <= text_len <= 900:
            score += 1
            notes.append("Description outside ideal 600-800 character target for Google")
        elif text_len >= 300:
            notes.append("Description under 500 characters")
        else:
            notes.append("Description under 300 characters")
    elif platform == "bing":
        if 700 <= text_len <= 1000:
            score += 2
        elif 600 <= text_len <= 1100:
            score += 1
            notes.append("Description outside ideal 700-1000 character target for Bing")
        elif text_len >= 300:
            notes.append("Description under 600 characters for Bing")
        else:
            notes.append("Description under 300 characters")
    else:  # shopify
        if 600 <= text_len <= 1000:
            score += 2
        elif text_len >= 500:
            score += 1
            notes.append("Description outside ideal 600-1000 character target range")
        elif text_len >= 300:
            notes.append("Description under 500 characters")
        else:
            notes.append("Description under 300 characters")

    opening = text[:160].lower()

    if platform in ("google", "bing"):
        # Feed fuel: reward attribute density in first 150 chars
        first_150 = text[:150].lower()
        attr_hits = sum(1 for cue in _ATTRIBUTE_DENSITY_CUES if cue in first_150)
        has_dim_in_opening = bool(_INCH_RE.search(text[:150]))
        if attr_hits >= 2 or (attr_hits >= 1 and has_dim_in_opening):
            score += 2
        elif attr_hits >= 1:
            score += 1
            notes.append("Opening has few searchable attributes (feed fuel)")
        else:
            notes.append("Opening lacks searchable attributes -- should lead with product type + specs")
    else:
        # Shopify: reward engagement hooks (original behavior)
        if any(w in opening for w in _OPENING_ENGAGEMENT_CUES):
            score += 2
        else:
            notes.append(
                "Opening may lack engagement hook (no problem/outcome cue detected)"
            )

    # Specs presence: at least 3 numeric/measurement tokens.
    measurements = len(_INCH_RE.findall(text)) + len(
        re.findall(r"\b\d+(?:\.\d+)?\s*(?:lb|lbs|pound|pounds)\b", text, re.I)
    )
    if measurements >= 3:
        score += 2
    else:
        notes.append("Few measurable specs detected")

    if not html and platform == "shopify":
        # Shopify plain-text structure cues (not applicable to Google/Bing feed fuel).
        lower = description.lower()
        bullet_lines = [
            line.strip()
            for line in description.splitlines()
            if line.strip().startswith(("-", "\u2022"))
        ]
        if len(bullet_lines) >= 3:
            score += 1
        else:
            notes.append("Missing structured highlights bullets")

        if re.search(r"\b(specs?|specifications)\b", lower) and measurements >= 3:
            score += 1
        else:
            notes.append("Missing specs section")

    # Trust signal scoring -- platform-aware weighting
    text_lower = text.lower()
    trust_hits = sum(1 for phrase in _TRUST_SIGNAL_PHRASES if phrase in text_lower)

    if platform == "shopify":
        # Shopify: trust signals in first 200 chars are highly valuable
        first_200 = text[:200].lower()
        early_trust_hits = sum(
            1 for phrase in _TRUST_SIGNAL_PHRASES if phrase in first_200
        )
        score += min(3, early_trust_hits * 2)  # +2 each, max +6 -> clamped to +3 here
        if early_trust_hits == 0 and trust_hits == 0:
            notes.append("No trust signals found (warranty, Virginia, finishes)")
    else:
        # Google/Bing: +1 for "lifetime warranty" or "solid brass" anywhere
        if "lifetime warranty" in text_lower or "solid brass" in text_lower:
            score += 1

    if platform in ("google", "bing"):
        # Synonym coverage: reward inclusion of product-type synonyms
        # (e.g., "towel bar" + "towel rack" + "towel holder")
        synonym_hits = _count_synonym_coverage(text_lower)
        if synonym_hits >= 2:
            score += 1

        # Room context: reward explicit room-type mention
        if any(room in text_lower for room in _ROOM_CONTEXT_PHRASES):
            score += 1

    if "installation" in text_lower or "mounting" in text_lower:
        score += 1

    if "!" in description:
        notes.append("Exclamation point detected")
        score -= 1
    if any(bad in text_lower for bad in _BANNED_MARKETING):
        notes.append("Promotional/budget language detected")
        score -= 2

    return _clamp_0_10(score), notes


def score_readability(text: str, *, platform: str = "google") -> tuple[int, list[str]]:
    """Readability proxy score (0-10). Penalizes egregiously robotic content.

    Philosophy: We're not enforcing rigid rules. We're catching obvious
    problems that hurt brand perception. Good writing has rhythm - a long
    sentence followed by a short one can work well. We only penalize
    egregious issues.

    Scoring criteria (lenient):
    - Dimension dump in opening: -3 (this is clearly robotic)
    - Keyword list at end: -2 (looks like SEO spam)
    - Very long sentences (>150 chars): -1 each (max -2)
    - Brand-only fragment at end: -1 (minor issue)

    Args:
        text: The description text to score
        platform: Target platform (only google/bing are scored)

    Returns:
        Tuple of (score 0-10, list of notes)
    """
    notes: list[str] = []

    # Only score Google/Bing -- Shopify descriptions are already human-focused
    if platform not in ("google", "bing"):
        return 10, notes

    score = 10  # Start at max, subtract for issues

    if not text or len(text) < 50:
        return score, notes

    # Split into sentences (accounting for decimal numbers like "2.5 in")
    sentences = re.split(r"(?<!\d)\.(?!\d)\s*", text)
    sentences = [s.strip() for s in sentences if s.strip()]

    # Penalty: Dimension dump in opening (clearly robotic)
    # Pattern: "Finished in X, product, 18.75 in L x 2.25 in H..."
    dimension_dump_pattern = r"^(?:Finished in \w+[\w\s]*,\s*)?[^,]+,\s*\d+(?:\.\d+)?\s*(?:in|inch)"
    if re.match(dimension_dump_pattern, text, re.IGNORECASE):
        score -= 3
        notes.append("Opens with dimension dump -- needs natural prose")

    # Penalty: Keyword list at end (SEO spam pattern)
    # Pattern: "Fits X hardware, Y accessories, Z fixtures"
    keyword_list_pattern = (
        r"(?:fits|matches|complements|coordinates with|works with)\s+"
        r"(?:\w+\s+)?(?:bathroom|bath|kitchen)\s+(?:hardware|accessories|fixtures)"
        r"(?:\s*,\s*(?:\w+\s+)?(?:bathroom|bath|kitchen)\s+(?:hardware|accessories|fixtures)){1,}\.?\s*$"
    )
    if re.search(keyword_list_pattern, text, re.IGNORECASE):
        score -= 2
        notes.append("Ends with keyword list -- integrate naturally")

    # Penalty: Very long sentences (>150 chars is genuinely hard to read)
    # Note: 100-150 chars is fine - good writing has varied sentence length
    very_long = [s for s in sentences if len(s) > 150]
    if very_long:
        penalty = min(2, len(very_long))
        score -= penalty
        notes.append(f"{len(very_long)} sentence(s) over 150 chars")

    # Penalty: Ends with brand-only fragment (minor issue)
    if re.search(r"\.\s*Allied Brass\.?\s*$", text):
        score -= 1
        notes.append("Ends with brand-only fragment")

    return _clamp_0_10(score), notes


def score_finish_integration(
    description: str, finish_name: str, *, platform: str = "google"
) -> tuple[int, list[str]]:
    """Score how naturally a finish is integrated into a variant description (0-10).

    Good integration:
    - Finish appears once, woven naturally into prose
    - Finish in first sentence, positioned like "This towel bar in Polished Chrome..."
    - Finish followed by benefit/coordination language, not repeated

    Bad integration (penalized):
    - "Available in X. X features..." pattern (repetitive, robotic)
    - Finish name repeated 3+ times (over-optimization)
    - Finish mentioned but not in first 200 chars (buried)

    Args:
        description: The variant description to score
        finish_name: The expected finish name (e.g., "Antique Brass")
        platform: Target platform (google, bing, shopify)

    Returns:
        Tuple of (score 0-10, list of notes)
    """
    notes: list[str] = []
    score = 10  # Start at max, subtract for issues

    if not description or not finish_name:
        return score, notes

    text_lower = description.lower()
    finish_lower = finish_name.lower()

    # Count finish occurrences
    finish_count = text_lower.count(finish_lower)

    # Check for the problematic "Available in X. X features..." pattern
    awkward_pattern = rf"available in {re.escape(finish_lower)}[.!?]\s*{re.escape(finish_lower)}\s+(?:features?|offers?|delivers?|brings?|provides?|makes?)"
    if re.search(awkward_pattern, text_lower):
        score -= 4
        notes.append(f"Awkward pattern: 'Available in {finish_name}. {finish_name} features...'")

    # Check if finish appears in first 200 chars (should be early for variant descriptions)
    first_200 = text_lower[:200]
    if finish_lower not in first_200:
        score -= 2
        notes.append(f"Finish '{finish_name}' not in first 200 characters")

    # Check if finish is repeated too many times (over-optimization)
    if finish_count >= 4:
        score -= 2
        notes.append(f"Finish '{finish_name}' appears {finish_count} times (over-optimized)")
    elif finish_count >= 3:
        score -= 1
        notes.append(f"Finish '{finish_name}' appears {finish_count} times")

    # Bonus: Check for natural integration patterns
    # Good: "in [Finish]" or "[Finish] finish" or "This [product] in [Finish]"
    natural_patterns = [
        rf"\bin {re.escape(finish_lower)}\b",  # "in Polished Chrome"
        rf"{re.escape(finish_lower)} finish\b",  # "Polished Chrome finish"
        rf"this .{{0,30}}\bin {re.escape(finish_lower)}\b",  # "This towel bar in Polished Chrome"
    ]
    has_natural_integration = any(
        re.search(p, first_200) for p in natural_patterns
    )
    if has_natural_integration and finish_count <= 2:
        # Natural integration, not over-repeated - this is good
        pass  # Keep full score
    elif finish_count == 0:
        # Finish not mentioned at all (might be a master SKU description)
        score -= 1
        notes.append(f"Finish '{finish_name}' not found in description")

    # Check for truncated sentences (common in post-processing)
    # Pattern: sentence ending with comma or mid-word
    truncation_pattern = r"[a-z]{3},\.|\.\."
    if re.search(truncation_pattern, text_lower):
        score -= 1
        notes.append("Possible truncated sentence detected")

    return _clamp_0_10(score), notes


def assess_soft_gates(
    *,
    title: str,
    description: str,
    html_description: bool = False,
    platform: str = "shopify",
) -> SoftGateAssessment:
    """Evaluate structure signals without hard-failing.

    Platform-aware: Google/Bing feed descriptions are attribute-dense by design
    and should NOT be penalised for missing engagement hooks or HTML bullets,
    which are Shopify-specific quality signals.
    """
    warnings: list[str] = []

    has_dimension = bool(_INCH_RE.search(title[:70]))
    if not has_dimension:
        warnings.append("Title missing primary dimension in first 70 chars")

    text = description
    if html_description:
        text = re.sub(r"<[^>]+>", " ", description)
        text = re.sub(r"\s+", " ", text).strip()

    # Engagement hook: only relevant for Shopify (shopper-facing copy).
    # Google/Bing feed descriptions lead with attributes by design.
    if platform == "shopify":
        opening = text[:160].lower()
        has_benefit_verb = any(w in opening for w in _OPENING_ENGAGEMENT_CUES)
        if not has_benefit_verb:
            warnings.append("Opening lacks engagement hook")
    else:
        has_benefit_verb = True  # Not applicable for feed platforms

    # Structured bullets: only relevant for Shopify HTML descriptions.
    # Google/Bing feed descriptions are plain text by design.
    if platform == "shopify":
        if html_description:
            lower_html = description.lower()
            has_bullets = "<ul" in lower_html and "<li" in lower_html
        else:
            bullet_lines = [
                line.strip()
                for line in description.splitlines()
                if line.strip().startswith(("-", "•"))
            ]
            has_bullets = len(bullet_lines) >= 3
        if not has_bullets:
            warnings.append("Missing structured bullets")
    else:
        has_bullets = True  # Not applicable for feed platforms

    lower_text = text.lower()
    measurements = len(_INCH_RE.findall(text)) + len(
        re.findall(r"\b\d+(?:\.\d+)?\s*(?:lb|lbs|pound|pounds)\b", text, re.I)
    )
    has_specs_header = bool(re.search(r"\b(specs?|specifications)\b", lower_text))
    has_specs = measurements >= 3 or (has_specs_header and measurements >= 1)
    if not has_specs:
        warnings.append("Few measurable specs detected")

    passes = {
        "dimension_in_first_70": has_dimension,
        "benefit_verb_opening": has_benefit_verb,
        "has_bullets": has_bullets,
        "has_specs": has_specs,
    }

    miss_count = sum(1 for passed in passes.values() if not passed)
    return SoftGateAssessment(
        miss_count=miss_count,
        warnings=tuple(warnings),
        passes=passes,
    )


def score_brand_voice(text: str) -> tuple[int, list[str]]:
    """Brand voice proxy score (0-10)."""
    notes: list[str] = []
    score = 5  # neutral baseline

    t = text.lower()
    cue_hits = sum(1 for cue in _PREMIUM_CUES if cue in t)
    # Diminishing returns: first 2 hits = +1 each, next 2 = +1 each, cap at +4
    if cue_hits >= 1:
        score += min(2, cue_hits)       # +1 or +2 for first 2
    if cue_hits >= 3:
        score += min(2, cue_hits - 2)   # +1 or +2 for next 2

    # Reward natural voice (absence of generic filler patterns)
    generic_fillers = ["this product", "this item", "this piece", "our product"]
    if not any(filler in t for filler in generic_fillers):
        score += 1

    if _ALL_CAPS_WORD_RE.search(text):
        notes.append("ALL CAPS word detected")
        score -= 2
    if "!" in text:
        notes.append("Exclamation point detected")
        score -= 1
    if any(bad in t for bad in _BANNED_MARKETING):
        notes.append("Promotional/budget language detected")
        score -= 3

    return _clamp_0_10(score), notes


def score_bundle(
    *,
    title: str,
    description: str,
    html_description: bool = False,
    platform: str = "google",
) -> HeuristicScore:
    """Convenience scorer combining title+description into a composite.

    Includes detailed title zone analysis for understanding keyword placement.
    Includes readability scoring for Google/Bing feed descriptions.
    """
    # Normalize title separators before scoring to match export format
    normalized_title = title.replace(" | ", ", ").replace("|", ", ")
    normalized_title = re.sub(r"\s{2,}", " ", normalized_title).strip()

    ctr, ctr_notes, zone_analysis = score_title(normalized_title, platform=platform)
    cvr, cvr_notes = score_description(
        description, html=html_description, platform=platform
    )
    voice, voice_notes = score_brand_voice(title + "\n" + description)
    readability, readability_notes = score_readability(description, platform=platform)
    notes = tuple(
        dict.fromkeys([*ctr_notes, *cvr_notes, *voice_notes, *readability_notes])
    )
    return HeuristicScore(
        ctr_proxy=ctr,
        cvr_proxy=cvr,
        brand_voice=voice,
        readability=readability,
        notes=notes,
        title_zone_analysis=zone_analysis,
    )


def _policy_component_score(
    text: str,
    policy_violations: list[str] | None = None,
) -> int:
    violations = [v for v in (policy_violations or []) if isinstance(v, str) and v.strip()]
    score = 100
    if _CITATION_RE.search(text):
        score -= 35
    if _URL_RE.search(text):
        score -= 35
    if _ALL_CAPS_WORD_RE.search(text):
        score -= 10
    score -= min(60, len(violations) * 12)
    return _clamp_0_100(score)


def _uniqueness_score(text: str) -> int:
    tokens = re.findall(r"[a-z0-9]+", (text or "").lower())
    if not tokens:
        return 0
    unique_ratio = len(set(tokens)) / len(tokens)
    repeated_token_penalty = sum(1 for token in set(tokens) if tokens.count(token) >= 4)
    score = int(unique_ratio * 100) - (repeated_token_penalty * 8)
    return _clamp_0_100(score)


def compute_title_quality_index(
    title: str,
    *,
    platform: str = "google",
    policy_violations: list[str] | None = None,
) -> dict[str, Any]:
    """Compute Phase 28 title quality index (0-100) with weighted components."""
    title = str(title or "").strip()
    zone = analyze_title_zones(title)
    title_score, title_notes, _ = score_title(
        title,
        platform=platform,
        include_zone_analysis=True,
    )

    query_match_coverage = 0
    if zone.has_product_type_in_mobile:
        query_match_coverage += 35
    elif zone.has_product_type_in_desktop:
        query_match_coverage += 25
    if zone.has_dimension_in_mobile:
        query_match_coverage += 35
    elif zone.has_dimension_in_desktop:
        query_match_coverage += 25
    if zone.has_material_in_desktop:
        query_match_coverage += 15
    if len(title) >= 50:
        query_match_coverage += 15
    query_match_coverage = _clamp_0_100(query_match_coverage)

    readability_fluency = 100
    if len(title) > MAX_TITLE_LENGTH:
        readability_fluency -= 25
    if len(title) < 40:
        readability_fluency -= 20
    if _ALL_CAPS_WORD_RE.search(title):
        readability_fluency -= 20
    if re.search(r"[|]{2,}|[-]{3,}|[,]{3,}", title):
        readability_fluency -= 15
    readability_fluency = _clamp_0_100(readability_fluency)

    policy_compliance = _policy_component_score(title, policy_violations)

    specificity = 0
    if _contains_any(title, _PRODUCT_TYPE_PHRASES):
        specificity += 35
    if _INCH_RE.search(title):
        specificity += 30
    if _contains_any(title, _MATERIAL_WORDS):
        specificity += 20
    if _contains_any(title, _FUNCTIONAL_MODIFIERS):
        specificity += 15
    specificity = _clamp_0_100(specificity)

    uniqueness = _uniqueness_score(title)

    overall = _clamp_0_100(
        query_match_coverage * 0.30
        + readability_fluency * 0.25
        + policy_compliance * 0.20
        + specificity * 0.15
        + uniqueness * 0.10
    )

    return {
        "overall": overall,
        "components": {
            "query_match_coverage": query_match_coverage,
            "readability_fluency": readability_fluency,
            "policy_compliance": policy_compliance,
            "specificity": specificity,
            "uniqueness": uniqueness,
        },
        "notes": list(dict.fromkeys(title_notes + list(zone.zone_notes))),
        "base_score_0_10": title_score,
    }


def compute_description_quality_index(
    description: str,
    *,
    platform: str = "google",
    html: bool = False,
    policy_violations: list[str] | None = None,
) -> dict[str, Any]:
    """Compute Phase 28 description quality index (0-100) with weighted components."""
    description = str(description or "").strip()
    opening = description[:160].lower()
    first_150 = description[:150].lower()

    benefit_cues = sum(1 for cue in _OPENING_ENGAGEMENT_CUES if cue in opening)
    benefit_first_opening = 35
    if benefit_cues >= 2:
        benefit_first_opening = 95
    elif benefit_cues == 1:
        benefit_first_opening = 75
    if platform in {"google", "bing"} and _INCH_RE.search(first_150):
        benefit_first_opening = min(100, benefit_first_opening + 10)
    benefit_first_opening = _clamp_0_100(benefit_first_opening)

    readability_score, readability_notes = score_readability(description, platform=platform)
    flow_readability = _clamp_0_100(readability_score * 10)
    sentence_chunks = [s.strip() for s in re.split(r"(?<!\d)\.(?!\d)\s*", description) if s.strip()]
    if sentence_chunks:
        avg_sentence_len = sum(len(s.split()) for s in sentence_chunks) / len(sentence_chunks)
        if avg_sentence_len > 26:
            flow_readability = _clamp_0_100(flow_readability - 12)
        elif avg_sentence_len < 7:
            flow_readability = _clamp_0_100(flow_readability - 8)

    factual_grounding = 0
    measurement_hits = len(_INCH_RE.findall(description))
    weight_hits = len(
        re.findall(r"\b\d+(?:\.\d+)?\s*(?:lb|lbs|pound|pounds)\b", description, re.I)
    )
    material_hits = sum(1 for cue in _MATERIAL_WORDS if cue in description.lower())
    factual_grounding += min(45, (measurement_hits + weight_hits) * 12)
    factual_grounding += min(35, material_hits * 12)
    if "solid brass" in description.lower():
        factual_grounding += 20
    factual_grounding = _clamp_0_100(factual_grounding)

    cvr_score, cvr_notes = score_description(description, html=html, platform=platform)
    conversion_utility = _clamp_0_100(cvr_score * 10)
    if platform == "shopify" and "<li" in description.lower():
        conversion_utility = _clamp_0_100(conversion_utility + 8)

    policy_compliance = _policy_component_score(description, policy_violations)

    overall = _clamp_0_100(
        benefit_first_opening * 0.20
        + flow_readability * 0.20
        + factual_grounding * 0.25
        + conversion_utility * 0.20
        + policy_compliance * 0.15
    )

    notes = list(dict.fromkeys(readability_notes + cvr_notes))
    return {
        "overall": overall,
        "components": {
            "benefit_first_opening": benefit_first_opening,
            "flow_readability": flow_readability,
            "factual_grounding": factual_grounding,
            "conversion_utility": conversion_utility,
            "policy_compliance": policy_compliance,
        },
        "notes": notes,
        "base_score_0_10": cvr_score,
    }


def compute_platform_quality_indices(
    *,
    platform: str,
    title: str,
    description: str,
    html_description: bool = False,
    policy_violations: list[str] | None = None,
) -> dict[str, Any]:
    """Return title/description Phase 28 quality indices for one platform."""
    title_index = compute_title_quality_index(
        title,
        platform=platform,
        policy_violations=policy_violations,
    )
    description_index = compute_description_quality_index(
        description,
        platform=platform,
        html=html_description,
        policy_violations=policy_violations,
    )
    return {
        "title_quality_index": title_index,
        "description_quality_index": description_index,
    }


@dataclass(frozen=True)
class CandidateHeuristicScore:
    google: HeuristicScore
    bing: HeuristicScore
    shopify: HeuristicScore
    weighted_composite: float
    soft_gate_penalty: float
    adjusted_weighted_composite: float
    soft_gate_warnings: tuple[str, ...] = ()
    soft_gate_miss_counts: dict[str, int] | None = None
    notes: tuple[str, ...] = ()


def score_candidate(
    candidate: Candidate,
    *,
    weights: dict[str, float],
    keyword_plan: KeywordPlacementPlan | None = None,
) -> CandidateHeuristicScore:
    """Score a candidate across platforms using weighted composites."""
    google_score = score_bundle(
        title=candidate.google_title,
        description=candidate.google_description,
        platform="google",
    )
    bing_score = score_bundle(
        title=candidate.bing_title,
        description=candidate.bing_description,
        platform="bing",
    )
    shopify_score = score_bundle(
        title=candidate.shopify_title,
        description=candidate.shopify_description,
        html_description=True,
        platform="shopify",
    )

    soft_gates = {
        "google": assess_soft_gates(
            title=candidate.google_title,
            description=candidate.google_description,
            platform="google",
        ),
        "bing": assess_soft_gates(
            title=candidate.bing_title,
            description=candidate.bing_description,
            platform="bing",
        ),
        "shopify": assess_soft_gates(
            title=candidate.shopify_title,
            description=candidate.shopify_description,
            html_description=True,
            platform="shopify",
        ),
    }

    weighted_total = 0.0
    weight_sum = 0.0
    weighted_misses = 0.0
    weighted_keyword_misses = 0.0
    per_platform = {
        "google": google_score,
        "bing": bing_score,
        "shopify": shopify_score,
    }
    keyword_miss_by_platform = {"google": 0, "bing": 0, "shopify": 0}
    if keyword_plan:
        for error in validate_candidate_keyword_placement(candidate, keyword_plan):
            if error.startswith("google_"):
                keyword_miss_by_platform["google"] += 1
            elif error.startswith("bing_"):
                keyword_miss_by_platform["bing"] += 1
            elif error.startswith("shopify_"):
                keyword_miss_by_platform["shopify"] += 1

    for platform, score in per_platform.items():
        weight = weights.get(platform, 0.0)
        if weight <= 0:
            continue
        keyword_misses = keyword_miss_by_platform[platform]
        if keyword_plan:
            keyword_alignment_score = max(0.0, 10.0 - keyword_misses * 3.0)
            effective_composite = round(
                score.composite * 0.8 + (keyword_alignment_score * 10.0) * 0.2,
                2,
            )
        else:
            effective_composite = score.composite
        weighted_total += weight * effective_composite
        weighted_misses += weight * soft_gates[platform].miss_count
        weighted_keyword_misses += weight * keyword_misses
        weight_sum += weight

    if weight_sum <= 0:
        weighted_total = sum(score.composite for score in per_platform.values())
        weight_sum = len(per_platform)
        weighted_misses = sum(gate.miss_count for gate in soft_gates.values()) / len(
            per_platform
        )
        weighted_keyword_misses = (
            sum(keyword_miss_by_platform.values()) / len(per_platform)
            if keyword_plan
            else 0.0
        )

    notes = tuple(
        dict.fromkeys([*google_score.notes, *bing_score.notes, *shopify_score.notes])
    )

    soft_gate_warnings: list[str] = []
    platform_labels = {"google": "Google", "bing": "Bing", "shopify": "Shopify"}
    for platform, assessment in soft_gates.items():
        for warning in assessment.warnings:
            soft_gate_warnings.append(f"{platform_labels[platform]}: {warning}")
    for platform, misses in keyword_miss_by_platform.items():
        if misses > 0:
            soft_gate_warnings.append(
                f"{platform_labels[platform]}: Keyword alignment misses ({misses})"
            )

    weighted_composite = round(weighted_total / weight_sum, 2)
    # Tiered penalty: first miss costs 1.5, subsequent misses cost 1.0 each
    if weighted_misses <= 0:
        soft_gate_penalty = 0.0
    elif weighted_misses <= 1:
        soft_gate_penalty = round(weighted_misses * 1.5, 2)
    else:
        soft_gate_penalty = round(1.5 + (weighted_misses - 1) * 1.0, 2)
    # Additional keyword-miss penalty to reduce score inflation.
    if weighted_keyword_misses > 0:
        soft_gate_penalty = round(soft_gate_penalty + weighted_keyword_misses * 0.75, 2)
    adjusted_weighted = max(0.0, round(weighted_composite - soft_gate_penalty, 2))

    return CandidateHeuristicScore(
        google=google_score,
        bing=bing_score,
        shopify=shopify_score,
        weighted_composite=weighted_composite,
        soft_gate_penalty=soft_gate_penalty,
        adjusted_weighted_composite=adjusted_weighted,
        soft_gate_warnings=tuple(dict.fromkeys(soft_gate_warnings)),
        soft_gate_miss_counts={k: v.miss_count for k, v in soft_gates.items()},
        notes=notes,
    )
