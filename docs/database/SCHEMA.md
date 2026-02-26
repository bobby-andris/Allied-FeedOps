# Allied-FeedOps Database Schema

**Supabase Project ID**: `qezuszwufortkiutlhym`

**Last full rebuild**: 2026-02-25 (Phase 31-01 — rebuilt from migration SQL cross-referenced with production)

---

## Schema Overview

| Category | Count | Tables |
|----------|-------|--------|
| Core Content | 4 | generated_content, sku_approvals, variant_approvals, variant_finish_sentences |
| Publishing | 3 | publish_batches, batch_sku_assignments, publish_events |
| Product Data | 2 | variant_index, product_catalog |
| Performance Tracking | 3 | performance_baselines, performance_snapshots, performance_impact_scores |
| Search & Keywords | 9 | search_queries, search_queries_by_master_sku, keyword_metrics, search_query_snapshots, search_query_sync_jobs, keyword_coverage_master, keyword_coverage_variant, finish_search_patterns, funnel_snapshots_daily |
| Images | 3 | product_lifestyle_images, variant_lifestyle_images, lifestyle_image_selections |
| Content Generation | 5 | regeneration_history, prompt_version_aliases, prompt_templates, batch_generation_jobs, batch_generation_job_skus |
| Legacy/Jobs | 1 | generation_jobs |
| Measurement & Classification | 2 | sku_bottleneck_classifications, gmc_product_status |
| Tier Scoring & Routing | 3 | query_value_scores, routing_recommendations, search_buildout_recommendations |
| Competitor Intelligence | 3 | competitor_listings, competitor_patterns, competitor_scrape_jobs |
| Support | 1 | shopify_products |
| Backfill Infrastructure | 2 | backfill_jobs, backfill_job_errors |
| GA4 Attribution (KEEP) | 4 | ga4_source_medium_daily, ga4_landing_page_quality_daily, ga4_attribution_root_cause_daily, ga4_shopify_reconciliation_daily |
| Intent Execution (KEEP) | 10 | term_intent_state, policy_decision_log, policy_action_execution_log, policy_snapshots, experiment_registry, experiment_assignments, experiment_outcomes, negative_registry, search_buildout_recommendations, operator_review_audit |
| Deferred (DEFER) | 4 | intent_taxonomy_versions, sku_margin_daily, order_line_returns_daily, attribution_confidence_daily |
| **Total** | **56** | |

### Status Tags

- No tag = Core production table (actively used)
- **KEEP** = Migration 034b/035b table kept per Phase 28 triage. Exists in production, has code consumers, awaiting data pipeline activation. Tagged on table headers.
- **DEFER** = Migration 034b/035b table deferred per Phase 28 triage. Exists in production at zero cost, no active data pipeline. Re-evaluate in v1.3c/v1.4. Tagged on table headers.

### Quick Reference: JSONB Conventions

**Storage**: JSONB columns may be stored as text strings. Parse before array operations:

```sql
-- CORRECT: Parse to JSONB first
SELECT * FROM table WHERE 'value' = ANY(SELECT jsonb_array_elements_text((jsonb_column#>>'{}')::jsonb));
```

**LATERAL joins** for array expansion:

```sql
SELECT t.id, elem.value
FROM table t
CROSS JOIN LATERAL jsonb_array_elements_text((t.jsonb_column#>>'{}')::jsonb) AS elem(value);
```

### Quick Reference: Column Naming Conventions

- `approval_status` (not `status`) for approval tracking
- `notes` (not `revision_notes`) for text notes
- `approved_by` / `approved_at` for approval attribution
- `created_at` / `updated_at` for timestamps
- Use `LOWER()` on both sides for case-insensitive matching

### Quick Reference: Case Sensitivity

- **Master SKUs**: Case-sensitive, slash separators: `WP-2/16-GAL`, `DMF-2/2X`
- **URLs**: Convert slashes to hyphens: `WP-2-16-GAL`, `DMF-2-2X`
- **GMC offer IDs**: Lowercase "us" in database: `shopify_us_{product_id}_{variant_id}`
- **Publishing**: Transform to uppercase for GMC: `shopify_US_{product_id}_{variant_id}`

### Quick Reference: Multi-SKU Products

Multiple master_skus can share the same Shopify product_id (e.g., DMF-2/2X, DMF-2/3X, DMF-2/4X, DMF-2/5X all share `4539975336068`). Google Ads aggregates at product_id level.

---

## Core Content Tables

### generated_content

Stores generated titles and descriptions for master SKUs across platforms. Single source of truth for content state.

| Column | Type | Nullable | Default | Notes |
|--------|------|----------|---------|-------|
| id | uuid | NO | gen_random_uuid() | Primary key |
| master_sku | text | NO | - | Master SKU identifier |
| platform | text | NO | - | "google", "bing", "shopify" |
| content_type | text | NO | - | "title", "description" |
| baseline_content | text | YES | - | Original content before optimization |
| candidate_content | text | YES | - | AI-generated candidate |
| approved_content | text | YES | - | User-approved content (immutable) |
| approved_at | timestamptz | YES | - | Approval timestamp |
| approved_version | integer | YES | - | Version number at approval |
| quality_score | numeric | YES | - | AI quality score (0-100) |
| quality_breakdown | jsonb | YES | - | Detailed scoring breakdown |
| generation_model | text | YES | - | Model used (e.g., "gpt-4") |
| generation_prompt_hash | text | YES | - | Hash of prompt used |
| generation_timestamp | timestamptz | YES | - | When content was generated |
| version | integer | YES | 1 | Content version number |
| is_current | boolean | YES | true | Current version flag |
| created_at | timestamptz | NO | now() | Record creation time |
| updated_at | timestamptz | NO | now() | Last update time |

**Unique Constraint**: `(master_sku, platform, content_type)`

**Indexes**: `idx_content_sku` (master_sku), `idx_content_platform` (platform), `idx_content_score` (quality_score DESC NULLS LAST), `idx_content_current` (master_sku, platform, content_type WHERE is_current = true), `idx_generated_content_approved` (master_sku, platform, content_type WHERE approved_content IS NOT NULL)

```sql
-- Get approved content for publishing
SELECT master_sku, content_type, approved_content
FROM generated_content
WHERE master_sku = 'WP-2/16-GAL' AND platform = 'google' AND approved_content IS NOT NULL;
```

---

### sku_approvals

Tracks approval status for master SKUs. Controls whether content is ready for publishing.

| Column | Type | Nullable | Default | Notes |
|--------|------|----------|---------|-------|
| id | bigint | NO | nextval() | Serial ID |
| master_sku | text | NO | - | Primary key (UNIQUE) |
| title_approved | boolean | YES | - | Title approval flag |
| description_approved | boolean | YES | - | Description approval flag |
| image_approved | boolean | YES | - | Image approval flag |
| selected_finish | text | YES | - | User-selected finish for hero image |
| selected_image_index | integer | YES | - | User-selected image index |
| approval_status | text | NO | 'pending' | 'pending', 'approved', 'rejected' |
| notes | text | YES | - | Approval notes |
| approved_by | text | YES | - | User who approved |
| approved_at | timestamptz | YES | - | Approval timestamp |
| created_at | timestamptz | NO | now() | Record creation time |
| updated_at | timestamptz | NO | now() | Last update time |

**Primary Key**: `master_sku` (UNIQUE)

**Indexes**: `idx_sku_approvals_status` (approval_status)

**Check Constraints**: `approval_status IN ('pending', 'approved', 'rejected')`

---

### variant_approvals

Tracks approval status for individual finish variants.

| Column | Type | Nullable | Default | Notes |
|--------|------|----------|---------|-------|
| id | bigint | NO | nextval() | Primary key |
| master_sku | text | NO | - | Master SKU identifier |
| finish | text | NO | - | Full finish name |
| finish_code | text | YES | - | Short finish code |
| title_approved | boolean | YES | - | Title approval flag |
| description_approved | boolean | YES | - | Description approval flag |
| image_approved | boolean | YES | - | Image approval flag |
| selected_image_index | integer | YES | - | User-selected image index |
| approval_status | text | NO | 'pending' | Overall approval status |
| notes | text | YES | - | Approval notes |
| approved_by | text | YES | - | User who approved |
| approved_at | timestamptz | YES | - | Approval timestamp |
| created_at | timestamptz | NO | now() | Record creation time |
| updated_at | timestamptz | NO | now() | Last update time |

**Unique Constraint**: `(master_sku, finish)`

---

### variant_finish_sentences

Stores finish-specific sentences used to generate variant content. Maps `{FINISH_NAME}` placeholders.

| Column | Type | Nullable | Default | Notes |
|--------|------|----------|---------|-------|
| id | uuid | NO | gen_random_uuid() | Primary key |
| master_sku | text | NO | - | Master SKU identifier |
| platform | text | NO | - | "google", "bing" |
| finish_sentences | jsonb | NO | - | Map of finish_code to sentence |
| created_at | timestamptz | NO | now() | Record creation time |
| updated_at | timestamptz | NO | now() | Last update time |

**Unique Constraint**: `(master_sku, platform)`

**Check Constraints**: `platform IN ('google', 'bing')`

**JSONB Structure**: `{"BKM": "in Black Matte finish", "BBR": "in Brushed Bronze finish"}`

---

## Publishing Tables

### publish_batches

Manages batch publishing operations.

