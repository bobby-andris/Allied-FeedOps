# PROMPT 1: Implement Data Source Migration (CSV → Shopify/GMC + Database)

## Context

Allied FeedOps currently loads product data from a static CSV file (`data/catalog/Product Catalog.csv`). The infrastructure for API-based loading already exists but isn't being used as the primary data source. This needs to be implemented properly.

## Current State

### What EXISTS

- ✅ `src/feedops/integrations/shopify_catalog.py` - GraphQL queries to fetch products from Shopify API
- ✅ `src/feedops/integrations/merchant_center.py` - Google Merchant Center API integration
- ✅ `src/feedops/db/schema.py` - SQLite database with tables for logging and snapshots
- ✅ `src/feedops/cli/sync.py` - `sync_catalog()` function to fetch from Shopify/GMC
- ✅ CLI command: `sync-catalog` exists in `src/feedops/cli/main.py`
- ✅ Database tables: `optimization_runs`, `merchant_center_items`, `content_versions`, `keyword_intent_snapshots`

### What's BROKEN

- ❌ The optimization pipeline (`src/feedops/pipeline/optimize.py`) STILL loads from CSV via `load_catalog(catalog_path)`
- ❌ No automatic sync before optimization runs
- ❌ No unified data loader that checks database → API → CSV fallback
- ❌ `merchant_center_items` table exists but isn't queried during optimization
- ❌ Shopify GraphQL data is written to CSV, then loaded back (inefficient roundtrip)

## Your Task

Implement a proper data loading hierarchy that uses API sources as primary with CSV fallback.

### Part 1: Create Unified Data Loader

**File to create:** `src/feedops/loaders/unified_loader.py`

```python
def load_parent_sku_unified(
    master_sku: str,
    *,
    db_path: Path | str | None = None,
    catalog_path: Path | str | None = None,
    shopify_env: dict | None = None,
    gmc_env: dict | None = None,
    force_refresh: bool = False,
) -> ParentSKU | None:
    """Load ParentSKU with hierarchy: DB cache → Shopify API → GMC API → CSV fallback.
    
    Logic:
    1. If force_refresh=False, check DB cache (timestamp < 24h)
    2. If not in cache or stale, try Shopify API (requires SHOPIFY_* env vars)
    3. Enrich with GMC data if available (requires GMC_* env vars)
    4. Cache result in DB
    5. Fall back to CSV if API calls fail
    
    Returns:
        ParentSKU with all variants and metadata, or None if not found
    """
```

**Key design decisions:**

- Database is a cache with TTL (24 hours), not the source of truth
- Shopify API is primary source for product data
- Google Merchant Center API provides enrichment (keywords, performance data)
- CSV is fallback only for when APIs are unavailable
- Store full JSON payloads in database for debugging/auditing

### Part 2: Database Schema Updates

**File to modify:** `src/feedops/db/schema.py`

**Add tables:**

```sql
CREATE TABLE IF NOT EXISTS shopify_products (
    master_sku TEXT PRIMARY KEY,
    product_id TEXT NOT NULL,
    payload_json TEXT NOT NULL,  -- Full GraphQL response
    fetched_at TEXT NOT NULL,
    ttl_hours REAL DEFAULT 24.0
);

CREATE INDEX IF NOT EXISTS idx_shopify_fetched 
ON shopify_products(fetched_at);
```

**Add functions:**

- `cache_shopify_product(master_sku, product_id, payload, ttl_hours=24)`
- `get_cached_shopify_product(master_sku, max_age_hours=24) -> dict | None`
- `get_cached_merchant_center_items(master_sku) -> list[dict]`

### Part 3: Update Optimization Pipeline

**File to modify:** `src/feedops/pipeline/optimize.py`

**Replace this:**

```python
df = load_catalog(catalog_path)
parent = get_parent_sku(df, master_sku)
```

**With this:**

