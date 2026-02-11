# Pitfalls Research

**Domain:** Google Ads API Data Backfill for Search Term Analysis
**Researched:** 2026-02-11
**Confidence:** HIGH

## Critical Pitfalls

### Pitfall 1: search_term_view Cannot Filter by product_item_id

**What goes wrong:**
Developers assume they can query `search_term_view` with `WHERE segments.product_item_id = 'shopify_US_...'` to get product-specific search terms. This query returns zero rows for Shopping campaigns because Google intentionally removed this capability, considering it an anti-pattern.

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
- Error message mentioning field compatibility issues between `search_term_view` and shopping-specific segments
- Queries work for Search campaigns but not Shopping campaigns

**Phase to address:**
Phase 0 (Discovery) — Validate this limitation and document the workaround before planning detailed backfill.

**Confidence:** HIGH — Confirmed in Google Ads developer forums ([Google Groups discussion](https://groups.google.com/g/adwords-api/c/SxEmuVTfBoQ)) and project codebase (`get_terms_for_master_sku()` deprecated with explicit warning).

---

### Pitfall 2: GMC Offer ID Case Sensitivity (shopify_us vs shopify_US)

**What goes wrong:**
Database stores offer IDs as lowercase `shopify_us_{product_id}_{variant_id}`, but GMC requires uppercase `shopify_US_{product_id}_{variant_id}`. Publishing code writes lowercase IDs to Google Sheets, which breaks GMC sync — rows append as duplicates instead of updating existing rows. Query logic using lowercase IDs fails to match uppercase IDs returned from Google Ads API.

**Why it happens:**
Historical data has mixed case from various sources. Google technically treats IDs as case-sensitive, but Shopify's auto-sync creates uppercase format. Database normalization chose lowercase, creating a mismatch.

**How to avoid:**
1. **Publishing**: Transform to uppercase when writing to Google Sheets: `.replace('shopify_us_', 'shopify_US_')`
2. **Queries**: Use lowercase for database lookups, but normalize API responses to uppercase before storing
3. **Joins**: Use `LOWER()` on both sides or case-insensitive regex matching

Already implemented in `save_search_terms_to_db()` at line 896:
```python
if gmc_offer_id:
    gmc_offer_id = re.sub(r'^shopify_us_', 'shopify_US_', gmc_offer_id, flags=re.IGNORECASE)
```

**Warning signs:**
- Google Sheets has duplicate rows for same product with different case
- `variant_index` lookups return NULL despite offer ID existing
- Performance queries return zero rows despite Google Ads showing data
- Publishing succeeds but GMC feed not updating

**Phase to address:**
Phase 0 (Discovery) + Phase 1 (Validation) — Audit all query patterns and enforce case normalization before backfill execution.

**Confidence:** HIGH — Documented in project CLAUDE.md, fixed in `google-sheets.ts` (line 754), and [Google Merchant Center documentation](https://support.google.com/merchants/answer/6324405?hl=en) confirms case sensitivity.

---

### Pitfall 3: GAQL Field Compatibility Errors (Resource Segmentation)

**What goes wrong:**
Queries fail with "field incompatibility" errors when trying to SELECT fields from incompatible resources or mixing segments that don't support the same metrics. Example: Trying to SELECT `campaign.advertising_channel_type` without including it in WHERE clause when filtering Shopping campaigns causes query rejection.

**Why it happens:**
GAQL enforces strict field compatibility rules. The `selectableWith` attribute on each field defines which other resources/segments can be included in the same query. Developers assume if two fields exist separately, they can be selected together — this is false.

**How to avoid:**
1. **Always SELECT fields you filter on**: If `WHERE campaign.advertising_channel_type = 'SHOPPING'`, you MUST `SELECT campaign.advertising_channel_type`
2. **Use Google Ads Query Validator** before implementing queries in code
3. **Check GoogleAdsFieldService** for field compatibility metadata
4. **Reference official docs** for each resource to see supported segment combinations

Example from existing code (line 478 in `google_ads_search_terms.py`):
```python
# CORRECT: Selecting the field we're filtering on
SELECT
    campaign.advertising_channel_type,  # Must be selected
    metrics.impressions
FROM shopping_performance_view
WHERE campaign.advertising_channel_type = 'SHOPPING'
```

**Warning signs:**
- Error message: "Field X is not compatible with resource Y"
- Query works in isolation but fails when combined with other fields
- Different metric totals when changing SELECT fields (indicates aggregation change)

**Phase to address:**
Phase 0 (Discovery) — Validate all query patterns with Query Validator before scale-up.

**Confidence:** HIGH — Documented in [Google Ads API field compatibility guide](https://developers.google.com/google-ads/api/docs/concepts/field-service) and [GAQL validation video](https://developers.google.com/google-ads/api/videos/catalog/gaql-8).

---

### Pitfall 4: Token Bucket Rate Limiting (RESOURCE_TEMPORARILY_EXHAUSTED)

**What goes wrong:**
Backfill scripts hit `RESOURCE_TEMPORARILY_EXHAUSTED` errors mid-execution despite staying under documented QPS limits. The API uses a Token Bucket algorithm with dynamic limits based on server load, so the actual limit varies. Naive retry logic with fixed delays causes cascading failures.

**Why it happens:**
Google Ads API doesn't publish exact QPS limits — they fluctuate based on overall system load. The token bucket refills over time, but aggressive retry strategies deplete tokens faster than they refill. Rate limiting is enforced per CID (customer ID) AND per developer token independently.

**How to avoid:**
1. **Implement exponential backoff**: Start with 5-second delay, double each retry (5s → 10s → 20s)
2. **Limit concurrent requests**: Max 10 concurrent per customer ID recommended
3. **Use batch operations**: Call `MutateFoo` once with 100 operations instead of 100 single-operation calls
4. **Implement client-side rate limiter**: Don't rely solely on API errors — preemptively throttle requests
5. **For backfill**: Process sequentially with 1-2 second delays between calls

Already partially implemented in existing code with delays, but needs exponential backoff for production backfill.

**Warning signs:**
- `QuotaError.RESOURCE_TEMPORARILY_EXHAUSTED` errors appearing
- Errors increase in frequency during backfill
- Same queries work fine when run individually but fail in batch
- Errors occur even with low concurrency

**Phase to address:**
Phase 1 (Validation) — Test rate limiting behavior with production data volumes. Phase 2 (Backfill Execution) — Implement exponential backoff before large-scale backfill.

**Confidence:** HIGH — Confirmed in [Google Ads API rate limiting documentation](https://developers.google.com/google-ads/api/docs/productionize/rate-limits) and [error handling guide](https://developers.google.com/google-ads/api/samples/handle-rate-exceeded-error).

---

### Pitfall 5: Data Retention Window Assumptions (180 Days vs 11 Years)

**What goes wrong:**
Developers assume search term data is available for 11 years (the new Google Ads retention policy) and build backfill plans accordingly. In reality, `search_term_view` is limited to **180 days** (6 months) while `shopping_performance_view` has ~2 years. Backfill scripts attempting to fetch older data get zero rows without clear error messages.

**Why it happens:**
Google's November 2024 announcement about 11-year retention applies to most Google Ads data, but search term data has always had shorter retention due to privacy considerations. Different views have different retention windows, and this isn't always explicitly documented in GAQL query errors.

**How to avoid:**
1. **Document retention windows per resource**:
   - `search_term_view`: 180 days max
   - `shopping_performance_view`: ~2 years
   - `campaign` and `ad_group` metadata: 11 years
   - Keyword Planner metrics: 12-month rolling average (no date range)

2. **Validate data availability** before backfill: Query oldest date with `WHERE segments.date BETWEEN 'YYYY-MM-DD' AND 'YYYY-MM-DD'` to confirm data exists

3. **Set realistic backfill expectations**: Accept that 6-month search term data is the maximum available

4. **Start collecting going forward**: Can't backfill older data, but can prevent future gaps by scheduling regular syncs

**Warning signs:**
- Zero rows returned for date ranges older than 6 months
- `shopping_performance_view` returns data but `search_term_view` doesn't for same date range
- Queries work for recent dates but fail silently for older dates

**Phase to address:**
Phase 0 (Discovery) — Test actual retention limits with date range queries. Document confirmed limits before planning backfill scope.

**Confidence:** HIGH — Confirmed in [Google Ads data retention policy](https://ads-developers.googleblog.com/2024/10/new-data-retention-policy-for-google-ads.html) and project backfill strategy document showing 180-day limit for search terms.

---

### Pitfall 6: Multi-SKU Products (Product ID Aggregation)

**What goes wrong:**
Developers assume one master_sku = one product_id. In reality, multiple master SKUs share the same product_id (e.g., DMF-2/2X, DMF-2/3X, DMF-2/4X all share `4539975336068`). Google Ads aggregates performance at product_id level, not master_sku level. Queries filtering by master_sku miss data that's aggregated at product_id level.

**Why it happens:**
Allied Brass treats different mounting bracket combinations as separate master SKUs for inventory purposes, but they're variants of the same Shopify product. Google Shopping sees all variants under one product_id.

**How to avoid:**
1. **Query by product_id, not master_sku** when fetching Google Ads data
2. **Post-process to split by master_sku** using `variant_index` mapping
3. **Aggregate carefully**: When showing "SKU performance," sum across all product_ids associated with that master_sku family
4. **Document multi-SKU families** in `multi-sku-detection.ts` and reference during analysis

Already implemented in codebase via `variant_index` lookups after fetching product_id-level data.

**Warning signs:**
- Master SKU shows zero data despite product_id having impressions
- Performance totals don't match between SKU-level and product-level reports
- Search terms appear for one master_sku variant but not others in same family
- `variant_index` has multiple master_skus with identical product_id

**Phase to address:**
Phase 0 (Discovery) — Document all multi-SKU product families before backfill. Phase 3 (Data Quality) — Validate master_sku attribution logic.

**Confidence:** HIGH — Documented in project `multi-sku-pattern.md` and confirmed in codebase pattern.

---

## Technical Debt Patterns

| Shortcut | Immediate Benefit | Long-term Cost | When Acceptable |
|----------|-------------------|----------------|-----------------|
| Using LIMIT 1000 instead of 50K | Faster queries, lower quota usage | Misses long-tail search terms, biases data toward high-traffic SKUs | Only for testing/prototyping, never for production backfill |
| Campaign-level search term association | Works around API limitation | Imprecise mapping (search terms associated with campaign, not exact product) | Acceptable — API limitation requires this approach |
| Case-insensitive offer ID matching | Handles mixed-case legacy data | Hides underlying data quality issues | Acceptable short-term, but should migrate to canonical uppercase format |
| Caching variant_index lookups in memory | Reduces database round-trips | Stale cache if variant_index updates mid-execution | Acceptable for batch jobs with short runtime (<1 hour) |
| Sequential date window processing | Simple resumability, avoids quota issues | Slower than parallel processing | Recommended for backfill — simplicity > speed for one-time operation |
| Storing item_ids as JSON string | Works around Supabase JSONB handling | Requires parsing in application layer | Acceptable — database constraint requires this pattern |

## Integration Gotchas

| Integration | Common Mistake | Correct Approach |
|-------------|----------------|------------------|
| Google Ads API | Assuming search_term_view supports product_item_id filtering | Use campaign-join pattern via shopping_performance_view |
| Keyword Planner | Calling with 1000 keywords at once | Batch to 100 keywords max per request, rate limit to ~10 requests/minute |
| Supabase upsert | Using `on_conflict` with wrong column combination | Match unique constraint exactly: `query_text,gmc_offer_id,period_start,period_end` |
| variant_index lookup | Querying every time in hot loop | Cache results in dictionary, clear cache between major phases |
| JSONB columns | Storing Python list directly | Convert to JSON string first: `json.dumps(list)` |
| Date ranges in GAQL | Using `DURING LAST_N_DAYS` for backfill | Use `BETWEEN 'YYYY-MM-DD' AND 'YYYY-MM-DD'` for precise control |

## Performance Traps

| Trap | Symptoms | Prevention | When It Breaks |
|------|----------|------------|----------------|
| **N+1 variant lookups** | Slow search term processing, thousands of DB queries | Cache variant_index results, batch lookups with IN clause | >1000 search terms per sync |
| **Large upsert batches** | Supabase timeout errors, slow response times | Batch upserts to 500 rows max, process in chunks | >5000 rows per upsert |
| **Keyword Planner without cache** | API quota exhausted, slow enrichment | Check `keyword_metrics` table first, only fetch missing keywords | >1000 unique keywords |
| **Unbounded search_stream** | Memory overflow, process crash | Always use LIMIT clause, paginate large result sets | >100K rows per query |
| **Synchronous API calls in loop** | Takes hours to process 1000 products | Use async/await or multiprocessing for independent queries | >100 sequential API calls |
| **No retry logic** | Intermittent failures abort entire backfill | Implement exponential backoff for transient errors | Any production backfill job |

## Security Mistakes

| Mistake | Risk | Prevention |
|---------|------|------------|
| **Logging offer IDs in plain text** | Exposes product catalog structure, competitive intelligence | Hash or truncate offer IDs in logs: `shopify_US_...{last 4 digits}` |
| **Exposing API credentials in error messages** | Credential leakage in error logs | Sanitize exceptions, never log developer_token or refresh_token |
| **No rate limiting on public endpoints** | DOS vector if sync endpoint exposed | Require authentication, implement request throttling |
| **Storing API keys in database** | Database breach = API access | Store in environment variables or secret manager (already done) |

## UX Pitfalls

| Pitfall | User Impact | Better Approach |
|---------|-------------|-----------------|
| **No backfill progress indicator** | User doesn't know if job is running or stuck | Update sync_jobs table with progress percentage, expose in dashboard |
| **Failing silently on partial data** | Users see 3% coverage, assume system broken | Show clear messaging: "Backfill in progress: 84/2,784 SKUs" |
| **Not explaining 180-day limit** | Users request historical data that doesn't exist | Display retention window in UI: "Search terms available for last 6 months" |
| **Showing zero data without context** | Users think product isn't running ads | Distinguish "No data available" vs "Product has zero impressions" |
| **No way to manually trigger backfill** | Users can't force refresh after data fixes | Add "Refresh Historical Data" button that starts backfill job |

## "Looks Done But Isn't" Checklist

- [ ] **Search term sync:** Often missing variant_index lookups — verify `master_sku` populated for >90% of rows
- [ ] **Performance backfill:** Often missing campaign_id filter — verify only Shopping campaigns included
- [ ] **Keyword enrichment:** Often missing cache check — verify not re-fetching recently updated keywords
- [ ] **Offer ID normalization:** Often missing case conversion — verify uppercase format in Google Sheets
- [ ] **Error handling:** Often missing exponential backoff — verify retry logic for RESOURCE_TEMPORARILY_EXHAUSTED
- [ ] **Resumability:** Often missing offset tracking — verify can resume mid-backfill after failure
- [ ] **Data quality:** Often missing NULL master_sku handling — verify variant_index coverage before backfill
- [ ] **Rate limiting:** Often missing client-side throttling — verify delays between API calls
- [ ] **Pagination:** Often missing next_page_token handling — verify can fetch >10K rows
- [ ] **Date window boundaries:** Often missing deduplication — verify upsert handles overlapping windows

## Recovery Strategies

| Pitfall | Recovery Cost | Recovery Steps |
|---------|---------------|----------------|
| **Hit rate limits mid-backfill** | LOW | Resume from last sync_job checkpoint, increase delays between calls |
| **Wrong case offer IDs in sheets** | MEDIUM | Run one-time migration: `UPDATE rows SET id = REPLACE(id, 'shopify_us_', 'shopify_US_')` |
| **Incomplete variant_index** | MEDIUM | Re-sync Shopify catalog, run backfill again to populate missing master_skus |
| **search_term_view query returns zero rows** | HIGH | Redesign query to use campaign-join pattern, cannot filter by product_item_id |
| **Assumed 11-year retention** | HIGH | Scope down backfill to 180 days, schedule regular syncs going forward |
| **N+1 query performance** | MEDIUM | Add caching layer, batch variant_index lookups, profile slow queries |

## Pitfall-to-Phase Mapping

| Pitfall | Prevention Phase | Verification |
|---------|------------------|--------------|
| search_term_view product filtering | Phase 0 (Discovery) | Test query with product_item_id filter, confirm zero rows |
| GMC offer ID case sensitivity | Phase 1 (Validation) | Audit all case handling code, test with lowercase → uppercase conversion |
| GAQL field compatibility | Phase 0 (Discovery) | Validate all queries in Google Ads Query Validator tool |
| Token bucket rate limiting | Phase 1 (Validation) | Test with 100-query burst, measure time to RESOURCE_EXHAUSTED |
| Data retention assumptions | Phase 0 (Discovery) | Query with 180-day-old dates, confirm data exists or doesn't |
| Multi-SKU product aggregation | Phase 0 (Discovery) | Document all multi-SKU families, test product_id-based queries |
| N+1 variant lookups | Phase 2 (Backfill) | Profile execution, add caching before scale-up |
| Missing retry logic | Phase 1 (Validation) | Simulate API failures, verify exponential backoff works |
| Unbounded LIMIT | Phase 0 (Discovery) | Test max LIMIT (10K → 50K → 100K), find API rejection point |
| Case-insensitive joins | Phase 3 (Data Quality) | Audit join patterns, ensure LOWER() or regex normalization |

## Sources

### Official Google Ads API Documentation
- [Handle API Errors](https://developers.google.com/google-ads/api/docs/get-started/handle-errors)
- [API Limits and Quotas](https://developers.google.com/google-ads/api/docs/best-practices/quotas)
- [Rate Limits and Token Bucket](https://developers.google.com/google-ads/api/docs/productionize/rate-limits)
- [GAQL Query Structure](https://developers.google.com/google-ads/api/docs/query/structure)
- [Field Compatibility](https://developers.google.com/google-ads/api/docs/concepts/field-service)
- [Google Ads Query Validator](https://developers.google.com/google-ads/api/docs/developer-toolkit/gaa-query-validator)
- [Segmentation](https://developers.google.com/google-ads/api/docs/reporting/segmentation)
- [Handle Rate Exceeded Error (Sample Code)](https://developers.google.com/google-ads/api/samples/handle-rate-exceeded-error)
- [search_term_view Reference](https://developers.google.com/google-ads/api/fields/v22/search_term_view)
- [shopping_performance_view Reference](https://developers.google.com/google-ads/api/fields/v22/shopping_performance_view)

### Google Ads Developer Blog & Forums
- [New Data Retention Policy (11 years)](https://ads-developers.googleblog.com/2024/10/new-data-retention-policy-for-google-ads.html)
- [Search Term View for Shopping Campaigns (Forum)](https://groups.google.com/g/adwords-api/c/SxEmuVTfBoQ) — Confirms product_item_id limitation
- [Resource Exhausted Errors (Forum)](https://groups.google.com/g/adwords-api/c/AChSpxBxlyQ)

### Google Merchant Center Documentation
- [ID [id] Attribute Documentation](https://support.google.com/merchants/answer/6324405?hl=en) — Confirms case sensitivity

### Project-Specific Documentation
- `/Users/bobby/Documents/GitHub/Allied-FeedOps/docs/audit/signal-audit-2026-02-11/google-ads-backfill-strategy.md`
- `/Users/bobby/Documents/GitHub/Allied-FeedOps/src/feedops/integrations/google_ads_search_terms.py` (lines 647-653: deprecated function with API limitation warning)
- `/Users/bobby/Documents/GitHub/Allied-FeedOps/CLAUDE.md` — Offer ID format documentation
- `/Users/bobby/Documents/GitHub/Allied-FeedOps/docs/architecture/multi-sku-pattern.md`

---
*Pitfalls research for: Google Ads API Data Backfill (Phase 0: Discovery)*
*Researched: 2026-02-11*
