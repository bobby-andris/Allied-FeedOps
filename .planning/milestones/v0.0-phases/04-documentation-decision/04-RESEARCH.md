# Phase 4: Documentation & Decision - Research

**Researched:** 2026-02-13
**Domain:** Technical API documentation and decision framework synthesis
**Confidence:** HIGH

## Summary

Phase 4 synthesizes 3 completed discovery phases (Phases 1-3) into comprehensive API reference documentation and a Go/No-Go recommendation for backfill execution. The primary challenge is consolidating 2.1MB of discovery data (335KB + 7.4KB + 313KB + 1.4MB across 4 JSON files), 8 Python scripts (2,171 total lines), and 15 prior decisions into a single actionable reference document.

This is a **documentation synthesis task**, not new technical research. All API capabilities have been validated through live queries. The work involves extracting, organizing, and presenting findings in a format optimized for future planning and execution decisions.

**Primary recommendation:** Use a structured documentation approach with clear sections for API capabilities, working query examples, sample responses, data value assessment, and decision framework. Build the Go/No-Go recommendation using a weighted scoring matrix that evaluates technical feasibility, data availability, performance characteristics, and business value.

## Standard Stack

### Core Documentation Tools

| Tool | Version | Purpose | Why Standard |
|------|---------|---------|--------------|
| Markdown | - | Documentation format | Project standard (all docs in `/docs/` are .md) |
| Python scripts | 3.x | Query pattern extraction | All discovery scripts use Python |
| JSON | - | Sample response storage | Discovery results stored as JSON |

### Supporting Tools

| Tool | Version | Purpose | When to Use |
|------|---------|---------|-------------|
| Supabase MCP | - | Query database for context | Cross-reference with existing data |
| grep/jq | - | Extract patterns from JSON | Parse discovery results |
| Git | - | Version control documentation | Commit final docs to repo |

**Installation:**
```bash
# No new dependencies - all tools already available
# Python environment: already configured
# MCP tools: already available
```

## Architecture Patterns

### Recommended Documentation Structure

Based on project conventions (see `/docs/architecture/`, `/docs/troubleshooting/`):

```
docs/
├── google-ads-api-capabilities.md    # Primary deliverable (DOC-01)
│   ├── Executive Summary
│   ├── API Views Reference
│   ├── Metrics Catalog
│   ├── Working Query Examples
│   ├── Sample API Responses
│   ├── Data Value Assessment
│   ├── Alternative Strategies
│   └── Go/No-Go Recommendation
└── (optional) google-ads-query-patterns.md  # Quick reference
```

### Pattern 1: Field Reference Tables

**What:** Tabular format for API field documentation
**When to use:** Documenting views, metrics, and resource fields
**Example:**
```markdown
## shopping_performance_view

**Granularity:** Product + Date level
**Use case:** Product-level performance tracking

| Field | Type | Nullable | Description |
|-------|------|----------|-------------|
| segments.product_item_id | STRING | NO | GMC offer ID (lowercase shopify_us_) |
| segments.date | DATE | NO | Date of performance data |
| metrics.impressions | INT64 | YES | Number of ad impressions |
| metrics.clicks | INT64 | YES | Number of clicks |
| metrics.ctr | DOUBLE | YES | Click-through rate (clicks/impressions) |
```

**Source:** Existing pattern from `docs/database/SCHEMA.md`

### Pattern 2: Working Query Examples

