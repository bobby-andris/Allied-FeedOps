# tests/test_config.py
from feedops.config.columns import CSV_COLUMNS, POSITIONAL_RENAMES


def test_csv_columns_has_all_fields():
    """CSV_COLUMNS maps all 56 columns from Product Catalog CSV."""
    assert len(CSV_COLUMNS) >= 48  # At least the unique columns
    assert "MasterSKU" in CSV_COLUMNS
    assert "OPTION SKU" in CSV_COLUMNS
    assert "GMCID" in CSV_COLUMNS


def test_positional_renames_handles_duplicates():
    """POSITIONAL_RENAMES maps duplicate column positions."""
    # First occurrence (product dimensions)
    assert POSITIONAL_RENAMES[23] == "product_length"
    assert POSITIONAL_RENAMES[24] == "product_height"
    assert POSITIONAL_RENAMES[25] == "product_width"
    assert POSITIONAL_RENAMES[27] == "product_weight"
    # Second occurrence (shipping dimensions)
    assert POSITIONAL_RENAMES[28] == "shipping_length"
    assert POSITIONAL_RENAMES[29] == "shipping_height"
    assert POSITIONAL_RENAMES[30] == "shipping_width"
    assert POSITIONAL_RENAMES[31] == "shipping_weight"
