# Domain Pitfalls

**Domain:** Adding content-performance feedback loops, historical data persistence, and deferred migration evaluation to an existing feed optimization platform
**Researched:** 2026-02-25
**System context:** Allied FeedOps v1.3b (36+ tables, 2,784 SKUs, Python pipeline + Next.js dashboard)

---

## Critical Pitfalls

Mistakes that cause rewrites, data corruption, or multi-week delays.

### Pitfall 1: Duplicating Existing Performance Infrastructure

**What goes wrong:** A new "content-performance feedback" table gets created that overlaps with what `performance_baselines`, `performance_snapshots`, `performance_impact_scores`, `regeneration_history`, and `publish_events` already track. You end up with two sources of truth for "what content was published and how did it perform."

**Why it happens:** The existing schema already has the building blocks but they are not linked together with a clean JOIN path. `performance_snapshots` has `publish_event_id` and `content_version`, `publish_events` has `prompt_hash` and `final_payload_hash`, and `regeneration_history` has `generated_content_id` and `prompt_hash`. The gap is data quality in the JOIN keys (NULLs, missing rows) and a convenient view — not a new table.

**Consequences:**
- Two codepaths for "get performance of content X" — dashboard and pipeline diverge
- Migration bloat (36 tables already, duplicate migration numbers 026/032/033 exist)
- Stale data when one table gets updated but its duplicate does not
- Every future feature (v1.3c scoring, v1.4 closed-loop) must pick which source to use

**Prevention:**
- Before creating ANY new table, write the SQL JOIN that connects `regeneration_history.prompt_hash` -> `publish_events.prompt_hash` -> `performance_snapshots.publish_event_id`. If this JOIN works, you need a VIEW or materialized view, not a table.
- If a lightweight linking table is needed (e.g., to cache computed feedback scores), it should reference existing PKs only — never duplicate columns like `impressions`, `clicks`, `ctr` that already live in `performance_snapshots`.
- Rule: new table columns should be ONLY the new data (feedback scores, learning signals, optimization recommendations). All performance metrics come via FK joins.

**Detection:** If a new migration has columns named `impressions`, `clicks`, `ctr`, `conversions`, or `content_version` — it is almost certainly duplicating existing data.

---

### Pitfall 2: Applying Deferred Migrations Without Pruning Dead Code First

**What goes wrong:** 035b's 14 intent execution tables get applied to production Supabase, making the 32 TypeScript files in `dashboard/src/lib/intent/` "work" — but the underlying logic has hardcoded thresholds (ROAS 3.6/3.1/2.6 in `control-center.ts`, CVR 5%/3% gates) that produce zero results for Allied Brass's actual data. You now have live tables being written to but showing nothing useful, and the next developer assumes the feature works.

**Why it happens:** The migration files exist, the TypeScript code exists, and the temptation is to "just apply and see." But the 032/033/034b/035b migration chain was written speculatively during v1.2 research phases — the code was never tested against real data because the tables never existed in production.

**Consequences:**
- 14 empty tables consuming Supabase resources and schema complexity
- Dashboard pages (Shopping Funnel recommendations, Optimization Control, Intent Control, Search Governance, Experiment Lab) show UI but with zero rows — users see "working" pages with no data, which is worse than a clean "coming soon" state
- Maintenance burden: any schema change to "real" tables must now avoid breaking the speculative tables
- Future v1.3c work must untangle which tables are actually needed vs which were speculative

**Prevention:**
1. Categorize each of the 18 deferred tables (4 from 034b, 14 from 035b) into: KEEP (needed for v1.3b/c/1.4), DEFER (not needed yet but valid design), or REMOVE (speculative, no clear use case within 6 months)
2. For KEEP tables: verify the TypeScript code that references them actually works by writing integration tests BEFORE applying the migration
3. For REMOVE tables: delete the TypeScript files first, verify build passes, THEN remove the migration file
4. Never apply a migration without a consumer that will populate and read the data within the same milestone

**Detection:** After applying any migration, query `SELECT COUNT(*) FROM [new_table]` after 7 days. If zero, the table is dead weight.

---

### Pitfall 3: Breaking the Live Google Ads Query Path in service.ts

**What goes wrong:** Adding persistence to `service.ts`'s 6 GAQL queries (~1,600 lines of live Google Ads API integration) introduces a write layer that blocks the response path, returns stale data from Supabase instead of live API, or causes API quota overruns by accidentally doubling query volume (once for cache, once for persistence).