**What:** Copy-paste ready GAQL queries with context
**When to use:** Documenting validated query patterns from discovery
**Example:**
```markdown
### Fetch Product Performance (30-day)

**Use case:** Get baseline performance metrics for specific products

**Query:**
\`\`\`sql
SELECT
  segments.product_item_id,
  segments.date,
  campaign.advertising_channel_type,
  metrics.impressions,
  metrics.clicks,
  metrics.ctr,
  metrics.cost_micros,
  metrics.conversions,
  metrics.conversions_value
FROM shopping_performance_view
WHERE segments.product_item_id IN ('shopify_us_123_456', 'shopify_us_789_012')
  AND segments.date BETWEEN '2026-01-14' AND '2026-02-12'
  AND campaign.advertising_channel_type IN ('SHOPPING', 'PERFORMANCE_MAX')
ORDER BY segments.date DESC
LIMIT 10000
\`\`\`

**Notes:**
- Must include `campaign.advertising_channel_type` in SELECT when filtering by it
- Date ranges must be explicit (LAST_N_DAYS syntax rejected by API)
- Offer IDs are lowercase `shopify_us_` format
- Response time: ~2-4s for 100K rows

**Sample response:** See [Sample 1](#sample-response-1)
```

**Source:** Validated in Phase 1 (test_api_02.py), documented in 01-01-SUMMARY.md

### Pattern 3: Sample API Responses

**What:** Real API response snippets showing data structures
**When to use:** Demonstrating actual API behavior with live data
**Example:**
```markdown
### Sample Response 1: shopping_performance_view

**Query:** Product performance (single SKU, 30 days)
**Rows returned:** 30
**Response time:** 1.2s

\`\`\`json
{
  "results": [
    {
      "segments": {
        "product_item_id": "shopify_us_4539975336068_32103134298244",
        "date": "2026-02-10"
      },
      "campaign": {
        "advertising_channel_type": "PERFORMANCE_MAX"
      },
      "metrics": {
        "impressions": 125,
        "clicks": 8,
        "ctr": 0.064,
        "cost_micros": 1200000,
        "conversions": 0.5,
        "conversions_value": 45.00
      }
    }
  ]
}
\`\`\`

**Key observations:**
- Performance Max campaigns populate shopping_performance_view
- CTR calculated as clicks/impressions (0.064 = 8/125)
- Cost in micros (1,200,000 = $1.20)
- Fractional conversions from attribution model
```

**Source:** Extracted from `.planning/phases/02-comprehensive-data-discovery/disc-01-02-06-results.json`

### Pattern 4: Data Value Assessment Matrix

**What:** Structured evaluation of data sources by content optimization relevance
**When to use:** Prioritizing which metrics/views matter most for FeedOps
**Example:**
```markdown
## Data Value Assessment

**Assessment criteria:** Relevance to FeedOps content optimization
**Rating scale:** HIGH (directly informs content), MEDIUM (contextual), LOW (campaign management)

| Data Source | Value | Reason | Use Case |
|-------------|-------|--------|----------|
| search_term_view | HIGH | Reveals customer language and intent | Inform title/description word choice |
| shopping_performance_view (CTR) | HIGH | Directly measures content effectiveness | Identify underperforming products |
| custom_attribute (labels) | HIGH | Efficient product segmentation | Filter by category for batch operations |
| segments.device | MEDIUM | Device performance differences | Optimize description length for mobile |
```

**Source:** Existing pattern from `disc-10-11-12-results.json` data_value_assessment

### Pattern 5: Go/No-Go Decision Framework

**What:** Weighted scoring matrix for backfill execution decision
**When to use:** Final phase recommendation synthesis
**Example:**
```markdown
## Go/No-Go Recommendation

### Scoring Matrix

| Criterion | Weight | Score (1-5) | Weighted | Evidence |
|-----------|--------|-------------|----------|----------|
| **Technical Feasibility** | 30% | 5 | 1.50 | All 5 API requirements satisfied (Phase 1) |
| **Data Availability** | 25% | 4 | 1.00 | 14/17 metrics available (82% coverage) |
| **Query Performance** | 20% | 5 | 1.00 | 7.1 min for 2,784 SKUs (acceptable) |
| **Data Value** | 15% | 5 | 0.75 | High-value data sources confirmed |
| **Alternative Strategies** | 10% | 3 | 0.30 | Workarounds needed for 3 limitations |
| **TOTAL** | 100% | - | **4.55/5** | **Strong GO** |

### Recommendation: **GO**

**Confidence:** HIGH (4.55/5)

**Rationale:**
1. All core API capabilities validated with working queries
2. 82% metric coverage sufficient for content optimization
3. Performance acceptable (7.1 min for full backfill)
4. High-value data sources (search terms, product CTR) available
5. Alternative strategies documented for 3 limitations

**Proceed with Phases 1-5 backfill execution.**
```

