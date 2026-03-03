"""
Hybrid Content Generation for Multi-SKU Products

Adapts content from a base SKU for variant SKUs with focused prompting.
Maintains brand consistency while updating key specification differences.

Python port of dashboard/src/lib/regeneration/core.ts (adaptVariantContent)
"""

from datetime import datetime, timezone
import hashlib
import inspect
import json
import logging
import re
import time

from feedops.api.prompt_loader import (
    get_finish_list,
    get_platform_system_prompt_hash,
)
from feedops.api.generation_telemetry import (
    estimate_openai_cost_usd_from_usage,
    extract_platform_telemetry,
    provider_label,
    safe_int,
)
from feedops.api.sku_alias import resolve_canonical_master_sku
from feedops.api.runtime_controls import finish_sentence_regeneration_enabled
from feedops.generation.contracts import GenerationTaskKind, TaskSpec
from feedops.generation.persistence import persist_finish_sentences
from feedops.generation.tasks import (
    build_task_schema,
    build_task_system_prompt,
    task_prompt_hash,
)
from feedops.models import Candidate, Score
from feedops.observability import log_event
from feedops.observability import get_request_id
from feedops.observability.metrics import metrics_registry
from feedops.pipeline.finish_sentence_placeholder import (
    count_finish_sentence_placeholders,
    strip_generic_finish_count_claims,
)
from feedops.pipeline.validators import validate_candidate_content
from feedops.providers import get_provider
from feedops.providers.base import close_provider

logger = logging.getLogger(__name__)


async def _generate_with_provider_compat(
    *,
    provider,
    prompt: str,
    schema: dict[str, object],
    system_prompt: str,
    reasoning_effort: str,
    max_completion_tokens: int,
) -> dict[str, object]:
    """Call provider.generate while tolerating legacy test doubles."""
    generate_fn = provider.generate
    signature = inspect.signature(generate_fn)
    accepts_varkw = any(
        param.kind == inspect.Parameter.VAR_KEYWORD
        for param in signature.parameters.values()
    )
    kwargs: dict[str, object] = {
        "prompt": prompt,
        "schema": schema,
        "system_prompt": system_prompt,
    }
    if accepts_varkw or "reasoning_effort" in signature.parameters:
        kwargs["reasoning_effort"] = reasoning_effort
    if accepts_varkw or "max_completion_tokens" in signature.parameters:
        kwargs["max_completion_tokens"] = max_completion_tokens
    return await generate_fn(**kwargs)


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