| Column | Type | Nullable | Default | Notes |
|--------|------|----------|---------|-------|
| id | bigint | NO | nextval() | Serial ID |
| batch_id | text | NO | - | Primary key (UNIQUE) |
| name | text | YES | - | User-friendly batch name |
| status | text | NO | 'pending' | Batch status |
| target_date | text | YES | - | Target publish date |
| sku_count | integer | YES | 0 | Number of SKUs in batch |
| success_count | integer | YES | 0 | Successfully published |
| failed_count | integer | YES | 0 | Failed SKUs |
| notes | text | YES | - | Batch notes |
| created_at | timestamptz | NO | now() | Batch creation time |
| executed_at | timestamptz | YES | - | Execution timestamp |

**Primary Key**: `batch_id`

**Check Constraints**: `status IN ('draft', 'pending', 'executing', 'published', 'partial', 'failed')`

---

### batch_sku_assignments

Links SKUs to publish batches.

| Column | Type | Nullable | Default | Notes |
|--------|------|----------|---------|-------|
| id | integer | NO | nextval() | Primary key |
| batch_id | text | NO | - | FK to publish_batches |
| master_sku | text | NO | - | Master SKU identifier |
| created_at | timestamptz | NO | now() | Assignment timestamp |

**Unique Constraint**: `(batch_id, master_sku)`

**Foreign Key**: `batch_id` references `publish_batches(batch_id)`

---

### publish_events

Audit log for all publishing operations. Stores content snapshots for rollback.

| Column | Type | Nullable | Default | Notes |
|--------|------|----------|---------|-------|
| id | integer | NO | nextval() | Primary key |
| master_sku | text | NO | - | Master SKU identifier |
| platform | text | NO | - | "google", "bing", "shopify" |
| environment | text | NO | - | "staging", "production" |
| action | text | NO | 'publish' | Action type |
| status | text | NO | - | "success", "failed", "pending" |
| batch_id | text | YES | - | Associated batch ID |
| patch_file | text | YES | '' | Path to patch file |
| published_title | text | YES | - | Snapshot: published title |
| published_description | text | YES | - | Snapshot: published description |
| variant_count | integer | YES | - | Variants expanded |
| content_version | integer | YES | - | Content version at publish |
| quality_score | real | YES | - | Quality score at publish |
| product_category | text | YES | - | Product category |
| product_collection | text | YES | - | Product collection |
| approval_status | text | YES | - | Approval status at publish |
| published_by | text | YES | - | User who published |
| rollback_id | bigint | YES | - | ID of event being rolled back |
| error_message | text | YES | - | Error details if failed |
| published_at | timestamptz | NO | now() | Publish timestamp |
| final_payload_snapshot | jsonb | YES | - | Post-expansion channel-ready payload (migration 033) |
| final_payload_hash | text | YES | - | SHA-256 of payload JSON (migration 034) |
| prompt_hash | text | YES | - | Prompt identity hash for lineage (migration 034) |
| evidence_hash | text | YES | - | SHA-256 of evidence input (migration 034) |
| segment_key | text | YES | - | Normalized custom_label_0 (migration 034) |

**Indexes**: `idx_publish_events_sku` (master_sku), `idx_publish_events_published_at` (published_at DESC), `idx_publish_events_platform_env` (platform, environment), `idx_publish_events_final_payload_hash`, `idx_publish_events_prompt_hash`, `idx_publish_events_segment_key`

**Check Constraints**: `environment IN ('staging', 'production')`, `status IN ('success', 'failed', 'pending')`

---

## Product Data Tables

### variant_index

**THE SOURCE OF TRUTH** for master_sku to gmc_offer_id mapping. ~72,023 rows.

| Column | Type | Nullable | Default | Notes |
|--------|------|----------|---------|-------|
| id | bigint | NO | nextval() | Primary key |
| gmc_offer_id | text | NO | - | GMC offer ID (lowercase "us") |
| master_sku | text | NO | - | Master SKU identifier |
| option_sku | text | YES | - | Unique per variant |
| shopify_product_id | text | YES | - | Shopify product ID |
| shopify_variant_id | text | YES | - | Shopify variant ID |
| finish | text | YES | - | Full finish name |
| finish_code | text | YES | - | Short finish code |
| dimensions | text | YES | - | Product dimensions |
| product_title | text | YES | - | Product title |
| product_category | text | YES | - | Product category |
| created_at | timestamptz | NO | now() | Record creation time |
| updated_at | timestamptz | NO | now() | Last update time |

**Unique Constraints**: `gmc_offer_id`, `option_sku` (idx_variant_index_option_sku)

**Indexes**: `idx_variant_master_sku` (master_sku), `idx_variant_shopify` (shopify_product_id)

---

### product_catalog

Comprehensive product data. ~75,770 variants.

| Column | Type | Nullable | Default | Notes |
|--------|------|----------|---------|-------|
| id | bigint | NO | nextval() | Primary key |
| master_sku | text | NO | - | Master SKU identifier |
| option_sku | text | NO | - | Unique option SKU |
| core_sku | text | YES | - | Core product SKU |
| upc | text | YES | - | UPC code |
| gtin | text | YES | - | GTIN code |
| gmc_id | text | YES | - | GMC item ID |
| amazon_asin | text | YES | - | Amazon ASIN |
| finish_name | text | NO | - | Full finish name |
| finish_code | text | NO | - | Short finish code |
| position | integer | YES | - | Sort position |
| category | text | NO | - | Product category |
| collection | text | YES | - | Product collection |
| title | text | NO | - | Product title |
| narrative_copy | text | YES | - | Descriptive narrative |
| bullet_1 through bullet_6 | text | YES | - | Feature bullets |
| product_length | numeric | YES | - | Length (inches) |
| product_height | numeric | YES | - | Height (inches) |
| product_width | numeric | YES | - | Width (inches) |
| projection | numeric | YES | - | Projection (inches) |
| product_weight | numeric | YES | - | Weight (lbs) |
| box_length | numeric | YES | - | Box length |
| box_height | numeric | YES | - | Box height |
| box_width | numeric | YES | - | Box width |
| box_weight | numeric | YES | - | Box weight |
| center_to_center | numeric | YES | - | Center-to-center measurement |
| diameter | numeric | YES | - | Diameter (inches) |
| screw_size | text | YES | - | Screw size |
| mirror_height | numeric | YES | - | Mirror height |
| mirror_width | numeric | YES | - | Mirror width |
| thickness | numeric | YES | - | Thickness |
| weight_capacity | numeric | YES | - | Weight capacity (lbs) |
| material | text | YES | - | Material type |
| style | text | YES | - | Style description |
| shape | text | YES | - | Shape |
| orientation | text | YES | - | Orientation |
| tilting | text | YES | - | Tilting capability |
| mounting_type | text | YES | - | Mounting type |
| assembly_required | boolean | YES | false | Assembly required flag |
| item_number | text | YES | - | Item number |
| included_items | text | YES | - | Included items |
| installation_url | text | YES | - | Installation guide URL |
| specification_url | text | YES | - | Specification sheet URL |
| main_image_filename | text | YES | - | Main image filename |
| main_image_url | text | YES | - | Main image URL |
| alt_image_1 through alt_image_4 | text | YES | - | Alt image URLs |
| created_at | timestamptz | NO | now() | Record creation time |
| updated_at | timestamptz | NO | now() | Last update time |

**Unique Constraint**: `option_sku`

**Indexes**: `idx_product_catalog_master_sku`, `idx_product_catalog_finish` (master_sku, finish_code), `idx_product_catalog_category`, `idx_product_catalog_collection`, `idx_product_catalog_gmc_id`, `idx_product_catalog_narrative_fts` (full-text search)

---

## Performance Tracking Tables

### performance_baselines

30-day pre-optimization performance metrics. Auto-captured, stale threshold 60 days.

| Column | Type | Nullable | Default | Notes |
|--------|------|----------|---------|-------|
| master_sku | text | NO | - | PK part 1 |
| platform | text | NO | - | PK part 2 ("google", "bing") |
| baseline_start_date | date | NO | - | Start date (converted from text in migration 032) |
| baseline_end_date | date | NO | - | End date |
| avg_impressions | real | YES | - | Average daily impressions |
| avg_clicks | real | YES | - | Average daily clicks |
| avg_ctr | real | YES | - | Average CTR (0-1) |
| avg_conversions | real | YES | - | Average daily conversions |
| avg_conversion_value | numeric(18,6) | YES | - | Average daily conversion value |
| avg_cvr | real | YES | - | Average CVR (0-1) |
| avg_cost | numeric(18,6) | YES | - | Average daily cost |
| avg_roas | real | YES | - | Average ROAS |
| metadata | jsonb | YES | '{}'::jsonb | Baseline metadata flags |
| created_at | timestamptz | NO | now() | Baseline capture time |

**Primary Key**: `(master_sku, platform)`

---

### performance_snapshots

Daily fact table for post-publish shopping performance. Powers diff-in-diff scorecards.

| Column | Type | Nullable | Default | Notes |
|--------|------|----------|---------|-------|
| id | bigint | NO | nextval() | Primary key |
| master_sku | text | NO | - | Master SKU identifier |
| platform | text | NO | - | "google", "bing" |
| environment | text | NO | - | "staging", "production" |
| snapshot_date | date | NO | - | Daily snapshot date (converted from text) |
| impressions | integer | YES | 0 | Total impressions |
| clicks | integer | YES | 0 | Total clicks |
| ctr | real | YES | 0.0 | Click-through rate |
| conversions | integer | YES | 0 | Total conversions |
| conversion_value | numeric(18,6) | YES | 0.0 | Total conversion value |
| cvr | real | YES | 0.0 | Conversion rate |
| cost | numeric(18,6) | YES | 0.0 | Total cost |
| cpc | numeric(18,6) | YES | 0.0 | Cost per click |
| roas | real | YES | 0.0 | Return on ad spend |
| publish_event_id | bigint | YES | - | FK to publish_events |
| content_version | text | YES | - | Content version at snapshot |
| days_since_publish | integer | YES | - | Days since publish |
| cohort_type | text | YES | - | 'treated' or 'control' |
| product_category | text | YES | - | Category for control matching |
| fetched_at | timestamptz | NO | now() | Data fetch timestamp |

