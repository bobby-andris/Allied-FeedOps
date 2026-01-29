# tests/test_project_setup.py
import os
import subprocess
import sys
import importlib.util
from pathlib import Path

import pytest


def test_package_installable():
    """Verify feedops package can be installed."""
    if importlib.util.find_spec("hatchling") is None:
        pytest.skip("hatchling not installed; packaging check requires build deps")

    # Use stdlib pip instead of `uv` because `uv` can panic on some macOS
    # system configurations in sandboxed environments.
    env = dict(os.environ)
    ensurepip = subprocess.run(
        [sys.executable, "-m", "ensurepip", "--upgrade"],
        capture_output=True,
        text=True,
        env=env,
    )
    assert ensurepip.returncode == 0, f"ensurepip failed: {ensurepip.stderr}"
    result = subprocess.run(
        [sys.executable, "-m", "pip", "install", "-e", ".", "--dry-run", "--no-deps"],
        capture_output=True,
        text=True,
        env=env,
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
        [sys.executable, "-m", "pytest", "--collect-only", "-q"],
        capture_output=True,
        text=True,
    )
    assert result.returncode == 0
    assert "test_" in result.stdout
