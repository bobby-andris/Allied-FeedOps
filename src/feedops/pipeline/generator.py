"""Candidate generator using LLM providers."""

import asyncio
import hashlib
import json
import logging
import os
import re
import time

from feedops.api.prompt_loader import (
    format_gold_standard_examples_bundle,
    get_category_guidance,
    get_finish_list,
    get_system_prompt,
)
from feedops.api.prompt_builder import (
    build_bing_prompt,
    build_finish_prompt,
    build_google_prompt,
    get_prompt_experiment_variant,
    build_shopify_prompt,
)
from feedops.models import Candidate, Claim, ParentSKU, Score
from feedops.pipeline.evidence import (
    build_evidence_table,
    filter_evidence_for_copy_context,
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
    BING_SCHEMA,
    CANDIDATE_SCHEMA,
    FINISH_SENTENCES_SCHEMA,
    FINISH_CONTEXT_TEMPLATE,
    GOOGLE_SCHEMA,
    OPTIMIZATION_TEMPLATE,
    SHOPIFY_SCHEMA,
    USER_PROMPT_TEMPLATE,
    VARIANT_USER_PROMPT_TEMPLATE,
)
from feedops.pipeline.segment_strategy import (
    SegmentStrategy,
    format_segment_strategy_guidance,
    resolve_segment_strategy,
)
from feedops.pipeline.skill_loader import get_platform_system_prompt
from feedops.pipeline.feature_flags import is_segment_strategy_v1_enabled
from feedops.pipeline.title_normalization import trim_title_to_length
from feedops.providers.base import LLMProvider

logger = logging.getLogger(__name__)
_TOKEN_RE = re.compile(r"[a-z0-9]+")


def _platform_reasoning_effort(platform: str, default_reasoning_effort: str) -> str:
    """Resolve per-platform reasoning effort."""
    return default_reasoning_effort


def _platform_completion_cap(platform: str, base_cap: int) -> int:
    """Apply per-platform completion caps for v2 generation."""
    if platform == "finish":
        return max(base_cap, 8000)
    if platform in {"google", "bing", "shopify"}:
        return max(base_cap, 16000)
    return base_cap


def _payload_value_lengths(payload: dict[str, object]) -> dict[str, int]:
    """Return best-effort character lengths for payload values."""
    lengths: dict[str, int] = {}
    for key, value in payload.items():
        if isinstance(value, str):
            lengths[key] = len(value.strip())
        elif value is None:
            lengths[key] = 0
        else:
            lengths[key] = len(str(value))
    return lengths


