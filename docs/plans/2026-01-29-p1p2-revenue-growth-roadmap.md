# FeedOps Revenue Growth Roadmap (P1/P2) Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use `superpowers:executing-plans` to implement this plan task-by-task.

**Goal:** Improve Shopping/PMax performance by making titles more click-worthy and less cannibalizing, making Bing output more literal/clean, and enabling controlled experiments + policy-safe AI disclosures without breaking the dashboard or pipeline.

**Architecture:** Keep all changes additive, behind flags where behavior changes could affect production. Prefer validators + deterministic labeling so failures are caught pre-publish and experiments are measurable via `custom_label_*` in Google/Microsoft.

**Tech Stack:** Python (`src/feedops/*`), pytest, XML feed generators (`src/feedops/integrations/*`), patch JSON inputs, CLI publish flows (`src/feedops/cli/publish.py`).

---

## P1 (High leverage, low risk): Stop cannibalization + improve measurement

### Evidence update (2026-01-29): finish terms often lead queries

From Google Ads search term data (customer `6253381786`, `2025-10-01` → `2026-01-28`), high-impression finish-specified queries frequently start with the finish/material phrase, e.g.:
- `polished nickel paper towel holder` (1,353 impressions)
- `unlacquered brass toilet paper holder` (1,152 impressions)
- `unlacquered brass towel ring` (960 impressions)
- `unlacquered brass towel bar` (933 impressions)

Implication: for many categories, “finish-first” is not a stylistic choice — it mirrors how users search. The roadmap below treats **finish placement in the first ~70 characters as a first-class constraint** (tested via experiment labels), rather than assuming finish should always be last.

### Task 1: Add a “variant cannibalization” validator (title uniqueness + differentiator position)

**Why:** 100+ finish/size variants with near-identical titles reduce relevance signals, make shopping listings harder to scan, and make performance analysis ambiguous.

**Files:**
- Modify: `src/feedops/pipeline/validators.py`
- Modify: `src/feedops/pipeline/validators.py` (wire into `validate_candidate_content_full`)
- Test: `tests/test_variant_title_uniqueness.py`

**Step 1: Write the failing test**

Create `tests/test_variant_title_uniqueness.py` with a minimal “candidate-like” structure and a helper that calls the new validator:

```python
from feedops.pipeline.validators import validate_variant_title_uniqueness


def test_flags_duplicate_variant_titles_when_only_finish_changes_too_late():
    titles = [
        "24-Inch Wall Mount Towel Bar, Solid Brass, Allied Brass, Satin Nickel",
        "24-Inch Wall Mount Towel Bar, Solid Brass, Allied Brass, Polished Chrome",
    ]
    warnings = validate_variant_title_uniqueness(titles)
    assert any("variant" in w.lower() for w in warnings)
```

**Step 2: Run test to verify it fails**

Run: `PYTHONPATH=./src .venv/bin/python -m pytest -q tests/test_variant_title_uniqueness.py`
Expected: FAIL (function not found or no warning generated).

**Step 3: Write minimal implementation**

Implement `validate_variant_title_uniqueness(titles: list[str]) -> list[str]`:
- Normalize titles (lowercase; strip punctuation; collapse whitespace).
- Create a “core signature” by removing known finish tokens (from finish metadata) and brand token.
- Warn if multiple titles share the same core signature.
- Warn if the differentiator token (finish and/or size) occurs after character 70.
  - For products with finishes, prefer **finish** to appear in the first 70 characters.
  - For products with multiple sizes, prefer the **size** to appear in the first 70 characters.
  - Do not require finish to be the first token; instead require it to be **early enough to be visible** and to match common query patterns.

**Step 4: Run test to verify it passes**

Run: `PYTHONPATH=./src .venv/bin/python -m pytest -q tests/test_variant_title_uniqueness.py`
Expected: PASS.

**Step 5: Run full suite**

Run: `PYTHONPATH=./src .venv/bin/python -m pytest -q`
Expected: All tests pass.

---

### Task 2: Add deterministic experiment labels (control vs treatment) via `custom_label_3`

**Why:** If we can’t reliably segment variants in Ads/MC, we can’t learn quickly. Deterministic labels let us run a single test across 40 SKUs without breaking reporting.

**Files:**
- Modify: `src/feedops/integrations/google_supplemental.py`
- Modify: `src/feedops/integrations/bing_catalog.py`
- Test: `tests/test_custom_label_experiment.py`
- Doc: `docs/ops/experiments-via-custom-labels.md`

**Step 1: Write failing test**

Create `tests/test_custom_label_experiment.py` to assert:
- When `FEEDOPS_EXPERIMENT_LABEL=title_v2` is set, feed items include `custom_label_3=title_v2-control|title_v2-treatment` (deterministic).
- Distribution is stable across runs (hash-based).

**Step 2: Run test to verify it fails**

