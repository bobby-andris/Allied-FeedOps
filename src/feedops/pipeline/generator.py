"""Candidate generator using LLM providers."""

import json

from feedops.models import Candidate, Claim, ParentSKU, Score
from feedops.pipeline.collection_descriptions import is_known_collection_name
from feedops.pipeline.evidence import build_evidence_table, format_evidence_markdown
from feedops.pipeline.images import fetch_image
from feedops.pipeline.keyword_placement import (
    build_keyword_placement_plan,
    format_keyword_placement_section,
)
from feedops.pipeline.prompts import (
    CANDIDATE_SCHEMA,
    OPTIMIZATION_TEMPLATE,
    SYSTEM_PROMPT,
)
from feedops.providers.base import LLMProvider


def _trim_google_short_title(title: str, max_len: int = 70) -> str:
    """Trim google_short_title to fit overlay constraints."""
    cleaned = title.strip()
    if len(cleaned) <= max_len:
        return cleaned

    brand_index = cleaned.lower().rfind("allied brass")
    if brand_index != -1:
        cleaned = cleaned[:brand_index].rstrip()
        cleaned = cleaned.rstrip(" |-—–")

    if len(cleaned) > max_len:
        for sep in [" | ", " - ", " — ", " – "]:
            if sep in cleaned:
                cleaned = cleaned.split(sep)[0].rstrip()
                break

    if len(cleaned) > max_len:
        truncated = cleaned[:max_len].rstrip()
        if " " in truncated:
            truncated = truncated.rsplit(" ", 1)[0]
        cleaned = truncated.rstrip()

    return cleaned or title.strip()[:max_len]


def _normalize_title_separators(title: str) -> str:
    """Normalize separators for readability and policy compliance.

    - Convert pipes to commas (avoid symbol-heavy separators).
    - Remove empty segments and dangling punctuation.
    - Ensure 'Allied Brass' appears once as the last segment when present.
    """
    raw = (title or "").strip()
    if not raw:
        return ""

    cleaned = raw.replace("|", ",")
    parts = []
    saw_brand = False
    for chunk in cleaned.split(","):
        part = chunk.strip().strip("-–—").strip()
        if not part:
            continue
        if part.lower().endswith(" collection"):
            name = part[: -len(" collection")].strip()
            if not is_known_collection_name(name):
                continue
            part = f"{name} Collection"
        if part.lower() == "allied brass":
            saw_brand = True
            continue
        parts.append(part)

    if saw_brand:
        parts.append("Allied Brass")

    return ", ".join(parts).strip(" ,")


def _trim_title_to_length(title: str, max_len: int) -> str:
    """Trim a comma-separated title to max_len without leaving trailing separators."""
    cleaned = _normalize_title_separators(title)
    if len(cleaned) <= max_len:
        return cleaned

    parts = [p.strip() for p in cleaned.split(",") if p.strip()]
    brand = None
    if parts and parts[-1].lower() == "allied brass":
        brand = parts.pop()

    # Drop least-critical trailing segments first.
    while parts and len(", ".join(parts + ([brand] if brand else []))) > max_len:
        if len(parts) <= 1:
            break
        parts.pop()

    rebuilt = ", ".join(parts + ([brand] if brand else []))
    if len(rebuilt) <= max_len:
        return rebuilt.strip(" ,")

    # Final fallback: hard truncate while preserving whole words and brand if present.
    suffix = f", {brand}" if brand else ""
    budget = max_len - len(suffix)
    head = ", ".join(parts)
    head = head[: max(budget, 0)].rstrip()
    if " " in head:
        head = head.rsplit(" ", 1)[0].rstrip()
    if suffix and head.endswith(","):
        head = head.rstrip(", ").rstrip()
    final = f"{head}{suffix}" if head else (brand or "")
    return final.strip()[:max_len].strip(" ,")


