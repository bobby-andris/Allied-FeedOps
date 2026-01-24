"""Claim verification against source data."""
import re

from feedops.models import ParentSKU, Candidate, Claim, Score


def get_source_value(parent_sku: ParentSKU, field_name: str) -> str | None:
    """Get value from ParentSKU or its first variant by field name.

    Args:
        parent_sku: The parent SKU to look up.
        field_name: The field name to retrieve.

    Returns:
        String value or None if field doesn't exist.
    """
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

    for claim in candidate.claims:
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
        specificity=candidate.self_score.specificity,
        benefit_coverage=candidate.self_score.benefit_coverage,
        keyword_inclusion=candidate.self_score.keyword_inclusion,
        format_adherence=candidate.self_score.format_adherence,
        brand_voice=candidate.self_score.brand_voice,
        factual_accuracy=accuracy_score,
    )

    verified_candidate = Candidate(
        google_title=candidate.google_title,
        google_short_title=candidate.google_short_title,
        google_description=candidate.google_description,
        bing_title=candidate.bing_title,
        bing_description=candidate.bing_description,
        shopify_title=candidate.shopify_title,
        shopify_description=candidate.shopify_description,
        claims=verified_claims,
        self_score=candidate.self_score,
        verified_score=verified_score,
    )

    return verified_candidate, errors
