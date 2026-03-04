"""Report generation for SKU optimization results."""

from __future__ import annotations

from datetime import datetime
from html import escape
import os
import re

from feedops.models import Candidate, ParentSKU, Variant
from feedops.pipeline.enrichment import detect_collection
from feedops.pipeline.finish_injection import (
    generate_variant_description,
    generate_variant_keywords,
    generate_variant_title,
)
from feedops.pipeline.keyword_placement import get_canonical_product_type
from feedops.pipeline.collection_descriptions import (
    get_collection_description,
    is_known_collection_name,
    sanitize_collection_description,
)
from feedops.pipeline.selection import RankedCandidate
from feedops.pipeline.size_matrix import build_size_matrix, get_variant_size_label
from feedops.pipeline.validators import validate_variant_title_uniqueness

# Google Merchant Center digital source type for AI-generated content
# Required for compliance with April 2024 product data specification update
DIGITAL_SOURCE_TYPE_AI = "trained_algorithmic_media"


_FIRST_P_RE = re.compile(r"<p\b[^>]*>.*?</p>", re.IGNORECASE | re.DOTALL)
_FIRST_UL_RE = re.compile(r"<ul\b[^>]*>.*?</ul>", re.IGNORECASE | re.DOTALL)


_TITLE_PIPE_RE = re.compile(r"\s*\|\s*")

_SKU_KEY_RE = re.compile(r"[^a-z0-9]+", re.IGNORECASE)


def _gmc_structured_only_enabled() -> bool:
    value = os.getenv("FEEDOPS_GMC_STRUCTURED_ONLY")
    if value is None:
        return False
    return value.strip().lower() in {"1", "true", "yes"}


def _normalize_sku_key(value: str | None) -> str:
    """Normalize SKU strings for fuzzy matching (slashes/hyphens/spaces)."""
    if not value:
        return ""
    return _SKU_KEY_RE.sub("", value.strip().lower())


def _select_primary_variant(parent_sku: ParentSKU) -> Variant | None:
    """Pick the variant that best matches the requested MasterSKU.

    When a Shopify product family contains multiple sizes and finishes, the caller
    may still request a size-specific MasterSKU (e.g., "CL-41-30"). For offer-scoped
    exports (Google/Bing), the top-level offerId/title/description must align to the
    intended variant instead of arbitrarily using the first variant.
    """
    if not parent_sku.variants:
        return None

    master_key = _normalize_sku_key(parent_sku.master_sku)
    if master_key:
        for variant in parent_sku.variants:
            if _normalize_sku_key(variant.option_sku).startswith(master_key):
                return variant

    return parent_sku.variants[0]


def _normalize_title_separators(title: str) -> str:
    """Normalize titles for feed readability (avoid pipe separators in exports).

    Internally, some parts of the pipeline may still use `|` as a segment delimiter.
    For customer-facing exports (GMC/Bing/Shopify), prefer commas/hyphens to avoid
    "gimmicky punctuation" and improve scanability.
    """
    if not title:
        return title
    normalized = _TITLE_PIPE_RE.sub(", ", title.strip())
    normalized = re.sub(r"\s{2,}", " ", normalized)

    # Remove empty segments and dangling punctuation that can be introduced when optional
    # segments (e.g., collection descriptors) are missing.
    parts = []
    for raw in normalized.split(","):
        segment = re.sub(r"\s{2,}", " ", raw).strip()
        if not segment:
            continue
        if segment.lower().endswith(" collection"):
            name = segment[: -len(" collection")].strip()
            if not is_known_collection_name(name):
                continue
            segment = f"{name} Collection"
        # Drop segments that are effectively just separators.
        if segment.strip() in {"-", "–", "—"}:
            continue
        # Trim trailing hyphens left by upstream templates like ") -"
        segment = segment.rstrip(" -–—").rstrip()
        if not segment:
            continue
        parts.append(segment)

    normalized = ", ".join(parts)
    normalized = re.sub(r"\s*,\s*", ", ", normalized).strip()
    return normalized.strip(" ,|")


