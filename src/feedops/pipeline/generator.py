"""Candidate generator using LLM providers."""
import json
from feedops.models import ParentSKU, Candidate, Claim, Score
from feedops.providers.base import LLMProvider
from feedops.pipeline.evidence import build_evidence_table, format_evidence_markdown
from feedops.pipeline.images import fetch_image
from feedops.pipeline.keyword_placement import (
    build_keyword_placement_plan,
    format_keyword_placement_section,
)
from feedops.pipeline.prompts import SYSTEM_PROMPT, OPTIMIZATION_TEMPLATE, CANDIDATE_SCHEMA


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

    return OPTIMIZATION_TEMPLATE.format(
        system_prompt=SYSTEM_PROMPT,
        evidence_table=evidence_markdown,
        keyword_placement=keyword_placement,
        schema=json.dumps(CANDIDATE_SCHEMA, indent=2),
        master_sku=parent_sku.master_sku,
    )


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

    return Candidate(
        google_title=response["google_title"],
        google_short_title=response["google_short_title"],
        google_description=response["google_description"],
        bing_title=response["bing_title"],
        bing_description=response["bing_description"],
        shopify_title=response["shopify_title"],
        shopify_description=response["shopify_description"],
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
