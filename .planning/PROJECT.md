# Allied FeedOps

## What This Is

A Google Ads feed optimization platform that automatically collects search performance data, generates AI-powered product content, and publishes optimized feeds to Google Merchant Center, Bing, and Shopify. Built for Allied Brass's 2,784-SKU catalog to improve search visibility and conversion rates through data-driven content optimization.

## Core Value

Transform low-performing product feeds into high-converting assets by combining real search query data with AI content generation, enabling data-driven optimization at scale for the entire catalog.

## Current State (after v1.1)

**What's shipped:**
- Full Google Ads data pipeline: search terms, performance metrics, Keyword Planner for all 2,784 SKUs
- Daily automated refresh via Cloud Scheduler
- Dashboard with compact SKU review, per-platform approval badges, inline detail expansion
- User-controlled variant selection for lifestyle image generation with impression-based auto-fallback
- Performance page with baseline vs. snapshot delta comparison and trend indicators
- Dashboard audit complete — no dead-end states, all pages functional
- Google Ads backfill pipeline with parallelized GAQL chunking (3.4x speedup)
- Content generation via Cloud Run Python pipeline (single SKU, batch, and hybrid multi-SKU)
- Publishing to Google Sheets supplemental feed, Shopify, and Bing

**Active background jobs:**
- Performance metrics backfill running (~2,784 SKUs, job 3da77cd6)
- Search terms: 824/2,784 SKUs covered, 10,000+ queries collected

## Requirements

### Validated (Phase 0)

- ✓ API-01 through API-05: Google Ads API capabilities validated (campaign-join pattern, query limits, data retention)
- ✓ DISC-01 through DISC-12: 23 API views, 36+ metrics cataloged
- ✓ SAMP-01 through SAMP-06: Sample testing across 6 SKUs
- ✓ DOC-01 through DOC-06: Comprehensive API reference, GO decision (4.65/5)

### Validated (v1.0)

- ✓ JOB-01 through JOB-10: Job infrastructure with rate limiting, checkpointing, resumability
- ✓ DATA-01 through DATA-10: Data collection pipeline (search terms, performance, Keyword Planner)
- ✓ VALID-01 through VALID-10: Data quality validation, freshness checks, multi-SKU family detection
- ✓ MON-01 through MON-10: Monitoring dashboard, alerting, automated refresh

### Validated (v1.1)

- ✓ SKUR-01 through SKUR-05: SKU review revamp (compact list, per-platform badges, filtering, inline expand)
- ✓ IMG-01 through IMG-04: Image workflow (variant selection, impression-based auto-select, coverage view)
- ✓ PERF-01 through PERF-03: Performance page (baseline vs. snapshot deltas, days-since-publish, trend indicators)
- ✓ DASH-01 through DASH-03: Dashboard audit (no dead ends, stale data fixed, unused pages simplified)
- ✓ VER-01: Visual verification via agent-browser for all UI changes

### Active

(No active milestone — define with `/gsd:new-milestone`)

### Out of Scope

- Real-time data streaming (batch collection sufficient)
- Multi-account Google Ads management (single account: 6253381786)
- Mobile app or native integrations (web dashboard sufficient)

## Context

### Technical Environment

- **Supabase Project:** qezuszwufortkiutlhym
- **Google Ads Customer ID:** 6253381786
- **Python Pipeline:** Cloud Run (auto-deploys on push to master)
- **Dashboard:** Vercel (allied-feed-ops.vercel.app)
- **Developer Token:** Highest level with standard access

### Known Issues / Tech Debt

- Performance metrics backfill still running (may need monitoring)
- Search terms coverage at 824/2,784 SKUs — full 180-day backfill in progress
- Phase 15 partially complete (bugs were found, fixed in Phase 16)
- Monitoring freshness endpoint slow (~51s) — has 10s timeout workaround
- Some phase summaries missing (14-02 rolled into 15, 15-03 skipped)

## Key Decisions

| Decision | Rationale | Outcome |
|----------|-----------|---------|
| Phase 0 discovery before execution | Validate API assumptions before planning | ✓ Good — found 6 critical modifications |
| Campaign-join pattern for search terms | API rejects direct product filtering | ✓ Good — validated at scale |
| Batch size 10 for Google Ads API | Optimal throughput vs retry granularity | ✓ Good — stable at 2,784 SKUs |
| GAQL chunk size 25 for IN() clauses | Conservative safe value for performance queries | ✓ Good — 250 IDs in 13.2s |
| ThreadPoolExecutor(5) for parallel chunks | Balance throughput vs API rate limits | ✓ Good — 3.4x speedup |
| Bulk variant cache preload | Eliminates N+1 queries for 72K+ rows | ✓ Good — 7.7s one-time load |
| Dashboard compact list over magazine layout | Users need to scan 100+ SKUs quickly | ✓ Good — eliminated per-SKU scrolling |
| Impression-based variant auto-select | Data-driven vs hardcoded heuristic | ✓ Good — uses real Google Ads data |

## Constraints

- **API Rate Limits:** Google Ads API — batch size 10, chunk size 25 for safety
- **Data Retention:** 180 days search terms, ~6 years performance
- **Tech Stack:** Python for pipelines (Cloud Run), TypeScript for dashboard (Next.js/Vercel)
- **Competitive Metrics:** Only 33% coverage for impression/click share

---
*Last updated: 2026-02-21 after v1.1 milestone*
