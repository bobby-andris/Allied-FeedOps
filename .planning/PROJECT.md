# Allied FeedOps

## What This Is

A Google Ads feed optimization platform that automatically collects search performance data, generates AI-powered product content with Google Shopping intelligence, and publishes optimized feeds to Google Merchant Center, Bing, and Shopify. Built for Allied Brass's 2,784-SKU catalog to improve search visibility and conversion rates through data-driven content optimization with measurement infrastructure to track impact.

## Core Value

Transform low-performing product feeds into high-converting assets by combining real search query data with AI content generation informed by Google Shopping ranking intelligence, enabling data-driven optimization at scale for the entire catalog.

## Current State (after v1.3b)

**What's shipped:**
- Full Google Ads data pipeline: search terms, performance metrics, Keyword Planner for all 2,784 SKUs
- Daily automated refresh via Cloud Scheduler
- Dashboard with compact SKU review, per-platform approval badges, inline detail expansion
- User-controlled variant selection for lifestyle image generation with impression-based auto-fallback
- Performance page with baseline vs. snapshot delta comparison and trend indicators
- Content generation via Cloud Run Python pipeline (single SKU, batch, and hybrid multi-SKU)
- Publishing to Google Sheets supplemental feed, Shopify, and Bing
- v1.2: Google Shopping intelligence, GPT-5.2 upgrade, unified prompt builder, measurement infrastructure
- v1.3a: Per-platform v2 generation, skill-driven prompts, 15 gold standards, quality rubric, title formula, content guardrails
- **v1.3b: Data flow audit** — complete map with 11 Mermaid diagrams, 5 dead ends marked, circular feedback loop validated
- **v1.3b: Migration triage** — 18 deferred tables evaluated (14 KEEP, 4 DEFER), SCHEMA.md rebuilt to 56 tables
- **v1.3b: Content Impact dashboard** — landing + detail pages showing baseline vs post-publish CTR/CVR at 7/14/30-day windows, search term gained/lost split view
- **v1.3b: Funnel persistence** — daily snapshot capture endpoint, 7d vs prev-7d trend cards, backfill endpoint
- **v1.3b: Schema cleanup** — GmcDisapprovalBadge + PromptLineagePanel wired into SKU Review, Coming Soon states for DEFER'd pages, prompt_hash enforcement

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

### Validated (v1.3b)

- ✓ AUDIT-01 through AUDIT-05: Architecture audit complete — data flow map, migration triage (14 KEEP, 4 DEFER), NULL audit, API quota analysis (1.2% utilization), circular loop validated
- ✓ FEED-01 through FEED-04: Content-performance feedback linkage — Content Impact landing + detail pages, performance_impact_scores table, search query snapshot capture on publish, prompt_hash NOT NULL enforcement
- ✓ HIST-01 through HIST-03: Historical funnel persistence — funnel_snapshots_daily table, daily capture endpoint with Cloud Scheduler, 7d vs prev-7d trend indicators
- ✓ MIGR-01 through MIGR-04: Schema cleanup — 14 KEEP'd tables verified, dead code removed, orphaned components wired, SCHEMA.md rebuilt (56 tables, 1,589 lines)
- ⚠ Tech debt: Cloud Scheduler not yet activated, funnel data needs re-backfill, DiD compute pipeline pending (v1.3c/v1.4), prompt_hash NULL on existing publish events

### Active

## Next Milestone: v1.3c Actionable Shopping Intelligence

**Goal:** Replace hardcoded thresholds with distribution-based scoring, surface revenue leakage with dollar estimates, enable tier movement tracking and market intelligence.

**Prerequisites met:** v1.3a (good content) + v1.3b (validated architecture) both complete.
**Existing spec:** `docs/plans/2026-02-21-gsd-milestone-v1.3-actionable-intelligence.md`

### Out of Scope

- Real-time data streaming (batch collection sufficient)
- Multi-account Google Ads management (single account: 6253381786)
- Mobile app or native integrations (web dashboard sufficient)
- Full Content API → Merchant API migration (Content API works until Aug 2026)
- Native Google Shopping experiments (only works with Performance Max)

## Context

### Technical Environment

- **Supabase Project:** qezuszwufortkiutlhym (56 tables documented in SCHEMA.md, 14 KEEP + 4 DEFER from 035b/034b)
- **Google Ads Customer ID:** 6253381786
- **GMC Merchant ID:** 136699027
- **Python Pipeline:** Cloud Run (auto-deploys on push to master, GPT-5.2 default model)
- **Dashboard:** Vercel (allied-feed-ops.vercel.app)
- **Developer Token:** Highest level with standard access

### Known Issues / Tech Debt

- **Content quality improving but not yet at target** — v1.3a raised quality from 0/10 title wins to structurally correct titles; self-scores at 80.5/100 (target 85). v2 pipeline active but no test batch published for CTR/CVR measurement.
- **Score model dead in v2 path** — 10-criterion Score model only consumed by v1 code path; v2 generate_per_platform() returns raw dicts with no quality gating
- **Cloud Scheduler activation pending** — funnel_snapshots_daily capture endpoint built but scheduler needs CRON_SECRET + `bash scripts/setup-funnel-scheduler.sh`
- **Funnel data needs re-backfill** — backfill endpoint exists at `/api/funnel-snapshots/backfill`, data was populated (4,093 rows) but production table is empty
- **DiD compute pipeline missing** — performance_impact_scores table and Content Impact API exist but no process computes diff-in-diff scores (v1.3c/v1.4 scope)
- **prompt_hash NULL on existing publish_events** — forward enforcement active (FEED-04) but all historical rows lack prompt_hash
- **Optimization Control + Intent Control** — replaced with Coming Soon cards (DEFER'd to v1.3c)
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
| 14 KEEP / 4 DEFER for 18 deferred tables | Keep tables with active TypeScript consumers; defer tables with zero code references | ✓ Good — eliminated 034b GA4 tables (no code), kept all intent execution tables |
| Forward-only prompt_hash enforcement | Application-layer throw, no DB constraint; preserves legacy rows | ✓ Good — zero disruption to existing data |
| Write-behind funnel persistence | Capture endpoint called by Cloud Scheduler, not blocking live service.ts | ✓ Good — zero latency impact on dashboard |
| Coming Soon cards for DEFER'd pages | Server components replacing broken client pages that query empty tables | ✓ Good — eliminates user confusion |
| SCHEMA.md full rebuild from migration SQL | Trust migrations as source of truth over incremental documentation updates | ✓ Good — caught 3 schema drift items |

## Constraints

- **API Rate Limits:** Google Ads API — batch size 10, chunk size 25 for safety
- **Data Retention:** 180 days search terms, ~6 years performance
- **Tech Stack:** Python for pipelines (Cloud Run), TypeScript for dashboard (Next.js/Vercel)
- **Competitive Metrics:** Only 33% coverage for impression/click share
- **Content API:** Works until Aug 2026 — Merchant API used only for diagnostic queries

---
*Last updated: 2026-02-25 after v1.3b milestone completed*
