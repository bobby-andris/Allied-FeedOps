# Technology Stack — v1.2 Impact Debug & Diagnostics

**Project:** Allied FeedOps — Google Shopping Feed Impact Diagnostics
**Researched:** 2026-02-20
**Milestone:** v1.2 (Impact Debug & Fix)
**Confidence:** MEDIUM-HIGH (core APIs verified via official docs; propagation timing from community sources)

> **Scope note:** This document covers only NET NEW tooling needed for v1.2 diagnosing.
> Existing stack (google-ads>=28.4.1, gspread>=6.0, supabase>=2.0, FastAPI, Next.js) is already
> installed. Do not re-install or alter those packages.

---

## Recommended Stack Additions

### Core Technologies — Feed Quality Diagnostics

| Technology | Version | Purpose | Why Recommended |
|------------|---------|---------|-----------------|
| **google-shopping-merchant-products** | Latest (PyPI) | Per-product GMC status + issue audit via Merchant API v1 | Only official Python SDK for the new Merchant API (replaces Content API). Provides `productStatus.itemLevelIssues[]` with `severity`, `code`, `attribute`, `documentation` per product. Content API shuts down August 2026. |
| **google-shopping-merchant-reports** | Latest (PyPI) | Merchant-side impression data, `product_view` queries | `reports.search` with `ProductView` table returns `aggregated_reporting_context_status` — the fastest way to find "NOT_ELIGIBLE_OR_DISAPPROVED" products at scale without paginating every product status. |
| **google-shopping-merchant-issueresolution** | Latest (PyPI) | Programmatic access to GMC diagnostics UI actions | Provides `renderproductissue` with human-readable descriptions; useful for surfacing actionable messages in the Allied Brass dashboard. |

**Why Merchant API not Content API:** Content API v2.1 `productstatuses.list` still works but is deprecated. The new Merchant API packages are the supported path forward. Both use the same OAuth credentials already in GCP secrets.

**Integration point:** Add to `pyproject.toml` dependencies. Auth reuses existing `google-auth>=2.48.0` service account credentials.

```toml
# Add to pyproject.toml [project.dependencies]
"google-shopping-merchant-products>=0.1.0",
"google-shopping-merchant-reports>=0.1.0",
"google-shopping-merchant-issueresolution>=0.1.0",
```

---

### Supporting Libraries — Diagnostics-Specific

| Library | Version | Purpose | When to Use |
|---------|---------|---------|-------------|
| **google-ads** (existing) | >=28.4.1 | `shopping_product` resource for per-product eligibility status linked to Google Ads campaigns | Use GAQL `SELECT shopping_product.status, shopping_product.issues FROM shopping_product WHERE shopping_product.status != 'ELIGIBLE'` — returns products that are IN a shopping campaign but disapproved/limited. Complements GMC-side audit. |
| **pandas** (existing) | >=2.0 | Join GMC issue data with Supabase `variant_index` and `generated_content` tables | Already installed. Use for pivot tables: issue_code → SKU count, severity heatmaps, coverage gap analysis. |
| **rich** (existing) | >=13.0 | CLI diagnostic report rendering | Already installed. Use `rich.table.Table` and `rich.progress` for script output. No new dependency. |
| **httpx** (existing) | >=0.25 | Direct Google Sheets API verification calls | Already installed. Use to fetch and parse live sheet rows to verify content actually made it to the supplemental feed. |

---

### Development Tools — Diagnostic Validation

| Tool | Purpose | Notes |
|------|---------|-------|
| **Google Ads Query Builder** (web) | Construct and validate GAQL queries before coding | https://developers.google.com/google-ads/api/docs/developer-toolkit/gaa-query-builder — free, no install. Use to prototype `shopping_product` and `shopping_performance_view` queries. |
| **Google Ads Query Validator** (web) | Validate GAQL syntax against API schema | https://developers.google.com/google-ads/api/docs/developer-toolkit/gaa-query-validator — validates field selectability before writing Python. |
| **Rich Results Test** (web) | Validate product JSON-LD structured data on Shopify storefront | https://search.google.com/test/rich-results — checks schema.org Product markup for name, image, offers, price. Run against `alliedbrass.com/products/[slug]` to verify Shopify structured data is valid. |
| **GMC Diagnostics UI** (web) | Source of truth for account-level issues before scripting | Check Merchant Center > Products > Diagnostics before building scripts. Confirm issue categories exist. The API mirrors this data. |

