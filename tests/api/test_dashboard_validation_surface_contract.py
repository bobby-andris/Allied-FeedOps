from pathlib import Path


REGENERATE_ROUTE = Path("dashboard/src/app/api/regenerate/route.ts")
BATCH_REGENERATE_ROUTE = Path("dashboard/src/app/api/regenerate/batch/route.ts")
REGENERATE_BUTTON = Path("dashboard/src/components/review/RegenerateButton.tsx")
BATCH_REGENERATE_BUTTON = Path("dashboard/src/components/review/BatchRegenerateButton.tsx")
BATCHES_CLIENT = Path("dashboard/src/components/batches/BatchesClient.tsx")


def _read(path: Path) -> str:
    return path.read_text(encoding="utf-8")


def test_regenerate_api_returns_actionable_validation_errors() -> None:
    source = _read(REGENERATE_ROUTE)

    assert "regenerate_missing_required_fields" in source
    assert "regenerate_feedback_missing_fields" in source
    assert "actionable_message" in source
    assert "errorResponse(" in source


def test_batch_regenerate_api_propagates_actionable_error_fields() -> None:
    source = _read(BATCH_REGENERATE_ROUTE)

    assert "actionable_message" in source
    assert "code:" in source
    assert "step:" in source
    assert "validation_errors" in source


def test_review_regenerate_ui_displays_actionable_messages() -> None:
    source = _read(REGENERATE_BUTTON)

    assert "actionable_message" in source
    assert "Next step:" in source


def test_batch_regenerate_ui_displays_actionable_messages() -> None:
    source = _read(BATCH_REGENERATE_BUTTON)

    assert "actionable_message" in source
    assert "Next step:" in source


def test_batch_publish_ui_displays_actionable_messages() -> None:
    source = _read(BATCHES_CLIENT)

    assert "actionable_message" in source
