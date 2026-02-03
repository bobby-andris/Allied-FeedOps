# FeedOps Candidate Regeneration + Dashboard Smoke Test Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use `superpowers:executing-plans` to implement this plan task-by-task.

**Goal:** Regenerate pilot titles/descriptions/images into `dashboard_data/lifestyle-eval-candidate`, verify tests, and smoke-test the Streamlit review dashboard via Playwright without breaking existing pipeline/dashboard behavior.

**Architecture:** Treat the dashboard as a consumer of exported artifacts. Promote prior Candidate → Baseline (already done), then re-run generation into a clean Candidate directory. Validate with unit tests + a browser smoke test.

**Tech Stack:** Python, pytest, Streamlit, Playwright MCP.

---

### Task 1: Verify repo + dashboard data directories

**Files:** None

**Step 1: Check git status**

Run: `git status --porcelain`
Expected: either clean or only intended modified files.

**Step 2: Confirm baseline/candidate dirs exist**

Run:
- `ls -la dashboard_data/lifestyle-eval | head`
- `find dashboard_data/lifestyle-eval-candidate -maxdepth 2 -type d | sort`

Expected:
- `dashboard_data/lifestyle-eval` contains baseline patch JSONs.
- `dashboard_data/lifestyle-eval-candidate` exists and contains `reports/`, `variants/`, `images/` directories.

---

### Task 2: Regenerate candidate titles/descriptions/images

**Files:** Generated artifacts under `dashboard_data/lifestyle-eval-candidate/`

**Step 1: Run batch generation script**

Run: `PYTHONPATH=./src .venv/bin/python batch_lifestyle_eval.py`

Expected:
- Exit code 0.
- New JSON patches in `dashboard_data/lifestyle-eval-candidate/*.json`
- New report markdown in `dashboard_data/lifestyle-eval-candidate/reports/`
- Per-variant JSONs in `dashboard_data/lifestyle-eval-candidate/variants/<sku>/`
- Images copied/synced into `dashboard_data/lifestyle-eval-candidate/images/` (if the script includes the optimizer/sync step)

**Step 2: Sanity check candidate count**

Run: `ls dashboard_data/lifestyle-eval-candidate/*.json | wc -l`
Expected: non-zero (pilot count, typically ~40).

---

### Task 3: Run test suite

**Files:** None

**Step 1: Run pytest**

Run: `PYTHONPATH=./src .venv/bin/python -m pytest -q`
Expected: PASS (no regressions).

---

### Task 4: Launch Streamlit dashboard locally

**Files:** None

**Step 1: Identify Streamlit entrypoint**

Run:
- `rg -n \"streamlit run\" -S .`
- `rg -n \"review_dashboard\" -S .`

Expected: a clear command to launch, likely:
- `PYTHONPATH=./src .venv/bin/python -m streamlit run src/feedops/quality/review_dashboard.py`

**Step 2: Start Streamlit (background)**

Run (example):
`PYTHONPATH=./src .venv/bin/python -m streamlit run src/feedops/quality/review_dashboard.py --server.headless true --server.port 8501`

Expected:
- Server starts without exceptions.
- Dashboard reachable at `http://localhost:8501`.

---

### Task 5: Playwright MCP UI smoke test (no functional changes)

**Files:** Optional screenshot artifacts

**Step 1: Navigate to dashboard**

Using Playwright MCP:
- Navigate to `http://localhost:8501`
- Capture accessibility snapshot

Expected:
- Page renders and is interactive.

**Step 2: Validate Candidate/Baseline view still works**

Using Playwright MCP:
- Confirm both Baseline and Candidate data load (no crashes)
- Confirm new sidebar section “Variant Title Warnings” renders
- Expand “View warning details” and confirm SKU selector lists SKUs

Expected:
- No exceptions or blank panels.
- Warnings metrics populate (may be zero; still should render).

**Step 3: Capture a screenshot**

Using Playwright MCP:
- Take full-page screenshot for human review.

---

### Task 6: Qualitative output audit (“ULTRATHINK” review)

**Files:** None (notes only)

**Step 1: Sample diverse candidate patches**

Run: `ls dashboard_data/lifestyle-eval-candidate/*.json | shuf | head -7`

For each sampled file:
- Inspect title first 70 characters (mobile + desktop zones)
- Inspect description first 150 characters (benefit hook)
- Check finish placement and readability (no pipes; avoid gimmicks)
- Check for size/variant-specific correctness (no hard-coded wrong size)
- Check image prompts/outputs don’t look obviously fake/mismatched

**Step 2: Summarize findings**

Produce a short report:
- What improved vs baseline
- Any remaining “must-fix” issues
- Proposed next P1/P2 actions (if any)

