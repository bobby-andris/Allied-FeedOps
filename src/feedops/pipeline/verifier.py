"""Claim verification against source data."""
import re

from feedops.models import ParentSKU, Candidate, Claim, Score
from feedops.pipeline.claim_extraction import extract_claims, dedupe_claims

# Enrichment fields that are computed at runtime and should be trusted.
# These are injected into the evidence table by ProductEnrichment.to_evidence_rows()
# but are not attributes of ParentSKU or Variant models.
_ENRICHMENT_FIELDS = {
    "finish_variety",
    "statement_finishes",
    "collection_context",
    "collection_subgroup",
    "competitive_edge",
    "design_style",
    "feature_title_keywords",
    "feature_benefits",
    "key_differentiators",
    "design_intent_keywords",
}


def get_source_value(parent_sku: ParentSKU, field_name: str) -> str | None:
    """Get value from ParentSKU or its first variant by field name.

    Args:
        parent_sku: The parent SKU to look up.
        field_name: The field name to retrieve.

    Returns:
        String value or None if field doesn't exist.
    """
    # Handle enrichment fields - these are computed at runtime and trusted
    if field_name in _ENRICHMENT_FIELDS:
        return "[enrichment]"

    # Handle computed fields
    if field_name == "available_finishes" and parent_sku.variants:
        return ", ".join(v.finish for v in parent_sku.variants)

    # Try ParentSKU first
    if hasattr(parent_sku, field_name):
        value = getattr(parent_sku, field_name)
        if value is not None:
            return str(value)

    # Try first variant
    if parent_sku.variants:
        variant = parent_sku.variants[0]
        if hasattr(variant, field_name):
            value = getattr(variant, field_name)
            if value is not None:
                return str(value)

    return None


def verify_claim(claim: Claim, parent_sku: ParentSKU) -> Claim:
    """Verify a single claim against source data.

    Args:
        claim: The claim to verify.
        parent_sku: The source data.

    Returns:
        Updated claim with verified status and rejection reason if applicable.
    """
    # Trust enrichment fields - these are computed at runtime from valid data
    if claim.source_field in _ENRICHMENT_FIELDS:
        return Claim(
            claim=claim.claim,
            source_field=claim.source_field,
            source_value=claim.source_value,
            verified=True,
        )

    actual_value = get_source_value(parent_sku, claim.source_field)

    if actual_value is None:
        return Claim(
            claim=claim.claim,
            source_field=claim.source_field,
            source_value=claim.source_value,
            verified=False,
            rejection_reason=f"Field '{claim.source_field}' not found in source data",
        )

    # Normalize for comparison (case-insensitive, trim whitespace)
    claimed = claim.source_value.strip().lower()
    actual = actual_value.strip().lower()

    if claim.source_field == "material":
        if claimed == actual:
            return Claim(
                claim=claim.claim,
                source_field=claim.source_field,
                source_value=claim.source_value,
                verified=True,
            )
        return Claim(
            claim=claim.claim,
            source_field=claim.source_field,
            source_value=claim.source_value,
            verified=False,
            rejection_reason=f"Claimed '{claim.source_value}' but actual value is '{actual_value}'",
        )

    numeric_fields = {
        "center_to_center",
        "diameter",
        "mirror_height",
        "mirror_width",
        "thickness",
        "weight_capacity",
        "product_length",
        "product_height",
        "product_width",
        "projection",
        "product_weight",
    }

    if claim.source_field in numeric_fields:
        num_re = re.compile(r"\d+(?:\.\d+)?")
        claimed_m = num_re.search(claimed)
        actual_m = num_re.search(actual)
        if claimed_m and actual_m:
            try:
                claimed_num = float(claimed_m.group(0))
                actual_num = float(actual_m.group(0))
                if abs(claimed_num - actual_num) < 1e-6:
                    return Claim(
                        claim=claim.claim,
                        source_field=claim.source_field,
                        source_value=claim.source_value,
                        verified=True,
                    )
            except ValueError:
                pass

    if claimed == actual or claimed in actual or actual in claimed:
        return Claim(
            claim=claim.claim,
            source_field=claim.source_field,
            source_value=claim.source_value,
            verified=True,
        )

    return Claim(
        claim=claim.claim,
        source_field=claim.source_field,
        source_value=claim.source_value,
        verified=False,
        rejection_reason=f"Claimed '{claim.source_value}' but actual value is '{actual_value}'",
    )


def verify_claims(candidate: Candidate, parent_sku: ParentSKU) -> tuple[Candidate, list[str]]:
    """Verify all claims in a candidate against source data.

    Args:
        candidate: The candidate with claims to verify.
        parent_sku: The source data.

    Returns:
        Tuple of (updated candidate, list of error messages).
    """
    verified_claims = []
    errors = []

    extracted_claims = extract_claims(candidate, parent_sku)
    merged_claims = dedupe_claims(list(candidate.claims) + extracted_claims)

    for claim in merged_claims:
        verified = verify_claim(claim, parent_sku)
        verified_claims.append(verified)
        if not verified.verified:
            errors.append(f"Claim rejected: '{claim.claim}' - {verified.rejection_reason}")

    # Calculate verified factual_accuracy score
    if verified_claims:
        verified_count = sum(1 for c in verified_claims if c.verified)
        accuracy_score = round(verified_count / len(verified_claims) * 10)
    else:
        accuracy_score = 10  # No claims = no violations

    verified_score = Score(
        hook_quality=candidate.self_score.hook_quality,
        product_specificity=candidate.self_score.product_specificity,
        competitive_diff=candidate.self_score.competitive_diff,
        keyword_integration=candidate.self_score.keyword_integration,
        customer_scenario=candidate.self_score.customer_scenario,
        emotional_resonance=candidate.self_score.emotional_resonance,
        factual_accuracy=accuracy_score,
        platform_compliance=candidate.self_score.platform_compliance,
        finish_integration=candidate.self_score.finish_integration,
        variety_score=candidate.self_score.variety_score,
    )

    verified_candidate = candidate.model_copy(
        update={
            "claims": verified_claims,
            "verified_score": verified_score,
        }
    )

    return verified_candidate, errors
