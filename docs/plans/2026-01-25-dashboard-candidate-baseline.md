# Dashboard Candidate/Baseline Split Implementation Plan
 
> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.
 
**Goal:** Allow the Streamlit dashboard to show baseline and candidate runs from separate directories so previous results remain visible while new candidates are displayed.
 
**Architecture:** Update `streamlit_app.resolve_dashboard_paths` to resolve baseline exports from `dashboard_data/lifestyle-eval`, candidate exports from `dashboard_data/lifestyle-eval-candidate` when present (fallback to baseline when missing), and map baseline/candidate reports to their respective `reports/` subfolders. Add tests to lock in the path-resolution behavior.
 
**Tech Stack:** Python, Streamlit, pytest
 
---
 
### Task 1: Add tests for dashboard path resolution
 
**Files:**
- Modify: `tests/test_streamlit_app.py`
 
**Step 1: Write the failing test**
```python
def test_resolve_dashboard_paths_uses_candidate_dir_when_present(tmp_path: Path) -> None:
    data_dir = tmp_path / "dashboard_data"
    baseline_dir = data_dir / "lifestyle-eval"
    candidate_dir = data_dir / "lifestyle-eval-candidate"
    (baseline_dir / "reports").mkdir(parents=True)
    (candidate_dir / "reports").mkdir(parents=True)
    (data_dir / "catalog.csv").write_text("MasterSKU,Category\n")

    from streamlit_app import resolve_dashboard_paths

    baseline, candidate, catalog, baseline_reports, candidate_reports = resolve_dashboard_paths(tmp_path)

    assert baseline == baseline_dir
    assert candidate == candidate_dir
    assert catalog == data_dir / "catalog.csv"
    assert baseline_reports == baseline_dir / "reports"
    assert candidate_reports == candidate_dir / "reports"
```
 
**Step 2: Run test to verify it fails**
Run: `PYTHONPATH=./src .venv/bin/python -m pytest tests/test_streamlit_app.py -v`
Expected: FAIL because `resolve_dashboard_paths` currently returns the same baseline/candidate path.
 
**Step 3: Write minimal implementation**
Update `resolve_dashboard_paths` to detect candidate directory and return distinct paths.
 
**Step 4: Run test to verify it passes**
Run: `PYTHONPATH=./src .venv/bin/python -m pytest tests/test_streamlit_app.py -v`
Expected: PASS
 
**Step 5: Commit**
```bash
git add tests/test_streamlit_app.py streamlit_app.py
git commit -m "test: cover candidate/baseline dashboard paths"
```
 
### Task 2: Add fallback behavior when candidate directory is missing
 
**Files:**
- Modify: `tests/test_streamlit_app.py`
 
**Step 1: Write the failing test**
```python
def test_resolve_dashboard_paths_falls_back_to_baseline(tmp_path: Path) -> None:
    data_dir = tmp_path / "dashboard_data"
    baseline_dir = data_dir / "lifestyle-eval"
    baseline_dir.mkdir(parents=True)
    (data_dir / "catalog.csv").write_text("MasterSKU,Category\n")

    from streamlit_app import resolve_dashboard_paths

    baseline, candidate, catalog, baseline_reports, candidate_reports = resolve_dashboard_paths(tmp_path)

    assert baseline == baseline_dir
    assert candidate == baseline_dir
    assert catalog == data_dir / "catalog.csv"
    assert baseline_reports is None
    assert candidate_reports is None
```
 
**Step 2: Run test to verify it fails**
Run: `PYTHONPATH=./src .venv/bin/python -m pytest tests/test_streamlit_app.py -v`
Expected: FAIL because `resolve_dashboard_paths` doesn't fallback yet.
 
**Step 3: Write minimal implementation**
Add candidate fallback to baseline and return `None` for missing reports.
 
**Step 4: Run test to verify it passes**
Run: `PYTHONPATH=./src .venv/bin/python -m pytest tests/test_streamlit_app.py -v`
Expected: PASS
 
**Step 5: Commit**
```bash
git add tests/test_streamlit_app.py streamlit_app.py
git commit -m "feat: separate baseline and candidate dashboard paths"
```
