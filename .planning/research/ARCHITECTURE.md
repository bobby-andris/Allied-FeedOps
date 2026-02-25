# Architecture Patterns

**Domain:** Content-performance feedback, historical data persistence, and migration evaluation for feed optimization platform
**Researched:** 2026-02-25
**Confidence:** HIGH (based on direct codebase inspection of existing tables, migrations, and data flows)

---

## Recommended Architecture

### High-Level Data Flow (Current + Proposed v1.3b Additions)

```
                       EXISTING                                    NEW (v1.3b)
                       --------                                    -----------

Google Ads API ─────> service.ts (2-min cache, ephemeral) ──> [NEW] funnel_snapshots_daily
       │                                                              │
       v                                                              v
search_queries ──────────────────────────────────────────────> Historical trend queries
keyword_metrics                                                       │
       │                                                              │
       v                                                              v
prompt_builder.py ──> generated_content ──> publish_events ──> [NEW] content_performance_feedback (VIEW)
       │                    │                     │                    │
       v                    │                     v                    v
regeneration_history        │            performance_snapshots ──> v1.4 closed-loop
  (prompt_hash)             │              (publish_event_id)      optimization
                            │                     │
                            v                     v
                     performance_baselines   performance_impact_scores
```

### Component Boundaries

| Component | Responsibility | Communicates With | Change Type |
|-----------|---------------|-------------------|-------------|
| `content_performance_feedback` | Materialized view linking content to CTR/CVR outcomes | generated_content, publish_events, performance_snapshots, regeneration_history | **NEW** materialized view |
| `funnel_snapshots_daily` | Daily persistence of service.ts ephemeral funnel data | service.ts (source), dashboard pages (consumer) | **NEW** table + capture endpoint + Cloud Scheduler |
| Migration triage | Evaluate 035b (14 tables) and 034b (4 tables) | intent TS files, 035b/034b SQL files | **Decision process**, then DB DDL cleanup |
| Data flow audit | Map every existing table to its writer(s) and reader(s) | All 36+ tables | **Analysis** producing a documented map |
| Empty table resolution | Populate or remove query_value_scores, routing_recommendations, opportunity_clusters | migration 033, optimization TS files | **Cleanup** -- remove or repurpose |

### Data Flow: Content-Performance Feedback

This is the critical missing link. The join keys exist across 4 tables but no single query connects them today.

**Current state (disconnected):**
```
generated_content.master_sku + .platform + .generation_prompt_hash
       (no direct FK to)
publish_events.master_sku + .platform + .prompt_hash + .published_at
       (FK exists via publish_event_id)
performance_snapshots.publish_event_id + .days_since_publish + .ctr + .cvr
       (plus baseline comparison via)
performance_baselines.master_sku + .platform + .avg_ctr + .avg_cvr
```

**Proposed: `content_performance_feedback` materialized view:**

