# Dashboard Approval Crash + All-Finishes + Image Selection Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use `superpowers:executing-plans` to implement this plan task-by-task.

**Goal:** Fix the Streamlit review dashboard approval crash, add an “All finishes” approval option, and allow overriding the selected lifestyle image used in patch JSON.

**Architecture:** Make approval UI robust to `NULL`/missing fields (especially `selected_image_index`), represent “All finishes” via a DB-stored sentinel value, and persist the user-selected image variation back into the candidate patch JSON (`selected_lifestyle_image`) so preview + exports stay consistent.

**Tech Stack:** Python, Streamlit, sqlite, pytest.

---

### Task 1: Confirm failing behavior and locate crash

**Files:**
- Inspect: `src/feedops/quality/review_dashboard.py`
- Inspect: `src/feedops/db/schema.py`

**Steps:**
1. Reproduce approval UI path for a SKU with `selected_image_index = NULL`.
2. Trace the stack to `render_approval_controls()` where `min(None, int)` occurs.
3. Confirm DB read returns `None` for `selected_image_index`.

---

### Task 2: Add robust index coercion + empty-list handling

**Files:**
- Modify: `src/feedops/quality/review_dashboard.py`

**Steps:**
1. Implement helper(s) to coerce `None`/invalid values to a safe int and clamp to list bounds.
2. Guard selectbox rendering when `successful_images` is empty (show message + disable approval).
3. Ensure no crash even with stale cached approvals or missing fields.

---

### Task 3: Add “All finishes” option

**Files:**
- Modify: `src/feedops/quality/review_dashboard.py`

**Steps:**
1. Add sentinel constant `__ALL_FINISHES__` and UI label “All finishes”.
2. Update finish selection UI to include this option and store sentinel to DB.
3. Update any dashboard display of selected finish to render sentinel as “All finishes”.

---

### Task 4: Add lifestyle image override and persist to patch JSON

**Files:**
- Modify: `src/feedops/quality/review_dashboard.py`

**Steps:**
1. Add image variation selectbox to choose among successful lifestyle images.
2. Default selection to patch’s `selected_lifestyle_image` when DB has no stored selection.
3. On approval, write `selected_lifestyle_image` back into all applicable candidate patch JSONs (best-effort).

---

### Task 5: Add regression tests

**Files:**
- Add/Modify: `tests/...`

**Steps:**
1. Add unit tests for index coercion/clamping helpers.
2. Add unit test for sentinel display mapping.
3. Add regression test for non-crashing approval selection logic when `selected_image_index` is `None`.
4. Run: `PYTHONPATH=./src .venv/bin/python -m pytest -q`

---

### Task 6: Manual + Playwright verification

**Steps:**
1. Local smoke (optional): start dashboard and confirm SKU approvals don’t error.
2. Playwright: open production dashboard, locate `BSK-275LA`, verify:
   - Approve controls render without exception
   - Finish select includes “All finishes”
   - Image variation selection changes visible image
   - Approve action completes without error banners

