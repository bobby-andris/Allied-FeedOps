"""Offer ID normalization utility.

Centralizes the case-normalization pattern from google_ads_search_terms.py
into a single importable module for consistent handling across all data codepaths.

Canonical DB form: shopify_us_{product_id}_{variant_id}  (lowercase — matches 72K rows in variant_index)
GMC publish form:  shopify_US_{product_id}_{variant_id}  (uppercase US — required by Google Merchant Center)

Rules:
- Normalize on INGESTION — every data stream that brings in an offer ID normalizes
  to lowercase before storing or looking up in the database.
- Use to_gmc_format() ONLY at publish boundary (Google Sheets, GMC API).
- Never store uppercase form in the database.
"""
from __future__ import annotations


def normalize_offer_id(offer_id: str | None) -> str | None:
    """Normalize offer ID to canonical lowercase form (DB format).

    Canonical: shopify_us_{product_id}_{variant_id}
    Google Ads returns: shopify_US_{product_id}_{variant_id}
    DB stores: shopify_us_{product_id}_{variant_id} (72K rows in variant_index)

    Args:
        offer_id: Raw offer ID string, possibly uppercase from Google Ads API.
                  May be None or empty string.

    Returns:
        Lowercase canonical form, or the original value if None/empty.
    """
    if not offer_id:
        return offer_id
    return offer_id.lower()


def to_gmc_format(offer_id: str | None) -> str | None:
    """Convert offer ID to GMC publish format (uppercase US).

    Only use at publish boundary (Google Sheets, GMC API).
    Never use for DB lookups or storage — the database stores lowercase.

    Args:
        offer_id: Canonical lowercase offer ID from the database.
                  May be None or empty string.

    Returns:
        GMC format with uppercase 'shopify_US_' prefix, or the original value
        if None/empty.
    """
    if not offer_id:
        return offer_id
    return offer_id.replace("shopify_us_", "shopify_US_")