```sql
CREATE MATERIALIZED VIEW content_performance_feedback AS
SELECT
    pe.id AS publish_event_id,
    pe.master_sku,
    pe.platform,
    pe.published_at,
    pe.prompt_hash,
    pe.evidence_hash,
    pe.published_title,
    pe.published_description,
    pe.quality_score,
    pe.content_version,
    gc.generation_model,
    gc.quality_breakdown,
    pb.avg_ctr AS baseline_ctr,
    pb.avg_cvr AS baseline_cvr,
    pb.avg_impressions AS baseline_impressions,
    ps_7d.avg_ctr AS ctr_7d,
    ps_7d.total_impressions AS impressions_7d,
    ps_14d.avg_ctr AS ctr_14d,
    ps_30d.avg_ctr AS ctr_30d,
    ps_30d.avg_cvr AS cvr_30d,
    CASE
        WHEN pb.avg_ctr > 0 AND ps_14d.avg_ctr IS NOT NULL
        THEN ((ps_14d.avg_ctr - pb.avg_ctr) / pb.avg_ctr) * 100
        ELSE NULL
    END AS ctr_lift_pct_14d,
    CASE
        WHEN pb.avg_cvr > 0 AND ps_30d.avg_cvr IS NOT NULL
        THEN ((ps_30d.avg_cvr - pb.avg_cvr) / pb.avg_cvr) * 100
        ELSE NULL
    END AS cvr_lift_pct_30d,
    rh.feedback_text AS last_feedback,
    rh.mode AS generation_mode
FROM publish_events pe
JOIN generated_content gc
    ON gc.master_sku = pe.master_sku
    AND gc.platform = pe.platform
    AND gc.is_current = true
LEFT JOIN performance_baselines pb
    ON pb.master_sku = pe.master_sku
    AND pb.platform = pe.platform
LEFT JOIN LATERAL (
    SELECT AVG(ctr) AS avg_ctr, SUM(impressions) AS total_impressions
    FROM performance_snapshots
    WHERE publish_event_id = pe.id
      AND days_since_publish BETWEEN 1 AND 7
) ps_7d ON true
LEFT JOIN LATERAL (
    SELECT AVG(ctr) AS avg_ctr
    FROM performance_snapshots
    WHERE publish_event_id = pe.id
      AND days_since_publish BETWEEN 1 AND 14
) ps_14d ON true
LEFT JOIN LATERAL (
    SELECT AVG(ctr) AS avg_ctr, AVG(cvr) AS avg_cvr
    FROM performance_snapshots
    WHERE publish_event_id = pe.id
      AND days_since_publish BETWEEN 1 AND 30
) ps_30d ON true
LEFT JOIN LATERAL (
    SELECT feedback_text, mode
    FROM regeneration_history
    WHERE master_sku = pe.master_sku
      AND platform = pe.platform
    ORDER BY created_at DESC
    LIMIT 1
) rh ON true
WHERE pe.status = 'success'
  AND pe.environment = 'production'
ORDER BY pe.published_at DESC;

-- Required for CONCURRENTLY refresh:
CREATE UNIQUE INDEX idx_cpf_publish_event
    ON content_performance_feedback (publish_event_id);
```

**Why materialized view, not a new table with its own write path:**
- No new write process to build or maintain -- data already exists across 4 tables
- Refresh daily after performance snapshot capture: `REFRESH MATERIALIZED VIEW CONCURRENTLY content_performance_feedback`
- Queryable like a table with proper indexes
- Zero risk of stale data diverging from source tables (refresh reconstructs from source)
- If LATERAL join performance becomes a concern at scale, convert to a table with trigger-based updates later

**Why not a regular view:**
- The 4 LATERAL subqueries with aggregation are expensive (~1-5s depending on data volume)
- Dashboard will hit this for SKU review and reporting pages frequently
- Materialized view caches the result; daily refresh is sufficient since performance data updates daily

### Data Flow: Historical Funnel Snapshots

**Problem:** `service.ts` runs 6 parallel GAQL queries with a 2-minute TTL cache. No history is persisted. Cannot compute trends, before/after impact, or seasonal patterns. The v1.3c milestone explicitly requires historical funnel data for trend analysis.

**Proposed: `funnel_snapshots_daily` table:**

```sql
CREATE TABLE funnel_snapshots_daily (
    id bigint GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    snapshot_date date NOT NULL,
    custom_label_0 text NOT NULL,
    tier text NOT NULL,  -- 'HIGH', 'MEDIUM', 'LOW'
    search_term text NOT NULL,
    impressions integer NOT NULL DEFAULT 0,
    clicks integer NOT NULL DEFAULT 0,
    cost_micros bigint NOT NULL DEFAULT 0,
    conversions numeric(12,4) NOT NULL DEFAULT 0,
    conversions_value numeric(14,4) NOT NULL DEFAULT 0,
    source_campaign text,
    ad_group_name text,
    created_at timestamptz NOT NULL DEFAULT now(),

    CONSTRAINT uq_funnel_snapshot_daily
        UNIQUE (snapshot_date, custom_label_0, tier, search_term)
);

CREATE INDEX idx_funnel_snapshots_date_label
    ON funnel_snapshots_daily (snapshot_date DESC, custom_label_0);
CREATE INDEX idx_funnel_snapshots_term
    ON funnel_snapshots_daily (search_term, snapshot_date DESC);
CREATE INDEX idx_funnel_snapshots_tier_date
    ON funnel_snapshots_daily (tier, snapshot_date DESC);
```

