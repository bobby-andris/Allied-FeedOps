"""Pytest configuration and fixtures."""
import pytest
from pathlib import Path


@pytest.fixture
def sample_catalog_path() -> Path:
    """Path to sample catalog CSV for testing."""
    return Path("samples/sample-catalog.csv")


@pytest.fixture
def temp_db_path(tmp_path: Path) -> Path:
    """Temporary database path for testing."""
    return tmp_path / "test_feedops.db"
