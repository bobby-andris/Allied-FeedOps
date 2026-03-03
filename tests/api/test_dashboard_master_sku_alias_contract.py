from pathlib import Path


GENERATE_ROUTE = Path("dashboard/src/app/api/sku-selection/generate/route.ts")
REGENERATE_ROUTE = Path("dashboard/src/app/api/regenerate/route.ts")
EXPAND_VARIANTS = Path("dashboard/src/lib/publishing/expand-variants.ts")
BATCH_REGENERATE_ROUTE = Path("dashboard/src/app/api/regenerate/batch/route.ts")
REGENERATE_REVERT_ROUTE = Path("dashboard/src/app/api/regenerate/revert/route.ts")
PUBLISH_SKU_ROUTE = Path("dashboard/src/app/api/publish/sku/route.ts")
PUBLISH_GOOGLE_ROUTE = Path("dashboard/src/app/api/publish/google/route.ts")
PUBLISH_SHOPIFY_ROUTE = Path("dashboard/src/app/api/publish/shopify/route.ts")


def _read(path: Path) -> str:
    return path.read_text(encoding="utf-8")


def test_generate_routes_canonicalize_master_skus_before_pipeline_calls() -> None:
    generate_source = _read(GENERATE_ROUTE)

    # generate/route.ts now calls /hybrid-generate directly (hybrid route was merged in)
    assert "resolveCanonicalMasterSkuList" in generate_source


def test_regenerate_route_canonicalizes_master_sku_for_queries_and_pipeline() -> None:
    source = _read(REGENERATE_ROUTE)

    assert "resolveCanonicalMasterSku" in source
    assert "canonicalMasterSku" in source


def test_publish_variant_expansion_resolves_canonical_master_sku() -> None:
    source = _read(EXPAND_VARIANTS)

    assert "resolveCanonicalMasterSku" in source
    assert "canonicalMasterSku" in source


def test_batch_regenerate_route_canonicalizes_master_sku_lists() -> None:
    source = _read(BATCH_REGENERATE_ROUTE)
    assert "resolveCanonicalMasterSkuList" in source


def test_regenerate_revert_route_canonicalizes_master_sku() -> None:
    source = _read(REGENERATE_REVERT_ROUTE)
    assert "resolveCanonicalMasterSku" in source
    assert "canonicalMasterSku" in source


def test_publish_routes_canonicalize_master_sku_inputs() -> None:
    sku_publish_source = _read(PUBLISH_SKU_ROUTE)
    google_publish_source = _read(PUBLISH_GOOGLE_ROUTE)
    shopify_publish_source = _read(PUBLISH_SHOPIFY_ROUTE)

    assert "resolveCanonicalMasterSku" in sku_publish_source
    assert "canonicalMasterSku" in sku_publish_source

    assert "resolveCanonicalMasterSku" in google_publish_source
    assert "canonicalMasterSku" in google_publish_source

    assert "resolveCanonicalMasterSku" in shopify_publish_source
    assert "canonicalMasterSku" in shopify_publish_source
