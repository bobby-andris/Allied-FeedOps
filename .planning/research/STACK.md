# Technology Stack — v1.3b Architecture Validation & Data Persistence

**Project:** Allied FeedOps v1.3b
**Researched:** 2026-02-25
**Milestone:** v1.3b (Architecture Validation & Data Persistence)
**Confidence:** HIGH (Supabase-native features verified via official docs; no new frameworks)

> **Scope note:** This document covers only NET NEW tooling needed for v1.3b.
> Existing stack (Next.js 14, Python/FastAPI, Supabase Postgres 15, Cloud Run, GPT-5.2,
> Google Ads API with Standard Access) is already installed and validated through v1.3a.
> Do not re-install or alter those packages.

---

## Guiding Principle

v1.3b adds NO new frameworks or services. Every addition is a Supabase-native feature, a standard npm package, or a PostgreSQL capability already available on the hosted platform. The goal is to use what Supabase and PostgreSQL already provide, not to add moving parts.

---

## Recommended Stack Additions

### 1. Content-Performance Feedback: Regular Table (NOT Materialized View)

| Technology | Version | Purpose | Why |
|------------|---------|---------|-----|
| PostgreSQL table + SQL view | Supabase Postgres 15 (existing) | `content_performance_feedback` table linking generated content to CTR/CVR outcomes | Regular table beats materialized view for this use case |

**Decision: Regular table populated by scheduled computation, NOT a materialized view.**