```python
from feedops.loaders.unified_loader import load_parent_sku_unified

parent = load_parent_sku_unified(
    master_sku,
    db_path=env.get("DATABASE_PATH"),
    catalog_path=catalog_path,
    shopify_env=env,
    gmc_env=env,
    force_refresh=False  # Use cache by default
)
```

### Part 4: CLI Integration

**File to modify:** `src/feedops/cli/main.py`

**Update the optimize command to:**

1. Auto-sync if data is stale (unless `--no-sync` flag)
2. Allow `--force-refresh` to bypass cache
3. Show data source in output (`Data source: Shopify API (cached 2h ago)`)

**Add new command:**

```bash
PYTHONPATH=./src .venv/bin/python -m feedops.cli.main refresh-cache \
  --sku TD-22 \
  --source shopify  # or 'mapi' or 'both'
```

### Part 5: Environment Variables

**File to update:** `.env.example`

```bash
# Data Sources (priority order)
SHOPIFY_STORE_URL=yourstore.myshopify.com
SHOPIFY_ACCESS_TOKEN=shpat_xxx
GMC_MERCHANT_ID=123456789
GMC_API_KEY=/path/to/service-account.json
CATALOG_PATH=data/catalog/Product Catalog.csv  # Fallback only

# Database (for caching API responses)
DATABASE_PATH=data/feedops.db
CACHE_TTL_HOURS=24
```

## Success Criteria

- ✅ **Optimization runs use Shopify API first**: `optimize --parent-sku TD-22` fetches from Shopify, not CSV
- ✅ **Database caching works**: Second run uses cached data (shows "cached 5m ago" message)
- ✅ **Graceful fallback**: If Shopify API fails, falls back to CSV without crashing
- ✅ **GMC enrichment**: Merchant Center data (if available) is merged into ParentSKU
- ✅ **Backward compatibility**: Existing CSV-only workflows still work (for users without API access)
- ✅ **Audit trail**: Database logs show which source was used for each optimization

## Testing Plan

```bash
# Test 1: Fresh Shopify fetch
rm data/feedops.db  # Clear cache
PYTHONPATH=./src .venv/bin/python -m feedops.cli.main optimize --parent-sku "TD-22" --dry-run
# Expected: "Data source: Shopify API (fetched just now)"

# Test 2: Cached data
PYTHONPATH=./src .venv/bin/python -m feedops.cli.main optimize --parent-sku "TD-22" --dry-run
# Expected: "Data source: Shopify API (cached 1m ago)"

# Test 3: Force refresh
PYTHONPATH=./src .venv/bin/python -m feedops.cli.main optimize --parent-sku "TD-22" --force-refresh --dry-run
# Expected: "Data source: Shopify API (fetched just now)"

# Test 4: CSV fallback (no API credentials)
unset SHOPIFY_ACCESS_TOKEN
PYTHONPATH=./src .venv/bin/python -m feedops.cli.main optimize --parent-sku "TD-22" --dry-run
# Expected: "Data source: CSV fallback (data/catalog/Product Catalog.csv)"
```

## Files to Review

- `src/feedops/integrations/shopify_catalog.py` - Shopify GraphQL queries
- `src/feedops/integrations/merchant_center.py` - GMC API client
- `src/feedops/db/schema.py` - Database schema
- `src/feedops/cli/sync.py` - Existing sync logic to build on
- `src/feedops/loaders/catalog.py` - Current CSV loader (keep as fallback)
- `src/feedops/pipeline/optimize.py` - Main pipeline entry point

## Important Notes

- **Do NOT remove CSV support** - it's the fallback for users without API access
- **Cache invalidation**: Use TTL (time-based), not on-demand invalidation
- **Error handling**: API failures should fall back gracefully, not crash
- **Logging**: Use `print()` statements to show data source (user visibility)
- **JSON storage**: Store full API payloads in DB for debugging (use `payload_json TEXT` columns)
# PROMPT 2: Platform Rollout Strategy - Part 1 (Export Pipeline)

