from pathlib import Path


CLOUDBUILD_PATH = Path("cloudbuild.yaml")
DOCKERFILE_PATH = Path("Dockerfile")
REGENERATE_ROUTE_PATH = Path("dashboard/src/app/api/regenerate/route.ts")
MAIN_API_PATH = Path("src/feedops/api/main.py")


def _read(path: Path) -> str:
    return path.read_text(encoding="utf-8")


def test_cloudbuild_contains_required_cloud_run_secrets_and_env() -> None:
    source = _read(CLOUDBUILD_PATH)

    assert "./scripts/verify_cloud_run_parity.sh" in source
    assert "docker run --rm" in source
    assert "OPENAI_API_KEY=feedops-openai-api-key:latest" in source
    assert "SUPABASE_URL=feedops-supabase-url:latest" in source
    assert "SUPABASE_KEY=feedops-supabase-key:latest" in source
    assert "GOOGLE_ADS_API_ENABLED=1" in source
    assert "FEEDOPS_ENV_CONTRACT_STRICT=1" in source
    assert "GOOGLE_ADS_CUSTOMER_ID=" in source


def test_cloudbuild_does_not_toggle_prompt_architecture_runtime_flags() -> None:
    source = _read(CLOUDBUILD_PATH)

    assert "FEEDOPS_PROMPT_VERSION" not in source
    assert "PROMPT_CONTRACT_V2" not in source


def test_dockerfile_matches_cloud_run_runtime_entrypoint_contract() -> None:
    source = _read(DOCKERFILE_PATH)

    assert "FROM python:3.11-slim" in source
    assert "ENV PORT=8080" in source
    assert "EXPOSE 8080" in source
    assert 'CMD ["uvicorn", "feedops.api.main:app"' in source


def test_dashboard_and_python_propagate_request_id_contract() -> None:
    route_source = _read(REGENERATE_ROUTE_PATH)
    api_source = _read(MAIN_API_PATH)

    assert "'X-Request-ID': requestId" in route_source
    assert 'response.headers["X-Request-ID"] = request_id' in api_source


def test_python_api_enforces_runtime_env_contract_on_startup() -> None:
    api_source = _read(MAIN_API_PATH)

    assert "lifespan=_app_lifespan" in api_source
    assert "async def _app_lifespan" in api_source
    assert "validate_runtime_env_contract()" in api_source
