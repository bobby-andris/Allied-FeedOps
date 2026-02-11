"""
Hybrid Content Generation for Multi-SKU Products

Adapts content from a base SKU for variant SKUs with focused prompting.
Maintains brand consistency while updating key specification differences.

Python port of dashboard/src/lib/regeneration/core.ts (adaptVariantContent)
"""

import openai
from datetime import datetime, timezone
import json
import logging
import os
import time

from feedops.api.prompt_loader import (
    get_finish_list,
    get_system_prompt,
    get_system_prompt_hash,
)
from feedops.api.runtime_controls import finish_sentence_regeneration_enabled
from feedops.models import Candidate, Score
from feedops.observability import log_event
from feedops.observability.metrics import metrics_registry
from feedops.pipeline.finish_sentence_validation import (
    normalize_and_validate_finish_sentences,
)
from feedops.pipeline.finish_sentence_placeholder import (
    inject_finish_sentence_placeholder,
)
from feedops.pipeline.validators import validate_candidate_content

logger = logging.getLogger(__name__)


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
            specificity=10,
            benefit_coverage=10,
            keyword_inclusion=10,
            format_adherence=10,
            brand_voice=10,
            factual_accuracy=10,
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
    is_variant_description = content_type == "description" and platform in [
        "google",
        "bing",
    ]

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
    Adapt content from base SKU for variant SKU.

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
        started = time.perf_counter()
        include_finish_sentences = finish_sentence_regeneration_enabled()
        log_event(
            logger,
            logging.INFO,
            "generation.variant_adaptation.start",
            base_sku=base_sku,
            variant_sku=variant_sku,
            platform=platform,
            content_type=content_type,
            include_finish_sentences=include_finish_sentences,
        )
        # Get base content
        base_result = (
            supabase.table("generated_content")
            .select("candidate_content, approved_content")
            .eq("master_sku", base_sku)
            .eq("platform", platform)
            .eq("content_type", content_type)
            .maybe_single()
            .execute()
        )

        if not base_result.data:
            return {
                "success": False,
                "error": f"No base content found for {base_sku}/{platform}/{content_type}",
            }

        base_content = base_result.data.get("approved_content") or base_result.data.get(
            "candidate_content"
        )
        if not base_content:
            return {
                "success": False,
                "error": f"Base content is empty for {base_sku}/{platform}/{content_type}",
            }

        # Get current content for version tracking
        try:
            current_result = (
                supabase.table("generated_content")
                .select("*")
                .eq("master_sku", variant_sku)
                .eq("platform", platform)
                .eq("content_type", content_type)
                .maybe_single()
                .execute()
            )

            # Validate result
            if not current_result or not hasattr(current_result, 'data'):
                logger.warning(
                    f"Query for existing content returned invalid result for {variant_sku}/{platform}/{content_type}"
                )
                current_result = type('obj', (object,), {'data': None})()
        except Exception as e:
            logger.warning(
                f"Failed to query existing content for {variant_sku}/{platform}/{content_type}: {e}"
            )
            current_result = type('obj', (object,), {'data': None})()

        # Build prompt
        system_prompt = get_system_prompt()

        user_prompt, requires_json = build_variant_adaptation_prompt(
            content_type,
            platform,
            base_sku,
            variant_sku,
            base_content,
            base_spec,
            variant_spec,
            include_finish_sentences=include_finish_sentences,
        )

        prompt_hash = get_system_prompt_hash()

        # Call OpenAI
        client = openai.OpenAI(api_key=os.getenv("OPENAI_API_KEY"))
        model = os.getenv("OPENAI_MODEL", "gpt-5.2")

        completion = client.chat.completions.create(
            model=model,
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt},
            ],
            temperature=0.6,  # Lower than full generation (0.7)
            max_completion_tokens=(
                4000
                if requires_json
                else (200 if content_type == "title" else 1000)
            ),
            **({"response_format": {"type": "json_object"}} if requires_json else {}),
        )

        raw_response = completion.choices[0].message.content.strip()

        # Parse response
        finish_sentences = None
        if requires_json:
            try:
                parsed = json.loads(raw_response)
                new_content = parsed.get("content", "").strip()
                raw_finish_sentences = parsed.get("finish_sentences")

                if not new_content:
                    return {
                        "success": False,
                        "error": "Invalid JSON response: missing content field",
                    }
                if isinstance(raw_finish_sentences, dict):
                    validated_finish_sentences, rejected = normalize_and_validate_finish_sentences(
                        raw=raw_finish_sentences,
                        finish_names=get_finish_list(),
                        base_description=new_content,
                    )
                    if rejected:
                        metrics_registry.increment(
                            "validation_failure_total",
                            type="variant_finish_sentence_rejected",
                            platform=platform,
                        )
                        logger.warning(
                            "Variant finish sentence validation rejected entries for %s/%s/%s: %s",
                            variant_sku,
                            platform,
                            content_type,
                            rejected,
                        )
                    if len(validated_finish_sentences) == len(get_finish_list()):
                        finish_sentences = validated_finish_sentences
                        new_content = inject_finish_sentence_placeholder(new_content)
                    else:
                        metrics_registry.increment(
                            "validation_failure_total",
                            type="variant_finish_sentence_incomplete",
                            platform=platform,
                        )
                        logger.warning(
                            "Variant finish sentence payload incomplete for %s/%s/%s (%s/%s accepted)",
                            variant_sku,
                            platform,
                            content_type,
                            len(validated_finish_sentences),
                            len(get_finish_list()),
                        )
            except json.JSONDecodeError as e:
                metrics_registry.increment(
                    "provider_error_total",
                    provider=f"openai/{model}",
                    error_type="JSONDecodeError",
                )
                logger.error(f"Failed to parse JSON response: {e}")
                new_content = raw_response
        else:
            new_content = raw_response

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
            logger.warning(
                "Variant adaptation validation failed for %s/%s/%s: %s",
                variant_sku,
                platform,
                content_type,
                content_validation_errors,
            )
            return {
                "success": False,
                "error": (
                    "Variant adaptation failed policy validation: "
                    + "; ".join(content_validation_errors[:3])
                ),
                "validation_errors": content_validation_errors,
            }

        # Save to database
        current_version = current_result.data["version"] if current_result.data else 0
        next_version = current_version + 1

        if current_result.data:
            supabase.table("generated_content").update(
                {
                    "candidate_content": new_content,
                    "version": next_version,
                    "is_current": True,
                    "generation_model": f"{model}-variant-adaptation",
                    "generation_prompt_hash": prompt_hash,
                    "generation_timestamp": datetime.now(timezone.utc).isoformat(),
                }
            ).eq("id", current_result.data["id"]).execute()
        else:
            supabase.table("generated_content").insert(
                {
                    "master_sku": variant_sku,
                    "platform": platform,
                    "content_type": content_type,
                    "candidate_content": new_content,
                    "version": 1,
                    "is_current": True,
                    "generation_model": f"{model}-variant-adaptation",
                    "generation_prompt_hash": prompt_hash,
                    "generation_timestamp": datetime.now(timezone.utc).isoformat(),
                }
            ).execute()

        # Save to regeneration_history
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
                "mode": "variant-adaptation",
            }
        ).execute()

        # Save finish_sentences if present (for descriptions)
        if finish_sentences and platform in ["google", "bing"]:
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
            provider=f"openai/{model}",
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
        return {"success": True, "content": new_content}

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