**Collection strategy:**
- New TypeScript API route: `POST /api/funnel/capture-snapshot` (on Vercel)
- Calls existing `service.ts` exports: `getExistingFunnelTerms()` + `getNeedsDecisionTerms()`
- Flattens into denormalized rows, upserts into `funnel_snapshots_daily`
- Triggered daily by Cloud Scheduler (same pattern as planned for performance snapshots)
- Estimated row growth: ~5,000-15,000 terms/day = ~150K-450K rows/month

**Why a new table, not extending `search_queries`:**
- `search_queries` stores variant-level data from the Python pipeline (keyed by gmc_offer_id)
- Funnel data is campaign-tier-level (keyed by custom_label_0 + tier + search_term)
- Different collection cadence, different source code (TS service.ts vs Python pipeline)
- Clean separation avoids polluting the search term pipeline with a different data shape

**Why not persist the full AdsContext:**
- `AdsContext` includes negative keyword lists, shared sets, criterion IDs -- operational state, not analytics
- Only performance metrics per search term per tier per label are needed for trend analysis
- Flat denormalized schema makes trend queries simple aggregations with GROUP BY

### Data Flow: Migration Evaluation Decision Framework

The 035b migration contains 14 tables. Both 034b and 035b comments state "Tables created out-of-band" meaning they likely exist in live Supabase but are empty. Here is the triage based on actual need for v1.3c (Actionable Shopping Intelligence) and v1.4 (Closed-Loop Optimization):

**035b -- 14 Intent Execution Tables:**

| Table | Referenced By (TS) | Needed for v1.3c? | Recommendation |
|-------|-------------------|--------------------|----------------|
| `intent_taxonomy_versions` | taxonomy.ts | NO -- v1.3c replaces intent classes with distribution-based scoring | **PRUNE** |
| `term_intent_state` | persistence.ts, policy.ts | MAYBE -- could store enriched term state, but v1.3c rewrites the scoring | **DEFER** to v1.3c |
| `policy_decision_log` | policy.ts | YES -- audit trail for tier movement decisions in v1.3c | **KEEP** |
| `policy_action_execution_log` | tier-movement.ts | YES -- tracks executed tier movements | **KEEP** |
| `policy_snapshots` | policy.ts | NO -- policy versioning is premature, no writer exists | **PRUNE** |
| `sku_margin_daily` | profit-forecast.ts | NO -- no margin data source exists (would need Shopify order API) | **PRUNE** |
| `order_line_returns_daily` | profit-forecast.ts | NO -- no returns data source exists | **PRUNE** |
| `attribution_confidence_daily` | value-signal.ts | NO -- GA4 attribution not in v1.3 scope | **PRUNE** |
| `experiment_registry` | multi-cell-experiment.ts | MAYBE -- A/B testing useful for v1.4 | **DEFER** to v1.4 |
| `experiment_assignments` | multi-cell-experiment.ts | MAYBE -- paired with registry | **DEFER** to v1.4 |
| `experiment_outcomes` | multi-cell-experiment.ts | MAYBE -- paired with registry | **DEFER** to v1.4 |
| `negative_registry` | policy.ts | YES -- tracks negative keywords added/removed by tier movements | **KEEP** |
| `search_buildout_recommendations` | buildout-intelligence.ts | YES -- stores search campaign expansion recommendations | **KEEP** |
| `operator_review_audit` | reviewer-calibration.ts | NO -- review queue calibration is v1.4+ at earliest | **PRUNE** |

