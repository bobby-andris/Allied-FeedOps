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
    "toilet tissue",
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
    "make-up mirror",
    "makeup mirror",
    "shower door",
    "shower curtain",
    "paper towel",
    "wall hook",
    "retractable",
    "garment rod",
    "squeegee",
    "vanity tray",
    "tissue holder",
    "basket",
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
class HeuristicScore:
    ctr_proxy: int
    cvr_proxy: int
    brand_voice: int
    notes: tuple[str, ...] = ()

    @property
    def composite(self) -> float:
        return round((self.ctr_proxy + self.cvr_proxy + self.brand_voice) / 30 * 100, 2)


@dataclass(frozen=True)
class SoftGateAssessment:
    miss_count: int
    warnings: tuple[str, ...]
    passes: dict[str, bool]


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
    if any(w in opening for w in _OPENING_ENGAGEMENT_CUES):
        score += 2
    else:
        notes.append("Opening may lack engagement hook (no problem/outcome cue detected)")

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


def assess_soft_gates(
    *,
    title: str,
    description: str,
    html_description: bool = False,
) -> SoftGateAssessment:
    """Evaluate structure signals without hard-failing."""
    warnings: list[str] = []

    has_dimension = bool(_INCH_RE.search(title[:70]))
    if not has_dimension:
        warnings.append("Title missing primary dimension in first 70 chars")

    text = description
    if html_description:
        text = re.sub(r"<[^>]+>", " ", description)
        text = re.sub(r"\s+", " ", text).strip()

    opening = text[:160].lower()
    has_benefit_verb = any(w in opening for w in _OPENING_ENGAGEMENT_CUES)
    if not has_benefit_verb:
        warnings.append("Opening lacks engagement hook")

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
    soft_gate_penalty: float
    adjusted_weighted_composite: float
    soft_gate_warnings: tuple[str, ...] = ()
    soft_gate_miss_counts: dict[str, int] | None = None
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

    soft_gates = {
        "google": assess_soft_gates(
            title=candidate.google_title,
            description=candidate.google_description,
        ),
        "bing": assess_soft_gates(
            title=candidate.bing_title,
            description=candidate.bing_description,
        ),
        "shopify": assess_soft_gates(
            title=candidate.shopify_title,
            description=candidate.shopify_description,
            html_description=True,
        ),
    }

    weighted_total = 0.0
    weight_sum = 0.0
    weighted_misses = 0.0
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
        weighted_misses += weight * soft_gates[platform].miss_count
        weight_sum += weight

    if weight_sum <= 0:
        weighted_total = sum(score.composite for score in per_platform.values())
        weight_sum = len(per_platform)
        weighted_misses = sum(gate.miss_count for gate in soft_gates.values()) / len(per_platform)

    notes = tuple(
        dict.fromkeys(
            [*google_score.notes, *bing_score.notes, *shopify_score.notes]
        )
    )

    soft_gate_warnings: list[str] = []
    platform_labels = {"google": "Google", "bing": "Bing", "shopify": "Shopify"}
    for platform, assessment in soft_gates.items():
        for warning in assessment.warnings:
            soft_gate_warnings.append(f"{platform_labels[platform]}: {warning}")

    weighted_composite = round(weighted_total / weight_sum, 2)
    soft_gate_penalty = round(weighted_misses * 2.0, 2)
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
