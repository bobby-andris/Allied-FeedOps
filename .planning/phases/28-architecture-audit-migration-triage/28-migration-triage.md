# Migration Triage: Deferred Tables (034b + 035b)

**Audited:** 2026-02-25
**Requirement:** AUDIT-03
**Phase:** 28 (Architecture Audit & Migration Triage)

## Introduction

Allied FeedOps has 18 database tables created from two deferred migration files that were applied out-of-band (directly to production) but never formally integrated into the application lifecycle:

- **034b** (`034b_DEFERRED_ga4_attribution_forensics.sql`): 4 GA4 attribution forensics tables for diagnosing revenue attribution quality between GA4 and Shopify.
- **035b** (`035b_DEFERRED_unified_intent_execution_system.sql`): 14 intent classification, policy execution, experiment tracking, and search governance tables for a planned Unified Intent Execution System.

Both migration files explicitly state: *"Tables created out-of-band; this file is reference only."* This means the tables exist in the production Supabase instance but may contain zero rows if no data pipeline ever populated them.

### Triage Criteria

Each table is evaluated on:

1. **Code references** -- Which production TypeScript or Python files query or write to this table? (Excluding planning docs, migration files, and research notes.)
2. **Data state** -- Does the table exist in production? Does it have data? (Based on migration file status and code behavior.)
3. **Downstream need** -- Which v1.3b-v1.4 requirements benefit from this table?
4. **Complexity** -- How much work to wire up vs. how much value it provides?
5. **Feedback loop alignment** -- Does this table contribute to the capture-monitor-analyze-optimize cycle?

### User Directives

- **Infrastructure-forward bias**: Lean toward KEEP for tables that support future scale, even if current code consumers are sparse.
- **GA4 tables evaluated for KEEP**: User considers GA4 attribution important for the master plan (v1.3-v1.4).
- **Pruned tables**: Delete TypeScript consumer files in Phase 31, keep migration SQL files as reference.
- **Orphaned dashboard components**: Simple wiring in Phase 31; complex UI deferred to v1.3c/v1.4.

### Decision Key

- **KEEP**: Apply/verify migration in Phase 31. Table is a prerequisite for v1.3b-v1.4 features.
- **DEFER**: Table stays in production but is not actively used. Re-evaluate in v1.3c/v1.4.
- **PRUNE**: Drop table in Phase 31 (or leave empty). Delete TypeScript consumer files.

---

## 034b Tables (GA4 Attribution Forensics)

All 4 tables in 034b are part of a GA4 attribution quality monitoring pipeline. They are consumed by a single, fully-functional API route (`/api/ga4/snapshot-capture/route.ts`) that fetches GA4 data, cross-references with Shopify orders, and upserts results. The route includes graceful error handling for missing tables (`isMissingRelationError` check).

### ga4_source_medium_daily

- **Migration:** 034b
- **Purpose:** Stores daily GA4 source/medium breakdowns with quality buckets (not_set, data_not_available, valid), session counts, transaction counts, and revenue shares. Used to diagnose which traffic sources have poor attribution.
- **Code References:** 2 production files
  - `dashboard/src/app/api/ga4/snapshot-capture/route.ts` (upserts rows from GA4 API data)
  - `dashboard/src/lib/supabase/types.ts` (type definition in Database interface)
  - 1 test file: `dashboard/src/app/api/ga4/__tests__/snapshot-capture.route.test.ts`
- **Data State:** EXISTS in production (created out-of-band). Likely EMPTY or low row count -- depends on whether the snapshot-capture endpoint has been called.
- **Schema:** id (uuid PK), property_id, report_date, source_medium, quality_bucket (constrained), sessions, transactions, purchase_revenue, revenue_share, session_share, source_payload (jsonb), created_at. Unique index on (property_id, report_date, quality_bucket, source_medium).
- **Downstream Need:** v1.4 LOOP-01/LOOP-03 (content A/B attribution needs attribution quality signals). Feeds the "analyze & learn" stage of the feedback loop.
- **Decision:** KEEP
- **Reasoning:** Active code consumer exists with a complete write pipeline. GA4 attribution quality is foundational for the v1.3-v1.4 closed-loop optimization vision. The snapshot-capture endpoint is production-ready and can be triggered via Cloud Scheduler. Infrastructure-forward: keeping this table costs nothing and enables future attribution diagnostics.
- **Phase 31 Action:** Verify table exists and schema matches migration. Set up Cloud Scheduler to call `/api/ga4/snapshot-capture` daily to begin populating data.

