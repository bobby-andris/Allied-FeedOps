from pathlib import Path


ROUTE_PATH = Path("dashboard/src/app/api/regenerate/route.ts")


def _source() -> str:
    return ROUTE_PATH.read_text(encoding="utf-8")


def test_regenerate_route_forwards_request_id_to_pipeline() -> None:
    source = _source()

    assert "const requestId = request.headers.get('x-request-id') ?? randomUUID()" in source
    assert "'X-Request-ID': requestId" in source


def test_regenerate_route_has_no_dashboard_side_generated_content_writes() -> None:
    source = _source()

    assert ".from('generated_content')" not in source
    assert ".from('regeneration_history')" not in source
    assert "single writer for generated_content/regeneration_history" in source


def test_regenerate_route_surfaces_pipeline_state_fields_and_validation() -> None:
    source = _source()

    assert "pipeline_contract_missing_regenerate_metadata" in source
    assert "pipelineState === 'no_change' || pipelineState === 'completed'" in source
    assert "typeof pipelineIdempotent === 'boolean'" in source
    assert "typeof pipelineVersion === 'number'" in source
    assert "generated_content_id: pipelineData.generated_content_id ?? null" in source
    assert "request_id: pipelineRequestId" in source
    assert "validation_errors: violations" in source