**Unique Constraint**: `uq_performance_snapshots_daily` on `(master_sku, platform, environment, snapshot_date)`

**Indexes**: `idx_snapshots_sku_platform_date`, `idx_performance_snapshots_snapshot_date`, `idx_performance_snapshots_platform_snapshot_date`, `idx_performance_snapshots_publish_event`, `idx_performance_snapshots_cohort_date`

**Check Constraints**: `chk_performance_snapshots_cohort_type` — `cohort_type IN ('treated', 'control')`

---

### performance_impact_scores

Diff-in-diff scorecards by publish event and metric. Created in migration 032, also in 20260225083710.

| Column | Type | Nullable | Default | Notes |
|--------|------|----------|---------|-------|
| id | bigint | NO | nextval() | Primary key |
| publish_event_id | bigint | NO | - | FK to publish_events |
| master_sku | text | NO | - | Master SKU identifier |
| platform | text | NO | - | "google" |
| environment | text | NO | - | "production"/"staging" |
| metric_name | text | NO | - | roas, cvr, ctr, clicks, etc. |
| pre_value | numeric(18,8) | YES | - | Treated pre-window mean |
| post_value | numeric(18,8) | YES | - | Treated post-window mean |
| control_pre | numeric(18,8) | YES | - | Control pre-window mean |
| control_post | numeric(18,8) | YES | - | Control post-window mean |
| did_lift_pct | numeric(18,8) | YES | - | Diff-in-diff lift percentage |
| label | text | NO | - | 'positive', 'negative', 'neutral' |
| confidence | numeric(6,4) | NO | 0 | Confidence score (0-1) |
| sample_size_treated | integer | NO | 0 | Treated sample size |
| sample_size_control | integer | NO | 0 | Control sample size |
| window_pre_days | integer | NO | 30 | Pre window length |
| window_post_days | integer | NO | 30 | Post window length |
| run_date | date | NO | - | Job run date |
| computed_at | timestamptz | NO | now() | Computation timestamp |

**Unique Constraint**: `(publish_event_id, metric_name, platform, environment)`

**Check Constraints**: `chk_performance_impact_scores_label` — `label IN ('positive', 'negative', 'neutral')`

**Indexes**: `idx_performance_impact_scores_publish_event`, `idx_performance_impact_scores_master_sku`, `idx_performance_impact_scores_run_date`, `idx_performance_impact_scores_metric`, `idx_performance_impact_scores_label`

---

## Search & Keyword Tables

### search_queries

Variant-level Google Ads search terms data. Enriched with Keyword Planner metrics.

| Column | Type | Nullable | Default | Notes |
|--------|------|----------|---------|-------|
| id | uuid | NO | gen_random_uuid() | Primary key |
| query_text | text | NO | - | Search query text |
| gmc_offer_id | text | YES | - | GMC offer ID |
| master_sku | text | YES | - | Denormalized from variant_index |
| finish | text | YES | - | Finish name (denormalized) |
| finish_code | text | YES | - | Finish code (denormalized) |
| shopify_variant_id | text | YES | - | Shopify variant ID |
| campaign_id | text | YES | - | Google Ads campaign ID |
| ad_group_id | text | YES | - | Google Ads ad group ID |
| item_ids | jsonb | YES | - | Array of GMC item IDs |
| impressions | integer | YES | 0 | Total impressions |
| clicks | integer | YES | 0 | Total clicks |
| conversions | numeric | YES | 0 | Total conversions |
| conversion_value | numeric | YES | 0 | Total conversion value |
| cost_micros | bigint | YES | 0 | Total cost in micros |
| ctr | numeric | YES | - | Click-through rate |
| cvr | numeric | YES | - | Conversion rate |
| avg_monthly_searches | integer | YES | - | Keyword Planner data |
| competition | text | YES | - | LOW/MEDIUM/HIGH/UNSPECIFIED |
| competition_index | integer | YES | - | 0-100 |
| low_cpc_micros | bigint | YES | - | Low CPC bid |
| high_cpc_micros | bigint | YES | - | High CPC bid |
| keyword_metrics_updated_at | timestamptz | YES | - | Last keyword enrichment |
| period_start | date | NO | - | Query period start |
| period_end | date | NO | - | Query period end |
| fetched_at | timestamptz | YES | now() | Data fetch timestamp |
| synced_at | timestamptz | YES | - | Last sync timestamp |
| sync_job_id | uuid | YES | - | FK to search_query_sync_jobs |

**Unique Constraint**: `(query_text, gmc_offer_id, period_start, period_end)`

**Indexes**: `idx_search_queries_master_sku`, `idx_search_queries_gmc`, `idx_search_queries_finish`, `idx_search_queries_impressions`, `idx_search_queries_period`, `idx_search_queries_sync_job`, `idx_search_queries_ad_group_id`, `idx_search_queries_synced_at`

---

### search_queries_by_master_sku

Aggregated search query data at master SKU level.

| Column | Type | Nullable | Default | Notes |
|--------|------|----------|---------|-------|
| id | uuid | NO | gen_random_uuid() | Primary key |
| master_sku | text | NO | - | Master SKU identifier |
| query_text | text | NO | - | Search query text |
| total_impressions | integer | YES | 0 | Sum across variants |
| total_clicks | integer | YES | 0 | Sum of clicks |
| total_conversions | numeric | YES | 0 | Sum of conversions |
| total_conversion_value | numeric | YES | 0 | Sum of conversion value |
| variant_count | integer | YES | 1 | Variants with this query |
| top_variant_finish | text | YES | - | Finish with most impressions |
| top_variant_finish_code | text | YES | - | Top variant finish code |
| avg_monthly_searches | integer | YES | - | Keyword Planner data |
| competition | text | YES | - | Keyword Planner data |
| competition_index | integer | YES | - | Keyword Planner data |
| period_start | date | NO | - | Query period start |
| period_end | date | NO | - | Query period end |
| updated_at | timestamptz | YES | now() | Last update time |

**Unique Constraint**: `(master_sku, query_text, period_start, period_end)`

---

### keyword_metrics

Cached Google Ads Keyword Planner data. 30-day TTL.

| Column | Type | Nullable | Default | Notes |
|--------|------|----------|---------|-------|
| keyword | text | NO | - | Primary key |
| avg_monthly_searches | integer | YES | - | 12-month average |
| competition | text | YES | - | LOW/MEDIUM/HIGH/UNSPECIFIED |
| competition_index | integer | YES | - | 0-100 |
| low_cpc_micros | bigint | YES | - | 20th percentile CPC bid |
| high_cpc_micros | bigint | YES | - | 80th percentile CPC bid |
| monthly_searches | jsonb | YES | - | Per-month breakdown |
| updated_at | timestamptz | YES | now() | Last update time |

**Primary Key**: `keyword`

---

### search_query_snapshots

Timestamped snapshots of search query performance for delta tracking after publish. Created in Phase 29.

| Column | Type | Nullable | Default | Notes |
|--------|------|----------|---------|-------|
| id | uuid | NO | gen_random_uuid() | Primary key |
| query_text | text | NO | - | Search query text |
| master_sku | text | NO | - | Master SKU identifier |
| gmc_offer_id | text | YES | - | GMC offer ID |
| finish | text | YES | - | Finish name |
| finish_code | text | YES | - | Finish code |
| impressions | integer | YES | 0 | Impressions in period |
| clicks | integer | YES | 0 | Clicks in period |
| conversions | numeric | YES | 0 | Conversions |
| conversion_value | numeric | YES | 0 | Conversion value |
| cost_micros | bigint | YES | 0 | Cost in micros |
| ctr | numeric | YES | - | Click-through rate |
| cvr | numeric | YES | - | Conversion rate |
| avg_monthly_searches | integer | YES | - | Keyword Planner data |
| competition | text | YES | - | Keyword Planner data |
| competition_index | integer | YES | - | Keyword Planner data |
| low_cpc_micros | bigint | YES | - | Keyword Planner data |
| high_cpc_micros | bigint | YES | - | Keyword Planner data |
| snapshot_date | date | NO | - | Date of snapshot |
| days_since_publish | integer | YES | - | Days since publish event |
| publish_event_id | bigint | YES | - | FK to publish_events |
| content_version | integer | YES | - | Content version |
| period_start | date | NO | - | Query period start |
| period_end | date | NO | - | Query period end |
| fetched_at | timestamptz | YES | now() | Data fetch time |

**Unique Constraint**: `search_query_snapshots_unique` on `(query_text, master_sku, snapshot_date)`

**Indexes**: `idx_search_query_snapshots_master_sku`, `idx_search_query_snapshots_query_text`, `idx_search_query_snapshots_snapshot_date`, `idx_search_query_snapshots_publish_event_id`

---

### search_query_sync_jobs

Tracks search query data collection jobs.

