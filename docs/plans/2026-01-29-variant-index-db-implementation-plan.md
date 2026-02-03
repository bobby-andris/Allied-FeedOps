# Variant Index DB Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Make variant mapping and size/dimension truth deterministic by indexing catalog + Shopify + Merchant Center at the variant (GMCID) level.

**Architecture:** Create a `variant_index` table keyed by `gmc_id` that stores catalog dimensions + Shopify IDs + normalized SKU fields. The loader can then resolve a `ParentSKU` by Shopify `product_id` (item_group_id) instead of fragile master SKU string formats.

**Tech Stack:** Python 3.11, SQLite (`data/feedops.db`), Pydantic models, existing loader/pipeline modules.

---

### Task 1: Add DB tables for catalog + variant index

**Files:**
- Modify: `src/feedops/db/schema.py`
- Test: `tests/test_db_variant_index.py`

**Step 1: Write failing test**

```python
def test_init_db_creates_variant_index_tables(tmp_path):
    db_path = tmp_path / "feedops.db"
    init_db(db_path)
    conn = get_connection(db_path)
    tables = {row[0] for row in conn.execute("SELECT name FROM sqlite_master WHERE type='table'")}
    assert "variant_index" in tables
    assert "catalog_ingest_state" in tables
```

**Step 2: Run test to verify it fails**

Run: `PYTHONPATH=./src .venv/bin/python -m pytest -q tests/test_db_variant_index.py::test_init_db_creates_variant_index_tables`

Expected: FAIL (missing tables)

**Step 3: Implement minimal tables**

- `variant_index` (keyed by `gmc_id`) with:
  - `master_sku`, `master_sku_norm`, `option_sku`, `option_sku_norm`
  - `finish`, `finish_code`
  - `shopify_product_id`, `shopify_variant_id`
  - `category`, `collection`, `material`
  - `product_length`, `product_width`, `product_height`, `projection`, `product_weight`
  - `shipping_length`, `shipping_width`, `shipping_height`, `shipping_weight`
- `catalog_ingest_state` with `source_path`, `source_mtime`, `ingested_at`

**Step 4: Run test to verify it passes**

Run: `PYTHONPATH=./src .venv/bin/python -m pytest -q tests/test_db_variant_index.py::test_init_db_creates_variant_index_tables`

Expected: PASS

---

### Task 2: Build/refresh variant index from `Product Catalog.csv`

**Files:**
- Create: `src/feedops/db/variant_index.py`
- Modify: `src/feedops/loaders/unified_loader.py`
- Test: `tests/test_variant_index_build.py`

**Step 1: Write failing test**

```python
def test_build_variant_index_writes_rows(tmp_path):
    db_path = tmp_path / "feedops.db"
    init_db(db_path)
    build_variant_index(db_path, Path("data/catalog/Product Catalog.csv"), limit_master_skus=["MB-20"])
    conn = get_connection(db_path)
    count = conn.execute("SELECT COUNT(*) FROM variant_index WHERE master_sku = 'MB-20'").fetchone()[0]
    assert count > 0
```

**Step 2: Run test to verify it fails**

Run: `PYTHONPATH=./src .venv/bin/python -m pytest -q tests/test_variant_index_build.py::test_build_variant_index_writes_rows`

Expected: FAIL (build function missing / no rows)

**Step 3: Implement builder**

- Read catalog via `feedops.loaders.catalog.load_catalog`
- For each row:
  - parse `gmc_id` to Shopify IDs using `feedops.models.variant.parse_gmcid`
  - normalize master/option skus (upper, slash↔hyphen variants, stripped)
  - upsert into `variant_index`
- Store ingest state (catalog mtime)

**Step 4: Run test to verify it passes**

---

### Task 3: Resolve parents by `shopify_product_id` when available

**Files:**
- Modify: `src/feedops/loaders/unified_loader.py`
- Modify: `src/feedops/integrations/shopify_catalog.py`
- Test: `tests/test_unified_loader_product_id_resolution.py`

**Approach**
- If `variant_index` has rows for requested master SKU, get `shopify_product_id`
- Prefer fetching Shopify product via `product(id:)` GraphQL query (stable)
- Build variants list by joining Shopify payload variants to `variant_index` rows (dimensions + finish codes)
- Attach Merchant Center items by `offerId` in `variant_index`

---

### Task 4: Verification + regression checks

**Run:** `PYTHONPATH=./src .venv/bin/python -m pytest -q`

**Manual audit (post-regeneration):**
- No `\", ,\"` in generated titles
- No series-number sizes injected (e.g., `SH-84` not showing `84-Inch`)
- No decimal corruption (e.g., `2.64` becoming `2.20`)
- QN slash/hyphen master SKUs resolve to Shopify data (no cache miss when creds present)

