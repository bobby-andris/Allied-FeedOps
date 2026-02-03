# Dashboard Approval Controls + Prod Parity Implementation Plan

> **For Codex:** Using `superpowers:systematic-debugging` + `superpowers:writing-plans`.

**Goal:** Fix approval crash, add “All finishes” + image override approvals, and verify local + production dashboards reflect the latest code/data.

**Architecture:** Keep approvals as DB state + patch JSON as source-of-truth for preview. UI chooses a finish scope (“All finishes” sentinel or a specific finish) and an image variation index, then persists both (DB + patch JSON best-effort).

**Tech Stack:** Streamlit, SQLite (local db), JSON patches in `dashboard_data/**`, pytest.

---

### Task 1: Inspect git state + deploy branch alignment

**Files:** None

**Step 1:** Check working tree and branch

Run:
- `git status -sb`
- `git branch -vv`
- `git remote -v`
- `git symbolic-ref refs/remotes/origin/HEAD || true`

Expected:
- Identify whether production is tracking `main` or `master`
- Identify which directories have uncommitted changes (especially `dashboard_data/**`)

---

### Task 2: Reproduce the approval crash locally (baseline)

**Files:** None

**Step 1:** Run tests quickly (sanity)

Run:
- `PYTHONPATH=./src .venv/bin/python -m pytest -q`

Expected:
- All tests pass

**Step 2:** Start dashboard locally and attempt approval

Run:
- `PYTHONPATH=./src .venv/bin/python -m feedops.cli.main review-dashboard`

Expected:
- UI loads and approving lifestyle image for `BSK-275LA` does not crash

---

### Task 3: Ensure approval UI supports “All finishes” + manual image selection

**Files:**
- Modify: `src/feedops/quality/review_dashboard.py`
- Test: `tests/test_review_dashboard.py`

**Step 1:** Add robust handling for `selected_image_index` being `None`
- Coerce/clamp selectbox index

**Step 2:** Add “All finishes” sentinel finish option
- Store sentinel value in DB
- Display sentinel as “All finishes” in UI tables

**Step 3:** Add “Choose image variation” selector (successful images only)
- Default selection:
  1) DB index if present
  2) Patch `selected_lifestyle_image` if present
  3) else 0

**Step 4:** When approving image, persist chosen variation back to patch JSONs
- Best-effort update to `selected_lifestyle_image` in google/bing/shopify patch JSON(s)

**Step 5:** Add tests covering:
- Index coercion/clamping
- “All finishes” display mapping
- Variation selection mapping
- Patch update helper updates JSON

**Step 6:** Run full tests

Run:
- `PYTHONPATH=./src .venv/bin/python -m pytest -q`

Expected:
- Pass

---

### Task 4: Production deploy verification (Playwright)

**Files:** None

**Step 1:** Open prod Streamlit app in Playwright and validate:
- App loads (no crash)
- Select `BSK-275LA`
- Toggle “Lifestyle Image” approval
- Confirm “All finishes” exists as a finish scope option
- Confirm image variation selection exists and does not crash

**Step 2:** If production still shows old UI:
- Confirm Streamlit Cloud is tracking correct branch
- Reboot app in Streamlit UI
- (Optional) add a visible build marker in the UI and redeploy

---

### Task 5: Decide what to commit for production parity

**Files:**
- Modify: `.streamlit/secrets.toml` (if used locally and safe)
- Documentation: `README.md`

**Step 1:** Determine which directories production reads from (Streamlit secrets).
- If production points to `dashboard_data/lifestyle-eval`, ensure that directory contains the patch JSONs and any required images committed in git.
- If production points to `dashboard_data/lifestyle-eval-candidate`, do not delete it; commit only the minimal required artifacts.

**Step 2:** Provide explicit “what to commit” guidance:
- Code (`src/**`)
- Tests (`tests/**`)
- Only the required `dashboard_data/**` artifacts that production must read (avoid mass-committing archives/old iterations).

