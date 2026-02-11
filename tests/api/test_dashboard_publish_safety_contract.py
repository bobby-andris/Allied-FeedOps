from pathlib import Path


SKU_ROUTE = Path("dashboard/src/app/api/publish/sku/route.ts")
BATCH_ROUTE = Path("dashboard/src/app/api/publish/batch/route.ts")
GUARD_HELPER = Path("dashboard/src/lib/auth/publish-guard.ts")


def _read(path: Path) -> str:
    return path.read_text(encoding="utf-8")


def test_publish_routes_enforce_rbac_guard() -> None:
    sku_source = _read(SKU_ROUTE)
    batch_source = _read(BATCH_ROUTE)

    assert "enforcePublishGuard" in sku_source
    assert "enforcePublishGuard" in batch_source
    assert "if (!guard.allowed)" in sku_source
    assert "if (!guard.allowed)" in batch_source


def test_publish_routes_have_idempotent_no_change_state() -> None:
    sku_source = _read(SKU_ROUTE)
    batch_source = _read(BATCH_ROUTE)

    assert "isIdempotentNoop" in sku_source
    assert "isIdempotentNoop" in batch_source
    assert "state: 'no_change'" in sku_source
    assert "state: 'no_change'" in batch_source
    assert "idempotent: true" in sku_source
    assert "idempotent: true" in batch_source


def test_publish_routes_surface_actionable_codes() -> None:
    sku_source = _read(SKU_ROUTE)
    batch_source = _read(BATCH_ROUTE)

    assert "code:" in sku_source
    assert "actionable_message" in sku_source
    assert "publishErrorResponse" in sku_source
    assert "code:" in batch_source
    assert "actionable_message" in batch_source
    assert "publishErrorResponse" in batch_source


def test_publish_guard_helper_is_configurable_by_env() -> None:
    helper_source = _read(GUARD_HELPER)

    assert "FEEDOPS_PUBLISH_RBAC_ENABLED" in helper_source
    assert "FEEDOPS_PUBLISH_ALLOWED_ROLES" in helper_source
    assert "publish_forbidden_missing_role" in helper_source
    assert "publish_forbidden_role" in helper_source