def _inject_finish_into_short_title(
    short_title: str,
    finish_name: str,
    *,
    max_len: int = 70,
) -> str:
    """Prefer finish-first short titles when it fits within overlay constraints."""
    base = (short_title or "").strip()
    finish = (finish_name or "").strip()
    if not base or not finish:
        return base
    if finish.lower() in base.lower():
        return base

    prefix = f"{finish} {base}".strip()
    if len(prefix) <= max_len:
        return prefix

    suffix = f"{base}, {finish}".strip()
    if len(suffix) <= max_len:
        return suffix

    # Last resort: drop brand token to make room for finish
    base_no_brand = re.sub(r"(\s*\|\s*Allied Brass|\s*,\s*Allied Brass)\s*$", "", base, flags=re.IGNORECASE).strip(" |-," )
    if base_no_brand and base_no_brand != base:
        prefix2 = f"{finish} {base_no_brand}".strip()
        if len(prefix2) <= max_len:
            return prefix2
        suffix2 = f"{base_no_brand}, {finish}".strip()
        if len(suffix2) <= max_len:
            return suffix2

    return base


def _build_shopify_size_table(parent_sku: ParentSKU) -> str | None:
    matrix = build_size_matrix(parent_sku)
    if len(matrix) < 2:
        return None

    columns: list[tuple[str, str]] = [("overall", "Overall (in)")]
    if any(row.get("projection_in") for row in matrix):
        columns.append(("projection_in", "Projection (in)"))
    if any(row.get("weight_lb") for row in matrix):
        columns.append(("weight_lb", "Weight (lb)"))

    head_cells = "".join(f"<th>{escape(label)}</th>" for _key, label in columns)
    rows_html = []
    for row in matrix:
        size_label = escape(str(row.get("size_label", "")).strip())
        if not size_label:
            continue
        cells = [f"<td>{size_label}</td>"]
        for key, _label in columns:
            cells.append(f"<td>{escape(str(row.get(key, '')).strip())}</td>")
        rows_html.append(f"<tr>{''.join(cells)}</tr>")

    if not rows_html:
        return None

    return (
        "<h3>Size &amp; Specs</h3>"
        "<table>"
        f"<thead><tr><th>Size</th>{head_cells}</tr></thead>"
        f"<tbody>{''.join(rows_html)}</tbody>"
        "</table>"
    )


def _build_shopify_body_html(parent_sku: ParentSKU, candidate: Candidate) -> str:
    """Generate Shopify body_html, avoiding single-size claims for multi-size products."""
    size_table = _build_shopify_size_table(parent_sku)
    if not size_table:
        return candidate.shopify_description

    desc = candidate.shopify_description or ""
    hook_match = _FIRST_P_RE.search(desc)
    hook = hook_match.group(0) if hook_match else f"<p>{escape(desc.strip())}</p>"

    ul_match = _FIRST_UL_RE.search(desc)
    if ul_match:
        highlights = ul_match.group(0)
    else:
        bullets = [
            b
            for b in [
                parent_sku.bullet_1,
                parent_sku.bullet_2,
                parent_sku.bullet_3,
                parent_sku.bullet_4,
                parent_sku.bullet_5,
            ]
            if b
        ]
        if bullets:
            lis = "".join(f"<li>{escape(text)}</li>" for text in bullets)
            highlights = f"<ul>{lis}</ul>"
        else:
            highlights = ""

    collection_block = ""
    raw_collection_desc = get_collection_description(parent_sku.collection)
    if raw_collection_desc:
        cleaned = sanitize_collection_description(raw_collection_desc)
        if cleaned:
            collection_name = escape(str(parent_sku.collection or "").strip())
            collection_block = (
                f"<h3>{collection_name} Collection</h3>"
                f"<p>{escape(cleaned)}</p>"
            )

    return f"{hook}{highlights}{collection_block}{size_table}"


