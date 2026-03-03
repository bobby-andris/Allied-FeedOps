"""Shared prompt construction module for all generation paths.

This module provides a single source of truth for prompt construction, ensuring
that single-SKU (/regenerate) and batch (/optimize-sku, /batch-optimize) paths
produce structurally identical prompts. This resolves FIX-01 (prompt parity) and
FIX-02 (observable feature flag activation).

Public API:
    build_core_prompt() -> str
    apply_feedback_layer() -> str

Feature flags:
    SEGMENT_STRATEGY_V1: Controls whether segment strategy guidance is included.
                         When disabled, the segment strategy section is omitted.
    INTENT_CURATOR_V1: Effect is upstream in evidence.py — when disabled, the
                       evidence markdown contains raw (uncurated) search queries.
                       Observable via the evidence content itself, not prompt structure.
"""

from __future__ import annotations

import logging
import os
import re
from typing import Any

from feedops.api.prompt_loader import (
    format_gold_standard_examples,
    format_gold_standard_examples_bundle,
    get_category_guidance,
    get_finish_list,
)
from feedops.models.parent_sku import ParentSKU
from feedops.pipeline.evidence import (
    build_evidence_table,
    format_evidence_markdown,
    sanitize_catalog_prose,
    sanitize_prompt_text,
)
from feedops.pipeline.feature_flags import (
    is_segment_strategy_v1_enabled,
)
from feedops.pipeline.finish_injection import get_finish_metadata
from feedops.pipeline.keyword_placement import (
    build_keyword_placement_plan,
    format_keyword_placement_section,
)
from feedops.pipeline.segment_strategy import (
    format_segment_strategy_guidance,
    resolve_segment_strategy,
)
from feedops.pipeline.shopping_intelligence import get_shopping_intelligence_section

logger = logging.getLogger(__name__)

_PHASE28_EXPERIMENT_ENV = "FEEDOPS_PROMPT_EXPERIMENT_VARIANT"
_PHASE28_ALLOWED_VARIANTS = {
    "control",
    "a1_placeholder_burden_relaxed",
    "a2_title_constraint_relaxed",
    "a3_keyword_pressure_reduced",
    "a4_evidence_context_trimmed",
    "a5_shopify_style_transfer",
}

_SEGMENT_TOKEN_RE = re.compile(r"[a-z0-9]+")


def _normalize_segment_token(value: str) -> str:
    return " ".join(_SEGMENT_TOKEN_RE.findall((value or "").lower()))


def get_prompt_experiment_variant() -> str:
    """Return the active prompt experiment variant for Phase 28 analysis."""
    raw_value = os.environ.get(_PHASE28_EXPERIMENT_ENV, "control") or "control"
    normalized = raw_value.strip().lower()
    if normalized in _PHASE28_ALLOWED_VARIANTS:
        return normalized
    logger.warning(
        "Unknown prompt experiment variant '%s'; falling back to control",
        raw_value,
    )
    return "control"


def _phase28_variant_overlay(platform: str, variant: str) -> str:
    """Return experiment-specific instruction overlay text."""
    if variant == "a1_placeholder_burden_relaxed" and platform in {"google", "bing"}:
        return (
            "Placeholder handling simplification:\n"
            "- Keep placeholder instructions minimal: exactly one {FINISH_SENTENCE} sentence.\n"
            "- Avoid choreography language in the prose itself.\n"
            "- Write naturally around the placeholder with one sentence before and one sentence after."
        )
    if variant == "a2_title_constraint_relaxed" and platform in {"google", "bing"}:
        return (
            "Title constraint relaxation:\n"
            "- Keep only mandatory structure and platform limits.\n"
            "- Prefer natural, shopper-readable phrasing over rigid slot-filling.\n"
            "- Avoid stacking multiple optional modifiers in a single title."
        )
    if variant == "a3_keyword_pressure_reduced" and platform in {"google", "bing"}:
        return (
            "Keyword pressure reduction:\n"
            "- Use at most one synonym cluster in description copy.\n"
            "- Prefer clarity and conversion language over keyword volume.\n"
            "- Do not force exact query fragments if they reduce fluency."
        )
    if variant == "a4_evidence_context_trimmed":
        return (
            "Evidence prioritization trim:\n"
            "- Prioritize only high-signal fields (product type, primary dimension, material, mounting, collection).\n"
            "- Ignore low-signal diagnostics and metadata-like context.\n"
            "- When evidence conflicts, favor concrete catalog facts."
        )
    if variant == "a5_shopify_style_transfer" and platform in {"google", "bing"}:
        return (
            "Shopify-style flow transfer:\n"
            "- Lead with a benefit-oriented opening sentence, then support with product truth.\n"
            "- Keep sentence cadence varied (roughly 10-22 words).\n"
            "- Use smooth transitions between opening, finish sentence, and trust close."
        )
    return ""