def _schema_hash(schema: dict[str, object]) -> str:
    """Return stable hash for schema diagnostics."""
    canonical = json.dumps(schema, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()


def _prompt_hash(system_prompt: str, user_prompt: str) -> str:
    """Return stable hash for per-platform prompt provenance."""
    combined = f"{system_prompt}\n\n{user_prompt}"
    return hashlib.sha256(combined.encode("utf-8")).hexdigest()


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
    segment_strategy = _resolve_segment_strategy(parent_sku)
    gold_examples = format_gold_standard_examples_bundle(max_examples=2)
    gold_examples_section = (
        f"\n## Gold Standard Examples\n{gold_examples}\n" if gold_examples else ""
    )

    prompt = OPTIMIZATION_TEMPLATE.format(
        system_prompt=get_system_prompt(),
        evidence_table=evidence_markdown,
        keyword_placement=keyword_placement,
        category_guidance=get_category_guidance(parent_sku.category),
        segment_strategy_guidance=format_segment_strategy_guidance(segment_strategy),
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
    segment_strategy = _resolve_segment_strategy(parent_sku)
    gold_examples = format_gold_standard_examples_bundle(max_examples=2)
    gold_examples_section = (
        f"\n## Gold Standard Examples\n{gold_examples}\n" if gold_examples else ""
    )

    user_prompt = USER_PROMPT_TEMPLATE.format(
        evidence_table=evidence_markdown,
        keyword_placement=keyword_placement,
        category_guidance=get_category_guidance(parent_sku.category),
        segment_strategy_guidance=format_segment_strategy_guidance(segment_strategy),
        customer_context=parent_sku.category or "",
        competitive_context="",
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
    reasoning_effort: str = "high",
    max_completion_tokens: int = 8000,
    selected_platforms: tuple[str, ...] | list[str] | None = None,
) -> dict[str, object]:
    """Generate content via per-platform prompts/schemas.

    ``prompt_version`` is retained for API compatibility but runtime generation
    is now deterministic and always uses the per-platform prompt path.
    """
    experiment_variant = get_prompt_experiment_variant()
    if (prompt_version or "v2").lower() != "v2":
        logger.info(
            "Ignoring non-v2 prompt_version=%s; per-platform generation is mandatory.",
            prompt_version,
        )

    evidence = build_evidence_table(parent_sku)
    evidence_for_copy = filter_evidence_for_copy_context(evidence)
    category_guidance = get_category_guidance(parent_sku.category) or ""
    keyword_section = format_keyword_placement_section(
        build_keyword_placement_plan(parent_sku, evidence)
    )
    gold_examples = format_gold_standard_examples_bundle(max_examples=2)
    finish_metadata = _build_finish_metadata_rows(parent_sku)

    user_prompts: dict[str, str] = {
        "google": build_google_prompt(
            parent_sku,
            evidence_for_copy,
            keyword_section,
            category_guidance,
            gold_examples,
        ),
        "bing": build_bing_prompt(
            parent_sku,
            evidence_for_copy,
            keyword_section,
            category_guidance,
        ),
        "shopify": build_shopify_prompt(
            parent_sku,
            evidence_for_copy,
            category_guidance,
        ),
        "finish": build_finish_prompt(parent_sku, finish_metadata),
    }
    if feedback_by_platform:
        for platform, feedback in feedback_by_platform.items():
            if (
                isinstance(feedback, str)
                and feedback.strip()
                and platform in user_prompts
            ):
                user_prompts[platform] = (
                    user_prompts[platform]
                    + "\n\nReviewer Feedback:\n"
                    + feedback.strip()
                )

    system_prompts: dict[str, str] = {
        platform: get_platform_system_prompt(platform)
        for platform in ("google", "bing", "shopify", "finish")
    }
    prompt_hashes: dict[str, str] = {
        platform: _prompt_hash(system_prompts[platform], user_prompts[platform])
        for platform in ("google", "bing", "shopify", "finish")
    }
    platform_schemas = {
        "google": GOOGLE_SCHEMA,
        "bing": BING_SCHEMA,
        "shopify": SHOPIFY_SCHEMA,
        "finish": FINISH_SENTENCES_SCHEMA,
    }
    schema_hashes = {
        platform: _schema_hash(schema)
        for platform, schema in platform_schemas.items()
    }

    raw_by_platform: dict[str, dict[str, object]] = {}
    usage_by_platform: dict[str, dict[str, int]] = {}
    latency_by_platform: dict[str, int] = {}
    parse_by_platform: dict[str, dict[str, object]] = {}
    retry_by_platform: dict[str, dict[str, int]] = {}
    requested_platforms = _resolve_requested_platforms(selected_platforms)
    for platform in requested_platforms:
        platform_reasoning = _platform_reasoning_effort(platform, reasoning_effort)
        platform_cap = _platform_completion_cap(platform, max_completion_tokens)
        started = time.perf_counter()
        payload = await provider.generate(
            prompt=user_prompts[platform],
            schema=platform_schemas[platform],
            system_prompt=system_prompts[platform],
            reasoning_effort=platform_reasoning,
            max_completion_tokens=platform_cap,
        )
        latency_by_platform[platform] = int((time.perf_counter() - started) * 1000)
        payload_keys: list[str] = []
        payload_lengths: dict[str, int] = {}
        if isinstance(payload, dict):
            payload_keys = sorted(payload.keys())
            payload_lengths = _payload_value_lengths(payload)
        logger.info(
            "Per-platform payload keys: sku=%s platform=%s keys=%s",
            parent_sku.master_sku,
            platform,
            payload_keys,
        )

        expected_content_key = {
            "google": "google_description",
            "bing": "bing_description",
            "shopify": "shopify_description",
        }.get(platform)
        if expected_content_key:
            expected_length = payload_lengths.get(expected_content_key, 0)
            if expected_length < 100:
                logger.warning(
                    "Short v2 content payload detected: sku=%s platform=%s expected_key=%s expected_len=%s keys=%s value_lengths=%s",
                    parent_sku.master_sku,
                    platform,
                    expected_content_key,
                    expected_length,
                    payload_keys,
                    payload_lengths,
                )

        raw_by_platform[platform] = payload
        usage_snapshot = getattr(provider, "last_usage", {})
        usage_by_platform[platform] = (
            usage_snapshot if isinstance(usage_snapshot, dict) else {}
        )
        parse_snapshot = getattr(provider, "last_parse_details", {})
        parse_by_platform[platform] = (
            parse_snapshot if isinstance(parse_snapshot, dict) else {}
        )
        retry_snapshot = getattr(provider, "last_retry_counts", {})
        retry_by_platform[platform] = (
            retry_snapshot if isinstance(retry_snapshot, dict) else {}
        )
        logger.info(
            "Per-platform generation usage: sku=%s platform=%s usage=%s latency_ms=%s cap=%s reasoning=%s",
            parent_sku.master_sku,
            platform,
            usage_by_platform[platform],
            latency_by_platform[platform],
            platform_cap,
            platform_reasoning,
        )
        logger.info(
            "Per-platform parse diagnostics: sku=%s platform=%s parse_mode=%s missing_keys=%s",
            parent_sku.master_sku,
            platform,
            parse_by_platform[platform].get("parse_mode", "unknown"),
            parse_by_platform[platform].get("missing_keys", []),
        )
        logger.info(
            "Per-platform retry diagnostics: sku=%s platform=%s retries=%s",
            parent_sku.master_sku,
            platform,
            retry_by_platform[platform],
        )

    finish_sentences = _normalize_finish_sentence_payload(
        raw_by_platform.get("finish", {}),
        parent_sku,
    )
    google_payload = raw_by_platform.get("google", {})
    bing_payload = raw_by_platform.get("bing", {})
    shopify_payload = raw_by_platform.get("shopify", {})

    return {
        "google_title": str(google_payload.get("google_title", "")).strip(),
        "google_short_title": _trim_google_short_title(
            str(google_payload.get("google_short_title", "")).strip()
        ),
        "google_description": str(google_payload.get("google_description", "")).strip(),
        "bing_title": str(bing_payload.get("bing_title", "")).strip(),
        "bing_description": str(bing_payload.get("bing_description", "")).strip(),
        "shopify_title": str(shopify_payload.get("shopify_title", "")).strip(),
        "shopify_description": str(shopify_payload.get("shopify_description", "")).strip(),
        "shopify_meta_description": str(
            shopify_payload.get("shopify_meta_description", "")
        ).strip(),
        "finish_sentences": finish_sentences,
        "prompt_hashes": prompt_hashes,
        "system_prompts": system_prompts,
        "user_prompts": user_prompts,
        "usage_by_platform": usage_by_platform,
        "latency_by_platform": latency_by_platform,
        "raw_by_platform": raw_by_platform,
        "schema_hashes": schema_hashes,
        "parse_by_platform": parse_by_platform,
        "retry_by_platform": retry_by_platform,
        "prompt_experiment_variant": experiment_variant,
    }


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