**Why it happens:** `service.ts` runs 6 parallel GAQL queries against live Google Ads API with a 2-minute in-memory cache (`CACHE_TTL_MS = 2 * 60 * 1000`). The "add persistence" requirement means writing results to Supabase. But the write path adds latency, the read-then-write pattern can fail silently (Supabase timeout on large result sets), and changing cache behavior changes what the Shopping Funnel dashboard displays in real time.

**Consequences:**
- Dashboard shows stale data (user sees yesterday's numbers, thinks today's campaign is failing)
- Google Ads API quota exhaustion if persistence layer triggers additional queries (standard access: 15,000 operations/day)
- Silent data loss if Supabase writes fail but the in-memory cache still serves (no one notices persistence is broken for weeks)
- Race conditions: 6 parallel GAQL queries complete at different times, partial writes create inconsistent daily snapshots

**Prevention:**
1. Persistence must be WRITE-BEHIND, not read-through. The live query path stays unchanged. After serving the response, asynchronously persist to Supabase.
2. Add a separate "historical snapshot" endpoint/job that reads from Supabase — never modify the live query endpoint to read from the persistence layer.
3. Use a transaction or batch insert for the 6 query results — all succeed or all fail, never partial snapshots.
4. API quota analysis FIRST: calculate current queries-per-day, confirm adding daily persistence stays within limits.
5. Feature flag the persistence layer so it can be disabled without a deploy if Supabase writes cause latency spikes.

**Detection:** Monitor `service.ts` response times before and after. If P95 latency increases >20%, the persistence layer is blocking the response path.

---

### Pitfall 4: Feedback Loop Without Content Versioning Linkage

**What goes wrong:** A feedback mechanism gets built that says "CTR improved 15% after publish" but cannot answer "which specific prompt version, skill configuration, or content variant caused the improvement." The feedback is observational but not actionable — you know THAT something improved but not WHAT to repeat.

**Why it happens:** The system has multiple content versioning mechanisms that are not fully connected:
- `generated_content.version` and `generated_content.generation_prompt_hash`
- `regeneration_history.prompt_hash` and `regeneration_history.feature_flags_active`
- `publish_events.prompt_hash` and `publish_events.final_payload_hash`
- `performance_snapshots.content_version` (often NULL in practice)
- `prompt_version_aliases.alias` (maps hash to human-readable name)

The chain is: generation -> approval -> publish -> snapshot. But `content_version` in `performance_snapshots` is often NULL because `capture-snapshot` does not always have the content version available at capture time.

**Consequences:**
- Feedback loop becomes "content changed and performance changed" — correlation without causation
- Cannot compare prompt strategies (v2 creative brief vs v1 compliance doc) because prompt version is not reliably linked to outcomes
- v1.4 closed-loop optimization is impossible without this linkage — it is a hard prerequisite

**Prevention:**
1. Audit current NULL rates: `SELECT COUNT(*) FROM publish_events WHERE prompt_hash IS NULL AND published_at > '2026-02-01'` and `SELECT COUNT(*) FROM performance_snapshots WHERE content_version IS NULL`
2. Make `publish_events.prompt_hash` NOT NULL for new publishes going forward (it was added in migration 034 but is nullable)
3. Ensure `capture-snapshot` endpoint populates `content_version` from the most recent `publish_events` record for that SKU+platform
4. Build the feedback query as: `regeneration_history` JOIN `publish_events` ON `prompt_hash` JOIN `performance_snapshots` ON `publish_event_id` — verify this chain has no NULL gaps for recently published SKUs before building any feedback UI
5. Add a data quality check: after each publish batch, verify that every published SKU has a non-NULL `prompt_hash` in `publish_events`

**Detection:** Run the NULL audit queries above. If >10% of recent records have NULL in the join chain, the feedback loop will produce incomplete results.

---

## Moderate Pitfalls

### Pitfall 5: Multi-SKU Product Performance Attribution Error

**What goes wrong:** Performance feedback incorrectly attributes CTR changes to a single `master_sku` when multiple master_skus share the same `product_id`. Google Ads aggregates at product_id level, so DMF-2/2X, DMF-2/3X, DMF-2/4X, and DMF-2/5X (all sharing product_id `4539975336068`) show blended performance even if only one SKU's content changed.

**Why it happens:** `performance_baselines` and `performance_snapshots` key on `master_sku`, but Google Ads data comes at `product_id` granularity. The data collection pipeline handles this (see `metadata` JSONB field in `performance_baselines` noting multi-SKU families), but a feedback loop that treats each master_sku's performance as independent will produce wrong conclusions about which content change drove the improvement.