| Column | Type | Nullable | Default | Notes |
|--------|------|----------|---------|-------|
| id | uuid | NO | gen_random_uuid() | Primary key |
| status | text | NO | 'pending' | Job status |
| job_type | text | NO | 'search_terms' | Job type |
| days_lookback | integer | YES | 30 | Days to look back |
| limit_results | integer | YES | 1000 | Max results |
| enrich_with_keyword_planner | boolean | YES | false | Enrich flag |
| queries_fetched | integer | YES | 0 | Queries fetched |
| queries_enriched | integer | YES | 0 | Queries enriched |
| error_message | text | YES | - | Error details |
| created_at | timestamptz | NO | now() | Job creation time |
| started_at | timestamptz | YES | - | Job start time |
| completed_at | timestamptz | YES | - | Job completion time |

**Check Constraints**: `status IN ('pending', 'running', 'completed', 'failed')`, `job_type IN ('search_terms', 'keyword_planner', 'full_sync')`

---

### keyword_coverage_master

Keyword coverage tracking for master SKU content.

| Column | Type | Nullable | Default | Notes |
|--------|------|----------|---------|-------|
| id | uuid | NO | gen_random_uuid() | Primary key |
| master_sku | text | NO | - | Master SKU identifier |
| keyword | text | NO | - | Keyword to check |
| in_title | boolean | YES | false | Present in title |
| in_description | boolean | YES | false | Present in description |
| query_volume | integer | YES | 0 | Search query impressions |
| avg_monthly_searches | integer | YES | - | Keyword Planner volume |
| updated_at | timestamptz | YES | now() | Last update time |

**Unique Constraint**: `(master_sku, keyword)`

---

### keyword_coverage_variant

Keyword coverage tracking for variant content.

| Column | Type | Nullable | Default | Notes |
|--------|------|----------|---------|-------|
| id | uuid | NO | gen_random_uuid() | Primary key |
| master_sku | text | NO | - | Master SKU identifier |
| finish | text | NO | - | Finish name |
| finish_code | text | YES | - | Finish code |
| gmc_offer_id | text | YES | - | GMC offer ID |
| keyword | text | NO | - | Keyword to check |
| in_title | boolean | YES | false | Present in title |
| in_description | boolean | YES | false | Present in description |
| query_volume | integer | YES | 0 | Search query impressions |
| avg_monthly_searches | integer | YES | - | Keyword Planner volume |
| updated_at | timestamptz | YES | now() | Last update time |

**Unique Constraint**: `(master_sku, finish, keyword)`

---

### finish_search_patterns

Aggregated search query patterns by finish.

| Column | Type | Nullable | Default | Notes |
|--------|------|----------|---------|-------|
| id | uuid | NO | gen_random_uuid() | Primary key |
| finish | text | NO | - | Full finish name |
| finish_code | text | NO | - | Short finish code |
| pattern_keyword | text | NO | - | Pattern keyword |
| category | text | YES | - | Product category |
| total_impressions | integer | YES | 0 | Sum of impressions |
| total_clicks | integer | YES | 0 | Sum of clicks |
| query_count | integer | YES | 1 | Number of queries |
| updated_at | timestamptz | YES | now() | Last update time |

**Unique Constraint**: `(finish_code, pattern_keyword, category)`

---

### funnel_snapshots_daily

Historical shopping funnel data. Created in Phase 30 (migration 20260225105102). ~4,093 rows (backfilled in Phase 30.1).

| Column | Type | Nullable | Default | Notes |
|--------|------|----------|---------|-------|
| id | uuid | NO | gen_random_uuid() | Primary key |
| snapshot_date | date | NO | - | Daily snapshot date |
| custom_label_0 | text | NO | - | Product segment label |
| tier | text | NO | - | 'HIGH', 'MEDIUM', 'LOW' |
| impressions | bigint | NO | 0 | Total impressions |
| clicks | bigint | NO | 0 | Total clicks |
| cost_micros | bigint | NO | 0 | Total cost in micros |
| conversions | double precision | NO | 0 | Total conversions |
| conversions_value | double precision | NO | 0 | Total conversion value |
| roas | double precision | NO | 0 | Return on ad spend |
| captured_at | timestamptz | NO | now() | Capture timestamp |

**Unique Constraint**: `(snapshot_date, custom_label_0, tier)`

**Check Constraints**: `tier IN ('HIGH', 'MEDIUM', 'LOW')`

---

## Image Tables

### product_lifestyle_images

Product-level lifestyle images (master SKU level).

| Column | Type | Nullable | Default | Notes |
|--------|------|----------|---------|-------|
| id | uuid | NO | gen_random_uuid() | Primary key |
| master_sku | text | NO | - | Master SKU identifier |
| shopify_product_id | text | NO | - | Shopify product ID |
| variation_index | integer | NO | - | Image variation (1-N) |
| image_url | text | NO | - | Supabase Storage URL |
| thumbnail_url | text | YES | - | Thumbnail URL |
| shopify_media_id | text | YES | - | Shopify media ID |
| shopify_cdn_url | text | YES | - | Shopify CDN URL |
| migrated_to_shopify_at | timestamptz | YES | - | Migration timestamp |
| prompt | text | YES | - | Generation prompt |
| generation_model | text | YES | - | Model used |
| generation_timestamp | timestamptz | YES | - | Generation time |
| score | numeric | YES | - | Quality score (0-100) |
| score_breakdown | jsonb | YES | - | Detailed scoring |
| approval_status | text | NO | 'pending' | Approval status |
| approved_by | text | YES | - | User who approved |
| approved_at | timestamptz | YES | - | Approval timestamp |
| rejection_reason | text | YES | - | Rejection reason |
| ai_selected | boolean | YES | false | AI-selected flag |
| user_selected | boolean | YES | false | User-selected flag |
| created_at | timestamptz | NO | now() | Record creation time |

**Unique Constraint**: `(master_sku, variation_index)`

**Lifecycle**: Supabase Storage -> Shopify CDN -> Google Sheets

---

### variant_lifestyle_images

Variant-level lifestyle images (finish-specific).

| Column | Type | Nullable | Default | Notes |
|--------|------|----------|---------|-------|
| id | uuid | NO | gen_random_uuid() | Primary key |
| master_sku | text | NO | - | Master SKU identifier |
| gmc_offer_id | text | NO | - | GMC offer ID |
| finish | text | NO | - | Full finish name |
| finish_code | text | NO | - | Short finish code |
| variation_index | integer | NO | - | Image variation (1-N) |
| image_url | text | NO | - | Supabase Storage URL |
| thumbnail_url | text | YES | - | Thumbnail URL |
| shopify_media_id | text | YES | - | Shopify media ID |
| shopify_cdn_url | text | YES | - | Shopify CDN URL |
| migrated_to_shopify_at | timestamptz | YES | - | Migration timestamp |
| gmc_pushed_at | timestamptz | YES | - | GMC push timestamp |
| prompt | text | YES | - | Generation prompt |
| generation_model | text | YES | - | Model used |
| generation_timestamp | timestamptz | YES | - | Generation time |
| score | numeric | YES | - | Quality score (0-100) |
| score_breakdown | jsonb | YES | - | Detailed scoring |
| approval_status | text | NO | 'pending' | Approval status |
| approved_by | text | YES | - | User who approved |
| approved_at | timestamptz | YES | - | Approval timestamp |
| rejection_reason | text | YES | - | Rejection reason |
| ai_selected | boolean | YES | false | AI-selected flag |
| user_selected | boolean | YES | false | User-selected flag |
| created_at | timestamptz | NO | now() | Record creation time |

**Unique Constraint**: `(gmc_offer_id, variation_index)`

---

### lifestyle_image_selections

User's selected hero images.

| Column | Type | Nullable | Default | Notes |
|--------|------|----------|---------|-------|
| id | uuid | NO | gen_random_uuid() | Primary key |
| master_sku | text | NO | - | Master SKU identifier |
| finish | text | YES | - | Finish name (NULL = product-level) |
| selected_image_id | uuid | YES | - | FK to lifestyle images |
| selection_reason | text | YES | - | Selection reason |
| selected_by | text | YES | - | User who selected |
| selected_at | timestamptz | YES | now() | Selection timestamp |

**Unique Constraint**: `(master_sku, COALESCE(finish, ''))`

---

## Content Generation Tables

### regeneration_history

Audit log for content regeneration operations.

| Column | Type | Nullable | Default | Notes |
|--------|------|----------|---------|-------|
| id | uuid | NO | gen_random_uuid() | Primary key |
| master_sku | text | NO | - | Master SKU identifier |
| content_type | text | NO | - | "title", "description" |
| platform | text | NO | - | "google", "bing" |
| mode | text | NO | - | Regeneration mode |
| feedback_text | text | YES | - | User feedback text |
| feedback_preset | text | YES | - | Preset feedback option |
| previous_content | text | YES | - | Content before regeneration |
| new_content | text | YES | - | Content after regeneration |
| model_version | text | YES | - | Model used |
| system_prompt | text | YES | - | System prompt used |
| user_prompt | text | YES | - | User prompt used |
| prompt_hash | text | YES | - | Hash of combined prompts |
| quality_score_before | numeric | YES | - | Quality score before |
| quality_score_after | numeric | YES | - | Quality score after |
| generated_content_id | uuid | YES | - | FK to generated_content |
| created_at | timestamptz | NO | now() | Regeneration timestamp |
| created_by | text | YES | - | User who triggered |
| feature_flags_active | jsonb | YES | - | Feature flag state (MEAS-01, migration 035) |
| tokens_used | integer | YES | - | Token count (migration 035) |
| latency_ms | integer | YES | - | Generation latency ms (migration 035) |
| cost_usd | numeric(10,6) | YES | - | Estimated cost USD (migration 035) |