Rationale:
- Materialized views in Supabase lack Realtime support, have no Dashboard table visibility, and cannot have RLS policies applied directly (only via wrapping functions). [Source: Supabase GitHub Discussion #16389](https://github.com/orgs/supabase/discussions/16389)
- The feedback data is computed at specific moments (after performance snapshot capture), not derived from a continuously-changing live join. A regular table with a `computed_at` timestamp is simpler and fully supported by all Supabase features (RLS, Realtime, Dashboard, supabase-js client).
- The existing `performance_impact_scores` table already follows this exact pattern: it stores computed diff-in-diff results in a regular table, not a live view. Follow the established pattern.
- A lightweight SQL VIEW (not materialized) can be layered on top for convenience queries that join `publish_events`, `regeneration_history`, and `performance_snapshots` without data duplication concerns.

**What the table stores:** For each published SKU: `publish_event_id`, `prompt_hash` (from `publish_events.prompt_hash`), `content_version`, pre-publish baseline metrics (from `performance_baselines`), post-publish metrics at 7/14/30 day windows (from `performance_snapshots`), and computed deltas (CTR lift, CVR lift, ROAS change). The linkage chain is: `regeneration_history.prompt_hash` -> `publish_events.prompt_hash` -> `performance_snapshots.publish_event_id`.

**Confidence:** HIGH — follows existing `performance_impact_scores` pattern already validated in production.

---

### 2. Historical Data Persistence: `funnel_snapshots` Table

| Technology | Version | Purpose | Why |
|------------|---------|---------|-----|
| PostgreSQL table | Supabase Postgres 15 (existing) | `funnel_snapshots` table persisting service.ts GAQL query results | Replace 2-min in-memory cache with daily persistence |

**Decision: Daily snapshot table, populated by existing Cloud Scheduler infrastructure.**

Rationale:
- `dashboard/src/lib/shopping-funnel/service.ts` runs 6 GAQL queries with a 2-minute in-memory cache (`CACHE_TTL_MS = 2 * 60 * 1000`). This data is lost on every Vercel cold start, has zero historical record, and cannot be used for trend analysis.
- The project already has Cloud Scheduler calling performance capture endpoints daily. Add a companion endpoint or extend the existing one to also persist funnel data.
- The 6 GAQL queries return: search term performance by campaign tier, label-tier aggregates, and campaign structure. Store as daily aggregated rows, NOT raw GAQL responses (which would balloon storage).
- Estimated storage: ~100 labels x 3 tiers x 1 row/day = 300 rows/day = 110K rows/year. Trivial for Supabase free/pro tier.
- Service.ts can then read from the persisted table (with a freshness check) instead of always hitting Google Ads API live, reducing API calls and eliminating cold-start data loss.

**Confidence:** HIGH — straightforward table design following existing `performance_snapshots` and `search_query_snapshots` patterns.

---

### 3. Supabase pg_cron for Scheduled DB Computation

| Technology | Version | Purpose | Why |
|------------|---------|---------|-----|
| pg_cron | Built into Supabase (all plans) | Schedule feedback table computation and stale data cleanup | Eliminates need for external scheduler for DB-internal jobs |

**Decision: Use pg_cron for DB-internal scheduled work; keep Cloud Scheduler for API calls that need network access.**

Rationale:
- pg_cron is available on all Supabase plans and runs SQL snippets or database functions on cron schedules. [Source: Supabase Cron Docs](https://supabase.com/docs/guides/cron)
- Constraints: max 8 concurrent jobs, each max 10 minutes runtime. This is sufficient for computing feedback aggregates (~2,784 SKUs, simple joins).
- Use pg_cron for: (1) computing `content_performance_feedback` rows from snapshots after daily capture, (2) cleaning up stale `funnel_snapshots` older than 180 days, (3) refreshing any convenience SQL views.
- Keep Cloud Scheduler for: API endpoint calls that need network access (Google Ads GAQL queries, snapshot capture, Shopify polling).
- The project already discussed using pg_cron in `docs/plans/2026-02-11-schema-scalability-and-backfill.md` Phase 4 — this follows through on that plan.

**Confidence:** HIGH — Supabase documentation confirms availability, syntax, and limitations.

---

### 4. Dead Code Detection: Knip

| Technology | Version | Purpose | Why |
|------------|---------|---------|-----|
| knip | latest (5.x) | Detect dead TypeScript files, unused exports, unused dependencies in dashboard | De facto standard, replaces unmaintained ts-prune |

**Decision: Use Knip for migration evaluation dead code analysis.**

Rationale:
- ts-prune is unmaintained as of 2024. Knip is its successor and is used by Vercel, Shopify, Microsoft, and Google. [Source: Knip.dev](https://knip.dev/)
- Knip has a built-in Next.js plugin, which is critical since the dashboard is Next.js 14. It understands page routes, API routes, and Next.js-specific entry points automatically.
- Key capability for v1.3b: identify which of the 32 intent TypeScript files (`lib/intent/*.ts`) and 11 shopping-funnel files (`lib/shopping-funnel/*.ts`) are actually imported by live page/API routes vs completely orphaned. This directly informs whether to apply, prune, or remove the 18 deferred migration tables.
- Install as dev dependency only. Run on-demand during migration evaluation, not in CI (yet).

```bash
cd dashboard && npm install -D knip
```

**Confidence:** HIGH — well-documented, active maintenance, Next.js plugin confirmed on knip.dev.

---

### 5. Google Ads API Quota Management: No New Library Needed

| Technology | Version | Purpose | Why |
|------------|---------|---------|-----|
| Existing rate limiting | N/A | Validate current approach is sustainable | Document, don't add |

**Decision: No new rate-limiting library. Current patterns are sufficient; add quota monitoring.**

Rationale:
- The project has **Standard Access** developer token = **unlimited daily operations** for GET/mutate. [Source: Google Ads API Quotas](https://developers.google.com/google-ads/api/docs/best-practices/quotas)
- Rate limiting is per-QPS per customer ID, using a token bucket algorithm. The existing `ThreadPoolExecutor(5)` with batch size 10 and GAQL chunk size 25 is well within limits. [Source: Google Ads API Rate Limits](https://developers.google.com/google-ads/api/docs/best-practices/quotas)
- Planning Service (Keyword Planner) is limited to **1 QPS** per customer ID — this is the only real constraint and is already handled by sequential calls in `google_ads_search_terms.py`.
- GAQL `IN` clause maximum is **20,000 items** — current chunk size of 25 is far below this.
- The real question for v1.3b is not "are we hitting limits?" but "should we cache more aggressively to reduce unnecessary API calls?" Answer: yes, via the `funnel_snapshots` persistence table (item 2 above), which eliminates the 6 live GAQL queries on every dashboard page load.
- Optional: add a `api_quota_log` table to track daily API operations for long-term monitoring. LOW priority — implement only if quota concerns emerge.

**Confidence:** HIGH — Standard Access confirmed in PROJECT.md, quota docs are authoritative.

---

## What NOT to Add

| Temptation | Why Avoid | What to Do Instead |
|------------|-----------|-------------------|
| **Redis / Upstash for caching** | The 2-min cache problem is a persistence problem, not a speed problem. Adding Redis adds a service to monitor and pay for. | Persist to Supabase table; read from table with freshness check |
| **Prisma or Drizzle ORM** | 36+ tables already work with raw SQL via `supabase-js` and Python `supabase` client. Adding an ORM mid-project creates two data access patterns and migration confusion. | Continue raw SQL; document query patterns in SCHEMA.md |
| **dbt for data transformations** | Overkill for 3-4 computed tables. Adds a build pipeline, dbt profiles, and a new deployment concern. | pg_cron + SQL functions handle scheduled computation |
| **Apache Airflow / Prefect / Temporal** | Cloud Scheduler + pg_cron + Cloud Run background tasks cover all scheduling needs. A workflow orchestrator adds significant operational complexity. | Keep existing Cloud Scheduler for API calls, pg_cron for DB jobs |
| **Separate analytics database (BigQuery, ClickHouse)** | 2,784 SKUs with daily snapshots = ~1M rows/year. Supabase handles this trivially. No OLAP workload justifies a second database. | PostgreSQL indexes and partitioning if needed (won't be) |
| **pg_ivm (incremental materialized views)** | Not available on Supabase hosted platform per community discussions. | Regular tables with scheduled computation achieve the same result |
| **New Python packages for dead code** | Python codebase is small (~20 files in `src/feedops/`) and well-structured. | Manual audit + grep sufficient for Python; Knip for TypeScript |
| **Database branching / Supabase Branching** | Preview branches add complexity. Single production DB with careful migrations is sufficient at this scale. | Test migrations locally, apply via Supabase SQL Editor |

---

## Existing Stack (Validated, No Changes Needed)

### Core Framework
| Technology | Version | Purpose | Status |
|------------|---------|---------|--------|
| Next.js | 14.x | Dashboard | Stable, auto-deploys on Vercel |
| Python / FastAPI | 3.11+ | Cloud Run pipeline | Stable, auto-deploys via Cloud Build |
| Supabase | Postgres 15 | Database (36+ tables, 36+ migrations) | Stable |
| Vercel | N/A | Dashboard hosting | Auto-deploy on push |
| Cloud Run | N/A | Python pipeline hosting | Auto-deploy via Cloud Build |
| Cloud Scheduler | N/A | Daily data collection jobs | Running |

### Integrations (No Changes)
| Technology | Purpose | Status |
|------------|---------|--------|
| Google Ads API (Standard Access) | Search terms, performance, Keyword Planner | Working, unlimited daily ops |
| Google Sheets API | Supplemental feed publishing | Working |
| Shopify Admin API | Product publishing | Working |
| OpenAI API (GPT-5.2) | Content generation | Working |

### Key Existing Tables for v1.3b (Join Targets)
| Table | Role in v1.3b |
|-------|--------------|
| `performance_baselines` | Pre-publish metrics (join target for feedback computation) |
| `performance_snapshots` | Post-publish daily metrics (primary data source for feedback) |
| `performance_impact_scores` | Existing diff-in-diff pattern to follow |
| `publish_events` | Links content to publish timestamp + `prompt_hash` |
| `regeneration_history` | Links prompt_hash to content generation details |
| `generated_content` | Content versions with quality scores |
| `search_queries` | Persisted search term data (model for funnel persistence) |

---

## Installation

```bash
# Only new dependency: dashboard dev dependency for dead code analysis
cd dashboard && npm install -D knip

# No new Python dependencies needed
# No new Supabase extensions needed (pg_cron already available on all plans)
```

### pg_cron Setup (via Supabase SQL Editor or Dashboard > Integrations > Cron)

```sql
-- Jobs are created in the cron schema
-- Supabase Cron can also be managed via Dashboard UI

-- Example: Compute content-performance feedback daily at 6 AM UTC
-- (runs after Cloud Scheduler captures performance snapshots at 5 AM)
SELECT cron.schedule(
  'compute-content-feedback',
  '0 6 * * *',
  $$SELECT compute_content_performance_feedback()$$
);

-- Example: Clean up stale funnel snapshots (>180 days) weekly on Sunday 3 AM
SELECT cron.schedule(
  'cleanup-stale-funnel-data',
  '0 3 * * 0',
  $$DELETE FROM funnel_snapshots WHERE snapshot_date < CURRENT_DATE - INTERVAL '180 days'$$
);

-- Monitor job execution
SELECT * FROM cron.job_run_details ORDER BY start_time DESC LIMIT 20;
```

### Knip Configuration

```jsonc
// dashboard/knip.json
{
  "$schema": "https://unpkg.com/knip@5/schema.json",
  "entry": ["src/app/**/*.{ts,tsx}"],
  "project": ["src/**/*.{ts,tsx}"],
  "ignore": ["src/**/*.test.{ts,tsx}"],
  "next": true
}
```

```bash
# Run full dead code analysis
cd dashboard && npx knip

# Report unused exports only (most useful for migration evaluation)
cd dashboard && npx knip --include exports

# Report unused files only (identifies completely orphaned modules)
cd dashboard && npx knip --include files
```

---

## Migration Evaluation Tooling Summary

For evaluating the 18 deferred tables (034b: 4 GA4 tables, 035b: 14 intent tables):

| Tool | What It Tells Us | How to Run |
|------|-----------------|------------|
| **Knip** | Which TS files in `lib/intent/` and `lib/shopping-funnel/` are imported by live page/API routes vs orphaned | `cd dashboard && npx knip --include files` |
| **TypeScript compiler** | Which files have type errors from missing table types (32 files reference 035b tables) | `cd dashboard && npx tsc --noEmit 2>&1 \| grep -c error` |
| **grep** | Which API routes reference specific table names — determines code cleanup scope | `grep -r "intent_taxonomy\|term_intent_state\|experiment_registry" dashboard/src/app/` |
| **Supabase SQL** | Confirm which tables actually exist in production vs only in migration files | `SELECT tablename FROM pg_tables WHERE schemaname = 'public' ORDER BY tablename` |

No additional tooling needed beyond Knip. The TypeScript compiler and grep are already available.

---

## Schema Design Patterns for New Tables

### Pattern: Follow `performance_impact_scores`

The `performance_impact_scores` table is the model for `content_performance_feedback`:
- Regular table (not view)
- Populated by a computation function
- Foreign key to `publish_events`
- Indexed by `master_sku`, `publish_event_id`, computation date
- RLS enabled with permissive policy
- `computed_at` timestamp for freshness tracking

### Pattern: Follow `search_query_snapshots` for `funnel_snapshots`

- Daily fact table with `snapshot_date` column
- Unique constraint on `(label, tier, snapshot_date)` to prevent duplicates
- Index on `snapshot_date DESC` for recent-first queries
- `fetched_at` timestamp for data lineage

### RLS Policy Pattern (Existing)

All existing tables use permissive RLS:
```sql
ALTER TABLE new_table ENABLE ROW LEVEL SECURITY;
CREATE POLICY "Allow all access" ON new_table FOR ALL USING (true);
```

This is appropriate for a single-tenant application where authentication is handled at the application layer (Supabase Auth), not per-row.

---

## Confidence Assessment

| Component | Confidence | Rationale |
|-----------|------------|-----------|
| Regular table over materialized view | HIGH | Follows existing `performance_impact_scores` pattern; Supabase materialized view limitations well-documented in official discussions |
| pg_cron for scheduled computation | HIGH | Official Supabase docs confirm availability on all plans; max 8 concurrent / 10 min runtime is sufficient |
| Knip for dead code detection | HIGH | Active project (5.x), Next.js plugin confirmed, used by Vercel/Shopify/Microsoft |
| No new rate-limiting library | HIGH | Standard Access = unlimited daily ops confirmed in Google Ads API docs |
| funnel_snapshots persistence | HIGH | Straightforward table design; 110K rows/year is trivial; follows existing snapshot patterns |
| No Redis/dbt/Airflow/ORM | HIGH | Scale (2,784 SKUs, ~1M rows/year) does not justify additional infrastructure complexity |

---

## Sources

- [Supabase pg_cron Documentation](https://supabase.com/docs/guides/database/extensions/pg_cron) — HIGH confidence (official docs)
- [Supabase Cron Documentation](https://supabase.com/docs/guides/cron) — HIGH confidence (official docs)
- [Supabase Materialized View Limitations — GitHub Discussion #16389](https://github.com/orgs/supabase/discussions/16389) — HIGH confidence (official GitHub)
- [Google Ads API Quotas and Access Levels](https://developers.google.com/google-ads/api/docs/best-practices/quotas) — HIGH confidence (official docs)
- [Google Ads API Rate Limits](https://developers.google.com/google-ads/api/docs/best-practices/quotas) — HIGH confidence (official docs)
- [Knip — Dead Code Detector for JavaScript/TypeScript](https://knip.dev/) — HIGH confidence (official project site)
- [PostgreSQL REFRESH MATERIALIZED VIEW Documentation](https://www.postgresql.org/docs/current/sql-refreshmaterializedview.html) — HIGH confidence (official Postgres docs)
- [Supabase Views Documentation](https://supabase.com/docs/guides/graphql/views) — HIGH confidence (official docs)
- Existing project: `docs/plans/2026-02-11-schema-scalability-and-backfill.md` — pg_cron discussion (Phase 4)
- Existing project: `docs/plans/2026-02-21-strategic-milestone-assessment.md` — content-performance feedback gap identified (Part 5)
