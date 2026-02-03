# FeedOps Production Readiness Revisions Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Eliminate production-blocking data accuracy and formatting defects (multi-size specs, Shopify variant architecture, offerId preflight, finish-options artifacts) and add regression gates so FeedOps cannot reintroduce them.

**Architecture:** Treat “accuracy” as a first-class constraint: derive all size-dependent specs from the `OPTION SKU` row (variant-level truth), ensure Shopify `body_html` never claims a single size when multiple sizes exist, and add preflight validation for offer IDs and content structure before export/publish.

**Tech Stack:** Python, sqlite3, pytest; optional Shopify theme Liquid changes (if metafield-based variant spec rendering is chosen).

---

## Decision: Shopify “split by size” vs “metafields + theme” vs “size table (no theme)”

**Background:** Shopify’s product description (`body_html`) is product-level. It does **not** vary by selected variant unless you implement theme logic that reads variant-specific fields. Shopify’s own theme guidance expects variant selection to update the page with variant-specific information, using the selected variant (e.g., `product.selected_or_first_available_variant`). See: `/docs/storefronts/themes/product-merchandising/variants`.

**Recommendation for the 40-SKU pilot:** Implement **Size Table (No Theme)** now (fastest, lowest risk), then optionally add **Variant Metafields + Theme** later for best UX.

### Option A — Split products by size (finishes-only variants)
**Use when:** You can safely restructure the Shopify catalog and accept new product IDs/URLs.
**Pros:** Product description can safely include size-specific specs.
**Cons:** Requires catalog migration (SEO, collections, ads, GMC grouping), high operational risk.

### Option B — Variant metafields + theme rendering (best long-term UX)
**Use when:** You can modify the Shopify theme and you have a reliable way to write metafield values (Admin API/app).
**Pros:** Size-specific specs display correctly for the selected variant, without duplicating products.
**Cons:** Requires theme work + metafield definition + metafield population pipeline.

### Option C — Size table in `body_html` (no theme changes) **(Recommended for pilot)**
**Use when:** You need correctness fast with minimal storefront changes.
**Pros:** Eliminates misinformation immediately; works with any theme; can be generated from catalog variant rows.
**Cons:** Less “tailored” than per-variant specs, but accurate and scannable.

---

## P0: Launch blockers (must fix)

### Task 1: Add regression test for finish-options “dangling line” artifact

**Files:**
- Modify: `tests/test_finish_injection.py`

**Step 1: Write the failing test**
```python
def test_variant_description_does_not_leave_dangling_finish_options_line(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("FEEDOPS_FINISH_FORWARD_V2", "true")
    base = (
        "Keep towels dry and within reach.\n\n"
        "Highlights:\n"
        "- Reliable wall mount support\n\n"
        "Specs:\n"
        "- Finish options: multiple designer finish options available\n"
        "- Warranty: Limited Lifetime Warranty\n"
    )
    result = generate_variant_description(
        base_description=base,
        finish_name="Antique Brass",
        collection_name="Carolina",
        collection_group="Traditional",
        platform="google",
        size="18 Inch",
    )
    assert "\nmultiple designer finish options available\n" not in result
    assert "- Finish options:" not in result
```

**Step 2: Run test to verify it fails**
Run: `PYTHONPATH=./src .venv/bin/python -m pytest tests/test_finish_injection.py -v`
Expected: FAIL because the current removal logic can leave a naked line.

**Step 3: Commit**
```bash
git add tests/test_finish_injection.py
git commit -m "test: prevent dangling finish-options line in variant descriptions"
```

---

### Task 2: Fix finish-options removal to consume the entire line safely

**Files:**
- Modify: `src/feedops/pipeline/finish_injection.py:541-576`

**Step 1: Make the minimal implementation change**
- Replace prefix-only string replacements with line-aware removal:
  - Remove any line containing “Finish options:” (with optional leading bullet markers) entirely.
  - Remove the exact phrase “multiple designer finish options available” only when it appears as a standalone line artifact.