def _build_structured_title(title: str) -> dict:
    """Build structured_title attribute for AI-generated content.

    Google requires structured_title and structured_description attributes
    when using AI-generated content in product feeds.

    Args:
        title: The AI-generated title content

    Returns:
        Dict with digital_source_type and content fields
    """
    return {
        "digital_source_type": DIGITAL_SOURCE_TYPE_AI,
        "content": title,
    }


def _build_structured_description(description: str) -> dict:
    """Build structured_description attribute for AI-generated content.

    Args:
        description: The AI-generated description content

    Returns:
        Dict with digital_source_type and content fields
    """
    return {
        "digital_source_type": DIGITAL_SOURCE_TYPE_AI,
        "content": description,
    }


def generate_report(
    parent_sku: ParentSKU,
    candidate: Candidate,
    verification_errors: list[str],
    evidence_table: str | None = None,
    prompt: str | None = None,
    image_url: str | None = None,
    provider_name: str | None = None,
    token_usage: dict[str, int] | None = None,
    estimated_cost: float | None = None,
    selection_ranking: list[RankedCandidate] | None = None,
    generation_errors: list[str] | None = None,
    mc_metadata: dict[str, dict] | None = None,
) -> str:
    """Generate markdown report for SKU optimization.

    Args:
        parent_sku: The original parent SKU.
        candidate: The optimized candidate.
        verification_errors: List of claim verification errors.

    Returns:
        Markdown report string.
    """
    score = candidate.final_score
    verified_count = len(candidate.verified_claims)
    total_claims = len(candidate.claims)

    provider_label = provider_name or "Unknown"
    image_label = image_url if image_url else "No image available"
    if (
        token_usage
        and "prompt_tokens" in token_usage
        and "completion_tokens" in token_usage
    ):
        prompt_tokens = token_usage.get("prompt_tokens", 0)
        completion_tokens = token_usage.get("completion_tokens", 0)
        cached_tokens = token_usage.get("cached_tokens", 0)
        token_usage_label = (
            f"Prompt tokens: {prompt_tokens}, Completion tokens: {completion_tokens}"
        )
        if cached_tokens:
            cache_pct = cached_tokens * 100 // max(prompt_tokens, 1)
            token_usage_label += (
                f", Cached tokens: {cached_tokens} ({cache_pct}% cache hit)"
            )
    else:
        token_usage_label = "Not available"

    estimated_cost_label = (
        f"${estimated_cost:.6f}" if estimated_cost is not None else "Not available"
    )
    evidence_block = evidence_table or "_No evidence table provided._"
    prompt_block = prompt or "Prompt not available."

    report = f"""# Optimization Report: {parent_sku.master_sku}

**Generated:** {datetime.now().isoformat()}
**Status:** {score.approval_status.upper()}

---

## Current Content

**Title:** {parent_sku.current_title}

**Description:** {parent_sku.current_description[:200]}...

---

## Optimized Content

**Title ({len(candidate.google_title)} chars):**
```
{candidate.google_title}
```

**Description ({len(candidate.google_description)} chars):**
```
{candidate.google_description}
```

---

## Input Data Sent to LLM

**Provider/Model:** {provider_label}
**Image URL:** {image_label}
**Token Usage:** {token_usage_label}
**Estimated Cost:** {estimated_cost_label}

{evidence_block}

<details>
<summary>Full Prompt</summary>

```
{prompt_block}
```
</details>

## Quality Scores

| Dimension | Score |
|-----------|-------|
| Hook Quality | {score.hook_quality}/10 |
| Product Specificity | {score.product_specificity}/10 |
| Competitive Diff | {score.competitive_diff}/10 |
| Keyword Integration | {score.keyword_integration}/10 |
| Customer Scenario | {score.customer_scenario}/10 |
| Emotional Resonance | {score.emotional_resonance}/10 |
| Factual Accuracy | {score.factual_accuracy}/10 |
| Platform Compliance | {score.platform_compliance}/10 |
| Finish Integration | {score.finish_integration}/10 |
| Variety Score | {score.variety_score}/10 |
| **Composite** | **{score.composite}%** |

---

## Claim Verification

**Verified:** {verified_count}/{total_claims} claims

"""

    if verification_errors:
        report += "### Rejected Claims\n\n"
        for error in verification_errors:
            report += f"- {error}\n"
        report += "\n"

    if candidate.verified_claims:
        report += "### Verified Claims\n\n"
        for claim in candidate.verified_claims:
            report += (
                f"- {claim.claim} (source: {claim.source_field}={claim.source_value})\n"
            )

    if mc_metadata is not None:
        report += "\n---\n\n## Merchant Center Metadata (diagnostic)\n\n"
        if not mc_metadata:
            report += "_No Merchant Center metadata available._\n"
        else:
            variants = parent_sku.variants or []
            matched_any = False
            for variant in variants:
                offer_id = variant.gmc_id or variant.option_sku
                payload = mc_metadata.get(offer_id)
                if not payload:
                    continue
                matched_any = True

                labels = []
                for idx in range(5):
                    value = payload.get(f"customLabel{idx}")
                    if value:
                        labels.append(f"{idx}:{value}")
                labels_value = ", ".join(labels) if labels else "None"

                product_types = payload.get("productTypes") or []
                if isinstance(product_types, list):
                    product_types_label = (
                        ", ".join(product_types) if product_types else "None"
                    )
                else:
                    product_types_label = str(product_types)

                destinations = payload.get("destinationStatuses") or []
                destination_lines = []
                for status in destinations:
                    context = (
                        status.get("reportingContext")
                        or status.get("destination")
                        or "unknown"
                    )
                    if "status" in status:
                        destination_lines.append(f"{context}: {status.get('status')}")
                    else:
                        approved = ",".join(status.get("approvedCountries", []) or [])
                        pending = ",".join(status.get("pendingCountries", []) or [])
                        disapproved = ",".join(
                            status.get("disapprovedCountries", []) or []
                        )
                        destination_lines.append(
                            f"{context}: approved={approved or '-'} pending={pending or '-'} disapproved={disapproved or '-'}"
                        )
                destination_label = (
                    "; ".join(destination_lines) if destination_lines else "None"
                )

                issues = payload.get("itemLevelIssues") or []
                issue_lines = []
                for issue in issues:
                    code = issue.get("code") or "unknown"
                    severity = issue.get("severity")
                    if severity:
                        issue_lines.append(f"{code} ({severity})")
                    else:
                        issue_lines.append(code)
                issues_label = ", ".join(issue_lines) if issue_lines else "None"

                report += f"### {variant.option_sku or offer_id}\n\n"
                report += f"- Offer ID: {payload.get('offerId', offer_id)}\n"
                report += f"- Custom labels: {labels_value}\n"
                report += f"- Google product category: {payload.get('googleProductCategory') or 'None'}\n"
                report += f"- Product types: {product_types_label}\n"
                report += f"- Destination status: {destination_label}\n"
                report += f"- Item issues: {issues_label}\n\n"

            if not matched_any:
                report += "_No Merchant Center metadata matched the SKU variants._\n"

    if selection_ranking:
        weights = candidate.selection_weights or {}
        weight_label = (
            ", ".join(f"{key}={value:.2f}" for key, value in weights.items())
            or "Not available"
        )
        selected_index = (
            candidate.candidate_index
            if candidate.candidate_index is not None
            else "Not available"
        )
        total_candidates = candidate.num_candidates or len(selection_ranking)
        report += f"""

---

## Candidate Selection

**Candidates Generated:** {total_candidates}
**Selected Index:** {selected_index}
**Weights:** {weight_label}

### Top Candidates (heuristic)

| Rank | Candidate | Weighted | Google | Bing | Shopify | Validation Errors |
|------|----------:|---------:|-------:|-----:|--------:|-------------------|
"""
        for idx, entry in enumerate(selection_ranking[:3], start=1):
            candidate_index = (
                entry.candidate.candidate_index
                if entry.candidate.candidate_index is not None
                else entry.index
            )
            errors = (
                "; ".join(entry.validation_errors) if entry.validation_errors else ""
            )
            report += (
                f"| {idx} | {candidate_index} | {entry.heuristic.weighted_composite:0.2f}% |"
                f" {entry.heuristic.google.composite:0.2f}% |"
                f" {entry.heuristic.bing.composite:0.2f}% |"
                f" {entry.heuristic.shopify.composite:0.2f}% | {errors} |\n"
            )

        selected_entry = selection_ranking[0]
        if selected_entry.heuristic.soft_gate_warnings:
            report += "\n### Soft-Gate Warnings (selected candidate)\n\n"
            for warning in selected_entry.heuristic.soft_gate_warnings:
                report += f"- {warning}\n"
            report += f"\nSoft-gate penalty: {selected_entry.heuristic.soft_gate_penalty:0.2f}\n"

        if generation_errors:
            report += "\n### Generation Errors\n\n"
            for error in generation_errors[:3]:
                report += f"- {error}\n"

    report += """
---

## Recommendation

"""

    if score.approval_status == "approved":
        report += "**APPROVED** for publication. Content meets quality standards.\n"
    elif score.approval_status == "revise":
        report += "**REVISION NEEDED**. Address rejected claims before publishing.\n"
    else:
        report += "**REJECTED**. Major revisions or human review required.\n"

    return report