def _ev_value(ev: Any, field_name: str) -> str:
    """Read evidence value from either Evidence dataclass rows or dict rows."""
    if isinstance(ev, dict):
        value = ev.get(field_name) or ev.get(field_name.replace("_", " ").title())
        return str(value).strip() if value is not None else ""
    if getattr(ev, "field", "") == field_name:
        return str(getattr(ev, "value", "")).strip()
    return ""


def _extract_custom_label_0(parent_sku: ParentSKU) -> str | None:
    """Extract first custom_label_0 from parent_sku merchant_center_items.

    Mirrors the extraction logic in generator.py (_extract_custom_label_0_values)
    but returns only the first value, as shopping intelligence lookup uses a
    single category string.
    """
    for item in parent_sku.merchant_center_items or []:
        raw = item.get("customLabel0") or item.get("custom_label_0")
        if not raw and isinstance(item.get("attributes"), dict):
            attrs = item["attributes"]
            raw = attrs.get("customLabel0") or attrs.get("custom_label_0")
        if not raw and isinstance(item.get("custom_labels"), dict):
            labels = item["custom_labels"]
            raw = labels.get("customLabel0") or labels.get("custom_label_0")
        value = str(raw or "").strip()
        if value:
            return value
    # Fall back to parent_sku.category (same values in practice, different source)
    return parent_sku.category or None


def _coerce_evidence_rows(
    sku_data: ParentSKU,
    evidence: list[dict[str, Any]] | None,
) -> list[dict[str, Any]]:
    if evidence:
        return evidence
    generated = build_evidence_table(sku_data)
    return generated if isinstance(generated, list) else []


def _coerce_keyword_section(
    sku_data: ParentSKU,
    evidence_rows: list[dict[str, Any]],
    keywords: Any = None,
) -> str:
    if isinstance(keywords, str) and keywords.strip():
        return sanitize_prompt_text(
            keywords.strip(),
            strip_competitor_brands=True,
        )
    if keywords and hasattr(keywords, "must_include"):
        return sanitize_prompt_text(
            format_keyword_placement_section(keywords),
            strip_competitor_brands=True,
        )
    try:
        plan = build_keyword_placement_plan(sku_data, evidence_rows)
        return sanitize_prompt_text(
            format_keyword_placement_section(plan),
            strip_competitor_brands=True,
        )
    except Exception as exc:
        logger.warning("Keyword placement section skipped for %s: %s", sku_data.master_sku, exc)
        return ""


def _default_finish_metadata(sku_data: ParentSKU) -> list[dict[str, Any]]:
    finish_code_lookup = {
        (variant.finish or "").strip(): (variant.finish_code or "").strip()
        for variant in sku_data.variants
        if getattr(variant, "finish", None)
    }
    finish_rows: list[dict[str, Any]] = []
    for finish_name in get_finish_list():
        meta = get_finish_metadata(finish_name) or {}
        finish_rows.append(
            {
                "finish_name": finish_name,
                "finish_code": finish_code_lookup.get(finish_name, finish_name),
                "functional_description": meta.get("functional_description", ""),
                "style_affinities": meta.get("style_affinities", []),
                "coordination_note": meta.get("coordination_note", ""),
            }
        )
    return finish_rows


def _build_product_design_story(sku_data: ParentSKU, evidence_rows: list[dict[str, Any]]) -> str:
    """Extract product-specific data that makes THIS product unique.

    This is the foundation for differentiation — what makes this specific
    product's design special, grounded in real evidence.
    """
    parts: list[str] = []

    if sku_data.category:
        parts.append(f"Category: {sku_data.category}")
    if sku_data.collection:
        parts.append(f"Collection: {sku_data.collection}")

    if sku_data.current_description and sku_data.current_description != sku_data.current_title:
        cleaned_description = sanitize_catalog_prose(sku_data.current_description)
        if cleaned_description:
            parts.append(f"Manufacturer description: {cleaned_description}")

    bullets = []
    for attr in ["bullet_1", "bullet_2", "bullet_3", "bullet_4"]:
        val = getattr(sku_data, attr, None)
        if val and val.strip():
            cleaned_bullet = sanitize_catalog_prose(val.strip())
            if cleaned_bullet:
                bullets.append(cleaned_bullet)
    if bullets:
        parts.append("Product selling points:\n" + "\n".join(f"- {b}" for b in bullets))

    for field_name, label in [
        ("mounting_type", "Mounting type"),
        ("style", "Style"),
    ]:
        for ev in evidence_rows:
            val = _ev_value(ev, field_name)
            if val:
                parts.append(f"{label}: {val}")
                break

    return "\n".join(parts) if parts else ""