---

## GAQL Queries for Impact Diagnostics

These are the specific GAQL patterns to implement in the Python pipeline. All use the existing `google-ads` client.

### 1. Product Eligibility Status Audit

Finds products IN campaigns that are not serving ads. The most direct "why isn't this showing up?" diagnostic.

```sql
SELECT
  shopping_product.resource_name,
  shopping_product.merchant_center_id,
  shopping_product.feed_label,
  shopping_product.item_id,
  shopping_product.status,
  shopping_product.issues
FROM shopping_product
WHERE shopping_product.status != 'ELIGIBLE'
```

**Integration point:** New file `src/feedops/integrations/gmc_product_audit.py`. Call from a new
Cloud Run endpoint `GET /diagnostics/feed-audit` or as a standalone script.

### 2. Impression Share — Where Traffic Is Lost

Answers "are we losing impressions to budget or to rank?" at campaign level.

```sql
SELECT
  campaign.name,
  campaign.id,
  metrics.search_impression_share,
  metrics.search_budget_lost_impression_share,
  metrics.search_rank_lost_impression_share,
  segments.date
FROM campaign
WHERE campaign.advertising_channel_type = 'SHOPPING'
  AND segments.date DURING LAST_30_DAYS
```

**Note:** Impression share is only available at campaign and ad group level (HIGH confidence — confirmed in Google Ads API docs). Not available at product-item level. Join with `shopping_performance_view` by campaign to identify which products are in budget-constrained vs. rank-constrained campaigns.

### 3. Product-Level Performance — Which SKUs Are Actually Serving

```sql
SELECT
  segments.product_item_id,
  segments.product_title,
  segments.product_feed_label,
  metrics.impressions,
  metrics.clicks,
  metrics.cost_micros,
  metrics.conversions,
  metrics.conversions_value
FROM shopping_performance_view
WHERE segments.date DURING LAST_30_DAYS
  AND metrics.impressions > 0
ORDER BY metrics.impressions DESC
LIMIT 500
```

**Integration point:** Compare this list against `generated_content` in Supabase to find the "published but not serving" gap. Join on `segments.product_item_id` = lowercase GMC offer ID.

### 4. Zero-Impression Published SKUs (the core impact gap diagnostic)

No direct GAQL for this — it requires a JOIN at the Python layer:

```python
# Pseudo-code for the diagnostic join
published_skus = supabase.query("SELECT gmc_offer_id FROM batch_sku_assignments WHERE status = 'published'")
serving_skus = google_ads.query(shopping_performance_view_query)  # impressions > 0
zero_impression_published = published_skus - serving_skus
# These are SKUs where content was published but Google isn't showing them
```

---

## GMC Product Status Audit — Merchant API Pattern

Uses `google-shopping-merchant-products` and `google-shopping-merchant-reports`.

### Fast Path: Filter Disapproved via Reports API

Faster than paginating all product statuses. Returns only problem products.

```python
from google.shopping.merchant_reports_v1beta import ReportServiceClient
from google.shopping.merchant_reports_v1beta.types import SearchRequest

client = ReportServiceClient(credentials=credentials)
request = SearchRequest(
    parent=f"accounts/{merchant_id}",
    query="""
        SELECT offer_id, id, title, item_issues
        FROM product_view
        WHERE aggregated_reporting_context_status = 'NOT_ELIGIBLE_OR_DISAPPROVED'
    """,
    page_size=1000,
)
for row in client.search(request=request):
    # row.product_view.offer_id, row.product_view.item_issues
```

### Per-Product Issue Detail (after fast path identifies problem SKUs)

```python
from google.shopping.merchant_products_v1beta import ProductsServiceClient

products_client = ProductsServiceClient(credentials=credentials)
# product_name format: "accounts/{merchant_id}/products/{product_id}"
product = products_client.get_product(name=product_name)
for issue in product.product_status.item_level_issues:
    print(issue.code, issue.severity, issue.attribute, issue.documentation)
```

**Severity values:** `critical` (account suspension risk), `error` (warning, may cause disapproval),
`suggestion` (optimization opportunity). Focus v1.2 fixes on `critical` and `error` first.

---

## Feed Content A/B Testing Approach

