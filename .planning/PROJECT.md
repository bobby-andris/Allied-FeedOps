# Allied-FeedOps

## What This Is

A content generation and feed optimization platform for Allied Brass Manufacturing — ~120 master SKUs expanding to ~3,300 Google Merchant Center listings across 28 finishes. Generates optimized product titles, descriptions, and lifestyle images for Google Shopping, Bing Shopping, and Shopify, then publishes through Google Sheets supplemental feeds and Shopify's GraphQL API. Dashboard (Next.js/Vercel) provides SKU review, batch publishing, performance tracking, and content regeneration. Pipeline (Python/Cloud Run) serves all content generation via Claude Sonnet 4.6.

## Core Value

The pipeline produces high-quality product content reliably at scale, backed by accurate performance data that maps seamlessly across Google Ads, Shopify, and Merchant Center.

## Current Milestone: v1.1 Dead Code Cleanup + Data Infrastructure

**Goal:** Remove dead code from the v1.0 pipeline decomposition, then fix and harden the Google Ads data import layer — correct schema constraints, proper entity relationships, full lifecycle data collection scaled to all SKUs.

**Target features:**
- Dead code removal (generator.py legacy paths, backward-compat re-exports, unused imports)
- Fix performance snapshot upsert constraint bug (daily Slack failures)
- Audit and correct all data table schemas and constraints
- Proper entity relationship mapping across Google Ads ↔ variant_index ↔ Shopify ↔ GMC
- Full lifecycle data collection (baselines → snapshots → impact scores) for all SKUs
- Image support wiring in executor.py

## Requirements

### Validated

<!-- Shipped and confirmed valuable -->

- ✓ Single-SKU content generation (`/optimize-sku`) — v1.0
- ✓ Content regeneration with feedback (`/regenerate`) — v1.0
- ✓ Batch job creation and status tracking (`/batch-optimize`, `/batch-status`) — v1.2
- ✓ Hybrid multi-SKU generation with variant adaptation (`/hybrid-generate`) — v1.3b
- ✓ Lifestyle image generation (`/generate-images`) — v1.3b
- ✓ Performance baseline capture (`/performance/capture-baseline`) — v1.2
- ✓ Search insights sync (`/search-insights/sync`) — v1.2
- ✓ Health check with Supabase status (`/health`) — v1.0
- ✓ `run_async_in_thread()` background task pattern — v1.3b
- ✓ Finish placeholder contract (`{FINISH_NAME}`, `{FINISH_SENTENCE}`) — v1.3a
- ✓ Prompt authority chain (prompt_builder → prompts.py → prompt_loader → shopping_intelligence) — v1.3a
- ✓ 98% human approval rate on generated Google content — v1.3b
- ✓ main.py decomposed into focused modules (9 extracted) — v1.0
- ✓ GPT-5.2 bugs fixed (all 5) — v1.0
- ✓ Claude provider with structured output — v1.0
- ✓ Model evaluation: Claude Sonnet 4.6 live in production — v1.0
- ✓ Deploy checklist workflow — v1.0

### Active

<!-- Current scope — v1.1 -->

- [ ] Remove dead code from pipeline decomposition
- [ ] Fix performance snapshot schema constraints
- [ ] Audit and correct all data import table schemas
- [ ] Design proper entity relationships for cross-platform data mapping
- [ ] Scale data collection to all SKUs (not just on-demand subset)
- [ ] Wire image support in executor.py

### Out of Scope

- Bing {FINISH_NAME} regeneration (96 SKUs) — next milestone, generation works correctly now
- v1.3c dashboard phases (tier intelligence redesign, distribution scoring) — PAUSED
- v1.4 closed-loop optimization (performance-informed regeneration) — future
- Deferred database migrations (034b GA4 attribution, 035b intent execution) — not yet evaluated
- New dashboard pages or UI changes
- Prompt content rewriting

## Context

**Codebase state:** 58+ PRs merged across v1.0–v1.0. Pipeline decomposed from 3,737-line monolith to 9 focused modules. Claude Sonnet 4.6 serving all production traffic (84% cheaper, 2x faster than GPT-5.2).

**Dead code:** ~500 lines of never-used variant generation behind `FEEDOPS_VARIANT_AT_LLM_TIME` feature flag, 7 duplicated functions in generator.py, ~130 lines of backward-compat re-exports in main.py, unused imports in extracted modules. See `/tmp/dead-code-research.md`.

**Data import issues:** Daily snapshot capture failing since launch — `performance_snapshots` table missing unique constraint for upsert. Only 274/2,500 master SKUs have baselines (on-demand only). Search term attribution approximate (campaign-level). Performance Max campaigns excluded. Offer ID case mismatch handled inconsistently. See `/tmp/google-ads-import-research.md`.

**Entity mapping:** `variant_index` (72K rows) is the central hub linking GMC offer IDs ↔ master SKUs ↔ Shopify product/variant IDs ↔ finish codes. Google Ads data flows through this table but the relationships aren't enforced or optimized at the schema level.

## Constraints

- **Backward compatibility**: All existing API endpoints must work identically
- **Background task pattern**: `run_async_in_thread()` MUST be preserved
- **Pre-deploy gates**: `cd dashboard && npm run build`, `npx tsc --noEmit`, `npm run lint` must pass
- **Content storage**: Generated content in Supabase only (not git)
- **Python pipeline**: Pipeline changes in Python; dashboard in TypeScript
- **Schema migrations**: Use Supabase migrations, test locally first

## Key Decisions

| Decision | Rationale | Outcome |
|----------|-----------|---------|
| Decompose before fixing bugs | Modular isolation makes bug fixes safer and testable | ✓ Good |
| Incremental prompt changes only | Phase 27 proved GPT-5.2 crashes on batch changes | ✓ Good |
| Preserve run_async_in_thread | Container lifecycle kills BackgroundTasks on scale-to-zero | ✓ Good |
| Claude Sonnet 4.6 as primary provider | 84% cheaper, 2x faster, 8.85/10 blind score | ✓ Good |
| Dead code before data infra | Low-risk cleanup reduces noise before schema changes | — Pending |
| variant_index as entity hub | Already 72K rows, central to all cross-platform mapping | — Pending |

---
*Last updated: 2026-03-03 after v1.1 milestone initialization*