**Indexes**: `idx_regen_history_sku`, `idx_regen_history_sku_type`, `idx_regen_history_created`, `idx_regen_history_prompt_hash`, `idx_regen_history_flags` (GIN)

---

### prompt_version_aliases

Maps prompt hashes to human-readable version names. Created in migration 035.

| Column | Type | Nullable | Default | Notes |
|--------|------|----------|---------|-------|
| id | bigint | NO | nextval() | Primary key |
| prompt_hash | text | NO | - | Unique hash |
| alias | text | YES | - | Human-readable name |
| notes | text | YES | - | Change notes |
| created_at | timestamptz | NO | now() | Created time |
| created_by | text | YES | - | Creator |

**Unique Constraint**: `prompt_hash`

---

### prompt_templates

Stores gold standard examples and system prompts.

| Column | Type | Nullable | Default | Notes |
|--------|------|----------|---------|-------|
| id | uuid | NO | gen_random_uuid() | Primary key |
| name | text | NO | - | Unique template name |
| version | integer | NO | 1 | Template version |
| is_active | boolean | YES | false | Active flag |
| system_prompt | text | NO | - | System prompt text |
| gold_standard_examples | jsonb | NO | - | Example objects |
| category_guidance | jsonb | YES | - | Category guidance |
| platform_rules | jsonb | YES | - | Platform rules |
| description | text | YES | - | Template description |
| created_by | text | YES | - | Creator |
| created_at | timestamptz | YES | now() | Created time |
| updated_at | timestamptz | YES | now() | Updated time |

**Unique Constraint**: `name`

---

### batch_generation_jobs

Manages bulk content generation jobs.

| Column | Type | Nullable | Default | Notes |
|--------|------|----------|---------|-------|
| id | uuid | NO | gen_random_uuid() | Primary key |
| status | text | NO | 'queued' | Job status |
| total_skus | integer | NO | - | Total SKUs |
| completed_skus | integer | YES | 0 | Completed |
| failed_skus | integer | YES | 0 | Failed |
| options | jsonb | NO | '{}' | Job options |
| error_message | text | YES | - | Error details |
| created_at | timestamptz | NO | now() | Created time |
| started_at | timestamptz | YES | - | Start time |
| completed_at | timestamptz | YES | - | Completion time |
| created_by | text | YES | - | Creator |

**Check Constraints**: `status IN ('queued', 'processing', 'completed', 'failed')`

---

### batch_generation_job_skus

Per-SKU status within batch generation jobs.

| Column | Type | Nullable | Default | Notes |
|--------|------|----------|---------|-------|
| id | uuid | NO | gen_random_uuid() | Primary key |
| job_id | uuid | NO | - | FK to batch_generation_jobs |
| master_sku | text | NO | - | Master SKU |
| status | text | NO | 'pending' | SKU status |
| error_message | text | YES | - | Error details |
| generated_content_ids | text[] | YES | - | Array of IDs |
| created_at | timestamptz | NO | now() | Created time |
| started_at | timestamptz | YES | - | Start time |
| completed_at | timestamptz | YES | - | Completion time |

**Unique Constraint**: `(job_id, master_sku)`

**Check Constraints**: `status IN ('pending', 'processing', 'completed', 'failed')`

---

## Legacy Tables

### generation_jobs

Legacy job queue table. May be deprecated in favor of batch_generation_jobs.

| Column | Type | Nullable | Default | Notes |
|--------|------|----------|---------|-------|
| id | uuid | NO | gen_random_uuid() | Primary key |
| master_sku | text | NO | - | Master SKU |
| job_type | text | NO | - | Job type |
| status | text | NO | 'pending' | Status |
| priority | integer | YES | 0 | Priority |
| input_params | jsonb | YES | - | Parameters |
| result | jsonb | YES | - | Result |
| error | text | YES | - | Error |
| attempt_count | integer | YES | 0 | Retries |
| max_attempts | integer | YES | 3 | Max retries |
| requested_by | text | YES | - | Requester |
| created_at | timestamptz | NO | now() | Created |
| started_at | timestamptz | YES | - | Started |
| completed_at | timestamptz | YES | - | Completed |

---

## Measurement & Classification Tables

### sku_bottleneck_classifications

Per-SKU bottleneck classification. Created in migration 035.

| Column | Type | Nullable | Default | Notes |
|--------|------|----------|---------|-------|
| id | bigint | NO | nextval() | Primary key |
| master_sku | text | NO | - | Master SKU |
| classification | text | NO | - | Bottleneck type |
| confidence | numeric(4,2) | YES | - | Confidence 0-1 |
| evidence | jsonb | YES | - | Supporting evidence |
| override_by | text | YES | - | Manual override user |
| override_note | text | YES | - | Override explanation |
| is_override | boolean | YES | false | Override flag |
| classified_at | timestamptz | NO | now() | Classification time |
| publish_event_id | bigint | YES | - | Associated publish event |

**Partial Unique Index**: `idx_sku_bottleneck_master_sku` on `master_sku WHERE is_override = false`

---

### gmc_product_status

Google Merchant Center product approval status. Created in migration 035.

| Column | Type | Nullable | Default | Notes |
|--------|------|----------|---------|-------|
| id | bigint | NO | nextval() | Primary key |
| gmc_offer_id | text | NO | - | GMC offer ID (UNIQUE) |
| master_sku | text | YES | - | Master SKU |
| offer_title | text | YES | - | GMC product title |
| status | text | NO | - | "approved"/"disapproved"/"pending" |
| item_issues | jsonb | YES | - | Array of GMC issues |
| issue_count | integer | YES | 0 | Total issues |
| disapproval_count | integer | YES | 0 | Disapprovals |
| synced_at | timestamptz | NO | now() | Last sync |
| sync_job_id | uuid | YES | - | Source sync job |

**Unique Constraint**: `gmc_offer_id`

---

## Competitor Intelligence Tables

### competitor_listings

Competitor product listings from SERP and marketplaces.

| Column | Type | Nullable | Default | Notes |
|--------|------|----------|---------|-------|
| id | uuid | NO | gen_random_uuid() | Primary key |
| source | text | NO | - | Source identifier |
| source_type | text | NO | - | "serp", "marketplace" |
| source_url | text | YES | - | URL |
| domain | text | YES | - | Seller domain |
| product_category | text | NO | - | Category |
| title | text | NO | - | Product title |
| description | text | YES | - | Description |
| price | numeric | YES | - | Price |
| rating | numeric | YES | - | Star rating |
| review_count | integer | YES | - | Reviews |
| brand | text | YES | - | Brand name |
| position | integer | YES | - | SERP position |
| image_url | text | YES | - | Image URL |
| keywords_extracted | text[] | YES | - | Extracted keywords |
| scraped_at | timestamptz | YES | now() | Scrape time |
| scrape_job_id | uuid | YES | - | FK to scrape_jobs |

**Unique Constraint**: `(source, source_url)`

---

### competitor_patterns

Aggregated patterns from competitor listings.

| Column | Type | Nullable | Default | Notes |
|--------|------|----------|---------|-------|
| id | uuid | NO | gen_random_uuid() | Primary key |
| category | text | NO | - | Product category |
| pattern_type | text | NO | - | "keyword", "phrase" |
| pattern_value | text | NO | - | Pattern value |
| frequency | integer | YES | 1 | Occurrence count |
| avg_position | numeric | YES | - | Average SERP position |
| sources | text[] | YES | - | Source domains |
| example_titles | text[] | YES | - | Example titles |
| updated_at | timestamptz | YES | now() | Updated time |

**Unique Constraint**: `(category, pattern_type, pattern_value)`

---

### competitor_scrape_jobs

Competitor scraping job management.

| Column | Type | Nullable | Default | Notes |
|--------|------|----------|---------|-------|
| id | uuid | NO | gen_random_uuid() | Primary key |
| status | text | NO | 'pending' | Job status |
| job_type | text | NO | - | 'serp', 'marketplace' |
| category | text | NO | - | Product category |
| source | text | NO | - | Source platform |
| search_query | text | YES | - | Search query |
| apify_run_id | text | YES | - | Apify run ID |
| apify_dataset_id | text | YES | - | Apify dataset ID |
| listings_count | integer | YES | 0 | Listings scraped |
| error_message | text | YES | - | Error details |
| created_at | timestamptz | NO | now() | Created time |
| started_at | timestamptz | YES | - | Start time |
| completed_at | timestamptz | YES | - | Completion time |

**Check Constraints**: `status IN ('pending', 'running', 'completed', 'failed')`, `job_type IN ('serp', 'marketplace')`

---

## Support Tables

### shopify_products

Tracks Shopify products (minimal data).

| Column | Type | Nullable | Default | Notes |
|--------|------|----------|---------|-------|
| shopify_product_id | text | NO | - | Primary key |
| created_at | timestamptz | NO | now() | Created time |
| updated_at | timestamptz | NO | now() | Updated time |

---

## Backfill Infrastructure Tables

### backfill_jobs

Historical data backfill job management. Supports checkpoint/resume.