**Prevention:**
- Any feedback score must account for multi-SKU families: if one SKU in a family was published and others were not, the performance delta for ALL sibling SKUs is contaminated
- Use `variant_index` to identify product_id families before computing feedback
- Flag multi-SKU family feedback as LOWER confidence than single-SKU feedback
- Consider family-level feedback aggregation (one score per product_id, not per master_sku)

**Detection:** `SELECT product_id, COUNT(DISTINCT master_sku) FROM variant_index GROUP BY product_id HAVING COUNT(DISTINCT master_sku) > 1` — cross-reference with any content-performance feedback scores.

---

### Pitfall 6: Empty Optimization Tables Create False "Working" State

**What goes wrong:** Existing tables from migrations 032/033 (`sku_bottleneck_classifications`, optimization control tables) have schemas but zero rows because the classification logic uses hardcoded thresholds no SKU meets. Adding new data persistence on top of these tables (or building new features that JOIN to them) silently produces empty results. Worse: dashboard pages render with proper UI but zero data, creating a "looks functional but empty" experience that confuses users.

**Why it happens:** The optimization pipeline was built speculatively with thresholds like ROAS > 3.6 and CVR > 5% that were never calibrated against Allied Brass's actual performance data. The tables exist but are empty, and queries that LEFT JOIN to them return NULLs that propagate silently through aggregations.

**Prevention:**
1. Before building anything on top of existing optimization tables, run `SELECT table_name, n_live_tup FROM pg_stat_user_tables ORDER BY n_live_tup` — this gives a complete row count census
2. Any table with zero rows should be classified: populate with real data, remove, or explicitly mark as "v1.3c prerequisite"
3. Never LEFT JOIN to a table you have not verified has data — use INNER JOIN so missing data produces visible empty results rather than silent NULLs
4. For empty dashboard pages: add explicit "No data yet - this feature requires [prerequisite]" messaging rather than empty tables

**Detection:** A dashboard page that renders a table/chart but shows empty space is the symptom. Run the schema-wide row count audit at the start of the milestone.

---

### Pitfall 7: Per-Platform Content Generation Complicates Feedback Schema

**What goes wrong:** The v1.3a per-platform v2 generation architecture means each SKU has separate content for Google, Bing, and Shopify (6 records in `generated_content`: title + description for each platform). A feedback loop that measures "content performance" must handle that Google performance data only applies to Google content, Bing data only to Bing content, and Shopify has different metrics entirely (page views, add-to-cart rather than impressions/clicks).

**Why it happens:** The v2 per-platform architecture shipped in v1.3a. Anyone building the feedback loop who last looked at the system pre-v1.3a will assume one content set per SKU. The `generated_content` table has a `(master_sku, platform, content_type)` unique constraint, making it obvious at the schema level — but the feedback schema design may not account for platform-specific metrics.

**Prevention:**
- Feedback table/view must be keyed on `(master_sku, platform)`, not just `master_sku`
- Google/Bing feedback uses CTR/CVR from Google Ads / Bing Ads
- Shopify feedback needs different metrics (page conversion rate, bounce rate) which are NOT currently captured in any table
- For v1.3b: scope feedback to Google only (the platform with the most data and the most complete measurement infrastructure). Bing and Shopify feedback are v1.4 scope.

**Detection:** If the feedback schema has `master_sku` as a unique key without `platform`, it is wrong.

---

### Pitfall 8: Migration Numbering Conflicts and Ordering Issues

**What goes wrong:** New migrations collide with existing migration numbers. The repo already has duplicate numbers (026, 032, 033 each have two files) plus the deferred 034b/035b files. Adding new migrations requires careful numbering to avoid Supabase migration runner conflicts.

**Why it happens:** Supabase migration system tracks applied migrations by filename/timestamp. Duplicate numbers with different suffixes (034 vs 034b) can confuse the runner. The deferred files are marked "DEFERRED" in the filename but still exist in the `supabase/migrations/` directory, and Supabase may attempt to run them.

**Prevention:**
1. Before creating any migration, run `ls supabase/migrations/ | sort` and pick the next available number
2. If pruning deferred migrations, MOVE files out of the migrations directory entirely (to `supabase/migrations_archive/`) rather than relying on naming conventions
3. Use sequential numbering from the current highest (037+) — never insert between existing numbers
4. Apply migrations one at a time in a development environment, verify each succeeds before the next
5. Note in the 034b/035b headers: "STATUS: Tables created out-of-band" — these tables may already exist in production even though the migration was "deferred." Verify with `SELECT tablename FROM pg_tables WHERE schemaname = 'public'` before deciding to apply or remove.

