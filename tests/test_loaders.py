# tests/test_loaders.py
import pytest
from pathlib import Path
from feedops.loaders.catalog import load_catalog, rename_duplicate_columns, get_parent_sku


def test_rename_duplicate_columns(sample_catalog_path):
    """Duplicate columns are renamed by position."""
    import pandas as pd
    df = pd.read_csv(sample_catalog_path)
    df = rename_duplicate_columns(df)
    assert "product_length" in df.columns
    assert "shipping_length" in df.columns
    assert "product_weight" in df.columns
    assert "shipping_weight" in df.columns


def test_load_catalog_returns_dataframe(sample_catalog_path):
    """load_catalog returns pandas DataFrame."""
    df = load_catalog(sample_catalog_path)
    assert len(df) > 0
    assert "master_sku" in df.columns
    assert "gmc_id" in df.columns


def test_get_parent_sku_extracts_variants(sample_catalog_path):
    """get_parent_sku returns ParentSKU with all variants."""
    df = load_catalog(sample_catalog_path)
    parent = get_parent_sku(df, "101")
    assert parent is not None
    assert parent.master_sku == "101"
    assert len(parent.variants) == 2
    assert parent.variants[0].finish_code == "ABR"
    assert parent.variants[1].finish_code == "ABZ"


def test_get_parent_sku_returns_none_for_missing(sample_catalog_path):
    """get_parent_sku returns None for non-existent SKU."""
    df = load_catalog(sample_catalog_path)
    parent = get_parent_sku(df, "NONEXISTENT-SKU")
    assert parent is None


def test_get_parent_sku_parses_gmcid(sample_catalog_path):
    """Variants have Shopify IDs extracted from GMCID."""
    df = load_catalog(sample_catalog_path)
    parent = get_parent_sku(df, "101")
    variant = parent.variants[0]
    assert variant.shopify_product_id == "4542872518788"
    assert variant.shopify_variant_id == "32118222192772"