Run: `PYTHONPATH=./src .venv/bin/python -m pytest -q tests/test_custom_label_experiment.py`
Expected: FAIL.

**Step 3: Implement minimal labeling**

Add:
- Env var `FEEDOPS_EXPERIMENT_LABEL` (string; empty disables).
- Deterministic assignment: `hash(offerId) % 2` (stable hashing; avoid Python’s randomized hash).
- Emit `custom_label_3` in both Google supplemental and Bing feed generators.

**Step 4: Run tests**

Run: `PYTHONPATH=./src .venv/bin/python -m pytest -q tests/test_custom_label_experiment.py`
Expected: PASS.

**Step 5: Document usage**

Create `docs/ops/experiments-via-custom-labels.md`:
- How to create listing groups by `custom_label_3`
- How to read results (CTR/CVR/CPA guardrails)

---

## P2 (High impact, moderate risk): Fix the “trust inputs” that beat copy

### Task 2.5 (Optional, low risk): Use collection descriptions to improve on-site trust (Shopify-first)

**Why:** Collection names are not heavily searched in Google Ads query data, but they can increase on-site trust and help shoppers understand the design intent (“clean square geometry”, “traditional elegance”) when they’re comparing similar SKUs.

**Source of truth:** `data/Collection_Descriptions_Complete_All_41_20260124.csv`

**Files (likely):**
- Modify: `src/feedops/pipeline/enrichment.py` (attach collection description fields to candidate evidence)
- Modify: `src/feedops/pipeline/prompts.py` (allow using the collection description as a *verifiable* style cue)
- Test: `tests/test_collection_description_usage.py`

**Rules:**
- Collection **name** may be appended late in titles (after the core query zone), but do not sacrifice finish/size visibility in the first ~70 characters.
- Collection **description** may be used in Shopify descriptions as a brief “Design notes” section, but must not invent materials/features.

### Task 3: Add GTIN/MPN/identifier coverage auditing (preflight report)

**Why:** Merchant trust + product identity drives matching, aggregation, and approval stability. Missing GTIN/MPN doesn’t just lower match coverage; it can block “same product” clustering and suppress performance.

**Files:**
- Modify: `src/feedops/pipeline/reporter.py` (or new report module)
- Modify: `src/feedops/cli/publish.py` (emit report path)
- Test: `tests/test_identifier_preflight_report.py`
- Doc: `docs/ops/identifier-preflight.md`

**Steps:**
1. Add a preflight that counts missing GTIN/MPN by platform patch.
2. Fail “production publish” if missing rate crosses a threshold (flagged by env var to avoid breaking current workflows).
3. Output CSV for merchants/ops to fix upstream catalog.

---

### Task 4: AI lifestyle image safety + compliance (metadata + “additional image only” policy)

**Why:** Lifestyle images can lift CTR, but “fake-looking” or non-identical images destroy trust and can create policy risk. Google’s AI image disclosure requirement adds a technical compliance burden.

**Files:**
- Modify: `src/feedops/pipeline/lifestyle_images.py`
- Modify: `src/feedops/pipeline/sync_images_to_patches.py`
- Modify: `src/feedops/integrations/google_supplemental.py` (optional: emit `lifestyle_image_link`)
- Test: `tests/test_ai_image_metadata.py`
- Doc: `docs/ops/ai-images-compliance.md`

**Steps:**
1. Add a “primary vs additional” rule in patch generation: AI images are only appended as additional images.
2. Add a metadata step to embed IPTC/XMP DigitalSourceType where feasible (tooling decision required; prefer `exiftool` if available).
3. Add a visual QA gate: reject images where the product silhouette differs from the base product image beyond a threshold (simple perceptual hash / SSIM heuristic).

---

## Measurement + expected revenue impact (how we’ll know)

### Single best test to run first (P1)

**Hypothesis (Shopping CTR):**
Because shoppers scan the first ~70 characters and Google weights early tokens, we believe “clean punctuation + early finish/size tokens aligned to query patterns” titles will increase CTR and reduce wasted clicks.

**Variant ordering to test (based on evidence):**
- Treatment A (finish-first): `[Finish] [Product Type], [Key Dimension], …`
- Treatment B (type-first): `[Product Type], [Key Dimension], [Finish], …`

**Primary metric:** Shopping CTR (SKU-level)
**Secondary metrics:** conversion rate, CPC/CPA
**Guardrails:** refund/return rate, “wrong size” support tickets, bounce rate

**Sizing (rough):**
At ~0.28% sitewide CVR, tests must run long enough to detect small lifts; prioritize CTR-first tests (higher signal, faster).

---

## Commands (verification)

- Run unit tests: `PYTHONPATH=./src .venv/bin/python -m pytest -q`
- Run targeted tests: `PYTHONPATH=./src .venv/bin/python -m pytest -q tests/<file>.py`
