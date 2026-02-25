# Project Research Summary

**Project:** Allied FeedOps v1.3b — Architecture Validation & Data Persistence
**Domain:** Feed optimization platform — content-performance feedback loops, historical data persistence, deferred migration triage
**Researched:** 2026-02-25
**Confidence:** HIGH

## Executive Summary

Allied FeedOps v1.3b is a focused infrastructure milestone whose singular purpose is to close the gap between content generation and measurable performance outcomes. The platform already has all the raw data it needs — publish events, performance baselines, performance snapshots, regeneration history — but none of it is connected. The recommended approach treats this milestone as plumbing, not features: create a materialized view that joins existing tables into a single content-performance feedback record, persist the ephemeral service.ts funnel data into a daily snapshot table, and surgically triage 18 deferred migration tables so the schema reflects reality rather than aspiration.

The most important architectural decision for this milestone is to resist the temptation to build a new "feedback" table with its own write path. All the performance data already exists across five tables; the gap is a convenient JOIN and a reliable linkage chain (prompt_hash -> publish_event_id -> performance snapshots). A materialized view that refreshes daily costs nothing to maintain and puts zero new data in motion. This is the right tool. Similarly, the service.ts persistence problem is best solved by adding a write-behind snapshot endpoint — leaving the live query path completely unchanged — rather than rearchitecting the 1,600-line Google Ads integration.

The key risk is scope creep in two directions: applying all 18 deferred migration tables wholesale (which creates a schema full of empty aspirational tables), and building new write paths for data that already exists (which creates a maintenance fork). Research strongly recommends triage-first — audit actual production schema state before touching any migration file — and a strict rule that no new performance metric column (impressions, clicks, ctr) appears in any new table. This milestone lays the data foundation that v1.3c (distribution-based scoring) and v1.4 (closed-loop optimization) depend on. Getting the linkage chain right here is more important than delivering any user-visible feature.

---

## Key Findings

### Recommended Stack

v1.3b adds no new frameworks or services. Every addition is a native Supabase/PostgreSQL capability already available in the hosted environment. The stack research confirmed that the perceived "caching problem" with service.ts is actually a persistence problem — Redis or Upstash would solve the wrong problem and add a paid service to operate. Similarly, dbt and Airflow are overkill for a 3-table computation job that pg_cron handles in a SQL function. The only new developer dependency is Knip (dead code detection), installed as a dev tool only.

**Core technologies:**
- **PostgreSQL materialized view** (Supabase Postgres 15, existing): `content_performance_feedback` — joins publish_events + performance_snapshots into a single queryable artifact; daily REFRESH CONCURRENTLY keeps it fresh without blocking reads
- **Regular PostgreSQL table** (Supabase Postgres 15, existing): `funnel_snapshots_daily` — persists the 6 live GAQL query results from service.ts into daily rows; replaces 2-minute in-memory cache with queryable history
- **pg_cron** (built into all Supabase plans, zero setup cost): scheduled computation of feedback aggregates and stale data cleanup; eliminates need for Cloud Scheduler on DB-internal jobs; max 8 concurrent jobs, 10-min runtime — sufficient for 2,784 SKU workloads
- **Knip v5.x** (dev dependency only): Next.js-aware dead code detection; identifies which of the 32 intent TypeScript files are orphaned vs referenced by live routes; directly informs migration triage decisions

**What NOT to add:** Redis, Prisma/Drizzle, dbt, Apache Airflow, BigQuery, Supabase Branching, pg_ivm (not available on hosted Supabase). Scale (2,784 SKUs, ~1M rows/year) does not justify any of these.

### Expected Features

The milestone has a clear three-phase feature structure. Phase 1 is pure analysis with no code changes; Phase 2 creates the critical feedback linkage using only existing tables; Phase 3 adds persistence infrastructure for historical funnel data.

