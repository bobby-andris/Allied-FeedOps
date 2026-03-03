from pathlib import Path


LEGACY_PIPELINE_HOST = "feedops-pipeline-623866089882"
GENERATE_ROUTE = Path("dashboard/src/app/api/sku-selection/generate/route.ts")
REGENERATE_ROUTE = Path("dashboard/src/app/api/regenerate/route.ts")
IMAGES_GENERATE_ROUTE = Path("dashboard/src/app/api/images/generate/route.ts")
PIPELINE_RUNTIME_FILES = [
    GENERATE_ROUTE,
    REGENERATE_ROUTE,
    Path("dashboard/src/app/api/performance/capture-snapshot/route.ts"),
    Path("dashboard/src/app/api/gmc/sync/route.ts"),
    Path("dashboard/src/app/api/monitoring/backfill-health/route.ts"),
    Path("dashboard/src/app/api/search-insights/sync/route.ts"),
    Path("dashboard/src/app/api/shopping-funnel/tier-scoring/route.ts"),
    Path("dashboard/src/app/api/backfill/route.ts"),
    IMAGES_GENERATE_ROUTE,
    Path("dashboard/src/components/review/LifestyleImageReview.tsx"),
    Path("scripts/setup-cloud-scheduler.sh"),
    Path("dashboard/.env.local.example"),
]


def _read(path: Path) -> str:
    return path.read_text(encoding="utf-8")


def test_generate_route_forwards_generation_options_to_pipeline() -> None:
    source = _read(GENERATE_ROUTE)

    assert "options:" in source
    assert "titles: options.titles" in source
    assert "descriptions: options.descriptions" in source
    assert "platforms: options.platforms" in source


def test_runtime_dashboard_paths_do_not_hardcode_legacy_pipeline_url() -> None:
    for path in PIPELINE_RUNTIME_FILES:
        source = _read(path)
        assert LEGACY_PIPELINE_HOST not in source, f"legacy pipeline host leaked in {path}"


def test_generation_routes_fail_closed_when_pipeline_url_missing() -> None:
    generate_source = _read(GENERATE_ROUTE)
    regenerate_source = _read(REGENERATE_ROUTE)

    assert "if (!PIPELINE_URL)" in generate_source
    assert "if (!PIPELINE_URL)" in regenerate_source
    assert "FEEDOPS_PIPELINE_URL" in generate_source
    assert "FEEDOPS_PIPELINE_URL" in regenerate_source


def test_runtime_proxy_routes_use_required_pipeline_url_helper() -> None:
    helper_backed_routes = [
        Path("dashboard/src/app/api/performance/capture-snapshot/route.ts"),
        Path("dashboard/src/app/api/gmc/sync/route.ts"),
        Path("dashboard/src/app/api/search-insights/sync/route.ts"),
        Path("dashboard/src/app/api/backfill/route.ts"),
        IMAGES_GENERATE_ROUTE,
    ]

    for path in helper_backed_routes:
        source = _read(path)
        assert "getRequiredPipelineUrl" in source, f"expected helper-backed pipeline resolution in {path}"


def test_lifestyle_image_generation_uses_dashboard_proxy() -> None:
    source = _read(Path("dashboard/src/components/review/LifestyleImageReview.tsx"))

    assert "/api/images/generate" in source
    assert "NEXT_PUBLIC_CLOUD_RUN_URL" not in source


def test_cloud_scheduler_script_requires_service_url_configuration() -> None:
    source = _read(Path("scripts/setup-cloud-scheduler.sh"))

    assert 'SERVICE_URL="${SERVICE_URL:-${1:-}}"' in source
    assert "SERVICE_URL must be provided via environment variable or first positional argument." in source


def test_dashboard_env_example_documents_canonical_pipeline_variable() -> None:
    source = _read(Path("dashboard/.env.local.example"))

    assert "FEEDOPS_PIPELINE_URL=" in source
    assert "NEXT_PUBLIC_CLOUD_RUN_URL" not in source
