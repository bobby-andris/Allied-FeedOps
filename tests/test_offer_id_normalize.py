"""Unit tests for feedops.utils.offer_id normalization functions.

Tests cover ENTM-01: shared offer ID normalization utility.

Canonical DB form: shopify_us_{product_id}_{variant_id} (lowercase)
GMC publish form:  shopify_US_{product_id}_{variant_id} (uppercase US)
"""
import pytest

from feedops.utils.offer_id import normalize_offer_id, to_gmc_format


class TestNormalizeOfferId:
    """Tests for normalize_offer_id() — converts to canonical lowercase DB format."""

    def test_normalizes_uppercase_us_to_lowercase(self):
        """Google Ads returns uppercase shopify_US_; DB stores lowercase shopify_us_."""
        assert normalize_offer_id("shopify_US_123_456") == "shopify_us_123_456"

    def test_noop_on_already_lowercase(self):
        """Already-lowercase IDs pass through unchanged (idempotent)."""
        assert normalize_offer_id("shopify_us_123_456") == "shopify_us_123_456"

    def test_empty_string_returns_empty_string(self):
        """Empty string input returns empty string (safe, no exception)."""
        assert normalize_offer_id("") == ""

    def test_none_returns_none(self):
        """None input returns None (safe, no exception)."""
        assert normalize_offer_id(None) is None

    def test_mixed_case_fully_lowercased(self):
        """Any mixed-case variant is fully lowercased."""
        assert normalize_offer_id("SHOPIFY_US_999_888") == "shopify_us_999_888"

    def test_preserves_numeric_ids(self):
        """Numeric product/variant IDs in the offer ID are preserved."""
        assert normalize_offer_id("shopify_US_4539975336068_40123456789") == (
            "shopify_us_4539975336068_40123456789"
        )


class TestToGmcFormat:
    """Tests for to_gmc_format() — converts to uppercase GMC publish format."""

    def test_converts_lowercase_to_gmc_uppercase(self):
        """DB-format lowercase ID is converted to GMC uppercase."""
        assert to_gmc_format("shopify_us_123_456") == "shopify_US_123_456"

    def test_noop_on_already_uppercase(self):
        """Already-uppercase GMC format is idempotent."""
        assert to_gmc_format("shopify_US_123_456") == "shopify_US_123_456"

    def test_empty_string_returns_empty_string(self):
        """Empty string input returns empty string (safe, no exception)."""
        assert to_gmc_format("") == ""

    def test_none_returns_none(self):
        """None input returns None (safe, no exception)."""
        assert to_gmc_format(None) is None

    def test_preserves_numeric_ids(self):
        """Numeric product/variant IDs in the offer ID are preserved."""
        assert to_gmc_format("shopify_us_4539975336068_40123456789") == (
            "shopify_US_4539975336068_40123456789"
        )

    def test_roundtrip_normalize_then_gmc(self):
        """normalize_offer_id followed by to_gmc_format yields GMC format."""
        raw = "shopify_US_123_456"
        canonical = normalize_offer_id(raw)
        gmc = to_gmc_format(canonical)
        assert gmc == "shopify_US_123_456"

    def test_roundtrip_gmc_then_normalize(self):
        """to_gmc_format followed by normalize_offer_id yields canonical lowercase."""
        gmc = "shopify_US_123_456"
        canonical = normalize_offer_id(to_gmc_format(gmc))
        assert canonical == "shopify_us_123_456"