def _build_competitive_context(sku_data: ParentSKU, evidence_rows: list[dict[str, Any]]) -> str:
    """Build product-specific competitive positioning from evidence."""
    parts: list[str] = []
    for ev in evidence_rows:
        material = _ev_value(ev, "material")
        if "brass" in material.lower():
            parts.append(
                "Solid brass construction confirmed — frame this positively "
                "(won't corrode, pit, or tarnish) without naming competitor materials."
            )
            break

    parts.append(
        "Focus on what makes THIS product's design better than alternatives. "
        "Never mention competitor materials by name."
    )
    return sanitize_prompt_text(
        "\n".join(parts),
        strip_competitor_brands=True,
    )


def build_google_prompt(
    sku_data: ParentSKU,
    evidence: list[dict[str, Any]] | None,
    keywords: Any,
    category_guidance: str | None,
    gold_examples: str | None,
) -> str:
    """Build Google-specific user prompt for variant-level generation."""
    variant = get_prompt_experiment_variant()
    evidence_rows = _coerce_evidence_rows(sku_data, evidence)
    evidence_markdown = format_evidence_markdown(
        evidence_rows,
        for_customer_copy=True,
    )
    keyword_section = _coerce_keyword_section(sku_data, evidence_rows, keywords)
    product_story = _build_product_design_story(sku_data, evidence_rows)
    competitive_context = _build_competitive_context(sku_data, evidence_rows)
    cleaned_category_guidance = sanitize_prompt_text(
        category_guidance or "",
        strip_competitor_brands=True,
        strip_banned_words=True,
    ).strip()
    cleaned_gold_examples = sanitize_prompt_text(
        gold_examples or "",
        strip_competitor_brands=True,
        strip_banned_words=True,
    ).strip()

    sections = [
        f"<task>Generate Google Shopping content for MasterSKU: {sku_data.master_sku}.</task>",
        (
            "<objective>\n"
            "Create the best product-specific Google title and description for this exact product.\n"
            "Prioritize conversion clarity and factual accuracy over keyword density.\n"
            "</objective>"
        ),
        (
            "<placeholders>\n"
            "Use the literal string {FINISH_NAME} where the finish name belongs in the title.\n"
            "{FINISH_SENTENCE} is generated by a separate finish-sentence API call and inserted during variant expansion.\n"
            "In this call, place the literal string {FINISH_SENTENCE} exactly once as its own sentence where finish context flows naturally.\n"
            "Good flow: [Design-specific opening.] {FINISH_SENTENCE} [Material or trust close.]\n"
            "Good flow: [Concrete spec opening.] [Benefit sentence.] {FINISH_SENTENCE} [Warranty/what's included close.]\n"
            "Bad flow: [Awkward transition ...] {FINISH_SENTENCE} {FINISH_SENTENCE} [duplicate or broken sentence].\n"
            "These are literal placeholders — output them exactly. Do not expand, paraphrase, or replace them.\n"
            "</placeholders>"
        ),
        f"<evidence_table>\n{evidence_markdown}\n</evidence_table>",
    ]
    if product_story:
        sections.append(
            f"<product_design_story>\n{product_story}\n</product_design_story>"
        )
    if competitive_context:
        sections.append(
            f"<competitive_positioning>\n{competitive_context}\n</competitive_positioning>"
        )
    if keyword_section:
        sections.append(
            "<keyword_enrichment_hints>\n"
            "Use keyword hints only when they improve shopper clarity and conversion relevance.\n"
            "Do not force awkward phrasing. Distill hints into clean buyer language instead of mirroring raw query fragments.\n"
            "Do not mention what a shopper searched for; write direct product copy.\n"
            "If a hint conflicts with product truth, category fidelity, or natural language, ignore it.\n\n"
            f"{keyword_section}\n"
            "</keyword_enrichment_hints>"
        )
    if cleaned_category_guidance:
        sections.append(
            f"<category_guidance>\n{cleaned_category_guidance}\n</category_guidance>"
        )
    if cleaned_gold_examples:
        sections.append(f"<gold_examples>\n{cleaned_gold_examples}\n</gold_examples>")
    if variant != "control":
        overlay = _phase28_variant_overlay("google", variant)
        sections.append(f"<experiment_variant>{variant}</experiment_variant>")
        if overlay:
            sections.append(f"<experiment_overlay>\n{overlay}\n</experiment_overlay>")
    sections.append(
        "<output>Return JSON with keys: google_title, google_short_title, "
        "google_description, claims.</output>"
    )
    return "\n\n".join(sections)