**Recommendation:** Manual cohort split using custom labels, not a third-party tool. Reason: Allied Brass has 2,784 SKUs — enough statistical power — and the existing supplemental feed infrastructure supports this without new tooling.

**Pattern (verified by Feedonomics, DataFeedWatch, industry sources):**

1. Split SKUs into two cohorts by modulo of product_id: even = control, odd = test
2. Write different content variants to `custom_label_3` (currently unused) to track cohort
3. Publish test cohort with new content; keep control cohort on old content
4. After 30 days, compare `shopping_performance_view` impressions/CTR/CVR between cohorts
5. Statistical significance: minimum 100 clicks per cohort before drawing conclusions

**No new tool needed.** Implement as a filter in the existing batch publishing flow: `batch_sku_assignments.cohort = 'control' | 'test'`. Add `cohort` column to `batch_sku_assignments` or use `custom_label_3` in the supplemental feed.

**Why not Google's native A/B experiment tool:** Google Ads launched Shopping experiment support (confirmed, searchengineland.com 2024) but it requires Performance Max or Smart Shopping campaigns, not standard Shopping. Allied Brass likely uses standard Shopping — verify before investing in this path.

---

## Content Propagation Verification Stack

**Problem:** After publishing to Google Sheets supplemental feed, how do we know Google ingested it?

### Verification Layers (in order of reliability)

| Layer | Tool | How to Check | Latency |
|-------|------|-------------|---------|
| 1. Google Sheets write confirmation | `gspread` (existing) | Verify row exists with correct content in sheet | Immediate |
| 2. GMC feed fetch status | Merchant API `datasources.list` | Check `lastFetchTime` and `fetchSchedule` on data source | ~1-24 hours |
| 3. GMC product status update | `productstatuses.get` | `googleExpirationDate` advances, `destinationStatuses` changes | 1-3 days |
| 4. Google Ads serving confirmation | `shopping_performance_view` | Impressions appear for product_item_id | 3-7 days |

**Implementation:** Add a `propagation_check` field to `publish_events` table tracking which verification layer has been confirmed. Run as a Cloud Scheduler daily job calling the existing `/api/performance/capture-snapshot` endpoint, extended with GMC status polling.

### Concrete Verification Script Pattern

```python
# src/feedops/integrations/propagation_verifier.py
async def verify_propagation(gmc_offer_ids: list[str]) -> dict:
    """
    Check propagation status for a batch of published SKUs.
    Returns dict of offer_id -> PropagationStatus.
    """
    # Layer 1: sheets check (fast, use existing gspread client)
    sheet_confirmed = await check_google_sheets(gmc_offer_ids)

    # Layer 2: GMC status (use Merchant API products client)
    gmc_confirmed = await check_merchant_center_status(gmc_offer_ids)

    # Layer 3: Ads serving (use existing GAQL shopping_performance_view)
    ads_serving = await check_ads_serving(gmc_offer_ids)

    return {id: PropagationStatus(sheet=s, gmc=g, ads=a)
            for id, s, g, a in zip(gmc_offer_ids, sheet_confirmed, gmc_confirmed, ads_serving)}
```

---

## Structured Data Validation

**For Shopify storefront** (alliedbrass.com): Product schema.org markup affects organic search rich results, not Shopping ads directly. Low priority for impact debugging unless organic traffic is a goal.

**For GMC feed fields:** The relevant "structured" validation is already in the supplemental feed:
- `structured_title` (column M in Google Sheets)
- `structured_description` (column N)

Validate these fields by checking they're non-empty after publish via the existing sheet-read pattern in `google-sheets.ts`.