**Summary:** KEEP 4, DEFER 4, PRUNE 6.

**034b -- 4 GA4 Attribution Tables:**

| Table | Referenced By | Recommendation |
|-------|--------------|----------------|
| `ga4_source_medium_daily` | No API routes | **PRUNE** |
| `ga4_landing_page_quality_daily` | No API routes | **PRUNE** |
| `ga4_attribution_root_cause_daily` | No API routes | **PRUNE** |
| `ga4_shopify_reconciliation_daily` | No API routes | **PRUNE** |

All 4 have zero API route references and no immediate use case. **Prune all 4.**

**Migration 033 -- Empty Optimization Tables:**

| Table | Writer | Reader | Recommendation |
|-------|--------|--------|----------------|
| `query_value_scores` | None (would be query-intelligence.ts) | intent/route.ts, governance/route.ts | **REPURPOSE** in v1.3c with distribution-based scoring |
| `routing_recommendations` | None (would be control-center.ts) | intent/route.ts | **REPURPOSE** in v1.3c |
| `opportunity_clusters` | None (would be control-center.ts) | governance/route.ts | **REPURPOSE** in v1.3c |
| `query_intent_features` | None (would be query-intelligence.ts) | governance/route.ts | **REPURPOSE** in v1.3c |

These tables have the right shape for v1.3c. Keep them; v1.3c will write to them with distribution-based scoring instead of hardcoded thresholds.

**Important implementation note:** "Pruning" means: (1) Confirm tables are empty via SQL, (2) DROP TABLE from live DB, (3) Remove from SCHEMA.md, (4) Mark referencing TypeScript files as deprecated or delete them. This is safe cleanup -- no data loss since tables are empty.

## Patterns to Follow

### Pattern 1: Materialized View for Cross-Table Analytics

**What:** Use PostgreSQL materialized views when dashboard needs to join 3+ tables for read-heavy analytics.
**When:** The underlying data changes at most daily (publish events + performance snapshots).

```sql
-- Refresh strategy: daily, after performance snapshot capture completes
REFRESH MATERIALIZED VIEW CONCURRENTLY content_performance_feedback;
```

**Implementation note:** The UNIQUE index on the materialized view is required for `CONCURRENTLY` to work (prevents table lock during refresh). Without `CONCURRENTLY`, the view is inaccessible during refresh.

### Pattern 2: Snapshot-Then-Query for Ephemeral API Data

**What:** Capture a daily snapshot of live API data into a denormalized table, then query the table for trends.
**When:** Data source is an external API with rate limits and no built-in history (service.ts / Google Ads API).

```typescript
// Capture endpoint pattern (matches existing /api/performance/capture-snapshot)
export async function POST(request: Request) {
    const existingTerms = await getExistingFunnelTerms({ dateWindow: 'LAST_30_DAYS' })
    const needsDecisionTerms = await getNeedsDecisionTerms({ dateWindow: 'LAST_30_DAYS' })
    const today = new Date().toISOString().split('T')[0]

    const rows = existingTerms.map(t => ({
        snapshot_date: today,
        custom_label_0: t.customLabel0,
        tier: t.assignedTier,
        search_term: t.searchTerm,
        impressions: t.impressions,
        clicks: t.clicks,
        cost_micros: t.costMicros,
        conversions: t.conversions,
        conversions_value: t.conversionsValue,
        source_campaign: t.sourceCampaign,
    }))

    const { error } = await supabase
        .from('funnel_snapshots_daily')
        .upsert(rows, { onConflict: 'snapshot_date,custom_label_0,tier,search_term' })
    // ...
}
```

### Pattern 3: Publish Event as the Universal Linkage Key

