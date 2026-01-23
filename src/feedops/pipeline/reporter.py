"""Report generation for SKU optimization results."""
from datetime import datetime
from feedops.models import ParentSKU, Candidate


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
