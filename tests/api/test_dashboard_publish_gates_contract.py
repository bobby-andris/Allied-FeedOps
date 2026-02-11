from pathlib import Path


SKU_ROUTE = Path("dashboard/src/app/api/publish/sku/route.ts")
BATCH_ROUTE = Path("dashboard/src/app/api/publish/batch/route.ts")


def _read(path: Path) -> str:
    return path.read_text(encoding="utf-8")


def test_sku_publish_route_uses_strict_shopify_validation_without_google_fallback() -> None:
    source = _read(SKU_ROUTE)

    assert "validateContentForPublishing(master_sku, 'shopify')" in source
    assert "Try Google content as fallback" not in source


def test_publish_routes_surface_structured_validation_issues() -> None:
    sku_source = _read(SKU_ROUTE)
    batch_source = _read(BATCH_ROUTE)

    assert "validation_issues" in sku_source
    assert "validation_issues" in batch_source
    assert "batch_publish_google_validation_failed" in batch_source
    assert "batch_publish_shopify_validation_failed" in batch_source
    assert "validateContentForPublishing(sku, 'google')" in batch_source
    assert "validateContentForPublishing(sku, 'shopify')" in batch_source