**Detection:** `supabase migration list` shows conflicts or "already applied" errors.

---

### Pitfall 9: Historical Snapshot Storage Grows Unbounded

**What goes wrong:** Daily persistence of service.ts Google Ads data for 2,784 SKUs with 6 query types generates 15,000-50,000 rows per day. Within a year: 5-18 million rows. Supabase query performance degrades, storage costs increase, and the simplest dashboard query (latest snapshot) requires scanning through months of historical data.

**Why it happens:** The "persist everything" instinct is strong when moving from ephemeral 2-minute cache to historical storage. Without a retention policy, the table grows forever. The initial implementation focuses on writing data, not on pruning it.

**Prevention:**
1. Define retention policy BEFORE creating the table: daily granularity for 90 days, weekly aggregates for 1 year, monthly aggregates beyond that
2. Build the rollup/prune job in the SAME PR as the table creation — not as "future work"
3. Partition the table by month (Supabase supports PostgreSQL native partitioning)
4. Calculate expected storage: (rows_per_day * avg_row_bytes * 365) and compare to Supabase plan limits
5. Add an index on `snapshot_date DESC` and use `WHERE snapshot_date > NOW() - INTERVAL '90 days'` in all default queries

**Detection:** `SELECT pg_total_relation_size('table_name')` quarterly. Alert if growth rate exceeds 1GB/quarter.

---

## Minor Pitfalls

### Pitfall 10: Offer ID Case Sensitivity Breaks Feedback Joins

**What goes wrong:** Performance data uses lowercase offer IDs (`shopify_us_...`) while GMC uses uppercase (`shopify_US_...`). Feedback queries that JOIN across tables without normalizing case silently return zero rows, making it look like published content has no performance data.

**Prevention:** All JOINs involving `gmc_offer_id` must use `LOWER()` on both sides, or normalize to lowercase in the persistence layer. This is a known issue (documented in CLAUDE.md) but easy to forget in new query code. Add it to code review checklist.

---

### Pitfall 11: Score Model Dead in v2 Path Creates Misleading Quality Data

**What goes wrong:** The 10-criterion quality score model from v1.3a is only consumed by the v1 code path. The v2 `generate_per_platform()` returns raw dicts with no quality gating. If the feedback loop correlates `quality_score` from `generated_content` with performance, it may use v1-era scores that do not reflect the v2-generated content — or find NULLs for all v2 content.

**Prevention:**
- Verify that `quality_score` is populated for v2-generated content: `SELECT COUNT(*) FROM generated_content WHERE quality_score IS NOT NULL AND generation_timestamp > '2026-02-20'`
- If not populated, either wire the score model into v2 (v1.3b scope?) or explicitly exclude `quality_score` from feedback correlations
- Document which columns are reliably populated in the v2 era vs legacy v1 data

---

### Pitfall 12: Background Tasks vs Migration Application Timing

**What goes wrong:** Applying Supabase migrations while Cloud Run is processing batch jobs causes table locks or schema mismatches mid-generation. Cloud Run uses `run_async_in_thread()` for long-running tasks that survive HTTP responses — these threads hold open database connections that can conflict with DDL changes.

**Prevention:**
- Apply migrations during off-hours or after confirming no active batch jobs: `SELECT * FROM batch_generation_jobs WHERE status = 'running'`
- Column additions (ALTER TABLE ADD COLUMN) are generally non-blocking in PostgreSQL
- Column modifications, constraint additions, and index creation on large tables CAN lock — use `CREATE INDEX CONCURRENTLY` where possible

---

### Pitfall 13: 034b GA4 Tables Already Exist Out-of-Band

**What goes wrong:** The deferred migration files contain `CREATE TABLE IF NOT EXISTS` statements, and the file headers note "Tables created out-of-band; this file is reference only." This means the tables MAY already exist in production Supabase despite the migration being "deferred." Attempting to evaluate "should we apply this migration?" misses that the tables are already there, potentially with stale schemas if the migration file was updated after out-of-band creation.

**Prevention:**
- Before ANY migration evaluation, query production: `SELECT tablename FROM pg_tables WHERE schemaname = 'public' AND tablename LIKE 'ga4_%' OR tablename LIKE 'intent_%' OR tablename LIKE 'term_%' OR tablename LIKE 'policy_%' OR tablename LIKE 'experiment_%'`
- Compare actual table schemas against migration file definitions to check for drift
- The evaluation is not "apply or not" — it may be "the tables exist, do we keep/modify/drop them"

