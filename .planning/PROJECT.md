# Allied FeedOps

## What This Is

A Google Ads feed optimization platform that automatically collects search performance data, generates AI-powered product content with Google Shopping intelligence, and publishes optimized feeds to Google Merchant Center, Bing, and Shopify. Built for Allied Brass's 2,784-SKU catalog to improve search visibility and conversion rates through data-driven content optimization with measurement infrastructure to track impact.

## Core Value

Transform low-performing product feeds into high-converting assets by combining real search query data with AI content generation informed by Google Shopping ranking intelligence, enabling data-driven optimization at scale for the entire catalog.

## Current State (after v1.2)

**What's shipped:**
- Full Google Ads data pipeline: search terms, performance metrics, Keyword Planner for all 2,784 SKUs
- Daily automated refresh via Cloud Scheduler
- Dashboard with compact SKU review, per-platform approval badges, inline detail expansion
- User-controlled variant selection for lifestyle image generation with impression-based auto-fallback
- Performance page with baseline vs. snapshot delta comparison and trend indicators
- Content generation via Cloud Run Python pipeline (single SKU, batch, and hybrid multi-SKU)
- Publishing to Google Sheets supplemental feed, Shopify, and Bing
- **v1.2: Google Shopping intelligence** — ranked ranking factor research, competitive gap analysis, 15-category YAML config wired into all generation prompts
- **v1.2: GPT-5.2 upgrade** — model switch with accuracy guardrail in SYSTEM_PROMPT
- **v1.2: Unified prompt builder** — `build_core_prompt()` used by all 4 generation paths (eliminated path divergence)
- **v1.2: Measurement infrastructure** — bottleneck classifier (5 categories), prompt lineage tracking, GMC disapproval sync, feature flag capture at generation time
- **v1.2: SKU coverage funnel** — live on overview page showing catalog → generated → approved → published → confirmed
- **v1.2: Structured feedback** — tone/emphasis/length controls with persistent corrections per SKU
- **v1.2: Three-dimensional image guidance** — 28-finish lighting, 30-category scenes, collection DNA in lifestyle image prompts

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

### Validated (v1.2)

- ✓ GOOG-01 through GOOG-05: Google Shopping intelligence — ranking factors, competitive analysis, optimization checklist, prompt integration, image guidance
- ✓ MODEL-01 through MODEL-03: Model research — GPT-5.2/Claude/Gemini benchmarks, model switch with accuracy guardrail
- ✓ DIAG-01 through DIAG-04: Diagnosis — SKU coverage funnel, code path tracing, feature flag audit, propagation spot-check
- ✓ MEAS-01 through MEAS-04: Measurement — feature flag capture, GMC disapproval sync, prompt lineage, bottleneck classifier
- ✓ FIX-01, FIX-02: Fixes — prompt parity (unified builder), feature flag observable activation

### Active

(No active milestone — run `/gsd:new-milestone` to start next)

### Out of Scope

- Real-time data streaming (batch collection sufficient)
- Multi-account Google Ads management (single account: 6253381786)
- Mobile app or native integrations (web dashboard sufficient)
- Full Content API → Merchant API migration (Content API works until Aug 2026)
- Native Google Shopping experiments (only works with Performance Max)

## Context

### Technical Environment

- **Supabase Project:** qezuszwufortkiutlhym (36 tables, 36+ migrations)
- **Google Ads Customer ID:** 6253381786
- **GMC Merchant ID:** 136699027
- **Python Pipeline:** Cloud Run (auto-deploys on push to master, GPT-5.2 default model)
- **Dashboard:** Vercel (allied-feed-ops.vercel.app)
- **Developer Token:** Highest level with standard access

### Known Issues / Tech Debt

- 2 orphaned dashboard components (GmcDisapprovalBadge, PromptLineagePanel) — built but not yet surfaced in UI pages
- Phase 20 SUMMARY frontmatter uses underscore key convention in 20-01, 20-03, 20-04
- Pre-existing duplicate migration file numbers (026, 032, 033)
- Monitoring freshness endpoint slow (~51s) — has 10s timeout workaround

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
| GPT-5.2 as default model | 90.0/100 vs GPT-4o 76.4/100 quality; 18% higher cost acceptable | ✓ Good — clear quality improvement |
| Shopping intelligence in user prompt (not system) | Preserve OpenAI prompt caching for static SYSTEM_PROMPT | ✓ Good — caching-safe |
| Unified build_core_prompt() for all paths | Eliminated path divergence between UI and batch | ✓ Good — single code path |
| Accuracy guardrail in SYSTEM_PROMPT P0 | GPT-5.2 can over-embellish; guardrail prevents spec fabrication | ✓ Good — immutable safety |
| Research-first before code changes | v1.2 started with 3 research phases before touching code | ✓ Good — evidence-backed fixes |
| Persistent corrections via sku_corrections table | Per-SKU feedback accumulates, not lost between sessions | ✓ Good — corrections survive regeneration |

## Constraints

- **API Rate Limits:** Google Ads API — batch size 10, chunk size 25 for safety
- **Data Retention:** 180 days search terms, ~6 years performance
- **Tech Stack:** Python for pipelines (Cloud Run), TypeScript for dashboard (Next.js/Vercel)
- **Competitive Metrics:** Only 33% coverage for impression/click share
- **Content API:** Works until Aug 2026 — Merchant API used only for diagnostic queries

---
*Last updated: 2026-02-21 after v1.2 milestone*