## Context

Allied FeedOps generates optimized titles/descriptions and saves them as JSON patches in `dashboard_data/lifestyle-eval-candidate/`. These patches need to be pushed to three platforms: Google Shopping (via supplemental feed), Bing Shopping (via catalog update), and Shopify (via Admin API).

This prompt covers building the export pipeline. Part 2 (monitoring) will be a separate prompt.

## Current State

### What EXISTS

- ✅ JSON patches generated per platform: `{google|bing|shopify}-patch-{SKU}.json`
- ✅ Shopify Admin API integration (`src/feedops/integrations/shopify_catalog.py`)
- ✅ Google Merchant Center API integration (`src/feedops/integrations/merchant_center.py`)
- ✅ Quality scores and approval status in `_meta` field of each patch

### What's MISSING

- ❌ No command to publish approved patches to platforms
- ❌ No supplemental feed generation for Google
- ❌ No Bing catalog update mechanism
- ❌ No Shopify GraphQL mutations for product updates
- ❌ No rollback mechanism if content performs poorly
- ❌ No staging/preview before production push

## Your Task
Design and implement a multi-stage rollout pipeline with safety controls.

Part 1: Publish Command Structure
File to create: src/feedops/cli/publish.py

Create a publish command with these options:


# Dry run (show what would be published)
PYTHONPATH=./src .venv/bin/python -m feedops.cli.main publish \
  --sku TD-22 \
  --platform google \
  --dry-run

# Publish to staging (Google supplemental feed with test label)
PYTHONPATH=./src .venv/bin/python -m feedops.cli.main publish \
  --sku TD-22 \
  --platform google \
  --environment staging

# Publish to production
PYTHONPATH=./src .venv/bin/python -m feedops.cli.main publish \
  --sku TD-22 \
  --platform google \
  --environment production \
  --require-approval  # Only publish if status=APPROVED

# Batch publish (all approved patches)
PYTHONPATH=./src .venv/bin/python -m feedops.cli.main publish \
  --platform google \
  --environment staging \
  --batch \
  --min-score 80.0  # Only SKUs with score ≥ 80%

# Rollback (revert to original content)
PYTHONPATH=./src .venv/bin/python -m feedops.cli.main rollback \
  --sku TD-22 \
  --platform google
Part 2: Google Shopping - Supplemental Feed
File to create: src/feedops/integrations/google_supplemental.py

Strategy: Use Google Merchant Center Supplemental Feeds to override titles/descriptions without changing the primary feed.


def generate_supplemental_feed(
    patches: list[dict],
    environment: str = "staging"
) -> str:
    """Generate Google Merchant Center supplemental feed XML.
    
    Args:
        patches: List of google-patch-*.json files
        environment: 'staging' or 'production'
    
    Returns:
        XML string in Google Merchant Center format
        
    Format:
        <?xml version="1.0"?>
        <rss version="2.0" xmlns:g="http://base.google.com/ns/1.0">
          <channel>
            <title>Allied Brass FeedOps - Supplemental Feed (Staging)</title>
            <item>
              <g:id>shopify_US_7721863643362_42804912849122</g:id>
              <g:title><![CDATA[Traditional Retractable Wall Hook | 2-1/2-Inch Extension | Brass Wall Mount | Allied Brass]]></g:title>
              <g:description><![CDATA[Need a place to hang towels...]]></g:description>
              <g:custom_label_4>feedops-staging</g:custom_label_4>
            </item>
          </channel>
        </rss>
    """
File to create: src/feedops/integrations/google_feed_upload.py


def upload_supplemental_feed(
    feed_xml: str,
    feed_name: str = "feedops-supplemental",
    merchant_id: str | None = None
) -> dict:
    """Upload supplemental feed to Google Merchant Center via Content API.
    
    Uses: https://developers.google.com/shopping-content/reference/rest/v2.1/datafeeds
    """
