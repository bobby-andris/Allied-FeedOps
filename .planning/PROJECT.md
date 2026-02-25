# Allied FeedOps

## What This Is

A Google Ads feed optimization platform that automatically collects search performance data, generates AI-powered product content with Google Shopping intelligence, and publishes optimized feeds to Google Merchant Center, Bing, and Shopify. Built for Allied Brass's 2,784-SKU catalog to improve search visibility and conversion rates through data-driven content optimization with measurement infrastructure to track impact.

## Core Value

Transform low-performing product feeds into high-converting assets by combining real search query data with AI content generation informed by Google Shopping ranking intelligence, enabling data-driven optimization at scale for the entire catalog.

## Current State (after v1.3a)

**What's shipped:**
- Full Google Ads data pipeline: search terms, performance metrics, Keyword Planner for all 2,784 SKUs
- Daily automated refresh via Cloud Scheduler
- Dashboard with compact SKU review, per-platform approval badges, inline detail expansion
- User-controlled variant selection for lifestyle image generation with impression-based auto-fallback
- Performance page with baseline vs. snapshot delta comparison and trend indicators
- Content generation via Cloud Run Python pipeline (single SKU, batch, and hybrid multi-SKU)
- Publishing to Google Sheets supplemental feed, Shopify, and Bing
- v1.2: Google Shopping intelligence, GPT-5.2 upgrade, unified prompt builder, measurement infrastructure
- **v1.3a: GPT-5.2 bug fixes** — temperature/reasoning mutual exclusion, json_schema strict mode, prompt cache retention, XML tags
- **v1.3a: Per-platform v2 generation** — separate Google/Bing/Shopify/finish sentence calls with strict JSON schemas, FEEDOPS_PROMPT_VERSION=v2 active on Cloud Run
- **v1.3a: Skill-driven prompts** — 8 runtime skill configs loaded via skill_loader.py, SYSTEM_PROMPT rewritten as creative brief, 24 categories
- **v1.3a: 15 gold standards** — across 15 product categories, wired into prompts via prompt_templates table
- **v1.3a: Quality rubric** — 10-criterion differentiation-first model replacing old 6-criterion compliance model
- **v1.3a: Title formula** — Robert's formula codified: {FINISH_NAME} first, product function, Collection, dims when varies, Allied Brass last
- **v1.3a: Content guardrails** — competitor brand prohibition, no "28 finishes" on variants, evidence exclusion rules, 120/120 constraint checks pass

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

### Planned (v1.3 Roadmap)

The v1.3 series addresses the **content quality crisis** identified in the strategic assessment
(`docs/plans/2026-02-21-strategic-milestone-assessment.md`). Despite v1.2's infrastructure
improvements, generated content remains generic and monotonous — keyword-stuffed fragments
that fail to differentiate Allied Brass from mass-market competitors.

**Milestone order (each builds on the previous):**

**v1.3a: Content Generation Excellence** (3 phases)
- Fix the content quality problem at its source: prompts, creative direction, and scoring
- 8 runtime config files already created (`src/feedops/config/`) — need to be wired into `prompt_builder.py`
- 8 Claude Code skills created (`.claude/skills/`) for development guidance
- Rewrite SYSTEM_PROMPT from compliance document → creative brief
- Create gold standard examples, expand category guidance, fix quality rubric
- Success: human-rated "significantly better" for 8/10 test SKUs

**v1.3b: Architecture Validation & Data Persistence** (2-3 phases)
- Evaluate and selectively apply deferred migrations (035b: 14 intent execution tables)
- Create content↔performance feedback table (links generated content to CTR/CVR outcomes)
- Add persistence for ephemeral service.ts Google Ads queries (currently 2-min cache, no history)
- Validate end-to-end data flow with no dead ends

**v1.3c: Actionable Shopping Intelligence** (4 phases)
- Existing spec: `docs/plans/2026-02-21-gsd-milestone-v1.3-actionable-intelligence.md`
- Replace hardcoded thresholds with distribution-based scoring
- Surface revenue leakage with dollar estimates
- Enable tier movements and market intelligence
- Requires 1.3a (good content) and 1.3b (validated architecture) as prerequisites

**v1.4: Closed-Loop Optimization** (2-3 phases)
- Build the feedback loop: capture → monitor → analyze → learn → optimize → repeat
- Performance-informed content regeneration
- Cross-system learning (what prompt changes drove CTR improvement?)
- Automated optimization cycles (daily/weekly/monthly)

### Validated (v1.3a)

