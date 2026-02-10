from pydantic import ValidationError

from feedops.api.main import RegenerateResponse


def test_regenerate_response_requires_prompt_hash() -> None:
    try:
        RegenerateResponse(
            success=True,
            master_sku="FT-16",
            content_type="description",
            platform="google",
            content="Sample content",
            used_feedback=False,
            model="openai/gpt-5.2",
        )
    except ValidationError:
        return

    raise AssertionError("RegenerateResponse should require prompt_hash")


def test_regenerate_response_includes_prompt_hash_in_dump() -> None:
    response = RegenerateResponse(
        success=True,
        master_sku="FT-16",
        content_type="description",
        platform="google",
        content="Sample content",
        used_feedback=False,
        model="openai/gpt-5.2",
        prompt_hash="deadbeefdeadbeef",
    )

    payload = response.model_dump()
    assert payload["prompt_hash"] == "deadbeefdeadbeef"


def test_regenerate_response_accepts_finish_sentences() -> None:
    response = RegenerateResponse(
        success=True,
        master_sku="FT-16",
        content_type="description",
        platform="google",
        content="Sample content",
        finish_sentences={"Antique Brass": "Antique Brass adds warm character."},
        used_feedback=False,
        model="openai/gpt-5.2",
        prompt_hash="deadbeefdeadbeef",
    )

    payload = response.model_dump()
    assert payload["finish_sentences"] is not None
    assert payload["finish_sentences"]["Antique Brass"] == "Antique Brass adds warm character."