### ga4_landing_page_quality_daily

- **Migration:** 034b
- **Purpose:** Stores daily GA4 landing page quality diagnostics -- which landing pages have sessions/transactions with "not_set" or "data_not_available" quality buckets. Used to identify pages with broken GA4 tracking.
- **Code References:** 2 production files
  - `dashboard/src/app/api/ga4/snapshot-capture/route.ts` (upserts rows)
  - `dashboard/src/lib/supabase/types.ts` (type definition)
  - 1 test file: `dashboard/src/app/api/ga4/__tests__/snapshot-capture.route.test.ts`
- **Data State:** EXISTS in production (created out-of-band). Likely EMPTY -- same condition as ga4_source_medium_daily.
- **Schema:** id (uuid PK), property_id, report_date, landing_page, quality_bucket (constrained), sessions, transactions, purchase_revenue, revenue_share, session_share, source_payload (jsonb), created_at. Unique index on (property_id, report_date, quality_bucket, landing_page).
- **Downstream Need:** Identifies landing pages with attribution gaps -- prerequisite for targeted attribution improvement in v1.4.
- **Decision:** KEEP
- **Reasoning:** Same active code consumer as ga4_source_medium_daily. Landing page quality data helps prioritize which product pages need GA4 implementation fixes. Keeps the GA4 attribution pipeline complete.
- **Phase 31 Action:** Verify table exists and schema matches migration. Populated by same Cloud Scheduler job as ga4_source_medium_daily.

### ga4_attribution_root_cause_daily

- **Migration:** 034b
- **Purpose:** Stores root cause analysis rows derived from source/medium, landing page, and campaign pattern data. Identifies specific reasons for attribution quality issues (e.g., "source_medium_not_set", "landing_page_invalid").
- **Code References:** 2 production files
  - `dashboard/src/app/api/ga4/snapshot-capture/route.ts` (upserts rows via `buildRootCauseRows()`)
  - `dashboard/src/lib/supabase/types.ts` (type definition)
  - 1 test file: `dashboard/src/app/api/ga4/__tests__/snapshot-capture.route.test.ts`
- **Data State:** EXISTS in production (created out-of-band). Likely EMPTY.
- **Schema:** id (uuid PK), property_id, report_date, root_cause_type, root_cause_key, sessions, transactions, purchase_revenue, revenue_share, session_share, source_payload (jsonb), created_at. Unique index on (property_id, report_date, root_cause_type, root_cause_key).
- **Downstream Need:** Actionable diagnostics for the "analyze" stage of the feedback loop. Without root cause data, attribution issues are visible but not debuggable.
- **Decision:** KEEP
- **Reasoning:** Derived from the same snapshot-capture pipeline. Root cause analysis is the diagnostic layer that makes the other GA4 tables actionable rather than just observational.
- **Phase 31 Action:** Verify table exists and schema matches migration. Populated automatically by snapshot-capture endpoint.

### ga4_shopify_reconciliation_daily

- **Migration:** 034b
- **Purpose:** Stores daily revenue reconciliation between GA4-reported revenue and Shopify order revenue. Tracks revenue_ratio (GA4/Shopify) to detect attribution drift. The route also checks consecutive out-of-range streaks and generates guardrail incidents.
- **Code References:** 2 production files
  - `dashboard/src/app/api/ga4/snapshot-capture/route.ts` (upserts reconciliation summary, reads last 3 rows for streak detection)
  - `dashboard/src/lib/supabase/types.ts` (type definition)
  - 1 test file: `dashboard/src/app/api/ga4/__tests__/snapshot-capture.route.test.ts`
- **Data State:** EXISTS in production (created out-of-band). Likely EMPTY.
- **Schema:** id (uuid PK), property_id, report_date, ga4_revenue, shopify_revenue, revenue_delta, revenue_ratio, order_count, source_payload (jsonb), created_at. Unique index on (property_id, report_date).
- **Downstream Need:** Revenue parity monitoring is critical for trusting performance metrics. If GA4 and Shopify revenue diverge significantly, all CTR/CVR-based content optimization decisions become unreliable.
- **Decision:** KEEP
- **Reasoning:** This is arguably the most important 034b table. Revenue reconciliation validates the integrity of all downstream metrics. The guardrail incident system already wires into this for automated alerts. Without reconciliation data, the entire feedback loop operates on potentially untrustworthy revenue signals.
- **Phase 31 Action:** Verify table exists and schema matches migration. Priority for Cloud Scheduler activation.
