# Phase 0: Google Ads API Discovery

## Project Overview

**Purpose**: Validate Google Ads API capabilities and data access patterns before executing the full 5-phase backfill and monitoring plan.

**Why Phase 0 Exists**: The comprehensive backfill plan (Phases 1-5) makes critical assumptions about Google Ads API capabilities:
- Product-level search term queries (filtering by `product_item_id`)
- Large result set limits (50K rows per query)
- Specific retention windows (180 days for search terms, 2 years for performance)
- Custom label availability via Merchant API

These assumptions need validation BEFORE detailed planning. If they're wrong, the entire backfill strategy needs rework.

**Timeline**: 1-2 days of investigation before ANY Phase 1-5 planning begins.

**Context**: Only 84/2,784 SKUs (3%) currently have search query data. The infrastructure is solid, signals are wired correctly, but we need historical data backfill. Phase 0 ensures we know HOW to backfill before planning the execution.

## Success Criteria

Phase 0 is complete when we have:

1. ✅ **All 5 core questions answered** (even if answers are "no" or "limited")
2. ✅ **Working GAQL queries** that demonstrate feasible backfill approach
3. ✅ **Alternative strategies documented** if any assumptions fail
4. ✅ **Comprehensive API reference** (`docs/google-ads-api-capabilities.md`)
5. ✅ **Sample data** from 5-10 test SKUs showing actual API responses
6. ✅ **Decision document** - Proceed with original plan vs. modified plan vs. different approach

**Definition of Success**: We have enough information to confidently plan Phases 1-5 OR pivot to a different strategy if critical assumptions are wrong.

## The 5 Core Questions

### Q1: Product-Level Search Term Filtering
**Question**: Can we filter `search_term_view` by `product_item_id`? Or must we use `shopping_performance_view`?

**Why Critical**: Original plan assumes we can query search terms for specific products. If we can only get campaign-level data, backfill strategy needs major rework.

**Test Approach**:
- Try GAQL query: `SELECT ... FROM search_term_view WHERE segments.product_item_id = 'shopify_US_...'`
- If fails, try: `SELECT ... FROM shopping_performance_view WHERE ...`
- Document which fields are available in each view

**Success Output**: Working query that gets product-specific search terms OR documented alternative approach.

---

### Q2: Query Result Limits
**Question**: What's the actual LIMIT we can request in GAQL queries?

**Current State**:
- Plan assumes: 50K rows per query
- Current code uses: 1K rows per query
- Developer token: **Highest level with standard access** (no read limits)

**Why Critical**: Determines batch size for backfill jobs. If limit is lower than 50K, need more query batching.

**Test Approach**:
- Start with LIMIT 10000, then 50000, then 100000
- Find where API starts rejecting or rate limiting
- Test on `search_term_view` and `shopping_performance_view`

**Success Output**: Documented maximum LIMIT per view + recommended batch size for production.

---

### Q3: Data Retention Windows
**Question**: Confirm retention periods - 180 days for search terms, 2 years for shopping performance?

**Why Critical**: Determines how far back we can backfill and how often we need to collect fresh data.

**Test Approach**:
- Query with `WHERE segments.date BETWEEN '2024-08-11' AND '2025-02-11'` (180 days ago to today)
- Query with `WHERE segments.date BETWEEN '2024-02-11' AND '2025-02-11'` (365 days ago to today)
- Query with `WHERE segments.date BETWEEN '2023-02-11' AND '2025-02-11'` (2 years ago to today)
- Document oldest available date for each view

**Success Output**: Confirmed retention windows OR corrected retention windows + impact on backfill plan.

---

### Q4: Custom Label Availability
**Question**: Is `custom_label_0` available via Merchant API `products.list()`?

