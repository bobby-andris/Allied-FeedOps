"""Variant model representing a single product variant."""

from __future__ import annotations

import re
from decimal import Decimal

from pydantic import BaseModel, computed_field

GMCID_PATTERN = re.compile(r"^shopify_US_(\d+)_(\d+)$")


def parse_gmcid(gmc_id: str) -> tuple[str | None, str | None]:
    """Extract Shopify product and variant IDs from GMCID.

    GMCID format: shopify_US_{ProductID}_{VariantID}

    Returns:
        Tuple of (product_id, variant_id) or (None, None) if invalid.
    """
    if not gmc_id:
        return None, None
    match = GMCID_PATTERN.match(gmc_id)
    if not match:
        return None, None
    return match.group(1), match.group(2)


class Variant(BaseModel):
    """A single product variant (finish/option combination)."""

    # Identifiers
    option_sku: str
    finish: str
    finish_code: str
    gmc_id: str
    upc: str | None = None
    gtin: str | None = None
    amazon_asin: str | None = None
    position: int = 0

    # Pricing
    list_price: Decimal | None = None
    wholesale_price: Decimal | None = None
    map_price: Decimal | None = None

    # Product dimensions
    product_length: float | None = None
    product_height: float | None = None
    product_width: float | None = None
    projection: float | None = None
    product_weight: float | None = None

    # Shipping dimensions
    shipping_length: float | None = None
    shipping_height: float | None = None
    shipping_width: float | None = None
    shipping_weight: float | None = None

    # Images
    main_image: str | None = None
    main_image_url: str | None = None
    alt_image_1: str | None = None
    alt_image_2: str | None = None
    alt_image_3: str | None = None
    alt_image_4: str | None = None

    @computed_field
    @property
    def shopify_product_id(self) -> str | None:
        """Extract Shopify product ID from GMCID."""
        product_id, _ = parse_gmcid(self.gmc_id)
        return product_id

    @computed_field
    @property
    def shopify_variant_id(self) -> str | None:
        """Extract Shopify variant ID from GMCID."""
        _, variant_id = parse_gmcid(self.gmc_id)
        return variant_id

    @computed_field
    @property
    def item_id(self) -> str:
        """Merchant Center item_id (same as gmc_id)."""
        return self.gmc_id

    @computed_field
    @property
    def item_group_id(self) -> str | None:
        """Merchant Center item_group_id (Shopify product ID)."""
        return self.shopify_product_id
