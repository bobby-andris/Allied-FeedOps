from pydantic import ValidationError

from feedops.api.main import RegenerateResponse


def test_regenerate_response_requires_prompt_hash_and_request_id() -> None:
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

    raise AssertionError("RegenerateResponse should require prompt_hash and request_id")


def test_regenerate_response_includes_state_fields() -> None:
    response = RegenerateResponse(
        success=True,
        master_sku="FT-16",
        content_type="description",
        platform="google",
        content="Sample content",
        used_feedback=False,
        model="openai/gpt-5.2",
        prompt_hash="deadbeefdeadbeef",
        generated_content_id="row-1",
        version=7,
        state="completed",
        idempotent=False,
        request_id="req-123",
    )

    payload = response.model_dump()
    assert payload["prompt_hash"] == "deadbeefdeadbeef"
    assert payload["generated_content_id"] == "row-1"
    assert payload["version"] == 7
    assert payload["state"] == "completed"
    assert payload["idempotent"] is False
    assert payload["request_id"] == "req-123"


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
        version=1,
        state="no_change",
        idempotent=True,
        request_id="req-456",
    )

    payload = response.model_dump()
    assert payload["finish_sentences"] is not None
    assert payload["finish_sentences"]["Antique Brass"] == "Antique Brass adds warm character."
    assert payload["state"] == "no_change"
