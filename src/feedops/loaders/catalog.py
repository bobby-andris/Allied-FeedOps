"""Product Catalog CSV loader with duplicate column handling."""
from pathlib import Path
from decimal import Decimal
import pandas as pd

from feedops.config.columns import (
    CSV_COLUMNS,
    POSITIONAL_RENAMES,
    PARENT_SKU_FIELDS,
    VARIANT_FIELDS,
)
from feedops.models import ParentSKU, Variant


def rename_duplicate_columns(df: pd.DataFrame) -> pd.DataFrame:
    """Rename duplicate columns using positional mapping.

    The CSV has duplicate column names (Length, Height, Width, Weight).
    This function renames them based on their position.
    """
    columns = list(df.columns)
    for pos, new_name in POSITIONAL_RENAMES.items():
        if pos < len(columns):
            columns[pos] = new_name
    df.columns = columns
    return df


def normalize_column_names(df: pd.DataFrame) -> pd.DataFrame:
    """Normalize column names using CSV_COLUMNS mapping."""
    rename_map = {}
    for col in df.columns:
        if col in CSV_COLUMNS:
            rename_map[col] = CSV_COLUMNS[col]
    return df.rename(columns=rename_map)


def load_catalog(path: Path | str) -> pd.DataFrame:
    """Load Product Catalog CSV with proper column handling.

    Args:
        path: Path to the Product Catalog CSV file.

    Returns:
        DataFrame with normalized column names.
    """
    path = Path(path)
    if not path.exists():
        raise FileNotFoundError(f"Catalog not found: {path}")

    df = pd.read_csv(path, dtype=str, keep_default_na=False)
    df = rename_duplicate_columns(df)
    df = normalize_column_names(df)
    return df


def get_parent_sku(df: pd.DataFrame, master_sku: str) -> ParentSKU | None:
    """Extract ParentSKU with all variants from catalog.

    Args:
        df: Loaded catalog DataFrame.
        master_sku: The MasterSKU value to look up.

    Returns:
        ParentSKU with variants, or None if not found.
    """
    rows = df[df["master_sku"] == master_sku]
    if rows.empty:
        return None

    # Build variants from all rows
    variants = []
    for _, row in rows.iterrows():
        variant_data = {}
        for field in VARIANT_FIELDS:
            if field in row.index and row[field]:
                value = row[field]
                # Convert numeric fields
                if field in ("position",):
                    try:
                        value = int(value)
                    except (ValueError, TypeError):
                        value = 0
                elif field.endswith(("_length", "_height", "_width", "_weight", "projection")):
                    try:
                        value = float(value)
                    except (ValueError, TypeError):
                        value = None
                elif field.endswith("_price"):
                    try:
                        value = Decimal(value.replace("$", "").replace(",", ""))
                    except (ValueError, TypeError):
                        value = None
                variant_data[field] = value

        if variant_data.get("option_sku") and variant_data.get("gmc_id"):
            variants.append(Variant(**variant_data))

    if not variants:
        return None

    # Build ParentSKU from first row (shared attributes)
    first_row = rows.iloc[0]
    parent_data = {"variants": variants}
    for field in PARENT_SKU_FIELDS:
        if field in first_row.index and first_row[field]:
            value = first_row[field]
            # Convert numeric fields
            if field in ("center_to_center", "diameter", "mirror_height", "mirror_width", "thickness", "weight_capacity"):
                try:
                    value = float(value)
                except (ValueError, TypeError):
                    value = None
            elif field == "assembly_required":
                value = value.lower() in ("true", "yes", "1")
            parent_data[field] = value

    return ParentSKU(**parent_data)


def list_master_skus(df: pd.DataFrame) -> list[str]:
    """List all unique MasterSKU values in catalog.

    Args:
        df: Loaded catalog DataFrame.

    Returns:
        Sorted list of unique MasterSKU values.
    """
    return sorted(df["master_sku"].unique().tolist())
