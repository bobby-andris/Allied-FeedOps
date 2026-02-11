from pathlib import Path


GENERATE_ROUTE = Path("dashboard/src/app/api/sku-selection/generate/route.ts")
GENERATE_HYBRID_ROUTE = Path(
    "dashboard/src/app/api/sku-selection/generate-hybrid/route.ts"
)
REGENERATE_ROUTE = Path("dashboard/src/app/api/regenerate/route.ts")


def _read(path: Path) -> str:
    return path.read_text(encoding="utf-8")


def test_generate_route_forwards_generation_options_to_pipeline() -> None:
    source = _read(GENERATE_ROUTE)

    assert "options:" in source
    assert "titles: options.titles" in source
    assert "descriptions: options.descriptions" in source
    assert "platforms: options.platforms" in source


def test_generation_routes_do_not_hardcode_production_pipeline_url() -> None:
    hybrid_source = _read(GENERATE_HYBRID_ROUTE)
    regenerate_source = _read(REGENERATE_ROUTE)

    assert "feedops-pipeline-623866089882" not in hybrid_source
    assert "feedops-pipeline-623866089882" not in regenerate_source


def test_generation_routes_fail_closed_when_pipeline_url_missing() -> None:
    hybrid_source = _read(GENERATE_HYBRID_ROUTE)
    regenerate_source = _read(REGENERATE_ROUTE)

    assert "if (!PIPELINE_URL)" in hybrid_source
    assert "if (!PIPELINE_URL)" in regenerate_source
    assert "FEEDOPS_PIPELINE_URL" in hybrid_source
    assert "FEEDOPS_PIPELINE_URL" in regenerate_source
