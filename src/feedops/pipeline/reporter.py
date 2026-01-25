"""Report generation for SKU optimization results."""
from __future__ import annotations

from datetime import datetime
from feedops.models import ParentSKU, Candidate, Variant
from feedops.pipeline.finish_injection import (
    generate_variant_description,
    generate_variant_title,
)
from feedops.pipeline.enrichment import detect_collection
from feedops.pipeline.selection import RankedCandidate


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
    if token_usage and "prompt_tokens" in token_usage and "completion_tokens" in token_usage:
        prompt_tokens = token_usage.get("prompt_tokens", 0)
        completion_tokens = token_usage.get("completion_tokens", 0)
        token_usage_label = f"Prompt tokens: {prompt_tokens}, Completion tokens: {completion_tokens}"
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
| Specificity | {score.specificity}/10 |
| Benefit Coverage | {score.benefit_coverage}/10 |
| Keyword Inclusion | {score.keyword_inclusion}/10 |
| Format Adherence | {score.format_adherence}/10 |
| Brand Voice | {score.brand_voice}/10 |
| Factual Accuracy | {score.factual_accuracy}/10 |
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
            report += f"- {claim.claim} (source: {claim.source_field}={claim.source_value})\n"

    if selection_ranking:
        weights = candidate.selection_weights or {}
        weight_label = ", ".join(
            f"{key}={value:.2f}" for key, value in weights.items()
        ) or "Not available"
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
            errors = "; ".join(entry.validation_errors) if entry.validation_errors else ""
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
            report += (
                f"\nSoft-gate penalty: {selected_entry.heuristic.soft_gate_penalty:0.2f}\n"
            )

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
    offer_id = parent_sku.variants[0].gmc_id if parent_sku.variants else parent_sku.master_sku
    product_id = parent_sku.item_group_id

    meta = {
        "master_sku": parent_sku.master_sku,
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
        return {
            "offerId": offer_id,
            "title": candidate.google_title,
            "short_title": candidate.google_short_title,
            "description": candidate.google_description,
            "channel": "online",
            "contentLanguage": "en",
            "targetCountry": "US",
            "_meta": meta,
            "_previous": previous,
        }

    if platform == "bing":
        return {
            "sku": offer_id,
            "title": candidate.bing_title,
            "description": candidate.bing_description,
            "_meta": meta,
            "_previous": previous,
        }

    if platform == "shopify":
        return {
            "productId": product_id or offer_id,
            "title": candidate.shopify_title,
            "body_html": candidate.shopify_description,
            "_meta": meta,
            "_previous": previous,
        }

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
        candidate: The optimized candidate (base content).
        platform: One of "google", "bing", or "shopify".
        
    Returns:
        Dict in platform-specific patch format with finish-specific content.
    """
    # Get collection context for finish-collection alignment
    collection_context = detect_collection(parent_sku)
    collection_name = collection_context.name if collection_context else parent_sku.collection
    collection_group = collection_context.group if collection_context else None
    collection_subgroup = collection_context.subgroup if collection_context else None
    
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
    variant_title = generate_variant_title(base_title, finish_name)
    variant_description = generate_variant_description(
        base_description=base_description,
        finish_name=finish_name,
        collection_name=collection_name,
        collection_group=collection_group,
        collection_subgroup=collection_subgroup,
        platform=platform,
    )
    
    # Build meta
    meta = {
        "master_sku": parent_sku.master_sku,
        "option_sku": variant.option_sku,
        "finish": finish_name,
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
        # Also generate variant-specific short title
        short_title = candidate.google_short_title
        if finish_name.lower() not in short_title.lower():
            # Append finish to short title if not present
            if len(short_title) + len(finish_name) + 3 <= 70:
                short_title = f"{short_title}, {finish_name}"
        
        return {
            "offerId": variant.gmc_id,
            "title": variant_title,
            "short_title": short_title,
            "description": variant_description,
            "channel": "online",
            "contentLanguage": "en",
            "targetCountry": "US",
            "_meta": meta,
            "_previous": previous,
        }
    
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
    
    return patches
