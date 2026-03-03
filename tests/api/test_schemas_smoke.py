"""Smoke tests — schemas.py importable without main.py."""


def test_schemas_importable_standalone():
    from feedops.api.schemas import (
        OptimizeRequest, RegenerateRequest, BatchOptimizeRequest,
        RegenerateResponse, HybridGenerateRequest,
        GenerateImagesRequest, ScoreIntentRequest,
    )
    assert OptimizeRequest is not None


def test_no_circular_import_with_main():
    import feedops.api.schemas
    import feedops.api.main


def test_optimize_request_defaults():
    from feedops.api.schemas import OptimizeRequest
    req = OptimizeRequest(master_sku="FT-16")
    assert req.dry_run is True
    assert req.num_candidates == 3


def test_content_field_key():
    from feedops.api.schemas import _content_field_key
    assert _content_field_key("google", "description") is not None


def test_all_seventeen_models_accessible():
    from feedops.api.schemas import (
        OptimizeRequest, RegenerateRequest, BatchOptimizeRequest,
        HealthResponse, OptimizeResponse, RegenerateResponse,
        RegenerateJobResponse, RegenerateJobStatusResponse,
        BatchJobResponse, BatchStatusResponse,
        GenerateImagesRequest, GenerateImagesResponse,
        HybridGenerateRequest, HybridJobResponse,
        ScoreIntentRequest, ScoreIntentItem, ScoreIntentResponse,
    )
    models = [
        OptimizeRequest, RegenerateRequest, BatchOptimizeRequest,
        HealthResponse, OptimizeResponse, RegenerateResponse,
        RegenerateJobResponse, RegenerateJobStatusResponse,
        BatchJobResponse, BatchStatusResponse,
        GenerateImagesRequest, GenerateImagesResponse,
        HybridGenerateRequest, HybridJobResponse,
        ScoreIntentRequest, ScoreIntentItem, ScoreIntentResponse,
    ]
    assert len(models) == 17