**Current State**:
- User has 60 manually-curated categories in `custom_label_0` in Google Merchant Center
- Field exists in Google Sheets but NOT in `product_catalog` database table
- Decision made: Use `custom_label_0` for FST clustering (don't extract from titles)

**Why Critical**: Need to sync `custom_label_0` to database for clustering analysis. If not available via API, need manual CSV export workflow.

**Test Approach**:
- Use Merchant API MCP tool: `mcp__merchant-api-devdocs__query_mapi_docs` to check available fields
- Test query: `SELECT id, offer_id, custom_label_0 FROM product_view LIMIT 10`
- Document field name and data structure

**Success Output**: Working query to fetch `custom_label_0` OR alternative sync strategy (CSV export, Google Sheets API).

---

### Q5: Keyword Planner Opportunity Gap
**Question**: For 5-10 sample SKUs across categories, what high-volume Keyword Planner terms are NOT in current Google Ads search data?

**Why Critical**: Validates decision to use KP for ALL SKUs (not just cold-start). Current Google Ads data reflects unoptimized feed → KP reveals ranking opportunities.

**Sample Strategy**: 5-10 SKUs across product categories:
- 2x Towel bars (different styles/finishes)
- 2x Grab bars (different sizes)
- 2x Mirrors (different types)
- 2x Shelves (glass vs metal)
- 2x Cabinet hardware (different categories)

**Test Approach**:
1. Get current Google Ads search terms for sample SKUs (via `search_term_view`)
2. Generate KP keyword ideas using product titles/descriptions as seed
3. Compare: What high-volume KP terms (avg_monthly_searches > 100) are missing from Google Ads data?
4. Document gap size and opportunity value

**Success Output**: Evidence document showing KP opportunity gaps + validation that KP is necessary for comprehensive coverage.

---

## Investigation Approach

**Hybrid Strategy** (Manual Exploration → Automated Validation):

### Phase 1: Manual Exploration (Day 1, Hours 1-4)
- Use Google Ads Developer Assistant for interactive query testing
- Test each of the 5 questions manually
- Document findings, errors, limitations in scratch notes
- Identify working query patterns

### Phase 2: Automated Validation (Day 1, Hours 5-8)
- Write Python script to run validated queries at scale
- Test with 5-10 sample SKUs across categories
- Capture actual API responses
- Generate sample data for evidence review

### Phase 3: Documentation (Day 2, Hours 1-4)
- Write comprehensive `docs/google-ads-api-capabilities.md`
- Include working GAQL queries, field references, limitations
- Document alternative strategies for any failed assumptions
- Create decision tree: Original plan vs. Modified plan vs. Pivot

## Deliverables

### Primary Deliverable
**`docs/google-ads-api-capabilities.md`** - Comprehensive API reference including:
- Answers to all 5 core questions
- Working GAQL query examples
- Field reference for `search_term_view`, `shopping_performance_view`, `product_view`
- Documented limitations and workarounds
- Alternative strategies if assumptions fail
- Sample API responses (10-20 examples)
- Decision recommendation: Proceed vs. Modify vs. Pivot

### Supporting Artifacts
- **Sample data**: JSON/CSV files with API responses from 5-10 test SKUs
- **Test queries**: Collection of working GAQL queries for backfill
- **Error log**: Documented failures and lessons learned
- **Decision doc**: Go/No-Go recommendation for Phases 1-5

## Out of Scope for Phase 0

**NOT doing in Phase 0**:
- ❌ Full backfill execution (that's Phases 1-5)
- ❌ Schema migrations for `custom_label_0` (that's Phase 1)
- ❌ Prompt updates or content generation changes
- ❌ Dashboard UI changes
- ❌ Production deployment of any code
- ❌ Detailed planning for Phases 1-5 (wait until Phase 0 completes)

**Phase 0 is pure research** - No production changes, no schema updates, no user-facing features.

## Key Context

### Technical Environment
- **Supabase Project**: qezuszwufortkiutlhym
- **Google Ads Customer ID**: 6253381786
- **Developer Token Level**: Highest with standard access (no read limits)
- **Python Pipeline**: Cloud Run (auto-deploys on push to master)
- **Dashboard**: Vercel (allied-feed-ops.vercel.app)

### Current Data Coverage
- Total SKUs: 2,784
- SKUs with search query data: 84 (3%)
- Coverage problem: Backfill hasn't run yet, not a data sync issue

### Available Tools
- **MCP Servers**: `mcp__google-ads-mcp__*`, `mcp__merchant-api-devdocs__*`, `mcp__supabase__*`
- **Google Ads Developer Assistant**: `/Users/bobby/Documents/GitHub/google-ads-api-developer-assistant`
- **Existing code**: `src/feedops/integrations/google_ads_search_terms.py` (reference implementation)

### Related Documents
- **Original 5-phase plan**: `docs/plans/2026-02-11-schema-scalability-and-backfill.md`
- **Signal audit**: `docs/audit/signal-audit-2026-02-11/*.md` (9 agent reports)
- **Codebase map**: `.planning/codebase/*.md` (7 files from `/gsd:map-codebase`)
- **Database schema**: `docs/database/SCHEMA.md`
- **Notion reference**: https://www.notion.so/3041adf992e9814d9a86eb931c130438 (Phases 1-5 details)

## Risks and Mitigations

### Risk 1: API Doesn't Support Product-Level Queries
**Impact**: Can't filter search terms by product → must query all terms → huge result sets
**Mitigation**: Document alternative: Use `shopping_performance_view` with broader filters + post-query filtering
**Fallback**: Campaign-level queries + heuristic matching via product titles

### Risk 2: Retention Window Shorter Than Assumed
**Impact**: Can't backfill full 180 days → less historical data
**Mitigation**: Document actual window + adjust backfill plan timeline
**Fallback**: Focus on most recent data, run more frequent collections going forward

### Risk 3: Custom Label Not Available via API
**Impact**: Can't sync `custom_label_0` programmatically
**Mitigation**: CSV export workflow from Merchant Center + manual upload to Supabase
**Fallback**: Extract categories from titles (less clean but workable)

### Risk 4: Query Limits Lower Than Expected
**Impact**: Need more batching → slower backfill
**Mitigation**: Document actual limits + design batch jobs accordingly
**Fallback**: Use pagination + smaller chunks (already standard pattern)

### Risk 5: KP Opportunity Gap Is Small
**Impact**: Decision to use KP for all SKUs might be overkill
**Mitigation**: If gap is <10% of total volume, reconsider KP strategy
**Fallback**: KP only for cold-start + low-performer SKUs (original plan)

## Success Metrics

### Quantitative
- ✅ All 5 questions have documented answers
- ✅ At least 3 working GAQL queries tested
- ✅ Sample data from 5-10 SKUs collected
- ✅ API response times measured (p50, p95, p99)
- ✅ Error rates documented (<5% query failure acceptable)

### Qualitative
- ✅ Confident in backfill feasibility (Go/No-Go decision clear)
- ✅ Alternative strategies documented for any blockers
- ✅ API reference comprehensive enough to plan Phases 1-5
- ✅ User confirms: "We have enough information to proceed"

## Next Steps After Phase 0

**If assumptions validated** (happy path):
1. Run new `/gsd:new-project` with validated API data
2. Plan Phases 1-5 in detail (roadmap with tasks)
3. Execute Phase 1: Schema + custom_label_0 sync
4. Execute Phase 2: Historical backfill (180 days)
5. Continue through Phase 5

**If assumptions partially wrong** (modify plan):
1. Update backfill plan with corrected constraints
2. Re-estimate timeline and batch sizes
3. Run new `/gsd:new-project` with modified approach
4. Proceed with adjusted plan

**If critical blockers found** (pivot):
1. Document why original approach won't work
2. Design alternative strategy (e.g., campaign-level aggregation)
3. User decision: Proceed with alternative vs. wait for API changes vs. different data source
