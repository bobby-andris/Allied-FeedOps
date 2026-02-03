# Streamlit Review Dashboard Cache + Variant Preview Fix Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use `superpowers:executing-plans` to implement this plan task-by-task.

**Goal:** Make the Streamlit review dashboard always reflect the latest on-disk patch/report data, prevent crashes from stale cached objects, and ensure Variant Preview uses patch variants when available.

**Architecture:** Add cache invalidation keys based on directory mtimes + a `schema_version` to `@st.cache_data` loads, guard access to potentially-missing attributes on cached objects, and make Variant Preview explicitly select patch variants from candidate export JSON before any regenerated fallback.

**Tech Stack:** Python, Streamlit, pytest.

---

### Task 1: Confirm production evidence (no code changes)

**Files:**
- Read: `dashboard_data/lifestyle-eval-candidate/google-patch-CL-41-18.json`
- Read: `dashboard_data/lifestyle-eval-candidate/reports/`
- Read: `src/feedops/quality/data_loader.py`

**Step 1: Verify patch JSON variant is correct**

Run:
`PYTHONPATH=./src .venv/bin/python -c "import json; from pathlib import Path; d=json.loads(Path('dashboard_data/lifestyle-eval-candidate/google-patch-CL-41-18.json').read_text()); v=[x for x in (d.get('variants') or []) if x.get('_meta',{}).get('finish')=='Autumn Sparkle'][0]; desc=(v.get('description') or v.get('structured_description',{}).get('content') or ''); assert 'Antique Brass' not in desc"`

Expected: command exits 0.

**Step 2: Verify report exists and parses**

Run:
`PYTHONPATH=./src .venv/bin/python -c "from pathlib import Path; from feedops.quality.data_loader import load_latest_report; r=load_latest_report(Path('dashboard_data/lifestyle-eval-candidate/reports'),'cl-41-18'); assert r and r.prompt_text and r.evidence_markdown"`

Expected: command exits 0.

---

### Task 2: Add cache invalidation + cache clear button

**Files:**
- Modify: `src/feedops/quality/review_dashboard.py`

**Step 1: Add mtimes + schema version into cached load**
- Compute latest mtimes for baseline/candidate exports and reports dirs.
- Update the cached `load_data(...)` wrapper to accept these values as arguments.

**Step 2: Add explicit “Clear data cache” UI control**
- Add a sidebar button that calls `st.cache_data.clear()` then `st.rerun()`.

**Step 3: Run the dashboard entrypoint (smoke)**

Run:
`PYTHONPATH=./src .venv/bin/python -m feedops.cli.main review-dashboard`

Expected: dashboard starts without crashing.

---

### Task 3: Make Variant Preview strictly prefer patch variants (and never crash)

**Files:**
- Modify: `src/feedops/quality/review_dashboard.py`
- Test: `tests/test_review_dashboard.py`

**Step 1: Guard access to cached objects**
- Replace direct `.variants` access with `getattr(..., "variants", None)` (and similar for `variant_titles` where used).

**Step 2: Prefer exact patch variants**
- Choose the first platform content (Google, then Bing) that actually contains a non-empty `variants` list.
- Render a UI indicator that the preview is using patch variants.
- Only fall back to `generate_variant_description(...)` if patch variants are absent.

**Step 3: Add test for “variants missing” safety**
- Add a unit test that simulates an `ExportContent`-like object with no `variants` attribute and asserts the helper/selection logic does not raise.

---

### Task 4: Ensure Reasoning Inputs shows report details

**Files:**
- Modify: `src/feedops/quality/review_dashboard.py`

**Step 1: Display provider/model**
- Ensure the panel shows Provider/Model when available.

**Step 2: Display evidence + full prompt**
- Add an expander for “Available Product Data” (evidence table).
- Add an expander for “Full Prompt” that shows `report.prompt_text` when present.

---

### Task 5: Verification

**Files:**
- Test: `tests/`

**Step 1: Run full test suite**

Run:
`PYTHONPATH=./src .venv/bin/python -m pytest -q`

Expected: PASS.

**Step 2: Manual verification checklist**
- Open dashboard, select `CL-41-18`.
- In Reasoning Inputs, verify Provider/Model, Available Product Data, and Full Prompt are present.
- In Variant Preview, select “Autumn Sparkle” and confirm description does **not** contain “Antique Brass”.
- Select “Antique Brass” and confirm description **does** contain “Antique Brass”.

**Step 3: Playwright smoke check**
- Launch the dashboard locally.
- Use Playwright MCP to navigate, open Review Queue, select `CL-41-18`, and verify Reasoning Inputs + Variant Preview behavior.