| Column | Type | Nullable | Default | Notes |
|--------|------|----------|---------|-------|
| id | uuid | NO | gen_random_uuid() | Primary key |
| job_type | text | NO | - | Job type |
| status | text | NO | 'creating' | Job status |
| total_items | integer | NO | - | Total items |
| completed_items | integer | YES | 0 | Completed |
| failed_items | integer | YES | 0 | Failed |
| skus | jsonb | YES | - | Array of SKU strings |
| checkpoint_data | jsonb | YES | - | Checkpoint state |
| config | jsonb | YES | '{}' | Job configuration |
| created_at | timestamptz | NO | now() | Created time |
| started_at | timestamptz | YES | - | Start time |
| completed_at | timestamptz | YES | - | Completion time |
| eta_seconds | integer | YES | - | Estimated time remaining |
| created_by | text | YES | - | Creator |

**Check Constraints**: `status IN ('creating', 'running', 'complete', 'failed', 'partial')`, `job_type IN ('search_terms', 'performance_metrics', 'keyword_planner', 'custom_labels', 'full_backfill')`

---

### backfill_job_errors

Per-item error logs for backfill jobs.

| Column | Type | Nullable | Default | Notes |
|--------|------|----------|---------|-------|
| id | bigint | NO | nextval() | Primary key |
| job_id | uuid | NO | - | FK to backfill_jobs (CASCADE) |
| item_id | text | NO | - | Failed item identifier |
| error_type | text | NO | - | Error category |
| error_message | text | YES | - | Detailed error |
| retry_count | integer | YES | 0 | Retry attempts |
| created_at | timestamptz | NO | now() | Error timestamp |

**RPC Functions**: `increment_backfill_failures(p_job_id UUID)`

---

## GA4 Attribution Tables (KEEP)

*Migration 034b. Tables exist in production (created out-of-band). All have active code consumers via `/api/ga4/snapshot-capture/route.ts`. Currently likely empty — awaiting Cloud Scheduler activation.*

### ga4_source_medium_daily [KEEP]

Daily GA4 source/medium breakdowns with quality buckets for attribution diagnostics.

| Column | Type | Nullable | Default | Notes |
|--------|------|----------|---------|-------|
| id | uuid | NO | gen_random_uuid() | Primary key |
| property_id | text | NO | - | GA4 property ID |
| report_date | date | NO | - | Report date |
| source_medium | text | NO | - | Source/medium string |
| quality_bucket | text | NO | - | 'not_set', 'data_not_available', 'valid' |
| sessions | bigint | NO | 0 | Session count |
| transactions | bigint | NO | 0 | Transaction count |
| purchase_revenue | numeric(14,4) | NO | 0 | Revenue |
| revenue_share | numeric(10,6) | NO | 0 | Revenue share |
| session_share | numeric(10,6) | NO | 0 | Session share |
| source_payload | jsonb | NO | '{}'::jsonb | Raw payload |
| created_at | timestamptz | NO | now() | Created time |

**Unique Index**: `(property_id, report_date, quality_bucket, source_medium)`

**Check Constraints**: `quality_bucket IN ('not_set', 'data_not_available', 'valid')`

---

### ga4_landing_page_quality_daily [KEEP]

Daily GA4 landing page quality diagnostics.

| Column | Type | Nullable | Default | Notes |
|--------|------|----------|---------|-------|
| id | uuid | NO | gen_random_uuid() | Primary key |
| property_id | text | NO | - | GA4 property ID |
| report_date | date | NO | - | Report date |
| landing_page | text | NO | - | Landing page path |
| quality_bucket | text | NO | - | 'blank', 'not_set', 'valid' |
| sessions | bigint | NO | 0 | Session count |
| transactions | bigint | NO | 0 | Transaction count |
| purchase_revenue | numeric(14,4) | NO | 0 | Revenue |
| revenue_share | numeric(10,6) | NO | 0 | Revenue share |
| session_share | numeric(10,6) | NO | 0 | Session share |
| source_payload | jsonb | NO | '{}'::jsonb | Raw payload |
| created_at | timestamptz | NO | now() | Created time |

**Unique Index**: `(property_id, report_date, quality_bucket, landing_page)`

**Check Constraints**: `quality_bucket IN ('blank', 'not_set', 'valid')`

---

### ga4_attribution_root_cause_daily [KEEP]

Root cause analysis for attribution quality issues.

| Column | Type | Nullable | Default | Notes |
|--------|------|----------|---------|-------|
| id | uuid | NO | gen_random_uuid() | Primary key |
| property_id | text | NO | - | GA4 property ID |
| report_date | date | NO | - | Report date |
| root_cause_type | text | NO | - | 'source_medium', 'campaign_pattern', 'landing_page' |
| root_cause_key | text | NO | - | Specific root cause |
| sessions | bigint | NO | 0 | Session count |
| transactions | bigint | NO | 0 | Transaction count |
| purchase_revenue | numeric(14,4) | NO | 0 | Revenue |
| revenue_share | numeric(10,6) | NO | 0 | Revenue share |
| session_share | numeric(10,6) | NO | 0 | Session share |
| source_payload | jsonb | NO | '{}'::jsonb | Raw payload |
| created_at | timestamptz | NO | now() | Created time |

**Unique Index**: `(property_id, report_date, root_cause_type, root_cause_key)`

**Check Constraints**: `root_cause_type IN ('source_medium', 'campaign_pattern', 'landing_page')`

---

### ga4_shopify_reconciliation_daily [KEEP]

Daily revenue reconciliation between GA4 and Shopify. Revenue parity monitoring.

| Column | Type | Nullable | Default | Notes |
|--------|------|----------|---------|-------|
| id | uuid | NO | gen_random_uuid() | Primary key |
| property_id | text | NO | - | GA4 property ID |
| report_date | date | NO | - | Report date |
| ga4_revenue | numeric(14,4) | NO | 0 | GA4-reported revenue |
| shopify_revenue | numeric(14,4) | NO | 0 | Shopify order revenue |
| revenue_delta | numeric(14,4) | NO | 0 | Difference |
| revenue_ratio | numeric(12,6) | YES | - | GA4/Shopify ratio |
| order_count | bigint | NO | 0 | Order count |
| source_payload | jsonb | NO | '{}'::jsonb | Raw payload |
| created_at | timestamptz | NO | now() | Created time |

**Unique Index**: `(property_id, report_date)`

---

## Intent Execution Tables (KEEP)

*Migration 035b. Tables exist in production (created out-of-band). All have TypeScript code consumers. Currently likely empty — activated when intent/governance features are used. See Phase 28 triage: `.planning/phases/28-architecture-audit-migration-triage/28-migration-triage.md`*

### term_intent_state [KEEP]

Current resolved intent state per normalized query and label scope.

| Column | Type | Nullable | Default | Notes |
|--------|------|----------|---------|-------|
| id | uuid | NO | gen_random_uuid() | Primary key |
| search_term | text | NO | - | Raw search term |
| normalized_search_term | text | NO | - | Normalized for matching |
| custom_label_0 | text | YES | - | Product segment |
| intent_class | text | NO | - | See check constraint |
| intent_subclasses | text[] | NO | '{}' | Sub-classifications |
| route_action | text | NO | - | See check constraint |
| shopping_tier | text | YES | - | Shopping tier |
| search_tier | text | YES | - | Search tier |
| confidence | numeric(5,4) | NO | 0 | Confidence score |
| requires_review | boolean | NO | true | Human review flag |
| policy_version | text | NO | - | Policy version |
| source_window_start | date | YES | - | Analysis window start |
| source_window_end | date | YES | - | Analysis window end |
| last_decided_at | timestamptz | NO | now() | Last decision time |
| metadata | jsonb | NO | '{}'::jsonb | Additional metadata |
| created_at | timestamptz | NO | now() | Created time |
| updated_at | timestamptz | NO | now() | Updated time |

**Unique Index**: `(normalized_search_term, COALESCE(custom_label_0, '__all__'))`

**Check Constraints**: `intent_class IN ('BRAND_CORE', 'PRODUCT_HIGH', 'CATEGORY_MID', 'DISCOVERY_LOW', 'COMPETITOR', 'INFO_ASSIST', 'MISMATCH', 'RISK_POLICY')`, `route_action IN ('funnel', 'global_block', 'competitor', 'branded', 'search_discovery', 'search_exact_candidate', 'observe_only')`

---

### policy_decision_log [KEEP]

Immutable ledger of policy decisions.

| Column | Type | Nullable | Default | Notes |
|--------|------|----------|---------|-------|
| id | uuid | NO | gen_random_uuid() | Primary key |
| search_term | text | YES | - | Search term |
| custom_label_0 | text | YES | - | Product segment |
| decision_type | text | NO | - | Decision category |
| channel | text | NO | - | Channel |
| policy_version | text | NO | - | Policy version |
| decision_payload | jsonb | NO | '{}'::jsonb | Decision details |
| confidence | numeric(5,4) | YES | - | Confidence score |
| requires_review | boolean | NO | true | Review flag |
| created_by | text | YES | - | Creator |
| created_at | timestamptz | NO | now() | Created time |

**Indexes**: `(decision_type, created_at DESC)`, `(search_term, created_at DESC)`

---

### policy_action_execution_log [KEEP]

Execution status log for policy actions. Most-referenced 035b table (9 production files).

| Column | Type | Nullable | Default | Notes |
|--------|------|----------|---------|-------|
| id | uuid | NO | gen_random_uuid() | Primary key |
| action_type | text | NO | - | Action category |
| search_term | text | YES | - | Search term |
| custom_label_0 | text | YES | - | Product segment |
| status | text | NO | 'planned' | Execution status |
| policy_version | text | NO | - | Policy version |
| action_payload | jsonb | NO | '{}'::jsonb | Action details |
| reason_codes | text[] | NO | '{}' | Reason codes |
| created_by | text | YES | - | Creator |
| created_at | timestamptz | NO | now() | Created time |
| updated_at | timestamptz | NO | now() | Updated time |