def _deterministic_spec_rewrite(
    *,
    base_content: str,
    base_spec: str,
    variant_spec: str,
) -> str:
    """Best-effort deterministic replacement for spec-only variant adaptation."""
    source = str(base_content or "")
    old = str(base_spec or "").strip()
    new = str(variant_spec or "").strip()
    if not source or not old or not new or old == new:
        return source

    token_pattern = re.compile(
        rf"(?<![A-Za-z0-9]){re.escape(old)}(?![A-Za-z0-9])"
    )
    rewritten = token_pattern.sub(new, source)
    if rewritten != source:
        return rewritten

    return source.replace(old, new)


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
    *,
    base_content: str | None = None,
    base_finish_sentences: dict[str, str] | None = None,
    request_id: str | None = None,
    provider=None,  # Kept for call-site compatibility; variant adaptation is deterministic.
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
        requested_base_sku = base_sku
        requested_variant_sku = variant_sku
        base_sku = resolve_canonical_master_sku(supabase, base_sku)
        variant_sku = resolve_canonical_master_sku(supabase, variant_sku)

        started = time.perf_counter()
        reuse_finish_sentences = (
            content_type == "description"
            and platform in {"google", "bing"}
            and isinstance(base_finish_sentences, dict)
            and bool(base_finish_sentences)
        )
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
            include_finish_sentences=reuse_finish_sentences,
            generate_finish_sentences=False,
        )
        if not base_content:
            base_row = (
                supabase.table("generated_content")
                .select("candidate_content")
                .eq("master_sku", base_sku)
                .eq("platform", platform)
                .eq("content_type", content_type)
                .eq("is_current", True)
                .maybe_single()
                .execute()
            )
            base_content = (
                str((base_row.data or {}).get("candidate_content", "")).strip()
                if getattr(base_row, "data", None)
                else ""
            )
        if not base_content:
            return {
                "success": False,
                "error": (
                    f"Missing base content for variant adaptation: "
                    f"{base_sku} {platform}/{content_type}"
                ),
            }

        prompt, requires_json = build_variant_adaptation_prompt(
            content_type=content_type,
            platform=platform,
            base_sku=base_sku,
            variant_sku=variant_sku,
            base_content=base_content,
            base_spec=base_spec,
            variant_spec=variant_spec,
            include_finish_sentences=False,
        )
        spec = TaskSpec(
            task_id=f"adapt-{variant_sku}-{platform}-{content_type}",
            kind=GenerationTaskKind.VARIANT_ADAPTATION,
            master_sku=base_sku,
            variant_sku=variant_sku,
            platform=platform,
            content_type=content_type,
            prompt_version="v2",
            request_id=(request_id or "").strip() or (get_request_id() or "").strip(),
        )
        system_prompt = build_task_system_prompt(spec)
        schema = build_task_schema(spec)
        deterministic_content = _deterministic_spec_rewrite(
            base_content=base_content,
            base_spec=base_spec,
            variant_spec=variant_spec,
        )
        use_deterministic_path = (
            deterministic_content.strip() != str(base_content).strip()
        ) or provider is not None

        if use_deterministic_path:
            payload = {"content": deterministic_content}
            usage_snapshot: dict[str, object] = {}
            retry_snapshot: dict[str, object] = {}
            model = "deterministic-variant-adapter"
        else:
            managed_provider = get_provider()
            payload = await _generate_with_provider_compat(
                provider=managed_provider,
                prompt=prompt,
                schema=schema,
                system_prompt=system_prompt,
                reasoning_effort="medium" if content_type == "description" else "low",
                max_completion_tokens=_variant_completion_tokens(
                    platform=platform,
                    content_type=content_type,
                    requires_json=requires_json,
                ),
            )
            usage_snapshot = (
                getattr(managed_provider, "last_usage", {})
                if managed_provider is not None
                else {}
            )
            retry_snapshot = (
                getattr(managed_provider, "last_retry_counts", {})
                if managed_provider is not None
                else {}
            )
            model = (
                provider_label(managed_provider)
                if managed_provider is not None
                else "unknown"
            )
            await close_provider(managed_provider)

        if spec.request_id == "-":
            spec.request_id = ""

        if spec.content_type == "description" and platform in {"google", "bing"}:
            new_content = str(payload.get("content", "")).strip()
            new_content = strip_generic_finish_count_claims(new_content)
            finish_sentences = (
                dict(base_finish_sentences)
                if isinstance(base_finish_sentences, dict)
                else None
            )
        else:
            new_content = str(payload.get("content", "")).strip()
            finish_sentences = None

        platform_telemetry = extract_platform_telemetry(
            platform=platform,
            usage_by_platform={platform: usage_snapshot}
            if isinstance(usage_snapshot, dict)
            else {},
            latency_by_platform={platform: int((time.perf_counter() - started) * 1000)},
            retry_by_platform={platform: retry_snapshot}
            if isinstance(retry_snapshot, dict)
            else {},
        )
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

        try:
            current_result = (
                supabase.table("generated_content")
                .select("*")
                .eq("master_sku", variant_sku)
                .eq("platform", platform)
                .eq("content_type", content_type)
                .eq("is_current", True)
                .maybe_single()
                .execute()
            )
            current_data = (
                current_result.data
                if current_result and hasattr(current_result, "data")
                else None
            )
        except Exception as lookup_err:
            logger.warning(
                "generated_content lookup returned multiple rows for "
                "%s/%s/%s, falling back to insert: %s",
                variant_sku, platform, content_type, lookup_err,
            )
            current_data = None
        current_version = current_data["version"] if current_data else 0
        next_version = current_version + 1

        prompt_hash = task_prompt_hash(system_prompt, prompt)
        user_prompt = prompt
        request_id = spec.request_id if spec.request_id != "-" else ""
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

        try:
            content_id_result = (
                supabase.table("generated_content")
                .select("id")
                .eq("master_sku", variant_sku)
                .eq("platform", platform)
                .eq("content_type", content_type)
                .eq("is_current", True)
                .maybe_single()
                .execute()
            )
            generated_content_id = (
                content_id_result.data["id"]
                if content_id_result and getattr(content_id_result, "data", None)
                else None
            )
        except Exception as id_err:
            logger.warning(
                "Content ID lookup failed for %s/%s/%s: %s",
                variant_sku, platform, content_type, id_err,
            )
            generated_content_id = None
        supabase.table("regeneration_history").insert(
            {
                "generated_content_id": generated_content_id,
                "master_sku": variant_sku,
                "platform": platform,
                "content_type": content_type,
                "previous_content": current_data.get("candidate_content")
                if isinstance(current_data, dict)
                else None,
                "new_content": new_content,
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
            persist_finish_sentences(
                supabase=supabase,
                master_sku=variant_sku,
                platform=platform,
                finish_sentences=finish_sentences,
            )

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
        return {
            "success": True,
            "content": new_content,
            "mode": "v2",
            "generated_content_id": content_id_result.data["id"],
        }

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