**Source:** Adapted from project management Go/No-Go templates, incorporating Phase 0-3 findings

### Anti-Patterns to Avoid

- **Fabricating API capabilities:** Only document what was actually tested (Phases 1-3)
- **Generic recommendations:** Use specific metrics from discovery (e.g., "7.1 min" not "fast enough")
- **Burying the decision:** Go/No-Go must be clear, upfront, and unambiguous
- **Ignoring limitations:** Document failed assumptions (e.g., Auction Insights access restriction)
- **Stale examples:** Use actual API responses from discovery JSON files, not invented data

## Don't Hand-Roll

| Problem | Don't Build | Use Instead | Why |
|---------|-------------|-------------|-----|
| Sample response extraction | Custom JSON parsers | `jq` + Python `json` module | Already collected in discovery JSONs |
| Query pattern documentation | Manual rewriting | Extract from working Python scripts | Scripts are source of truth (already tested) |
| Field enumeration | Manual typing | Copy from `disc-01-02-06-results.json` | 23 views with 76 fields each already discovered |
| Data value ranking | Subjective assessment | Use existing `data_value_assessment` from disc-10-11-12 | Already prioritized by content optimization relevance |
| Decision framework | Ad-hoc narrative | Weighted scoring matrix | Provides objective, reproducible evaluation |

**Key insight:** Phase 4 is a **synthesis task**, not a discovery task. All raw data exists in `.planning/phases/01-03/`. The work is extraction, organization, and presentation - not new research.

## Common Pitfalls

### Pitfall 1: Documentation Drift from Source Data

**What goes wrong:** Manually typing field names/queries instead of extracting from discovery files, causing documentation to misrepresent actual API behavior.

**Why it happens:** Copying from Phase 1-3 SUMMARY files (which may have typos/simplifications) instead of discovery JSONs and Python scripts (ground truth).

**How to avoid:**
1. Source query examples directly from `.planning/phases/*/test_*.py` and `discover_*.py` scripts
2. Source field listings directly from `disc-01-02-06-results.json` views section
3. Source sample responses directly from `disc-*-results.json` files (not hand-written)
4. Cross-reference all examples with actual code to ensure accuracy

**Warning signs:**
- Query examples that weren't in discovery scripts
- Field names that don't match JSON discovery results
- Response samples with different structure than discovery JSONs

### Pitfall 2: Missing the "Why" in Decision Rationale

**What goes wrong:** Go/No-Go recommendation states "proceed" or "don't proceed" without clear reasoning tied to specific Phase 0-3 findings.

**Why it happens:** Treating the decision as binary (yes/no) instead of evidence-based synthesis.

**How to avoid:**
1. Build decision framework FIRST (criteria + weights)
2. Map each criterion to specific Phase 1-3 evidence (e.g., "Query Performance → 7.1 min from 03-03-SUMMARY.md")
3. Score objectively using quantitative metrics where possible
4. Document alternative strategies for failed assumptions (transparency)

**Warning signs:**
- Recommendation appears before evidence summary
- Decision rationale uses vague terms ("seems feasible", "should work")
- No mention of specific limitations or workarounds

### Pitfall 3: Over-Documenting Low-Value Details

**What goes wrong:** Spending effort documenting every discovered field/metric/view instead of focusing on high-value data sources relevant to content optimization.

**Why it happens:** Completeness bias - assuming comprehensive = better.

**How to avoid:**
1. Use existing `data_value_assessment` from `disc-10-11-12-results.json` to prioritize
2. Provide complete field reference (for completeness) but emphasize high-value sources
3. Structure doc with "Quick Start" (high-value only) + "Complete Reference" (everything)
4. Cross-reference with CLAUDE.md anti-pattern: "Never fabricate... query database FIRST"

