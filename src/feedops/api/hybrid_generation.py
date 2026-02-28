"""
Hybrid Content Generation for Multi-SKU Products

Adapts content from a base SKU for variant SKUs with focused prompting.
Maintains brand consistency while updating key specification differences.

Python port of dashboard/src/lib/regeneration/core.ts (adaptVariantContent)

Note:
- The production batch hybrid path is implemented in `feedops.api.main`
  (`process_hybrid_batch_job`) and currently uses unified v2 generation for
  both base and variant SKUs.
- `adapt_variant_content` in this module is retained as a legacy/test helper
  for parity and controlled experiments, not as the active production path.
"""

from datetime import datetime, timezone
import hashlib
import json
import logging
import time

from feedops.api.prompt_loader import (
    get_finish_list,
    get_platform_system_prompt_hash,
    get_system_prompt,
    get_system_prompt_hash,
)
from feedops.api.generation_telemetry import extract_platform_telemetry
from feedops.api.supabase_loader import load_parent_sku_from_supabase
from feedops.api.sku_alias import resolve_canonical_master_sku
from feedops.api.runtime_controls import finish_sentence_regeneration_enabled
from feedops.models import Candidate, Score
from feedops.observability import log_event
from feedops.observability import get_request_id
from feedops.observability.metrics import metrics_registry
from feedops.pipeline.generator import generate_per_platform
from feedops.pipeline.finish_sentence_placeholder import (
    count_finish_sentence_placeholders,
    strip_generic_finish_count_claims,
)
from feedops.pipeline.validators import validate_candidate_content
from feedops.providers import get_provider

logger = logging.getLogger(__name__)


def _assemble_prompt_hash(system_prompt: str, user_prompt: str) -> str:
    canonical = json.dumps(
        {
            "system_prompt": system_prompt or "",
            "user_prompt": user_prompt or "",
        },
        sort_keys=True,
        separators=(",", ":"),
    )
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()


