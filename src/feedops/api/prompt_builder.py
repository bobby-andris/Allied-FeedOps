"""Shared prompt construction module for all generation paths.

This module provides a single source of truth for prompt construction, ensuring
that single-SKU (/regenerate) and batch (/optimize-sku, /batch-optimize) paths
produce structurally identical prompts. This resolves FIX-01 (prompt parity) and
FIX-02 (observable feature flag activation).

Public API:
    build_core_prompt() -> str
    apply_feedback_layer() -> str

Feature flags:
    PROMPT_CONTRACT_V2: Controls whether Shopping intelligence section is included.
                        When enabled (default), the prompt includes the
                        '=== GOOGLE SHOPPING OPTIMIZATION ===' block.
                        When disabled, the block is omitted — this makes the flag
                        observably structural.
    SEGMENT_STRATEGY_V1: Controls whether segment strategy guidance is included.
                         When disabled, the segment strategy section is omitted.
    INTENT_CURATOR_V1: Effect is upstream in evidence.py — when disabled, the
                       evidence markdown contains raw (uncurated) search queries.
                       Observable via the evidence content itself, not prompt structure.
"""

from __future__ import annotations

import logging
import re

from feedops.api.prompt_loader import (
    format_gold_standard_examples,
    format_gold_standard_examples_bundle,
    get_category_guidance,
    get_finish_list,
)
from feedops.models.parent_sku import ParentSKU
from feedops.pipeline.feature_flags import (
    is_prompt_contract_v2_enabled,
    is_segment_strategy_v1_enabled,
)
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

_SEGMENT_TOKEN_RE = re.compile(r"[a-z0-9]+")


def _normalize_segment_token(value: str) -> str:
    return " ".join(_SEGMENT_TOKEN_RE.findall((value or "").lower()))


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


def build_core_prompt(
    parent_sku: ParentSKU,
    evidence: list,
    evidence_markdown: str,
    platform: str,
    content_type: str,
    finish_code: str | None = None,
    mode: str = "batch",
) -> str:
    """Build rich prompt — identical for batch and single-SKU paths.

    Includes: keyword placement plan, segment strategy, gold examples,
    Shopping intelligence (when PROMPT_CONTRACT_V2 enabled),
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

    # --- 1. Evidence table ---
    sections.append(f"Product Evidence Table:\n{evidence_markdown}")

    # --- 2. Target platform + content type header ---
    sections.append(
        f"Target platform: {platform}\nContent type to generate: {content_type}"
    )

    # --- 3. Keyword placement plan ---
    # Gracefully skip if keyword data is unavailable or errors out.
    keyword_section = ""
    try:
        if evidence:
            keyword_plan = build_keyword_placement_plan(parent_sku, evidence)
            keyword_section = format_keyword_placement_section(keyword_plan)
        else:
            # Build with empty evidence list — the plan will use fallback logic
            keyword_plan = build_keyword_placement_plan(parent_sku, [])
            keyword_section = format_keyword_placement_section(keyword_plan)
    except Exception as exc:
        logger.warning(
            "Keyword placement plan skipped for %s: %s", parent_sku.master_sku, exc
        )
        keyword_section = ""

    if keyword_section:
        sections.append(keyword_section)

    # --- 4. Segment strategy guidance ---
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

    # --- 5. Shopping intelligence section ---
    # FIX-02: PROMPT_CONTRACT_V2 gates this section.
    # Toggling PROMPT_CONTRACT_V2=0 removes the Shopping intelligence section from the prompt.
    # This makes the flag observably structural — the prompt is structurally different when toggled.
    # INTENT_CURATOR_V1 effect is in evidence.py (curated vs raw evidence content).
    # SEGMENT_STRATEGY_V1 gates the segment strategy guidance section (see step 4 above).
    if is_prompt_contract_v2_enabled():
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
    else:
        logger.debug(
            "PROMPT_CONTRACT_V2 disabled — Shopping intelligence section omitted for %s",
            parent_sku.master_sku,
        )

    # --- 6. Category guidance ---
    # shopping_intelligence.yaml is the canonical source (PRMT-03)
    category_guidance = get_category_guidance(parent_sku.category)
    if category_guidance:
        sections.append(f"Category Guidance:\n{category_guidance}")

    # --- 7. Gold standard examples ---
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
        sections.append(f"Gold Standard Examples (data-only guidance):\n{examples}")

    # --- 8. Product design story (PRMT-04, Gap 2 fix) ---
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
        product_story_parts.append(f"Manufacturer description: {parent_sku.current_description}")

    # Extract product bullets (specific selling points from the manufacturer)
    bullets = []
    for attr in ["bullet_1", "bullet_2", "bullet_3", "bullet_4"]:
        val = getattr(parent_sku, attr, None)
        if val and val.strip():
            bullets.append(val.strip())
    if bullets:
        product_story_parts.append("Product selling points:\n" + "\n".join(f"- {b}" for b in bullets))

    # Extract material, mounting, dimensions from evidence
    for ev in evidence:
        if isinstance(ev, dict):
            for field_name, label in [
                ("mounting_type", "Mounting type"),
                ("weight_capacity", "Weight capacity"),
                ("style", "Style"),
            ]:
                val = ev.get(field_name) or ev.get(field_name.replace("_", " ").title())
                if val and str(val).strip():
                    product_story_parts.append(f"{label}: {val}")
            break  # Only need first evidence row

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

    # --- 9. Competitive positioning guidance (PRMT-05, Gap 2+5 fix) ---
    # Defer to skills for competitive positioning. Only provide product-specific
    # material confirmation from evidence — not a fixed checklist.
    competitive_parts: list[str] = []

    # Material confirmation from evidence (keep this — it's product-specific)
    for ev in evidence:
        if isinstance(ev, dict):
            material = ev.get("material") or ev.get("Material") or ""
            if "brass" in str(material).lower():
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

    # --- 10. Finish context ---
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

    # --- 11. JSON output instruction ---
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
