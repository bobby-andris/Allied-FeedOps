from feedops.pipeline.finish_sentence_validation import (
    normalize_and_validate_finish_sentences,
    validate_finish_sentence,
)


def test_validate_finish_sentence_accepts_product_specific_sentence() -> None:
    sentence = (
        "Antique Brass gives this towel bar a warm, classic tone while keeping the "
        "wall-mounted profile clean."
    )
    base_description = (
        "This towel bar is wall-mounted and crafted for everyday bathroom use."
    )

    violations = validate_finish_sentence(
        finish_name="Antique Brass",
        sentence=sentence,
        base_description=base_description,
    )

    assert violations == []


def test_validate_finish_sentence_rejects_keyword_dump_and_missing_finish() -> None:
    sentence = "Elegant rack/holder (bathroom, towel, wall mount) with timeless style."
    base_description = "This towel holder keeps bathroom linens organized."

    violations = validate_finish_sentence(
        finish_name="Antique Brass",
        sentence=sentence,
        base_description=base_description,
    )

    assert "missing finish name" in violations
    assert "keyword-dump formatting (slash/parenthetical list)" in violations


def test_validate_finish_sentence_rejects_unverifiable_claim_not_in_base() -> None:
    sentence = "Matte Black finish will never rust on this grab bar."
    base_description = "This grab bar provides secure support in wet areas."

    violations = validate_finish_sentence(
        finish_name="Matte Black",
        sentence=sentence,
        base_description=base_description,
    )

    assert any("unverifiable claim" in violation for violation in violations)


def test_normalize_and_validate_finish_sentences_returns_only_valid_entries() -> None:
    finish_names = ["Antique Brass", "Matte Black"]
    payload = {
        "Antique Brass": (
            "Antique Brass gives this towel bar a warm look while preserving the "
            "clean wall-mounted profile."
        ),
        "Matte Black": "Matte Black is premium and elegant for any decor.",
    }
    base_description = "This towel bar is wall-mounted and designed for bathroom use."

    accepted, rejected = normalize_and_validate_finish_sentences(
        raw=payload,
        finish_names=finish_names,
        base_description=base_description,
    )

    assert set(accepted.keys()) == {"Antique Brass"}
    assert "Matte Black" in rejected