**If Shopify structured data validation is needed:**
- Tool: Google Rich Results Test (https://search.google.com/test/rich-results) — free, no install
- Check `Product` type, verify `offers.price`, `offers.availability`, `image`, `name` fields
- Run against 5-10 sample product URLs to spot systematic gaps

---

## What NOT to Use

| Avoid | Why | Use Instead |
|-------|-----|-------------|
| **Content API for Shopping v2.1 `productstatuses`** | Deprecated, August 2026 shutdown; same auth overhead as Merchant API | `google-shopping-merchant-products` (Merchant API v1) |
| **Third-party feed auditing SaaS** (DataFeedWatch, Feedonomics, Channable) | Expensive, external, can't join against Supabase data, no programmatic output | Build thin audit script using Merchant API + existing GAQL |
| **Google Optimize / Optimize 360** | Discontinued September 2023 | Custom cohort split via `custom_label_3` in supplemental feed |
| **schema.org validators for impact debugging** | JSON-LD validates HTML page structure; Shopping ads use feed data, not page schema | GMC `productstatuses` API for feed-level validation |
| **BigQuery / Looker Studio** | Overkill for 2,784 SKU dataset; adds infrastructure to maintain | pandas + existing Supabase tables for diagnostic joins |
| **Separate A/B testing infrastructure** | Unnecessary complexity for feed testing | Custom label cohort split in existing supplemental feed |

---

## Installation

Only three new Python packages need to be added for the full diagnostic capability:

```bash
# Add to pyproject.toml then run:
uv pip install google-shopping-merchant-products google-shopping-merchant-reports google-shopping-merchant-issueresolution

# Verify existing packages cover remaining needs:
uv pip show google-ads        # should show >=28.4.1
uv pip show google-api-python-client  # covers Sheets verification
uv pip show supabase          # covers DB joins
```

**No dashboard changes needed** for diagnostic scripts — run as standalone Python scripts in
`src/feedops/scripts/` or as new Cloud Run endpoints.

---

## Alternatives Considered

| Recommended | Alternative | When to Use Alternative |
|-------------|-------------|-------------------------|
| Merchant API `product_view` query (fast path) | Paginate all `productstatuses.list` | When you need complete issue detail for every SKU, not just disapproved ones |
| Custom cohort split via `custom_label_3` | Google Ads Shopping experiments | If Allied Brass migrates to Performance Max campaigns — native experiments work there |
| GAQL `shopping_product` for eligibility | GMC UI manual review | Only for spot-checking 1-2 SKUs; doesn't scale to 2,784 |
| Python scripts in `src/feedops/scripts/` | New Cloud Run endpoints | When diagnostics need to be triggered from the dashboard UI or on a schedule |

---

## Version Compatibility

| Package | Compatible With | Notes |
|---------|-----------------|-------|
| `google-shopping-merchant-products` | `google-auth>=2.48.0` | Uses same OAuth2 credentials as existing Google Ads client |
| `google-shopping-merchant-reports` | `google-auth>=2.48.0` | Same credential chain |
| `google-ads>=28.4.1` (existing) | API v19-v22 | `shopping_product` resource available since v18; use latest API version |
| Merchant API client libraries | Python 3.11+ (project requirement) | Min supported is Python 3.8; project uses 3.11, no conflict |

---

## Sources

- [Google Merchant API — List products data and product issues](https://developers.google.com/merchant/api/guides/products/list-products-data-issues) — MEDIUM confidence (official docs, verified Feb 2026)
- [Issue severity and Merchant Center Diagnostics](https://developers.google.com/shopping-content/guides/how-tos/severity-mapping) — HIGH confidence (official)
- [Google Ads API — Shopping Ads Reporting](https://developers.google.com/google-ads/api/docs/shopping-ads/reporting) — HIGH confidence (official)
- [shopping_product resource fields (v19)](https://developers.google.com/google-ads/api/fields/v19/shopping_product) — HIGH confidence (official)
- [Merchant API Python client libraries](https://developers.google.com/merchant/api/client-libraries/python) — HIGH confidence (official)
- [A/B Testing Product Titles for Google Shopping — Feedonomics](https://feedonomics.com/blog/how-to-ab-test-different-titles-for-google-shopping/) — MEDIUM confidence (verified industry source)
- [Google Ads tests A/B experiments for Shopping product data — Search Engine Land](https://searchengineland.com/google-ads-tests-a-b-experiments-for-shopping-ad-product-data-467644) — MEDIUM confidence (industry news, verify campaign type requirement)
- [PyPI — google-shopping-merchant-products](https://pypi.org/project/google-shopping-merchant-accounts/) — HIGH confidence (official package registry)
- [productstatuses.list — Content API for Shopping](https://developers.google.com/shopping-content/reference/rest/v2.1/productstatuses/list) — HIGH confidence (official, deprecated path for reference)

---

*Stack research for: Google Shopping feed impact diagnostics*
*Researched: 2026-02-20*
*Milestone: v1.2 Impact Debug & Fix*