Deployment:

Generate supplemental feed XML from approved patches
Upload to GMC via Datafeeds API
Use custom_label_4 = "feedops-staging" or "feedops-production" for tracking
Feed updates propagate within 24-48 hours
Part 3: Shopify - GraphQL Product Updates
File to modify: src/feedops/integrations/shopify_catalog.py

Add mutation function:


SHOPIFY_UPDATE_PRODUCT_MUTATION = """
mutation UpdateProduct($input: ProductInput!) {
  productUpdate(input: $input) {
    product {
      id
      title
      descriptionHtml
    }
    userErrors {
      field
      message
    }
  }
}
"""

def update_shopify_product(
    product_id: str,
    title: str,
    description_html: str,
    *,
    store_url: str,
    access_token: str,
    dry_run: bool = False
) -> dict:
    """Update Shopify product title and description via Admin API.
    
    Args:
        product_id: Shopify product GID (e.g., "gid://shopify/Product/7721863643362")
        title: New product title
        description_html: New HTML description
        store_url: yourstore.myshopify.com
        access_token: Shopify Admin API token
        dry_run: If True, validate but don't execute
        
    Returns:
        Response dict with success status and any errors
        
    Notes:
        - Shopify updates propagate immediately to storefront
        - Use with caution - no rollback mechanism
        - Consider creating a product duplicate for A/B testing
    """
Strategy:

Staging: Update product tags with feedops-test-content before changing title/description
Production: Direct GraphQL mutation to update title/descriptionHtml
Rollback: Store original content in _previous field (already done in patches)
Part 4: Bing Shopping - Merchant Center Catalog
File to create: src/feedops/integrations/bing_catalog.py

Strategy: Bing uses Bing Merchant Center with catalog feeds similar to Google.


def generate_bing_catalog_feed(
    patches: list[dict],
    environment: str = "staging"
) -> str:
    """Generate Bing Merchant Center catalog feed XML.
    
    Bing doesn't support supplemental feeds, so this generates a FULL feed
    with only the updated products. You'll need to merge this with your
    existing feed or use Bing's API to update individual items.
    
    Format: Similar to Google Shopping XML but with Bing-specific namespaces
    Ref: https://help.ads.microsoft.com/#apex/ads/en/51084/1
    """

def update_bing_catalog_item(
    offer_id: str,
    title: str,
    description: str,
    *,
    merchant_id: str,
    access_token: str
) -> dict:
    """Update single catalog item via Bing Content API.
    
    Uses: https://learn.microsoft.com/en-us/advertising/shopping-content/manage-products
    """
Deployment:

Option 1: Generate full feed and re-upload to Bing Merchant Center (batch)
Option 2: Use Content API for individual item updates (slower but safer)
Recommendation: Use full feed for batch updates (weekly), API for urgent fixes
Part 5: Rollback Mechanism
File to create: src/feedops/rollback.py


def rollback_content(
    sku: str,
    platform: str,
    *,
    patches_dir: Path,
    db_path: Path
) -> None:
    """Revert product content to original version.
    
    Process:
    1. Load patch file's `_previous` field (original content)
    2. Push original content back to platform
    3. Log rollback event in database
    4. Mark patch as "rolled_back" status
    """
Part 6: Database Logging
File to modify: src/feedops/db/schema.py

Add table:


CREATE TABLE IF NOT EXISTS publish_events (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    master_sku TEXT NOT NULL,
    platform TEXT NOT NULL,  -- 'google', 'bing', 'shopify'
    environment TEXT NOT NULL,  -- 'staging', 'production'
    action TEXT NOT NULL,  -- 'publish', 'rollback'
    patch_file TEXT NOT NULL,
    quality_score REAL,
    approval_status TEXT,
    status TEXT NOT NULL,  -- 'success', 'failed', 'pending'
    error_message TEXT,
    published_at TEXT NOT NULL,
    published_by TEXT,  -- Username or 'cli' or 'api'
    rollback_id INTEGER,  -- Reference to rollback event if reverted
    FOREIGN KEY (rollback_id) REFERENCES publish_events(id)
);

