# Pitfalls Research

**Domain:** Large-scale batch data collection and monitoring for Google Ads feed optimization
**Researched:** 2026-02-13 (Updated from 2026-02-11)
**Confidence:** HIGH

## Critical Pitfalls

### Pitfall 1: Silent Completion with Incomplete Data

**What goes wrong:**
Batch job completes successfully (status = 'completed'), but only collected data for 30% of SKUs. Dashboard shows "success" but data is incomplete. Users don't discover missing data until they try to use it weeks later.

**Why it happens:**
- API errors (rate limits, timeouts) are caught and logged but don't fail the entire batch
- Progress counters increment even when individual operations fail
- Status updates check "processed count == total count" not "success count == total count"
- No post-completion validation of data coverage

**How to avoid:**
1. Track three separate counters: `total_skus`, `success_count`, `failure_count`
2. Final status logic: `status = 'partial' if failure_count > 0 else 'completed'`
3. Add post-job validation: Query collected data count, compare to expected count
4. Set `error_message` even when status is 'completed' if any SKUs failed
5. Dashboard alerts: Warn user if `success_count < total_skus * 0.95` (95% threshold)

**Warning signs:**
- Job shows "completed" but logs contain rate limit errors
- Database row count doesn't match `total_skus` count
- Timestamps show batch finished too quickly (4 minutes for 2,784 SKUs = impossible)
- Success rate dropped from historical 98% to 60% but status still "completed"

**Phase to address:**
Phase 1 (Foundation) - Validation framework must be in place before first batch runs

