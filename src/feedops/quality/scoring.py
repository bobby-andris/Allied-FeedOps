"""Heuristic (offline) content scoring for CTR/CVR/brand voice proxies.

This is not a substitute for real performance data. It is intended to help
compare prompt variants and catch obvious regressions without calling an LLM.
"""

from __future__ import annotations

import re
from dataclasses import dataclass

from feedops.models import Candidate
_URL_RE = re.compile(r"https?://", re.IGNORECASE)
_CITATION_RE = re.compile(r"catalog_csv\.|\(\s*catalog_csv\.[^)]+\)", re.IGNORECASE)
_ALL_CAPS_WORD_RE = re.compile(r"\b[A-Z]{4,}\b")

# Examples: "18-inch", "18 in", "1-1/2 in", '18"', "0.5 in"
_INCH_RE = re.compile(
    r"(\d+\s*-\s*\d+/\d+|\d+/\d+|\d+(?:\.\d+)?)\s*(?:-\s*)?(?:in\b|inch(?:es)?\b|\")",
    re.IGNORECASE,
)

_PRODUCT_TYPE_PHRASES = [
    "towel bar",
    "cabinet knob",
    "grab bar",
    "toilet paper holder",
    "towel ring",
    "robe hook",
    "guest towel",
    "soap dish",
    "glass shelf",
    "wood shelf",
    "wall mirror",
    "make-up mirror",
    "makeup mirror",
    "shower door",
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
    "concealed",
    "ada",
    "pivot",
    "tilt",
    "tilting",
    "retractable",
    "quick",
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

_BANNED_MARKETING = [
    "best",
    "amazing",
    "incredible",
    "perfect",
    "cheap",
    "bargain",
    "free shipping",
    "sale",
]


@dataclass(frozen=True)
class HeuristicScore:
    ctr_proxy: int
    cvr_proxy: int
    brand_voice: int
    notes: tuple[str, ...] = ()

    @property
    def composite(self) -> float:
        return round((self.ctr_proxy + self.cvr_proxy + self.brand_voice) / 30 * 100, 2)


def _clamp_0_10(value: int) -> int:
    return max(0, min(10, value))


def _contains_any(text: str, phrases: list[str]) -> bool:
    t = text.lower()
    return any(p in t for p in phrases)


def score_title(title: str, *, require_brand: bool = True) -> tuple[int, list[str]]:
    """CTR proxy score for a title (0-10)."""
    notes: list[str] = []
    score = 0

    if _CITATION_RE.search(title):
        notes.append("Citation leakage detected in title")
        return 0, notes
    if _URL_RE.search(title):
        notes.append("URL detected in title")
        return 0, notes

    length = len(title)
    if length > 150:
        notes.append("Title exceeds 150 characters")
    if 50 <= length <= 150:
        score += 1
    if 70 <= length <= 150:
        score += 1

    # Product type + dimension are strong CTR anchors
    if _contains_any(title, _PRODUCT_TYPE_PHRASES):
        score += 2
    else:
        notes.append("No recognized product-type phrase detected")

    if _INCH_RE.search(title[:70]):
        score += 2
    else:
        notes.append("No primary dimension detected in first 70 chars")

    if _contains_any(title, _MATERIAL_WORDS):
        score += 1
    else:
        notes.append("No material keyword detected")

    if _contains_any(title, _FUNCTIONAL_MODIFIERS):
        score += 1

    if require_brand:
        if "allied brass" in title.lower():
            score += 1
        else:
            notes.append("Brand missing: Allied Brass")

    if _ALL_CAPS_WORD_RE.search(title):
        notes.append("ALL CAPS word detected")
        score -= 1

    if any(bad in title.lower() for bad in _BANNED_MARKETING):
        notes.append("Promotional/budget language detected")
        score -= 2

    return _clamp_0_10(score), notes


def score_description(description: str, *, html: bool = False) -> tuple[int, list[str]]:
    """CVR proxy score for a description (0-10)."""
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

    if len(text) >= 500:
        score += 2
    elif len(text) >= 300:
        score += 1
        notes.append("Description under 500 characters")
    else:
        notes.append("Description under 300 characters")

    opening = text[:160].lower()
    if any(w in opening for w in ["upgrade", "add", "refresh", "protect", "keep", "organize", "maximize"]):
        score += 2
    else:
        notes.append("Opening may be feature-first (no clear benefit verb detected)")

    # Specs presence: at least 3 numeric/measurement tokens.
    measurements = len(_INCH_RE.findall(text)) + len(re.findall(r"\b\d+(?:\.\d+)?\s*(?:lb|lbs|pound|pounds)\b", text, re.I))
    if measurements >= 3:
        score += 2
    else:
        notes.append("Few measurable specs detected")

    if not html:
        # Plain-text structure cues: reward Highlights + Specs sections.
        lower = description.lower()
        bullet_lines = [
            line.strip()
            for line in description.splitlines()
            if line.strip().startswith(("-", "•"))
        ]
        if len(bullet_lines) >= 3:
            score += 1
        else:
            notes.append("Missing structured highlights bullets")

        if re.search(r"\b(specs?|specifications)\b", lower) and measurements >= 3:
            score += 1
        else:
            notes.append("Missing specs section")

    # Mentions warranty/installation details helps confidence.
    if "warranty" in text.lower():
        score += 1
    if "installation" in text.lower() or "mounting" in text.lower():
        score += 1

    if "!" in description:
        notes.append("Exclamation point detected")
        score -= 1
    if any(bad in text.lower() for bad in _BANNED_MARKETING):
        notes.append("Promotional/budget language detected")
        score -= 2

    return _clamp_0_10(score), notes


def score_brand_voice(text: str) -> tuple[int, list[str]]:
    """Brand voice proxy score (0-10)."""
    notes: list[str] = []
    score = 5  # neutral baseline

    t = text.lower()
    cue_hits = sum(1 for cue in _PREMIUM_CUES if cue in t)
    score += min(5, cue_hits)  # up to +5

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


def score_bundle(*, title: str, description: str, html_description: bool = False) -> HeuristicScore:
    """Convenience scorer combining title+description into a composite."""
    ctr, ctr_notes = score_title(title)
    cvr, cvr_notes = score_description(description, html=html_description)
    voice, voice_notes = score_brand_voice(title + "\n" + description)
    notes = tuple(dict.fromkeys([*ctr_notes, *cvr_notes, *voice_notes]))
    return HeuristicScore(ctr_proxy=ctr, cvr_proxy=cvr, brand_voice=voice, notes=notes)


@dataclass(frozen=True)
class CandidateHeuristicScore:
    google: HeuristicScore
    bing: HeuristicScore
    shopify: HeuristicScore
    weighted_composite: float
    notes: tuple[str, ...] = ()


def score_candidate(candidate: Candidate, *, weights: dict[str, float]) -> CandidateHeuristicScore:
    """Score a candidate across platforms using weighted composites."""
    google_score = score_bundle(
        title=candidate.google_title,
        description=candidate.google_description,
    )
    bing_score = score_bundle(
        title=candidate.bing_title,
        description=candidate.bing_description,
    )
    shopify_score = score_bundle(
        title=candidate.shopify_title,
        description=candidate.shopify_description,
        html_description=True,
    )

    weighted_total = 0.0
    weight_sum = 0.0
    per_platform = {
        "google": google_score,
        "bing": bing_score,
        "shopify": shopify_score,
    }
    for platform, score in per_platform.items():
        weight = weights.get(platform, 0.0)
        if weight <= 0:
            continue
        weighted_total += weight * score.composite
        weight_sum += weight

    if weight_sum <= 0:
        weighted_total = sum(score.composite for score in per_platform.values())
        weight_sum = len(per_platform)

    notes = tuple(
        dict.fromkeys(
            [*google_score.notes, *bing_score.notes, *shopify_score.notes]
        )
    )

    return CandidateHeuristicScore(
        google=google_score,
        bing=bing_score,
        shopify=shopify_score,
        weighted_composite=round(weighted_total / weight_sum, 2),
        notes=notes,
    )