CREATE INDEX IF NOT EXISTS idx_publish_sku_platform 
ON publish_events(master_sku, platform, published_at DESC);
Success Criteria
Staging rollout works: publish --environment staging updates content with test label
Production requires approval: publish --environment production fails if approval_status != "approved"
Dry run shows diff: publish --dry-run displays current vs. new content side-by-side
Batch publish safe: publish --batch --min-score 80 only publishes SKUs meeting threshold
Rollback functional: rollback --sku TD-22 --platform google reverts to original
Audit trail complete: Database logs every publish/rollback with timestamp, user, status
Testing Plan

# Test 1: Dry run (no changes)
PYTHONPATH=./src .venv/bin/python -m feedops.cli.main publish \
  --sku TD-22 --platform google --dry-run

# Test 2: Staging publish
PYTHONPATH=./src .venv/bin/python -m feedops.cli.main publish \
  --sku TD-22 --platform google --environment staging

# Test 3: Production publish (should require approval)
PYTHONPATH=./src .venv/bin/python -m feedops.cli.main publish \
  --sku TD-22 --platform google --environment production

# Test 4: Batch publish (multiple SKUs)
PYTHONPATH=./src .venv/bin/python -m feedops.cli.main publish \
  --platform shopify --environment staging --batch --min-score 85

# Test 5: Rollback
PYTHONPATH=./src .venv/bin/python -m feedops.cli.main rollback \
  --sku TD-22 --platform google

# Test 6: Check publish history
PYTHONPATH=./src .venv/bin/python -m feedops.cli.main publish-history \
  --sku TD-22
Platform-Specific Notes
Google Shopping
✅ Supplemental feeds are the safest approach (non-destructive, easy rollback)
⏱️ Propagation time: 24-48 hours
🔧 API: Content API v2.1 Datafeeds endpoint
📊 Tracking: Use custom_label_4 for cohort analysis
Shopify
⚠️ Direct updates (no supplemental feed option)
⏱️ Propagation time: Immediate
🔧 API: Admin GraphQL API (productUpdate mutation)
📊 Tracking: Use product tags or metafields
Bing Shopping
⚠️ Full feed replacement or Content API updates
⏱️ Propagation time: 4-24 hours
🔧 API: Bing Content API
📊 Tracking: Use custom labels in feed
Files to Create/Modify
Create: src/feedops/cli/publish.py - CLI commands
Create: src/feedops/integrations/google_supplemental.py - Supplemental feed generation
Create: src/feedops/integrations/google_feed_upload.py - GMC upload
Create: src/feedops/integrations/bing_catalog.py - Bing feed generation
Create: src/feedops/rollback.py - Rollback logic
Modify: src/feedops/integrations/shopify_catalog.py - Add update mutations
Modify: src/feedops/db/schema.py - Add publish_events table
Modify: src/feedops/cli/main.py - Register new commands
# PROMPT 3: Platform Rollout Strategy - Part 2 (Monitoring & Performance)

## Context

After publishing optimized content to platforms (see Part 1), we need to monitor performance to determine if the changes improved CTR, CVR, and ROAS. This requires fetching platform-specific metrics, comparing against baselines, and automating rollback decisions.

## Your Task

Build a monitoring and performance analysis system to measure the impact of FeedOps-generated content.

### Part 1: Performance Metrics Database

**File to modify:** `src/feedops/db/schema.py`

**Add tables:**

