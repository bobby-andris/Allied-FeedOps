# Phase 31: Schema Cleanup & End-to-End Validation - Context

**Gathered:** 2026-02-25
**Status:** Ready for planning

<domain>
## Phase Boundary

Production schema reflects reality — no aspirational empty tables confusing users, no orphaned components, no stale SCHEMA.md. The full data loop (generate → publish → capture → feedback) is validated end-to-end. Existing production workflows (especially Shopping Funnel) MUST NOT be disrupted.

</domain>

<decisions>
## Implementation Decisions

### Orphaned Components (GmcDisapprovalBadge, PromptLineagePanel)
- Wire both components into the **main SKU Review variant only** (not magazine or original variants)
- **Hide when no data** — don't render component shell if underlying data is missing/empty
- Components should conditionally render based on data availability, not show empty states

### Empty Dashboard Pages — DEFER'd Tables
- **Optimization Control Center** and **Intent Control Center**: Show "Coming Soon" / "Coming in v1.3c" state when accessed
- Keep pages in sidebar navigation with a visual indicator (e.g., badge or dimmed text)
- Code stays in repo — don't delete, just add the Coming Soon gate

### Empty Dashboard Pages — KEEP'd Tables
- **Search Governance** and **Experiment Lab**: Validate with seed data, then clean up test rows
- **Shopping Funnel**: DO NOT TOUCH the existing page — it is a critical production workflow used daily
- Create a **new separate page** (e.g., "Intent Intelligence" or "Tier Movements") for term_intent_state tier movement features
- Zero risk to existing Shopping Funnel functionality

### Seed Data Approach
- Build a **lightweight Python seed script** that reads existing search_queries data and populates term_intent_state with basic intent classifications
- Use seed data to validate Search Governance, Experiment Lab, and the new Tier Movements page render correctly
- Clean up seed data after validation (don't leave test rows in production)

### Dead Code / DEFER'd File Consumers
- Leave files referencing DEFER'd tables **as-is** (profit-forecast.ts, value-signal.ts, bid-policy/route.ts)
- They already handle empty results gracefully — no code changes needed
- They'll activate automatically when data pipelines are built in v1.3c

### SCHEMA.md Update
- **Full refresh from production** — query `information_schema.columns` and rebuild SCHEMA.md from scratch
- Document ALL 18 deferred tables with clear **[KEEP]** and **[DEFER]** status tags
- Include Phase 29-30 tables (content_performance_summary, funnel_snapshots, etc.)
- Guarantees nothing is missed — no incremental patching

### E2E Validation
- **Manual walkthrough** with a **real production SKU** that already has performance baselines and published content
- Trace the **full loop including funnels**: generate → publish → capture snapshot → see feedback in content-performance view → verify funnel snapshot data
- Document findings as a **validation report** (not an automated test)
- Validates all Phase 28-30 work integrates correctly in production

### Claude's Discretion
- Exact "Coming Soon" UI treatment for DEFER'd pages (banner, overlay, redirect — whatever fits cleanly)
- Which real SKU to use for E2E validation (pick one with richest data coverage)
- New page name and nav placement for tier movements (e.g., "Intent Intelligence", "Tier Movements")
- Seed script design — how many rows, which intent classes to simulate
- Order of operations for the phase (schema verification, component wiring, validation can be parallelized)

</decisions>

<specifics>
## Specific Ideas

- Shopping Funnel is used by Bobby's dad for hours daily — absolute zero-risk requirement for that page
- Tier movement / intent state features belong on a brand new page, not added to Shopping Funnel
- SCHEMA.md should serve as the single source of truth for any future session's database queries

</specifics>

<deferred>
## Deferred Ideas

- Automated E2E smoke test script (manual walkthrough is sufficient for Phase 31; automation could be a future quality-of-life improvement)
- Cloud Scheduler setup for GA4 snapshot-capture endpoint (mentioned in Phase 28 triage — should evaluate if this belongs in Phase 31 scope or is a separate operational task)

</deferred>

---

*Phase: 31-schema-cleanup-end-to-end-validation*
*Context gathered: 2026-02-25*