**Check Constraints**: `status IN ('planned', 'applied', 'rolled_back', 'failed', 'cancelled')`

**Indexes**: `(status, created_at DESC)`, `(action_type, created_at DESC)`

---

### policy_snapshots [KEEP]

Point-in-time policy snapshots for rollback capability.

| Column | Type | Nullable | Default | Notes |
|--------|------|----------|---------|-------|
| id | uuid | NO | gen_random_uuid() | Primary key |
| snapshot_key | text | NO | - | Unique snapshot key |
| policy_version | text | NO | - | Policy version |
| payload | jsonb | NO | '{}'::jsonb | Complete policy state |
| created_by | text | YES | - | Creator |
| created_at | timestamptz | NO | now() | Created time |
| restored_at | timestamptz | YES | - | Restore timestamp |
| restored_by | text | YES | - | Who restored |

**Unique Constraint**: `snapshot_key`

---

### experiment_registry [KEEP]

Central experiment definitions with thresholds and decision rules.

| Column | Type | Nullable | Default | Notes |
|--------|------|----------|---------|-------|
| id | uuid | NO | gen_random_uuid() | Primary key |
| experiment_key | text | NO | - | Unique experiment key |
| name | text | NO | - | Experiment name |
| initiative | text | NO | - | Initiative category |
| hypothesis | text | NO | - | Hypothesis text |
| decision_rule | text | YES | - | Decision rule |
| success_threshold | numeric(14,4) | YES | - | Success threshold |
| failure_threshold | numeric(14,4) | YES | - | Failure threshold |
| status | text | NO | 'active' | Experiment status |
| start_date | date | NO | - | Start date |
| end_date | date | YES | - | End date |
| metadata | jsonb | NO | '{}'::jsonb | Additional metadata |
| created_by | text | YES | - | Creator |
| created_at | timestamptz | NO | now() | Created time |

**Unique Constraint**: `experiment_key`

**Check Constraints**: `status IN ('draft', 'active', 'paused', 'completed', 'cancelled')`

---

### experiment_assignments [KEEP]

Entity-level cohort assignments for experiments.

| Column | Type | Nullable | Default | Notes |
|--------|------|----------|---------|-------|
| id | uuid | NO | gen_random_uuid() | Primary key |
| experiment_key | text | NO | - | FK to experiment_registry |
| entity_key | text | NO | - | Entity identifier |
| cohort | text | NO | - | Cohort name |
| assigned_at | timestamptz | NO | now() | Assignment time |
| metadata | jsonb | NO | '{}'::jsonb | Additional data |

**Unique Index**: `(experiment_key, entity_key)`

**Foreign Key**: `experiment_key` references `experiment_registry(experiment_key)` ON DELETE CASCADE

---

### experiment_outcomes [KEEP]

Observed outcomes/lift measurements by experiment and metric.

| Column | Type | Nullable | Default | Notes |
|--------|------|----------|---------|-------|
| id | uuid | NO | gen_random_uuid() | Primary key |
| experiment_key | text | NO | - | FK to experiment_registry |
| metric_name | text | NO | - | Metric being measured |
| observed_lift | numeric(14,6) | NO | 0 | Observed lift |
| sample_size | bigint | NO | 0 | Sample size |
| status | text | NO | 'observing' | Outcome status |
| measured_at | timestamptz | NO | now() | Measurement time |
| metadata | jsonb | NO | '{}'::jsonb | Additional data |

**Check Constraints**: `status IN ('observing', 'success', 'failure', 'inconclusive')`

**Foreign Key**: `experiment_key` references `experiment_registry(experiment_key)` ON DELETE CASCADE

---

### negative_registry [KEEP]

Centralized negative keyword governance with rollback tokens.

| Column | Type | Nullable | Default | Notes |
|--------|------|----------|---------|-------|
| id | uuid | NO | gen_random_uuid() | Primary key |
| term | text | NO | - | Negative keyword |
| scope | text | NO | - | Campaign/ad group scope |
| source_policy | text | NO | - | Source policy |
| confidence | numeric(5,4) | NO | 0 | Confidence score |
| reason_codes | text[] | NO | '{}' | Reason codes |
| rollback_token | text | YES | - | Rollback token |
| active | boolean | NO | true | Active flag |
| metadata | jsonb | NO | '{}'::jsonb | Additional data |
| created_by | text | YES | - | Creator |
| created_at | timestamptz | NO | now() | Created time |
| deactivated_at | timestamptz | YES | - | Deactivation time |
| deactivated_by | text | YES | - | Deactivator |

**Indexes**: `(scope, active, created_at DESC)`, `(term, created_at DESC)`

---

### search_buildout_recommendations [KEEP]

Search governance recommendations for match type upgrades.

| Column | Type | Nullable | Default | Notes |
|--------|------|----------|---------|-------|
| id | uuid | NO | gen_random_uuid() | Primary key |
| search_term | text | NO | - | Search term |
| custom_label_0 | text | YES | - | Product segment |
| recommended_search_tier | text | NO | - | 'broad', 'phrase', 'exact' |
| status | text | NO | 'candidate' | Workflow status |
| confidence | numeric(5,4) | NO | 0 | Confidence score |
| metadata | jsonb | NO | '{}'::jsonb | Additional data |
| approved_by | text | YES | - | Approver |
| approved_at | timestamptz | YES | - | Approval time |
| created_at | timestamptz | NO | now() | Created time |

**Check Constraints**: `recommended_search_tier IN ('broad', 'phrase', 'exact')`, `status IN ('candidate', 'approved', 'applied', 'rejected', 'paused')`

**Indexes**: `(status, created_at DESC)`, `(search_term, created_at DESC)`

---

### operator_review_audit [KEEP]

Universal audit trail for human review actions.

| Column | Type | Nullable | Default | Notes |
|--------|------|----------|---------|-------|
| id | uuid | NO | gen_random_uuid() | Primary key |
| queue_name | text | NO | - | Review queue |
| entity_key | text | NO | - | Entity identifier |
| action | text | NO | - | Action taken |
| before_state | jsonb | YES | - | State before action |
| after_state | jsonb | YES | - | State after action |
| actor | text | YES | - | Who acted |
| created_at | timestamptz | NO | now() | Action time |

**Indexes**: `(queue_name, created_at DESC)`, `(entity_key, created_at DESC)`

---

## Deferred Tables (DEFER)

*Migration 035b. Tables exist in production at zero cost. No active data pipeline. Re-evaluate in v1.3c/v1.4. Code consumers handle empty results gracefully.*

### intent_taxonomy_versions [DEFER]

Versioned intent classification taxonomies. Re-evaluate when intent classification work begins in v1.3c.

| Column | Type | Nullable | Default | Notes |
|--------|------|----------|---------|-------|
| id | uuid | NO | gen_random_uuid() | Primary key |
| version_key | text | NO | - | Unique taxonomy version |
| description | text | YES | - | Description |
| class_definitions | jsonb | NO | '{}'::jsonb | Intent class definitions |
| mapping_rules | jsonb | NO | '{}'::jsonb | Mapping rules |
| is_active | boolean | NO | false | Active flag |
| activated_at | timestamptz | YES | - | Activation time |
| activated_by | text | YES | - | Activator |
| created_at | timestamptz | NO | now() | Created time |

**Unique Constraint**: `version_key`

---

### sku_margin_daily [DEFER]

Daily SKU-level margin data. No data source integrated (Shopify does not expose COGS). Re-evaluate in v1.3c.

| Column | Type | Nullable | Default | Notes |
|--------|------|----------|---------|-------|
| id | uuid | NO | gen_random_uuid() | Primary key |
| snapshot_date | date | NO | - | Daily date |
| sku | text | NO | - | SKU identifier |
| unit_cogs | numeric(14,4) | YES | - | Unit COGS |
| gross_margin_rate | numeric(10,6) | YES | - | Gross margin rate |
| currency_code | text | YES | - | Currency code |
| source_payload | jsonb | NO | '{}'::jsonb | Source data |
| created_at | timestamptz | NO | now() | Created time |

**Unique Index**: `(snapshot_date, sku)`

**Code consumers**: `profit-forecast.ts`, `value-signal.ts` (return defaults when empty)

---

### order_line_returns_daily [DEFER]

Daily return data per SKU. No return data pipeline exists. Re-evaluate in v1.3c.

| Column | Type | Nullable | Default | Notes |
|--------|------|----------|---------|-------|
| id | uuid | NO | gen_random_uuid() | Primary key |
| snapshot_date | date | NO | - | Daily date |
| shopify_order_gid | text | YES | - | Shopify order GID |
| sku | text | YES | - | SKU identifier |
| returned_quantity | integer | NO | 0 | Returned units |
| return_amount | numeric(14,4) | NO | 0 | Return value |
| restock_fee | numeric(14,4) | YES | - | Restock fee |
| source_payload | jsonb | NO | '{}'::jsonb | Source data |
| created_at | timestamptz | NO | now() | Created time |

**Indexes**: `(sku, snapshot_date DESC)`, `(shopify_order_gid, snapshot_date DESC)`

**Code consumers**: `profit-forecast.ts`, `value-signal.ts` (return defaults when empty)

---

### attribution_confidence_daily [DEFER]

Daily attribution confidence by channel/campaign. Re-evaluate when bid-policy features are prioritized.

