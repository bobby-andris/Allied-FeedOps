"""Finish sentence building, validation, and parity enforcement."""

from __future__ import annotations

import logging

from feedops.api.persistence import _assembled_prompt_hash
from feedops.api.prompt_loader import get_finish_list, get_platform_system_prompt
from feedops.api.runtime_controls import finish_sentence_regeneration_enabled
from feedops.observability import log_event
from feedops.observability.metrics import metrics_registry
from feedops.pipeline.finish_sentence_placeholder import (
    build_fallback_finish_sentences,
    normalize_base_description_with_finish_placeholder,
    strip_hardcoded_finish_names,
    strip_generic_finish_count_claims,
)
from feedops.pipeline.finish_sentence_validation import normalize_and_validate_finish_sentences

logger = logging.getLogger(__name__)


def _build_finish_sentences_user_prompt(
    *,
    base_description: str,
    master_sku: str,
    platform: str,
) -> str:
    """Build finish-sentence prompt for Google/Bing variant descriptions."""
    finish_names = get_finish_list()
    finish_list_markdown = "\n".join(f'- "{finish}"' for finish in finish_names)
    finish_schema_template = ",\n".join(
        f'    "{finish}": "One product-specific sentence..."'
        for finish in finish_names
    )

    return f"""\
You are generating finish-specific companion lines for an existing product description.

Master SKU: {master_sku}
Platform: {platform}

Base description:
"{base_description}"

Task:
- Generate one sentence per finish in the canonical list below.
- Each sentence must reference THIS product description context (not a generic finish blurb).
- Keep claims factual and consistent with the base description.
- Do not use slash-separated keyword dumps or parenthetical keyword stuffing.

Canonical finishes:
{finish_list_markdown}

Return ONLY valid JSON:
{{
  "finish_sentences": {{
{finish_schema_template}
  }}
}}
"""


def _validate_finish_sentences_payload(
    raw: object,
    *,
    base_description: str,
    master_sku: str,
    platform: str,
) -> dict[str, str]:
    """Normalize + validate finish sentences and log rejection reasons."""
    finish_names = get_finish_list()
    accepted, rejected = normalize_and_validate_finish_sentences(
        raw=raw,
        finish_names=finish_names,
        base_description=base_description,
    )

    if rejected:
        metrics_registry.increment(
            "validation_failure_total",
            type="finish_sentence_rejected",
            platform=platform,
        )
        logger.warning(
            "Rejected finish sentences for %s/%s: %s",
            master_sku,
            platform,
            rejected,
        )
    if len(accepted) != len(finish_names):
        metrics_registry.increment(
            "validation_failure_total",
            type="finish_sentence_incomplete",
            platform=platform,
        )
    return accepted


# Deferred import to avoid circular dependency: telemetry -> generation_telemetry -> finish_processing
# We use a module-level reference so monkeypatching works in tests.
def _get_generate_with_metrics():
    from feedops.api.telemetry import _generate_with_metrics
    return _generate_with_metrics


async def _enforce_finish_sentence_parity(
    *,
    provider,
    content: str,
    master_sku: str,
    platform: str,
    endpoint: str,
) -> tuple[str, dict[str, str] | None]:
    """Apply regenerate-equivalent finish handling for Google/Bing descriptions."""
    _generate_with_metrics = _get_generate_with_metrics()

    finish_names = get_finish_list()
    fallback_finish_sentences = build_fallback_finish_sentences(finish_names)
    sanitized_content = strip_hardcoded_finish_names(
        strip_generic_finish_count_claims(content),
        finish_names,
    )
    normalized_content = normalize_base_description_with_finish_placeholder(
        sanitized_content
    )

    if not finish_sentence_regeneration_enabled():
        metrics_registry.increment(
            "generation_kill_switch_total",
            endpoint=endpoint,
            switch="finish_sentence_regen",
        )
        log_event(
            logger,
            logging.WARNING,
            "generation.finish_sentences.skipped",
            endpoint=endpoint,
            master_sku=master_sku,
            platform=platform,
            reason="FEEDOPS_DISABLE_FINISH_SENTENCE_REGEN",
        )
        metrics_registry.increment(
            "validation_failure_total",
            type="finish_sentence_fallback_used",
            platform=platform,
        )
        return normalized_content, fallback_finish_sentences

    finish_schema = {
        "type": "object",
        "properties": {
            "finish_sentences": {
                "type": "object",
                "properties": {finish: {"type": "string"} for finish in finish_names},
                "required": finish_names,
            }
        },
        "required": ["finish_sentences"],
    }
    finish_prompt = _build_finish_sentences_user_prompt(
        base_description=sanitized_content,
        master_sku=master_sku,
        platform=platform,
    )
    finish_system_prompt = get_platform_system_prompt("finish")
    finish_prompt_hash = _assembled_prompt_hash(finish_system_prompt, finish_prompt)
    log_event(
        logger,
        logging.INFO,
        "generation.finish_sentences.request",
        endpoint=endpoint,
        master_sku=master_sku,
        platform=platform,
        system_prompt_source="platform_finish",
        prompt_hash_finish=finish_prompt_hash,
    )
    finish_response = await _generate_with_metrics(
        endpoint=f"{endpoint}_finish_sentences",
        provider=provider,
        prompt=finish_prompt,
        schema=finish_schema,
        system_prompt=finish_system_prompt,
        platform=platform,
        content_type="finish_sentences",
    )

    finish_payload = finish_response.get("finish_sentences", finish_response)
    validated_finish_sentences = _validate_finish_sentences_payload(
        finish_payload,
        base_description=sanitized_content,
        master_sku=master_sku,
        platform=platform,
    )
    if len(validated_finish_sentences) != len(get_finish_list()):
        logger.warning(
            "Finish sentence generation returned incomplete canonical coverage "
            "for %s/%s (%s/%s accepted)",
            master_sku,
            platform,
            len(validated_finish_sentences),
            len(get_finish_list()),
        )
        metrics_registry.increment(
            "validation_failure_total",
            type="finish_sentence_fallback_used",
            platform=platform,
        )
        return normalized_content, fallback_finish_sentences

    return normalized_content, validated_finish_sentences