def build_prompt(parent_sku: ParentSKU) -> str:
    """Build the full optimization prompt for a ParentSKU.

    Args:
        parent_sku: The parent SKU to optimize.

    Returns:
        Complete prompt string for LLM.
    """
    evidence = build_evidence_table(parent_sku)
    evidence_markdown = format_evidence_markdown(evidence)
    keyword_plan = build_keyword_placement_plan(parent_sku, evidence)
    keyword_placement = format_keyword_placement_section(keyword_plan)

    prompt = OPTIMIZATION_TEMPLATE.format(
        system_prompt=SYSTEM_PROMPT,
        evidence_table=evidence_markdown,
        keyword_placement=keyword_placement,
        schema=json.dumps(CANDIDATE_SCHEMA, indent=2),
        master_sku=parent_sku.master_sku,
    )
    return prompt


def parse_candidate_response(response: dict) -> Candidate:
    """Parse LLM response into Candidate model.

    Args:
        response: Parsed JSON response from LLM.

    Returns:
        Candidate model instance.
    """
    claims = [
        Claim(
            claim=c["claim"],
            source_field=c["source_field"],
            source_value=c["source_value"],
        )
        for c in response.get("claims", [])
    ]

    score_data = response.get("self_score", {})
    self_score = Score(
        specificity=score_data.get("specificity", 5),
        benefit_coverage=score_data.get("benefit_coverage", 5),
        keyword_inclusion=score_data.get("keyword_inclusion", 5),
        format_adherence=score_data.get("format_adherence", 5),
        brand_voice=score_data.get("brand_voice", 5),
        factual_accuracy=score_data.get("factual_accuracy", 5),
    )

    google_title = _trim_title_to_length(response["google_title"], 150)
    bing_title = _trim_title_to_length(response["bing_title"], 150)
    shopify_title = _trim_title_to_length(response["shopify_title"], 255)
    google_short_title = _trim_google_short_title(response["google_short_title"])

    # Get shopify_meta_description, generate fallback from description if not provided
    shopify_meta_description = response.get("shopify_meta_description", "")
    if not shopify_meta_description:
        # Fallback: extract first 155 chars from shopify_description (strip HTML)
        import re

        desc = response.get("shopify_description", "")
        text = re.sub(r"<[^>]+>", " ", desc)
        text = re.sub(r"\s+", " ", text).strip()
        shopify_meta_description = text[:155] if text else ""

    return Candidate(
        google_title=google_title,
        google_short_title=google_short_title,
        google_description=response["google_description"],
        bing_title=bing_title,
        bing_description=response["bing_description"],
        shopify_title=shopify_title,
        shopify_description=response["shopify_description"],
        shopify_meta_description=shopify_meta_description,
        claims=claims,
        self_score=self_score,
    )


async def generate_candidate(
    parent_sku: ParentSKU,
    llm: LLMProvider,
) -> Candidate:
    """Generate optimized title/description candidate.

    Args:
        parent_sku: The parent SKU to optimize.
        llm: The LLM provider to use.

    Returns:
        Generated Candidate (unverified).
    """
    candidates, errors = await generate_candidates(parent_sku, llm, 1)
    if not candidates:
        detail = errors[0] if errors else "No candidates generated"
        raise ValueError(detail)
    return candidates[0]


async def generate_candidates(
    parent_sku: ParentSKU,
    llm: LLMProvider,
    n: int,
) -> tuple[list[Candidate], list[str]]:
    """Generate multiple optimized candidates for a ParentSKU."""
    count = max(1, n)
    prompt = build_prompt(parent_sku)
    image = None
    if parent_sku.variants:
        main_image_url = parent_sku.variants[0].main_image_url
        if main_image_url:
            image = await fetch_image(main_image_url)

    candidates: list[Candidate] = []
    errors: list[str] = []
    for idx in range(count):
        try:
            response = await llm.generate(prompt, CANDIDATE_SCHEMA, image=image)
            candidate = parse_candidate_response(response)
            candidates.append(
                candidate.model_copy(
                    update={"candidate_index": idx, "num_candidates": count}
                )
            )
        except Exception as exc:
            errors.append(f"Candidate {idx}: {exc}")

    return candidates, errors
    return candidates, errors
