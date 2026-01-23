"""Report generation for SKU optimization results."""
from datetime import datetime
from feedops.models import ParentSKU, Candidate


def generate_report(
    parent_sku: ParentSKU,
    candidate: Candidate,
    verification_errors: list[str],
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

    report = f"""# Optimization Report: {parent_sku.master_sku}

**Generated:** {datetime.now().isoformat()}
**Status:** {score.approval_status.upper()}

---

## Current Content

**Title:** {parent_sku.current_title}

**Description:** {parent_sku.current_description[:200]}...

---

## Optimized Content

**Title ({len(candidate.title)} chars):**
```
{candidate.title}
```

**Description ({len(candidate.description)} chars):**
```
{candidate.description}
```

---

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

    report += f"""
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
) -> dict:
    """Generate Merchant Center patch preview JSON.

    Args:
        parent_sku: The parent SKU being updated.
        candidate: The optimized candidate.

    Returns:
        Dict in Content API patch format.
    """
    # Use first variant's GMCID as offerId
    offer_id = parent_sku.variants[0].gmc_id if parent_sku.variants else parent_sku.master_sku

    return {
        "offerId": offer_id,
        "title": candidate.title,
        "description": candidate.description,
        "channel": "online",
        "contentLanguage": "en",
        "targetCountry": "US",
        "_meta": {
            "master_sku": parent_sku.master_sku,
            "generated_at": datetime.now().isoformat(),
            "quality_score": candidate.final_score.composite,
            "approval_status": candidate.final_score.approval_status,
        },
        "_previous": {
            "title": parent_sku.current_title,
            "description": parent_sku.current_description,
        },
    }
