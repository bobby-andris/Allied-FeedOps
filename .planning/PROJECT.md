# Allied-FeedOps

## What This Is

A content generation and feed optimization platform for Allied Brass Manufacturing — ~120 master SKUs expanding to ~3,300 Google Merchant Center listings across 28 finishes. Generates optimized product titles, descriptions, and lifestyle images for Google Shopping, Bing Shopping, and Shopify, then publishes through Google Sheets supplemental feeds and Shopify's GraphQL API. Dashboard (Next.js/Vercel) provides SKU review, batch publishing, performance tracking, and content regeneration. Pipeline (Python/Cloud Run) serves all content generation via Claude Sonnet 4.6.

## Core Value

The pipeline produces high-quality product content reliably at scale, backed by accurate performance data that maps seamlessly across Google Ads, Shopify, and Merchant Center.

## Current Milestone: (Planning next milestone)

**Previous:** v1.0 Pipeline Reliability Rewrite (shipped 2026-03-03), v1.1 Dead Code Cleanup + Data Infrastructure (shipped 2026-03-04)

**Next milestone candidates:**
- Pipeline reliability rewrite (see `docs/setup/pipeline-rewrite-brief.md`)
- Bing content fix (96 SKUs with hardcoded finish names)
- Dashboard data model migration (master_sku → gmc_offer_id joins)

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
- ✓ Dead code removal (8 orphan functions, ~500-line feature flag, ~130-line re-export block, 6 duplicate functions) — v1.1
- ✓ Schema hardening (unique constraints, CHECK constraints, FK on performance_snapshots) — v1.1
- ✓ Offer ID normalization across all data codepaths — v1.1
- ✓ Entity relationship documentation (variant_index as hub) — v1.1
- ✓ Bulk baseline capture for all ~2,500 master SKUs — v1.1
- ✓ Image wiring through executor.py to Claude provider — v1.1
- ✓ Shared utils extraction (utils.py canonical location) — v1.1

### Active

<!-- Next milestone scope — TBD -->

(No active requirements — run `/gsd:new-milestone` to define next scope)

### Out of Scope

- Bing {FINISH_NAME} regeneration (96 SKUs) — next milestone, generation works correctly now
- v1.3c dashboard phases (tier intelligence redesign, distribution scoring) — PAUSED
- v1.4 closed-loop optimization (performance-informed regeneration) — future
- Deferred database migrations (034b GA4 attribution, 035b intent execution) — not yet evaluated
- New dashboard pages or UI changes
- Prompt content rewriting

## Context

**Codebase state:** 60+ PRs merged across v1.0–v1.1. Pipeline decomposed from 3,737-line monolith to 9 focused modules + shared utils. Claude Sonnet 4.6 serving all production traffic (84% cheaper, 2x faster than GPT-5.2). ~1,200 lines of dead code removed in v1.1.

**Data infrastructure:** Schema constraints hardened (unique, CHECK, FK). Offer ID normalization applied across all 4 Python data codepaths. Variant-level performance tables created. Bulk baseline capture available for all ~2,500 master SKUs.

**Entity mapping:** `variant_index` (72K rows) is the documented central hub linking GMC offer IDs ↔ master SKUs ↔ Shopify product/variant IDs ↔ finish codes. Entity relationships documented with Mermaid ER diagrams.

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
| Dead code before data infra | Low-risk cleanup reduces noise before schema changes | ✓ Good |
| variant_index as entity hub | Already 72K rows, central to all cross-platform mapping | ✓ Good |

---
*Last updated: 2026-03-04 after v1.1 milestone completion*
