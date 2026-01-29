from pathlib import Path

from feedops.db.schema import get_connection, init_db


def test_init_db_creates_variant_index_tables(tmp_path: Path) -> None:
    db_path = tmp_path / "feedops.db"
    init_db(db_path)
    conn = get_connection(db_path)
    try:
        tables = {
            row[0]
            for row in conn.execute(
                "SELECT name FROM sqlite_master WHERE type='table'"
            ).fetchall()
        }
    finally:
        conn.close()
    assert "variant_index" in tables
    assert "catalog_ingest_state" in tables