**Must have (table stakes — prerequisites for v1.3c and v1.4):**
- **Data flow audit document** — no single document maps the complete flow from Google Ads API through every table to the dashboard; dead ends (empty optimization tables, orphaned components) are invisible without it; must come first
- **API quota sustainability confirmation** — service.ts makes 6 GAQL queries per page load; Standard Access provides unlimited daily ops but adding daily snapshot capture must be confirmed within rate limits before building persistence
- **Deferred migration triage** — 32 TypeScript files reference tables that don't exist in production; decision on each of 18 tables (KEEP 4, DEFER 4 to v1.4, PRUNE 10) must precede any schema work
- **Content-performance feedback view** — the only missing link between "what content was published" and "how it performed"; keyed on (master_sku, platform); scoped to Google only for v1.3b; joins regeneration_history -> publish_events -> performance_snapshots via existing FK chain
- **Historical funnel persistence** — `funnel_snapshots_daily` table with daily capture endpoint; Cloud Scheduler daily trigger; backfill initial 30-day window

**Should have (differentiators that increase feedback loop value):**
- **Populate performance_impact_scores** — diff-in-diff scorecard table exists but is empty; compute job calculates treated vs control lift for published SKUs
- **Populate search_query_snapshots after publish** — table exists with FK to publish_events but nothing writes to it; enables "which search terms changed after content update" analysis
- **Wire or remove orphaned components** — GmcDisapprovalBadge and PromptLineagePanel exist but appear on no page; PromptLineagePanel is particularly valuable for feedback visibility