| Column | Type | Nullable | Default | Notes |
|--------|------|----------|---------|-------|
| id | uuid | NO | gen_random_uuid() | Primary key |
| snapshot_date | date | NO | - | Daily date |
| channel | text | NO | - | Channel |
| campaign_key | text | YES | - | Campaign identifier |
| confidence_score | numeric(10,6) | NO | 0 | Confidence score |
| quality_bucket | text | NO | 'unknown' | 'high', 'medium', 'low', 'unknown' |
| signals | jsonb | NO | '{}'::jsonb | Confidence signals |
| created_at | timestamptz | NO | now() | Created time |

**Unique Index**: `(snapshot_date, channel, COALESCE(campaign_key, '__all__'))`

**Check Constraints**: `quality_bucket IN ('high', 'medium', 'low', 'unknown')`

**Code consumers**: `bid-policy/route.ts` (uses default confidence when empty)

---

## Key Relationships

### Foreign Key Relationships

1. **batch_sku_assignments.batch_id** -> publish_batches(batch_id)
2. **publish_events.rollback_id** -> publish_events(id)
3. **performance_snapshots.publish_event_id** -> publish_events(id)
4. **performance_impact_scores.publish_event_id** -> publish_events(id) ON DELETE CASCADE
5. **search_queries.sync_job_id** -> search_query_sync_jobs(id)
6. **search_query_snapshots.publish_event_id** -> publish_events(id)
7. **batch_generation_job_skus.job_id** -> batch_generation_jobs(id)
8. **regeneration_history.generated_content_id** -> generated_content(id)
9. **competitor_listings.scrape_job_id** -> competitor_scrape_jobs(id)
10. **backfill_job_errors.job_id** -> backfill_jobs(id) ON DELETE CASCADE
11. **experiment_assignments.experiment_key** -> experiment_registry(experiment_key) ON DELETE CASCADE
12. **experiment_outcomes.experiment_key** -> experiment_registry(experiment_key) ON DELETE CASCADE

---

## Common Query Patterns

### Get Complete SKU Data
```sql
SELECT vi.master_sku, vi.gmc_offer_id, vi.finish, vi.finish_code,
       pc.title, pc.category, pc.narrative_copy,
       gc.candidate_content AS title_content, sa.approval_status
FROM variant_index vi
LEFT JOIN product_catalog pc ON vi.option_sku = pc.option_sku
LEFT JOIN generated_content gc ON vi.master_sku = gc.master_sku
  AND gc.platform = 'google' AND gc.content_type = 'title'
LEFT JOIN sku_approvals sa ON vi.master_sku = sa.master_sku
WHERE vi.master_sku = 'WP-2/16-GAL' LIMIT 1;
```

### Performance Delta Analysis
```sql
WITH baseline AS (
  SELECT master_sku, avg_impressions, avg_ctr
  FROM performance_baselines
  WHERE master_sku = 'WP-2/16-GAL' AND platform = 'google'
),
current_snap AS (
  SELECT master_sku, impressions, ctr
  FROM performance_snapshots
  WHERE master_sku = 'WP-2/16-GAL' AND platform = 'google'
    AND snapshot_date = CURRENT_DATE
)
SELECT b.master_sku,
       c.impressions - b.avg_impressions AS impression_delta,
       ((c.ctr - b.avg_ctr) / NULLIF(b.avg_ctr, 0)) * 100 AS ctr_pct_change
FROM baseline b JOIN current_snap c ON b.master_sku = c.master_sku;
```

### Get Approved Content for Publishing
```sql
SELECT gc.master_sku, gc.content_type, gc.approved_content, vfs.finish_sentences
FROM generated_content gc
LEFT JOIN variant_finish_sentences vfs
  ON gc.master_sku = vfs.master_sku AND gc.platform = vfs.platform
WHERE gc.master_sku = 'WP-2/16-GAL' AND gc.platform = 'google'
  AND gc.approved_content IS NOT NULL;
```

---

## Tier Scoring & Routing Tables

### routing_recommendations

Stores operator decisions on search term routing: approve/reject/undo tier changes, block wasted spend terms, and label-level category blocks.

| Column | Type | Constraints | Notes |
|--------|------|-------------|-------|
| id | uuid | PK, default gen_random_uuid() | |
| search_term | text | NOT NULL | For label blocks, uses sentinel `__LABEL_BLOCK__` |
| custom_label_0 | text | NOT NULL | Product category |
| recommended_action | text | NOT NULL, CHECK IN ('global_block', 'competitor', 'branded', 'funnel', 'label_block') | Action type |
| recommended_tier | text | CHECK IN (NULL, 'campaign_negative', 'high', 'medium', 'low') | Target tier (nullable) |
| reason_codes | text[] | NOT NULL, default '{}' | |
| confidence | numeric(5,4) | NOT NULL, default 0 | |
| review_status | text | NOT NULL, default 'pending', CHECK IN ('pending', 'accepted', 'rejected', 'expired') | |
| accepted | boolean | | |
| accepted_at | timestamptz | | |
| accepted_by | text | | |
| action_scope | text | NOT NULL, default 'term', CHECK IN ('term', 'label') | 'label' for category-level blocks |
| metadata | jsonb | NOT NULL, default '{}' | Stores currentTier, impact, append-only history array |
| created_at | timestamptz | NOT NULL, default now() | |

**Unique constraint:** `(search_term, custom_label_0)` — enables upsert for idempotent approve/reject/undo.

**Label blocks:** Use `search_term = '__LABEL_BLOCK__'` sentinel with `action_scope = 'label'` and `recommended_action = 'label_block'`. This blocks all terms under the given `custom_label_0` category.

**Indexes:**
- `idx_routing_recommendations_term_label_created` on `(search_term, custom_label_0, created_at DESC)`
- `idx_routing_recommendations_status_created` on `(review_status, created_at DESC)`

**Source:** Migrations 033b (original), 039 (upsert support), 040 (label scope)

---

### query_value_scores

Stores per-term scoring results from the tier scoring engine. Upserted by the `/api/shopping-funnel/tier-scoring` route on each computation.

| Column | Type | Constraints | Notes |
|--------|------|-------------|-------|
| id | uuid | PK, default gen_random_uuid() | |
| search_term | text | NOT NULL | |
| custom_label_0 | text | NOT NULL | Product category |
| score_version | text | NOT NULL, default 'v1' | Currently 'v2-tier-scoring' |
| expected_clicks | numeric(12,4) | NOT NULL, default 0 | Legacy field |
| expected_cvr | numeric(10,6) | NOT NULL, default 0 | Legacy field |
| expected_conversion_value | numeric(14,4) | NOT NULL, default 0 | Legacy field |
| expected_profit_proxy | numeric(14,4) | NOT NULL, default 0 | Legacy field |
| uncertainty | numeric(10,6) | NOT NULL, default 1 | `1 - confidence.score` |
| impact_score | numeric(14,4) | NOT NULL, default 0 | Monthly impact mid estimate |
| model_inputs | jsonb | NOT NULL, default '{}' | Stores confidence, fallbackLevel, currentTier, fitScoreDelta, dataConfirmed, isMisplaced |
| tier_fit_scores | jsonb | | Per-tier fit scores object |
| recommended_tier | text | CHECK IN (NULL, 'HIGH', 'MEDIUM', 'LOW') | Best-fit tier |
| net_monthly_impact | numeric(14,4) | | Monthly revenue impact estimate |
| scored_at | timestamptz | | When last scored |
| created_at | timestamptz | NOT NULL, default now() | |

**Unique index:** `(search_term, custom_label_0)` — enables upsert conflict resolution.

**Indexes:**
- `idx_query_value_scores_term_label_created` on `(search_term, custom_label_0, created_at DESC)`
- `idx_query_value_scores_impact_created` on `(impact_score DESC, created_at DESC)`
- `idx_query_value_scores_scored_at` on `(scored_at DESC NULLS LAST)`

**Source:** Migrations 033b (original), 037 (tier scoring columns), 038 (unique index)

---

### search_buildout_recommendations

Shopping-to-Search promotion candidates. Populated automatically by the tier scoring engine when it finds high-ROAS, high-volume, converting terms. Consumed by the Search Governance page (`/search-governance`).

| Column | Type | Notes |
|--------|------|-------|
| id | uuid | PK, auto-generated |
| search_term | text | NOT NULL, UNIQUE |
| custom_label_0 | text | Product category |
| recommended_search_tier | text | 'broad', 'phrase', or 'exact' |
| status | text | 'candidate', 'approved', 'applied', 'rejected', 'paused' |
| confidence | numeric(5,4) | 0-1 confidence score |
| metadata | jsonb | Source, ROAS, conversions, impressions |
| approved_by | text | Who approved |
| approved_at | timestamptz | When approved |
| created_at | timestamptz | When identified |

**Constraints:**
- `search_buildout_reco_term_unique` UNIQUE on `search_term`
- `search_buildout_reco_tier_check` CHECK tier in ('broad', 'phrase', 'exact')
- `search_buildout_reco_status_check` CHECK status in ('candidate', 'approved', 'applied', 'rejected', 'paused')

**Indexes:**
- `idx_search_buildout_recommendations_status_created` on `(status, created_at DESC)`
- `idx_search_buildout_recommendations_term` on `(search_term, created_at DESC)`

**Source:** Migration 041

---

*Schema last rebuilt: 2026-02-25 (Phase 31-01), updated 2026-02-26 (Phase 34.1-03, migration 041)*
*Source: Migration SQL files cross-referenced with production state*
*Total tables: 57 (39 core + 4 GA4 KEEP + 10 intent KEEP + 4 DEFER)*
