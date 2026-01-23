"""ParentSKU model aggregating variants."""
from pydantic import BaseModel, computed_field
from feedops.models.variant import Variant


class ParentSKU(BaseModel):
    """Parent product with multiple finish/option variants."""

    # Identifiers
    master_sku: str
    core_sku: str | None = None

    # Classification
    category: str
    collection: str | None = None
    style: str | None = None

    # Current content
    current_title: str
    current_description: str
    bullet_1: str | None = None
    bullet_2: str | None = None
    bullet_3: str | None = None
    bullet_4: str | None = None
    bullet_5: str | None = None
    bullet_6: str | None = None

    # Specifications
    material: str | None = None
    shape: str | None = None
    orientation: str | None = None
    tilting: str | None = None
    mounting_type: str | None = None
    assembly_required: bool | None = None

    # Dimensions (product-level, shared across variants)
    center_to_center: float | None = None
    diameter: float | None = None
    screw_size: str | None = None
    mirror_height: float | None = None
    mirror_width: float | None = None
    thickness: float | None = None
    weight_capacity: float | None = None

    # Documents
    installation_url: str | None = None
    specification_url: str | None = None

    # Included items
    included_items: str | None = None
    item_number: str | None = None

    # Variants
    variants: list[Variant] = []

    @computed_field
    @property
    def item_group_id(self) -> str | None:
        """Merchant Center item_group_id from first variant's Shopify product ID."""
        if not self.variants:
            return None
        return self.variants[0].shopify_product_id

    @computed_field
    @property
    def finish_options(self) -> list[str]:
        """List of available finish codes."""
        return [v.finish_code for v in self.variants]
