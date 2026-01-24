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


def test_compare_runs_help_available():
    """compare-runs command is registered and documented."""
    result = subprocess.run(
        [sys.executable, "-m", "feedops.cli.main", "compare-runs", "--help"],
        capture_output=True,
        text=True,
    )
    assert result.returncode == 0
    assert "--baseline-exports-dir" in result.stdout
    assert "--candidate-exports-dir" in result.stdout


def test_compare_runs_writes_html(tmp_path):
    """compare-runs generates a self-contained HTML report."""
    baseline_dir = tmp_path / "baseline"
    candidate_dir = tmp_path / "candidate"
    baseline_dir.mkdir()
    candidate_dir.mkdir()
    (baseline_dir / "google-patch-ABC.json").write_text(
        """{
  "offerId": "x",
  "title": "18-Inch Wall Mount Towel Bar Solid Brass | Allied Brass",
  "short_title": "18-Inch Towel Bar",
  "description": "Upgrade your bath with a solid brass towel bar. Center-to-center: 18 in. Projection: 2.5 in. Warranty: Limited Lifetime Warranty."
}"""
    )
    (candidate_dir / "google-patch-ABC.json").write_text(
        """{
  "offerId": "x",
  "title": "18-Inch Wall Mount Towel Bar Solid Brass | Allied Brass",
  "short_title": "18-Inch Towel Bar",
  "description": "Refresh your bath with a solid brass towel bar. Center-to-center: 18 in. Projection: 2.5 in. Warranty: Limited Lifetime Warranty."
}"""
    )
    output_path = tmp_path / "compare.html"
    result = subprocess.run(
        [
            sys.executable,
            "-m",
            "feedops.cli.main",
            "compare-runs",
            "--baseline-exports-dir",
            str(baseline_dir),
            "--candidate-exports-dir",
            str(candidate_dir),
            "--output",
            str(output_path),
        ],
        capture_output=True,
        text=True,
    )
    assert result.returncode == 0
    assert output_path.exists()
    content = output_path.read_text()
    assert "Baseline" in content
    assert "Candidate" in content
    assert "ABC" in content


def test_compare_runs_creates_output_parent(tmp_path):
    """compare-runs creates output directory when needed."""
    baseline_dir = tmp_path / "baseline"
    candidate_dir = tmp_path / "candidate"
    baseline_dir.mkdir()
    candidate_dir.mkdir()
    (baseline_dir / "google-patch-ABC.json").write_text(
        """{
  "offerId": "x",
  "title": "18-Inch Wall Mount Towel Bar Solid Brass | Allied Brass",
  "short_title": "18-Inch Towel Bar",
  "description": "Upgrade your bath with a solid brass towel bar. Center-to-center: 18 in. Projection: 2.5 in. Warranty: Limited Lifetime Warranty."
}"""
    )
    (candidate_dir / "google-patch-ABC.json").write_text(
        """{
  "offerId": "x",
  "title": "18-Inch Wall Mount Towel Bar Solid Brass | Allied Brass",
  "short_title": "18-Inch Towel Bar",
  "description": "Refresh your bath with a solid brass towel bar. Center-to-center: 18 in. Projection: 2.5 in. Warranty: Limited Lifetime Warranty."
}"""
    )
    output_path = tmp_path / "nested" / "compare.html"
    result = subprocess.run(
        [
            sys.executable,
            "-m",
            "feedops.cli.main",
            "compare-runs",
            "--baseline-exports-dir",
            str(baseline_dir),
            "--candidate-exports-dir",
            str(candidate_dir),
            "--output",
            str(output_path),
        ],
        capture_output=True,
        text=True,
    )
    assert result.returncode == 0
    assert output_path.exists()


def test_evaluate_exports_creates_output_parent(tmp_path):
    """evaluate-exports creates output directory when needed."""
    exports_dir = tmp_path / "exports"
    exports_dir.mkdir()
    (exports_dir / "google-patch-ABC.json").write_text(
        """{
  "offerId": "x",
  "title": "18-Inch Wall Mount Towel Bar Solid Brass | Allied Brass",
  "short_title": "18-Inch Towel Bar",
  "description": "Upgrade your bath with a solid brass towel bar. Center-to-center: 18 in. Projection: 2.5 in. Warranty: Limited Lifetime Warranty."
}"""
    )

    output_path = tmp_path / "nested" / "report.md"
    result = subprocess.run(
        [
            sys.executable,
            "-m",
            "feedops.cli.main",
            "evaluate-exports",
            "--exports-dir",
            str(exports_dir),
            "--output",
            str(output_path),
        ],
        capture_output=True,
        text=True,
    )
    assert result.returncode == 0
    assert output_path.exists()


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
async def test_optimize_pipeline_integration(tmp_path):
    """Test full optimization pipeline with mocked LLM."""
    from feedops.pipeline.optimize import optimize_parent_sku

    # Mock LLM response
    mock_response = {
        "google_title": "Test Optimized Title",
        "google_short_title": "Test Short Title",
        "google_description": "Test optimized description " * 30,
        "bing_title": "Test Bing Title",
        "bing_description": "Test optimized description " * 30,
        "shopify_title": "Test Shopify Title",
        "shopify_description": "<p>Test optimized description</p>",
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
            master_sku="101",
            catalog_path=Path("samples/sample-catalog.csv"),
            dry_run=True,
            output_dir=tmp_path,
            exports_dir=tmp_path,
        )

        assert result is not None
        assert result.candidate.google_title == "Test Optimized Title"
        assert "google" in result.patch_previews
        assert "bing" in result.patch_previews
        assert "shopify" in result.patch_previews
        assert result.patch_previews["google"]["title"] == "Test Optimized Title"