**Confidence:** HIGH — Learned from documented baseline capture issues and [batch processing metrics best practices](https://oneuptime.com/blog/post/2026-01-30-batch-processing-metrics/view).

---

### Pitfall 2: Database Connection Exhaustion from Concurrent Batch Jobs

**What goes wrong:**
Start 5 batch jobs simultaneously (different date ranges). First job succeeds, others fail with "connection pool exhausted" errors. Supabase shows 100/100 connections used, jobs hang waiting for connections that never free up.

**Why it happens:**
- Each background thread opens its own Supabase client connection
- Connection pooling doesn't work across threads in Python
- Supabase free tier: max 50 direct connections, pro tier: max 200
- Batch jobs hold connections for entire duration (30+ minutes)
- No connection cleanup on job failure or timeout
- Each API call within batch opens new connection instead of reusing

**How to avoid:**
1. Implement global connection pool with max size = Supabase tier limit - 20 (buffer for dashboard)
2. Use connection context managers that guarantee cleanup: `with get_pooled_connection() as conn:`
3. Limit concurrent batch jobs: Database flag `SELECT count(*) FROM batch_jobs WHERE status IN ('processing', 'queued')` < 3
4. Fail-fast: Return 429 "Too many concurrent jobs" instead of queueing indefinitely
5. Monitor `pg_stat_activity` in health checks, kill idle connections > 5 minutes old
6. Use Supabase connection pooling mode ('transaction' for batch jobs, not 'session')

**Warning signs:**
- Cloud Run logs show "connection timeout" after 2-3 concurrent batches start
- Supabase dashboard shows connections spike to limit and stay there
- Jobs stuck in "processing" status with no progress for > 10 minutes
- Error rate increases when multiple users trigger batch operations

**Phase to address:**
Phase 1 (Foundation) - Connection management is architectural, can't retrofit later

**Confidence:** HIGH — Confirmed in [Supabase connection management docs](https://supabase.com/docs/guides/database/connection-management) and [serverless database connection challenges](https://vercel.com/blog/the-real-serverless-compute-to-database-connection-problem-solved).

---

### Pitfall 3: Google Ads API Rate Limits with No Backoff

**What goes wrong:**
Batch processes 500 SKUs successfully, hits rate limit, then fails the remaining 2,284 SKUs. All 2,284 fail with RESOURCE_TEMPORARILY_EXHAUSTED. No retry logic, entire batch marked failed, data for first 500 SKUs is lost because transaction rolled back.

**Why it happens:**
- Google Ads API rate limits are not documented precisely - varies with server load
- Token bucket algorithm means hitting one limit puts you in "cool down" for unknown duration
- No exponential backoff implemented - code retries immediately and exhausts retry budget
- Batch size (10 SKUs) optimal for latency, but creates 278 API calls (2,784 / 10)
- Campaign-join pattern = 2 API calls per SKU = 556 total calls
- Keyword Planner = additional API call per unique keyword (100s of calls)
- Rate limit applies per developer token + customer ID, not per job

**How to avoid:**
1. Implement exponential backoff: 5s, 15s, 45s, 2min, 5min delays
2. Global rate limiter: Track API call timestamps, enforce max 10 QPS across all jobs
3. Break batch into smaller chunks with sleep between: Process 100 SKUs, sleep 30s, repeat
4. Persist progress after each chunk: Don't wait until end to commit data
5. Implement jitter in retry delays: `random.uniform(base_delay * 0.8, base_delay * 1.2)`
6. Monitor for rate limit pattern: If 3 consecutive chunks fail, pause job for 10 minutes
7. Use BatchJobService for Google Ads mutations (auto-retries), not for reporting queries

**Warning signs:**
- Multiple RESOURCE_TEMPORARILY_EXHAUSTED errors in logs clustered within seconds
- API call timestamps show 50 calls in 3 seconds (way above 10 QPS)
- Job fails at same point every time (500 SKUs = hit limit consistently)
- Different jobs running concurrently both fail at ~250 SKUs each (shared rate limit)

**Phase to address:**
Phase 1 (Foundation) - Rate limiting must be implemented before scaling up

**Confidence:** HIGH — Documented in [Google Ads API rate limits](https://developers.google.com/google-ads/api/docs/productionize/rate-limits) and [batch processing best practices](https://developers.google.com/google-ads/api/docs/batch-processing/best-practices).

---

### Pitfall 4: Stale Data Causing Incorrect Historical Baselines

**What goes wrong:**
Collect 180-day baseline for SKU that was just optimized. Baseline includes 179 days of old content performance + 1 day of new content. Post-optimization comparison shows "no improvement" because baseline is contaminated. Can't prove optimization worked.

**Why it happens:**
- No validation that SKU is in "pre-optimization" state before capturing baseline
- `publish_events` table has publish dates, but baseline capture doesn't check them
- 180-day window crosses multiple content iterations for frequently updated SKUs
- Baseline capture runs on schedule without context of recent changes
- No "time since last publish" filter in query logic

**How to avoid:**
1. Check `publish_events` before baseline capture: `SELECT MAX(published_at) FROM publish_events WHERE master_sku = ? AND platform = ?`
2. If published within last 30 days: Skip baseline or shorten window to pre-publish period only
3. Add `content_version` to baselines table: Link to specific content iteration
4. Validation rule: Baseline date range must not overlap with any publish date ± 7 days
5. Dashboard flag: Show "baseline may be contaminated" warning if published during baseline period
6. Alternative: Capture baseline at time of approval, before publish (proactive not reactive)

**Warning signs:**
- Baseline shows steady performance but publish_events shows 3 updates in that period
- Post-publish delta analysis shows identical CTR despite content changes
- Baseline capture timestamp is AFTER publish timestamp (reversed causality)
- Historical trend chart shows spike in metrics mid-baseline period

**Phase to address:**
Phase 2 (Validation Layer) - Temporal validation requires understanding of data lifecycle

**Confidence:** HIGH — Based on existing baseline capture troubleshooting guide and project-specific patterns.

---

### Pitfall 5: Multi-SKU Family Data Aggregation Errors

**What goes wrong:**
Query Google Ads for DMF-2/2X performance data. Get back aggregated data for DMF-2/2X, DMF-2/3X, DMF-2/4X, DMF-2/5X (all share product_id). Attribute all impressions/clicks to DMF-2/2X only. Other SKUs show zero data. Total metrics correct, distribution completely wrong.

**Why it happens:**
- Google Ads aggregates at product_id level for Shopping campaigns
- Returns data with product_item_id of whichever variant had most impressions
- variant_index maps offer_id → master_sku, but offer_id returned doesn't match expected
- Code assumes 1:1 mapping product_item_id → master_sku (FALSE for multi-SKU families)
- No detection of multi-SKU families before data collection
- No proportional allocation of aggregated metrics across family members

**How to avoid:**
1. Pre-flight check: Query variant_index to detect multi-SKU families
   ```sql
   SELECT product_id, COUNT(DISTINCT master_sku) as sku_count
   FROM variant_index
   GROUP BY product_id
   HAVING COUNT(DISTINCT master_sku) > 1
   ```
2. For multi-SKU families: Collect data once, allocate proportionally based on variant count
3. Flag multi-SKU data in database: `is_aggregated = true`, `family_members = ['DMF-2/2X', 'DMF-2/3X']`
4. Dashboard display: Show "aggregated family data" badge, list all members
5. Alternative: Use variant-level tracking via custom labels (custom_label_4 = master_sku)

**Warning signs:**
- One SKU in family has 10k impressions, others have 0 (sum is wrong)
- product_item_id in API response doesn't match any gmc_offer_id in variant_index
- Baseline data shows 100% of traffic to one variant, impossible product mix
- Investigation shows all family members use same product_id (SUBSTRING(gmc_offer_id FROM 'shopify_us_(\d+)_'))

**Phase to address:**
Phase 0 (Current) - Multi-SKU pattern already documented, must extend to batch collection

**Confidence:** HIGH — Documented in `/Users/bobby/Documents/GitHub/Allied-FeedOps/docs/architecture/multi-sku-pattern.md` and baseline capture troubleshooting.

---

### Pitfall 6: Cloud Run Container Restart Mid-Batch

**What goes wrong:**
Batch job processing 1,400 of 2,784 SKUs. Cloud Run scales down to zero during traffic lull, container terminates, background thread killed. Job record stuck in "processing" status forever. 1,400 SKUs of data collected but not committed. Restart from scratch loses all progress.

**Why it happens:**
- Cloud Run scales to zero after 15 minutes of no HTTP requests
- Background threads are NOT preserved during scale-down (despite using non-daemon threads)
- FastAPI BackgroundTasks killed when container terminates
- No checkpoint/resume mechanism - batch is all-or-nothing
- Job status never updated to "failed" because no exception thrown (just killed)
- Deployment during batch processing also kills in-flight jobs

**How to avoid:**
1. Implement checkpoint system: Commit progress every 100 SKUs, update job status
2. Job recovery: On restart, check for jobs stuck in "processing" > 1 hour, mark as "failed_recoverable"
3. Resume logic: Load last checkpoint, continue from `completed_skus` count
4. Health ping: Background thread pokes HTTP endpoint every 5 minutes to prevent scale-down
5. Alternative: Use Cloud Run Jobs (not Cloud Run services) for batch operations
6. Set min-instances=1 for batch processing service (costs ~$10/month, guarantees availability)
7. Add timeout: If job exceeds expected duration (2,784 SKUs * 5s/SKU = 4 hours), auto-fail

**Warning signs:**
- Jobs stuck in "processing" for days with no log activity
- `completed_at` is NULL but `started_at` is 2 days ago
- Cloud Run logs show container termination during batch run
- Deployment logs timestamp matches "stuck job" started_at timestamp

**Phase to address:**
Phase 1 (Foundation) - Checkpoint system must exist before running long batches

**Confidence:** HIGH — Confirmed in [Cloud Run always-on CPU allocation](https://cloud.google.com/blog/topics/developers-practitioners/use-cloud-run-always-cpu-allocation-background-work) and [background job limitations](https://www.grouparoo.com/blog/google-cloud-run-no-background-job).

---

### Pitfall 7: Keyword Planner Cache Stampede

**What goes wrong:**
1000 SKUs all need search volume data for "brass towel bar". Cache is empty. Trigger 1000 concurrent Keyword Planner API calls for same keyword. Hit rate limit, 990 fail. Retry logic triggers 990 more calls. Rate limit again. Exponential growth in failed calls.

**Why it happens:**
- No locking mechanism when cache miss detected
- Multiple threads/jobs check cache simultaneously, all see "not found"
- Each thread independently calls Keyword Planner API for same keyword
- 30-day TTL means cache expires all at once for keywords collected in same batch
- Retry logic doesn't check if another thread already fetched the data
- No deduplication of keyword requests within a batch

**How to avoid:**
1. Implement distributed lock: `SELECT pg_try_advisory_lock(hashtext('keyword'))` before API call
2. After lock acquired, recheck cache - another thread may have populated it
3. Batch keyword enrichment: Deduplicate keywords across all SKUs before API calls
4. Keyword Planner supports bulk requests (up to 1000 keywords) - use it
5. Cache warming: Pre-fetch top 1000 keywords before batch starts
6. Stagger TTL: Add random 1-7 days to 30-day TTL so expirations spread out
7. Rate limit per keyword: Max 1 request per keyword per 10 seconds globally

**Warning signs:**
- Keyword Planner logs show 100 calls for "brass towel bar" within 1 second
- Cache hit rate < 20% despite 30-day TTL (should be 80%+)
- Rate limit errors only for Keyword Planner, not for other APIs
- Database shows 1000 rows inserted for same keyword with identical timestamps

**Phase to address:**
Phase 2 (Optimization) - Cache strategy can be improved after foundation works

**Confidence:** MEDIUM — Based on common caching patterns and Keyword Planner API documentation.

---

### Pitfall 8: Monitoring Blind Spots (Jobs Degrade, Nobody Notices)

**What goes wrong:**
Batch jobs run nightly for 3 weeks. Success rate gradually drops from 98% to 65%. Nobody notices. On week 4, user complains "dashboard shows stale data". Investigation reveals 900 SKUs haven't updated in 2 weeks. No alerts fired. No monitoring in place.

**Why it happens:**
- Job status is binary (success/failed), doesn't capture degradation
- No metrics tracking: success rate, average duration, data coverage
- Logs exist but nobody reads them unless users complain
- No automated anomaly detection (success rate drops 20% = should alert)
- Dashboard shows last successful update timestamp, not data freshness for ALL SKUs
- Stakeholders don't know what "normal" looks like (no baseline metrics)

**How to avoid:**
1. Track metrics over time: `batch_job_metrics` table (timestamp, success_rate, avg_duration, failure_reasons)
2. Anomaly detection: Alert if success_rate < 7-day average - 15%
3. Data freshness SLA: Every SKU should have data < 48 hours old, alert if > 100 SKUs stale
4. Dashboard health widget: "2,650/2,784 SKUs current (95%), 134 stale"
5. Weekly report: Email summary of batch job health to stakeholders
6. Failure reason tracking: Group errors by type, alert if new error type appears
7. Performance regression detection: Alert if p95 duration increases > 50%

**Warning signs:**
- User reports stale data before you discover it (monitoring failed its job)
- Logs show gradual increase in timeout errors over 2 weeks
- Success rate chart shows downward trend but no alerts
- No metrics dashboard exists (can't answer "is this normal?")

**Phase to address:**
Phase 3 (Monitoring) - Purpose-built for monitoring, but basic metrics needed in Phase 1

**Confidence:** HIGH — Based on [data reliability best practices](https://www.siffletdata.com/blog/data-reliability) and [self-healing data pipelines](https://analyticsweek.com/self-healing-data-pipelines-2026/).

---

### Pitfall 9: Validation Happens Too Late (Garbage In, Dashboard Out)

**What goes wrong:**
Batch collects 180 days of data for 2,784 SKUs. Takes 6 hours. Writes to database. Dashboard loads it. Users see negative CTR (-0.05%), clicks > impressions, conversion_value = $999,999,999. Data is corrupted but validation happens at display time, not collection time. Can't fix without re-running 6-hour batch.

**Why it happens:**
- Validation logic in dashboard frontend (TypeScript), not in data collection (Python)
- "Fail fast" principle not applied - wait until all data collected to validate
- API responses trusted blindly - assume Google Ads returns valid data
- No schema validation on database writes - accepts any numeric value
- Batch commits all data at end, not incrementally - can't rollback individual errors
- No data quality checks: range validation, referential integrity, statistical sanity

**How to avoid:**
1. Validate at collection time: Check CTR = clicks/impressions ± 0.1% before writing
2. Range validation: impressions >= 0, CTR between 0 and 1, cost_micros >= 0
3. Statistical outliers: Flag if metric > 3 standard deviations from SKU's historical average
4. Reject invalid rows: Don't write to database, log validation failure, increment error count
5. Incremental commits: Validate + commit every 100 SKUs, rollback only failed chunk
6. Database constraints: CHECK (ctr >= 0 AND ctr <= 1), CHECK (clicks <= impressions)
7. Pre-flight validation: Check 10 SKUs first, if >50% fail validation, abort entire batch

**Warning signs:**
- Dashboard shows impossible metrics (negative rates, values > 100%)
- Data warehouse team reports "data quality issues from FeedOps table"
- Users screenshot bugs instead of trusting the data
- Validation logic duplicated in 3 places (API, database, dashboard)

**Phase to address:**
Phase 1 (Foundation) - Validation is foundational, can't bolt on later

**Confidence:** HIGH — Based on [data quality in batch pipelines](https://community.databricks.com/t5/data-engineering/best-practices-for-ensuring-data-quality-in-batch-pipelines/td-p/105876) and project-specific patterns.

---

### Pitfall 10: Date Range Boundary Errors (Off-by-One at Scale)

**What goes wrong:**
Request 180-day baseline. Query uses `>= start_date AND <= end_date`. Gets 181 days. Request 30-day post-publish snapshot, gets 29 days (< instead of <=). Delta comparison uses different denominators. Results show "10% improvement" that's actually 0% (just different sample sizes).

**Why it happens:**
- Timezone mismatches: Google Ads uses account timezone, code uses UTC
- Inclusive vs exclusive bounds: `BETWEEN` is inclusive on both ends (181 days)
- Leap year edge case: "Last 180 days" in leap year vs non-leap year
- DST transitions: "Last 24 hours" = 23 or 25 hours depending on DST
- Python datetime vs SQL date types: datetime includes time, date is midnight only
- Different date math in different parts of codebase (timedelta vs dateutil)

**How to avoid:**
1. Standardize date logic: Always use account timezone, convert at API boundary
2. Use explicit date ranges: `>= start_date AND < end_date` (exclusive upper bound)
3. Document expected behavior: "Last N days" = N full days, not including today
4. Validation: Assert `date_range.days == expected_days` before querying
5. Test edge cases: DST transition dates, leap day, month boundaries, year boundaries
6. Store timezone with timestamps: `timestamp with time zone` in Postgres
7. Helper function: `get_date_range(days=180, end_date=None)` with clear semantics

**Warning signs:**
- Baseline shows 181 rows when query was for 180 days
- Metrics differ slightly when re-running same query (timezone drift)
- Data for "today" sometimes included, sometimes not (midnight boundary issue)
- Delta comparison uses different row counts for before/after periods

**Phase to address:**
Phase 1 (Foundation) - Date handling bugs compound over time, fix early

**Confidence:** HIGH — Common date handling pitfall, validated in existing codebase patterns.

---

### Pitfall 11: search_term_view Cannot Filter by product_item_id

**What goes wrong:**
Developers assume they can query `search_term_view` with `WHERE segments.product_item_id = 'shopify_US_...'` to get product-specific search terms. This query returns zero rows for Shopping campaigns because Google intentionally removed this capability.

**Why it happens:**
The legacy AdWords API supported product partition data in search query reports, leading developers to expect similar functionality in the Google Ads API. The newer API intentionally decouples search terms from products to avoid misleading results.

**How to avoid:**
Use the campaign-join pattern already implemented in the codebase:
1. Query `shopping_performance_view` to get products by campaign
2. Query `search_term_view` to get search terms by campaign
3. Join via campaign_id to associate (approximate association, not exact)

Do NOT attempt to add `segments.product_item_id` as a WHERE filter or SELECT field in `search_term_view` queries.

**Warning signs:**
- GAQL query returns zero rows for Shopping campaigns despite active traffic
- Error message mentioning field compatibility issues
- Queries work for Search campaigns but not Shopping campaigns

**Phase to address:**
Phase 0 (Discovery) — Validate this limitation before planning detailed backfill

**Confidence:** HIGH — Confirmed in [Google Groups discussion](https://groups.google.com/g/adwords-api/c/SxEmuVTfBoQ) and project codebase.

---

### Pitfall 12: GMC Offer ID Case Sensitivity

**What goes wrong:**
Database stores offer IDs as lowercase `shopify_us_{product_id}_{variant_id}`, but GMC requires uppercase `shopify_US_{product_id}_{variant_id}`. Query logic using lowercase IDs fails to match uppercase IDs returned from Google Ads API.

**Why it happens:**
Historical data has mixed case from various sources. Google technically treats IDs as case-sensitive, but Shopify's auto-sync creates uppercase format. Database normalization chose lowercase, creating a mismatch.

**How to avoid:**
1. Normalize API responses: Convert to uppercase before storing
2. Database joins: Use `LOWER()` on both sides or case-insensitive regex
3. Already implemented pattern: `re.sub(r'^shopify_us_', 'shopify_US_', gmc_offer_id, flags=re.IGNORECASE)`

**Warning signs:**
- variant_index lookups return NULL despite offer ID existing
- Performance queries return zero rows despite Google Ads showing data

**Phase to address:**
Phase 0 (Discovery) + Phase 1 (Validation) — Audit all query patterns before backfill

**Confidence:** HIGH — Documented in CLAUDE.md and [GMC documentation](https://support.google.com/merchants/answer/6324405?hl=en).

---

## Technical Debt Patterns

| Shortcut | Immediate Benefit | Long-term Cost | When Acceptable |
|----------|-------------------|----------------|-----------------|
| Skip connection pooling | Simpler code | Connection exhaustion at scale | Never (for batch jobs) |
| Commit all data at end | Atomic semantics | Lost work on failure | MVP only, fix in Phase 1 |
| No checkpointing | Faster implementation | Can't recover from failures | Only if batch < 15 minutes |
| Trust API data without validation | Shorter code | Corrupted data in production | Never (data quality critical) |
| Binary success/failed status | Simpler state machine | Silent degradation | MVP only, add in Phase 1 |
| Log errors without alerting | Quick to implement | Problems discovered too late | Never (monitoring essential) |
| Hard-coded retry delays | Predictable behavior | Rate limit exhaustion | Only if no rate limits |
| Cache without TTL | Infinite cache hits | Stale data forever | Never (data changes frequently) |
| Using LIMIT 1000 instead of 50K | Faster queries | Misses long-tail data | Testing only |
| Campaign-level search association | Works around API limit | Imprecise mapping | Acceptable (API limitation) |

## Integration Gotchas

| Integration | Common Mistake | Correct Approach |
|-------------|----------------|------------------|
| Google Ads API | Assume fixed rate limits | Implement adaptive backoff, limits vary with load |
| Google Ads API | Query without campaign.advertising_channel_type | Always include in SELECT for Performance Max data |
| Google Ads API | Assume 1:1 product_item_id → master_sku | Check for multi-SKU families, allocate metrics |
| Google Ads API | Use LAST_N_DAYS for historical | Use explicit BETWEEN dates |
| Keyword Planner | Call API per keyword | Batch up to 1000 keywords per request |
| Supabase | Open new connection per operation | Use connection pool with max limit |
| Supabase | Assume connection closed on error | Use context managers or try/finally |
| Cloud Run | Use BackgroundTasks for long jobs | Use non-daemon threads with event loops |
| Cloud Run | Assume container stays running | Implement checkpoints, containers restart |
| search_term_view | Filter by product_item_id | Use campaign-join pattern |

## Performance Traps

| Trap | Symptoms | Prevention | When It Breaks |
|------|----------|------------|----------------|
| N+1 queries | 4 hours for 2,784 SKUs | Batch queries: 100 SKUs per API call | > 100 SKUs |
| Synchronous API calls | Linear scaling | Use asyncio, concurrent processing | Any batch job |
| No connection pooling | New connection overhead | Use pool, reuse connections | > 10 requests/min |
| Commit every row | Database overwhelmed | Batch commits every 100 rows | > 1000 rows |
| No pagination | OOM error | Stream results, process chunks | > 10k results |
| Cache stampede | 1000 threads fetch same data | Distributed locking | High concurrency |
| Polling every second | Database CPU at 100% | Exponential poll backoff | Multiple jobs polling |
| Full table scan | Query takes 10 seconds | Index on (status, created_at) | > 10k job records |
| N+1 variant lookups | Thousands of DB queries | Cache variant_index results | > 1000 search terms |
| Large upsert batches | Timeout errors | Batch to 500 rows max | > 5000 rows |

## Security Mistakes

| Mistake | Risk | Prevention |
|---------|------|------------|
| Log API responses with PII | GDPR violation | Sanitize logs, never log full product data |
| Store customer ID in code | Multi-tenant data leakage | Parameterize, validate from environment |
| No auth on batch endpoints | Anyone triggers expensive ops | Require service account token |
| Database credentials in logs | Credential leakage | Use Secret Manager, never log connection strings |
| No validation on SKU input | SQL injection | Parameterized queries, validate format |
| Logging offer IDs plaintext | Exposes catalog structure | Hash or truncate in logs |
| API keys in database | DB breach = API access | Environment variables or secret manager |

## UX Pitfalls

| Pitfall | User Impact | Better Approach |
|---------|-------------|-----------------|
| "Success" when 40% failed | Trust incomplete data | Show "partial: 1670/2784 SKUs" with details |
| No progress indicator | Thinks it's hung, cancels | Show "1234/2784 (44%), ~2h remaining" |
| No error message | Can't fix issue | Show "Failed: Rate limit. Retry in 30min" |
| Data freshness not visible | Doesn't know if stale | Show "Last updated: 2 hours ago" |
| No cancel button | Stuck waiting 4 hours | Add "Cancel batch", graceful shutdown |
| No filtering | Can't find specific SKU | Search box, filters by category/tier |
| No last-batch indicator | Doesn't know if job ran | Show "Last: 2026-02-13 02:15 AM (2,650)" |
| No backfill progress | Unknown if running/stuck | Update with progress percentage |
| Fail silently on partial | Sees 3% coverage | Show "Backfill: 84/2,784 SKUs" |
| Not explaining 180-day limit | Requests impossible data | Display "Last 6 months available" |

## "Looks Done But Isn't" Checklist

- [ ] **Batch job success:** Often missing validation that all SKUs succeeded — verify success_count + failure_count == total_count
- [ ] **Data validation:** Often missing sanity checks — verify ranges, no nulls, CTR math correct
- [ ] **Connection cleanup:** Often missing in error paths — verify context managers or try/finally
- [ ] **Rate limit handling:** Often missing exponential backoff — verify delays increase (5s, 15s, 45s)
- [ ] **Progress persistence:** Often missing checkpoints — verify can resume from arbitrary point
- [ ] **Multi-SKU handling:** Often missing aggregation — verify family members all get data
- [ ] **Date range logic:** Often missing timezone — verify account timezone used
- [ ] **Monitoring:** Often missing alerting — verify automated alerts fire on degradation
- [ ] **Validation timing:** Often at display not collection — verify bad data rejected at API
- [ ] **Cache TTL:** Often missing or infinite — verify stale data expires
- [ ] **Search term sync:** Often missing variant_index — verify master_sku populated >90%
- [ ] **Performance backfill:** Often missing campaign filter — verify Shopping campaigns only
- [ ] **Keyword enrichment:** Often missing cache check — verify not re-fetching recent
- [ ] **Offer ID normalization:** Often missing case conversion — verify uppercase in sheets
- [ ] **Resumability:** Often missing offset tracking — verify can resume mid-batch

## Recovery Strategies

| Pitfall | Recovery Cost | Recovery Steps |
|---------|---------------|----------------|
| Silent incomplete data | MEDIUM | Query gaps → re-run failed SKUs → update status → add validation |
| Connection exhaustion | LOW | Kill idle connections → restart jobs → add pool → limit concurrent |
| Rate limit exceeded | LOW | Wait 30 min → re-run with backoff → reduce batch size |
| Stale baseline | HIGH | Drop contaminated → check publish_events → re-capture pre-publish |
| Multi-SKU aggregation | HIGH | Identify families → allocate proportionally → re-run with detection |
| Container restart | MEDIUM | Mark stuck as failed_recoverable → resume from checkpoint |
| Cache stampede | MEDIUM | Clear duplicates → add locking → pre-warm → use bulk API |
| Monitoring blind spots | HIGH | Audit 30-day logs → identify timeline → backfill → add metrics |
| Late validation | HIGH | Identify corrupt data → delete invalid → re-run with validation |
| Date boundary errors | MEDIUM | Audit date queries → standardize timezone → fix bounds → re-capture |
| Hit rate limits | LOW | Resume from checkpoint, increase delays |
| Wrong case IDs | MEDIUM | Run migration: UPDATE to uppercase format |
| Incomplete variant_index | MEDIUM | Re-sync catalog, re-run backfill |
| search_term query fails | HIGH | Redesign with campaign-join pattern |

## Pitfall-to-Phase Mapping

| Pitfall | Prevention Phase | Verification |
|---------|------------------|--------------|
| Silent incomplete data | Phase 1: Foundation | success_count logic, status updated correctly |
| Connection exhaustion | Phase 1: Foundation | Pool exists, concurrent limit enforced, no timeouts |
| Rate limit exceeded | Phase 1: Foundation | Exponential backoff, global rate limiter tracking |
| Stale baseline | Phase 2: Validation | Checks publish_events, skips if recent |
| Multi-SKU aggregation | Phase 0: Research | Family detection runs, metrics allocated |
| Container restart | Phase 1: Foundation | Checkpoints exist, jobs can resume |
| Cache stampede | Phase 2: Optimization | Locks before writes, bulk API calls |
| Monitoring blind spots | Phase 3: Monitoring | Dashboard exists, alerts fire (tested) |
| Late validation | Phase 1: Foundation | Validation at collection, DB constraints |
| Date boundary errors | Phase 1: Foundation | Helper functions, timezone standardized |
| search_term filtering | Phase 0: Discovery | Test with product_item_id, confirm zero rows |
| Offer ID case | Phase 1: Validation | Audit case handling, test conversion |

## Sources

**Google Ads API:**
- [API Limits and Quotas](https://developers.google.com/google-ads/api/docs/best-practices/quotas)
- [Rate limits](https://developers.google.com/google-ads/api/docs/productionize/rate-limits)
- [Batch Processing Overview](https://developers.google.com/google-ads/api/docs/batch-processing/overview)
- [Best Practices and Limitations](https://developers.google.com/google-ads/api/docs/batch-processing/best-practices)
- [search_term_view Reference](https://developers.google.com/google-ads/api/fields/v22/search_term_view)
- [Field Compatibility](https://developers.google.com/google-ads/api/docs/concepts/field-service)

**Cloud Run:**
- [Always-on CPU allocation for background work](https://cloud.google.com/blog/topics/developers-practitioners/use-cloud-run-always-cpu-allocation-background-work)
- [Don't Do Background Jobs on Google Cloud Run](https://www.grouparoo.com/blog/google-cloud-run-no-background-job)
- [Cloud Run Jobs for background tasks](https://medium.com/@shubhangi.thakur4532/google-cloud-run-jobs-for-background-tasks-1413ed41e433)

**Database:**
- [Connect to your database | Supabase](https://supabase.com/docs/guides/database/connecting-to-postgres)
- [Connection management | Supabase](https://supabase.com/docs/guides/database/connection-management)
- [Supavisor connection pooler](https://supabase.com/blog/supavisor-postgres-connection-pooler)
- [Serverless database connection problem solved](https://vercel.com/blog/the-real-serverless-compute-to-database-connection-problem-solved)

**Data Quality:**
- [How to Implement Batch Metrics](https://oneuptime.com/blog/post/2026-01-30-batch-processing-metrics/view)
- [Data Reliability Guide](https://www.siffletdata.com/blog/data-reliability)
- [Self-Healing Data Pipelines](https://analyticsweek.com/self-healing-data-pipelines-2026/)
- [Best practices for data quality in batch pipelines](https://community.databricks.com/t5/data-engineering/best-practices-for-ensuring-data-quality-in-batch-pipelines/td-p/105876)

**Project-Specific:**
- `/Users/bobby/Documents/GitHub/Allied-FeedOps/docs/troubleshooting/baseline-capture.md`
- `/Users/bobby/Documents/GitHub/Allied-FeedOps/docs/architecture/multi-sku-pattern.md`
- `/Users/bobby/Documents/GitHub/Allied-FeedOps/src/feedops/api/main.py`

---
*Pitfalls research for: Allied FeedOps - Large-scale batch data collection and monitoring*
*Researched: 2026-02-13 (Updated from 2026-02-11)*
