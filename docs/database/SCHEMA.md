# Allied-FeedOps Database Schema

**Supabase Project ID**: `qezuszwufortkiutlhym`

This document provides a comprehensive reference for all database tables, columns, constraints, and common query patterns.

---

## Table of Contents

1. [Core Content Tables](#core-content-tables)
   - [generated_content](#generated_content)
   - [sku_approvals](#sku_approvals)
   - [variant_approvals](#variant_approvals)
   - [variant_finish_sentences](#variant_finish_sentences)
2. [Publishing Tables](#publishing-tables)
   - [publish_batches](#publish_batches)
   - [batch_sku_assignments](#batch_sku_assignments)
   - [publish_events](#publish_events)
3. [Product Data Tables](#product-data-tables)
   - [variant_index](#variant_index)
   - [product_catalog](#product_catalog)
4. [Performance Tracking Tables](#performance-tracking-tables)
   - [performance_baselines](#performance_baselines)
   - [performance_snapshots](#performance_snapshots)
   - [performance_impact_scores](#performance_impact_scores)
5. [Search & Keyword Tables](#search--keyword-tables)
   - [search_queries](#search_queries)
   - [search_queries_by_master_sku](#search_queries_by_master_sku)
   - [keyword_metrics](#keyword_metrics)
   - [search_query_snapshots](#search_query_snapshots)
   - [search_query_sync_jobs](#search_query_sync_jobs)
   - [keyword_coverage_master](#keyword_coverage_master)
   - [keyword_coverage_variant](#keyword_coverage_variant)
   - [finish_search_patterns](#finish_search_patterns)
6. [Image Tables](#image-tables)
   - [product_lifestyle_images](#product_lifestyle_images)
   - [variant_lifestyle_images](#variant_lifestyle_images)
   - [lifestyle_image_selections](#lifestyle_image_selections)
7. [Content Generation Tables](#content-generation-tables)
   - [regeneration_history](#regeneration_history)
   - [prompt_version_aliases](#prompt_version_aliases)
   - [prompt_templates](#prompt_templates)
   - [batch_generation_jobs](#batch_generation_jobs)
   - [batch_generation_job_skus](#batch_generation_job_skus)
   - [generation_jobs](#generation_jobs)
8. [Measurement & Classification Tables](#measurement--classification-tables)
   - [sku_bottleneck_classifications](#sku_bottleneck_classifications)
   - [gmc_product_status](#gmc_product_status)
9. [Competitor Intelligence Tables](#competitor-intelligence-tables)
   - [competitor_listings](#competitor_listings)
   - [competitor_patterns](#competitor_patterns)
   - [competitor_scrape_jobs](#competitor_scrape_jobs)
10. [Support Tables](#support-tables)
   - [shopify_products](#shopify_products)
11. [Backfill Infrastructure Tables](#backfill-infrastructure-tables)
   - [backfill_jobs](#backfill_jobs)
   - [backfill_job_errors](#backfill_job_errors)
11. [Optimization & Intent Control Tables](#optimization--intent-control-tables)
   - [intent_taxonomy_versions](#intent_taxonomy_versions)
   - [term_intent_state](#term_intent_state)
   - [policy_decision_log](#policy_decision_log)
   - [policy_action_execution_log](#policy_action_execution_log)
   - [policy_snapshots](#policy_snapshots)
   - [sku_margin_daily](#sku_margin_daily)
   - [order_line_returns_daily](#order_line_returns_daily)
   - [attribution_confidence_daily](#attribution_confidence_daily)
   - [experiment_registry](#experiment_registry)
   - [experiment_assignments](#experiment_assignments)
   - [experiment_outcomes](#experiment_outcomes)
   - [negative_registry](#negative_registry)
   - [search_buildout_recommendations](#search_buildout_recommendations)
   - [operator_review_audit](#operator_review_audit)

---

## Core Content Tables

### generated_content

Stores generated titles and descriptions for master SKUs across platforms. This is the single source of truth for content state.

**Columns**:
| Column | Type | Nullable | Default | Description |
|--------|------|----------|---------|-------------|
| id | uuid | NO | gen_random_uuid() | Primary key |
| master_sku | text | NO | - | Master SKU identifier (e.g., "WP-2/16-GAL") |
| platform | text | NO | - | Platform ("google", "bing", "shopify") |
| content_type | text | NO | - | Type ("title", "description") |
| baseline_content | text | YES | - | Original content before optimization |
| candidate_content | text | YES | - | AI-generated candidate content |
| approved_content | text | YES | - | User-approved content (immutable) |
| approved_at | timestamp with time zone | YES | - | Timestamp of approval |
| approved_version | integer | YES | - | Version number at approval |
| quality_score | numeric | YES | - | AI quality score (0-100) |
| quality_breakdown | jsonb | YES | - | Detailed scoring breakdown |
| generation_model | text | YES | - | Model used (e.g., "gpt-4") |
| generation_prompt_hash | text | YES | - | Hash of prompt used |
| generation_timestamp | timestamp with time zone | YES | - | When content was generated |
| version | integer | YES | 1 | Content version number |
| is_current | boolean | YES | true | Is this the current version |
| created_at | timestamp with time zone | NO | now() | Record creation time |
| updated_at | timestamp with time zone | NO | now() | Last update time |

**Primary Key**: `id`

**Unique Constraint**: `(master_sku, platform, content_type)`

**Indexes**:
- `idx_content_sku` on `master_sku`
- `idx_content_platform` on `platform`
- `idx_content_score` on `quality_score DESC NULLS LAST`
- `idx_content_current` on `(master_sku, platform, content_type) WHERE is_current = true`
- `idx_generated_content_approved` on `(master_sku, platform, content_type) WHERE approved_content IS NOT NULL`

**Common Queries**:
```sql
-- Get approved content for publishing
SELECT master_sku, content_type, approved_content
FROM generated_content
WHERE master_sku = 'WP-2/16-GAL'
  AND platform = 'google'
  AND approved_content IS NOT NULL;

-- Get candidate content for review
SELECT master_sku, content_type, candidate_content, quality_score
FROM generated_content
WHERE master_sku = 'WP-2/16-GAL'
  AND platform = 'google';
```

---

### sku_approvals

Tracks approval status for master SKUs. Controls whether content is ready for publishing.

**Columns**:
| Column | Type | Nullable | Default | Description |
|--------|------|----------|---------|-------------|
| master_sku | text | NO | - | Primary key: Master SKU identifier |
| approval_status | text | NO | 'pending' | Status: 'pending', 'approved', 'rejected' |
| title_approved | boolean | YES | - | Title approval flag |
| description_approved | boolean | YES | - | Description approval flag |
| image_approved | boolean | YES | - | Image approval flag |
| selected_finish | text | YES | - | User-selected finish for hero image |
| selected_image_index | integer | YES | - | User-selected image index |
| approved_by | text | YES | - | User who approved |
| approved_at | timestamp with time zone | YES | - | Approval timestamp |
| notes | text | YES | - | Approval notes |
| created_at | timestamp with time zone | NO | now() | Record creation time |
| updated_at | timestamp with time zone | NO | now() | Last update time |
| id | bigint | NO | nextval() | Serial ID |

**Primary Key**: `master_sku`

**Indexes**:
- `idx_sku_approvals_status` on `approval_status`

**Check Constraints**:
- `approval_status IN ('pending', 'approved', 'rejected')`

**Common Queries**:
```sql
-- Get approved SKUs ready for batch
SELECT master_sku
FROM sku_approvals
WHERE approval_status = 'approved';

-- Check approval details
SELECT master_sku, title_approved, description_approved, image_approved, approved_by
FROM sku_approvals
WHERE master_sku = 'WP-2/16-GAL';
```

---

### variant_approvals

Tracks approval status for individual finish variants. Used for variant-level content review.

**Columns**:
| Column | Type | Nullable | Default | Description |
|--------|------|----------|---------|-------------|
| id | bigint | NO | nextval() | Primary key |
| master_sku | text | NO | - | Master SKU identifier |
| finish | text | NO | - | Full finish name |
| finish_code | text | YES | - | Short finish code (e.g., "BKM") |
| title_approved | boolean | YES | - | Title approval flag |
| description_approved | boolean | YES | - | Description approval flag |
| image_approved | boolean | YES | - | Image approval flag |
| selected_image_index | integer | YES | - | User-selected image index |
| approval_status | text | NO | 'pending' | Overall approval status |
| notes | text | YES | - | Approval notes |
| approved_by | text | YES | - | User who approved |
| approved_at | timestamp with time zone | YES | - | Approval timestamp |
| created_at | timestamp with time zone | NO | now() | Record creation time |
| updated_at | timestamp with time zone | NO | now() | Last update time |

**Primary Key**: `id`

**Unique Constraint**: `(master_sku, finish)`

**Common Queries**:
```sql
-- Get variant approvals for a SKU
SELECT master_sku, finish, approval_status, approved_at
FROM variant_approvals
WHERE master_sku = 'WP-2/16-GAL'
ORDER BY finish;
```

---

### variant_finish_sentences

Stores finish-specific sentences used to generate variant content. Maps `{FINISH_NAME}` placeholders.

**Columns**:
| Column | Type | Nullable | Default | Description |
|--------|------|----------|---------|-------------|
| id | uuid | NO | gen_random_uuid() | Primary key |
| master_sku | text | NO | - | Master SKU identifier |
| platform | text | NO | - | Platform ("google", "bing") |
| finish_sentences | jsonb | NO | - | Map of finish_code → sentence |
| created_at | timestamp with time zone | NO | now() | Record creation time |
| updated_at | timestamp with time zone | NO | now() | Last update time |

**Primary Key**: `id`

**Unique Constraint**: `(master_sku, platform)`

**Indexes**:
- `idx_variant_finish_sentences_sku` on `master_sku`

**Check Constraints**:
- `platform IN ('google', 'bing')`

**JSONB Structure**:
```json
{
  "BKM": "in Black Matte finish",
  "BBR": "in Brushed Bronze finish",
  "ORB": "in Oil-Rubbed Bronze finish"
}
```

**Common Queries**:
```sql
-- Get finish sentences for expansion
SELECT finish_sentences
FROM variant_finish_sentences
WHERE master_sku = 'WP-2/16-GAL' AND platform = 'google';
```

---

## Publishing Tables

### publish_batches

Manages batch publishing operations. Groups SKUs for coordinated publishing.

**Columns**:
| Column | Type | Nullable | Default | Description |
|--------|------|----------|---------|-------------|
| batch_id | text | NO | - | Primary key: Unique batch ID |
| name | text | YES | - | User-friendly batch name |
| status | text | NO | 'pending' | Batch status |
| target_date | text | YES | - | Target publish date |
| sku_count | integer | YES | 0 | Number of SKUs in batch |
| success_count | integer | YES | 0 | Successfully published SKUs |
| failed_count | integer | YES | 0 | Failed SKUs |
| notes | text | YES | - | Batch notes |
| created_at | timestamp with time zone | NO | now() | Batch creation time |
| executed_at | timestamp with time zone | YES | - | Execution timestamp |
| id | bigint | NO | nextval() | Serial ID |

**Primary Key**: `batch_id`

**Check Constraints**:
- `status IN ('draft', 'pending', 'executing', 'published', 'partial', 'failed')`

**Common Queries**:
```sql
-- Get active batches
SELECT batch_id, name, status, sku_count, created_at
FROM publish_batches
WHERE status IN ('draft', 'pending')
ORDER BY created_at DESC;
```

---

### batch_sku_assignments

Links SKUs to publish batches. Many-to-one relationship.

**Columns**:
| Column | Type | Nullable | Default | Description |
|--------|------|----------|---------|-------------|
| id | integer | NO | nextval() | Primary key |
| batch_id | text | NO | - | Foreign key to publish_batches |
| master_sku | text | NO | - | Master SKU identifier |
| created_at | timestamp with time zone | NO | now() | Assignment timestamp |

**Primary Key**: `id`

**Unique Constraint**: `(batch_id, master_sku)`

**Indexes**:
- `idx_batch_assignments_sku` on `master_sku`

**Common Queries**:
```sql
-- Get all SKUs in a batch
SELECT master_sku
FROM batch_sku_assignments
WHERE batch_id = 'batch_2024_01_15';

-- Check if SKU is in any batch
SELECT batch_id
FROM batch_sku_assignments
WHERE master_sku = 'WP-2/16-GAL';
```

---

### publish_events

Audit log for all publishing operations. Stores content snapshots for rollback capability.

**Columns**:
| Column | Type | Nullable | Default | Description |
|--------|------|----------|---------|-------------|
| id | integer | NO | nextval() | Primary key |
| master_sku | text | NO | - | Master SKU identifier |
| platform | text | NO | - | Platform ("google", "bing", "shopify") |
| environment | text | NO | - | Environment ("staging", "production") |
| action | text | NO | 'publish' | Action type |
| status | text | NO | - | Event status ("success", "failed", "pending") |
| batch_id | text | YES | - | Associated batch ID |
| patch_file | text | YES | - | Path to patch file |
| published_title | text | YES | - | Snapshot: published title |
| published_description | text | YES | - | Snapshot: published description |
| variant_count | integer | YES | - | Number of variants expanded |
| content_version | integer | YES | - | Content version at publish |
| quality_score | real | YES | - | Quality score at publish |
| product_category | text | YES | - | Product category |
| product_collection | text | YES | - | Product collection |
| approval_status | text | YES | - | Approval status at publish |
| published_by | text | YES | - | User who published |
| rollback_id | bigint | YES | - | ID of event being rolled back |
| error_message | text | YES | - | Error details if failed |
| published_at | timestamp with time zone | NO | now() | Publish timestamp |
| final_payload_snapshot | jsonb | YES | - | Post-expansion channel-ready payload snapshot for audit/debug (migration 033) |
| final_payload_hash | text | YES | - | SHA-256 of canonicalized final_payload_snapshot JSON (migration 034) |
| prompt_hash | text | YES | - | Prompt identity hash for generation lineage tracking (migration 034) |
| evidence_hash | text | YES | - | SHA-256 of canonicalized evidence input at publish time (migration 034) |
| segment_key | text | YES | - | Normalized custom_label_0 segment key, lowercased with collapsed whitespace (migration 034) |

**Primary Key**: `id`

**Indexes**:
- `idx_publish_events_sku` on `master_sku`
- `idx_publish_events_published_at` on `published_at DESC`
- `idx_publish_events_platform_env` on `(platform, environment)`
- `idx_publish_events_final_payload_hash` on `final_payload_hash` (migration 034)
- `idx_publish_events_prompt_hash` on `prompt_hash` (migration 034)
- `idx_publish_events_segment_key` on `segment_key` (migration 034)

**Check Constraints**:
- `environment IN ('staging', 'production')`
- `status IN ('success', 'failed', 'pending')`

**Common Queries**:
```sql
-- Get publish history for SKU
SELECT published_at, platform, status, published_title
FROM publish_events
WHERE master_sku = 'WP-2/16-GAL'
ORDER BY published_at DESC;

-- Get rollback snapshot
SELECT published_title, published_description, content_version
FROM publish_events
WHERE id = 12345;

-- Get prompt lineage for published SKU (migration 034)
SELECT id, published_at, prompt_hash, evidence_hash, segment_key
FROM publish_events
WHERE master_sku = 'WP-2/16-GAL'
  AND platform = 'google'
  AND prompt_hash IS NOT NULL
ORDER BY published_at DESC LIMIT 5;
```

---

## Product Data Tables

### variant_index

**THE SOURCE OF TRUTH** for master_sku ↔ gmc_offer_id mapping. Essential for all product queries.

**Columns**:
| Column | Type | Nullable | Default | Description |
|--------|------|----------|---------|-------------|
| id | bigint | NO | nextval() | Primary key |
| gmc_offer_id | text | NO | - | Unique GMC offer ID (format: `shopify_us_{product_id}_{variant_id}`) |
| master_sku | text | NO | - | Master SKU identifier |
| option_sku | text | YES | - | Option SKU (unique per variant) |
| shopify_product_id | text | YES | - | Shopify product ID |
| shopify_variant_id | text | YES | - | Shopify variant ID |
| finish | text | YES | - | Full finish name |
| finish_code | text | YES | - | Short finish code |
| dimensions | text | YES | - | Product dimensions |
| product_title | text | YES | - | Product title |
| product_category | text | YES | - | Product category |
| created_at | timestamp with time zone | NO | now() | Record creation time |
| updated_at | timestamp with time zone | NO | now() | Last update time |

**Primary Key**: `id`

**Unique Constraints**:
- `gmc_offer_id` (unique index)
- `option_sku` (unique index: `idx_variant_index_option_sku`)

**Indexes**:
- `idx_variant_master_sku` on `master_sku`
- `idx_variant_shopify` on `shopify_product_id`

**Critical Notes**:
- GMC offer IDs use **lowercase** "us": `shopify_us_123_456` (not uppercase "US")
- Multiple master_skus can share the same product_id (e.g., DMF-2/2X, DMF-2/3X)
- 72,023 total rows

**Common Queries**:
```sql
-- Get all variants for a master SKU
SELECT gmc_offer_id, finish, finish_code, shopify_variant_id
FROM variant_index
WHERE master_sku = 'WP-2/16-GAL';

-- Reverse lookup: get master SKU from GMC offer ID
SELECT master_sku, finish, finish_code
FROM variant_index
WHERE gmc_offer_id = 'shopify_us_4539975336068_12345678';

-- Get all master SKUs for a Shopify product (multi-SKU products)
SELECT DISTINCT master_sku
FROM variant_index
WHERE shopify_product_id = '4539975336068';
```

---

### product_catalog

Comprehensive product data including specs, dimensions, images, and narrative copy. 75,770 variants.

**Columns**:
| Column | Type | Nullable | Default | Description |
|--------|------|----------|---------|-------------|
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
| bullet_1 | text | YES | - | Feature bullet 1 |
| bullet_2 | text | YES | - | Feature bullet 2 |
| bullet_3 | text | YES | - | Feature bullet 3 |
| bullet_4 | text | YES | - | Feature bullet 4 |
| bullet_5 | text | YES | - | Feature bullet 5 |
| bullet_6 | text | YES | - | Feature bullet 6 |
| product_length | numeric | YES | - | Length in inches |
| product_height | numeric | YES | - | Height in inches |
| product_width | numeric | YES | - | Width in inches |
| projection | numeric | YES | - | Projection in inches |
| product_weight | numeric | YES | - | Weight in lbs |
| box_length | numeric | YES | - | Box length |
| box_height | numeric | YES | - | Box height |
| box_width | numeric | YES | - | Box width |
| box_weight | numeric | YES | - | Box weight |
| center_to_center | numeric | YES | - | Center-to-center measurement |
| diameter | numeric | YES | - | Diameter in inches |
| screw_size | text | YES | - | Screw size |
| mirror_height | numeric | YES | - | Mirror height |
| mirror_width | numeric | YES | - | Mirror width |
| thickness | numeric | YES | - | Thickness |
| weight_capacity | numeric | YES | - | Weight capacity in lbs |
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
| alt_image_1 | text | YES | - | Alt image 1 URL |
| alt_image_2 | text | YES | - | Alt image 2 URL |
| alt_image_3 | text | YES | - | Alt image 3 URL |
| alt_image_4 | text | YES | - | Alt image 4 URL |
| created_at | timestamp with time zone | NO | now() | Record creation time |
| updated_at | timestamp with time zone | NO | now() | Last update time |

**Primary Key**: `id`

**Unique Constraint**: `option_sku`

**Indexes**:
- `idx_product_catalog_master_sku` on `master_sku`
- `idx_product_catalog_finish` on `(master_sku, finish_code)`
- `idx_product_catalog_category` on `category`
- `idx_product_catalog_collection` on `collection`
- `idx_product_catalog_gmc_id` on `gmc_id`
- `idx_product_catalog_narrative_fts` on `to_tsvector('english', COALESCE(narrative_copy, ''))`

**Common Queries**:
```sql
-- Get product data for evidence building
SELECT
    master_sku,
    title,
    narrative_copy,
    category,
    material,
    style,
    product_length,
    product_height,
    product_width
FROM product_catalog
WHERE master_sku = 'WP-2/16-GAL'
LIMIT 1;

-- Get all variants for a master SKU
SELECT option_sku, finish_name, finish_code, main_image_url
FROM product_catalog
WHERE master_sku = 'WP-2/16-GAL'
ORDER BY position;

-- Full-text search on narrative copy
SELECT master_sku, title, category
FROM product_catalog
WHERE to_tsvector('english', COALESCE(narrative_copy, '')) @@ to_tsquery('english', 'bathroom & towel');
```

---

## Performance Tracking Tables

### performance_baselines

Stores 30-day pre-optimization performance metrics. Used to measure improvement.

**Columns**:
| Column | Type | Nullable | Default | Description |
|--------|------|----------|---------|-------------|
| master_sku | text | NO | - | Master SKU identifier |
| platform | text | NO | - | Platform ("google", "bing") |
| baseline_start_date | date | NO | - | Start date |
| baseline_end_date | date | NO | - | End date |
| avg_impressions | real | YES | - | Average daily impressions |
| avg_clicks | real | YES | - | Average daily clicks |
| avg_ctr | real | YES | - | Average CTR (0-1) |
| avg_conversions | real | YES | - | Average daily conversions |
| avg_conversion_value | numeric(18,6) | YES | - | Average daily conversion value |
| avg_cvr | real | YES | - | Average CVR (0-1) |
| avg_cost | numeric(18,6) | YES | - | Average daily cost |
| avg_roas | real | YES | - | Average ROAS |
| metadata | jsonb | YES | '{}'::jsonb | Baseline metadata flags (multi-SKU family, etc.) |
| created_at | timestamp with time zone | NO | now() | Baseline capture time |

**Primary Key**: `(master_sku, platform)`

**Critical Notes**:
- Baselines are typically 30-day lookback from publish date
- Auto-captured by SKU selection and regeneration APIs
- Stale threshold: 60 days (triggers re-capture)

**Common Queries**:
```sql
-- Get baseline for comparison
SELECT
    avg_impressions,
    avg_clicks,
    avg_ctr,
    avg_conversions
FROM performance_baselines
WHERE master_sku = 'WP-2/16-GAL' AND platform = 'google';

-- Check if baseline exists and is fresh
SELECT
    master_sku,
    EXTRACT(EPOCH FROM (NOW() - created_at)) / 86400 AS days_old
FROM performance_baselines
WHERE master_sku = 'WP-2/16-GAL'
  AND platform = 'google'
  AND created_at > NOW() - INTERVAL '60 days';
```

---

### performance_snapshots

Daily fact table for post-publish shopping performance. This is the source of truth
for impact analysis and powers difference-in-differences scorecards.

**Columns**:
| Column | Type | Nullable | Default | Description |
|--------|------|----------|---------|-------------|
| id | bigint | NO | nextval() | Primary key |
| master_sku | text | NO | - | Master SKU identifier |
| platform | text | NO | - | Platform ("google", "bing") |
| environment | text | NO | - | Environment ("staging", "production") |
| snapshot_date | date | NO | - | Daily snapshot date |
| impressions | integer | YES | 0 | Total impressions |
| clicks | integer | YES | 0 | Total clicks |
| ctr | real | YES | 0.0 | Click-through rate |
| conversions | integer | YES | 0 | Total conversions |
| conversion_value | numeric(18,6) | YES | 0.0 | Total conversion value |
| cvr | real | YES | 0.0 | Conversion rate |
| cost | numeric(18,6) | YES | 0.0 | Total cost |
| cpc | numeric(18,6) | YES | 0.0 | Cost per click |
| roas | real | YES | 0.0 | Return on ad spend |
| publish_event_id | bigint | YES | - | Foreign key to publish_events |
| content_version | text | YES | - | Content version at snapshot |
| days_since_publish | integer | YES | - | Days elapsed since publish |
| cohort_type | text | YES | - | Treated/control cohort label |
| product_category | text | YES | - | Category used for control matching |
| fetched_at | timestamp with time zone | NO | now() | Data fetch timestamp |

**Primary Key**: `id`

**Unique Constraint**:
- `uq_performance_snapshots_daily` on `(master_sku, platform, environment, snapshot_date)`

**Indexes**:
- `idx_snapshots_sku_platform_date` on `(master_sku, platform, snapshot_date DESC)`
- `idx_performance_snapshots_snapshot_date` on `snapshot_date DESC`
- `idx_performance_snapshots_platform_snapshot_date` on `(platform, snapshot_date DESC)`
- `idx_performance_snapshots_publish_event` on `publish_event_id`
- `idx_performance_snapshots_cohort_date` on `(cohort_type, snapshot_date DESC)`

**Check Constraints**:
- `chk_performance_snapshots_cohort_type` ensures `cohort_type IN ('treated', 'control')`

**Common Queries**:
```sql
-- Get daily trend for one SKU
SELECT
    snapshot_date,
    days_since_publish,
    impressions,
    clicks,
    ctr
FROM performance_snapshots
WHERE master_sku = 'WP-2/16-GAL'
  AND platform = 'google'
ORDER BY snapshot_date DESC
LIMIT 30;

-- Latest available snapshot date (staleness indicator)
SELECT snapshot_date
FROM performance_snapshots
WHERE platform = 'google' AND environment = 'production'
ORDER BY snapshot_date DESC
LIMIT 1;
```

---

### performance_impact_scores

Persisted difference-in-differences scorecards by publish event and metric.
This table is populated by the impact computation job and read directly by dashboard APIs.

**Columns**:
| Column | Type | Nullable | Default | Description |
|--------|------|----------|---------|-------------|
| id | bigint | NO | nextval() | Primary key |
| publish_event_id | bigint | NO | - | Foreign key to publish_events |
| master_sku | text | NO | - | Master SKU identifier |
| platform | text | NO | - | Platform ("google") |
| environment | text | NO | - | Environment ("production"/"staging") |
| metric_name | text | NO | - | Metric key (`roas`, `cvr`, `ctr`, `clicks`, `conversions`, `cost`, `conversion_value`, `impressions`) |
| pre_value | numeric(18,8) | YES | - | Treated pre-window mean |
| post_value | numeric(18,8) | YES | - | Treated post-window mean |
| control_pre | numeric(18,8) | YES | - | Control pre-window mean |
| control_post | numeric(18,8) | YES | - | Control post-window mean |
| did_lift_pct | numeric(18,8) | YES | - | Diff-in-diff lift percentage |
| label | text | NO | - | Overall classification (`positive`, `negative`, `neutral`) |
| confidence | numeric(6,4) | NO | 0 | Confidence score (0-1) |
| sample_size_treated | integer | NO | 0 | Treated sample size |
| sample_size_control | integer | NO | 0 | Control sample size |
| window_pre_days | integer | NO | 30 | Pre window length |
| window_post_days | integer | NO | 30 | Post window length |
| run_date | date | NO | - | Job run date |
| computed_at | timestamp with time zone | NO | now() | Computation timestamp |

**Primary Key**: `id`

**Unique Constraint**:
- `(publish_event_id, metric_name, platform, environment)`

**Indexes**:
- `idx_performance_impact_scores_publish_event` on `publish_event_id`
- `idx_performance_impact_scores_master_sku` on `master_sku`
- `idx_performance_impact_scores_run_date` on `run_date DESC`
- `idx_performance_impact_scores_metric` on `metric_name`
- `idx_performance_impact_scores_label` on `label`

**Check Constraints**:
- `chk_performance_impact_scores_label` ensures `label IN ('positive', 'negative', 'neutral')`

**Common Queries**:
```sql
-- Scorecard metrics for a publish event
SELECT metric_name, did_lift_pct, label, confidence
FROM performance_impact_scores
WHERE publish_event_id = 12345
ORDER BY metric_name;

-- Latest ROAS impact by SKU
SELECT master_sku, publish_event_id, did_lift_pct, label, confidence, computed_at
FROM performance_impact_scores
WHERE metric_name = 'roas'
  AND platform = 'google'
  AND environment = 'production'
ORDER BY computed_at DESC
LIMIT 100;
```

---

## Search & Keyword Tables

### search_queries

Variant-level Google Ads search terms data. Enriched with Keyword Planner metrics.

**Columns**:
| Column | Type | Nullable | Default | Description |
|--------|------|----------|---------|-------------|
| id | uuid | NO | gen_random_uuid() | Primary key |
| query_text | text | NO | - | Search query text |
| gmc_offer_id | text | YES | - | GMC offer ID |
| master_sku | text | YES | - | Master SKU (denormalized from variant_index) |
| finish | text | YES | - | Finish name (denormalized) |
| finish_code | text | YES | - | Finish code (denormalized) |
| shopify_variant_id | text | YES | - | Shopify variant ID |
| campaign_id | text | YES | - | Google Ads campaign ID |
| ad_group_id | text | YES | - | Google Ads ad group ID |
| item_ids | jsonb | YES | - | Array of GMC item IDs (for multi-product ads) |
| impressions | integer | YES | 0 | Total impressions |
| clicks | integer | YES | 0 | Total clicks |
| conversions | numeric | YES | 0 | Total conversions |
| conversion_value | numeric | YES | 0 | Total conversion value |
| cost_micros | bigint | YES | 0 | Total cost in micros |
| ctr | numeric | YES | - | Click-through rate |
| cvr | numeric | YES | - | Conversion rate |
| avg_monthly_searches | integer | YES | - | Keyword Planner: avg monthly searches |
| competition | text | YES | - | Keyword Planner: competition level |
| competition_index | integer | YES | - | Keyword Planner: competition index (0-100) |
| low_cpc_micros | bigint | YES | - | Keyword Planner: low CPC bid |
| high_cpc_micros | bigint | YES | - | Keyword Planner: high CPC bid |
| keyword_metrics_updated_at | timestamp with time zone | YES | - | Last keyword enrichment |
| period_start | date | NO | - | Query period start date |
| period_end | date | NO | - | Query period end date |
| fetched_at | timestamp with time zone | YES | now() | Data fetch timestamp |
| synced_at | timestamp with time zone | YES | - | Timestamp of last sync with corrected Phase 13 logic; NULL = pre-fix data |
| sync_job_id | uuid | YES | - | Foreign key to search_query_sync_jobs |

**Primary Key**: `id`

**Unique Constraint**: `(query_text, gmc_offer_id, period_start, period_end)`

**Indexes**:
- `idx_search_queries_master_sku` on `master_sku`
- `idx_search_queries_gmc` on `gmc_offer_id`
- `idx_search_queries_finish` on `finish_code`
- `idx_search_queries_impressions` on `impressions DESC`
- `idx_search_queries_period` on `(period_start, period_end)`
- `idx_search_queries_sync_job` on `sync_job_id`
- `idx_search_queries_ad_group_id` on `ad_group_id`
- `idx_search_queries_synced_at` on `synced_at`

**Check Constraints**:
- `competition IN ('LOW', 'MEDIUM', 'HIGH', 'UNSPECIFIED', NULL)`
- `competition_index BETWEEN 0 AND 100 OR NULL`

**Common Queries**:
```sql
-- Get top queries for a master SKU
SELECT
    query_text,
    impressions,
    clicks,
    avg_monthly_searches,
    competition
FROM search_queries
WHERE master_sku = 'WP-2/16-GAL'
ORDER BY impressions DESC
LIMIT 20;

-- Get high-volume queries missing from title
SELECT
    sq.query_text,
    sq.impressions,
    sq.avg_monthly_searches
FROM search_queries sq
LEFT JOIN generated_content gc
    ON sq.master_sku = gc.master_sku
    AND gc.platform = 'google'
    AND gc.content_type = 'title'
WHERE sq.master_sku = 'WP-2/16-GAL'
  AND sq.avg_monthly_searches > 100
  AND gc.candidate_content NOT ILIKE '%' || sq.query_text || '%'
ORDER BY sq.impressions DESC;
```

---

### search_queries_by_master_sku

Aggregated search query data at the master SKU level. Rolls up variant-level data.

**Columns**:
| Column | Type | Nullable | Default | Description |
|--------|------|----------|---------|-------------|
| id | uuid | NO | gen_random_uuid() | Primary key |
| master_sku | text | NO | - | Master SKU identifier |
| query_text | text | NO | - | Search query text |
| total_impressions | integer | YES | 0 | Sum of impressions across variants |
| total_clicks | integer | YES | 0 | Sum of clicks across variants |
| total_conversions | numeric | YES | 0 | Sum of conversions |
| total_conversion_value | numeric | YES | 0 | Sum of conversion value |
| variant_count | integer | YES | 1 | Number of variants with this query |
| top_variant_finish | text | YES | - | Finish with most impressions |
| top_variant_finish_code | text | YES | - | Finish code of top variant |
| avg_monthly_searches | integer | YES | - | Keyword Planner data |
| competition | text | YES | - | Keyword Planner data |
| competition_index | integer | YES | - | Keyword Planner data |
| period_start | date | NO | - | Query period start |
| period_end | date | NO | - | Query period end |
| updated_at | timestamp with time zone | YES | now() | Last update time |

**Primary Key**: `id`

**Unique Constraint**: `(master_sku, query_text, period_start, period_end)`

**Indexes**:
- `idx_search_queries_by_master_sku` on `master_sku`
- `idx_search_queries_by_master_sku_impressions` on `total_impressions DESC`

**Common Queries**:
```sql
-- Get aggregated queries for master SKU
SELECT
    query_text,
    total_impressions,
    total_clicks,
    variant_count,
    top_variant_finish
FROM search_queries_by_master_sku
WHERE master_sku = 'WP-2/16-GAL'
ORDER BY total_impressions DESC
LIMIT 20;
```

---

### keyword_metrics

Cached Google Ads Keyword Planner data. 30-day TTL for reuse across queries.

**Columns**:
| Column | Type | Nullable | Default | Description |
|--------|------|----------|---------|-------------|
| keyword | text | NO | - | Primary key: keyword text |
| avg_monthly_searches | integer | YES | - | 12-month average searches |
| competition | text | YES | - | Competition level |
| competition_index | integer | YES | - | Competition index (0-100) |
| low_cpc_micros | bigint | YES | - | 20th percentile CPC bid |
| high_cpc_micros | bigint | YES | - | 80th percentile CPC bid |
| monthly_searches | jsonb | YES | - | Per-month breakdown |
| updated_at | timestamp with time zone | YES | now() | Last update time |

**Primary Key**: `keyword`

**Check Constraints**:
- `competition IN ('LOW', 'MEDIUM', 'HIGH', 'UNSPECIFIED')`
- `competition_index BETWEEN 0 AND 100 OR NULL`

**Common Queries**:
```sql
-- Get cached keyword data
SELECT
    keyword,
    avg_monthly_searches,
    competition,
    competition_index
FROM keyword_metrics
WHERE keyword IN ('bathroom towel bar', 'towel rack', 'wall mount towel holder');

-- Check if data is stale (>30 days)
SELECT keyword, updated_at
FROM keyword_metrics
WHERE keyword = 'bathroom towel bar'
  AND updated_at < NOW() - INTERVAL '30 days';
```

---

### search_query_snapshots

Timestamped snapshots of search query performance. Enables delta tracking after publish.

**Columns**:
| Column | Type | Nullable | Default | Description |
|--------|------|----------|---------|-------------|
| id | uuid | NO | gen_random_uuid() | Primary key |
| query_text | text | NO | - | Search query text |
| master_sku | text | NO | - | Master SKU identifier |
| gmc_offer_id | text | YES | - | GMC offer ID |
| finish | text | YES | - | Finish name |
| finish_code | text | YES | - | Finish code |
| impressions | integer | YES | 0 | Impressions in period |
| clicks | integer | YES | 0 | Clicks in period |
| conversions | numeric | YES | 0 | Conversions in period |
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
| publish_event_id | bigint | YES | - | Foreign key to publish_events |
| content_version | integer | YES | - | Content version at snapshot |
| period_start | date | NO | - | Query period start |
| period_end | date | NO | - | Query period end |
| fetched_at | timestamp with time zone | YES | now() | Data fetch time |

**Primary Key**: `id`

**Unique Constraint**: `(query_text, master_sku, snapshot_date)` (index: `search_query_snapshots_unique`)

**Indexes**:
- `idx_search_query_snapshots_master_sku` on `master_sku`
- `idx_search_query_snapshots_query_text` on `query_text`
- `idx_search_query_snapshots_snapshot_date` on `snapshot_date DESC`
- `idx_search_query_snapshots_publish_event_id` on `publish_event_id`

**Common Queries**:
```sql
-- Get query delta after publish
SELECT
    query_text,
    snapshot_date,
    days_since_publish,
    impressions,
    clicks
FROM search_query_snapshots
WHERE master_sku = 'WP-2/16-GAL'
  AND publish_event_id = 12345
ORDER BY snapshot_date;
```

---

### search_query_sync_jobs

Tracks search query data collection jobs. Manages sync state and errors.

**Columns**:
| Column | Type | Nullable | Default | Description |
|--------|------|----------|---------|-------------|
| id | uuid | NO | gen_random_uuid() | Primary key |
| status | text | NO | 'pending' | Job status |
| job_type | text | NO | 'search_terms' | Job type |
| days_lookback | integer | YES | 30 | Days to look back |
| limit_results | integer | YES | 1000 | Max results to fetch |
| enrich_with_keyword_planner | boolean | YES | false | Enrich with Keyword Planner |
| queries_fetched | integer | YES | 0 | Number of queries fetched |
| queries_enriched | integer | YES | 0 | Number enriched |
| error_message | text | YES | - | Error details if failed |
| created_at | timestamp with time zone | NO | now() | Job creation time |
| started_at | timestamp with time zone | YES | - | Job start time |
| completed_at | timestamp with time zone | YES | - | Job completion time |

**Primary Key**: `id`

**Indexes**:
- `idx_search_query_sync_jobs_status` on `(status, created_at DESC)`

**Check Constraints**:
- `status IN ('pending', 'running', 'completed', 'failed')`
- `job_type IN ('search_terms', 'keyword_planner', 'full_sync')`

**Common Queries**:
```sql
-- Get recent sync jobs
SELECT id, status, job_type, queries_fetched, created_at
FROM search_query_sync_jobs
ORDER BY created_at DESC
LIMIT 10;
```

---

### keyword_coverage_master

Tracks keyword coverage in master SKU content. Identifies gaps for regeneration.

**Columns**:
| Column | Type | Nullable | Default | Description |
|--------|------|----------|---------|-------------|
| id | uuid | NO | gen_random_uuid() | Primary key |
| master_sku | text | NO | - | Master SKU identifier |
| keyword | text | NO | - | Keyword to check |
| in_title | boolean | YES | false | Present in title |
| in_description | boolean | YES | false | Present in description |
| query_volume | integer | YES | 0 | Search query impressions |
| avg_monthly_searches | integer | YES | - | Keyword Planner volume |
| updated_at | timestamp with time zone | YES | now() | Last update time |

**Primary Key**: `id`

**Unique Constraint**: `(master_sku, keyword)`

**Indexes**:
- `idx_keyword_coverage_master_sku` on `master_sku`
- `idx_keyword_coverage_master_gaps` on `master_sku WHERE in_title = false AND query_volume > 0`

**Common Queries**:
```sql
-- Find high-volume keywords missing from title
SELECT keyword, query_volume, avg_monthly_searches
FROM keyword_coverage_master
WHERE master_sku = 'WP-2/16-GAL'
  AND in_title = false
  AND query_volume > 100
ORDER BY query_volume DESC;
```

---

### keyword_coverage_variant

Tracks keyword coverage in variant-specific content.

**Columns**:
| Column | Type | Nullable | Default | Description |
|--------|------|----------|---------|-------------|
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
| updated_at | timestamp with time zone | YES | now() | Last update time |

**Primary Key**: `id`

**Unique Constraint**: `(master_sku, finish, keyword)`

**Indexes**:
- `idx_keyword_coverage_variant_sku` on `(master_sku, finish)`
- `idx_keyword_coverage_variant_gaps` on `master_sku WHERE in_title = false AND query_volume > 0`

---

### finish_search_patterns

Aggregates search query patterns by finish. Identifies finish-specific keyword trends.

**Columns**:
| Column | Type | Nullable | Default | Description |
|--------|------|----------|---------|-------------|
| id | uuid | NO | gen_random_uuid() | Primary key |
| finish | text | NO | - | Full finish name |
| finish_code | text | NO | - | Short finish code |
| pattern_keyword | text | NO | - | Pattern keyword |
| category | text | YES | - | Product category |
| total_impressions | integer | YES | 0 | Sum of impressions |
| total_clicks | integer | YES | 0 | Sum of clicks |
| query_count | integer | YES | 1 | Number of queries |
| updated_at | timestamp with time zone | YES | now() | Last update time |

**Primary Key**: `id`

**Unique Constraint**: `(finish_code, pattern_keyword, category)`

**Indexes**:
- `idx_finish_search_patterns_finish` on `finish_code`
- `idx_finish_search_patterns_category` on `(category, total_impressions DESC)`

**Common Queries**:
```sql
-- Get top patterns for a finish
SELECT pattern_keyword, total_impressions, query_count
FROM finish_search_patterns
WHERE finish_code = 'BKM' AND category = 'Towel Bars'
ORDER BY total_impressions DESC;
```

---

## Image Tables

### product_lifestyle_images

Product-level lifestyle images. Master SKU images used as hero images.

**Columns**:
| Column | Type | Nullable | Default | Description |
|--------|------|----------|---------|-------------|
| id | uuid | NO | gen_random_uuid() | Primary key |
| master_sku | text | NO | - | Master SKU identifier |
| shopify_product_id | text | NO | - | Shopify product ID |
| variation_index | integer | NO | - | Image variation index (1-N) |
| image_url | text | NO | - | Supabase Storage URL |
| thumbnail_url | text | YES | - | Thumbnail URL |
| shopify_media_id | text | YES | - | Shopify media ID |
| shopify_cdn_url | text | YES | - | Shopify CDN URL |
| migrated_to_shopify_at | timestamp with time zone | YES | - | Shopify migration timestamp |
| prompt | text | YES | - | Generation prompt |
| generation_model | text | YES | - | Model used (e.g., "dall-e-3") |
| generation_timestamp | timestamp with time zone | YES | - | Generation time |
| score | numeric | YES | - | Quality score (0-100) |
| score_breakdown | jsonb | YES | - | Detailed scoring |
| approval_status | text | NO | 'pending' | Approval status |
| approved_by | text | YES | - | User who approved |
| approved_at | timestamp with time zone | YES | - | Approval timestamp |
| rejection_reason | text | YES | - | Rejection reason |
| ai_selected | boolean | YES | false | AI-selected flag |
| user_selected | boolean | YES | false | User-selected flag |
| created_at | timestamp with time zone | NO | now() | Record creation time |

**Primary Key**: `id`

**Unique Constraint**: `(master_sku, variation_index)`

**Indexes**:
- `idx_product_images_sku` on `master_sku`
- `idx_product_images_shopify` on `shopify_product_id`
- `idx_product_images_approval` on `approval_status WHERE approval_status = 'approved'`
- `idx_product_images_needs_migration` on `(approval_status, shopify_cdn_url) WHERE approval_status = 'approved' AND shopify_cdn_url IS NULL`

**Lifecycle**: Supabase Storage → Shopify CDN → Google Sheets

**Common Queries**:
```sql
-- Get approved hero image for SKU
SELECT id, shopify_cdn_url, score
FROM product_lifestyle_images
WHERE master_sku = 'WP-2/16-GAL'
  AND approval_status = 'approved'
  AND user_selected = true
LIMIT 1;

-- Find images needing migration
SELECT master_sku, image_url
FROM product_lifestyle_images
WHERE approval_status = 'approved'
  AND shopify_cdn_url IS NULL;
```

---

### variant_lifestyle_images

Variant-level lifestyle images. Finish-specific images for variant expansion.

**Columns**:
| Column | Type | Nullable | Default | Description |
|--------|------|----------|---------|-------------|
| id | uuid | NO | gen_random_uuid() | Primary key |
| master_sku | text | NO | - | Master SKU identifier |
| gmc_offer_id | text | NO | - | GMC offer ID |
| finish | text | NO | - | Full finish name |
| finish_code | text | NO | - | Short finish code |
| variation_index | integer | NO | - | Image variation index (1-N) |
| image_url | text | NO | - | Supabase Storage URL |
| thumbnail_url | text | YES | - | Thumbnail URL |
| shopify_media_id | text | YES | - | Shopify media ID |
| shopify_cdn_url | text | YES | - | Shopify CDN URL |
| migrated_to_shopify_at | timestamp with time zone | YES | - | Shopify migration timestamp |
| gmc_pushed_at | timestamp with time zone | YES | - | GMC push timestamp |
| prompt | text | YES | - | Generation prompt |
| generation_model | text | YES | - | Model used |
| generation_timestamp | timestamp with time zone | YES | - | Generation time |
| score | numeric | YES | - | Quality score (0-100) |
| score_breakdown | jsonb | YES | - | Detailed scoring |
| approval_status | text | NO | 'pending' | Approval status |
| approved_by | text | YES | - | User who approved |
| approved_at | timestamp with time zone | YES | - | Approval timestamp |
| rejection_reason | text | YES | - | Rejection reason |
| ai_selected | boolean | YES | false | AI-selected flag |
| user_selected | boolean | YES | false | User-selected flag |
| created_at | timestamp with time zone | NO | now() | Record creation time |

**Primary Key**: `id`

**Unique Constraint**: `(gmc_offer_id, variation_index)`

**Indexes**:
- `idx_variant_images_sku` on `master_sku`
- `idx_variant_images_finish` on `(master_sku, finish_code)`
- `idx_variant_images_offer` on `gmc_offer_id`
- `idx_variant_images_approval` on `approval_status WHERE approval_status = 'approved'`
- `idx_variant_images_needs_migration` on `(approval_status, shopify_cdn_url) WHERE approval_status = 'approved' AND shopify_cdn_url IS NULL`

**Common Queries**:
```sql
-- Get approved variant images for finish
SELECT id, gmc_offer_id, shopify_cdn_url, score
FROM variant_lifestyle_images
WHERE master_sku = 'WP-2/16-GAL'
  AND finish_code = 'BKM'
  AND approval_status = 'approved'
ORDER BY user_selected DESC, score DESC;
```

---

### lifestyle_image_selections

Tracks user's selected hero images. Links master SKU + optional finish to selected image.

**Columns**:
| Column | Type | Nullable | Default | Description |
|--------|------|----------|---------|-------------|
| id | uuid | NO | gen_random_uuid() | Primary key |
| master_sku | text | NO | - | Master SKU identifier |
| finish | text | YES | - | Finish name (NULL for product-level) |
| selected_image_id | uuid | YES | - | Foreign key to lifestyle images |
| selection_reason | text | YES | - | Selection reason |
| selected_by | text | YES | - | User who selected |
| selected_at | timestamp with time zone | YES | now() | Selection timestamp |

**Primary Key**: `id`

**Unique Constraint**: `idx_lifestyle_selections_unique` on `(master_sku, COALESCE(finish, ''))`

**Indexes**:
- `idx_lifestyle_selections_sku` on `master_sku`

**Common Queries**:
```sql
-- Get hero image selection
SELECT selected_image_id, selection_reason
FROM lifestyle_image_selections
WHERE master_sku = 'WP-2/16-GAL' AND finish IS NULL;
```

---

## Content Generation Tables

### regeneration_history

Audit log for all content regeneration operations. Tracks prompts, feedback, quality deltas, feature flags, and generation cost.

**Columns**:
| Column | Type | Nullable | Default | Description |
|--------|------|----------|---------|-------------|
| id | uuid | NO | gen_random_uuid() | Primary key |
| master_sku | text | NO | - | Master SKU identifier |
| content_type | text | NO | - | Content type ("title", "description") |
| platform | text | NO | - | Platform ("google", "bing") |
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
| generated_content_id | uuid | YES | - | Foreign key to generated_content |
| created_at | timestamp with time zone | NO | now() | Regeneration timestamp |
| created_by | text | YES | - | User who triggered |
| feature_flags_active | jsonb | YES | - | Feature flag state snapshot at generation time (MEAS-01) |
| tokens_used | integer | YES | - | Token count from LLM provider response |
| latency_ms | integer | YES | - | Generation wall-clock latency in milliseconds |
| cost_usd | numeric(10,6) | YES | - | Estimated generation cost in USD |

**Primary Key**: `id`

**Indexes**:
- `idx_regen_history_sku` on `master_sku`
- `idx_regen_history_sku_type` on `(master_sku, content_type, platform)`
- `idx_regen_history_created` on `created_at DESC`
- `idx_regen_history_prompt_hash` on `prompt_hash`
- `idx_regen_history_flags` on `feature_flags_active` (GIN)

**Common Queries**:
```sql
-- Get regeneration history for SKU
SELECT
    created_at,
    content_type,
    feedback_text,
    quality_score_before,
    quality_score_after,
    feature_flags_active,
    latency_ms
FROM regeneration_history
WHERE master_sku = 'WP-2/16-GAL'
ORDER BY created_at DESC;

-- Find regenerations with same prompt
SELECT master_sku, created_at, quality_score_after
FROM regeneration_history
WHERE prompt_hash = 'abc123'
ORDER BY created_at DESC;

-- Analyze generations by flag state (MEAS-01)
SELECT
    (feature_flags_active->>'PROMPT_CONTRACT_V2')::boolean AS contract_v2,
    COUNT(*) AS generation_count,
    AVG(latency_ms) AS avg_latency_ms
FROM regeneration_history
WHERE feature_flags_active IS NOT NULL
GROUP BY 1;
```

---

### prompt_version_aliases

Maps prompt hashes to human-readable version names for MEAS-03 tracking. Applied in migration 035.

**Columns**:
| Column | Type | Nullable | Default | Description |
|--------|------|----------|---------|-------------|
| id | bigint | NO | nextval() | Primary key |
| prompt_hash | text | NO | - | Unique hash of prompt content |
| alias | text | YES | - | Human-readable version name (e.g., "v2.1-grab-bar-fix") |
| notes | text | YES | - | Notes about what changed in this version |
| created_at | timestamptz | NO | now() | When alias was created |
| created_by | text | YES | - | User who created the alias |

**Primary Key**: `id`

**Unique Constraint**: `prompt_hash`

**Indexes**:
- `idx_prompt_version_aliases_hash` on `prompt_hash`

**Common Queries**:
```sql
-- Lookup alias for a prompt hash
SELECT alias, notes
FROM prompt_version_aliases
WHERE prompt_hash = 'abc123';

-- Join with regeneration history to see version usage
SELECT
    pva.alias,
    COUNT(*) AS usage_count,
    MIN(rh.created_at) AS first_used,
    MAX(rh.created_at) AS last_used
FROM regeneration_history rh
LEFT JOIN prompt_version_aliases pva ON rh.prompt_hash = pva.prompt_hash
GROUP BY pva.alias
ORDER BY usage_count DESC;
```

---

### sku_bottleneck_classifications

Stores per-SKU bottleneck classification results for MEAS-04. Applied in migration 035.

**Columns**:
| Column | Type | Nullable | Default | Description |
|--------|------|----------|---------|-------------|
| id | bigint | NO | nextval() | Primary key |
| master_sku | text | NO | - | Master SKU identifier |
| classification | text | NO | - | Bottleneck type (e.g., "content_quality", "coverage_gap") |
| confidence | numeric(4,2) | YES | - | Confidence score 0-1 |
| evidence | jsonb | YES | - | Evidence supporting the classification |
| override_by | text | YES | - | User who created manual override |
| override_note | text | YES | - | Explanation for override |
| is_override | boolean | YES | false | True if this is a manual override record |
| classified_at | timestamptz | NO | now() | When classification was made |
| publish_event_id | bigint | YES | - | Associated publish event (if applicable) |

**Primary Key**: `id`

**Indexes**:
- `idx_sku_bottleneck_master_sku` (UNIQUE PARTIAL) on `master_sku WHERE is_override = false`
- `idx_sku_bottleneck_classification` on `classification`
- `idx_sku_bottleneck_classified_at` on `classified_at DESC`

**Note**: The partial unique index ensures only one non-override classification exists per SKU. Manual overrides are allowed to coexist.

---

### gmc_product_status

Stores Google Merchant Center product approval status and item issues for MEAS-02. Applied in migration 035.

**Columns**:
| Column | Type | Nullable | Default | Description |
|--------|------|----------|---------|-------------|
| id | bigint | NO | nextval() | Primary key |
| gmc_offer_id | text | NO | - | GMC offer ID (format: shopify_us_...) |
| master_sku | text | YES | - | Master SKU (if resolved) |
| offer_title | text | YES | - | Product title from GMC |
| status | text | NO | - | GMC status: "approved", "disapproved", "pending" |
| item_issues | jsonb | YES | - | Array of GMC item issues |
| issue_count | integer | YES | 0 | Total number of issues |
| disapproval_count | integer | YES | 0 | Number of disapprovals |
| synced_at | timestamptz | NO | now() | Last sync timestamp |
| sync_job_id | uuid | YES | - | Source sync job ID |

**Primary Key**: `id`

**Unique Constraint**: `gmc_offer_id` (via index)

**Indexes**:
- `idx_gmc_product_status_offer_id` (UNIQUE) on `gmc_offer_id`
- `idx_gmc_product_status_master_sku` on `master_sku`
- `idx_gmc_product_status_status` on `status`
- `idx_gmc_product_status_synced_at` on `synced_at DESC`

**Common Queries**:
```sql
-- Get disapproved products
SELECT master_sku, offer_title, issue_count, disapproval_count, item_issues
FROM gmc_product_status
WHERE status = 'disapproved'
ORDER BY disapproval_count DESC;

-- Check sync freshness
SELECT MAX(synced_at) AS last_sync, COUNT(*) AS total_products
FROM gmc_product_status;
```

---

### prompt_templates

Stores gold standard examples and system prompts. Referenced by content generation.

**Columns**:
| Column | Type | Nullable | Default | Description |
|--------|------|----------|---------|-------------|
| id | uuid | NO | gen_random_uuid() | Primary key |
| name | text | NO | - | Unique template name |
| version | integer | NO | 1 | Template version |
| is_active | boolean | YES | false | Is this version active |
| system_prompt | text | NO | - | System prompt text |
| gold_standard_examples | jsonb | NO | - | Array of example objects |
| category_guidance | jsonb | YES | - | Category-specific guidance |
| platform_rules | jsonb | YES | - | Platform-specific rules |
| description | text | YES | - | Template description |
| created_by | text | YES | - | User who created |
| created_at | timestamp with time zone | YES | now() | Creation timestamp |
| updated_at | timestamp with time zone | YES | now() | Last update time |

**Primary Key**: `id`

**Unique Constraint**: `name`

**Indexes**:
- `idx_prompt_templates_name_version` on `(name, version)`
- `idx_prompt_templates_active` on `is_active WHERE is_active = true`

**JSONB Structure Examples**:
```json
// gold_standard_examples
[
  {
    "sku": "WP-2/16-GAL",
    "title": "16\" Towel Bar - Modern Bathroom Hardware",
    "description": "Premium 16-inch towel bar with mounting hardware...",
    "quality_score": 95,
    "reason": "High conversion rate, clear specs"
  }
]

// category_guidance
{
  "Towel Bars": {
    "key_features": ["length", "finish", "mounting"],
    "avoid_terms": ["cheap", "basic"]
  }
}
```

**Common Queries**:
```sql
-- Get active template
SELECT system_prompt, gold_standard_examples
FROM prompt_templates
WHERE name = 'google_title_v1' AND is_active = true;
```

---

### batch_generation_jobs

Manages bulk content generation jobs. Tracks overall job progress.

**Columns**:
| Column | Type | Nullable | Default | Description |
|--------|------|----------|---------|-------------|
| id | uuid | NO | gen_random_uuid() | Primary key |
| status | text | NO | 'queued' | Job status |
| total_skus | integer | NO | - | Total SKUs to process |
| completed_skus | integer | YES | 0 | Completed SKUs |
| failed_skus | integer | YES | 0 | Failed SKUs |
| options | jsonb | NO | '{}' | Job options |
| error_message | text | YES | - | Error details |
| created_at | timestamp with time zone | NO | now() | Job creation time |
| started_at | timestamp with time zone | YES | - | Job start time |
| completed_at | timestamp with time zone | YES | - | Job completion time |
| created_by | text | YES | - | User who created job |

**Primary Key**: `id`

**Indexes**:
- `idx_batch_gen_jobs_status` on `(status, created_at)`
- `idx_batch_gen_jobs_user` on `(created_by, created_at DESC)`

**Check Constraints**:
- `status IN ('queued', 'processing', 'completed', 'failed')`

**Common Queries**:
```sql
-- Get active jobs
SELECT id, status, completed_skus, total_skus, created_at
FROM batch_generation_jobs
WHERE status IN ('queued', 'processing')
ORDER BY created_at;
```

---

### batch_generation_job_skus

Tracks per-SKU status within batch generation jobs.

**Columns**:
| Column | Type | Nullable | Default | Description |
|--------|------|----------|---------|-------------|
| id | uuid | NO | gen_random_uuid() | Primary key |
| job_id | uuid | NO | - | Foreign key to batch_generation_jobs |
| master_sku | text | NO | - | Master SKU identifier |
| status | text | NO | 'pending' | SKU status |
| error_message | text | YES | - | Error details |
| generated_content_ids | ARRAY | YES | - | Array of generated_content IDs |
| created_at | timestamp with time zone | NO | now() | Record creation time |
| started_at | timestamp with time zone | YES | - | Processing start time |
| completed_at | timestamp with time zone | YES | - | Processing completion time |

**Primary Key**: `id`

**Unique Constraint**: `(job_id, master_sku)`

**Indexes**:
- `idx_batch_gen_job_skus_job` on `job_id`
- `idx_batch_gen_job_skus_status` on `(job_id, status)`

**Check Constraints**:
- `status IN ('pending', 'processing', 'completed', 'failed')`

**Common Queries**:
```sql
-- Get job progress
SELECT
    COUNT(*) FILTER (WHERE status = 'completed') AS completed,
    COUNT(*) FILTER (WHERE status = 'failed') AS failed,
    COUNT(*) FILTER (WHERE status = 'pending') AS pending
FROM batch_generation_job_skus
WHERE job_id = 'abc-123';
```

---

### generation_jobs

Legacy job queue table. May be deprecated in favor of batch_generation_jobs.

**Columns**:
| Column | Type | Nullable | Default | Description |
|--------|------|----------|---------|-------------|
| id | uuid | NO | gen_random_uuid() | Primary key |
| master_sku | text | NO | - | Master SKU identifier |
| job_type | text | NO | - | Job type |
| status | text | NO | 'pending' | Job status |
| priority | integer | YES | 0 | Job priority |
| input_params | jsonb | YES | - | Job parameters |
| result | jsonb | YES | - | Job result |
| error | text | YES | - | Error message |
| attempt_count | integer | YES | 0 | Retry attempt count |
| max_attempts | integer | YES | 3 | Max retry attempts |
| requested_by | text | YES | - | User who requested |
| created_at | timestamp with time zone | NO | now() | Job creation time |
| started_at | timestamp with time zone | YES | - | Job start time |
| completed_at | timestamp with time zone | YES | - | Job completion time |

**Primary Key**: `id`

**Indexes**:
- `idx_jobs_sku` on `(master_sku, created_at DESC)`
- `idx_jobs_status` on `(status, priority DESC, created_at)`

---

## Competitor Intelligence Tables

### competitor_listings

Stores competitor product listings scraped from SERP and marketplaces.

**Columns**:
| Column | Type | Nullable | Default | Description |
|--------|------|----------|---------|-------------|
| id | uuid | NO | gen_random_uuid() | Primary key |
| source | text | NO | - | Source identifier (e.g., "google_shopping") |
| source_type | text | NO | - | Source type ("serp", "marketplace") |
| source_url | text | YES | - | URL of listing |
| domain | text | YES | - | Domain of seller |
| product_category | text | NO | - | Product category |
| title | text | NO | - | Product title |
| description | text | YES | - | Product description |
| price | numeric | YES | - | Price |
| rating | numeric | YES | - | Star rating |
| review_count | integer | YES | - | Number of reviews |
| brand | text | YES | - | Brand name |
| position | integer | YES | - | SERP position |
| image_url | text | YES | - | Product image URL |
| keywords_extracted | ARRAY | YES | - | Extracted keywords |
| scraped_at | timestamp with time zone | YES | now() | Scrape timestamp |
| scrape_job_id | uuid | YES | - | Foreign key to competitor_scrape_jobs |

**Primary Key**: `id`

**Unique Constraint**: `(source, source_url)`

**Indexes**:
- `idx_competitor_listings_domain` on `domain`
- `idx_competitor_listings_category` on `product_category`
- `idx_competitor_listings_job` on `scrape_job_id`
- `idx_competitor_listings_source_type` on `(source_type, product_category)`

**Common Queries**:
```sql
-- Get top SERP competitors
SELECT title, domain, position, rating
FROM competitor_listings
WHERE product_category = 'Towel Bars'
  AND source_type = 'serp'
ORDER BY position
LIMIT 20;
```

---

### competitor_patterns

Aggregated patterns extracted from competitor listings. Identifies trends.

**Columns**:
| Column | Type | Nullable | Default | Description |
|--------|------|----------|---------|-------------|
| id | uuid | NO | gen_random_uuid() | Primary key |
| category | text | NO | - | Product category |
| pattern_type | text | NO | - | Pattern type (e.g., "keyword", "phrase") |
| pattern_value | text | NO | - | Pattern value |
| frequency | integer | YES | 1 | Occurrence count |
| avg_position | numeric | YES | - | Average SERP position |
| sources | ARRAY | YES | - | Array of source domains |
| example_titles | ARRAY | YES | - | Example titles |
| updated_at | timestamp with time zone | YES | now() | Last update time |

**Primary Key**: `id`

**Unique Constraint**: `(category, pattern_type, pattern_value)`

**Indexes**:
- `idx_competitor_patterns_category` on `(category, pattern_type)`
- `idx_competitor_patterns_frequency` on `(category, frequency DESC)`

**Common Queries**:
```sql
-- Get top keyword patterns
SELECT pattern_value, frequency, avg_position
FROM competitor_patterns
WHERE category = 'Towel Bars'
  AND pattern_type = 'keyword'
ORDER BY frequency DESC
LIMIT 20;
```

---

### competitor_scrape_jobs

Tracks competitor scraping jobs. Manages Apify integration state.

**Columns**:
| Column | Type | Nullable | Default | Description |
|--------|------|----------|---------|-------------|
| id | uuid | NO | gen_random_uuid() | Primary key |
| status | text | NO | 'pending' | Job status |
| job_type | text | NO | - | Job type ('serp', 'marketplace') |
| category | text | NO | - | Product category |
| source | text | NO | - | Source platform |
| search_query | text | YES | - | Search query used |
| apify_run_id | text | YES | - | Apify run ID |
| apify_dataset_id | text | YES | - | Apify dataset ID |
| listings_count | integer | YES | 0 | Number of listings scraped |
| error_message | text | YES | - | Error details |
| created_at | timestamp with time zone | NO | now() | Job creation time |
| started_at | timestamp with time zone | YES | - | Job start time |
| completed_at | timestamp with time zone | YES | - | Job completion time |

**Primary Key**: `id`

**Indexes**:
- `idx_competitor_scrape_jobs_status` on `(status, created_at)`
- `idx_competitor_scrape_jobs_category` on `(category, source)`

**Check Constraints**:
- `status IN ('pending', 'running', 'completed', 'failed')`
- `job_type IN ('serp', 'marketplace')`

---

## Support Tables

### shopify_products

Tracks Shopify products. Currently stores minimal data.

**Columns**:
| Column | Type | Nullable | Default | Description |
|--------|------|----------|---------|-------------|
| shopify_product_id | text | NO | - | Primary key: Shopify product ID |
| created_at | timestamp with time zone | NO | now() | Record creation time |
| updated_at | timestamp with time zone | NO | now() | Last update time |

**Primary Key**: `shopify_product_id`

**Indexes**:
- `idx_shopify_products_id` on `shopify_product_id`

---

## Backfill Infrastructure Tables

### backfill_jobs

Manages historical data backfill jobs for v1.0 milestone. Supports full checkpoint/resume for long-running batch operations.

**Columns**:
| Column | Type | Nullable | Default | Description |
|--------|------|----------|---------|-------------|
| id | uuid | NO | gen_random_uuid() | Primary key |
| job_type | text | NO | - | Job type ('search_terms', 'performance_metrics', 'keyword_planner', 'custom_labels', 'full_backfill') |
| status | text | NO | 'creating' | Job status |
| total_items | integer | NO | - | Total items to process |
| completed_items | integer | YES | 0 | Number completed |
| failed_items | integer | YES | 0 | Number failed |
| skus | jsonb | YES | - | Array of SKU strings to process |
| checkpoint_data | jsonb | YES | - | Checkpoint state for resume |
| config | jsonb | YES | '{}' | Job configuration |
| created_at | timestamp with time zone | NO | now() | Job creation time |
| started_at | timestamp with time zone | YES | - | Job start time |
| completed_at | timestamp with time zone | YES | - | Job completion time |
| eta_seconds | integer | YES | - | Estimated time remaining (seconds) |
| created_by | text | YES | - | User who created job |

**Primary Key**: `id`

**Indexes**:
- `idx_backfill_jobs_status` on `(status, created_at DESC)`
- `idx_backfill_jobs_type` on `(job_type, created_at DESC)`

**Check Constraints**:
- `status IN ('creating', 'running', 'complete', 'failed', 'partial')`
- `job_type IN ('search_terms', 'performance_metrics', 'keyword_planner', 'custom_labels', 'full_backfill')`

**JSONB Structure Examples**:
```json
// skus (array of SKU strings)
["WP-2/16-GAL", "920D-6", "DMF-2/2X"]

// checkpoint_data (resume state)
{
  "batch_index": 50,
  "last_sku": "920D-6",
  "last_processed_at": "2026-02-13T12:34:56Z"
}

// config (job configuration)
{
  "batch_size": 10,
  "days_lookback": 180,
  "enrich_keyword_planner": true
}
```

**Common Queries**:
```sql
-- Get active jobs
SELECT id, job_type, status, completed_items, total_items, eta_seconds
FROM backfill_jobs
WHERE status IN ('creating', 'running')
ORDER BY created_at;

-- Get job progress
SELECT
    id,
    job_type,
    status,
    ROUND(100.0 * completed_items / NULLIF(total_items, 0), 2) AS percent_complete,
    eta_seconds
FROM backfill_jobs
WHERE id = 'abc-123';

-- Find failed jobs with errors
SELECT
    bj.id,
    bj.job_type,
    bj.failed_items,
    COUNT(bje.id) AS error_count
FROM backfill_jobs bj
LEFT JOIN backfill_job_errors bje ON bj.id = bje.job_id
WHERE bj.status = 'failed'
GROUP BY bj.id, bj.job_type, bj.failed_items
ORDER BY bj.created_at DESC;
```

---

### backfill_job_errors

Per-item error logs for backfill jobs. Supports debugging and selective retry operations.

**Columns**:
| Column | Type | Nullable | Default | Description |
|--------|------|----------|---------|-------------|
| id | bigserial | NO | nextval() | Primary key |
| job_id | uuid | NO | - | Foreign key to backfill_jobs |
| item_id | text | NO | - | Failed item identifier (usually SKU) |
| error_type | text | NO | - | Error category |
| error_message | text | YES | - | Detailed error message |
| retry_count | integer | YES | 0 | Number of retry attempts |
| created_at | timestamp with time zone | NO | now() | Error timestamp |

**Primary Key**: `id`

**Foreign Keys**:
- `job_id` references `backfill_jobs(id)` ON DELETE CASCADE

**Indexes**:
- `idx_backfill_job_errors_job` on `(job_id, created_at DESC)`

**Common Queries**:
```sql
-- Get errors for a job
SELECT
    item_id,
    error_type,
    error_message,
    retry_count,
    created_at
FROM backfill_job_errors
WHERE job_id = 'abc-123'
ORDER BY created_at DESC
LIMIT 100;

-- Group errors by type
SELECT
    error_type,
    COUNT(*) AS error_count,
    ARRAY_AGG(DISTINCT item_id) AS affected_items
FROM backfill_job_errors
WHERE job_id = 'abc-123'
GROUP BY error_type
ORDER BY error_count DESC;
```

**RPC Functions**:
- `increment_backfill_failures(p_job_id UUID)`: Atomically increments failed_items counter

---

## Optimization & Intent Control Tables

These tables were introduced by migration `035_unified_intent_execution_system.sql` and support unified Shopping/Search intent routing, policy decisioning, guardrails, search governance, and experimentation.

### intent_taxonomy_versions

Versioned taxonomy registry used by routing and governance policies.

**Key columns**:
- `version_key` (unique): policy/taxonomy identifier
- `class_definitions` / `mapping_rules` (jsonb): canonical intent mappings
- `is_active`, `activated_at`, `activated_by`: active version controls

---

### term_intent_state

Current resolved intent state per normalized query and label scope.

**Key columns**:
- `search_term`, `normalized_search_term`, `custom_label_0`
- `intent_class`, `intent_subclasses`, `route_action`
- `shopping_tier`, `search_tier`, `confidence`, `requires_review`
- `policy_version`, `source_window_start`, `source_window_end`, `metadata`

**Unique index**:
- `(normalized_search_term, coalesce(custom_label_0, '__all__'))`

---

### policy_decision_log

Immutable ledger of policy decisions (routing, promotion/demotion, bid policy, etc.).

**Key columns**:
- `decision_type`, `channel`, `policy_version`
- `decision_payload` (jsonb), `confidence`, `requires_review`
- `search_term`, `custom_label_0`, `created_by`, `created_at`

---

### policy_action_execution_log

Execution-status log for planned/applied/rolled-back actions.

**Key columns**:
- `action_type`, `status`, `policy_version`
- `action_payload` (jsonb), `reason_codes`
- `search_term`, `custom_label_0`, `created_by`, `updated_at`

**Status check values**:
- `planned`, `applied`, `rolled_back`, `failed`, `cancelled`

---

### policy_snapshots

Snapshot/restore state for safe rollback workflows.

**Key columns**:
- `snapshot_key` (unique), `policy_version`
- `payload` (jsonb)
- `created_by`, `restored_by`, `restored_at`

---

### sku_margin_daily

Daily SKU-level margin enrichment for profit-weighted optimization.

**Key columns**:
- `snapshot_date`, `sku` (unique pair)
- `unit_cogs`, `gross_margin_rate`, `currency_code`
- `source_payload` (jsonb)

---

### order_line_returns_daily

Daily return/refund enrichment to support contribution-margin quality signals.

**Key columns**:
- `snapshot_date`, `shopify_order_gid`, `sku`
- `returned_quantity`, `return_amount`, `restock_fee`
- `source_payload` (jsonb)

---

### attribution_confidence_daily

Daily confidence scoring for attribution quality by channel/campaign scope.

**Key columns**:
- `snapshot_date`, `channel`, `campaign_key`
- `confidence_score`, `quality_bucket`, `signals` (jsonb)

**Quality bucket check values**:
- `high`, `medium`, `low`, `unknown`

---

### experiment_registry

Top-level experiment definitions with thresholds and decision rules.

**Key columns**:
- `experiment_key` (unique), `name`, `initiative`, `hypothesis`
- `decision_rule`, `success_threshold`, `failure_threshold`
- `status`, `start_date`, `end_date`, `metadata`

**Status check values**:
- `draft`, `active`, `paused`, `completed`, `cancelled`

---

### experiment_assignments

Entity-level cohort assignments for controlled experiments.

**Key columns**:
- `experiment_key`, `entity_key`, `cohort`
- `assigned_at`, `metadata`

**Foreign key**:
- `experiment_key` references `experiment_registry(experiment_key)` ON DELETE CASCADE

---

### experiment_outcomes

Observed outcomes/lift measurements by experiment and metric.

**Key columns**:
- `experiment_key`, `metric_name`
- `observed_lift`, `sample_size`, `status`, `measured_at`
- `metadata`

**Status check values**:
- `observing`, `success`, `failure`, `inconclusive`

**Foreign key**:
- `experiment_key` references `experiment_registry(experiment_key)` ON DELETE CASCADE

---

### negative_registry

Centralized cross-channel negative governance with rollback tokens.

**Key columns**:
- `term`, `scope`, `source_policy`
- `confidence`, `reason_codes`, `rollback_token`
- `active`, `metadata`, `deactivated_at`, `deactivated_by`

---

### search_buildout_recommendations

Search governance output queue for candidate/approved/applied buildout terms.

**Key columns**:
- `search_term`, `custom_label_0`
- `recommended_search_tier`, `status`, `confidence`
- `metadata`, `approved_by`, `approved_at`

**Check values**:
- Tiers: `broad`, `phrase`, `exact`
- Status: `candidate`, `approved`, `applied`, `rejected`, `paused`

---

### operator_review_audit

Audit trail for human review actions (queue decisions and before/after state).

**Key columns**:
- `queue_name`, `entity_key`, `action`
- `before_state` / `after_state` (jsonb)
- `actor`, `created_at`

---

## Key Relationships

### Foreign Key Relationships

1. **batch_sku_assignments** → **publish_batches**
   - `batch_id` references `publish_batches(batch_id)`

2. **publish_events** → **publish_batches**
   - `batch_id` references `publish_batches(batch_id)`

3. **performance_snapshots** → **publish_events**
   - `publish_event_id` references `publish_events(id)`

4. **search_query_snapshots** → **publish_events**
   - `publish_event_id` references `publish_events(id)`

5. **search_queries** → **search_query_sync_jobs**
   - `sync_job_id` references `search_query_sync_jobs(id)`

6. **batch_generation_job_skus** → **batch_generation_jobs**
   - `job_id` references `batch_generation_jobs(id)`

7. **regeneration_history** → **generated_content**
   - `generated_content_id` references `generated_content(id)`

8. **competitor_listings** → **competitor_scrape_jobs**
   - `scrape_job_id` references `competitor_scrape_jobs(id)`

9. **backfill_job_errors** → **backfill_jobs**
   - `job_id` references `backfill_jobs(id)` ON DELETE CASCADE

10. **experiment_assignments** → **experiment_registry**
   - `experiment_key` references `experiment_registry(experiment_key)` ON DELETE CASCADE

11. **experiment_outcomes** → **experiment_registry**
   - `experiment_key` references `experiment_registry(experiment_key)` ON DELETE CASCADE

---

## JSONB Column Conventions

### Storage
Store JSONB as **text strings** in the database. Parse before array operations:

```sql
-- WRONG: Direct array operation
SELECT * FROM table WHERE 'value' = ANY(jsonb_column);

-- CORRECT: Parse to JSONB first
SELECT * FROM table WHERE 'value' = ANY(SELECT jsonb_array_elements_text((jsonb_column#>>'{}')::jsonb));
```

### LATERAL Joins
Use LATERAL joins to expand JSONB arrays:

```sql
SELECT t.id, elem.value
FROM table t
CROSS JOIN LATERAL jsonb_array_elements_text((t.jsonb_column#>>'{}')::jsonb) AS elem(value);
```

---

## Case Sensitivity

### Master SKUs
Master SKUs are **case-sensitive** and use slash separators:
- Database: `WP-2/16-GAL`, `DMF-2/2X`
- URLs: Convert to hyphens (`WP-2-16-GAL`, `DMF-2-2X`)

### GMC Offer IDs
GMC offer IDs use **lowercase** "us":
- Format: `shopify_us_{product_id}_{variant_id}`
- Example: `shopify_us_4539975336068_12345678`

### Queries
Always use `LOWER()` on both sides for case-insensitive matching:

```sql
SELECT * FROM variant_index
WHERE LOWER(gmc_offer_id) = LOWER('shopify_US_123_456');
```

---

## Multi-SKU Products

**CRITICAL**: Multiple master_skus can share the same Shopify product_id.

Example:
- `DMF-2/2X`, `DMF-2/3X`, `DMF-2/4X`, `DMF-2/5X` all share `product_id = 4539975336068`
- Google Ads aggregates at product_id level (not master_sku)
- Must use JSONB `item_ids` array in `search_queries` to handle this

See: `/Users/bobby/Documents/GitHub/Allied-FeedOps/docs/architecture/multi-sku-pattern.md`

---

## Common Query Patterns

### Get Complete SKU Data
```sql
SELECT
    vi.master_sku,
    vi.gmc_offer_id,
    vi.finish,
    vi.finish_code,
    pc.title,
    pc.category,
    pc.narrative_copy,
    gc.candidate_content AS title_content,
    sa.approval_status
FROM variant_index vi
LEFT JOIN product_catalog pc ON vi.option_sku = pc.option_sku
LEFT JOIN generated_content gc
    ON vi.master_sku = gc.master_sku
    AND gc.platform = 'google'
    AND gc.content_type = 'title'
LEFT JOIN sku_approvals sa ON vi.master_sku = sa.master_sku
WHERE vi.master_sku = 'WP-2/16-GAL'
LIMIT 1;
```

### Check Data Freshness
```sql
-- Check if baseline is stale
SELECT
    master_sku,
    EXTRACT(EPOCH FROM (NOW() - created_at)) / 86400 AS days_old
FROM performance_baselines
WHERE master_sku = 'WP-2/16-GAL'
  AND created_at < NOW() - INTERVAL '60 days';

-- Check if search query data is stale
SELECT
    master_sku,
    MAX(fetched_at) AS last_sync
FROM search_queries
WHERE master_sku = 'WP-2/16-GAL'
GROUP BY master_sku
HAVING MAX(fetched_at) < NOW() - INTERVAL '7 days';
```

### Performance Delta Analysis
```sql
WITH baseline AS (
    SELECT
        master_sku,
        avg_impressions AS baseline_impressions,
        avg_ctr AS baseline_ctr
    FROM performance_baselines
    WHERE master_sku = 'WP-2/16-GAL' AND platform = 'google'
),
current AS (
    SELECT
        master_sku,
        impressions AS current_impressions,
        ctr AS current_ctr
    FROM performance_snapshots
    WHERE master_sku = 'WP-2/16-GAL'
      AND platform = 'google'
      AND snapshot_date = CURRENT_DATE
)
SELECT
    b.master_sku,
    c.current_impressions - b.baseline_impressions AS impression_delta,
    ((c.current_ctr - b.baseline_ctr) / NULLIF(b.baseline_ctr, 0)) * 100 AS ctr_pct_change
FROM baseline b
JOIN current c ON b.master_sku = c.master_sku;
```

### Get Approved Content for Publishing
```sql
SELECT
    gc.master_sku,
    gc.content_type,
    gc.approved_content,
    vfs.finish_sentences
FROM generated_content gc
LEFT JOIN variant_finish_sentences vfs
    ON gc.master_sku = vfs.master_sku
    AND gc.platform = vfs.platform
WHERE gc.master_sku = 'WP-2/16-GAL'
  AND gc.platform = 'google'
  AND gc.approved_content IS NOT NULL;
```

---

## Notes

- **Version**: Schema documented 2026-02-21 (updated with unified intent execution + measurement infrastructure)
- **Total Tables**: 51 (includes unified intent execution tables + prompt_version_aliases, sku_bottleneck_classifications, gmc_product_status)
- **Backup Table**: `generated_images_backup_20260208` (historical data)
- **Data Collection**: Automated via `ensureSkuData()` and `ensureAllData()` in dashboard
- **Auto-Deploy**: Push to master triggers Cloud Run (Python) and Vercel (Dashboard) deploys
- **Pending Migration**: `supabase/migrations/035_measurement_infrastructure_schema.sql` — apply via Supabase SQL Editor or `supabase db push` with personal access token

For architecture details, see:
- `/Users/bobby/Documents/GitHub/Allied-FeedOps/docs/architecture/`
- `/Users/bobby/Documents/GitHub/Allied-FeedOps/docs/troubleshooting/`