def _selection_meta(candidate: Candidate) -> dict:
    meta: dict = {}
    if candidate.heuristic_score is not None:
        meta["heuristic_score"] = candidate.heuristic_score
    if candidate.selection_score_adjusted is not None:
        meta["selection_score_adjusted"] = candidate.selection_score_adjusted
    if candidate.heuristic_score_breakdown:
        meta["heuristic_score_breakdown"] = candidate.heuristic_score_breakdown
    if candidate.selection_weights:
        meta["selection_weights"] = candidate.selection_weights
    if candidate.soft_gate_penalty is not None:
        meta["soft_gate_penalty"] = candidate.soft_gate_penalty
    if candidate.soft_gate_warnings:
        meta["soft_gate_warnings"] = candidate.soft_gate_warnings
    if candidate.soft_gate_miss_counts:
        meta["soft_gate_miss_counts"] = candidate.soft_gate_miss_counts
    if candidate.candidate_index is not None:
        meta["candidate_index"] = candidate.candidate_index
    if candidate.num_candidates is not None:
        meta["num_candidates"] = candidate.num_candidates
    return meta


_TRUST_SIGNAL_PATTERNS = [
    re.compile(r"lifetime warranty", re.IGNORECASE),
    re.compile(r"assembled in (?:virginia|waynesboro)", re.IGNORECASE),
    re.compile(r"(?:28|designer) finish", re.IGNORECASE),
    re.compile(r"solid brass", re.IGNORECASE),
]