**Step 2: Run the test**
Run: `PYTHONPATH=./src .venv/bin/python -m pytest tests/test_finish_injection.py::test_variant_description_does_not_leave_dangling_finish_options_line -v`
Expected: PASS

**Step 3: Run full unit suite (quick)**
Run: `PYTHONPATH=./src .venv/bin/python -m pytest -q`
Expected: PASS (or only unrelated failures)

**Step 4: Commit**
```bash
git add src/feedops/pipeline/finish_injection.py
git commit -m "fix: remove finish-options lines without leaving artifacts"
```

---

### Task 3: Add size parsing + size-matrix builder from variant rows (catalog truth)

**Files:**
- Create: `src/feedops/pipeline/size_matrix.py`
- Test: `tests/test_size_matrix.py`

**Step 1: Write failing tests**
```python
from feedops.models.parent_sku import ParentSKU
from feedops.models.variant import Variant
from feedops.pipeline.size_matrix import build_size_matrix

def test_build_size_matrix_groups_by_size_from_option_sku() -> None:
    parent = ParentSKU(
        master_sku="CL-41-18",
        category="Towel Bars",
        current_title="x",
        current_description="x",
        variants=[
            Variant(option_sku="CL-41-18-ABR", finish="Antique Brass", finish_code="ABR", gmc_id="shopify_US_1_1", product_length=20, product_height=3.5, product_width=2, product_weight=2.4, projection=2),
            Variant(option_sku="CL-41-36-ABR", finish="Antique Brass", finish_code="ABR", gmc_id="shopify_US_1_2", product_length=36, product_height=3.5, product_width=2, product_weight=4, projection=2),
        ],
    )
    matrix = build_size_matrix(parent)
    assert [row["size_label"] for row in matrix] == ["18 Inch", "36 Inch"]
    assert matrix[0]["overall"] == "20 × 2 × 3.5 in"
    assert matrix[1]["weight_lb"] == "4"
```

**Step 2: Run test to verify it fails**
Run: `PYTHONPATH=./src .venv/bin/python -m pytest tests/test_size_matrix.py -v`
Expected: FAIL (module missing)

**Step 3: Implement minimal module**
- Parse size as the numeric segment after the second hyphen in `OPTION SKU` (e.g., `CL-41-18-ABR` → `18`).
- Build one row per unique size using representative variant values for `product_length/product_width/product_height/product_weight/projection`.

**Step 4: Run tests**
Run: `PYTHONPATH=./src .venv/bin/python -m pytest tests/test_size_matrix.py -v`
Expected: PASS

**Step 5: Commit**
```bash
git add src/feedops/pipeline/size_matrix.py tests/test_size_matrix.py
git commit -m "feat: build size matrix from variant-level catalog specs"
```

---

### Task 4: Fix Shopify patch generation for multi-size products (Option C: Size Table in body_html)

**Files:**
- Modify: `src/feedops/pipeline/reporter.py` (Shopify patch generation paths)
- Test: `tests/test_pipeline.py`

**Step 1: Add failing tests**
Add a test that:
- Creates a `ParentSKU` whose `variants` include multiple sizes
- Calls `generate_patch_preview(..., platform="shopify")`
- Asserts `body_html`:
  - Does **not** include `Length: 18` (or any single-size “Length:” line)
  - **Does** include a table or list that mentions multiple sizes (e.g., `18 Inch` and `36 Inch`)

Example assertion pattern:
```python
assert "Length:" not in patch["body_html"]
assert "18 Inch" in patch["body_html"] and "36 Inch" in patch["body_html"]
```

**Step 2: Run test to verify it fails**
Run: `PYTHONPATH=./src .venv/bin/python -m pytest tests/test_pipeline.py -v`
Expected: FAIL (Shopify output currently may embed single-size specs).

