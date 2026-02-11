from pathlib import Path


ROUTE_PATH = Path("dashboard/src/app/api/regenerate/route.ts")


def _source() -> str:
    return ROUTE_PATH.read_text(encoding="utf-8")


def test_regenerate_route_exposes_idempotent_state_contract() -> None:
    source = _source()

    assert "state: 'no_change'" in source
    assert "state: 'completed'" in source
    assert "idempotent: true" in source
    assert "idempotent: false" in source


def test_regenerate_route_surfaces_validation_and_actionable_fields() -> None:
    source = _source()

    assert "validation_errors" in source
    assert "actionable_message" in source
    assert "step:" in source
    assert "code:" in source


def test_regenerate_no_change_path_short_circuits_before_db_write() -> None:
    source = _source()

    marker = "if (isNoChange) {"
    assert marker in source
    tail = source.split(marker, 1)[1]
    no_change_block = tail.split("if (currentContentData)", 1)[0]

    assert ".from('generated_content')" not in no_change_block
    assert ".insert(" not in no_change_block
    assert ".update(" not in no_change_block


def test_regenerate_route_does_not_duplicate_python_history_insert() -> None:
    source = _source()

    assert ".from('regeneration_history')" not in source
    assert "Python pipeline already logs history authoritatively" in source
