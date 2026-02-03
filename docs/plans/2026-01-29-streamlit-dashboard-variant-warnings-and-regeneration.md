# Streamlit Variant Warnings + Regeneration Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Surface variant title warnings in the Streamlit dashboard, then roll the current Candidate outputs into Baseline and regenerate fresh Candidate titles/descriptions/images for review.

**Architecture:** Keep the pipeline unchanged (warnings are already emitted into patch `_meta`). The dashboard becomes a thin consumer: parse warnings from exported JSON and display a summary + per-SKU drilldown. Regeneration uses existing CLI/scripts to avoid inventing new orchestration paths.

**Tech Stack:** Python, Streamlit dashboard (repo), FeedOps CLI/scripts, Playwright MCP for manual UI verification.

---

### Task 1: Locate Streamlit dashboard entry + data loaders

**Files:**
- Modify: (to be discovered) Streamlit entrypoint (e.g. `dashboard/*.py` or `app.py`)

**Step 1: Find Streamlit entrypoint**

Run: `rg -n "import streamlit|st\\." -S .`
Expected: list of dashboard files using Streamlit.

**Step 2: Identify where candidate/baseline JSON is loaded**

Run: `rg -n "dashboard_data|lifestyle-eval-candidate|lifestyle-eval-baseline|read_text|json\\.load" -S <streamlit-file>`
Expected: a function or block that reads candidate exports.

---

### Task 2: Add a small helper to parse variant title warnings (unit-tested)

**Files:**
- Create: `src/feedops/dashboard/variant_warnings.py`
- Test: `tests/test_dashboard_variant_warnings.py`

**Step 1: Write the failing test**

```python
from feedops.dashboard.variant_warnings import summarize_variant_title_warnings


def test_summarize_variant_title_warnings_counts_types():
    patches = [
        {"_meta": {"variant_title_warnings": ["Duplicate variant title detected: 'x'"]}},
        {"_meta": {"variant_title_warnings": ["Finish 'Satin Nickel' appears after the first 70 characters; consider moving finish earlier for variant differentiation."]}},
        {"_meta": {}},
    ]
    summary = summarize_variant_title_warnings(patches)
    assert summary["total_patches"] == 3
    assert summary["patches_with_warnings"] == 2
    assert summary["warning_counts"]["duplicate"] == 1
    assert summary["warning_counts"]["finish_after_visible_chars"] == 1
```

**Step 2: Run test to verify it fails**

Run: `PYTHONPATH=./src .venv/bin/python -m pytest -q tests/test_dashboard_variant_warnings.py`
Expected: FAIL (module not found).

**Step 3: Implement minimal helper**

```python
from __future__ import annotations

from collections import Counter
from typing import Any


def summarize_variant_title_warnings(patches: list[dict[str, Any]]) -> dict[str, Any]:
    warning_counts: Counter[str] = Counter()
    patches_with_warnings = 0
    for patch in patches:
        warnings = ((patch or {}).get("_meta") or {}).get("variant_title_warnings") or []
        if not warnings:
            continue
        patches_with_warnings += 1
        for w in warnings:
            wl = (w or "").lower()
            if "duplicate variant title" in wl:
                warning_counts["duplicate"] += 1
            elif "appears after the first" in wl and "consider moving finish earlier" in wl:
                warning_counts["finish_after_visible_chars"] += 1
            else:
                warning_counts["other"] += 1

    return {
        "total_patches": len(patches),
        "patches_with_warnings": patches_with_warnings,
        "warning_counts": dict(warning_counts),
    }
```

**Step 4: Run test to verify it passes**

Run: `PYTHONPATH=./src .venv/bin/python -m pytest -q tests/test_dashboard_variant_warnings.py`
Expected: PASS.

---

### Task 3: Render warnings in Streamlit dashboard

**Files:**
- Modify: Streamlit dashboard file(s) from Task 1

**Step 1: Add “Variant Title Warnings” summary section**
- Show: total patches, patches with warnings, counts by type.

**Step 2: Add per-SKU drilldown**
- For each candidate patch: show SKU/master_sku and its warnings (if present).

**Step 3: Verify dashboard still loads without warnings present**
- Handle missing `_meta` and missing `variant_title_warnings` gracefully.

**Step 4: Run Streamlit locally**

Run (example; adjust path to entrypoint): `PYTHONPATH=./src .venv/bin/python -m streamlit run <streamlit-entry>.py --server.headless true --server.port 8501`
Expected: Streamlit starts on `http://localhost:8501`.

---

### Task 4: Promote current Candidate → Baseline (data move)

**Files:**
- Modify: none (prefer using existing CLI/script)

**Step 1: Confirm directories**

Run: `ls -1 dashboard_data`
Expected: candidate/baseline directories exist (or determine baseline path).

**Step 2: Promote candidate to baseline**

Run (preferred if exists): `PYTHONPATH=./src .venv/bin/python -m feedops.cli.main copy-to-baseline`
If no CLI exists, run the script directly (discover path): `PYTHONPATH=./src .venv/bin/python -m feedops.pipeline.copy_to_baseline`

Expected: baseline directory updated with previous candidate outputs.

---

### Task 5: Regenerate full titles/descriptions/images (new Candidate)

**Files:**
- Modify: none (run pipeline/CLI)

**Step 1: Run full generation for the pilot set**
- Use the repo’s existing command(s) for generating candidate JSON + reports + images.
- Ensure output goes to `dashboard_data/lifestyle-eval-candidate`.

Run: `PYTHONPATH=./src .venv/bin/python -m feedops.cli.main optimize-batch --help`
Then run the correct command with the 40 pilot SKUs configuration.

Expected: new JSON patches in `dashboard_data/lifestyle-eval-candidate/*.json` plus any image artifacts.

---

### Task 6: Manual dashboard inspection with Playwright MCP

**Files:**
- Modify: none

**Step 1: Open the Streamlit dashboard in Playwright**
- Navigate to `http://localhost:8501`
- Verify:
  - Page loads
  - Candidate/Baseline switch still works
  - New “Variant Title Warnings” section renders and updates
  - No obvious exceptions or broken UI interactions

**Step 2: Capture an accessibility snapshot**
- Save snapshot output for review.

---

### Task 7: Sanity checks + report findings (no merge yet)

**Files:**
- Modify: none

**Step 1: Run full test suite**

Run: `PYTHONPATH=./src .venv/bin/python -m pytest -q`
Expected: PASS.

**Step 2: Sample output quality check (manual)**

Run: `ls dashboard_data/lifestyle-eval-candidate/*.json | shuf | head -7`
Then open each and confirm:
- Finish + size visible early when needed
- No hallucinated claims
- Lifestyle images look plausible (not “AI plastic”)

**Step 3: Summarize “what improved / what’s still risky”**
- Provide a short readiness verdict and next fixes.

