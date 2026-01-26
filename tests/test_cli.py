# tests/test_cli.py
import subprocess
import sys
from pathlib import Path
from unittest.mock import AsyncMock, patch

import pytest


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


def test_compare_runs_command_removed():
    """compare-runs command should no longer be available."""
    result = subprocess.run(
        [sys.executable, "-m", "feedops.cli.main", "--help"],
        capture_output=True,
        text=True,
    )
    assert result.returncode == 0
    assert "compare-runs" not in result.stdout


def test_optimize_help_includes_candidate_flags():
    """optimize command documents candidate selection flags."""
    result = subprocess.run(
        [sys.executable, "-m", "feedops.cli.main", "optimize", "--help"],
        capture_output=True,
        text=True,
    )
    assert result.returncode == 0
    assert "--candidates" in result.stdout
    assert "--candidate-weights" in result.stdout


def test_default_output_dirs_point_to_dashboard_data():
    from feedops.cli import defaults

    assert str(defaults.CANDIDATE_EXPORTS_DIR).endswith(
        "dashboard_data/lifestyle-eval-candidate"
    )
    assert str(defaults.CANDIDATE_REPORTS_DIR).endswith(
        "dashboard_data/lifestyle-eval-candidate/reports"
    )


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

    with patch.dict("os.environ", {"CATALOG_PATH": str(catalog)}):
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

    weak_response = {
        "google_title": "Nice Towel Bar",
        "google_short_title": "Nice",
        "google_description": "Towel bar.",
        "bing_title": "Nice Towel Bar",
        "bing_description": "Towel bar.",
        "shopify_title": "Nice Towel Bar",
        "shopify_description": "<p>Towel bar.</p>",
        "claims": [],
        "self_score": {
            "specificity": 5,
            "benefit_coverage": 5,
            "keyword_inclusion": 5,
            "format_adherence": 5,
            "brand_voice": 5,
            "factual_accuracy": 8,
        },
    }
    strong_response = {
        "google_title": "18-Inch Wall Mount Towel Bar Solid Brass | Allied Brass",
        "google_short_title": "18-Inch Towel Bar",
        "google_description": "Add space-saving towel storage with this 18-inch wall mount towel bar crafted from solid brass. "
        "Highlights:\n- 18-inch center-to-center towel bar\n- Solid brass construction\n- Concealed mounting hardware\n"
        "Specs:\n- Overall length: 20 in\n- Projection: 2.5 in\n- Warranty: Limited Lifetime Warranty\n",
        "bing_title": "18-Inch Wall Mount Towel Bar Solid Brass | Allied Brass",
        "bing_description": "Organize towels with a wall mounted towel bar. Center-to-center: 18 in. Projection: 2.5 in. Warranty: Limited Lifetime Warranty.",
        "shopify_title": "18-Inch Solid Brass Towel Bar | Allied Brass",
        "shopify_description": "<p>Upgrade your bathroom with a solid brass towel bar.</p><ul><li>Solid brass</li><li>Wall mount</li><li>Hardware included</li></ul><p>Center-to-center: 18 in</p>",
        "claims": [],
        "self_score": {
            "specificity": 8,
            "benefit_coverage": 8,
            "keyword_inclusion": 8,
            "format_adherence": 8,
            "brand_voice": 8,
            "factual_accuracy": 8,
        },
    }
    leaky_response = {
        "google_title": "18-Inch Wall Mount Towel Bar (catalog_csv.Material)",
        "google_short_title": "18-Inch Towel Bar",
        "google_description": "Solid brass build catalog_csv.Material",
        "bing_title": "18-Inch Wall Mount Towel Bar (catalog_csv.Material)",
        "bing_description": "Solid brass build catalog_csv.Material",
        "shopify_title": "18-Inch Wall Mount Towel Bar (catalog_csv.Material)",
        "shopify_description": "<p>Solid brass build catalog_csv.Material</p>",
        "claims": [],
        "self_score": {
            "specificity": 8,
            "benefit_coverage": 8,
            "keyword_inclusion": 8,
            "format_adherence": 8,
            "brand_voice": 8,
            "factual_accuracy": 8,
        },
    }

    with patch("feedops.pipeline.optimize.get_provider") as mock_get_provider:
        mock_provider = AsyncMock()
        mock_provider.generate.side_effect = [
            weak_response,
            strong_response,
            leaky_response,
        ]
        mock_provider.name = "mock/test"
        mock_get_provider.return_value = mock_provider
        with patch(
            "feedops.pipeline.generator.fetch_image", new_callable=AsyncMock
        ) as mock_fetch:
            mock_fetch.return_value = None
            result = await optimize_parent_sku(
                master_sku="101",
                catalog_path=Path("samples/sample-catalog.csv"),
                dry_run=True,
                output_dir=tmp_path,
                exports_dir=tmp_path,
                num_candidates=3,
            )

        assert result is not None
        assert result.candidate.google_title == strong_response["google_title"]
        assert "google" in result.patch_previews
        assert "bing" in result.patch_previews
        assert "shopify" in result.patch_previews
        assert (
            result.patch_previews["google"]["title"] == strong_response["google_title"]
        )


@pytest.mark.asyncio
async def test_optimize_triggers_sync_for_dashboard_exports(tmp_path, monkeypatch):
    """Ensure dashboard exports trigger lifestyle image path sync."""
    from feedops.pipeline.optimize import optimize_parent_sku

    response = {
        "google_title": "18-Inch Wall Mount Towel Bar Solid Brass | Allied Brass",
        "google_short_title": "18-Inch Towel Bar",
        "google_description": "Add storage with solid brass.\nHighlights:\n- Solid brass\nSpecs:\n- 18 in\n",
        "bing_title": "18-Inch Wall Mount Towel Bar Solid Brass | Allied Brass",
        "bing_description": "Add storage with solid brass.",
        "shopify_title": "18-Inch Solid Brass Towel Bar | Allied Brass",
        "shopify_description": "<p>Upgrade your bath.</p><ul><li>Solid brass</li></ul>",
        "claims": [],
        "self_score": {
            "specificity": 8,
            "benefit_coverage": 8,
            "keyword_inclusion": 8,
            "format_adherence": 8,
            "brand_voice": 8,
            "factual_accuracy": 8,
        },
    }

    sync_calls = {}

    def fake_sync_lifestyle_images(exports_dir, **_kwargs):
        sync_calls["exports_dir"] = Path(exports_dir)
        return {"files_scanned": 0}

    monkeypatch.setattr(
        "feedops.quality.data_loader.sync_lifestyle_images",
        fake_sync_lifestyle_images,
    )

    with patch("feedops.pipeline.optimize.get_provider") as mock_get_provider:
        mock_provider = AsyncMock()
        mock_provider.generate.side_effect = [response, response, response]
        mock_provider.name = "mock/test"
        mock_get_provider.return_value = mock_provider
        with patch(
            "feedops.pipeline.generator.fetch_image", new_callable=AsyncMock
        ) as mock_fetch:
            mock_fetch.return_value = None
            exports_dir = tmp_path / "dashboard_data" / "lifestyle-eval-candidate"
            output_dir = exports_dir / "reports"
            await optimize_parent_sku(
                master_sku="101",
                catalog_path=Path("samples/sample-catalog.csv"),
                dry_run=True,
                output_dir=output_dir,
                exports_dir=exports_dir,
                num_candidates=3,
            )

    assert sync_calls["exports_dir"] == exports_dir
    assert sync_calls["exports_dir"] == exports_dir
