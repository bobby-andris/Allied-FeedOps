from pathlib import Path


SKU_APPROVAL_ROUTE = Path("dashboard/src/app/api/approvals/route.ts")
VARIANT_APPROVAL_ROUTE = Path("dashboard/src/app/api/variants/approvals/route.ts")


def _read(path: Path) -> str:
    return path.read_text(encoding="utf-8")


def test_master_approval_route_has_idempotent_no_change_response() -> None:
    source = _read(SKU_APPROVAL_ROUTE)

    assert "state: 'no_change'" in source
    assert "idempotent: true" in source
    assert "state: 'updated'" in source
    assert "idempotent: false" in source


def test_master_approval_route_surfaces_actionable_missing_source_errors() -> None:
    source = _read(SKU_APPROVAL_ROUTE)

    assert "missing_source_content" in source
    assert "approval_source_content_check" in source
    assert "Regenerate the missing platform/content items first, then retry approval." in source
    assert "missing_requirements" in source


def test_master_approval_route_only_versions_content_on_approval_transition() -> None:
    source = _read(SKU_APPROVAL_ROUTE)

    assert "transitionContentTypes" in source
    assert "if (currentState.title_approved !== true && nextState.title_approved === true)" in source
    assert "if (currentState.description_approved !== true && nextState.description_approved === true)" in source
    assert "approved_version: (source.approved_version || 0) + 1" in source


def test_variant_approval_route_has_idempotent_no_change_response() -> None:
    source = _read(VARIANT_APPROVAL_ROUTE)

    assert "state: 'no_change'" in source
    assert "idempotent: true" in source
    assert "state: 'updated'" in source
    assert "idempotent: false" in source