**Step 3: Implement minimal change**
- Detect multi-size: `len({size_from_option_sku(v.option_sku) for v in parent_sku.variants if size}) > 1`
- Generate Shopify `body_html` with:
  - Benefit-forward intro paragraph
  - 3–5 bullets (no size claims)
  - “Size & Specs” table generated from `build_size_matrix(parent_sku)`

**Step 4: Run tests**
Run: `PYTHONPATH=./src .venv/bin/python -m pytest tests/test_pipeline.py -v`
Expected: PASS

**Step 5: Commit**
```bash
git add src/feedops/pipeline/reporter.py tests/test_pipeline.py
git commit -m "fix: shopify body_html uses size table for multi-size products"
```

---

### Task 5: Fix Google/Bing multi-size variant specs (not just “Length”)

**Files:**
- Modify: `src/feedops/pipeline/finish_injection.py` (variant description generation)
- Test: `tests/test_finish_injection.py` or new `tests/test_variant_specs.py`

**Step 1: Write failing test (CL-41-like)**
- Build a `ParentSKU` + `Variant` with size-dependent `product_length/product_weight`
- Generate a variant description and assert:
  - `Overall dimensions` (or equivalent) matches the variant’s dimensions
  - `Weight` matches the variant’s weight

**Step 2: Implement minimal change**
- Add an optional `variant: Variant | None` argument to `generate_variant_description` (or a new helper that post-processes the Specs block).
- For Google/Bing, when `variant` is provided, replace/update:
  - `Overall dimensions`
  - `Weight`
  - `Projection` / `Depth`
  using the variant’s `product_*` fields.

**Step 3: Run tests**
Run: `PYTHONPATH=./src .venv/bin/python -m pytest tests/test_finish_injection.py -v`
Expected: PASS

**Step 4: Commit**
```bash
git add src/feedops/pipeline/finish_injection.py tests/test_finish_injection.py
git commit -m "fix: hydrate multi-size variant specs from variant row (google/bing)"
```

---

### Task 6: Add offerId existence preflight gate (GMC snapshot)

**Files:**
- Create: `src/feedops/pipeline/offerid_preflight.py`
- Modify: `src/feedops/integrations/google_supplemental.py`
- Test: `tests/test_offerid_preflight.py`

**Step 1: Write failing test**
- Create a temp sqlite DB with `merchant_center_items(offer_id, payload_json, fetched_at)`
- Assert: `offer_id_exists(db_path, offer_id)` returns True/False correctly

**Step 2: Implement helper**
- `offer_id_exists(db_path: Path, offer_id: str) -> bool`

**Step 3: Wire into supplemental writer**
- When loading patches, if `offerId` missing in DB, skip + add to a report list.
- Ensure the process exits non-zero in “strict mode” (env flag), so CI can block launch.

**Step 4: Run tests**
Run: `PYTHONPATH=./src .venv/bin/python -m pytest tests/test_offerid_preflight.py -v`
Expected: PASS

**Step 5: Commit**
```bash
git add src/feedops/pipeline/offerid_preflight.py src/feedops/integrations/google_supplemental.py tests/test_offerid_preflight.py
git commit -m "feat: offerId preflight gate against Merchant Center snapshot"
```

---

## P1: Revenue levers (after P0 gates are green)

### Task 7: Bing title de-spam (dedupe brand, remove synonym tails)

**Files:**
- Modify: `src/feedops/pipeline/selection.py` (or channel-specific normalizer)
- Test: `tests/test_selection.py`

**Step 1: Write failing test**
- Input: `Towel Bar 18-Inch ... | Allied Brass | Towel Bar Holder Rail Bath | Allied Brass`
- Expected: one “Allied Brass” max, and no redundant synonym tail in title

**Step 2: Implement minimal normalizer**
- Remove duplicate brand tokens.
- Enforce max segments (e.g., 4) for Bing titles.

**Step 3: Run tests**
Run: `PYTHONPATH=./src .venv/bin/python -m pytest tests/test_selection.py -v`
Expected: PASS

