"""Candidate generator using LLM providers."""

import asyncio
import json
import logging
import os
import re

from feedops.api.prompt_loader import (
    format_gold_standard_examples_bundle,
    get_category_guidance,
    get_finish_list,
    get_system_prompt,
)
from feedops.api.prompt_builder import (
    build_bing_prompt,
    build_google_prompt,
    build_shopify_prompt,
    get_prompt_experiment_variant,
)
from feedops.generation.executor import (
    ExecutionBudgetExceededError,
    execute_generation_legacy_payload,
)
from feedops.models import Candidate, Claim, ParentSKU, Score
from feedops.pipeline.evidence import (
    build_evidence_table,
    format_evidence_markdown,
)
from feedops.pipeline.finish_sentence_placeholder import build_fallback_finish_sentences
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
    VARIANT_USER_PROMPT_TEMPLATE,
)
from feedops.pipeline.segment_strategy import (
    SegmentStrategy,
    format_segment_strategy_guidance,
    resolve_segment_strategy,
)
from feedops.pipeline.feature_flags import is_segment_strategy_v1_enabled
from feedops.pipeline.title_normalization import trim_title_to_length
from feedops.providers.base import LLMProvider

logger = logging.getLogger(__name__)
_TOKEN_RE = re.compile(r"[a-z0-9]+")


class GenerationBudgetExceededError(RuntimeError):
    """Raised when estimated request cost exceeds configured per-request budget."""

    def __init__(
        self,
        *,
        cap_usd: float,
        estimated_cost_usd: float,
        platform: str,
    ) -> None:
        self.cap_usd = float(cap_usd)
        self.estimated_cost_usd = float(estimated_cost_usd)
        self.platform = platform
        super().__init__(
            "generation_request_budget_exceeded:"
            f" platform={platform} estimated_cost_usd={estimated_cost_usd:.6f}"
            f" cap_usd={cap_usd:.6f}"
        )


def _platform_reasoning_effort(platform: str, default_reasoning_effort: str) -> str:
    """Resolve per-platform reasoning effort."""
    if platform == "finish":
        return "low"
    return default_reasoning_effort


def _platform_completion_cap(platform: str, base_cap: int) -> int:
    """Apply per-platform completion caps for v2 generation.

    We intentionally *bound* completion budgets to reduce long-tail latency and
    runaway spend during strict JSON generation. Callers can pass a lower cap,
    but platform-specific hard limits prevent overly large completions.

    Defaults are tuned to avoid GPT-5.x strict-JSON truncation for description
    generation while remaining bounded by request-level cost and retry limits.
    Limits are configurable by env when tighter controls are needed.
    """
    normalized_cap = max(1, int(base_cap))
    default_cap = max(1, int(os.getenv("FEEDOPS_PLATFORM_COMPLETION_CAP_DEFAULT", "8000")))
    finish_cap = max(
        1,
        int(
            os.getenv(
                "FEEDOPS_PLATFORM_COMPLETION_CAP_FINISH",
                os.getenv("FEEDOPS_PLATFORM_COMPLETION_CAP_DEFAULT", "2000"),
            )
        ),
    )
    platform_limits = {
        "google": max(
            1, int(os.getenv("FEEDOPS_PLATFORM_COMPLETION_CAP_GOOGLE", str(default_cap)))
        ),
        "bing": max(
            1, int(os.getenv("FEEDOPS_PLATFORM_COMPLETION_CAP_BING", str(default_cap)))
        ),
        "shopify": max(
            1, int(os.getenv("FEEDOPS_PLATFORM_COMPLETION_CAP_SHOPIFY", str(default_cap)))
        ),
        "finish": finish_cap,
    }
    limit = platform_limits.get(platform)
    if limit is None:
        return normalized_cap
    return min(normalized_cap, limit)


def _resolve_requested_platforms(
    selected_platforms: tuple[str, ...] | list[str] | None,
) -> tuple[str, ...]:
    """Resolve requested platforms while preserving canonical execution order."""
    ordered = ("google", "bing", "shopify", "finish")
    if not selected_platforms:
        return ordered
    normalized = {
        str(platform).strip().lower()
        for platform in selected_platforms
        if str(platform).strip()
    }
    resolved = tuple(platform for platform in ordered if platform in normalized)
    return resolved or ordered


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


def _normalize_segment_token(value: str) -> str:
    return " ".join(_TOKEN_RE.findall((value or "").lower()))


def _extract_custom_label_0_values(parent_sku: ParentSKU) -> list[str]:
    """Extract unique custom_label_0 values from merchant_center_items."""
    values: list[str] = []
    seen: set[str] = set()
    for item in parent_sku.merchant_center_items or []:
        raw = item.get("customLabel0") or item.get("custom_label_0")
        if not raw and isinstance(item.get("attributes"), dict):
            attrs = item["attributes"]
            raw = attrs.get("customLabel0") or attrs.get("custom_label_0")
        if not raw and isinstance(item.get("custom_labels"), dict):
            labels = item["custom_labels"]
            raw = labels.get("customLabel0") or labels.get("custom_label_0")
        value = str(raw or "").strip()
        if not value:
            continue
        key = _normalize_segment_token(value)
        if not key or key in seen:
            continue
        seen.add(key)
        values.append(value)
    return values