- ✓ GPT52-01 through GPT52-05: GPT-5.2 integration bugs fixed (temperature, reasoning, json_schema, cache, XML tags)
- ✓ PRMT-01 through PRMT-05: Prompt architecture rewritten (creative brief, 8 configs wired, 24 categories, customer framing, competitive positioning)
- ✓ GOLD-01 through GOLD-04: Gold standards loaded (15 examples, 15 categories, 10-criterion rubric, batch evaluation)
- ✓ EVAL-01, EVAL-02, EVAL-04: Content regenerated, compared, passes differentiation test
- ✓ AUDIT-01 through AUDIT-05: Score model aligned, tests pass, audit report complete
- ⚠ EVAL-03: Human eval 8/10 threshold — not formally evaluated (accepted as tech debt)
- ⚠ EVAL-05: Quality scores >85% — actual 80.5/100 (accepted as tech debt)
- ⚠ EVAL-06: Test batch published — deferred to v1.3b

### Active

(No active milestone — run `/gsd:new-milestone` to start v1.3b)

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

- **Content quality improving but not yet at target** — v1.3a raised quality from 0/10 title wins to structurally correct titles; self-scores at 80.5/100 (target 85). Engagement criterion weakest at 6.9/10. v2 pipeline active but no test batch published yet for CTR/CVR measurement.
- **Score model dead in v2 path** — 10-criterion Score model only consumed by v1 code path; v2 generate_per_platform() returns raw dicts with no quality gating
- **Deferred migrations** — 034b (GA4 attribution, 4 tables) and 035b (intent execution, 14 tables) exist as files but NOT applied to live Supabase. TypeScript intent code (32 files) references 035b tables that don't exist in production
- **Ephemeral Google Ads data** — service.ts queries 6 GAQL queries with 2-minute cache, no historical persistence
- **Empty dashboard pages** — Shopping Funnel recommendations, Optimization Control, Intent Control, Search Governance, Experiment Lab all show zero results (hardcoded thresholds produce no matches)
- 2 orphaned dashboard components (GmcDisapprovalBadge, PromptLineagePanel) — built but not yet surfaced in UI pages
- Pre-existing duplicate migration file numbers (026, 032, 033)
- Monitoring freshness endpoint slow (~51s) — has 10s timeout workaround

### Dual-Use Skill Architecture

Skills serve two layers:
1. **Claude Code skills** (`.claude/skills/`) — full research-backed guidance for Claude when coding
2. **Runtime configs** (`src/feedops/config/`) — distilled rules injected into GPT-5.2 prompts during generation

All 8 runtime configs created: `shopping_intelligence.yaml`, `brand_voice.yaml`, `quality_rubric.yaml`, `finish_guide.yaml`, `storytelling_patterns.yaml`, `collection_stories.yaml`, `platform_bing.yaml`, `platform_shopify.yaml` + existing Python modules (`segment_strategy.py`, `collection_descriptions.py`, `keyword_bank.py`)

All 8 Claude Code skills created: `allied-brass-brand-expert`, `quality-evaluation`, `finish-expertise`, `product-storytelling`, `collection-storytelling`, `google-shopping-content`, `bing-shopping-content`, `shopify-conversion-content`

Gold standard examples: 30 total (10 Google avg 89.3/100, 10 Bing avg 87.8/100, 10 Shopify avg 88.7/100) covering 10 product categories

**Status:** Skills and configs complete. Pending: wire configs into `prompt_builder.py`, load gold standards into `prompt_templates` DB table, fix GPT-5.2 bugs.

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
| Content quality before optimization intelligence | Fix input data before optimizing what we do with it (garbage in, garbage out) | Pending — strategic assessment recommends 1.3a before 1.3c |
| Dual-use skills (Claude Code + runtime configs) | Skills guide Claude when coding AND inject into GPT-5.2 prompts at runtime | ✓ Complete — 8/8 skills + 8/8 runtime configs created, wiring into prompt_builder.py is v1.3a Phase 24 |
| Skills before agents for content quality | Better instructions to one model (skills) give better ROI than multiple agents arguing | ✓ Good — v2 per-platform with skills produces structurally correct content |
| Per-platform v2 generation | Separate GPT-5.2 calls for Google/Bing/Shopify/finish sentences | ✓ Good — eliminates cross-platform interference, strict JSON schemas |
| Feature flag for prompt versions | FEEDOPS_PROMPT_VERSION routes v1 vs v2 code paths | ✓ Good — safe rollback, v2 active in production |
| 3 rounds of human evaluation | Iterate prompts based on Bobby/Robert feedback | ⚠️ Revisit — R1 (0/10), R2 (4/10), R3 structurally correct but not formally scored |

## Constraints

- **API Rate Limits:** Google Ads API — batch size 10, chunk size 25 for safety
- **Data Retention:** 180 days search terms, ~6 years performance
- **Tech Stack:** Python for pipelines (Cloud Run), TypeScript for dashboard (Next.js/Vercel)
- **Competitive Metrics:** Only 33% coverage for impression/click share
- **Content API:** Works until Aug 2026 — Merchant API used only for diagnostic queries

---
*Last updated: 2026-02-25 after v1.3a milestone completed*
