import sqlite3
from pathlib import Path

from feedops.pipeline.offerid_preflight import filter_patches_by_offer_id, load_known_offer_ids
from feedops.integrations.google_supplemental import generate_supplemental_feed


def test_load_known_offer_ids_reads_merchant_center_items(tmp_path: Path) -> None:
    db_path = tmp_path / "feedops.db"
    conn = sqlite3.connect(db_path)
    conn.execute(
        "CREATE TABLE merchant_center_items (offer_id TEXT PRIMARY KEY, payload_json TEXT, fetched_at TEXT)"
    )
    conn.execute(
        "INSERT INTO merchant_center_items (offer_id, payload_json, fetched_at) VALUES (?, ?, ?)",
        ("shopify_US_1_1", "{}", "2026-01-01T00:00:00Z"),
    )
    conn.commit()
    conn.close()

    known = load_known_offer_ids(db_path)
    assert known == {"shopify_US_1_1"}


def test_filter_patches_by_offer_id_filters_missing_variants() -> None:
    patches = [
        {
            "offerId": "shopify_US_1_1",
            "title": "a",
            "description": "b",
            "variants": [
                {"offerId": "shopify_US_1_2", "title": "v", "description": "vd"},
                {"offerId": "missing", "title": "x", "description": "y"},
            ],
        }
    ]
    filtered, missing = filter_patches_by_offer_id(patches, {"shopify_US_1_1", "shopify_US_1_2"})
    assert missing == {"missing"}
    assert filtered[0]["offerId"] == "shopify_US_1_1"
    assert [v["offerId"] for v in filtered[0]["variants"]] == ["shopify_US_1_2"]


def test_generate_supplemental_feed_offerid_preflight_filters_missing(tmp_path: Path, monkeypatch) -> None:
    db_path = tmp_path / "feedops.db"
    conn = sqlite3.connect(db_path)
    conn.execute(
        "CREATE TABLE merchant_center_items (offer_id TEXT PRIMARY KEY, payload_json TEXT, fetched_at TEXT)"
    )
    conn.execute(
        "INSERT INTO merchant_center_items (offer_id, payload_json, fetched_at) VALUES (?, ?, ?)",
        ("shopify_US_1_1", "{}", "2026-01-01T00:00:00Z"),
    )
    conn.commit()
    conn.close()

    monkeypatch.setenv("DATABASE_PATH", str(db_path))
    monkeypatch.setenv("FEEDOPS_OFFERID_PREFLIGHT", "true")

    xml = generate_supplemental_feed(
        patches=[{"offerId": "missing", "title": "x", "description": "y"}],
        environment="staging",
        include_variants=False,
    )
    assert "missing" not in xml
