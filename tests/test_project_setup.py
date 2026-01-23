# tests/test_project_setup.py
import subprocess
import sys
from pathlib import Path


def test_package_installable():
    """Verify feedops package can be installed."""
    result = subprocess.run(
        [sys.executable, "-m", "pip", "install", "-e", ".", "--dry-run"],
        capture_output=True,
        text=True
    )
    assert result.returncode == 0, f"pip install failed: {result.stderr}"


def test_feedops_importable():
    """Verify feedops package can be imported."""
    import feedops
    assert hasattr(feedops, "__version__")


def test_env_example_exists():
    """Verify .env.example template exists with required keys."""
    env_example = Path(".env.example")
    assert env_example.exists(), ".env.example not found"
    content = env_example.read_text()
    required_keys = ["OPENAI_API_KEY", "GEMINI_API_KEY", "CATALOG_PATH"]
    for key in required_keys:
        assert key in content, f"Missing {key} in .env.example"


def test_pytest_configured():
    """Verify pytest can discover and run tests."""
    result = subprocess.run(
        ["pytest", "--collect-only", "-q"],
        capture_output=True,
        text=True
    )
    assert result.returncode == 0
    assert "test_" in result.stdout