**What:** Use `publish_events.id` as the foreign key connecting content to performance outcomes.
**When:** Building any content-to-outcome analysis.
**Why:** `publish_events` already captures everything needed for the join:
- `prompt_hash` -- links to regeneration_history
- `evidence_hash` -- identifies the evidence bundle used
- `published_title`, `published_description` -- exact content published
- `quality_score`, `content_version` -- quality metadata at publish time
- `published_at` -- timing reference for performance windows

The FK chain already exists:
```
publish_events.id = performance_snapshots.publish_event_id  (existing FK)
publish_events.master_sku + platform = generated_content.master_sku + platform  (natural key)
publish_events.prompt_hash = regeneration_history.prompt_hash  (hash join)
```

No new foreign keys needed. The materialized view simply makes this join explicit and cached.

### Pattern 4: Cloud Scheduler for Daily Collection Jobs

**What:** GCP Cloud Scheduler triggers HTTP POST to Vercel API routes on a daily schedule.
**When:** Any data that needs daily persistence (performance snapshots, funnel snapshots).

```
Cloud Scheduler (daily, e.g., 6:00 AM UTC)
  ├── POST /api/performance/capture-snapshot     (existing, planned)
  ├── POST /api/funnel/capture-snapshot           [NEW]
  └── (after both complete)
      POST /api/refresh-materialized-views        [NEW, optional]
```

This follows the same pattern already planned for performance snapshot capture. One scheduler, multiple endpoints.

### Pattern 5: Graceful Degradation for Optional Tables

**What:** TypeScript code checks for table existence before querying, returns warnings instead of errors.
**When:** Tables from deferred migrations may or may not exist in the live database.

Already implemented in `dashboard/src/lib/intent/persistence.ts`:
```typescript
import { insertRowsSafe, isMissingRelationError } from '@/lib/intent/persistence'

// insertRowsSafe() catches PostgreSQL error 42P01 (undefined_table)
// and returns { inserted: 0, warning: "Table missing..." } instead of throwing
```

Reuse this pattern for all 035b table access during the transition period.

## Anti-Patterns to Avoid

### Anti-Pattern 1: Building a Separate Feedback Table with Its Own Write Path

**What:** Creating a `content_feedback_outcomes` table that requires a new background job to populate.
**Why bad:** Introduces a new data pipeline to maintain. Risks going stale independently of source tables. Duplicates data already in publish_events + performance_snapshots.
**Instead:** Materialized view computes the linkage from existing tables. Zero new write paths. Single REFRESH command keeps it current.

### Anti-Pattern 2: Persisting Full AdsContext Objects as JSON Blobs

**What:** Storing the entire `AdsContext` from service.ts (~50KB+ including negative keyword lists, criterion IDs, campaign maps) as a JSONB column.
**Why bad:** Most of it is operational state useless for analytics. Makes queries slow and storage expensive (~1.5GB/month at daily capture).
**Instead:** Flatten to the specific metrics needed. Simple typed columns with proper indexes. ~50MB/month.

### Anti-Pattern 3: Applying All 18 Deferred Migration Tables at Once

**What:** Running both 034b and 035b migrations wholesale to "clean up" the deferred state.
**Why bad:** Creates/validates 18 tables, 10 of which have no writer and no immediate consumer. Bloats the schema. Makes SCHEMA.md harder to maintain. Empty tables create confusion about what is implemented vs aspirational.
**Instead:** Triage each table individually. Keep the 4 needed for v1.3c. Prune the 10 that have no near-term use. Defer 4 to v1.4.

### Anti-Pattern 4: Live Google Ads Queries for Trend Analysis

**What:** Computing 7-day and 30-day trends by calling service.ts multiple times with different date windows.
**Why bad:** Each call runs 6 parallel GAQL queries. Multiple calls for trend windows multiplies API quota usage. Google Ads API has daily quota limits. Also, service.ts cache TTL is 2 minutes so rapid sequential calls still hit the API.
**Instead:** Persist daily snapshots once. Query the snapshot table for any historical window with simple SQL aggregations.

