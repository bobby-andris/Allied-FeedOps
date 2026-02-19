from __future__ import annotations

import sys
from pathlib import Path
from types import SimpleNamespace

from types import ModuleType

try:  # pragma: no cover - import probe only
    from google import genai as _genai_probe  # noqa: F401
except Exception:  # pragma: no cover - fallback shim only
    google_module = ModuleType("google")
    google_genai_module = ModuleType("google.genai")
    google_genai_types_module = ModuleType("google.genai.types")
    google_genai_module.Client = object
    google_genai_types_module.GenerateContentConfig = lambda **kwargs: kwargs
    google_genai_module.types = google_genai_types_module
    google_module.genai = google_genai_module

    sys.modules.setdefault("google", google_module)
    sys.modules.setdefault("google.genai", google_genai_module)
    sys.modules.setdefault("google.genai.types", google_genai_types_module)

import feedops.pipeline.lifestyle_images as lifestyle_images
from feedops.pipeline.lifestyle_images import LifestyleImageResult


def test_generate_single_variation_retries_on_resource_exhausted(
    tmp_path, monkeypatch
) -> None:
    calls = {"n": 0}

    class FakeGeneratedImage:
        def save(self, path: str) -> None:
            Path(path).write_bytes(b"fake-image")

    class FakePart:
        def as_image(self):
            return FakeGeneratedImage()

    class FakeModels:
        def generate_content(self, *args, **kwargs):
            calls["n"] += 1
            if calls["n"] < 3:
                raise Exception(
                    "429 RESOURCE_EXHAUSTED. {'error': {'code': 429, 'status': 'RESOURCE_EXHAUSTED'}}"
                )
            return SimpleNamespace(parts=[FakePart()])

    class FakeClient:
        def __init__(self, api_key: str):
            self.models = FakeModels()

    monkeypatch.setattr(lifestyle_images.genai, "Client", FakeClient, raising=False)
    monkeypatch.setattr(
        lifestyle_images.types,
        "GenerateContentConfig",
        lambda **kwargs: kwargs,
        raising=False,
    )
    monkeypatch.setattr(
        lifestyle_images.time, "sleep", lambda *_args, **_kwargs: None
    )

    generator = lifestyle_images.LifestyleImageGenerator(
        api_key="fake",
        output_dir=tmp_path,
    )

    result = generator.generate_single_variation(
        prompt="test prompt",
        ref_images=[object()],
        master_sku="CS-1",
        variation_num=1,
    )

    assert result.generation_success is True
    assert calls["n"] == 3
    assert Path(result.image_path).exists()


def test_failed_generation_message_includes_variation_errors() -> None:
    failed_results = [
        LifestyleImageResult(
            image_path="",
            variation_num=1,
            generation_success=False,
            prompt_used="prompt",
            timestamp="2026-02-19_120000",
            error_message="429 RESOURCE_EXHAUSTED",
        ),
        LifestyleImageResult(
            image_path="",
            variation_num=2,
            generation_success=False,
            prompt_used="prompt",
            timestamp="2026-02-19_120001",
            error_message="model unavailable",
        ),
    ]

    message = lifestyle_images.build_generation_failure_message(failed_results)

    assert message.startswith("All image generation attempts failed.")
    assert "var1: 429 RESOURCE_EXHAUSTED" in message
    assert "var2: model unavailable" in message
