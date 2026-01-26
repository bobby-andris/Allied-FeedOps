"""Default paths for Streamlit-first output directories."""

from pathlib import Path

BASELINE_EXPORTS_DIR = Path("dashboard_data/lifestyle-eval")
CANDIDATE_EXPORTS_DIR = Path("dashboard_data/lifestyle-eval-candidate")
BASELINE_REPORTS_DIR = BASELINE_EXPORTS_DIR / "reports"
CANDIDATE_REPORTS_DIR = CANDIDATE_EXPORTS_DIR / "reports"
