from pathlib import Path


MAIN_API_PATH = Path("src/feedops/api/main.py")
HYBRID_API_PATH = Path("src/feedops/api/hybrid_generation.py")
PROMPT_LOADER_PATH = Path("src/feedops/api/prompt_loader.py")


def _read(path: Path) -> str:
    return path.read_text(encoding="utf-8")


def test_runtime_no_longer_reads_feedops_prompt_version() -> None:
    main_source = _read(MAIN_API_PATH)
    hybrid_source = _read(HYBRID_API_PATH)

    assert "FEEDOPS_PROMPT_VERSION" not in main_source
    assert "FEEDOPS_PROMPT_VERSION" not in hybrid_source


def test_main_generation_paths_call_v2_per_platform_generation_only() -> None:
    source = _read(MAIN_API_PATH)

    assert "prompt_version=\"v2\"" in source
    assert "prompt_version == \"v2\"" not in source


def test_prompt_loader_uses_code_owned_system_prompt() -> None:
    source = _read(PROMPT_LOADER_PATH)

    assert "CANONICAL_SYSTEM_PROMPT" in source
    assert "PROMPT_CONTRACT_V2 disabled" not in source
    assert "db_prompt" not in source