def build_bing_prompt(
    sku_data: ParentSKU,
    evidence: list[dict[str, Any]] | None,
    keywords: Any,
    category_guidance: str | None,
) -> str:
    """Build Bing-specific user prompt with literal-match emphasis."""
    variant = get_prompt_experiment_variant()
    evidence_rows = _coerce_evidence_rows(sku_data, evidence)
    evidence_markdown = format_evidence_markdown(
        evidence_rows,
        for_customer_copy=True,
    )
    keyword_section = _coerce_keyword_section(sku_data, evidence_rows, keywords)
    product_story = _build_product_design_story(sku_data, evidence_rows)
    competitive_context = _build_competitive_context(sku_data, evidence_rows)
    cleaned_category_guidance = sanitize_prompt_text(
        category_guidance or "",
        strip_competitor_brands=True,
        strip_banned_words=True,
    ).strip()

    sections = [
        f"<task>Generate Bing Shopping content for MasterSKU: {sku_data.master_sku}.</task>",
        (
            "<objective>\n"
            "Create product-specific Bing copy that is accurate, readable, and conversion-oriented.\n"
            "Treat keyword hints as optional support, not mandatory phrasing.\n"
            "</objective>"
        ),
        (
            "<placeholders>\n"
            "Use the literal string {FINISH_NAME} in the title.\n"
            "{FINISH_SENTENCE} is generated by a separate finish-sentence API call and inserted during variant expansion.\n"
            "Place {FINISH_SENTENCE} exactly once as its own sentence in the description.\n"
            "Good flow: [Spec-led opening.] {FINISH_SENTENCE} [Design detail sentence.]\n"
            "Good flow: [Product truth opening.] [Utility sentence.] {FINISH_SENTENCE} [Trust close.]\n"
            "Bad flow: [Searchy narration ...] {FINISH_SENTENCE} [fragment or duplicated placeholder].\n"
            "Do not expand, paraphrase, or duplicate placeholders.\n"
            "</placeholders>"
        ),
        f"<evidence_table>\n{evidence_markdown}\n</evidence_table>",
    ]
    if product_story:
        sections.append(
            f"<product_design_story>\n{product_story}\n</product_design_story>"
        )
    if competitive_context:
        sections.append(
            f"<competitive_positioning>\n{competitive_context}\n</competitive_positioning>"
        )
    if keyword_section:
        sections.append(
            "<keyword_enrichment_hints>\n"
            "Use keyword hints only when they improve readability and literal query relevance.\n"
            "Do not force synonym quotas or unnatural stuffing.\n"
            "Never narrate what a shopper searched for; write direct product copy.\n"
            "If a hint conflicts with product truth, category fidelity, or natural language, ignore it.\n\n"
            f"{keyword_section}\n"
            "</keyword_enrichment_hints>"
        )
    if cleaned_category_guidance:
        sections.append(
            f"<category_guidance>\n{cleaned_category_guidance}\n</category_guidance>"
        )
    if variant != "control":
        overlay = _phase28_variant_overlay("bing", variant)
        sections.append(f"<experiment_variant>{variant}</experiment_variant>")
        if overlay:
            sections.append(f"<experiment_overlay>\n{overlay}\n</experiment_overlay>")
    sections.append(
        "<output>Return JSON with keys: bing_title, bing_description, claims.</output>"
    )
    return "\n\n".join(sections)


