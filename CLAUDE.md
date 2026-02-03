# Allied-FeedOps Project Memory

## Project Overview

FeedOps is a feed optimization system for Allied Brass that generates optimized product titles, descriptions, and lifestyle images for Google Merchant Center, Bing, and Shopify. It uses LLMs to create content that passes Google's structured data requirements while incorporating SEO keywords.

**Business Goal**: Improve product feed quality to increase CTR, conversions, and ROAS on Shopping ads.

## MCP Server Defaults

- **Google Analytics**: Always use the **Allied Brass - GA4 (Old)** property when querying Google Analytics data.
- **Google Ads**: Always use customer ID **6253381786** when querying Google Ads data.

## Architecture

### Database Layer (`src/feedops/db/`)
- **Dual-backend**: SQLite for local development, Supabase for Streamlit Cloud
- **Router pattern**: `__init__.py` conditionally imports from `schema.py` (SQLite) or `supabase_client.py` based on `is_supabase_available()`
- **Key tables**:
  - `sku_approvals` - Master SKU-level approval tracking
  - `variant_approvals` - Per-finish variant approval tracking
  - `publish_batches` - Batch/cohort management for publishing
  - `publish_events` - Audit log of all publish actions
  - `variant_index` - Maps GMC IDs to master SKUs with finish/dimensions
  - `performance_snapshots` - Post-publish metrics tracking
  - `performance_baselines` - Pre-optimization baseline metrics

**Important Column Naming** (unified across SQLite and Supabase):
- Use `approval_status` (not `status`)
- Use `notes` (not `revision_notes`)
- Use `approved_by` / `approved_at` (not `reviewed_by` / `reviewed_at`)
- Batch uses `name` / `notes` / `executed_at` (not `batch_label` / `selection_criteria` / `published_at`)

### Pipeline (`src/feedops/pipeline/`)
- `optimize_sku.py` - Main optimization orchestrator
- `prompt_builder.py` - Constructs LLM prompts with product data
- `content_generator.py` - Calls LLM APIs (OpenAI, Gemini)
- `quality_scorer.py` - Scores generated content (0-100)

### Quality & Review (`src/feedops/quality/`)
- `review_dashboard.py` - Streamlit dashboard for approvals, batching, publishing
- `scorer.py` - Quality scoring logic (GMC compliance, keyword density, etc.)

### Integrations (`src/feedops/integrations/`)
- `google_sheets.py` - Reads/writes Google Merchant Center feed via Sheets
- `shopify.py` - Shopify GraphQL API for product updates
- `bing.py` - Bing Merchant Center API

### Key Data Files
- `data/Product Catalog.csv` - Master product catalog with SKUs, finishes, dimensions
- `dashboard_data/*/` - Generated content, patches, and reports per batch
- `data/pilot_sku_selection/` - SKU selection data for pilot batches

## Approval Workflow

1. **Generate**: Pipeline creates title/description variants for each SKU
2. **Review**: Dashboard shows variants with quality scores for human review
3. **Approve**: Reviewer approves/rejects title, description, image per variant
4. **Batch**: Approved SKUs are assigned to publish batches
5. **Publish**: Batch is published to staging → production (Google, Bing, Shopify)
6. **Monitor**: Performance snapshots track post-publish metrics

## SKU Selection Strategy

The pilot batch of 40 SKUs used this tiering strategy (see `dashboard_data/lifestyle-eval/reports/pilot-selection-report-detailed.md`):

- **Tier 1**: High conversion efficiency, low traffic (risk-managed winners)
- **Tier 2**: Mid-pack performance (primary test bed)
- **Tier 3**: High traffic, low efficiency (largest upside potential)
- **Fill**: Category diversity completion

**Key Principle**: Mix of performance levels to enable A/B testing impact measurement. Don't change all best OR all worst performers at once.

## Running the Dashboard

```bash
PYTHONPATH=src streamlit run src/feedops/quality/review_dashboard.py
```

## Running Tests

```bash
PYTHONPATH=src .venv/bin/pytest tests/ -v
```

## Important File Locations

| Purpose | File |
|---------|------|
| Database router | `src/feedops/db/__init__.py` |
| SQLite schema + CRUD | `src/feedops/db/schema.py` |
| Supabase client | `src/feedops/db/supabase_client.py` |
| Variant index builder | `src/feedops/db/variant_index.py` |
| Main dashboard | `src/feedops/quality/review_dashboard.py` |
| Quality scoring | `src/feedops/quality/scorer.py` |
| GMC feed integration | `src/feedops/integrations/google_sheets.py` |
| Optimization pipeline | `src/feedops/pipeline/optimize_sku.py` |
| Supabase migrations | `supabase/migrations/001_initial_schema.sql` |
| Pilot selection report | `dashboard_data/lifestyle-eval/reports/pilot-selection-report-detailed.md` |
| Product catalog | `data/Product Catalog.csv` |

## Recent Changes (2026-02)

- **Database Schema Overhaul**: Unified SQLite and Supabase column names for consistency
- **Variant Approvals**: Added per-finish approval tracking (`variant_approvals` table)
- **Auto-derive Status**: Approval status auto-derives from element-level approvals (title/desc/image)
- **Variant Index**: Added `finish` and `finish_code` columns for product mapping
- **Published SKU Tracking**: Real implementation of `get_published_skus()` for SQLite
- **Environment Filtering**: `get_publish_history()` now supports environment parameter

## Pilot SKUs (40 total)

The current pilot batch includes SKUs across 24 categories. See `data/pilot_sku_selection/selected_master_skus.txt` for the full list.

**Excluded from pilot** (top revenue protection): CL-55, FR-23, TD-23, CL-28-30, CL-54
