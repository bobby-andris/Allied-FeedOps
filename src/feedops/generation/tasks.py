"""Prompt and schema helpers for task-scoped generation."""

from __future__ import annotations

import hashlib
import json
from typing import Any

from feedops.api.prompt_builder import build_core_prompt, build_finish_prompt
from feedops.api.prompt_loader import get_finish_list
from feedops.api.runtime_controls import finish_sentence_regeneration_enabled
from feedops.generation.contracts import GenerationTaskKind, TaskSpec
from feedops.models.parent_sku import ParentSKU
from feedops.pipeline.finish_injection import get_finish_metadata
from feedops.pipeline.query_intent_brief import QueryIntentSection
from feedops.pipeline.skill_loader import get_platform_system_prompt

TASK_FIELD_MAP = {
    ("google", "title"): "google_title",
    ("google", "description"): "google_description",
    ("bing", "title"): "bing_title",
    ("bing", "description"): "bing_description",
    ("shopify", "title"): "shopify_title",
    ("shopify", "description"): "shopify_description",
}

GOOGLE_TITLE_TASK_SCHEMA = {
    "type": "object",
    "properties": {
        "google_title": {
            "type": "string",
            "description": "Google Shopping title. Must start with literal {FINISH_NAME}.",
            "maxLength": 150,
            "pattern": r"^\{FINISH_NAME\}.+",
        },
        "google_short_title": {
            "type": "string",
            "description": "Google short title (max 70 chars).",
            "maxLength": 70,
        },
    },
    "required": ["google_title", "google_short_title"],
    "additionalProperties": False,
}

BING_TITLE_TASK_SCHEMA = {
    "type": "object",
    "properties": {
        "bing_title": {
            "type": "string",
            "description": "Bing Shopping title. Must start with literal {FINISH_NAME}.",
            "maxLength": 150,
            "pattern": r"^\{FINISH_NAME\}.+",
        },
    },
    "required": ["bing_title"],
    "additionalProperties": False,
}

SHOPIFY_TITLE_TASK_SCHEMA = {
    "type": "object",
    "properties": {
        "shopify_title": {
            "type": "string",
            "description": "Shopify title for master SKU content. Finish-agnostic.",
            "maxLength": 255,
        },
    },
    "required": ["shopify_title"],
    "additionalProperties": False,
}

GOOGLE_DESCRIPTION_TASK_SCHEMA = {
    "type": "object",
    "properties": {
        "google_description": {
            "type": "string",
            "description": "Google Shopping description with exactly one {FINISH_SENTENCE}.",
            "minLength": 250,
        },
    },
    "required": ["google_description"],
    "additionalProperties": False,
}

BING_DESCRIPTION_TASK_SCHEMA = {
    "type": "object",
    "properties": {
        "bing_description": {
            "type": "string",
            "description": "Bing Shopping description with exactly one {FINISH_SENTENCE}.",
            "minLength": 250,
        },
    },
    "required": ["bing_description"],
    "additionalProperties": False,
}

SHOPIFY_DESCRIPTION_TASK_SCHEMA = {
    "type": "object",
    "properties": {
        "shopify_description": {
            "type": "string",
            "description": "Shopify description for the master SKU. No finish placeholders.",
        },
        "shopify_meta_description": {
            "type": "string",
            "description": "Shopify SEO meta description.",
            "maxLength": 160,
        },
    },
    "required": ["shopify_description", "shopify_meta_description"],
    "additionalProperties": False,
}

VARIANT_TITLE_TASK_SCHEMA = {
    "type": "object",
    "properties": {
        "content": {"type": "string", "minLength": 1, "maxLength": 255},
    },
    "required": ["content"],
    "additionalProperties": False,
}

VARIANT_DESCRIPTION_TASK_SCHEMA = {
    "type": "object",
    "properties": {
        "content": {"type": "string", "minLength": 50},
    },
    "required": ["content"],
    "additionalProperties": False,
}


def legacy_field_key(platform: str, content_type: str) -> str:
    """Map a platform/content type pair to the legacy payload key."""
    return TASK_FIELD_MAP[(platform, content_type)]


def build_finish_metadata_rows(parent_sku: ParentSKU) -> list[dict[str, object]]:
    """Build canonical finish metadata rows for finish prompting."""
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
    """Build adaptation prompt for variant content generation."""
    is_description = content_type == "description"
    is_variant_description = is_description and platform in ["google", "bing"]

    if is_variant_description:
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
4. Do NOT generate finish sentence mappings or any extra JSON fields.

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


def build_task_prompt(
    spec: TaskSpec,
    *,
    parent_sku: ParentSKU,
    evidence: list,
    evidence_markdown: str,
    feedback_by_platform: dict[str, str] | None = None,
    query_intent_context: QueryIntentSection | None = None,
) -> str:
    """Build a user prompt for one task spec."""
    if spec.kind == GenerationTaskKind.FINISH_SENTENCES:
        return build_finish_prompt(parent_sku, build_finish_metadata_rows(parent_sku))

    prompt = build_core_prompt(
        parent_sku,
        evidence,
        evidence_markdown,
        spec.platform,
        spec.content_type,
        query_intent_section=(
            query_intent_context.content
            if isinstance(query_intent_context, QueryIntentSection)
            else None
        ),
    )
    feedback = None
    if isinstance(feedback_by_platform, dict):
        raw_feedback = feedback_by_platform.get(spec.platform)
        if isinstance(raw_feedback, str) and raw_feedback.strip():
            feedback = raw_feedback
    if feedback:
        prompt = prompt + "\n\nReviewer Feedback:\n" + feedback.strip()
    schema = build_task_schema(spec)
    required_keys = ", ".join(schema.get("required", []))
    prompt = (
        prompt
        + "\n\n"
        + "Task Output Contract:\n"
        + f"Return ONLY valid JSON with keys: {required_keys}.\n"
        + "Do not add any extra keys, markdown fences, or commentary."
    )
    return prompt