```sql
CREATE TABLE IF NOT EXISTS performance_snapshots (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    master_sku TEXT NOT NULL,
    platform TEXT NOT NULL,
    environment TEXT NOT NULL,
    snapshot_date TEXT NOT NULL,  -- ISO date (YYYY-MM-DD)
    
    -- Traffic metrics
    impressions INTEGER DEFAULT 0,
    clicks INTEGER DEFAULT 0,
    ctr REAL DEFAULT 0.0,
    
    -- Conversion metrics
    conversions INTEGER DEFAULT 0,
    conversion_value REAL DEFAULT 0.0,
    cvr REAL DEFAULT 0.0,
    
    -- Cost metrics
    cost REAL DEFAULT 0.0,
    cpc REAL DEFAULT 0.0,
    roas REAL DEFAULT 0.0,
    
    -- Content tracking
    publish_event_id INTEGER,
    content_version TEXT,  -- 'original' or 'feedops-v1', 'feedops-v2', etc.
    days_since_publish INTEGER,
    
    fetched_at TEXT NOT NULL,
    FOREIGN KEY (publish_event_id) REFERENCES publish_events(id)
);

CREATE INDEX IF NOT EXISTS idx_snapshots_sku_platform_date
ON performance_snapshots(master_sku, platform, snapshot_date DESC);

CREATE TABLE IF NOT EXISTS performance_baselines (
    master_sku TEXT NOT NULL,
    platform TEXT NOT NULL,
    baseline_start_date TEXT NOT NULL,
    baseline_end_date TEXT NOT NULL,
    
    avg_impressions REAL,
    avg_clicks REAL,
    avg_ctr REAL,
    avg_conversions REAL,
    avg_conversion_value REAL,
    avg_cvr REAL,
    avg_cost REAL,
    avg_roas REAL,
    
    created_at TEXT NOT NULL,
    PRIMARY KEY (master_sku, platform)
);
```

### Part 2: Google Ads Performance API Integration

**File to create:** `src/feedops/integrations/google_ads_performance.py`

```python
def fetch_product_performance(
    master_sku: str,
    start_date: str,  # YYYY-MM-DD
    end_date: str,
    *,
    customer_id: str,
    merchant_id: str
) -> dict:
    """Fetch Google Shopping performance metrics via Google Ads API.
    
    Uses: Google Ads API shopping_performance_view
    Ref: https://developers.google.com/google-ads/api/fields/v16/shopping_performance_view
    
    Returns:
        {
            'impressions': 1234,
            'clicks': 56,
            'ctr': 0.0454,
            'conversions': 3,
            'conversion_value': 127.50,
            'cost': 45.67,
            'roas': 2.79
        }
    """
```

**GAQL Query to use:**

```sql
SELECT
  segments.product_item_id,
  segments.date,
  metrics.impressions,
  metrics.clicks,
  metrics.ctr,
  metrics.conversions,
  metrics.conversions_value,
  metrics.cost_micros
FROM shopping_performance_view
WHERE
  segments.product_item_id = 'shopify_US_7721863643362_42804912849122'
  AND segments.date BETWEEN '2026-01-01' AND '2026-01-31'
```

### Part 3: Shopify Analytics Integration

**File to create:** `src/feedops/integrations/shopify_analytics.py`

```python
def fetch_shopify_product_analytics(
    product_id: str,
    start_date: str,
    end_date: str,
    *,
    store_url: str,
    access_token: str
) -> dict:
    """Fetch Shopify product analytics via Admin API.
    
    Uses: Shopify Analytics API
    Ref: https://shopify.dev/docs/api/admin-graphql/latest/queries/productViews
    
    Returns:
        {
            'views': 456,
            'add_to_carts': 23,
            'purchases': 5,
            'revenue': 267.50,
            'conversion_rate': 0.011  # views → purchases
        }
    """
```

### Part 4: Performance Comparison CLI

**File to create:** `src/feedops/cli/performance.py`

**Add commands:**