### Anti-Pattern 5: Creating New TS Libraries for Pruned 035b Tables

**What:** Writing new code to populate/query 035b tables that will be pruned (sku_margin_daily, operator_review_audit, etc.).
**Why bad:** The tables have no data, no data source, and no immediate consumer. Code for empty tables is pure maintenance burden.
**Instead:** For KEEP tables, use them only when v1.3c actually needs them. For PRUNE tables, drop them and delete/deprecate the referencing TS files.

## Scalability Considerations

| Concern | At 100 SKUs published | At 500 SKUs published | At 2,784 SKUs (full catalog) |
|---------|----------------------|----------------------|------------------------------|
| `content_performance_feedback` matview refresh | <1s | ~5s (500 events x 30 days) | ~30s (acceptable for daily refresh) |
| `funnel_snapshots_daily` row growth | ~5K rows/day | ~10K rows/day | ~15K rows/day (~5.5M/year) |
| Google Ads API quota for snapshot capture | 1 call/day (6 GAQL queries) | Same (label-level, not SKU-level) | Same (funnel is by custom_label_0, not by SKU) |
| Matview index size | Negligible | ~10MB | ~50MB (fine for Supabase Pro) |
| Performance snapshot capture at scale | Fast (100 SKUs) | Batch chunking needed | Already implemented in pipeline (chunk size 25) |

**Data retention strategy for `funnel_snapshots_daily`:**
- Keep 90 days at full per-term granularity
- After 90 days, aggregate into `funnel_snapshots_weekly` rollup (by custom_label_0 + tier, no per-term detail)
- Implement as a monthly cleanup cron after 3+ months of data accumulation
- Alternative: Supabase table partitioning by month if row growth exceeds 500K/month

## Build Order (Dependency-Informed Phase Structure)

### Phase 1: Architecture Audit and Migration Triage
**No code changes. Pure analysis.**

1. Verify which 035b/034b tables actually exist in live Supabase (`SELECT tablename FROM pg_tables WHERE schemaname = 'public'`)
2. Check which tables have any rows (`SELECT count(*) FROM table_name` for each)
3. Map every table to its writer(s) and reader(s) -- produce documented data flow map
4. Identify dead-end tables (writers but no readers, or readers but no writers)
5. Formal triage decision on each of 18 deferred tables (keep/prune/defer) -- documented with rationale
6. Decision on migration 033 empty tables (query_value_scores, routing_recommendations, opportunity_clusters)
7. API quota analysis: measure current Google Ads API usage to confirm daily snapshot is sustainable

**Output:** Data flow map document, migration triage decisions, quota assessment

### Phase 2: Content-Performance Feedback Linkage
**Uses only existing tables. No new data collection.**

1. Create `content_performance_feedback` materialized view via Supabase migration
2. Add unique index for `CONCURRENTLY` refresh support
3. Create `/api/content-performance/summary` endpoint to query the view
4. Wire into SKU review dashboard -- add "Content Impact" indicator showing CTR lift vs baseline
5. Set up refresh mechanism (initially manual via API call, then daily via Cloud Scheduler)
6. Validate with real data: pick 5 published SKUs, confirm the view correctly links content to outcomes

**Output:** Working materialized view, dashboard integration, validated linkage

### Phase 3: Historical Data Persistence
**New table, new endpoint, new scheduler job.**

1. Create `funnel_snapshots_daily` table via Supabase migration
2. Create `POST /api/funnel/capture-snapshot` endpoint (TypeScript, Vercel)
3. Test with manual invocation -- verify rows written correctly
4. Wire to Cloud Scheduler for daily execution (alongside performance snapshot)
5. Backfill initial 30-day window by calling service.ts once with LAST_30_DAYS
6. Add basic trend query to Shopping Funnel page: 7d vs previous 7d comparison
7. Add data freshness indicator to funnel pages showing last snapshot date