**Step 4: Commit**
```bash
git add src/feedops/pipeline/selection.py tests/test_selection.py
git commit -m "fix: normalize bing titles (dedupe brand, limit segments)"
```

---

### Task 8: Enforce benefit-first title structure (AGENTS.md alignment)

**Why:** The current LLM system prompt contains conflicting requirements (e.g., “start titles with product type” + “never start titles with adjectives/benefit words”), which undermines AGENTS.md’s benefit-first strategy for niche brands like Allied Brass.

**Files:**
- Modify: `src/feedops/pipeline/prompts.py` (title requirements inside `SYSTEM_PROMPT`)
- Modify: `src/feedops/pipeline/finish_injection.py` (`generate_variant_title` ordering/size insertion)
- Test: `tests/test_finish_injection.py` (or new `tests/test_titles.py`)

**Step 1: Write failing tests (deterministic title injection)**
- Given a base title like: `Towel Bar 18-Inch Solid Brass Wall Mount | Carolina | Allied Brass`
- Assert Google/Bing variant titles:
  - Include size + product type within first ~70 characters
  - Include finish as its own segment near the front (avoid “identical titles except finish at char ~45+”)
  - End with `| Allied Brass`

**Step 2: Update `SYSTEM_PROMPT` title rules**
- Allow material/functional modifiers to lead titles for Allied Brass (e.g., `Solid Brass`, `ADA-Compliant`, `Concealed-Mount`), while still requiring product type within the first 30 characters.
- Remove/soften “NEVER start titles with adjectives or generic benefit words” (keep the ban on fluff like “Premium”, “Luxury”, “High-Quality”).
- Keep pipes and brand-last requirements.

**Step 3: Improve `generate_variant_title` heuristics**
- For multi-size products, insert size as a hyphenated prefix near the product type (e.g., `24-Inch Towel Bar`), not appended at the end of the first segment.
- Keep finish in the second segment for quick visual differentiation.

**Step 4: Run tests**
Run: `PYTHONPATH=./src .venv/bin/python -m pytest -q`
Expected: PASS (or only unrelated failures)

**Step 5: Commit**
```bash
git add src/feedops/pipeline/prompts.py src/feedops/pipeline/finish_injection.py tests/test_finish_injection.py
git commit -m "fix: align title strategy with AGENTS.md (benefit-first, cleaner variants)"
```

---

## Optional (Long-term best UX): Variant metafields + theme rendering (Option B)

> Implement only after P0 gates are green or if you explicitly choose Option B for the pilot.

### Task 9: Define variant metafields for size-specific specs

**Files:**
- Create (in Shopify app repo): `shopify.app.toml` metafield definitions for `ProductVariant`

**Steps:**
1. Define `ProductVariant` metafields for:
   - `specs.overall_dimensions` (string)
   - `specs.weight_lb` (number_decimal or string)
   - `specs.projection_in` (number_decimal)
2. Populate values via Admin API using `metafieldsSet` with `ownerId = gid://shopify/ProductVariant/...`

### Task 10: Theme snippet to display selected variant metafields

**Files (theme repo):**
- Add snippet: `snippets/variant-specs.liquid`
- Modify product section to render it

**Implementation requirements:**
- Use the selected variant per Shopify guidance: `product.selected_or_first_available_variant` (see `/docs/storefronts/themes/product-merchandising/variants`)
- Render metafields from that variant, and update on variant change.

---

## Verification checklist (must pass before “ready”)

Run these locally:
- `PYTHONPATH=./src .venv/bin/python -m pytest -q`
- Scan generated patches for known regressions:
  - No `\nmultiple designer finish options available\n` artifacts in Google/Bing variant descriptions
  - Shopify `body_html` contains no single-size “Length:” lines when multiple sizes exist
  - All exported offerIds exist in `data/feedops.db` (strict mode)

---

## Release plan (pilot safety)

1. Enable strict preflight + regression gates in CI for the pilot branch.
2. Regenerate patches for the 40 pilot SKUs.
3. Run one controlled A/B test (titles-first) before expanding scope.
