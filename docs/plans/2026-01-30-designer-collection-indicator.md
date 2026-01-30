# Designer Collection Indicator (Dashboard) Implementation Plan

> **Goal:** Show a clear “Designer collection (validated)” vs “Merchandising/unknown (exclude from titles)” indicator in the Streamlit review dashboard.

## Architecture

- Use the curated collection list in `data/Collection_Descriptions_Complete_All_41_20260124.csv` via `src/feedops/pipeline/collection_descriptions.py::is_known_collection_name`.
- Implement a small pure helper that maps a raw collection string → status + UI message.
- Render the indicator anywhere the dashboard currently prints “Collection: …” (split-pane detail panel + expander detail panel).

## Tasks

1. Add `src/feedops/quality/collection_badge.py` with a pure helper (no Streamlit imports).
2. Add a unit test asserting the helper returns:
   - `designer` for a known collection name (example: `Argo`)
   - `merchandising` for an unknown collection name
   - `none` when missing/blank
3. Update `src/feedops/quality/review_dashboard.py` to render the indicator below the existing “Collection” line in both SKU detail views.
4. Run full test suite: `PYTHONPATH=./src .venv/bin/python -m pytest -q`.
5. Commit only code + tests (avoid `dashboard_data/*`) and push.
