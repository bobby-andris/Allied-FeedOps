# Schema Scalability Audit

**Date**: 2026-02-11
**Auditor**: schema-auditor
**Scope**: Scaling from 84 SKUs to all 2,892 master SKUs (~75K variants) with historical Google Ads data and ongoing performance monitoring

---

## 1. Current State Summary

### Row Counts

| Table | Current Rows | Current Size |
|-------|-------------|-------------|
| product_catalog | 75,770 | 127 MB (101 MB data + 26 MB indexes) |
| variant_index | 72,023 | 58 MB (35 MB data + 23 MB indexes) |
| search_queries | 2,147 | 5.5 MB |
| search_queries_by_master_sku | 894 | 600 KB |
| keyword_metrics | 714 | 840 KB |
| generated_content | 496 | 872 KB |
| regeneration_history | 194 | 920 KB |
| performance_baselines | 168 | 72 KB |
| publish_events | 29 | 128 KB |
| performance_snapshots | 1 | 48 KB |
| search_query_snapshots | 0 | 56 KB (empty, indexes only) |
| keyword_coverage_master | 0 | 40 KB (empty) |
| keyword_coverage_variant | 0 | 40 KB (empty) |

### Coverage

- **84 / 2,784** master SKUs have search query data (3%)
- **76 / 2,784** master SKUs have performance baselines (2.7%)
- Average **25.6 queries per SKU**, max **198 queries** (CL-55)
- **197 rows** with `master_sku = NULL` in search_queries (data quality issue)

### Key Findings

- `search_queries_by_master_sku` is a **BASE TABLE** (not a materialized view) -- good for read performance, but requires manual sync
- **No partitioned tables** in the FeedOps schema (only Supabase system `messages` table is partitioned)
- **RLS policies** exist on performance_baselines, performance_snapshots, search_queries, keyword_metrics -- all "Allow all" (permissive), minimal overhead
- `performance_snapshots` has **NO unique constraint** on (master_sku, platform, snapshot_date) -- risk of duplicate snapshots

---

## 2. Growth Projections

### search_queries (HIGHEST RISK)

**Current**: 2,147 rows for 84 SKUs
**Projected at full catalog**: ~74K rows (2,784 SKUs x 25.6 avg queries/SKU)
**With historical periods** (12 monthly periods): ~888K rows
**With quarterly refresh** (4 periods/year ongoing): ~296K new rows/year
**3-year projection**: ~1.8M rows

**Size estimate**: ~1.8M rows x (5.5MB / 2,147 rows) = ~4.6 GB data + ~1.6 GB indexes = ~6.2 GB total

**Current indexes (9 total)**:
1. `search_queries_pkey` (id)
2. `search_queries_query_text_gmc_offer_id_period_start_period__key` (unique: query_text, gmc_offer_id, period_start, period_end)
3. `idx_search_queries_master_sku` (master_sku)
4. `idx_search_queries_gmc` (gmc_offer_id)
5. `idx_search_queries_finish` (finish_code)
6. `idx_search_queries_impressions` (impressions DESC)
7. `idx_search_queries_period` (period_start, period_end)
8. `idx_search_queries_sync_job` (sync_job_id)
9. `idx_search_queries_ad_group_id` (ad_group_id)

**Risk**: 9 indexes on a high-write table. Each bulk sync inserts thousands of rows; index maintenance will slow writes significantly at 1M+ rows.

### search_queries_by_master_sku (MODERATE RISK)

**Current**: 894 rows
**Projected at full catalog**: ~74K rows (same query count, aggregated at SKU level)
**With historical periods**: ~888K rows
**Concern**: This is a BASE TABLE that must be manually kept in sync with search_queries. No trigger or materialized view refresh mechanism observed.

### performance_snapshots (HIGHEST RISK - TIME SERIES)

**Current**: 1 row
**Weekly snapshots for full catalog**: 2,784 SKUs x 2 platforms x 52 weeks = ~290K rows/year
**Daily snapshots**: ~2M rows/year
**3-year projection (weekly)**: ~870K rows; (daily): ~6M rows

**Critical gap**: NO unique constraint on (master_sku, platform, snapshot_date). Without this, duplicate snapshots can accumulate unchecked.

### search_query_snapshots (HIGHEST RISK - TIME SERIES)

**Current**: 0 rows
**Weekly snapshots**: ~74K unique queries x 52 weeks = ~3.8M rows/year
**3-year projection**: ~11.5M rows

**Unique constraint exists**: (query_text, master_sku, snapshot_date) -- prevents duplicates, but this is a wide text-based unique index that will be expensive at millions of rows.

### keyword_metrics (LOW RISK)