_COMPETITIVE_PATTERNS = [
    re.compile(r"die[- ]cast zinc", re.IGNORECASE),
    re.compile(r"outlasts?", re.IGNORECASE),
    re.compile(r"unlike (?:mass[- ]market|lesser)", re.IGNORECASE),
    re.compile(r"alternatives?", re.IGNORECASE),
]


def _build_quality_breakdown(candidate: Candidate, platform: str) -> dict:
    """Build a quality breakdown dict for a given platform's content."""
    if platform == "google":
        title = candidate.google_title
        description = candidate.google_description
    elif platform == "bing":
        title = candidate.bing_title
        description = candidate.bing_description
    elif platform == "shopify":
        title = candidate.shopify_title
        description = candidate.shopify_description
    else:
        return {}

    trust_signals_found = sum(
        1 for pat in _TRUST_SIGNAL_PATTERNS if pat.search(description)
    )
    competitive_language_found = any(
        pat.search(description) for pat in _COMPETITIVE_PATTERNS
    )

    breakdown: dict = {
        "title_length": len(title),
        "description_length": len(description),
        "trust_signals_found": trust_signals_found,
        "competitive_language_found": competitive_language_found,
    }

    # Include per-platform heuristic composite if available
    if candidate.heuristic_score_breakdown:
        platform_score = candidate.heuristic_score_breakdown.get(platform)
        if platform_score is not None:
            breakdown["heuristic_platform_score"] = platform_score

    if candidate.heuristic_score is not None:
        breakdown["heuristic_composite"] = candidate.heuristic_score

    return breakdown


