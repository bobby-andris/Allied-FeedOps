import csv
from pathlib import Path

from feedops.db.schema import get_connection, init_db
from feedops.db.variant_index import build_variant_index


def test_build_variant_index_writes_rows(tmp_path: Path) -> None:
    db_path = tmp_path / "feedops.db"
    init_db(db_path)

    catalog_path = tmp_path / "Product Catalog.csv"
    with catalog_path.open("w", newline="") as f:
        writer = csv.DictWriter(
            f,
            fieldnames=[
                "MasterSKU",
                "OPTION SKU",
                "CoreSKU",
                "GMCID",
                "Category",
                "Collection",
                "Material",
            ],
        )
        writer.writeheader()
        writer.writerow(
            {
                "MasterSKU": "MB-20",
                "OPTION SKU": "MB-20-ABR",
                "CoreSKU": "MB-20",
                "GMCID": "shopify_US_123_456",
                "Category": "Robe Hooks",
                "Collection": "Malibu",
                "Material": "Brass",
            }
        )
        writer.writerow(
            {
                "MasterSKU": "MB-20",
                "OPTION SKU": "MB-20-PC",
                "CoreSKU": "MB-20",
                "GMCID": "shopify_US_123_789",
                "Category": "Robe Hooks",
                "Collection": "Malibu",
                "Material": "Brass",
            }
        )

    build_variant_index(db_path, catalog_path, limit_master_skus=["MB-20"])

    conn = get_connection(db_path)
    try:
        count = conn.execute(
            "SELECT COUNT(*) AS n FROM variant_index WHERE master_sku = ?",
            ("MB-20",),
        ).fetchone()["n"]
        assert count == 2
        row = conn.execute(
            "SELECT shopify_product_id, shopify_variant_id FROM variant_index WHERE gmc_id = ?",
            ("shopify_US_123_456",),
        ).fetchone()
    finally:
        conn.close()

    assert row["shopify_product_id"] == "123"
    assert row["shopify_variant_id"] == "456"