def _variant_adaptation_idempotency_key(
    *,
    base_sku: str,
    variant_sku: str,
    platform: str,
    content_type: str,
    base_spec: str,
    variant_spec: str,
) -> str:
    payload = {
        "base_sku": base_sku,
        "variant_sku": variant_sku,
        "platform": platform,
        "content_type": content_type,
        "base_spec": base_spec,
        "variant_spec": variant_spec,
    }
    canonical = json.dumps(payload, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()


def _enforce_variant_placeholder_contract(
    *,
    platform: str,
    content_type: str,
    content: str,
) -> None:
    if content_type != "description" or platform not in {"google", "bing"}:
        return
    placeholder_count = count_finish_sentence_placeholders(content)
    if placeholder_count == 1:
        return
    if placeholder_count == 0:
        raise ValueError(
            "regenerate_description_missing_finish_placeholder: "
            "Google/Bing descriptions must contain exactly one {FINISH_SENTENCE}."
        )
    raise ValueError(
        "regenerate_description_multiple_finish_placeholders: "
        "Google/Bing descriptions must contain exactly one {FINISH_SENTENCE}."
    )


def _variant_completion_tokens(platform: str, content_type: str, requires_json: bool) -> int:
    """
    Completion token policy for hybrid variant adaptation.

    Keep description generation budgets high enough to avoid placeholder-only or
    truncated responses. Titles stay intentionally small.
    """
    if content_type == "title":
        return 200
    if content_type == "description":
        if requires_json:
            return 16000
        return 8000
    # Keep non-title fallbacks generous to avoid reintroducing low-cap truncation.
    return 16000 if requires_json else 8000


def validate_adapted_variant_content(
    content_type: str,
    platform: str,
    content: str,
) -> list[str]:
    """Validate adapted variant content with the same hard policy checks as core generation."""
    sanitized_content = (
        content.replace("{FINISH_NAME}", "Polished Nickel")
        if content_type == "title"
        else content
    )

    default_title = "Variant product title"
    default_description = (
        "Solid brass construction with concealed mounting designed for long-term daily use."
    )
    target_field = f"{platform}_{content_type}"

    payload = {
        "google_title": default_title,
        "google_short_title": "Variant title",
        "google_description": default_description,
        "bing_title": default_title,
        "bing_description": default_description,
        "shopify_title": default_title,
        "shopify_description": default_description,
        "claims": [],
        "self_score": Score(
            hook_quality=10,
            product_specificity=10,
            competitive_diff=10,
            keyword_integration=10,
            customer_scenario=10,
            emotional_resonance=10,
            factual_accuracy=10,
            platform_compliance=10,
            finish_integration=10,
            variety_score=10,
        ),
    }
    payload[target_field] = sanitized_content

    candidate = Candidate(**payload)
    validation_errors = validate_candidate_content(candidate)
    return [error for error in validation_errors if error.startswith(f"{target_field} ")]


def build_variant_adaptation_prompt(
    content_type: str,
    platform: str,
    base_sku: str,
    variant_sku: str,
    base_content: str,
    base_spec: str,
    variant_spec: str,
    include_finish_sentences: bool = True,
) -> tuple[str, bool]:
    """
    Build adaptation prompt for variant content generation.

    Args:
        content_type: "title" or "description"
        platform: "google", "bing", or "shopify"
        base_sku: Base SKU name
        variant_sku: Variant SKU name
        base_content: Content from base SKU to adapt
        base_spec: Specification from base SKU (e.g., "2X")
        variant_spec: Specification for variant (e.g., "5X")

    Returns:
        Tuple of (prompt, requires_json)
    """
    is_description = content_type == "description"
    is_variant_description = is_description and platform in ["google", "bing"]

    if is_variant_description and include_finish_sentences:
        finish_names = get_finish_list()
        finish_template = {
            finish: f"One sentence relating {finish} to this {variant_spec} product..."
            for finish in finish_names
        }
        response_schema = {
            "content": f"The adapted description for {variant_spec}...",
            "finish_sentences": finish_template,
        }
        response_schema_text = json.dumps(response_schema, indent=2)

        prompt = f"""You are adapting product content for a variant specification. You MUST respond with valid JSON.

BASE PRODUCT: {base_sku}
BASE CONTENT:
{base_content}

TARGET PRODUCT: {variant_sku}
KEY DIFFERENCE: Specification changes from {base_spec} to {variant_spec}

TASK:
1. Adapt the description for the {variant_spec} specification
2. Update numeric specs and measurements ({base_spec} → {variant_spec})
3. Adjust use case emphasis based on the specification difference
4. Maintain the SAME brand voice, structure, and key selling points
5. Keep similar length and format
6. Generate finish_sentences for all 28 finishes relating to THIS variant

CRITICAL:
- This is a specification variant of the same product family
- Maintain consistency with the base content's storytelling and tone
- Focus only on meaningful differences (specs, use cases)
- Do NOT reinvent the entire description - adapt strategically

Respond with this EXACT JSON structure (no markdown, no code blocks):
{response_schema_text}"""
        return prompt, True

    if is_variant_description and not include_finish_sentences:
        prompt = f"""You are adapting product content for a variant specification.

BASE PRODUCT: {base_sku}
BASE CONTENT:
{base_content}

TARGET PRODUCT: {variant_sku}
KEY DIFFERENCE: Specification changes from {base_spec} to {variant_spec}

TASK:
1. Adapt the description for the {variant_spec} specification.
2. Update numeric specs and measurements ({base_spec} → {variant_spec}).
3. Maintain the same voice and structure from the base description.

Respond with ONLY the adapted description text."""
        return prompt, False

    if is_description:
        platform_rules = ""
        if platform == "shopify":
            platform_rules = """
4. Keep the description finish-agnostic; do NOT mention a specific finish name.
5. Preserve Shopify-friendly structure and conversion-oriented clarity."""
        prompt = f"""You are adapting product content for a variant specification.

BASE PRODUCT: {base_sku}
BASE CONTENT:
{base_content}

TARGET PRODUCT: {variant_sku}
KEY DIFFERENCE: Specification changes from {base_spec} to {variant_spec}

TASK:
1. Adapt the description for the {variant_spec} specification.
2. Update numeric specs and measurements ({base_spec} → {variant_spec}).
3. Maintain the same voice and structure from the base description.{platform_rules}

Respond with ONLY the adapted description text."""
        return prompt, False

    # For titles
    prompt = f"""You are adapting a product title for a variant specification.

BASE PRODUCT: {base_sku}
BASE TITLE: {base_content}

TARGET PRODUCT: {variant_sku}
KEY DIFFERENCE: Specification changes from {base_spec} to {variant_spec}

TASK:
Adapt the title for the {variant_spec} specification. Update the spec reference ({base_spec} → {variant_spec}) while maintaining the same structure and format.

CRITICAL RULES:
- For Google/Bing titles: Use {{FINISH_NAME}} placeholder at the START, update spec to {variant_spec}
- For Shopify titles: Update spec to {variant_spec}, keep same structure as base
- Maintain the SAME collection name, product name, and format
- ONLY change the specification number/identifier

Respond with ONLY the adapted title text."""
    return prompt, False


async def adapt_variant_content(
    supabase,
    base_sku: str,
    variant_sku: str,
    platform: str,
    content_type: str,
    base_spec: str,
    variant_spec: str,
) -> dict:
    """
    Legacy helper for variant adaptation experiments.

    Args:
        supabase: Supabase client instance
        base_sku: Base SKU to adapt from
        variant_sku: Variant SKU to generate for
        platform: "google", "bing", or "shopify"
        content_type: "title" or "description"
        base_spec: Base specification (e.g., "2X")
        variant_spec: Variant specification (e.g., "5X")

    Returns:
        Dict with success status and content/error
    """
    try:
        requested_base_sku = base_sku
        requested_variant_sku = variant_sku
        base_sku = resolve_canonical_master_sku(supabase, base_sku)
        variant_sku = resolve_canonical_master_sku(supabase, variant_sku)

        started = time.perf_counter()
        include_finish_sentences = finish_sentence_regeneration_enabled()
        log_event(
            logger,
            logging.INFO,
            "generation.variant_adaptation.start",
            base_sku=base_sku,
            variant_sku=variant_sku,
            requested_base_sku=requested_base_sku,
            requested_variant_sku=requested_variant_sku,
            platform=platform,
            content_type=content_type,
            include_finish_sentences=include_finish_sentences,
        )
        parent_sku = load_parent_sku_from_supabase(variant_sku)
        if not parent_sku:
            return {
                "success": False,
                "error": f"SKU not found for v2 variant generation: {variant_sku}",
            }

        provider = get_provider()
        selected_platforms = [platform]
        if content_type == "description" and platform in {"google", "bing"}:
            selected_platforms.append("finish")

        generated = await generate_per_platform(
            parent_sku=parent_sku,
            provider=provider,
            prompt_version="v2",
            selected_platforms=selected_platforms,
        )
        field_map = {
            ("google", "title"): "google_title",
            ("google", "description"): "google_description",
            ("bing", "title"): "bing_title",
            ("bing", "description"): "bing_description",
            ("shopify", "title"): "shopify_title",
            ("shopify", "description"): "shopify_description",
        }
        field_key = field_map.get((platform, content_type))
        if not field_key:
            return {
                "success": False,
                "error": f"Unsupported platform/content_type: {platform}/{content_type}",
            }

        new_content = str(generated.get(field_key, "")).strip()
        platform_telemetry = extract_platform_telemetry(
            platform=platform,
            usage_by_platform=generated.get("usage_by_platform"),
            latency_by_platform=generated.get("latency_by_platform"),
            retry_by_platform=generated.get("retry_by_platform"),
        )
        finish_sentences = None
        if content_type == "description" and platform in {"google", "bing"}:
            new_content = strip_generic_finish_count_claims(new_content)
            raw_finish_sentences = generated.get("finish_sentences")
            if isinstance(raw_finish_sentences, dict):
                finish_sentences = raw_finish_sentences
        _enforce_variant_placeholder_contract(
            platform=platform,
            content_type=content_type,
            content=new_content,
        )

        content_validation_errors = validate_adapted_variant_content(
            content_type=content_type,
            platform=platform,
            content=new_content,
        )
        if content_validation_errors:
            metrics_registry.increment(
                "validation_failure_total",
                type="variant_content_validation",
                platform=platform,
            )
            return {
                "success": False,
                "error": (
                    "Variant adaptation failed policy validation: "
                    + "; ".join(content_validation_errors[:3])
                ),
                "validation_errors": content_validation_errors,
            }

        current_result = (
            supabase.table("generated_content")
            .select("*")
            .eq("master_sku", variant_sku)
            .eq("platform", platform)
            .eq("content_type", content_type)
            .maybe_single()
            .execute()
        )
        current_data = (
            current_result.data
            if current_result and hasattr(current_result, "data")
            else None
        )
        current_version = current_data["version"] if current_data else 0
        next_version = current_version + 1

        prompt_hash = str(
            generated.get("prompt_hashes", {}).get(platform, get_system_prompt_hash())
        )
        system_prompt = str(
            generated.get("system_prompts", {}).get(platform, get_system_prompt())
        )
        user_prompt = str(generated.get("user_prompts", {}).get(platform, ""))
        model = provider.name
        request_id = (get_request_id() or "").strip()
        if request_id == "-":
            request_id = ""
        idempotency_key = _variant_adaptation_idempotency_key(
            base_sku=base_sku,
            variant_sku=variant_sku,
            platform=platform,
            content_type=content_type,
            base_spec=base_spec,
            variant_spec=variant_spec,
        )
        canonical_platform_hash = get_platform_system_prompt_hash(platform)
        assembled_prompt_hash = _assemble_prompt_hash(system_prompt, user_prompt)

        if current_data:
            supabase.table("generated_content").update(
                {
                    "candidate_content": new_content,
                    "version": next_version,
                    "is_current": True,
                    "generation_model": f"{model}-variant-v2",
                    "generation_prompt_hash": prompt_hash,
                    "generation_timestamp": datetime.now(timezone.utc).isoformat(),
                }
            ).eq("id", current_data["id"]).execute()
        else:
            supabase.table("generated_content").insert(
                {
                    "master_sku": variant_sku,
                    "platform": platform,
                    "content_type": content_type,
                    "candidate_content": new_content,
                    "version": 1,
                    "is_current": True,
                    "generation_model": f"{model}-variant-v2",
                    "generation_prompt_hash": prompt_hash,
                    "generation_timestamp": datetime.now(timezone.utc).isoformat(),
                }
            ).execute()

        content_id_result = (
            supabase.table("generated_content")
            .select("id")
            .eq("master_sku", variant_sku)
            .eq("platform", platform)
            .eq("content_type", content_type)
            .single()
            .execute()
        )
        supabase.table("regeneration_history").insert(
            {
                "generated_content_id": content_id_result.data["id"],
                "master_sku": variant_sku,
                "platform": platform,
                "content_type": content_type,
                "system_prompt": system_prompt,
                "user_prompt": user_prompt,
                "model_version": model,
                "prompt_hash": prompt_hash,
                "mode": "variant-adaptation-v2",
                "request_id": request_id or None,
                "result_state": "completed",
                "result_version": next_version,
                "result_idempotent": False,
                "idempotency_key": idempotency_key,
                "canonical_platform_hash": canonical_platform_hash,
                "assembled_prompt_hash": assembled_prompt_hash,
                "tokens_used": platform_telemetry.get("tokens_used"),
                "cost_usd": platform_telemetry.get("cost_usd"),
                "latency_ms": platform_telemetry.get("latency_ms"),
                "provider_attempt_count": platform_telemetry.get("provider_attempt_count"),
                "parse_retry_count": platform_telemetry.get("parse_retry_count"),
            }
        ).execute()

        if finish_sentences and platform in {"google", "bing"}:
            supabase.table("variant_finish_sentences").upsert(
                {
                    "master_sku": variant_sku,
                    "platform": platform,
                    "finish_sentences": finish_sentences,
                },
                on_conflict="master_sku,platform",
            ).execute()

        metrics_registry.observe(
            "generation_latency_seconds",
            time.perf_counter() - started,
            endpoint="adapt_variant_content",
            provider=model,
            platform=platform,
            content_type=content_type,
        )
        log_event(
            logger,
            logging.INFO,
            "generation.variant_adaptation.success",
            variant_sku=variant_sku,
            platform=platform,
            content_type=content_type,
        )
        return {"success": True, "content": new_content, "mode": "v2"}

    except Exception as e:
        metrics_registry.increment(
            "provider_error_total",
            provider="openai/variant-adaptation",
            error_type=type(e).__name__,
        )
        logger.error(f"Variant adaptation failed for {variant_sku}: {e}")
        log_event(
            logger,
            logging.ERROR,
            "generation.variant_adaptation.failure",
            variant_sku=variant_sku,
            platform=platform,
            content_type=content_type,
            error=str(e),
        )
        return {"success": False, "error": str(e)}