**Output:** Daily funnel persistence, trend queries, backfilled history

### Phase 4: Migration Cleanup and End-to-End Validation
**Cleanup based on Phase 1 decisions.**

1. Drop the PRUNE tables from live DB (after confirming empty): 6 from 035b + 4 from 034b
2. Delete or deprecate TypeScript files that only reference pruned tables
3. For KEEP tables: verify they have correct indexes and RLS policies
4. Update SCHEMA.md to reflect current true state
5. End-to-end data flow validation: trace a single SKU from generation through publish through performance through feedback view
6. Document the validated data flow for v1.3c and v1.4 consumption

**Output:** Clean schema, updated documentation, validated end-to-end flow

### Phase ordering rationale:
- **Phase 1 first** -- all subsequent phases depend on knowing which tables exist and which to keep
- **Phase 2 before Phase 3** -- the feedback view uses only existing tables (zero new infrastructure), while funnel persistence requires new table + endpoint + scheduler
- **Phase 3 before Phase 4** -- funnel persistence may inform which empty tables from 033 to repurpose vs remove
- **Phase 4 last** -- cleanup depends on all prior phases completing to make informed prune/keep decisions

## Integration Points Summary

| Integration | Existing Component | New Component | Connection |
|------------|-------------------|---------------|------------|
| Content to outcomes | publish_events + performance_snapshots | content_performance_feedback matview | JOIN on publish_event_id (existing FK) |
| Funnel history | service.ts (live API, 6 GAQL queries) | funnel_snapshots_daily table | Capture endpoint calls service.ts exports, writes to new table |
| Daily automation | Cloud Scheduler (planned) | capture-snapshot endpoints | HTTP POST triggers (same pattern as performance snapshots) |
| Dashboard display | SKU review pages | Content Impact column | Query matview by master_sku, show CTR lift |
| Prompt learning | regeneration_history.prompt_hash | feedback matview | Join via prompt_hash through publish_events |
| v1.3c prerequisite | Empty 033 optimization tables | Populated by distribution-based scoring | v1.3c writes to kept tables with new algorithms |
| v1.4 prerequisite | content_performance_feedback matview | Closed-loop regeneration trigger | v1.4 reads matview to identify underperforming content for re-generation |

## Sources

- **Direct codebase inspection** (HIGH confidence):
  - `docs/database/SCHEMA.md` -- all table definitions, columns, indexes, FKs
  - `supabase/migrations/033_optimization_control_plane.sql` -- empty optimization tables
  - `supabase/migrations/034b_DEFERRED_ga4_attribution_forensics.sql` -- 4 GA4 tables
  - `supabase/migrations/035b_DEFERRED_unified_intent_execution_system.sql` -- 14 intent tables
  - `dashboard/src/lib/shopping-funnel/service.ts` -- 6 GAQL queries, 2-min cache, AdsContext structure
  - `dashboard/src/lib/intent/persistence.ts` -- graceful degradation pattern for missing tables
  - `dashboard/src/lib/intent/*.ts` -- 18 TypeScript files referencing 035b tables
- **Project documentation** (HIGH confidence):
  - `.planning/PROJECT.md` -- v1.3b scope, known issues, tech debt
  - `docs/plans/2026-02-21-strategic-milestone-assessment.md` -- Part 3 architecture gaps analysis
  - `docs/plans/2026-02-21-gsd-milestone-v1.3-actionable-intelligence.md` -- v1.3c prerequisites
- **PostgreSQL materialized views** (MEDIUM confidence): Standard PostgreSQL feature. Verify Supabase managed PostgreSQL supports `CREATE MATERIALIZED VIEW` and `REFRESH MATERIALIZED VIEW CONCURRENTLY` -- expected to work on Supabase Pro plan which runs full PostgreSQL 15+.