def _resolve_segment_strategy(parent_sku: ParentSKU) -> SegmentStrategy:
    return resolve_segment_strategy(
        _extract_custom_label_0_values(parent_sku),
        enabled=is_segment_strategy_v1_enabled(),
    )


def _build_generator_prompt_payload(parent_sku: ParentSKU) -> dict[str, object]:
    """Assemble shared prompt inputs for legacy generator compatibility.

    The optimize-path generator still expects a single composite prompt, but the
    underlying Google/Bing/Shopify sections should now come from the
    platform-specific prompt builders in prompt_builder.py.
    """
    evidence = build_evidence_table(parent_sku)
    keyword_plan = build_keyword_placement_plan(parent_sku, evidence)
    category_guidance = get_category_guidance(parent_sku.category)
    gold_examples = format_gold_standard_examples_bundle(max_examples=2)
    return {
        "evidence": evidence,
        "evidence_markdown": format_evidence_markdown(evidence),
        "keyword_plan": keyword_plan,
        "category_guidance": category_guidance,
        "gold_examples": gold_examples,
    }


def build_prompt(parent_sku: ParentSKU) -> str:
    """Build the full optimization prompt for a ParentSKU (legacy single-string)."""
    system_prompt, user_prompt = build_split_prompt(parent_sku)
    return f"{system_prompt}\n\n{user_prompt}"


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
    prompt_payload = _build_generator_prompt_payload(parent_sku)
    evidence = prompt_payload["evidence"]
    evidence_markdown = prompt_payload["evidence_markdown"]
    keyword_plan = prompt_payload["keyword_plan"]
    segment_strategy = _resolve_segment_strategy(parent_sku)
    gold_examples = str(prompt_payload["gold_examples"] or "").strip()

    shared_sections = [
        f"MasterSKU: {parent_sku.master_sku}",
        f"Available Product Data:\n{evidence_markdown}",
    ]
    keyword_section = format_keyword_placement_section(keyword_plan)
    if keyword_section:
        shared_sections.append(f"Keyword Placement Plan:\n{keyword_section}")
    segment_guidance = format_segment_strategy_guidance(segment_strategy)
    if segment_guidance:
        shared_sections.append(segment_guidance)
    if gold_examples:
        shared_sections.append(f"## Gold Standard Examples\n{gold_examples}")

    google_prompt = build_google_prompt(
        sku_data=parent_sku,
        evidence=evidence,
        keywords=keyword_plan,
        category_guidance=str(prompt_payload["category_guidance"] or ""),
        gold_examples=gold_examples,
    )
    bing_prompt = build_bing_prompt(
        sku_data=parent_sku,
        evidence=evidence,
        keywords=keyword_plan,
        category_guidance=str(prompt_payload["category_guidance"] or ""),
    )
    shopify_prompt = build_shopify_prompt(
        sku_data=parent_sku,
        evidence=evidence,
        category_guidance=str(prompt_payload["category_guidance"] or ""),
    )

    platform_sections = [
        "<platform_prompt_google>\n" + google_prompt + "\n</platform_prompt_google>",
        "<platform_prompt_bing>\n" + bing_prompt + "\n</platform_prompt_bing>",
        "<platform_prompt_shopify>\n" + shopify_prompt + "\n</platform_prompt_shopify>",
        "Cross-platform output contract:\n" + json.dumps(CANDIDATE_SCHEMA, indent=2),
    ]

    user_prompt = "\n\n".join(shared_sections + platform_sections)
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
        hook_quality=score_data.get("hook_quality", 5),
        product_specificity=score_data.get("product_specificity", 5),
        competitive_diff=score_data.get("competitive_diff", 5),
        keyword_integration=score_data.get("keyword_integration", 5),
        customer_scenario=score_data.get("customer_scenario", 5),
        emotional_resonance=score_data.get("emotional_resonance", 5),
        factual_accuracy=score_data.get("factual_accuracy", 5),
        platform_compliance=score_data.get("platform_compliance", 5),
        finish_integration=score_data.get("finish_integration", 5),
        variety_score=score_data.get("variety_score", 5),
    )

    google_title = trim_title_to_length(response["google_title"], 150)
    bing_title = trim_title_to_length(response["bing_title"], 150)
    shopify_title = trim_title_to_length(response["shopify_title"], 255)
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