def build_shopify_prompt(
    sku_data: ParentSKU,
    evidence: list[dict[str, Any]] | None,
    category_guidance: str | None,
) -> str:
    """Build Shopify master-SKU prompt (finish agnostic, HTML output)."""
    variant = get_prompt_experiment_variant()
    evidence_rows = _coerce_evidence_rows(sku_data, evidence)
    evidence_markdown = format_evidence_markdown(evidence_rows)
    product_story = _build_product_design_story(sku_data, evidence_rows)
    competitive_context = _build_competitive_context(sku_data, evidence_rows)
    cleaned_category_guidance = sanitize_prompt_text(
        category_guidance or "",
        strip_competitor_brands=True,
        strip_banned_words=True,
    ).strip()

    sections = [
        f"<task>Generate Shopify product page content for MasterSKU: {sku_data.master_sku}.</task>",
        (
            "<constraints>\n"
            "This is master-SKU content — do NOT mention any specific finish.\n"
            "The content must work for all 28 finish variants.\n"
            "Do NOT include {FINISH_NAME} or {FINISH_SENTENCE} placeholders.\n"
            "</constraints>"
        ),
        f"<evidence_table>\n{evidence_markdown}\n</evidence_table>",
    ]
    if product_story:
        sections.append(
            f"<product_design_story>\n{product_story}\n</product_design_story>"
        )
    if competitive_context:
        sections.append(
            f"<competitive_positioning>\n{competitive_context}\n</competitive_positioning>"
        )
    if cleaned_category_guidance:
        sections.append(
            f"<category_guidance>\n{cleaned_category_guidance}\n</category_guidance>"
        )
    if variant != "control":
        overlay = _phase28_variant_overlay("shopify", variant)
        sections.append(f"<experiment_variant>{variant}</experiment_variant>")
        if overlay:
            sections.append(f"<experiment_overlay>\n{overlay}\n</experiment_overlay>")
    sections.append(
        "<output>Return JSON with keys: shopify_title, shopify_description, "
        "shopify_meta_description, claims.</output>"
    )
    return "\n\n".join(sections)


def build_finish_prompt(
    sku_data: ParentSKU,
    finish_metadata: list[dict[str, Any]] | None,
) -> str:
    """Build prompt for product-specific finish sentence generation."""
    finish_rows = finish_metadata or _default_finish_metadata(sku_data)
    bullet_lines: list[str] = []
    for bullet in [
        sku_data.bullet_1,
        sku_data.bullet_2,
        sku_data.bullet_3,
        sku_data.bullet_4,
    ]:
        if isinstance(bullet, str) and bullet.strip():
            cleaned = sanitize_catalog_prose(bullet.strip())
            if cleaned:
                bullet_lines.append(cleaned)
    bullet_block = "\n".join(f"- {line}" for line in bullet_lines) or "- No bullet data provided."
    finish_lines = []
    for row in finish_rows:
        finish_lines.append(
            f"- {row.get('finish_code', row.get('finish_name', 'UNKNOWN'))}: {row.get('finish_name', 'Unknown')} "
            f"| functional: {row.get('functional_description', '')} "
            f"| styles: {', '.join(row.get('style_affinities', []) if isinstance(row.get('style_affinities'), list) else [])}"
        )
    finish_block = "\n".join(finish_lines)

    return "\n\n".join(
        [
            f"<task>Generate 28 finish sentences for MasterSKU: {sku_data.master_sku}.</task>",
            (
                "<product_context>\n"
                f"Category: {sku_data.category}\n"
                f"Collection: {sku_data.collection or 'N/A'}\n"
                f"Current title: {sanitize_catalog_prose(sku_data.current_title)}\n"
                "</product_context>"
            ),
            f"<selling_points>\n{bullet_block}\n</selling_points>",
            f"<finish_metadata>\n{finish_block}\n</finish_metadata>",
            (
                "<output>Return JSON with key 'sentences' as an array of objects:\n"
                '[{"finish_code": "...", "finish_name": "...", "sentence": "..."}]</output>'
            ),
        ]
    )