---

## Phase-Specific Warnings

| Phase Topic | Likely Pitfall | Mitigation |
|-------------|---------------|------------|
| Architecture audit | Pitfall 6 (empty tables) | Run `pg_stat_user_tables` census first; document every table with row count |
| Architecture audit | Pitfall 11 (dead score model) | Verify which columns are populated for v2-era content |
| Architecture audit | Pitfall 13 (tables exist out-of-band) | Query production schema before evaluating migration files |
| Migration evaluation | Pitfall 2 (applying without pruning) | Categorize KEEP/DEFER/REMOVE before touching any migration |
| Migration evaluation | Pitfall 8 (numbering conflicts) | Move deferred files out of migrations directory; verify numbering |
| Content-performance linkage | Pitfall 1 (duplicating infrastructure) | Write the JOIN first, only create new table for genuinely new data |
| Content-performance linkage | Pitfall 4 (broken version chain) | Audit NULL rates in prompt_hash and publish_event_id for recent publishes |
| Content-performance linkage | Pitfall 5 (multi-SKU attribution) | Account for product_id families in feedback schema |
| Content-performance linkage | Pitfall 7 (per-platform) | Key feedback on (master_sku, platform), scope to Google-only for v1.3b |
| Data persistence | Pitfall 3 (breaking live queries) | Write-behind pattern, feature-flagged, separate read endpoint |
| Data persistence | Pitfall 9 (unbounded growth) | Retention policy in the same PR as table creation |
| All phases | Pitfall 10 (offer ID case) | LOWER() on all gmc_offer_id joins; add to code review checklist |
| All phases | Pitfall 12 (migrations during jobs) | Confirm no active batch jobs before applying migrations |

---

## Risk Summary

| Risk Level | Count | Key Theme |
|------------|-------|-----------|
| Critical | 4 | Schema duplication, untested migrations, breaking live APIs, missing version linkage |
| Moderate | 5 | Multi-SKU attribution, empty tables, per-platform complexity, migration numbering, storage growth |
| Minor | 4 | Case sensitivity, dead score model, migration timing, out-of-band tables |

**The single highest-risk pitfall is Pitfall 1 (duplicating performance infrastructure).** The system already has the data needed for feedback loops scattered across 5 tables. The gap is JOIN quality (NULL foreign keys) and a convenient aggregation layer — not new tables. Building a new "feedback" table that re-stores performance metrics will create a maintenance nightmare that compounds with every future milestone.

**The second highest risk is Pitfall 4 (broken version linkage).** Without reliable `prompt_hash` -> `publish_event_id` -> performance data chain, the entire v1.4 closed-loop optimization milestone becomes impossible. This must be fixed as infrastructure before any feedback feature is built.

---

## Sources

- `/Users/bobby/Documents/GitHub/Allied-FeedOps/docs/database/SCHEMA.md` — complete schema reference (36+ tables, column definitions, JOIN paths)
- `/Users/bobby/Documents/GitHub/Allied-FeedOps/docs/plans/2026-02-21-strategic-milestone-assessment.md` — strategic assessment identifying all gaps
- `/Users/bobby/Documents/GitHub/Allied-FeedOps/.planning/PROJECT.md` — project context, known issues, tech debt inventory
- `/Users/bobby/Documents/GitHub/Allied-FeedOps/supabase/migrations/035b_DEFERRED_unified_intent_execution_system.sql` — 14 deferred intent tables with "created out-of-band" note
- `/Users/bobby/Documents/GitHub/Allied-FeedOps/supabase/migrations/034b_DEFERRED_ga4_attribution_forensics.sql` — 4 deferred GA4 tables with "created out-of-band" note
- `/Users/bobby/Documents/GitHub/Allied-FeedOps/dashboard/src/lib/shopping-funnel/service.ts` — 1,600-line live Google Ads query layer with 2-min cache
- `/Users/bobby/Documents/GitHub/Allied-FeedOps/dashboard/src/lib/optimization/control-center.ts` — hardcoded ROAS thresholds (3.6/3.1/2.6)
- `/Users/bobby/Documents/GitHub/Allied-FeedOps/CLAUDE.md` — system conventions, known issues, architecture patterns

---
*Pitfalls research for: Allied FeedOps v1.3b — Architecture Validation & Data Persistence*
*Researched: 2026-02-25*