**Warning signs:**
- All views/metrics treated equally (no prioritization)
- Missing data value assessment section
- No "most useful for content optimization" guidance

### Pitfall 4: Ignoring Prior Decisions

**What goes wrong:** Documentation contradicts or overlooks decisions made during Phases 1-3 (e.g., documenting LAST_N_DAYS syntax that was proven to fail).

**Why it happens:** Not reviewing `.planning/REQUIREMENTS.md` and phase SUMMARY files for key decisions.

**How to avoid:**
1. Review all 16 prior decisions from REQUIREMENTS.md
2. Extract "Decisions Made" sections from 01-01, 01-02, 02-02, 02-03, 03-01, 03-02, 03-03 SUMMARY files
3. Include "Key Decisions" reference section in documentation
4. Flag any documentation that contradicts discovered limitations

**Warning signs:**
- Documenting API features that were proven unavailable (e.g., Auction Insights API access)
- Query examples using rejected syntax (e.g., LAST_90_DAYS)
- Missing segments.product_item_id in SELECT when filtering by it

### Pitfall 5: Static Documentation Without Maintenance Strategy

**What goes wrong:** Documentation becomes stale as API evolves (Google Ads API updates quarterly).

**Why it happens:** No clear ownership or update triggers defined.

**How to avoid:**
1. Include "Valid as of" date at top of document
2. Add "Known Limitations" section that links to Google Ads API changelog
3. Recommend validation cadence (e.g., re-run discovery scripts quarterly)
4. Document version-specific behavior (e.g., "performance_label unavailable in API v22")

**Warning signs:**
- No publication date on documentation
- No links to official Google Ads API docs
- No mention of API version used for discovery

## Code Examples

Verified patterns from discovery scripts:

### Product Performance Query (Validated)

```python
# Source: .planning/phases/01-api-capability-validation/test_api_02.py
# Lines: 165-182

from google.ads.googleads.client import GoogleAdsClient
from datetime import datetime, timedelta

client = GoogleAdsClient.load_from_storage()
ga_service = client.get_service("GoogleAdsService")

# Calculate explicit date range (LAST_N_DAYS syntax rejected)
end_date = datetime.now().date()
start_date = end_date - timedelta(days=30)

query = f"""
SELECT
  segments.product_item_id,
  segments.date,
  campaign.advertising_channel_type,
  metrics.impressions,
  metrics.clicks,
  metrics.ctr,
  metrics.cost_micros,
  metrics.conversions,
  metrics.conversions_value
FROM shopping_performance_view
WHERE segments.product_item_id IN ('shopify_us_4539975336068_32103134298244')
  AND segments.date BETWEEN '{start_date}' AND '{end_date}'
  AND campaign.advertising_channel_type IN ('SHOPPING', 'PERFORMANCE_MAX')
ORDER BY segments.date DESC
LIMIT 10000
"""

response = ga_service.search(customer_id="6253381786", query=query)
for row in response:
    print(f"Date: {row.segments.date}, Impressions: {row.metrics.impressions}")
```

### Search Term Fetching (Campaign-Join Pattern)

```python
# Source: .planning/phases/03-sample-testing-analysis/phase3_select_skus.py
# Lines: 324-357

# Step 1: Get campaigns for products (shopping_performance_view)
product_ids_clause = "','".join(offer_ids)
campaigns_query = f"""
SELECT
  campaign.id,
  campaign.name,
  campaign.advertising_channel_type
FROM shopping_performance_view
WHERE segments.product_item_id IN ('{product_ids_clause}')
  AND segments.date BETWEEN '{start_date}' AND '{end_date}'
  AND campaign.advertising_channel_type IN ('SHOPPING', 'PERFORMANCE_MAX')
"""

# Extract unique campaign IDs
campaign_ids = set()
for row in ga_service.search_stream(customer_id=customer_id, query=campaigns_query):
    campaign_ids.add(str(row.campaign.id))

# Step 2: Fetch search terms for those campaigns (search_term_view)
campaign_ids_clause = ",".join(campaign_ids)
search_terms_query = f"""
SELECT
  segments.search_term,
  metrics.impressions,
  metrics.clicks,
  metrics.conversions
FROM search_term_view
WHERE campaign.id IN ({campaign_ids_clause})
  AND segments.date BETWEEN '{start_date}' AND '{end_date}'
"""

for row in ga_service.search_stream(customer_id=customer_id, query=search_terms_query):
    print(f"Search term: {row.segments.search_term}")
```