def build_core_prompt(
    parent_sku: ParentSKU,
    evidence: list,
    evidence_markdown: str,
    platform: str,
    content_type: str,
    finish_code: str | None = None,
    mode: str = "batch",
    query_intent_section: str | None = None,
) -> str:
    """Build rich prompt — identical for batch and single-SKU paths.

    Includes: keyword placement plan, segment strategy, gold examples,
    Shopping intelligence (always included when available),
    category guidance, finish context.

    This is the canonical prompt construction function. Both /regenerate and
    /optimize-sku/batch-optimize call this function to guarantee structural
    parity (FIX-01).

    Args:
        parent_sku: The loaded parent SKU with product data.
        evidence: Raw evidence rows (list from build_evidence_table). Used for
                  keyword placement plan. If empty, keyword placement gracefully
                  skips without error.
        evidence_markdown: Pre-formatted evidence markdown string (from
                           format_evidence_markdown).
        platform: Target platform ('google', 'bing', 'shopify').
        content_type: Content type to generate ('title', 'description').
        finish_code: Optional finish code for variant-specific context.
        mode: "batch" or "single" — controls skill loading in the system prompt.
              This parameter does NOT change the user prompt built here.
              Callers should pass mode to get_system_prompt(mode=mode,
              platform=platform) when constructing LLM messages:
                - mode="batch": system prompt includes all 8 skills (cached
                  across SKUs in batch runs, higher quality, amortized cost)
                - mode="single": system prompt includes core + platform-relevant
                  skills only (lower token cost for single-SKU regeneration)
              Defaults to "batch" so existing callers work unchanged.

    Returns:
        Assembled user prompt string ready for LLM injection.
    """
    sections: list[str] = []

    # Use a copy-safe evidence projection for Google/Bing so metadata labels
    # and raw query rows do not leak into customer-facing generation context.
    if platform in {"google", "bing"}:
        try:
            evidence_markdown = format_evidence_markdown(
                evidence if isinstance(evidence, list) else [],
                for_customer_copy=True,
            )
        except Exception as exc:
            logger.warning(
                "Copy-safe evidence formatting failed for %s (%s): %s",
                parent_sku.master_sku,
                platform,
                exc,
            )

    # --- 1. Evidence table ---
    sections.append(f"Product Evidence Table:\n{evidence_markdown}")

    # --- 2. Target platform + content type header ---
    sections.append(
        f"Target platform: {platform}\nContent type to generate: {content_type}"
    )

    if platform in {"google", "bing"}:
        sections.append(
            "Placeholder contract:\n"
            "- {FINISH_NAME} is a literal title placeholder.\n"
            "- {FINISH_SENTENCE} is generated by a separate finish-sentence API call.\n"
            "- Use {FINISH_SENTENCE} exactly once as its own sentence in the description.\n"
            "- Never paraphrase, expand, or duplicate placeholders.\n"
            "- Never narrate what someone searched for."
        )

    # --- 3. Keyword placement plan ---
    # Gracefully skip if keyword data is unavailable or errors out.
    keyword_section = ""
    try:
        if evidence:
            keyword_plan = build_keyword_placement_plan(parent_sku, evidence)
            keyword_section = sanitize_prompt_text(
                format_keyword_placement_section(keyword_plan),
                strip_competitor_brands=True,
            )
        else:
            # Build with empty evidence list — the plan will use fallback logic
            keyword_plan = build_keyword_placement_plan(parent_sku, [])
            keyword_section = sanitize_prompt_text(
                format_keyword_placement_section(keyword_plan),
                strip_competitor_brands=True,
            )
    except Exception as exc:
        logger.warning(
            "Keyword placement plan skipped for %s: %s", parent_sku.master_sku, exc
        )
        keyword_section = ""

    if keyword_section:
        sections.append(
            "Keyword Enrichment Hints (secondary to product truth and buyer clarity):\n"
            "- Use only if they improve conversion-relevant language.\n"
            "- Never force awkward phrasing or list patterns.\n"
            "- Ignore any hint that conflicts with evidence-grounded product truth.\n\n"
            f"{keyword_section}"
        )

    # --- 4. Query intent brief ---
    if (
        platform in {"google", "bing"}
        and content_type in {"title", "description"}
        and isinstance(query_intent_section, str)
        and query_intent_section.strip()
    ):
        sections.append(query_intent_section.strip())

    # --- 5. Segment strategy guidance ---
    # FIX-02: SEGMENT_STRATEGY_V1 gates this section.
    # When disabled, segment guidance is omitted from the prompt (observable structural difference).
    if is_segment_strategy_v1_enabled():
        segment_section = ""
        try:
            custom_label_values = []
            for item in parent_sku.merchant_center_items or []:
                raw = item.get("customLabel0") or item.get("custom_label_0")
                if not raw and isinstance(item.get("attributes"), dict):
                    raw = item["attributes"].get("customLabel0") or item["attributes"].get("custom_label_0")
                if not raw and isinstance(item.get("custom_labels"), dict):
                    raw = item["custom_labels"].get("customLabel0") or item["custom_labels"].get("custom_label_0")
                value = str(raw or "").strip()
                if value:
                    key = _normalize_segment_token(value)
                    if key and value not in custom_label_values:
                        custom_label_values.append(value)

            segment_strategy = resolve_segment_strategy(
                custom_label_values, enabled=True
            )
            segment_section = format_segment_strategy_guidance(segment_strategy)
        except Exception as exc:
            logger.warning(
                "Segment strategy skipped for %s: %s", parent_sku.master_sku, exc
            )
            segment_section = ""

        if segment_section:
            sections.append(segment_section)
    else:
        logger.debug(
            "SEGMENT_STRATEGY_V1 disabled — segment strategy section omitted for %s",
            parent_sku.master_sku,
        )

    # --- 6. Shopping intelligence section ---
    # Always include when available; prompt architecture is now v2-only.
    custom_label_0 = _extract_custom_label_0(parent_sku)
    shopping_section = ""
    try:
        shopping_section = get_shopping_intelligence_section(custom_label_0)
    except Exception as exc:
        logger.warning(
            "Shopping intelligence section skipped for %s: %s",
            parent_sku.master_sku,
            exc,
        )
        shopping_section = ""

    if shopping_section:
        sections.append(shopping_section)

    # --- 7. Category guidance ---
    # shopping_intelligence.yaml is the canonical source (PRMT-03)
    category_guidance = get_category_guidance(parent_sku.category)
    if category_guidance:
        cleaned_category_guidance = sanitize_prompt_text(
            category_guidance,
            strip_competitor_brands=True,
            strip_banned_words=True,
        ).strip()
        if cleaned_category_guidance:
            sections.append(f"Category Guidance:\n{cleaned_category_guidance}")

    # --- 8. Gold standard examples ---
    # Use bundle format (cross-platform) when available — mirrors generator.py.
    # format_gold_standard_examples_bundle exists in prompt_loader.py (confirmed).
    examples = ""
    try:
        examples = format_gold_standard_examples_bundle(max_examples=2)
    except Exception as exc:
        logger.warning(
            "Gold examples bundle skipped for %s: %s. Falling back to platform-specific.",
            parent_sku.master_sku,
            exc,
        )
        examples = ""

    if not examples:
        # Fallback to platform-specific examples
        try:
            examples = format_gold_standard_examples(
                platform=platform,
                content_type=content_type,
                max_examples=3,
            )
        except Exception as exc:
            logger.warning(
                "Gold examples skipped for %s: %s", parent_sku.master_sku, exc
            )
            examples = ""

    if examples:
        cleaned_examples = sanitize_prompt_text(
            examples,
            strip_competitor_brands=True,
            strip_banned_words=True,
        ).strip()
        if cleaned_examples:
            sections.append(f"Gold Standard Examples (data-only guidance):\n{cleaned_examples}")

    # --- 9. Product design story (PRMT-04, Gap 2 fix) ---
    # Extract product-specific data that makes THIS product unique.
    # This replaces the generic customer_framing block that only had category/collection.
    product_story_parts: list[str] = []

    # Product category and collection (keep these)
    if parent_sku.category:
        product_story_parts.append(f"Product category: {parent_sku.category}")
    for item in parent_sku.merchant_center_items or []:
        collection = item.get("collection") or ""
        if collection:
            product_story_parts.append(f"Collection: {collection}")
            break

    # Extract narrative copy (manufacturer's description of what makes this product special)
    if parent_sku.current_description and parent_sku.current_description != parent_sku.current_title:
        cleaned_description = sanitize_catalog_prose(parent_sku.current_description)
        if cleaned_description:
            product_story_parts.append(f"Manufacturer description: {cleaned_description}")

    # Extract product bullets (specific selling points from the manufacturer)
    bullets = []
    for attr in ["bullet_1", "bullet_2", "bullet_3", "bullet_4"]:
        val = getattr(parent_sku, attr, None)
        if val and val.strip():
            cleaned_bullet = sanitize_catalog_prose(val.strip())
            if cleaned_bullet:
                bullets.append(cleaned_bullet)
    if bullets:
        product_story_parts.append("Product selling points:\n" + "\n".join(f"- {b}" for b in bullets))

    # Extract material, mounting, dimensions from evidence
    for field_name, label in [
        ("mounting_type", "Mounting type"),
        ("style", "Style"),
    ]:
        for ev in evidence:
            val = _ev_value(ev, field_name)
            if val:
                cleaned_val = sanitize_catalog_prose(val)
                if cleaned_val:
                    product_story_parts.append(f"{label}: {cleaned_val}")
                break

    product_story = "\n".join(product_story_parts) if product_story_parts else ""

    product_block = (
        "Product Design Story:\n"
        "The following is THIS product's specific data — use it as the foundation for differentiation.\n"
        "Do NOT invent features or scenarios beyond what this data supports.\n"
        "The skills contain guidance on how to transform this data into compelling copy."
    )
    if product_story:
        product_block += f"\n\n{product_story}"
    sections.append(product_block)

    # --- 10. Competitive positioning guidance (PRMT-05, Gap 2+5 fix) ---
    # Defer to skills for competitive positioning. Only provide product-specific
    # material confirmation from evidence — not a fixed checklist.
    competitive_parts: list[str] = []

    # Material confirmation from evidence (keep this — it's product-specific)
    for ev in evidence:
        material = _ev_value(ev, "material")
        if "brass" in material.lower():
            competitive_parts.append("Evidence confirms: solid brass construction (key differentiator vs zinc competitors)")
            break

    competitive_block = (
        "Competitive Positioning:\n"
        "The allied-brass-brand-expert skill contains detailed competitive positioning guidance.\n"
        "Use THIS product's specific evidence data to ground competitive advantages — do not rely on\n"
        "generic brand-level talking points. The differentiation should come from what makes THIS\n"
        "specific product's design, construction, or functionality better than alternatives."
    )
    if competitive_parts:
        competitive_block += "\n" + "\n".join(competitive_parts)

    # Suppress "28 finishes" for Google/Bing — these descriptions get expanded to
    # finish-specific variants, making finish count references irrelevant.
    if platform in {"google", "bing"}:
        competitive_block += (
            "\n\nIMPORTANT: Do NOT mention '28 finishes,' '28+ finishes,' or finish variety counts "
            "in Google/Bing descriptions. These descriptions will be expanded into finish-specific "
            "variants — mentioning '28 other finishes' on an Antique Bronze listing confuses shoppers."
        )
    sections.append(competitive_block)

    # --- 11. Finish context ---
    # Platform-specific finish handling (mirrors _build_generation_user_prompt logic).
    context_lines: list[str] = []
    if platform in {"google", "bing"}:
        if finish_code:
            context_lines.append(
                f"Entity context: variant listing (finish: {finish_code}). "
                f"Integrate this finish naturally into the title and description."
            )
            context_lines.append(
                f"Requested variant finish code: {finish_code}."
            )
        else:
            context_lines.append(
                "Entity context: Google/Bing listing. Titles MUST include a finish name. "
                "Since no specific finish was requested, use the product's default or most popular "
                "finish from the evidence data. If no finish is determinable from evidence, use "
                "the placeholder {FINISH_NAME} which will be expanded during variant publishing."
            )
        context_lines.append(
            "Use finish names from evidence data only; do not invent unsupported finish language."
        )
    else:
        context_lines.append(
            "Entity context: master SKU storefront copy (finish-agnostic base copy for Shopify)."
        )

    finish_list = ", ".join(get_finish_list())
    context_lines.append(
        "Canonical finish vocabulary reference (use only when supported by evidence): "
        f"{finish_list}."
    )
    if context_lines:
        sections.append("\n".join(context_lines))

    # --- 12. JSON output instruction ---
    sections.append(
        f"Generate only the {content_type} for {platform}.\n"
        f'Return your response as JSON: {{"content": "your generated {content_type} here"}}'
    )

    return "\n\n".join(sections)