**Current**: 714 rows
**Projected**: ~50K unique keywords (modest)
**30-day TTL**: Self-pruning if implemented; otherwise grows unbounded
**Risk**: Low. Even at 50K rows, this table stays small.

### performance_baselines (LOW RISK)

**Current**: 168 rows
**Max**: 2,784 SKUs x 2 platforms = ~5,568 rows (composite PK prevents growth beyond this)
**Risk**: Negligible. Natural cap from composite primary key.

### keyword_coverage_master / keyword_coverage_variant (MODERATE RISK)

**Current**: 0 rows (unused)
**Projected**: 2,784 SKUs x ~25 keywords = ~70K rows (master); 75K variants x ~25 keywords = ~1.9M rows (variant)
**Risk**: keyword_coverage_variant could reach ~2M rows but is simple data, manageable.

---

## 3. Top 5 Scalability Risks

### RISK 1: search_query_snapshots will be the largest table (CRITICAL)

**Problem**: At ~3.8M rows/year with no retention policy, this table will dominate storage. The unique constraint on `(query_text, master_sku, snapshot_date)` uses three columns, two of which are text -- expensive B-tree index at scale.

**Impact**: Query performance degrades, storage costs grow linearly, backups slow down.

**Recommendations**:
1. **Retention policy**: Add `created_at` column if missing, create a scheduled job to DELETE rows older than N months (suggest 12 months of detail, aggregate older data)
2. **Partition by snapshot_date**: Range partition by month. Enables fast `DROP PARTITION` for old data instead of expensive DELETEs
3. **Consider replacing text-based unique index** with a hash-based approach or integer foreign keys

### RISK 2: performance_snapshots lacks dedup and will grow unbounded (CRITICAL)

**Problem**: No unique constraint means duplicate snapshots can be inserted. No retention policy exists.

**Impact**: At 290K-2M rows/year, duplicates compound storage waste. Delta queries return incorrect results with duplicates.

**Recommendations**:
1. **Add unique constraint**: `CREATE UNIQUE INDEX idx_snapshots_unique ON performance_snapshots (master_sku, platform, snapshot_date, environment)` -- use UPSERT pattern in capture code
2. **Retention policy**: Keep 12 months of daily/weekly snapshots, aggregate to monthly summaries beyond that
3. **Partition by snapshot_date** (range, monthly) when table exceeds ~500K rows

### RISK 3: search_queries index bloat at scale (HIGH)

**Problem**: 9 indexes on a bulk-insert table. At ~1.8M rows, each sync operation (which can insert thousands of rows) will update all 9 indexes per row.

**Impact**: Sync operations slow from seconds to minutes. Index maintenance causes write amplification.

**Recommendations**:
1. **Audit index usage**: Run `pg_stat_user_indexes` to identify unused indexes. Candidates for removal:
   - `idx_search_queries_ad_group_id` (ad_group_id) -- only useful for debugging
   - `idx_search_queries_sync_job` (sync_job_id) -- only useful for job tracking, rarely queried
   - `idx_search_queries_finish` (finish_code) -- queries typically filter by master_sku first
2. **Consider composite indexes** instead of single-column: e.g., `(master_sku, impressions DESC)` replaces both individual indexes
3. **Batch inserts with deferred index updates**: If using Supabase client, insert with `COPY` or disable triggers during bulk loads

### RISK 4: search_queries_by_master_sku sync mechanism is fragile (HIGH)

**Problem**: This is a regular table (not a materialized view) that must be manually kept in sync with `search_queries`. If the sync code has bugs or is skipped, data drifts silently.

**Impact**: Dashboard shows stale/incorrect aggregated data. No automatic reconciliation.

**Recommendations**:
1. **Option A (preferred)**: Convert to a **materialized view** with `REFRESH MATERIALIZED VIEW CONCURRENTLY`. Add a unique index for concurrent refresh. Schedule refresh after each sync job.
   ```sql
   CREATE MATERIALIZED VIEW search_queries_by_master_sku_mv AS
   SELECT ... FROM search_queries GROUP BY master_sku, query_text, period_start, period_end;
   CREATE UNIQUE INDEX ON search_queries_by_master_sku_mv (master_sku, query_text, period_start, period_end);
   ```
2. **Option B**: Keep as table but add a database trigger on search_queries to auto-update aggregates on INSERT/UPDATE/DELETE
3. **Option C**: Keep current approach but add a "last_synced_at" check in the dashboard to warn when data is stale

### RISK 5: No data lifecycle / retention policies anywhere (MODERATE)

**Problem**: No table has any mechanism for archiving or purging old data. Tables that accumulate time-series data (snapshots, search queries, regeneration_history, sync_jobs) will grow indefinitely.

**Impact**: Supabase free/pro plans have storage limits. Even on paid plans, unbounded growth increases backup times, query planning complexity, and costs.

