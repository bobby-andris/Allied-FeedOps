"""Unit tests for multi-SKU detection logic."""

import pytest
from feedops.api.multi_sku_detection import (
    extract_product_id,
    extract_spec_difference,
    MultiSkuFamily,
)


class TestExtractProductId:
    """Tests for product ID extraction from GMC offer IDs."""

    def test_valid_offer_id(self):
        """Test extracting product_id from valid GMC offer ID."""
        offer_id = "shopify_US_4539975336068_32103134298244"
        result = extract_product_id(offer_id)
        assert result == "4539975336068"

    def test_lowercase_shopify(self):
        """Test extracting product_id when 'shopify' is lowercase."""
        offer_id = "shopify_us_4539975336068_32103134298244"
        result = extract_product_id(offer_id)
        assert result == "4539975336068"

    def test_invalid_format_too_few_parts(self):
        """Test invalid offer ID with too few parts."""
        offer_id = "shopify_US_4539975336068"
        result = extract_product_id(offer_id)
        assert result is None

    def test_invalid_format_empty(self):
        """Test empty offer ID."""
        offer_id = ""
        result = extract_product_id(offer_id)
        assert result is None

    def test_different_product_id(self):
        """Test different product ID extraction."""
        offer_id = "shopify_US_1234567890123_98765432109876"
        result = extract_product_id(offer_id)
        assert result == "1234567890123"


class TestExtractSpecDifference:
    """Tests for specification difference extraction."""

    def test_dmf_2x_vs_5x(self):
        """Test spec extraction for DMF-2/2X vs DMF-2/5X."""
        base_sku = "DMF-2/2X"
        variant_sku = "DMF-2/5X"
        base_spec, variant_spec = extract_spec_difference(base_sku, variant_sku)
        assert base_spec == "2X"
        assert variant_spec == "5X"

    def test_dmf_2x_vs_3x(self):
        """Test spec extraction for DMF-2/2X vs DMF-2/3X."""
        base_sku = "DMF-2/2X"
        variant_sku = "DMF-2/3X"
        base_spec, variant_spec = extract_spec_difference(base_sku, variant_sku)
        assert base_spec == "2X"
        assert variant_spec == "3X"

    def test_wp_gallon_difference(self):
        """Test spec extraction for gallon size differences."""
        base_sku = "WP-2/16-GAL"
        variant_sku = "WP-2/22-GAL"
        base_spec, variant_spec = extract_spec_difference(base_sku, variant_sku)
        assert base_spec == "16"
        assert variant_spec == "22"

    def test_numeric_only_difference(self):
        """Test spec extraction with numeric-only differences."""
        base_sku = "920-6"
        variant_sku = "920D-6"
        base_spec, variant_spec = extract_spec_difference(base_sku, variant_sku)
        # Should find first differing number
        assert base_spec == "920"
        assert variant_spec == "920"  # Same prefix, but D makes it different

    def test_hyphen_format(self):
        """Test spec extraction with hyphen format."""
        base_sku = "DMF-2-2X"
        variant_sku = "DMF-2-5X"
        base_spec, variant_spec = extract_spec_difference(base_sku, variant_sku)
        assert base_spec == "2X"
        assert variant_spec == "5X"

    def test_no_difference_found(self):
        """Test when no numeric difference is found."""
        base_sku = "SIMPLE-SKU"
        variant_sku = "SIMPLE-SKU"
        base_spec, variant_spec = extract_spec_difference(base_sku, variant_sku)
        # Should fall back to full SKU names
        assert base_spec == "SIMPLE-SKU"
        assert variant_spec == "SIMPLE-SKU"

    def test_decimal_specs(self):
        """Test spec extraction with decimal values."""
        base_sku = "ABC-1.5X"
        variant_sku = "ABC-2.5X"
        base_spec, variant_spec = extract_spec_difference(base_sku, variant_sku)
        assert base_spec == "1.5X"
        assert variant_spec == "2.5X"


class TestMultiSkuFamily:
    """Tests for MultiSkuFamily dataclass."""

    def test_dataclass_creation(self):
        """Test creating a MultiSkuFamily instance."""
        family = MultiSkuFamily(
            product_id="4539975336068",
            master_skus=["DMF-2/2X", "DMF-2/3X", "DMF-2/4X", "DMF-2/5X"],
            base_sku="DMF-2/2X",
            variant_skus=["DMF-2/3X", "DMF-2/4X", "DMF-2/5X"],
        )

        assert family.product_id == "4539975336068"
        assert len(family.master_skus) == 4
        assert family.base_sku == "DMF-2/2X"
        assert len(family.variant_skus) == 3

    def test_base_sku_is_first(self):
        """Test that base_sku is typically the first alphabetically."""
        family = MultiSkuFamily(
            product_id="test",
            master_skus=["DMF-2/2X", "DMF-2/3X"],
            base_sku="DMF-2/2X",
            variant_skus=["DMF-2/3X"],
        )

        assert family.base_sku == family.master_skus[0]


# Integration tests that require Supabase would go here
# These would test:
# - get_related_master_skus()
# - detect_multi_sku_families()
# - is_multi_sku_product()
# - get_base_sku()
#
# Example structure:
# @pytest.mark.integration
# def test_get_related_master_skus(supabase_client):
#     """Test getting related master SKUs from database."""
#     skus = get_related_master_skus(supabase_client, "DMF-2/2X")
#     assert "DMF-2/2X" in skus
#     assert "DMF-2/3X" in skus
#     assert len(skus) > 1