def generate_patch_preview(
    parent_sku: ParentSKU,
    candidate: Candidate,
    platform: str = "google",
) -> dict:
    """Generate platform-specific patch preview JSON.

    Args:
        parent_sku: The parent SKU being updated.
        candidate: The optimized candidate.
        platform: One of "google", "bing", or "shopify".

    Returns:
        Dict in platform-specific patch format.
    """
    primary_variant = _select_primary_variant(parent_sku)
    offer_id = (
        (primary_variant.gmc_id if primary_variant else None)
        or (parent_sku.variants[0].gmc_id if parent_sku.variants else None)
        or parent_sku.master_sku
    )
    product_id = parent_sku.item_group_id

    meta = {
        "master_sku": parent_sku.master_sku,
        "generated_at": datetime.now().isoformat(),
        "quality_score": candidate.final_score.composite,
        "approval_status": candidate.final_score.approval_status,
    }
    meta.update(_selection_meta(candidate))
    meta["quality_breakdown"] = _build_quality_breakdown(candidate, platform)
    previous = {
        "title": parent_sku.current_title,
        "description": parent_sku.current_description,
    }

    # Prepare lifestyle images data if available
    lifestyle_images_data = []
    if candidate.lifestyle_images:
        for img in candidate.lifestyle_images:
            lifestyle_images_data.append(
                {
                    "image_path": img.image_path,
                    "variation_num": img.variation_num,
                    "generation_success": img.generation_success,
                    "prompt_used": img.prompt_used,
                    "timestamp": img.timestamp,
                    "error_message": img.error_message,
                }
            )

    # Build lifestyle image link from selected image
    lifestyle_image_link = None
    if lifestyle_images_data and candidate.selected_lifestyle_image is not None:
        for img in lifestyle_images_data:
            if img.get("variation_num") == candidate.selected_lifestyle_image:
                if img.get("generation_success") and img.get("image_path"):
                    lifestyle_image_link = img["image_path"]
                break

    # Generate variant patches if variants exist
    variants_data = []
    if parent_sku.variants:
        for variant in parent_sku.variants:
            variant_patch = generate_variant_patch_preview(
                parent_sku=parent_sku,
                variant=variant,
                candidate=candidate,
                platform=platform,
            )
            variants_data.append(variant_patch)

    if platform == "google":
        structured_only = _gmc_structured_only_enabled()
        if primary_variant:
            primary_patch = generate_variant_patch_preview(
                parent_sku=parent_sku,
                variant=primary_variant,
                candidate=candidate,
                platform="google",
            )
            raw_title = primary_patch.get("title") or candidate.google_title
            title = _normalize_title_separators(raw_title)
            short_title = primary_patch.get("short_title") or candidate.google_short_title
            description = primary_patch.get("description") or candidate.google_description
        else:
            title = _normalize_title_separators(candidate.google_title)
            short_title = candidate.google_short_title
            description = candidate.google_description
        patch: dict = {
            "offerId": offer_id,
            "short_title": short_title,
            "channel": "online",
            "contentLanguage": "en",
            "targetCountry": "US",
            "_meta": meta,
            "_previous": previous,
        }
        if structured_only:
            # Structured attributes for AI-generated content disclosure.
            patch["structured_title"] = _build_structured_title(title)
            patch["structured_description"] = _build_structured_description(description)
        else:
            patch["title"] = title
            patch["description"] = description
        if lifestyle_images_data:
            patch["lifestyle_images"] = lifestyle_images_data
            patch["selected_lifestyle_image"] = candidate.selected_lifestyle_image
        if lifestyle_image_link:
            patch["lifestyle_image_link"] = lifestyle_image_link
        if variants_data:
            patch["variants"] = variants_data
        return patch

    if platform == "bing":
        if primary_variant:
            primary_patch = generate_variant_patch_preview(
                parent_sku=parent_sku,
                variant=primary_variant,
                candidate=candidate,
                platform="bing",
            )
            raw_title = primary_patch.get("title") or candidate.bing_title
            title = _normalize_title_separators(raw_title)
            description = primary_patch.get("description") or candidate.bing_description
        else:
            title = _normalize_title_separators(candidate.bing_title)
            description = candidate.bing_description
        patch = {
            "sku": offer_id,
            "title": title,
            "description": description,
            "_meta": meta,
            "_previous": previous,
        }
        if lifestyle_images_data:
            patch["lifestyle_images"] = lifestyle_images_data
            patch["selected_lifestyle_image"] = candidate.selected_lifestyle_image
        if lifestyle_image_link:
            patch["lifestyle_image_link"] = lifestyle_image_link
        if variants_data:
            patch["variants"] = variants_data
        return patch

    if platform == "shopify":
        title = _normalize_title_separators(candidate.shopify_title)
        patch = {
            "productId": product_id or offer_id,
            "title": title,
            "body_html": _build_shopify_body_html(parent_sku, candidate),
            "meta_description": candidate.shopify_meta_description,
            "_meta": meta,
            "_previous": previous,
        }
        if lifestyle_images_data:
            patch["lifestyle_images"] = lifestyle_images_data
            patch["selected_lifestyle_image"] = candidate.selected_lifestyle_image
        if lifestyle_image_link:
            patch["lifestyle_image_link"] = lifestyle_image_link
        if variants_data:
            patch["variants"] = variants_data
        return patch

    raise ValueError(f"Unsupported platform: {platform}")


