# Utility Scripts

One-time utility scripts for maintenance tasks.

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
set -a && source .env.vercel && set +a
python scripts/cleanup_duplicate_media.py
```

**Safety features**:
- Only processes SKUs with existing lifestyle images in database
- Only deletes media with specific alt text patterns
- Requires SHOPIFY_ACCESS_TOKEN and SUPABASE credentials

**Related fix**: `dashboard/src/lib/publishing/shopify-images.ts` now checks for existing media before uploading to prevent future duplicates.
