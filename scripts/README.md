# Utility Scripts

One-time utility scripts for maintenance tasks.

## Verification Scripts

### `verify_phase_0.sh`

**Purpose**: Run the Phase 0 baseline gate in one command.

**What it runs**:
1. Python test suite (`.venv/bin/pytest -q`)
2. Optional live Supabase canary
3. Dashboard lint + production build (`npm run lint`, `npm run build -- --webpack`)

**Usage**:
```bash
cd /path/to/Allied-FeedOps
bash scripts/verify_phase_0.sh
```

**Supabase canary modes**:
- `RUN_SUPABASE_CANARY=1`: require canary and fail if it fails
- `RUN_SUPABASE_CANARY=0`: skip canary
- default `0`: skip canary for deterministic offline runs
- `RUN_SUPABASE_CANARY=auto`: run only when Supabase credentials are present
- Env loading for verification scripts: `.env.local` (fallback: `dashboard/.env.local`).

### `verify_live_supabase_canary.sh`

**Purpose**: Validate live Supabase runtime dependencies (connectivity + key table/data checks).

**Checks**:
1. Supabase credentials exist (`SUPABASE_URL` + `SUPABASE_KEY` or `SUPABASE_SERVICE_ROLE_KEY`)
2. Core tables are reachable and non-empty (`product_catalog`, `prompt_templates`, `variant_index`)
3. Fixture probe SKU from `samples/eval-skus.json` can be loaded from `product_catalog`
4. Prompt hash lookup works (`get_system_prompt_hash`)

**Usage**:
```bash
cd /path/to/Allied-FeedOps
bash scripts/verify_live_supabase_canary.sh
```

## cleanup_duplicate_media.py

**Purpose**: Remove duplicate Shopify media records that were created during testing.

**When to use**: If lifestyle images appear multiple times on product pages due to duplicate media uploads.

**How it works**:
1. Queries Shopify products that have lifestyle images
2. Groups media by alt text to find duplicates
3. Keeps the first media record, deletes the rest
4. Safely targets only lifestyle images matching pattern "SKU - Finish"

**Usage**:
```bash
cd /path/to/Allied-FeedOps
source .venv/bin/activate
set -a && source .env.local && set +a
python scripts/cleanup_duplicate_media.py
```

**Safety features**:
- Only processes SKUs with existing lifestyle images in database
- Only deletes media with specific alt text patterns
- Requires SHOPIFY_ACCESS_TOKEN and SUPABASE credentials

**Related fix**: `dashboard/src/lib/publishing/shopify-images.ts` now checks for existing media before uploading to prevent future duplicates.