**Recommendations**:
1. **Create a retention policy table**:
   ```sql
   CREATE TABLE data_retention_policies (
     table_name text PRIMARY KEY,
     retention_days integer NOT NULL,
     archive_strategy text DEFAULT 'delete', -- 'delete', 'aggregate', 'export'
     last_cleanup_at timestamptz
   );
   ```
2. **Suggested retention periods**:
   - `search_query_snapshots`: 365 days (aggregate to monthly beyond)
   - `performance_snapshots`: 365 days (aggregate to monthly beyond)
   - `search_query_sync_jobs`: 90 days
   - `regeneration_history`: 365 days
   - `keyword_metrics`: 90 days (30-day TTL already designed, just not enforced)
   - `search_queries`: Keep latest period only per (query_text, gmc_offer_id); archive historical periods
3. **Implement via pg_cron** (available on Supabase) or external Cloud Scheduler hitting a cleanup endpoint

---

## 4. Missing Indexes

| Table | Missing Index | Rationale |
|-------|--------------|-----------|
| performance_snapshots | UNIQUE on (master_sku, platform, snapshot_date, environment) | Prevent duplicate snapshots |
| performance_snapshots | Index on (snapshot_date DESC) alone | For retention cleanup queries |
| search_queries | Composite (master_sku, period_start, impressions DESC) | Common query pattern: top queries for SKU in period |
| keyword_metrics | Index on updated_at | For TTL-based staleness checks |

---

## 5. Data Quality Issues

1. **197 rows in search_queries have NULL master_sku** -- these are orphaned records that won't appear in any SKU-level queries. Should investigate and either fix the mapping or delete them.
2. **search_queries_by_master_sku** has no foreign key to variant_index or any validation that master_sku values are valid.
3. **performance_snapshots** allows duplicate entries for the same SKU/platform/date combination.

---

## 6. Recommendations Priority Matrix

| Priority | Action | Effort | Impact |
|----------|--------|--------|--------|
| P0 | Add unique constraint to performance_snapshots | Low | Prevents data corruption |
| P0 | Fix 197 NULL master_sku rows in search_queries | Low | Data quality |
| P1 | Implement retention policy for time-series tables | Medium | Prevents storage blowout |
| P1 | Audit and remove unused indexes on search_queries | Low | Faster bulk inserts |
| P1 | Add composite index (master_sku, period_start, impressions DESC) to search_queries | Low | Query performance |
| P2 | Convert search_queries_by_master_sku to materialized view | Medium | Data consistency |
| P2 | Add updated_at index to keyword_metrics | Low | TTL query performance |
| P3 | Partition search_query_snapshots by month | Medium | Future-proofing for 3M+ rows |
| P3 | Partition performance_snapshots by month | Medium | Future-proofing for 500K+ rows |
| P3 | Create summary/aggregate tables for long-term trend analysis | High | Enables fast historical queries |

---

## 7. Supabase-Specific Considerations

1. **pg_cron**: Available on Supabase paid plans. Use for scheduled retention cleanup and materialized view refresh.
2. **Connection pooling**: Supabase uses PgBouncer. Bulk insert operations should use single transactions, not individual row inserts, to minimize connection overhead.
3. **Storage limits**: Supabase Pro plan includes 8 GB. Current usage is ~192 MB. Projected 3-year usage at full scale: ~8-12 GB for data tables + indexes. May need to upgrade or implement aggressive retention.
4. **Read replicas**: Not needed at current scale, but if dashboard queries start competing with bulk sync writes, consider Supabase read replicas for dashboard reads.
5. **RLS overhead**: All high-growth tables have "Allow all" RLS policies. While permissive, RLS still adds a small overhead per query. Consider disabling RLS on tables only accessed via service_role key (server-side only).

---

## 8. Quick Wins (Can implement today)

```sql
-- 1. Add unique constraint to prevent duplicate performance snapshots
CREATE UNIQUE INDEX IF NOT EXISTS idx_perf_snapshots_unique
ON performance_snapshots (master_sku, platform, snapshot_date, environment);

-- 2. Add updated_at index to keyword_metrics for TTL queries
CREATE INDEX IF NOT EXISTS idx_keyword_metrics_updated_at
ON keyword_metrics (updated_at);

-- 3. Add composite index for common search_queries access pattern
CREATE INDEX IF NOT EXISTS idx_search_queries_sku_period_imp
ON search_queries (master_sku, period_start, impressions DESC);

-- 4. Investigate NULL master_sku rows
SELECT query_text, gmc_offer_id, impressions, period_start
FROM search_queries
WHERE master_sku IS NULL
ORDER BY impressions DESC
LIMIT 20;
```