def _build_finish_metadata_rows(parent_sku: ParentSKU) -> list[dict[str, object]]:
    """Build canonical finish metadata rows for finish sentence prompting."""
    code_lookup = {
        (variant.finish or "").strip(): (variant.finish_code or "").strip()
        for variant in parent_sku.variants
        if getattr(variant, "finish", None)
    }
    rows: list[dict[str, object]] = []
    for finish_name in get_finish_list():
        finish_meta = get_finish_metadata(finish_name) or {}
        rows.append(
            {
                "finish_name": finish_name,
                "finish_code": code_lookup.get(finish_name, finish_name),
                "functional_description": finish_meta.get("functional_description", ""),
                "style_affinities": finish_meta.get("style_affinities", []),
                "coordination_note": finish_meta.get("coordination_note", ""),
            }
        )
    return rows


def _normalize_finish_sentence_payload(
    payload: dict[str, object],
    parent_sku: ParentSKU,
) -> dict[str, str]:
    """Normalize finish sentence payload to canonical finish-name mapping."""
    canonical_finishes = get_finish_list()
    fallback_map = build_fallback_finish_sentences(canonical_finishes)
    code_lookup = {
        (variant.finish_code or "").strip().upper(): (variant.finish or "").strip()
        for variant in parent_sku.variants
        if getattr(variant, "finish_code", None) and getattr(variant, "finish", None)
    }
    normalized: dict[str, str] = {}
    sentences = payload.get("sentences", [])
    if isinstance(sentences, list):
        for entry in sentences:
            if not isinstance(entry, dict):
                continue
            sentence = str(entry.get("sentence", "")).strip()
            if not sentence:
                continue
            finish_name = str(entry.get("finish_name", "")).strip()
            finish_code = str(entry.get("finish_code", "")).strip().upper()
            resolved_finish = ""
            if finish_name in canonical_finishes:
                resolved_finish = finish_name
            elif finish_code in code_lookup and code_lookup[finish_code] in canonical_finishes:
                resolved_finish = code_lookup[finish_code]
            if resolved_finish:
                normalized[resolved_finish] = sentence

    # Enforce complete canonical coverage to avoid downstream publish failures.
    completed: dict[str, str] = {}
    for finish_name in canonical_finishes:
        completed[finish_name] = normalized.get(
            finish_name,
            fallback_map.get(finish_name, ""),
        )
    return completed


async def generate_per_platform(
    parent_sku: ParentSKU,
    provider: LLMProvider,
    prompt_version: str = "v2",
    *,
    feedback_by_platform: dict[str, str] | None = None,
    reasoning_effort: str = "medium",
    max_completion_tokens: int = 6000,
    selected_platforms: tuple[str, ...] | list[str] | None = None,
    selected_content_types: tuple[str, ...] | list[str] | None = None,
    request_id: str | None = None,
) -> dict[str, object]:
    """Generate content via per-platform prompts/schemas.

    ``prompt_version`` is retained for API compatibility but runtime generation
    is now deterministic and always uses the per-platform prompt path.
    """
    if (prompt_version or "v2").lower() != "v2":
        logger.info(
            "Ignoring non-v2 prompt_version=%s; per-platform generation is mandatory.",
            prompt_version,
        )
    try:
        response = await execute_generation_legacy_payload(
            parent_sku=parent_sku,
            provider=provider,
            prompt_version="v2",
            feedback_by_platform=feedback_by_platform,
            reasoning_effort=reasoning_effort,
            max_completion_tokens=max_completion_tokens,
            selected_platforms=selected_platforms,
            selected_content_types=selected_content_types,
            request_id=request_id,
            prompt_overrides=None,
            system_prompt_overrides=None,
        )
    except ExecutionBudgetExceededError as exc:
        raise GenerationBudgetExceededError(
            cap_usd=exc.cap_usd,
            estimated_cost_usd=exc.estimated_cost_usd,
            platform=exc.platform,
        ) from exc
    response["prompt_experiment_variant"] = get_prompt_experiment_variant()
    return response


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
    segment_strategy = _resolve_segment_strategy(parent_sku)
    strategy_metadata = {
        "segment_strategy_id": segment_strategy.id,
        "segment_strategy_name": segment_strategy.name,
    }
    logger.info(
        "Applied segment strategy for generation",
        extra={
            "master_sku": parent_sku.master_sku,
            "segment_strategy_id": segment_strategy.id,
            "segment_strategy_name": segment_strategy.name,
        },
    )
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
            update={
                "candidate_index": idx,
                "num_candidates": count,
                "generation_metadata": strategy_metadata,
            }
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
    segment_strategy = _resolve_segment_strategy(parent_sku)
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
        category_guidance=get_category_guidance(parent_sku.category),
        segment_strategy_guidance=format_segment_strategy_guidance(segment_strategy),
        customer_context=parent_sku.category or "",
        competitive_context="",
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
    strategy = _resolve_segment_strategy(parent_sku)
    candidate = candidate.model_copy(
        update={
            "generation_metadata": {
                "segment_strategy_id": strategy.id,
                "segment_strategy_name": strategy.name,
            }
        }
    )
    logger.info(
        "Applied segment strategy for variant generation",
        extra={
            "master_sku": parent_sku.master_sku,
            "finish_name": finish_name,
            "segment_strategy_id": strategy.id,
            "segment_strategy_name": strategy.name,
        },
    )

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
