# Allied FeedOps

## What This Is

A Google Ads feed optimization platform that automatically collects search performance data, generates AI-powered product content, and publishes optimized feeds to Google Merchant Center, Bing, and Shopify. Built for Allied Brass's 2,784-SKU catalog to improve search visibility and conversion rates through data-driven content optimization.

## Core Value

Transform low-performing product feeds into high-converting assets by combining real search query data with AI content generation, enabling data-driven optimization at scale for the entire catalog.

## Current Milestone: v1.0 Historical Data Backfill

**Goal:** Execute comprehensive Google Ads historical data backfill for all 2,784 SKUs with production-ready monitoring and validation.

**Target capabilities:**
- Campaign-join pattern for product-specific search term collection
- Optimal batch sizing (size 10) for 127ms p95 query performance
- Keyword Planner integration for ALL SKUs (addressing 43% coverage gap)
- Custom label sync pipeline from Google Merchant Center
- 180-day historical backfill across search terms and performance metrics
- Monitoring & alerting pipeline with automated schedules
- Data quality validation (completeness, accuracy, freshness)
- Performance dashboards for tracking backfill progress
- Incremental refresh strategy for ongoing data sync

**Timeline:** 2-3 weeks (comprehensive approach)

**Success metric:** All 2,784 SKUs have 180 days of search terms, performance data, and Keyword Planner opportunities with ongoing automated collection.

## Requirements

### Validated (Phase 0 - Complete)

Phase 0 validated Google Ads API capabilities with GO recommendation (4.65/5 confidence):

- ✓ **API-01**: search_term_view product filtering limitation documented (campaign-join workaround validated)
- ✓ **API-02**: shopping_performance_view supports product-level queries
- ✓ **API-03**: Query LIMIT values up to 100K tested (50K recommended)
- ✓ **API-04**: Data retention from 2020-01-01 confirmed (~6 years available)
- ✓ **API-05**: custom_attribute0-4 fields accessible (note: no underscore before number)
- ✓ **DISC-01 through DISC-12**: 23 API views enumerated, 36+ metrics cataloged
- ✓ **SAMP-01 through SAMP-06**: 6 sample SKUs tested, 60K+ search terms validated
- ✓ **DOC-01 through DOC-06**: Comprehensive API reference created with Go/No-Go decision

### Active (v1.0 - In Planning)

Currently defining requirements for v1.0 milestone. Will be populated during requirements gathering phase.

### Out of Scope

**For v1.0:**
- Real-time data streaming (batch collection sufficient for v1)
- Advanced ML models for content optimization (manual prompts first)
- Multi-account Google Ads management (single account: 6253381786)
- Competitive intelligence beyond own metrics (auction insights API unavailable)
- Mobile app or native integrations (web dashboard sufficient)

## Context

### Phase 0 Discovery (Complete - 2026-02-13)

Phase 0 validated API feasibility through 4 phases:
1. **API Capability Validation** - Core query patterns and constraints identified
2. **Comprehensive Data Discovery** - 23 views, 36+ metrics cataloged
3. **Sample Testing & Analysis** - 6 SKUs tested, query performance benchmarked
4. **Documentation & Decision** - 60KB API reference created, GO recommendation issued

**Key findings:**
- Product-level search term queries require 2-step campaign-join pattern
- Optimal batch size is 10 SKUs (127ms p95 performance, 7.1 min for full catalog)
- Keyword Planner reveals 43% coverage gap (168K monthly searches)
- Custom labels available via custom_attribute0-4 fields
- Data retention: 2020-01-01 to present

**6 Critical modifications identified:**
1. Use batch size 10 (not 50K LIMIT per query)
2. Campaign-join pattern for search terms (2-step query)
3. Skip auction insights API (use own impression/click share)
4. Plan for 33% competitive metric coverage (sufficient for high-value SKUs)
5. Use explicit date ranges (LAST_N_DAYS syntax rejected by API)
6. Include Keyword Planner for ALL SKUs (not just cold-start)

### Current Data State

- **Total SKUs:** 2,784
- **SKUs with search data:** 84 (3%)
- **Coverage gap:** 97% of catalog lacks historical search intelligence
- **Backfill window:** 180 days (2025-08-16 to 2026-02-13)

### Technical Environment

- **Supabase Project:** qezuszwufortkiutlhym
- **Google Ads Customer ID:** 6253381786
- **Python Pipeline:** Cloud Run (auto-deploys on push to master)
- **Dashboard:** Vercel (allied-feed-ops.vercel.app)
- **Developer Token:** Highest level with standard access (no read limits)

## Constraints

- **API Rate Limits:** Google Ads API has undocumented rate limits - batch size 10 provides safety margin
- **Timeline:** 2-3 weeks for comprehensive v1.0 (fast execution would sacrifice monitoring/validation)
- **Data Retention:** 180 days for search terms, ~6 years for performance (account-dependent, not API limit)
- **Competitive Metrics:** Only 33% coverage for impression/click share (sufficient volume required)
- **Tech Stack:** Python for pipelines (Cloud Run), TypeScript for dashboard (Next.js/Vercel)

## Key Decisions

| Decision | Rationale | Outcome |
|----------|-----------|---------|
| Phase 0 discovery before execution | Validate API assumptions before detailed planning (5 core questions) | ✓ Good - Found 6 critical modifications, avoided failed assumptions |
| GO decision (4.65/5 confidence) | All core capabilities validated, performance acceptable, high-value data accessible | — Pending (v1.0 execution will validate) |
| Keyword Planner for ALL SKUs | 43% coverage gap identified (168K monthly searches) | — Pending (v1.0 will measure impact) |
| Campaign-join pattern for search terms | API rejects direct product filtering in search_term_view | ✓ Good - Workaround validated in Phase 3 testing |
| Batch size 10 (not 50K LIMIT) | Optimal throughput (127ms/SKU p95) vs retry granularity | — Pending (v1.0 will validate at scale) |

---
*Last updated: 2026-02-13 after Phase 0 completion and v1.0 milestone initialization*