### Batch Performance with Optimal LIMIT

```python
# Source: .planning/phases/03-sample-testing-analysis/phase3_performance_test.py
# Lines: 119-145

# Optimal batch size: 10 products at a time
# p95 response time: 1273ms (127ms per SKU)
batch_size = 10
for i in range(0, len(offer_ids), batch_size):
    batch = offer_ids[i:i+batch_size]
    batch_clause = "','".join(batch)

    query = f"""
    SELECT
      segments.product_item_id,
      segments.date,
      metrics.impressions,
      metrics.clicks,
      metrics.ctr,
      metrics.conversions
    FROM shopping_performance_view
    WHERE segments.product_item_id IN ('{batch_clause}')
      AND segments.date BETWEEN '{start_date}' AND '{end_date}'
    LIMIT 10000
    """

    start_time = time.perf_counter()
    response = list(ga_service.search_stream(customer_id=customer_id, query=query))
    elapsed = time.perf_counter() - start_time
    print(f"Batch {i//batch_size + 1}: {len(response)} rows in {elapsed:.2f}s")
```

### Custom Label Filtering

```python
# Source: scripts/test_api_boundaries.py (Phase 1)
# Lines: 185-205

# Custom attributes are product_custom_attribute0-4 (no underscore before number)
query = f"""
SELECT
  segments.product_item_id,
  segments.product_custom_attribute0,
  segments.product_custom_attribute1,
  metrics.impressions
FROM shopping_performance_view
WHERE segments.product_custom_attribute0 = 'double glass shelf'
  AND segments.date BETWEEN '{start_date}' AND '{end_date}'
LIMIT 100
"""

# Response time: ~1s for category-based filtering
# Population rates: attribute0 (100%), attribute1 (100%), attribute2 (90%)
```

## State of the Art

| Old Approach | Current Approach | When Changed | Impact |
|--------------|------------------|--------------|--------|
| Using Content API for Merchant Center | Using Merchant API | 2024 | Content API deprecated, must use Merchant API going forward |
| Assuming LAST_N_DAYS syntax works | Using explicit date ranges | Phase 1 (2026-02-12) | API rejects LAST_N_DAYS, must calculate dates in code |
| Filtering search_term_view by product | Campaign-join pattern | Phase 1 (2026-02-12) | API rejects product_item_id in search_term_view WHERE clause |
| Uppercase offer IDs (shopify_US_) | Lowercase offer IDs (shopify_us_) | Phase 1 (2026-02-12) | Google Ads API uses lowercase internally |
| Accessing Auction Insights via API | Manual export from UI only | Phase 2 (2026-02-12) | API access restricted for this account |

**Deprecated/outdated:**
- **Content API for Shopping:** Deprecated by Google, replaced by Merchant API (2024)
- **LAST_N_DAYS syntax:** Appears in some documentation but rejected by API
- **Direct product filtering in search_term_view:** Not supported, requires campaign-join workaround

## Open Questions

1. **How frequently should discovery scripts be re-run?**
   - What we know: Google Ads API evolves quarterly with new fields/metrics
   - What's unclear: Whether new Shopping-relevant capabilities are added frequently enough to justify quarterly re-discovery
   - Recommendation: Include "Valid as of 2026-02-13" date in docs, recommend annual validation unless Google announces Shopping API changes

