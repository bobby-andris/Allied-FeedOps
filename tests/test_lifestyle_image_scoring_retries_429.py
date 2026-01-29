from __future__ import annotations

from io import BytesIO
from types import SimpleNamespace

from PIL import Image

import feedops.pipeline.lifestyle_images as lifestyle_images


def test_score_lifestyle_image_retries_on_resource_exhausted(tmp_path, monkeypatch) -> None:
    generated_path = tmp_path / "CL-41-30_var1_20260129_104033.png"
    Image.new("RGB", (32, 32), color=(255, 255, 255)).save(generated_path)

    buf = BytesIO()
    Image.new("RGB", (16, 16), color=(0, 0, 0)).save(buf, format="PNG")
    ref_bytes = buf.getvalue()

    calls = {"n": 0}

    class FakeModels:
        def generate_content(self, *args, **kwargs):
            calls["n"] += 1
            if calls["n"] < 3:
                raise Exception(
                    "429 RESOURCE_EXHAUSTED. {'error': {'code': 429, 'status': 'RESOURCE_EXHAUSTED'}}"
                )
            return SimpleNamespace(
                text='{"product_accuracy": 90, "composition_quality": 80, "background_appropriateness": 80, "aesthetic_appeal": 80, "notes": "ok"}'
            )

    class FakeClient:
        def __init__(self, api_key: str):
            self.models = FakeModels()

    class FakeResponse:
        def __init__(self, content: bytes):
            self.content = content

        def raise_for_status(self) -> None:
            return None

    def fake_get(url: str, timeout: int = 10):
        return FakeResponse(ref_bytes)

    monkeypatch.setattr(lifestyle_images.genai, "Client", FakeClient)
    monkeypatch.setattr(lifestyle_images.requests, "get", fake_get)

    # If the implementation uses backoff sleeps, don’t slow tests down.
    if hasattr(lifestyle_images, "time"):
        monkeypatch.setattr(lifestyle_images.time, "sleep", lambda *_args, **_kwargs: None)

    score = lifestyle_images.score_lifestyle_image(
        image_path=generated_path,
        reference_image_url="https://example.com/ref.png",
        category="Towel Bars",
        api_key="fake",
    )

    assert score.evaluation_success is True
    assert calls["n"] == 3