def generate_variant_patch_preview(
    parent_sku: ParentSKU,
    variant: Variant,
    candidate: Candidate,
    platform: str = "google",
) -> dict:
    """Generate platform-specific patch preview JSON for a specific variant.

    This generates variant-specific content with finish-specific descriptions.

    Args:
        parent_sku: The parent SKU.
        variant: The specific variant to generate patch for.
        candidate: The optimized candidate (base content for titles/fallback).
        platform: One of "google", "bing", or "shopify".

    Returns:
        Dict in platform-specific patch format with finish-specific content.
    """
    # Get collection context for finish-collection alignment
    collection_context = detect_collection(parent_sku)
    collection_name = (
        collection_context.name if collection_context else parent_sku.collection
    )
    collection_group = collection_context.group if collection_context else None
    collection_subgroup = collection_context.subgroup if collection_context else None
    if not is_known_collection_name(collection_name):
        collection_name = None
        collection_group = None
        collection_subgroup = None

    # Get finish name
    finish_name = variant.finish

    # Generate variant-specific title
    if platform == "google":
        base_title = candidate.google_title
        base_description = candidate.google_description
    elif platform == "bing":
        base_title = candidate.bing_title
        base_description = candidate.bing_description
    elif platform == "shopify":
        base_title = candidate.shopify_title
        base_description = candidate.shopify_description
    else:
        raise ValueError(f"Unsupported platform: {platform}")

    # Generate variant-specific content
    # Only inject size for multi-size products (avoid misinterpreting series numbers like
    # "SH-84" as inches, and avoid corrupting decimal dimensions like "2.64-Inch").
    size_labels = {
        get_variant_size_label(v)
        for v in parent_sku.variants
        if get_variant_size_label(v)
    }
    is_multi_size = len(size_labels) > 1
    variant_size = get_variant_size_label(variant) if is_multi_size else None

    variant_title = _normalize_title_separators(
        generate_variant_title(
            base_title,
            finish_name,
            size=variant_size if platform in ("google", "bing") else None,
            platform=platform,
        )
    )
    variant_description = generate_variant_description(
        base_description=base_description,
        finish_name=finish_name,
        collection_name=collection_name,
        collection_group=collection_group,
        collection_subgroup=collection_subgroup,
        category=parent_sku.category,
        material=parent_sku.material,
        finish_count=len(parent_sku.variants) if parent_sku.variants else None,
        platform=platform,
        size=variant_size if platform in ("google", "bing") else None,
    )

    # Generate finish-specific keywords for this variant
    canonical_pt = get_canonical_product_type(parent_sku.category) if parent_sku.category else None
    variant_keywords = generate_variant_keywords(
        finish_name=finish_name,
        category=parent_sku.category,
        product_type=canonical_pt,
    )

    # Build meta
    meta = {
        "master_sku": parent_sku.master_sku,
        "option_sku": variant.option_sku,
        "finish": finish_name,
        "finish_keywords": variant_keywords,
        "generated_at": datetime.now().isoformat(),
        "quality_score": candidate.final_score.composite,
        "approval_status": candidate.final_score.approval_status,
    }
    meta.update(_selection_meta(candidate))
    previous = {
        "title": parent_sku.current_title,
        "description": parent_sku.current_description,
    }

    if platform == "google":
        structured_only = _gmc_structured_only_enabled()
        # Also generate variant-specific short title
        short_title = _inject_finish_into_short_title(
            candidate.google_short_title,
            finish_name,
            max_len=70,
        )
        patch: dict = {
            "offerId": variant.gmc_id,
            "short_title": short_title,
            "channel": "online",
            "contentLanguage": "en",
            "targetCountry": "US",
            "_meta": meta,
            "_previous": previous,
        }
        if structured_only:
            patch["structured_title"] = _build_structured_title(variant_title)
            patch["structured_description"] = _build_structured_description(
                variant_description
            )
        else:
            patch["title"] = variant_title
            patch["description"] = variant_description
        return patch

    if platform == "bing":
        return {
            "sku": variant.gmc_id,
            "title": variant_title,
            "description": variant_description,
            "_meta": meta,
            "_previous": previous,
        }

    if platform == "shopify":
        return {
            "productId": parent_sku.item_group_id or variant.gmc_id,
            "variantId": variant.shopify_variant_id,
            "title": variant_title,
            "body_html": variant_description,
            "meta_description": candidate.shopify_meta_description,
            "_meta": meta,
            "_previous": previous,
        }

    raise ValueError(f"Unsupported platform: {platform}")


def generate_all_variant_patches(
    parent_sku: ParentSKU,
    candidate: Candidate,
    platform: str = "google",
) -> list[dict]:
    """Generate patch previews for all variants of a parent SKU.

    Args:
        parent_sku: The parent SKU with all variants.
        candidate: The optimized candidate (base content).
        platform: One of "google", "bing", or "shopify".

    Returns:
        List of patch dicts, one per variant.
    """
    if not parent_sku.variants:
        # Fall back to single patch if no variants
        return [generate_patch_preview(parent_sku, candidate, platform)]

    patches = []
    for variant in parent_sku.variants:
        patch = generate_variant_patch_preview(
            parent_sku=parent_sku,
            variant=variant,
            candidate=candidate,
            platform=platform,
        )
        patches.append(patch)

    titles = [p.get("title", "") for p in patches]
    warnings = validate_variant_title_uniqueness(titles)
    if warnings:
        for patch in patches:
            meta = patch.get("_meta")
            if isinstance(meta, dict):
                meta["variant_title_warnings"] = warnings

    return patches
