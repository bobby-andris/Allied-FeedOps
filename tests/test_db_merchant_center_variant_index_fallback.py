from datetime import datetime, timezone


def test_get_cached_merchant_center_items_falls_back_to_variant_index(monkeypatch, tmp_path):
    from feedops.db.schema import get_cached_merchant_center_items, get_connection, init_db

    db_path = tmp_path / "feedops.db"
    init_db(db_path)
    monkeypatch.setenv("DATABASE_PATH", str(db_path))

    offer_id = "shopify_US_123_456"
    conn = get_connection(db_path)
    try:
        conn.execute(
            """
            INSERT INTO variant_index (
                gmc_id, master_sku, master_sku_norm, updated_at
            ) VALUES (?, ?, ?, ?)
            """,
            (offer_id, "QN-31/30", "QN-31-30", datetime.now(timezone.utc).isoformat()),
        )
        conn.execute(
            """
            INSERT INTO merchant_center_items (offer_id, payload_json, fetched_at)
            VALUES (?, ?, ?)
            """,
            (
                offer_id,
                '{"offerId":"shopify_US_123_456","title":"Test"}',
                datetime.now(timezone.utc).isoformat(),
            ),
        )
        conn.commit()
    finally:
        conn.close()

    items = get_cached_merchant_center_items("QN-31/30", max_age_hours=24)
    assert [i.get("offerId") for i in items] == [offer_id]

