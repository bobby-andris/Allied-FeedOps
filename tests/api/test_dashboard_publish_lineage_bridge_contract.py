from pathlib import Path


SKU_ROUTE = Path("dashboard/src/app/api/publish/sku/route.ts")
BATCH_ROUTE = Path("dashboard/src/app/api/publish/batch/route.ts")
LINEAGE_HELPER = Path("dashboard/src/lib/publishing/change-packages.ts")
R4_MIGRATION = Path("supabase/migrations/20260228203000_add_change_packages_and_generation_outcome_links.sql")


def _read(path: Path) -> str:
    return path.read_text(encoding="utf-8")


def test_publish_routes_attach_r4_lineage_after_publish_event_insert() -> None:
    sku_source = _read(SKU_ROUTE)
    batch_source = _read(BATCH_ROUTE)

    assert "attachPublishEventLineage" in sku_source
    assert "attachPublishEventLineage" in batch_source
    assert ".select(selectColumns)" in sku_source
    assert ".select(selectColumns)" in batch_source


def test_r4_helper_writes_change_package_and_generation_links() -> None:
    source = _read(LINEAGE_HELPER)

    assert ".from('change_packages')" in source
    assert ".from('change_package_events')" in source
    assert ".from('change_package_items')" in source
    assert ".from('generation_outcome_links')" in source
    assert ".from('generation_effect_windows')" in source
    assert ".from('publish_events')" in source


def test_r4_migration_defines_change_package_bridge_tables() -> None:
    migration = _read(R4_MIGRATION)

    assert "CREATE TABLE IF NOT EXISTS change_packages" in migration
    assert "CREATE TABLE IF NOT EXISTS change_package_events" in migration
    assert "CREATE TABLE IF NOT EXISTS change_package_items" in migration
    assert "CREATE TABLE IF NOT EXISTS generation_outcome_links" in migration
    assert "CREATE TABLE IF NOT EXISTS generation_effect_windows" in migration
    assert "ALTER TABLE publish_events" in migration
    assert "ADD COLUMN IF NOT EXISTS change_package_id" in migration
