# P1 Output Hardening Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Eliminate production-facing feed defects (empty title segments, wrong structured field behavior, inconsistent dimensions) and make the batch lifestyle run resilient to 429s before re-running all 40 pilot SKUs.

**Architecture:** Fix the issues at the patch-generation boundary (single source of truth for exported title/description fields), then add targeted regression tests that exercise patch previews directly. Keep changes surgical to avoid breaking Streamlit dashboard and the existing pipeline.

**Tech Stack:** Python, pytest, FeedOps pipeline (`src/feedops/pipeline/*`), dashboard artifacts (`dashboard_data/*`).

---

### Task 1: Always sanitize patch preview titles (no empty segments)

**Files:**
- Modify: `src/feedops/pipeline/reporter.py`
- Test: `tests/test_reporter_patch_preview_title_sanitization.py`

**Step 1: Write failing test**
- Create a minimal `ParentSKU` + `Candidate` where the selected primary variant title contains an empty segment (e.g., `"... Foxtrot |  | Allied Brass"`).
- Assert that `generate_patch_preview(..., platform="bing")["title"]` and `"google"` do **not** contain `", ,"` (or `|  |`).

**Step 2: Run test to verify it fails**
- Run: `PYTHONPATH=./src .venv/bin/python -m pytest -q tests/test_reporter_patch_preview_title_sanitization.py`
- Expected: FAIL with `", ,"` present.

**Step 3: Implement minimal fix**
- Ensure `generate_patch_preview()` **always** runs `_normalize_title_separators()` on the title derived from `primary_patch` (not only when falling back to the candidate title).

**Step 4: Run test to verify it passes**
- Run: `PYTHONPATH=./src .venv/bin/python -m pytest -q tests/test_reporter_patch_preview_title_sanitization.py`
- Expected: PASS.

---

### Task 2: Make Google patch output mutually exclusive (structured-only vs standard-only)

**Files:**
- Modify: `src/feedops/pipeline/reporter.py`
- Test: `tests/test_reporter_google_patch_structured_only.py`

**Step 1: Write failing test**
- Set/unset `FEEDOPS_GMC_STRUCTURED_ONLY` inside the test.
- When `FEEDOPS_GMC_STRUCTURED_ONLY=1`, assert top-level and variant-level Google patches contain `structured_title`/`structured_description` and **do not** contain `title`/`description`.
- When unset/false, assert the inverse (standard `title`/`description` present, structured fields omitted).

**Step 2: Run test to verify it fails**
- Run: `PYTHONPATH=./src .venv/bin/python -m pytest -q tests/test_reporter_google_patch_structured_only.py`
- Expected: FAIL because both are currently present.

**Step 3: Implement minimal fix**
- Add a small helper in `reporter.py`:
  - `structured_only = env FEEDOPS_GMC_STRUCTURED_ONLY truthy`
  - Emit **either** standard **or** structured fields, never both.
- Apply same rule to `generate_variant_patch_preview(..., platform="google")`.

**Step 4: Run test to verify it passes**
- Run: `PYTHONPATH=./src .venv/bin/python -m pytest -q tests/test_reporter_google_patch_structured_only.py`
- Expected: PASS.

---

### Task 3: Reduce run failures from Vertex AI 429s during image scoring

**Files:**
- Modify: `src/feedops/quality/evaluator.py` (or the module that calls the image-scoring provider)
- Test: `tests/test_lifestyle_image_scoring_backoff.py` (unit test, provider mocked)

**Step 1: Write failing test**
- Stub the image scoring call to raise a 429-like exception for N attempts then succeed.
- Assert the scoring function retries with backoff and returns a score when it eventually succeeds.

**Step 2: Run test to verify it fails**
- Run: `PYTHONPATH=./src .venv/bin/python -m pytest -q tests/test_lifestyle_image_scoring_backoff.py`
- Expected: FAIL (no retries).

**Step 3: Implement minimal fix**
- Add bounded retry/backoff (e.g., 4 attempts, exponential backoff + jitter) specifically for 429/RESOURCE_EXHAUSTED.
- Keep the existing “fallback to variation 1” behavior if all attempts fail.

**Step 4: Run test to verify it passes**
- Run: `PYTHONPATH=./src .venv/bin/python -m pytest -q tests/test_lifestyle_image_scoring_backoff.py`
- Expected: PASS.

---

### Task 4: Verify fixes on a targeted SKU subset before full run

**Files:**
- No code changes; run + inspect artifacts in `dashboard_data/lifestyle-eval-candidate/`

**Step 1: Re-run only affected SKUs**
- Run (example): `PYTHONPATH=./src .venv/bin/python batch_lifestyle_eval.py --skus FT-16,1051,MA-26`
- If 429 persists: run with `LIFESTYLE_IMAGE_AI_SELECT=false` for speed and stability.

**Step 2: Validate artifacts**
- Confirm `rg -n \"\\, \\,\" dashboard_data/lifestyle-eval-candidate` returns nothing for regenerated SKUs.
- Confirm Google patches follow the `FEEDOPS_GMC_STRUCTURED_ONLY` contract.

---

### Task 5: Full regression run

**Files:**
- No code changes; run + smoke test dashboard.

**Step 1: Run the full 40**
- Run: `PYTHONPATH=./src .venv/bin/python batch_lifestyle_eval.py`

**Step 2: Dashboard smoke test**
- Start Streamlit dashboard (existing repo command).
- Use Playwright MCP to confirm candidate/baseline toggles render, images load, and patch JSON previews open without errors.