**Defer to v1.3c:**
- Distribution-based scoring for optimization tables (this is v1.3c Phase 1's entire scope — do not pre-build)
- Full experiment framework UI

**Defer to v1.4:**
- Content A/B attribution analysis (requires multiple publish cycles per SKU with different prompt_hashes)
- Automated regeneration based on performance outcomes

**Defer indefinitely:**
- 034b GA4 attribution tables (4 tables, zero code references, no data pipeline)

**Migration triage recommendation (035b — 14 intent execution tables):**
- KEEP 4: policy_decision_log, policy_action_execution_log, negative_registry, search_buildout_recommendations
- DEFER 4 to v1.4: experiment_registry, experiment_assignments, experiment_outcomes, term_intent_state
- PRUNE 6: intent_taxonomy_versions, policy_snapshots, sku_margin_daily, order_line_returns_daily, attribution_confidence_daily, operator_review_audit

### Architecture Approach

The architecture is materialized-view-first for read-heavy cross-table analytics, snapshot-table-first for external API data that needs history. No new write paths should be introduced for data that already exists in source tables. The publish event (`publish_events.id`) is the universal linkage key — it already has prompt_hash, evidence_hash, quality_score, published content, and a direct FK to performance_snapshots. The materialized view makes this join explicit and cached; no new write pipeline needed.

**Major components:**
1. **`content_performance_feedback` materialized view** — joins publish_events + generated_content + performance_baselines + performance_snapshots (via 4 LATERAL subqueries for 7/14/30-day windows); refreshed daily after snapshot capture; unique index on publish_event_id required for CONCURRENTLY refresh; surfaces CTR lift % in SKU review dashboard via new `/api/content-performance/summary` endpoint
2. **`funnel_snapshots_daily` table + capture endpoint** — denormalized daily rows (snapshot_date, custom_label_0, tier, search_term, impressions, clicks, cost_micros, conversions); unique constraint on (snapshot_date, custom_label_0, tier, search_term) prevents duplicates; new `POST /api/funnel/capture-snapshot` Vercel route calls existing service.ts exports write-behind; Cloud Scheduler triggers daily alongside performance snapshot capture; 90-day retention at full granularity, weekly rollup beyond
3. **Migration triage and cleanup** — verify production schema state first; KEEP 4 intent tables; DEFER 4 to v1.4; PRUNE 6 from 035b + all 4 from 034b; move deferred migration files to archive directory; delete or deprecate TypeScript files for pruned tables; update SCHEMA.md to reflect true state

### Critical Pitfalls

Research identified 13 pitfalls grounded in actual codebase inspection. The top 5 most likely to cause rewrites or milestone failure:

1. **Duplicating existing performance infrastructure** — the gap is JOIN quality and a convenient aggregation layer, not missing data. If any new migration contains columns named `impressions`, `clicks`, `ctr`, or `conversions`, it is duplicating data that already lives in `performance_snapshots`. Write the JOIN first; only create a new table if the JOIN reveals genuinely new data to store.

2. **Applying deferred migrations without pruning dead code first** — the 032/033/034b/035b migration chain was written speculatively with thresholds (ROAS 3.6/3.1/2.6) that produce zero results for Allied Brass's actual data. Correct order: categorize KEEP/DEFER/PRUNE, delete TypeScript for PRUNE tables, verify build passes, then clean migration files. Never apply a migration without a consumer that will populate it within the same milestone.

3. **Breaking the live Google Ads query path in service.ts** — persistence must be write-behind only. The live query path stays completely unchanged. Daily snapshot triggered by a separate scheduled job, not the dashboard page load. Monitor service.ts P95 latency; if it increases >20% after any change, the persistence layer is blocking the response path.

4. **Feedback loop without content versioning linkage** — audit NULL rates in `publish_events.prompt_hash` and `performance_snapshots.content_version` before building any feedback UI. If >10% of recent records have NULL in the join chain, the feedback loop will produce incomplete results. This is a hard prerequisite for v1.4 closed-loop optimization.

5. **Out-of-band tables already exist in production** — the 034b/035b migration headers state "Tables created out-of-band." Query production schema first (`SELECT tablename FROM pg_tables WHERE schemaname = 'public'`) before evaluating any migration. The decision may be "tables exist with schema drift, compare and reconcile" rather than "apply or skip."

---

## Implications for Roadmap

Based on combined research, the milestone decomposes into 4 sequential phases. Phase ordering is driven by a hard dependency chain: you cannot safely build the feedback view or persistence layer until you know which tables actually exist in production and which join keys have NULL gaps.

### Phase 1: Architecture Audit and Migration Triage
**Rationale:** All subsequent phases depend on knowing actual production schema state. The deferred migration files note "created out-of-band" — tables may already exist with stale schemas. Empty optimization tables from migration 033 will corrupt any analytics built on top of them. This phase has zero risk of breaking anything because it produces only documentation and decisions, no code changes.
**Delivers:** Data flow map (every table with writer, reader, row count), migration triage decisions (KEEP/DEFER/PRUNE for all 18 tables with rationale), NULL rate audit of join chain keys, API quota analysis confirming daily snapshot is sustainable, Knip report on which intent TypeScript files are orphaned
**Addresses:** Table stakes features — data flow audit, API quota analysis, migration triage decision
**Avoids:** Pitfall 2 (applying migrations without pruning), Pitfall 6 (building on empty tables), Pitfall 13 (out-of-band tables with schema drift)
**Research flag:** None — pure codebase analysis and production schema queries; no external research needed

### Phase 2: Content-Performance Feedback Linkage
**Rationale:** Uses only existing tables; no new infrastructure required. This is the highest-value deliverable of the milestone and the direct prerequisite for v1.4 closed-loop optimization. Doing this before the persistence work (Phase 3) validates the linkage chain on real data before more infrastructure is added.
**Delivers:** `content_performance_feedback` materialized view, `/api/content-performance/summary` endpoint, CTR lift indicator in SKU review dashboard, validated end-to-end content-to-outcome linkage for 5+ published SKUs, prompt_hash NOT NULL constraint enforced for new publishes
**Uses:** pg_cron for daily refresh scheduling; PostgreSQL LATERAL joins (full SQL provided in ARCHITECTURE.md); existing Supabase Postgres 15
**Implements:** content_performance_feedback component (Pattern 1 — Materialized View for Cross-Table Analytics)
**Avoids:** Pitfall 1 (duplicating performance infrastructure), Pitfall 4 (broken version chain — audit NULLs first), Pitfall 7 (per-platform complexity — key on master_sku + platform, scope to Google only for v1.3b)
**Research flag:** None — LATERAL join pattern is standard PostgreSQL; complete SQL already documented in ARCHITECTURE.md; Supabase materialized view behavior documented in STACK.md

### Phase 3: Historical Data Persistence
**Rationale:** Depends on Phase 1 (quota analysis confirms safety) and benefits from Phase 2 insights (understanding what data shape is actually needed for trend analysis). Introduces new infrastructure (table, endpoint, scheduler) — more risk than Phase 2, so comes after the simpler feedback view is validated against real data.
**Delivers:** `funnel_snapshots_daily` table with 90-day retention policy and weekly rollup job in same PR, `POST /api/funnel/capture-snapshot` Vercel endpoint (write-behind, feature-flagged), Cloud Scheduler daily trigger, backfilled 30-day history, 7d vs previous-7d trend query on Shopping Funnel page, data freshness indicator
**Uses:** Cloud Scheduler (existing), Supabase Postgres 15, pg_cron for weekly rollup cleanup
**Implements:** funnel_snapshots_daily component (Pattern 2 — Snapshot-Then-Query for Ephemeral API Data)
**Avoids:** Pitfall 3 (breaking live service.ts queries — write-behind only with feature flag), Pitfall 9 (unbounded storage growth — retention policy in same PR as table creation), Pitfall 5 (multi-SKU attribution — funnel data is label-level not SKU-level, unaffected)
**Research flag:** None — snapshot table pattern already validated by existing search_query_snapshots and performance_snapshots tables in the same codebase

### Phase 4: Migration Cleanup and End-to-End Validation
**Rationale:** Cleanup requires all prior phases to complete so informed prune/keep decisions can be made. Dropping tables that turn out to be needed by Phase 2 or 3 would require recovery. Comes last to avoid premature deletions.
**Delivers:** Pruned schema (10 tables dropped from 035b/034b after confirming empty), deprecated or deleted TypeScript files for pruned tables, SCHEMA.md updated to true state, end-to-end data flow validated for a single SKU (generation -> publish -> performance -> feedback view), documented data flow for v1.3c and v1.4 consumption
**Uses:** Knip (identifies which intent TypeScript files are safe to delete), TypeScript compiler (verify build passes after deletions), Supabase SQL Editor (DROP TABLE after row count confirmation)
**Avoids:** Pitfall 8 (migration numbering conflicts — move deferred files to archive directory, use sequential numbers from 037+), Pitfall 12 (migrations during active batch jobs — confirm no running jobs before any DDL)
**Research flag:** None — deterministic cleanup based on Phase 1 audit output; standard PostgreSQL operations

### Phase Ordering Rationale

- **Audit first** because the 034b/035b "created out-of-band" note means production schema state is genuinely unknown; building on unknown foundations risks immediate rework when the real state is discovered
- **Feedback view second** because it uses only existing tables (zero new infrastructure risk) and delivers the milestone's highest business value — v1.4 cannot exist without this linkage
- **Persistence third** because it introduces new infrastructure (table, endpoint, scheduler) and the quota analysis from Phase 1 is required to confirm the daily capture is within Google Ads API limits
- **Cleanup last** because dropping tables before all phases complete risks deleting something a later phase needs; also, PRUNE decisions are more informed once Phase 2 and 3 reveal which tables are actually touched during the work
- **Google-only scope for feedback in v1.3b**: Bing and Shopify feedback require different metric sources not currently captured; defer to v1.4 with explicit documentation

### Research Flags

All phases use standard patterns already validated in this codebase. No phases require `/gsd:research-phase` during planning:

- **Phase 1:** Pure codebase analysis and production SQL queries — no external research needed
- **Phase 2:** Materialized view pattern is standard PostgreSQL; complete LATERAL join SQL provided in ARCHITECTURE.md; Supabase limitations documented in STACK.md
- **Phase 3:** Snapshot table pattern matches existing `search_query_snapshots` and `performance_snapshots` tables; capture endpoint follows identical structure to existing `/api/performance/capture-snapshot`
- **Phase 4:** Deterministic cleanup based on Phase 1 output; Knip configuration documented in STACK.md with exact commands

---

## Confidence Assessment

| Area | Confidence | Notes |
|------|------------|-------|
| Stack | HIGH | No new frameworks; all additions are Supabase-native features verified in official documentation; Knip confirmed active at v5.x with Next.js plugin; pg_cron availability on all plans confirmed in Supabase docs |
| Features | HIGH | Based on exhaustive codebase review of schema, migrations, service.ts, strategic assessment, and PROJECT.md; feature list derived from actual schema gaps, not speculation |
| Architecture | HIGH | Materialized view SQL provided in full in ARCHITECTURE.md; funnel_snapshots_daily DDL provided in full; both patterns follow existing validated tables (performance_snapshots, search_query_snapshots) in the same codebase |
| Pitfalls | HIGH | All 13 pitfalls sourced from actual code inspection: hardcoded ROAS thresholds in control-center.ts, NULL rates in join keys documented, out-of-band migration comments read directly, service.ts cache architecture inspected |

**Overall confidence:** HIGH

### Gaps to Address

- **Production schema true state is unknown until Phase 1 executes:** The "created out-of-band" note in 034b/035b means tables may already exist with schema drift from the migration files. This cannot be resolved by research alone — Phase 1 must query the live DB before any migration decisions.

- **NULL rate in prompt_hash join chain:** Research identifies this as a critical prerequisite for the feedback view but cannot determine actual NULL rates without a live DB query. Phase 2 must audit `SELECT COUNT(*) FROM publish_events WHERE prompt_hash IS NULL AND published_at > '2026-02-01'` before building feedback UI. If >10% NULL, prompt_hash enforcement must be addressed before the view delivers meaningful results.

- **Quality score coverage in v2 content:** The v1.3a per-platform v2 architecture may not populate `quality_score` in `generated_content`. Phase 1 should verify with `SELECT COUNT(*) FROM generated_content WHERE quality_score IS NOT NULL AND generation_timestamp > '2026-02-20'`. If not populated, exclude quality_score from feedback correlations in v1.3b scope.

- **Which 035b/034b tables already exist in production:** The "created out-of-band" note changes the triage question from "should we apply this migration?" to "do these tables exist, and if so do their schemas match the migration files?" Only resolvable via Phase 1 production query.

---

## Sources

### Primary (HIGH confidence)
- `docs/database/SCHEMA.md` — complete 36+ table schema reference with column definitions, indexes, FK relationships
- `docs/plans/2026-02-21-strategic-milestone-assessment.md` — Part 3 architecture gaps analysis, Part 7 migration analysis with specific table recommendations
- `.planning/PROJECT.md` — v1.3b scope, known issues, tech debt inventory, deferred migration status
- `supabase/migrations/035b_DEFERRED_unified_intent_execution_system.sql` — 14 deferred intent table definitions with "created out-of-band" note
- `supabase/migrations/034b_DEFERRED_ga4_attribution_forensics.sql` — 4 deferred GA4 table definitions with "created out-of-band" note
- `supabase/migrations/033_optimization_control_plane.sql` — empty optimization tables (empty due to hardcoded ROAS thresholds)
- `dashboard/src/lib/shopping-funnel/service.ts` — 1,600-line live GAQL query layer, 2-min cache, AdsContext structure
- `dashboard/src/lib/intent/persistence.ts` — graceful degradation pattern (insertRowsSafe, isMissingRelationError) for missing tables
- `dashboard/src/lib/optimization/control-center.ts` — hardcoded ROAS thresholds (3.6/3.1/2.6) confirmed as reason optimization tables are empty
- [Supabase pg_cron Documentation](https://supabase.com/docs/guides/database/extensions/pg_cron) — availability on all plans, max 8 concurrent jobs, 10-min runtime limit
- [Supabase Materialized View Limitations — GitHub Discussion #16389](https://github.com/orgs/supabase/discussions/16389) — no RLS, no Realtime, no Dashboard visibility (rationale for regular table in some cases)
- [Google Ads API Quotas and Access Levels](https://developers.google.com/google-ads/api/docs/best-practices/quotas) — Standard Access = unlimited daily operations; 1 QPS Keyword Planner limit
- [Knip v5.x](https://knip.dev/) — Next.js plugin confirmed, active maintenance, used by Vercel/Shopify/Microsoft

### Secondary (MEDIUM confidence)
- `docs/plans/2026-02-11-schema-scalability-and-backfill.md` — pg_cron discussed in Phase 4; this milestone follows through on that existing recommendation
- `CLAUDE.md` — offer ID case sensitivity pattern (shopify_us_ vs shopify_US_), multi-SKU product pattern (product_id aggregation in Google Ads), established code conventions

---
*Research completed: 2026-02-25*
*Ready for roadmap: yes*