2. **Should alternative data sources (e.g., Merchant API product performance) be explored?**
   - What we know: Merchant API has `product_performance_view` with different metrics
   - What's unclear: Whether Merchant API data overlaps with or complements Google Ads API data
   - Recommendation: Document as "Future Investigation" (out of scope for Phase 0) but note as potential enhancement

3. **How to handle multi-SKU products in backfill strategy?**
   - What we know: Multi-SKU products share product_id, Google Ads aggregates at product level
   - What's unclear: Whether backfill should assign aggregated metrics to all variants or primary variant only
   - Recommendation: Document the limitation, defer implementation decision to Phase 1-5 planning

4. **What is the retention policy for search_queries and keyword_metrics tables?**
   - What we know: Google Ads API retains data from 2020-01-01 (6 years)
   - What's unclear: Whether Supabase tables should mirror this retention or keep all historical data
   - Recommendation: Document API retention in capabilities doc, defer database retention policy to Phase 1 planning

## Sources

### Primary (HIGH confidence)

- `.planning/phases/01-api-capability-validation/` - Phase 1 test scripts and results (API-01 through API-05)
- `.planning/phases/02-comprehensive-data-discovery/` - Phase 2 discovery scripts and results (DISC-01 through DISC-12)
- `.planning/phases/03-sample-testing-analysis/` - Phase 3 sample testing scripts and results (SAMP-01 through SAMP-06)
- `.planning/REQUIREMENTS.md` - 16 documented decisions from Phases 1-3
- `docs/database/SCHEMA.md` - Existing database schema documentation pattern
- `docs/architecture/data-pipeline.md` - Existing architecture documentation pattern
- `docs/troubleshooting/baseline-capture.md` - Existing troubleshooting guide pattern
- [Google Ads Query Language Overview](https://developers.google.com/google-ads/api/docs/query/overview) - Official GAQL documentation
- [Google Ads Query Language Grammar](https://developers.google.com/google-ads/api/docs/query/grammar) - Official GAQL syntax reference

### Secondary (MEDIUM confidence)

- [API Documentation Best Practices | Postman](https://www.postman.com/api-platform/api-documentation/) - Industry standards for API documentation structure
- [How to Write API Documentation | Stoplight](https://stoplight.io/api-documentation-guide) - Documentation patterns including sample responses
- [Go/No-Go Decision Process | Inventive.ai](https://www.inventive.ai/blog-posts/go-no-go-decision-projects) - Decision framework templates
- [Go/No Go Production Readiness Checklist | IPM](https://instituteprojectmanagement.com/blog/go-no-go-production-readiness-checklist/) - Production readiness evaluation criteria

### Tertiary (LOW confidence)

- [7 Excellent API Documentation Examples for 2026 | Apidog](https://apidog.com/blog/api-documentation-example/) - Reference examples (varies by API)
- [API Governance Best Practices for 2026 | Treblle](https://treblle.com/blog/api-governance-best-practices) - General best practices (not Google Ads specific)

## Metadata

**Confidence breakdown:**
- Standard stack: HIGH - All tools already in use (Markdown, Python, JSON)
- Architecture patterns: HIGH - Patterns extracted from existing project docs
- Query examples: HIGH - All examples validated in Phases 1-3 with working scripts
- Sample responses: HIGH - All samples from actual API responses in discovery JSONs
- Decision framework: MEDIUM - Adapted from general PM templates, not specific to this project
- Pitfalls: HIGH - Based on actual Phase 0-3 execution learnings

**Research date:** 2026-02-13
**Valid until:** 90 days (2026-05-13) - Google Ads API updates quarterly, documentation patterns stable

**Key findings:**
1. Phase 4 is **synthesis, not discovery** - all raw data exists in `.planning/phases/01-03/`
2. Documentation must be extracted from source files (scripts + JSONs), not manually typed
3. Go/No-Go framework should use weighted scoring with specific Phase 0-3 metrics
4. 20-30 sample responses already collected across 4 discovery JSON files (2.1MB total)
5. Project has strong documentation conventions (`docs/architecture/`, `docs/troubleshooting/`) to follow