```bash
# Fetch baseline (before FeedOps content)
PYTHONPATH=./src .venv/bin/python -m feedops.cli.main performance baseline \
  --sku TD-22 \
  --platform google \
  --start 2025-12-01 \
  --end 2025-12-31

# Fetch current performance (after FeedOps content)
PYTHONPATH=./src .venv/bin/python -m feedops.cli.main performance fetch \
  --sku TD-22 \
  --platform google \
  --start 2026-01-15 \
  --end 2026-01-27

# Compare performance (baseline vs. current)
PYTHONPATH=./src .venv/bin/python -m feedops.cli.main performance compare \
  --sku TD-22 \
  --platform google

# Batch report (all published SKUs)
PYTHONPATH=./src .venv/bin/python -m feedops.cli.main performance report \
  --platform google \
  --min-days 14  # Only SKUs published ≥14 days ago (statistical significance)
```

**Output format:**

```
Performance Report: TD-22 (Google Shopping)
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

Baseline (Dec 1-31, 2025):
  Impressions: 1,234  |  Clicks: 56  |  CTR: 4.54%
  Conversions: 3      |  Value: $127.50  |  ROAS: 2.79

Current (Jan 15-27, 2026):
  Impressions: 1,456  |  Clicks: 89  |  CTR: 6.11%  ⬆ +34.6%
  Conversions: 6      |  Value: $287.40  |  ROAS: 4.21  ⬆ +50.9%

Verdict: ✅ WINNER (CTR +34.6%, ROAS +50.9%)
Recommendation: Keep FeedOps content, expand to similar SKUs
```

### Part 5: Automated Performance Monitoring

**File to create:** `src/feedops/monitoring/auto_review.py`

```python
def auto_review_performance(
    *,
    platform: str,
    min_days_since_publish: int = 14,
    rollback_threshold: float = -0.15,  # -15% ROAS = auto-rollback
    db_path: Path
) -> list[dict]:
    """Automatically review all published SKUs and flag underperformers.
    
    Process:
    1. Query publish_events for SKUs published ≥ min_days ago
    2. Fetch current performance from platform APIs
    3. Compare to baseline (from performance_baselines table)
    4. Flag SKUs with ROAS decline > rollback_threshold
    5. Generate recommendations: 'keep', 'monitor', 'rollback'
    
    Returns:
        List of dicts with SKU, platform, delta_roas, recommendation
    """
```

**Cron job setup:**

```bash
# Daily monitoring (add to crontab)
0 6 * * * PYTHONPATH=./src .venv/bin/python -m feedops.cli.main performance auto-review --platform google >> /var/log/feedops-monitor.log 2>&1
```

### Part 6: Dashboard Integration (Streamlit)

**File to create:** `streamlit_app_performance.py`

```python
import streamlit as st
from feedops.db.schema import get_connection

st.title("FeedOps Performance Dashboard")

# Filters
platform = st.selectbox("Platform", ["google", "bing", "shopify"])
min_days = st.slider("Min days since publish", 7, 60, 14)

# Query performance data
conn = get_connection("data/feedops.db")
query = """
SELECT 
    p.master_sku,
    p.platform,
    p.published_at,
    ps.ctr,
    ps.roas,
    pb.avg_ctr as baseline_ctr,
    pb.avg_roas as baseline_roas,
    (ps.ctr - pb.avg_ctr) / pb.avg_ctr * 100 as ctr_delta_pct,
    (ps.roas - pb.avg_roas) / pb.avg_roas * 100 as roas_delta_pct
FROM publish_events p
JOIN performance_snapshots ps ON p.id = ps.publish_event_id
JOIN performance_baselines pb ON p.master_sku = pb.master_sku AND p.platform = pb.platform
WHERE p.platform = ?
  AND julianday('now') - julianday(p.published_at) >= ?
ORDER BY roas_delta_pct DESC
"""
df = pd.read_sql(query, conn, params=(platform, min_days))

# Display charts
st.metric("Avg CTR Delta", f"{df['ctr_delta_pct'].mean():.1f}%")
st.metric("Avg ROAS Delta", f"{df['roas_delta_pct'].mean():.1f}%")

st.dataframe(df)
```

