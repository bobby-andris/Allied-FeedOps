# tests/test_cli.py
import subprocess
import sys
import pytest
from pathlib import Path
from unittest.mock import patch, AsyncMock


def test_cli_help_shows_commands():
    """CLI --help shows available commands."""
    result = subprocess.run(
        [sys.executable, "-m", "feedops.cli.main", "--help"],
        capture_output=True,
        text=True,
    )
    assert result.returncode == 0
    assert "healthcheck" in result.stdout.lower() or "health" in result.stdout.lower()


def test_cli_version_shows_version():
    """CLI --version shows version."""
    result = subprocess.run(
        [sys.executable, "-m", "feedops.cli.main", "--version"],
        capture_output=True,
        text=True,
    )
    assert result.returncode == 0
    assert "0.1.0" in result.stdout


def test_healthcheck_checks_catalog(tmp_path):
    """Healthcheck verifies catalog file exists."""
    # Create a temp catalog
    catalog = tmp_path / "catalog.csv"
    catalog.write_text("MasterSKU,OPTION SKU\nTEST,TEST-PC\n")

    with patch.dict('os.environ', {'CATALOG_PATH': str(catalog)}):
        result = subprocess.run(
            [sys.executable, "-m", "feedops.cli.main", "healthcheck"],
            capture_output=True,
            text=True,
        )
        # Should mention catalog check
        assert "catalog" in result.stdout.lower() or result.returncode == 0


@pytest.mark.asyncio
async def test_optimize_pipeline_integration():
    """Test full optimization pipeline with mocked LLM."""
    from feedops.pipeline.optimize import optimize_parent_sku

    # Mock LLM response
    mock_response = {
        "title": "Test Optimized Title",
        "description": "Test optimized description " * 30,
        "claims": [
            {"claim": "solid brass", "source_field": "material", "source_value": "Brass"}
        ],
        "self_score": {
            "specificity": 8,
            "benefit_coverage": 8,
            "keyword_inclusion": 8,
            "format_adherence": 8,
            "brand_voice": 8,
            "factual_accuracy": 8,
        }
    }

    with patch('feedops.pipeline.optimize.get_provider') as mock_get_provider:
        mock_provider = AsyncMock()
        mock_provider.generate.return_value = mock_response
        mock_provider.name = "mock/test"
        mock_get_provider.return_value = mock_provider

        result = await optimize_parent_sku(
            master_sku="SAMPLE-TB-24",
            catalog_path=Path("samples/sample-catalog.csv"),
            dry_run=True,
        )

        assert result is not None
        assert result.candidate.title == "Test Optimized Title"
