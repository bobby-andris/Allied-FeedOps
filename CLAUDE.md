# Allied-FeedOps Project Memory

## Project Overview

FeedOps is a feed optimization system for Allied Brass that generates optimized product titles, descriptions, and lifestyle images for Google Merchant Center, Bing, and Shopify. It uses LLMs to create content that passes Google's structured data requirements while incorporating SEO keywords.

**Business Goal**: Improve product feed quality to increase CTR, conversions, and ROAS on Shopping ads.

## Live Deployment

| Resource | URL/ID |
|----------|--------|
| **Live Dashboard** | https://allied-feedops-nqhv5z5vpypgcikbr8hhzy.streamlit.app/ |
| **Supabase Project** | `qezuszwufortkiutlhym` |
| **Deployment** | Streamlit Cloud (auto-deploys from GitHub `master` branch) |

## MCP Server Defaults

- **Google Analytics**: Always use the **Allied Brass - GA4 (Old)** property when querying Google Analytics data.
- **Google Ads**: Always use customer ID **6253381786** when querying Google Ads data.
- **Supabase**: Use project ID `qezuszwufortkiutlhym` for all Supabase MCP queries.

## LLM Stack

| Purpose | Model | Provider |
|---------|-------|----------|
| **Title/Description Generation** | GPT-5.2 | OpenAI (`src/feedops/providers/openai_provider.py`) |
| **Fallback Text Generation** | Gemini | Google (`src/feedops/providers/gemini_provider.py`) |
| **Lifestyle Image Generation** | `gemini-3-pro-image-preview` | Google Gemini Imagen |
| **Image Scoring/Evaluation** | `gemini-2.0-flash` | Google Gemini Flash |

The LLM provider is selected via `src/feedops/providers/factory.py` - OpenAI is preferred if `OPENAI_API_KEY` is set, otherwise falls back to Gemini.

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

## Running Locally

```bash
# Main unified dashboard (recommended)
PYTHONPATH=src streamlit run streamlit_app.py

# Review dashboard only
PYTHONPATH=src streamlit run src/feedops/quality/review_dashboard.py

# Run tests
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
| Performance dashboard | `streamlit_app_performance.py` |
| Quality scoring | `src/feedops/quality/scorer.py` |
| GMC feed integration | `src/feedops/integrations/google_sheets.py` |
| Optimization pipeline | `src/feedops/pipeline/optimize.py` |
| Content generator | `src/feedops/pipeline/generator.py` |
| LLM provider factory | `src/feedops/providers/factory.py` |
| OpenAI provider (GPT-5.2) | `src/feedops/providers/openai_provider.py` |
| Gemini provider | `src/feedops/providers/gemini_provider.py` |
| Lifestyle image generation | `src/feedops/pipeline/lifestyle_images.py` |
| Supabase migrations | `supabase/migrations/` |
| Pilot selection report | `dashboard_data/lifestyle-eval/reports/pilot-selection-report-detailed.md` |
| Product catalog | `data/Product Catalog.csv` |
| Generated content (local) | `dashboard_data/*/{platform}-patch-{sku}.json` |

## Recent Changes (2026-02)

- **Database Schema Overhaul**: Unified SQLite and Supabase column names for consistency
- **Variant Approvals**: Added per-finish approval tracking (`variant_approvals` table)
- **Auto-derive Status**: Approval status auto-derives from element-level approvals (title/desc/image)
- **Variant Index**: Added `finish` and `finish_code` columns for product mapping
- **Published SKU Tracking**: Real implementation of `get_published_skus()` for SQLite
- **Environment Filtering**: `get_publish_history()` now supports environment parameter
- **First Production Publish**: SKU 1051 (Paper Towel Holders) published to production on 2026-02-03

## Known Issues

### Generated Content Still Local (NEXT PRIORITY)
Titles/descriptions are stored in local JSON patch files (`dashboard_data/*/{platform}-patch-{sku}.json`), not in Supabase. Dashboard reads from GitHub repo files.

### Description Quality vs. Readability (NEEDS INVESTIGATION)
Descriptions score 90% on internal quality metrics but sound robotic. Example:
```
"Finished in Antique Brass, shower basket, 18.75 in L x 2.25 in H x 4.13 in W, solid brass wall mount oval combination shower caddy..."
```

**Root causes identified:**
- Prompt has too many mechanical rules that create compliance-seeking behavior
- Scoring rewards attribute density but not readability
- Finish injection creates awkward sentence openings
- No validation against actual search queries

**Research completed** (in `docs/titles_descriptions_independent_research/`):
- `Product Listing Optimization Research.md` - Algorithmic and psychological research
- `compass_artifact_wf-f630d2a3-044d-4d0c-87af-8f3f823e6bc9_text_markdown.md` - Title/description optimization
- `Youtube-video-transcript.md` - Practical feed optimization tactics
- `Product Title & Description Optimization for Revenue & Ad Efficiency.docx.md` - Revenue impact research

**Key insights from research:**
- 95% of buying decisions are emotional (System 1), then rationalized (System 2)
- Descriptions should reduce cognitive load and uncertainty
- Match search intent, not just include keywords
- Answer the 3 questions buyers have before purchasing

**Investigation prompt:** See `docs/prompts/description-optimization-investigation.md` for a comprehensive prompt to use in a fresh chat session to investigate and fix this with an unbiased perspective.

## GMC Offer ID Format

Google Merchant Center offer IDs follow this pattern:
```
shopify_us_{shopify_product_id}_{shopify_variant_id}
```

Example for SKU 1051:
- Shopify Product ID: `4545063682180`
- Offer IDs: `shopify_us_4545063682180_32128479625348`, `shopify_us_4545063682180_32128479559812`, etc.

**Important**: The `us` is lowercase. When querying Google Ads shopping_performance_view, use `%{shopify_product_id}%` to match all variants.

## Supabase Tables

| Table | Purpose |
|-------|---------|
| `sku_approvals` | SKU-level approval (title_approved, description_approved, image_approved) |
| `variant_approvals` | Per-finish approval tracking |
| `publish_batches` | Batch management |
| `batch_sku_assignments` | SKU-to-batch mapping |
| `publish_events` | Audit log of all publish actions |
| `performance_baselines` | Pre-optimization metrics baseline |
| `performance_snapshots` | Post-publish performance metrics |

**Not yet in Supabase** (stored locally): `generated_content`, `generated_images`, `generation_jobs`

## Pilot SKUs (40 total)

The current pilot batch includes SKUs across 24 categories. See `data/pilot_sku_selection/selected_master_skus.txt` for the full list.

**Excluded from pilot** (top revenue protection): CL-55, FR-23, TD-23, CL-28-30, CL-54

## Performance CLI Commands

```bash
# Capture performance baseline (requires Google Ads API credentials)
PYTHONPATH=src GOOGLE_ADS_API_ENABLED=1 GOOGLE_ADS_CUSTOMER_ID=6253381786 \
  python -m feedops.cli.main baseline --sku 1051 --platform google \
  --start 2025-11-01 --end 2025-11-30 \
  --offer-id "shopify_us_4545063682180_32128479625348"

# Fetch current performance
PYTHONPATH=src GOOGLE_ADS_API_ENABLED=1 GOOGLE_ADS_CUSTOMER_ID=6253381786 \
  python -m feedops.cli.main fetch --sku 1051 --platform google \
  --start 2025-12-01 --end 2025-12-31 \
  --offer-id "shopify_us_4545063682180_32128479625348"

# Compare baseline vs current
PYTHONPATH=src python -m feedops.cli.main compare --sku 1051 --platform google
```
