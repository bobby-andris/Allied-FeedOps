"""Candidate generator using LLM providers."""

import asyncio
import json
import logging
import os

from feedops.api.prompt_loader import (
    format_gold_standard_examples_bundle,
    get_system_prompt,
)
from feedops.models import Candidate, Claim, ParentSKU, Score
from feedops.pipeline.collection_descriptions import is_known_collection_name
from feedops.pipeline.evidence import build_evidence_table, format_evidence_markdown
from feedops.pipeline.finish_injection import get_finish_metadata
from feedops.pipeline.images import fetch_image
from feedops.pipeline.keyword_placement import (
    KeywordPlacementPlan,
    build_keyword_placement_plan,
    format_keyword_placement_section,
    validate_candidate_keyword_placement,
)
from feedops.pipeline.prompts import (
    CANDIDATE_SCHEMA,
    FINISH_CONTEXT_TEMPLATE,
    OPTIMIZATION_TEMPLATE,
    USER_PROMPT_TEMPLATE,
    VARIANT_USER_PROMPT_TEMPLATE,
    build_category_guidance,
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
    """Build the full optimization prompt for a ParentSKU (legacy single-string).

    This is the legacy single-string prompt used for reporting and backward
    compatibility. For LLM calls, prefer build_split_prompt() which separates
    static system content (cacheable) from dynamic user content.

    Args:
        parent_sku: The parent SKU to optimize.

    Returns:
        Complete prompt string for LLM.
    """
    evidence = build_evidence_table(parent_sku)
    evidence_markdown = format_evidence_markdown(evidence)
    keyword_plan = build_keyword_placement_plan(parent_sku, evidence)
    keyword_placement = format_keyword_placement_section(keyword_plan)
    gold_examples = format_gold_standard_examples_bundle(max_examples=2)
    gold_examples_section = (
        f"\n## Gold Standard Examples\n{gold_examples}\n" if gold_examples else ""
    )

    prompt = OPTIMIZATION_TEMPLATE.format(
        system_prompt=get_system_prompt(),
        evidence_table=evidence_markdown,
        keyword_placement=keyword_placement,
        category_guidance=build_category_guidance(parent_sku.category),
        gold_examples=gold_examples_section,
        schema=json.dumps(CANDIDATE_SCHEMA, indent=2),
        master_sku=parent_sku.master_sku,
    )
    return prompt


def build_split_prompt(parent_sku: ParentSKU) -> tuple[str, str]:
    """Build cache-optimized split prompt for a ParentSKU.

    Returns a (system_prompt, user_prompt) tuple. The system_prompt is
    identical across all SKUs and variants, enabling OpenAI prompt caching.
    The user_prompt contains only per-SKU evidence, keywords, and schema.

    Args:
        parent_sku: The parent SKU to optimize.

    Returns:
        Tuple of (system_prompt, user_prompt).
    """
    evidence = build_evidence_table(parent_sku)
    evidence_markdown = format_evidence_markdown(evidence)
    keyword_plan = build_keyword_placement_plan(parent_sku, evidence)
    keyword_placement = format_keyword_placement_section(keyword_plan)
    gold_examples = format_gold_standard_examples_bundle(max_examples=2)
    gold_examples_section = (
        f"\n## Gold Standard Examples\n{gold_examples}\n" if gold_examples else ""
    )

    user_prompt = USER_PROMPT_TEMPLATE.format(
        evidence_table=evidence_markdown,
        keyword_placement=keyword_placement,
        category_guidance=build_category_guidance(parent_sku.category),
        gold_examples=gold_examples_section,
        schema=json.dumps(CANDIDATE_SCHEMA, indent=2),
        master_sku=parent_sku.master_sku,
    )
    return get_system_prompt(), user_prompt


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


_MIN_TITLE_LENGTH = 60


def _needs_title_retry(candidate: Candidate) -> list[str]:
    """Check if a candidate has titles that are too short.

    Returns list of field names that failed the minimum length check.
    """
    short_fields = []
    for field in ("google_title", "bing_title"):
        value = getattr(candidate, field, "")
        if len(value) < _MIN_TITLE_LENGTH:
            short_fields.append(field)
    return short_fields


def _needs_keyword_alignment_retry(
    candidate: Candidate,
    keyword_plan: KeywordPlacementPlan,
) -> list[str]:
    """Return keyword placement violations that should trigger a retry."""
    if not keyword_plan.enforce_alignment:
        return []
    return validate_candidate_keyword_placement(candidate, keyword_plan)


async def generate_candidates(
    parent_sku: ParentSKU,
    llm: LLMProvider,
    n: int,
    reasoning_effort: str | None = None,
) -> tuple[list[Candidate], list[str]]:
    """Generate multiple optimized candidates for a ParentSKU.

    If any candidate has a google_title or bing_title shorter than 60
    characters, it is regenerated once. This guards against edge cases
    where the model produces truncated titles for products with short names.

    Args:
        parent_sku: The parent SKU to optimize.
        llm: The LLM provider to use.
        n: Number of candidates to generate.
        reasoning_effort: Optional reasoning effort level ("low", "medium", "high").

    Returns:
        Tuple of (candidates, errors).
    """
    count = max(1, n)
    system_prompt, user_prompt = build_split_prompt(parent_sku)
    keyword_plan = build_keyword_placement_plan(
        parent_sku, build_evidence_table(parent_sku)
    )
    image = None
    if parent_sku.variants:
        main_image_url = parent_sku.variants[0].main_image_url
        if main_image_url:
            image = await fetch_image(main_image_url)

    async def _generate_one(idx: int) -> Candidate:
        response = await llm.generate(
            user_prompt,
            CANDIDATE_SCHEMA,
            image=image,
            system_prompt=system_prompt,
            reasoning_effort=reasoning_effort,
        )
        candidate = parse_candidate_response(response)
        return candidate.model_copy(
            update={"candidate_index": idx, "num_candidates": count}
        )

    if count == 1:
        # Fast path: no concurrency overhead for single candidate
        candidates: list[Candidate] = []
        errors: list[str] = []
        try:
            candidates.append(await _generate_one(0))
        except Exception as exc:
            errors.append(f"Candidate 0: {exc}")
        # Retry once if title is too short or keyword alignment misses.
        if candidates:
            short_fields = _needs_title_retry(candidates[0])
            keyword_errors = _needs_keyword_alignment_retry(candidates[0], keyword_plan)
            if short_fields or keyword_errors:
                errors.append(
                    f"Candidate 0 retry (title/keyword alignment): "
                    f"short_titles={short_fields or 'none'}, "
                    f"keyword_errors={len(keyword_errors)}"
                )
                try:
                    retry = await _generate_one(0)
                    retry_short = _needs_title_retry(retry)
                    retry_keyword_errors = _needs_keyword_alignment_retry(
                        retry, keyword_plan
                    )
                    original_penalty = len(short_fields) * 2 + len(keyword_errors)
                    retry_penalty = len(retry_short) * 2 + len(retry_keyword_errors)
                    if retry_penalty < original_penalty:
                        candidates[0] = retry
                    elif retry_penalty == original_penalty and not retry_short:
                        candidates[0] = retry
                    elif retry_penalty == original_penalty and len(retry.google_title) > len(
                        candidates[0].google_title
                    ):
                        candidates[0] = retry
                except Exception as exc:
                    errors.append(f"Candidate 0 retry failed: {exc}")
        return candidates, errors

    # Parallel generation for multiple candidates
    tasks = [_generate_one(idx) for idx in range(count)]
    results = await asyncio.gather(*tasks, return_exceptions=True)

    candidates = []
    errors = []
    retry_indices = []
    for idx, result in enumerate(results):
        if isinstance(result, Exception):
            errors.append(f"Candidate {idx}: {result}")
        else:
            candidates.append(result)
            short_fields = _needs_title_retry(result)
            keyword_errors = _needs_keyword_alignment_retry(result, keyword_plan)
            if short_fields or keyword_errors:
                errors.append(
                    f"Candidate {idx} retry (title/keyword alignment): "
                    f"short_titles={short_fields or 'none'}, "
                    f"keyword_errors={len(keyword_errors)}"
                )
                retry_indices.append(len(candidates) - 1)

    # Retry candidates with short titles (parallel)
    if retry_indices:
        retry_tasks = [_generate_one(candidates[i].candidate_index or i) for i in retry_indices]
        retry_results = await asyncio.gather(*retry_tasks, return_exceptions=True)
        for pos, retry_result in zip(retry_indices, retry_results):
            if isinstance(retry_result, Exception):
                errors.append(f"Retry failed for candidate at position {pos}: {retry_result}")
                continue
            original = candidates[pos]
            retry_short = _needs_title_retry(retry_result)
            retry_keyword_errors = _needs_keyword_alignment_retry(retry_result, keyword_plan)
            original_short = _needs_title_retry(original)
            original_keyword_errors = _needs_keyword_alignment_retry(original, keyword_plan)
            original_penalty = len(original_short) * 2 + len(original_keyword_errors)
            retry_penalty = len(retry_short) * 2 + len(retry_keyword_errors)
            if retry_penalty < original_penalty:
                candidates[pos] = retry_result
            elif retry_penalty == original_penalty and not retry_short:
                candidates[pos] = retry_result
            elif retry_penalty == original_penalty and len(retry_result.google_title) > len(
                original.google_title
            ):
                candidates[pos] = retry_result

    return candidates, errors


# ---------------------------------------------------------------------------
# VARIANT-SPECIFIC GENERATION (finish-integrated content)
# ---------------------------------------------------------------------------
# These functions generate content for specific finish variants directly from
# the LLM, rather than post-processing master SKU content. This produces more
# natural finish integration in descriptions.
# ---------------------------------------------------------------------------


def _variant_generation_enabled() -> bool:
    """Check if variant-at-LLM-time generation is enabled."""
    value = os.getenv("FEEDOPS_VARIANT_AT_LLM_TIME")
    if value is None:
        return False
    return value.strip().lower() in {"1", "true", "yes"}


def build_variant_prompt(
    parent_sku: ParentSKU,
    finish_name: str,
    platform: str = "google",
) -> tuple[str, str]:
    """Build prompt with finish context for variant generation.

    Args:
        parent_sku: The parent SKU to optimize.
        finish_name: The specific finish for this variant (e.g., "Antique Brass").
        platform: Target platform (google, bing, shopify).

    Returns:
        Tuple of (system_prompt, user_prompt) with finish context injected.
    """
    evidence = build_evidence_table(parent_sku)
    evidence_markdown = format_evidence_markdown(evidence)
    keyword_plan = build_keyword_placement_plan(parent_sku, evidence)
    keyword_placement = format_keyword_placement_section(keyword_plan)
    gold_examples = format_gold_standard_examples_bundle(max_examples=2)
    gold_examples_section = (
        f"\n## Gold Standard Examples\n{gold_examples}\n" if gold_examples else ""
    )

    # Get finish metadata for context
    finish_meta = get_finish_metadata(finish_name) or {}
    finish_category = finish_meta.get("category", "metallic")
    finish_character = finish_meta.get("functional_description", "")
    style_affinities = finish_meta.get("style_affinities", [])
    style_context = ", ".join(style_affinities) if style_affinities else "versatile"

    # Platform-specific emphasis
    platform_emphasis = {
        "google": "material coordination and searchable attributes",
        "bing": "explicit finish synonyms and literal keyword matching",
        "shopify": "design aesthetic and buyer appeal",
    }.get(platform, "natural integration")

    # Build finish context
    finish_context = FINISH_CONTEXT_TEMPLATE.format(
        finish_name=finish_name,
        finish_category=finish_category,
        finish_character=finish_character,
        style_context=style_context,
        platform_emphasis=platform_emphasis,
    )

    # Build variant SKU identifier
    variant_sku = f"{parent_sku.master_sku}-{finish_name.upper().replace(' ', '-')[:3]}"

    # Build user prompt with finish context
    user_prompt = VARIANT_USER_PROMPT_TEMPLATE.format(
        evidence_table=evidence_markdown,
        keyword_placement=keyword_placement,
        category_guidance=build_category_guidance(parent_sku.category),
        finish_context=finish_context,
        gold_examples=gold_examples_section,
        schema=json.dumps(CANDIDATE_SCHEMA, indent=2),
        variant_sku=variant_sku,
        finish_name=finish_name,
    )

    return get_system_prompt(), user_prompt


async def generate_variant_candidate(
    parent_sku: ParentSKU,
    finish_name: str,
    llm: LLMProvider,
    platform: str = "google",
) -> Candidate:
    """Generate a finish-specific candidate directly from LLM.

    This produces content where the finish is naturally integrated into the
    description, rather than being awkwardly injected via post-processing.

    Args:
        parent_sku: The parent SKU to optimize.
        finish_name: The specific finish for this variant (e.g., "Antique Brass").
        llm: The LLM provider to use.
        platform: Target platform (google, bing, shopify).

    Returns:
        Candidate with finish-integrated content.
    """
    system_prompt, user_prompt = build_variant_prompt(parent_sku, finish_name, platform)

    # Fetch image if available
    image = None
    if parent_sku.variants:
        main_image_url = parent_sku.variants[0].main_image_url
        if main_image_url:
            image = await fetch_image(main_image_url)

    response = await llm.generate(
        user_prompt,
        CANDIDATE_SCHEMA,
        image=image,
        system_prompt=system_prompt,
    )

    candidate = parse_candidate_response(response)

    # Validate that finish appears in the description
    desc_lower = candidate.google_description.lower()
    if finish_name.lower() not in desc_lower:
        # Log warning but don't fail - the content may still be good
        logging.warning(
            f"Finish '{finish_name}' not found in generated description for {parent_sku.master_sku}"
        )

    return candidate


async def generate_variant_candidates_batch(
    parent_sku: ParentSKU,
    finish_names: list[str],
    llm: LLMProvider,
    platform: str = "google",
    max_concurrent: int = 5,
) -> tuple[dict[str, Candidate], list[str]]:
    """Generate candidates for multiple finish variants in parallel.

    Args:
        parent_sku: The parent SKU to optimize.
        finish_names: List of finish names to generate variants for.
        llm: The LLM provider to use.
        platform: Target platform.
        max_concurrent: Maximum concurrent LLM calls.

    Returns:
        Tuple of (finish_name -> Candidate dict, list of errors).
    """
    semaphore = asyncio.Semaphore(max_concurrent)

    async def _generate_one(finish: str) -> tuple[str, Candidate | Exception]:
        async with semaphore:
            try:
                candidate = await generate_variant_candidate(
                    parent_sku, finish, llm, platform
                )
                return (finish, candidate)
            except Exception as e:
                return (finish, e)

    results = await asyncio.gather(*[_generate_one(f) for f in finish_names])

    candidates: dict[str, Candidate] = {}
    errors: list[str] = []

    for finish, result in results:
        if isinstance(result, Exception):
            errors.append(f"{finish}: {result}")
        else:
            candidates[finish] = result

    return candidates, errors