### Part 7: Statistical Significance Testing

**File to create:** `src/feedops/monitoring/significance.py`

```python
from scipy import stats

def test_significance(
    baseline_conversions: int,
    baseline_impressions: int,
    test_conversions: int,
    test_impressions: int,
    confidence_level: float = 0.95
) -> dict:
    """Run chi-square test to determine if performance change is significant.
    
    Returns:
        {
            'p_value': 0.023,
            'is_significant': True,
            'confidence': 0.95,
            'test_type': 'chi_square'
        }
    """
```

## Success Criteria

- ✅ **Baseline capture works**: `performance baseline` stores pre-FeedOps metrics
- ✅ **Current metrics fetch**: `performance fetch` pulls latest data from Google Ads API
- ✅ **Comparison reports accurate**: `performance compare` shows delta percentages with statistical significance
- ✅ **Batch reporting functional**: `performance report` generates summary for all SKUs
- ✅ **Auto-review flags underperformers**: `performance auto-review` identifies SKUs with declining ROAS
- ✅ **Dashboard visualizes trends**: Streamlit app shows performance over time with charts

## Testing Plan

```bash
# Test 1: Capture baseline
PYTHONPATH=./src .venv/bin/python -m feedops.cli.main performance baseline \
  --sku TD-22 --platform google --start 2025-12-01 --end 2025-12-31

# Test 2: Fetch current metrics
PYTHONPATH=./src .venv/bin/python -m feedops.cli.main performance fetch \
  --sku TD-22 --platform google --start 2026-01-15 --end 2026-01-27

# Test 3: Compare performance
PYTHONPATH=./src .venv/bin/python -m feedops.cli.main performance compare \
  --sku TD-22 --platform google

# Test 4: Batch report
PYTHONPATH=./src .venv/bin/python -m feedops.cli.main performance report \
  --platform google --min-days 14

# Test 5: Auto-review
PYTHONPATH=./src .venv/bin/python -m feedops.cli.main performance auto-review \
  --platform google --rollback-threshold -0.20

# Test 6: Launch Streamlit dashboard
streamlit run streamlit_app_performance.py
```

## Files to Create/Modify

**Create:**
- `src/feedops/integrations/google_ads_performance.py` - Google Ads metrics
- `src/feedops/integrations/shopify_analytics.py` - Shopify analytics
- `src/feedops/cli/performance.py` - CLI commands
- `src/feedops/monitoring/auto_review.py` - Automated monitoring
- `src/feedops/monitoring/significance.py` - Statistical tests
- `streamlit_app_performance.py` - Performance dashboard

**Modify:**
- `src/feedops/db/schema.py` - Add performance tables

## API Requirements

**Add to `.env`:**

```bash
# Google Ads API (for performance metrics)
GOOGLE_ADS_CLIENT_ID=xxx
GOOGLE_ADS_CLIENT_SECRET=xxx
GOOGLE_ADS_REFRESH_TOKEN=xxx
GOOGLE_ADS_DEVELOPER_TOKEN=xxx
GOOGLE_ADS_CUSTOMER_ID=123-456-7890

# Shopify Analytics API (already have store URL + token)
SHOPIFY_STORE_URL=yourstore.myshopify.com
SHOPIFY_ACCESS_TOKEN=shpat_xxx

# Bing Ads API (if needed)
BING_ADS_DEVELOPER_TOKEN=xxx
BING_ADS_CUSTOMER_ID=xxx
```

---

## Implementation Roadmap

These three prompts provide a comprehensive implementation plan. Use them sequentially:

1. **First**: Update README (already provided above)
2. **Second**: Implement data source migration (Prompt 1)
3. **Third**: Build export pipeline (Prompt 2)
4. **Fourth**: Add monitoring system (Prompt 3)

Each prompt is self-contained and can be executed independently.