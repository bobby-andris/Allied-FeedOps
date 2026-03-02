from pathlib import Path


EXPAND_VARIANTS = Path("dashboard/src/lib/publishing/expand-variants.ts")
VARIANT_CONTENT = Path("dashboard/src/lib/variant-content.ts")


def _read(path: Path) -> str:
    return path.read_text(encoding="utf-8")


def test_google_publish_validation_enforces_finish_parity_gates() -> None:
    source = _read(EXPAND_VARIANTS)

    assert "publish_google_description_missing_finish_placeholder" in source
    assert "publish_google_description_multiple_finish_placeholders" in source
    assert "publish_google_finish_sentences_incomplete" in source
    assert "publish_google_description_contains_finish_name" in source
    assert "publish_google_description_contains_generic_finish_count_claim" in source
    assert "variant_finish_sentences" in source
    # PR #52 replaced hardcoded EXPECTED_FINISH_SENTENCE_COUNT=28 with dynamic
    # validation that queries actual distinct finish count from variant_index
    assert "variant_index" in source


def test_shopify_publish_validation_enforces_title_and_description_policy() -> None:
    source = _read(EXPAND_VARIANTS)

    assert "publish_shopify_title_contains_brand" in source
    assert "publish_shopify_title_contains_finish_name" in source
    assert "publish_shopify_description_contains_finish_placeholder" in source
    assert "publish_shopify_description_contains_finish_name" in source


def test_variant_expansion_blocks_dual_finish_contradictions() -> None:
    source = _read(VARIANT_CONTENT)

    assert "templateHasHardcodedFinish(result)" in source
    assert "variant_finish_contradiction" in source