def build_task_schema(spec: TaskSpec) -> dict[str, object]:
    """Resolve the schema for a task spec."""
    if spec.kind == GenerationTaskKind.TITLE:
        if spec.platform == "google":
            return GOOGLE_TITLE_TASK_SCHEMA
        if spec.platform == "bing":
            return BING_TITLE_TASK_SCHEMA
        if spec.platform == "shopify":
            return SHOPIFY_TITLE_TASK_SCHEMA
    if spec.kind == GenerationTaskKind.DESCRIPTION_BASE:
        if spec.platform == "google":
            return GOOGLE_DESCRIPTION_TASK_SCHEMA
        if spec.platform == "bing":
            return BING_DESCRIPTION_TASK_SCHEMA
        if spec.platform == "shopify":
            return SHOPIFY_DESCRIPTION_TASK_SCHEMA
    if spec.kind == GenerationTaskKind.FINISH_SENTENCES:
        finish_names = get_finish_list()
        return {
            "type": "object",
            "properties": {
                "finish_sentences": {
                    "type": "object",
                    "properties": {finish: {"type": "string"} for finish in finish_names},
                    "required": finish_names,
                    "additionalProperties": False,
                }
            },
            "required": ["finish_sentences"],
            "additionalProperties": False,
        }
    if spec.kind == GenerationTaskKind.VARIANT_ADAPTATION:
        if spec.content_type == "title":
            return VARIANT_TITLE_TASK_SCHEMA
        return VARIANT_DESCRIPTION_TASK_SCHEMA
    raise ValueError(f"Unsupported task kind: {spec.kind}")


def build_task_system_prompt(spec: TaskSpec) -> str:
    """Resolve system prompt for a task."""
    if spec.kind == GenerationTaskKind.FINISH_SENTENCES:
        return get_platform_system_prompt("finish")
    return get_platform_system_prompt(spec.platform)


def task_prompt_hash(system_prompt: str, user_prompt: str) -> str:
    """Return a stable prompt hash for lineage."""
    combined = f"{system_prompt}\n\n{user_prompt}"
    return hashlib.sha256(combined.encode("utf-8")).hexdigest()


def _normalize_finish_sentences_payload(payload: dict[str, Any]) -> dict[str, str]:
    """Normalize finish generation payloads into the canonical flat mapping."""
    if not isinstance(payload, dict):
        return {}

    explicit_map = payload.get("finish_sentences")
    if isinstance(explicit_map, dict):
        return {
            str(finish).strip(): str(sentence).strip()
            for finish, sentence in explicit_map.items()
            if str(finish).strip() and str(sentence).strip()
        }

    sentences = payload.get("sentences")
    if isinstance(sentences, list):
        normalized: dict[str, str] = {}
        for row in sentences:
            if not isinstance(row, dict):
                continue
            finish_name = str(row.get("finish_name", "")).strip()
            sentence = str(row.get("sentence", "")).strip()
            if finish_name and sentence:
                normalized[finish_name] = sentence
        return normalized

    return {}


def task_result_content(payload: dict[str, Any], spec: TaskSpec) -> tuple[str, dict[str, Any]]:
    """Extract the primary content string and task metadata from a payload."""
    if spec.kind == GenerationTaskKind.FINISH_SENTENCES:
        return "", {"finish_sentences": _normalize_finish_sentences_payload(payload)}
    if spec.kind == GenerationTaskKind.VARIANT_ADAPTATION:
        content = str(payload.get("content", "")).strip()
        finish_sentences = _normalize_finish_sentences_payload(payload)
        metadata: dict[str, Any] = {}
        if finish_sentences:
            metadata["finish_sentences"] = finish_sentences
        return content, metadata

    field_key = legacy_field_key(spec.platform, spec.content_type)
    content = str(payload.get(field_key, "")).strip()
    metadata: dict[str, Any] = {}
    if spec.platform == "google" and spec.content_type == "title":
        metadata["google_short_title"] = str(payload.get("google_short_title", "")).strip()
    if "shopify_meta_description" in payload:
        metadata["shopify_meta_description"] = str(
            payload.get("shopify_meta_description", "")
        ).strip()
    if "claims" in payload and isinstance(payload.get("claims"), list):
        metadata["claims"] = payload["claims"]
    return content, metadata


def finish_should_execute(
    *,
    selected_platforms: tuple[str, ...] | list[str],
    selected_content_types: tuple[str, ...] | list[str],
) -> bool:
    """Return True when the request scope genuinely needs finish generation."""
    requested_platforms = {platform for platform in selected_platforms}
    requested_content_types = {content_type for content_type in selected_content_types}
    return (
        finish_sentence_regeneration_enabled()
        and "finish" in requested_platforms
        and "description" in requested_content_types
        and bool({"google", "bing"} & requested_platforms)
    )