def apply_feedback_layer(
    core_prompt: str,
    corrections: list[dict] | None = None,
    session_feedback: str | None = None,
) -> str:
    """Layer persistent corrections + session feedback on top of core prompt.

    Feedback is additive per architecture principles — enriches the base prompt,
    doesn't fork it. If both are empty/None, returns core_prompt unchanged.

    Args:
        core_prompt: The base prompt from build_core_prompt().
        corrections: List of persistent correction dicts from sku_corrections table
                     (from sku_corrections table). Each dict should have a 'correction_text' key
                     (from sku_corrections table).
        session_feedback: Single-session feedback text from the request body.

    Returns:
        Prompt string with feedback layers appended if provided.
    """
    additions: list[str] = []

    # Persistent corrections (STRONGLY WEIGHTED) — from sku_corrections table (Plan 04)
    if corrections:
        correction_lines = []
        for correction in corrections:
            text = correction.get("correction_text") or correction.get("text") or correction.get("correction") or str(correction)
            if text:
                correction_lines.append(f"- {text}")
        if correction_lines:
            additions.append(
                "Persistent Corrections (STRONGLY WEIGHTED):\n"
                + "\n".join(correction_lines)
            )

    # Session feedback — single-request reviewer feedback
    if session_feedback and session_feedback.strip():
        additions.append(f"Reviewer Feedback:\n{session_feedback.strip()}")

    if not additions:
        return core_prompt

    return core_prompt + "\n\n" + "\n\n".join(additions)
