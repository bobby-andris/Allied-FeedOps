# Allied-FeedOps (Project Memory — Keep Short)

## Canonical UI / Production

- **Next.js Dashboard (Vercel)**: `https://allied-feed-ops.vercel.app/login`
- **Supabase project**: `qezuszwufortkiutlhym`

**Access**

- Do **not** store login passwords in git. Share test credentials via a password manager / internal note.

## Defaults (for integrations / tooling)

- **Google Ads customer ID**: `6253381786`
- **GA4 property**: Allied Brass — GA4 (Old)

### Google Ads API Capabilities

- **Search Terms**: `search_term_view` - actual queries triggering Shopping ads
  - Note: Cannot get `product_item_id` in same query - product matching done via post-processing
- **Keyword Planner**: `KeywordPlanIdeaService` - search volume, competition, CPC estimates
  - `GenerateKeywordHistoricalMetrics` - get avg monthly searches, competition index (0-100), CPC ranges
  - `GenerateKeywordIdeas` - discover related keywords from seeds (keywords, URLs, sites)
  - Rate limited - cache results (metrics update monthly)

## Available MCP Servers & Skills (use these!)

**MCP Servers** - Use these for database operations, external APIs, and browser automation:

- **Supabase MCP** (`mcp__supabase__*`): Use for direct database queries, migrations, and schema inspection. Prefer `mcp__supabase__execute_sql` for quick queries instead of writing scripts. Available tools: `execute_sql`, `apply_migration`, `list_tables`, `get_project`, etc.
- **Playwright MCP** (`mcp__plugin_playwright_playwright__*`): Use for visual verification, UI testing, and screenshots. Tools: `browser_navigate`, `browser_take_screenshot`, `browser_click`, `browser_snapshot`, etc.
- **Apify MCP** (`mcp__Apify__*`): Use for web scraping, competitor analysis, and data extraction. Search actors first with `search-actors`.
- **Google Ads MCP** (`mcp__google-ads-mcp__*`): Use for Ads data queries and Keyword Planner.
- **Merchant API MCP** (`mcp__merchant-api-devdocs__*`): Use for GMC product data, performance metrics, and feed management. Tools: `query_mapi_docs` (documentation), `find_mapi_code_sample` (code examples). Queries: `product_performance_view`, `product_view`, `price_competitiveness_product_view`.
- **Analytics MCP** (`mcp__analytics-mcp__*`): Use for GA4 reporting.
- **Context7 MCP** (`mcp__plugin_context7_context7__*`): Use to fetch up-to-date library documentation.
- **Vercel MCP** (`mcp__vercel__*`): Use for deployment management and logs.
- **GCloud MCP** (`mcp__gcloud__*`): Use for GCP operations via gcloud CLI.
- **Cloud Run MCP** (`mcp__cloud-run__*`): Use for Cloud Run deployments and service management.

**Agents** - Use via Task tool with `subagent_type`:

- **merchant-integrator**: Use when migrating from Content API for Shopping to Merchant API, or implementing new Google Merchant API features. Handles authentication setup and integration patterns.

**Skills** - Invoke with `Skill` tool for specialized workflows:

- `superpowers:brainstorming` - Use before any creative/feature work
- `superpowers:systematic-debugging` - Use when encountering bugs
- `superpowers:test-driven-development` - Use before writing implementation code
- `superpowers:verification-before-completion` - Use before claiming work is done
- `marketing-skills:*` - Use for copy, SEO, and marketing content

**Key rule**: Always check if an MCP tool or skill can accomplish the task before writing custom code or scripts.

## What's implemented (dashboard prompts)

- **Implemented**: `docs/prompts/01`–`09`, `14`, `19`, `20`, `21`
  - 01-06: performance, batches, publishing, variant review, settings health, regeneration
  - 07: dashboard overview with charts (ApprovalChart, PlatformBreakdown, QualityDistribution, RecentActivity)
  - 08: SKU selection & generation (`/generate` page, `/api/sku-selection/*` routes, tier-based scoring)
  - 09: Competitor intelligence (`/competitors` page, SERP analysis, marketplace scraping via Apify MCP)
  - 14: Search query insights (`/search-insights` page, Google Ads search terms + Keyword Planner enrichment, variant-level tracking)
  - 19: Evidence table for rich product context (product_catalog table, evidence builder, vision support)
  - 20: SKU review page enhancements (product hero images, lifestyle image approval workflow with AI vs user selection, per-platform current content comparison)
  - 21: Variant content review (accordion UI to view/approve all 28 variants per platform with bulk actions)
- **Next up**: `docs/prompts/23` — Publishing enhancements (structured title/description, lifestyle images, Shopify strategy)

## Supabase schema (tables we rely on)

- `sku_approvals` (SKU-level approvals)
- `variant_approvals` (per-finish approvals)
- `variant_index` (maps `master_sku` ⇄ `gmc_offer_id`, finish info)
- `publish_batches`, `batch_sku_assignments` (batch mgmt)
- `publish_events` (audit log with content snapshots: `published_title`, `published_description`, `variant_count`, `content_version` for rollback)
- `performance_baselines`, `performance_snapshots` (performance)
- `batch_generation_jobs`, `batch_generation_job_skus` (batch content generation)
- `competitor_scrape_jobs`, `competitor_listings`, `competitor_patterns` (competitor intelligence)
- `product_catalog` (75,770 variants with full product data for evidence table - narrative_copy, bullets, dimensions, images)
- `generated_content` (title/description content with baseline_content, candidate_content, **approved_content**, quality_score per platform; **approved_at**, **approved_version** for publishing locks)
- `regeneration_history` (prompt audit trail with system_prompt, user_prompt, model_version, prompt_hash)
- `generated_images` (lifestyle images with ai_selected, user_selected, use_for_master, approval_status, gmc tracking)
- `lifestyle_image_selections` (audit trail for image selection decisions)
- `variant_finish_sentences` (product+finish tailored sentences for Google/Bing variant content generation)
- `prompt_templates` (gold standard examples + category guidance; system prompt lives in code, DB `system_prompt` column is ignored)
- `search_queries` (variant-level search terms with GMC offer ID mapping, Keyword Planner metrics)
- `search_queries_by_master_sku` (aggregated search data by master SKU)
- `keyword_metrics` (cached Keyword Planner data - search volume, competition, CPC; 30-day TTL)
- `search_query_sync_jobs` (sync job tracking for Google Ads search term imports)

**Column naming conventions (do not drift)**

- Use `approval_status` (not `status`)
- Use `notes` (not `revision_notes`)
- Use `approved_by` / `approved_at` (not `reviewed_by` / `reviewed_at`)
- Batches use `name` / `notes` / `executed_at`

## GMC / Google policy guardrails (critical)

- **No hallucinations**: never invent specs/claims not in product data.
- **AI text compliance**: prefer `structured_title` / `structured_description` with `digital_source_type=trained_algorithmic_media`.
- **Structured-only mode**: when `FEEDOPS_GMC_STRUCTURED_ONLY=1`, omit standard `title`/`description` so Google does not ignore structured fields.

## Future TODOs

- **Switch to `structured_title`/`structured_description` for GMC**: Google recommends AI-generated content use `structured_title` and `structured_description` attributes (compound format: `trained_algorithmic_media:"content text"`). Currently we write to plain `title`/`description` columns. Need to: add `structured_title` and `structured_description` columns to the supplemental feed sheet, enable `FEEDOPS_GMC_STRUCTURED_ONLY=1`, and stop writing plain title/description for AI content. See GMC product data spec for details.
- **Lifestyle image publishing**: The Google Sheets code supports a `lifestyle_image_link` column (auto-creates if missing), but the SKU and batch publish routes do NOT pass image URLs through. Need to: query `generated_images` for approved lifestyle images during publish, pass `image_url` to the Google Sheets function, and implement Shopify image publishing via the `productCreateMedia` GraphQL mutation.
- **Shopify variant vs master SKU strategy**: Currently Shopify publish updates the product-level title/description (master SKU). Shopify variants are finish-specific but variant-level title/description is limited in Shopify's data model. Need to decide: use metafields for variant content? Update variant option names? Leave as product-level only?

## Offer ID format (Google / Ads joins)

GMC offer IDs:
`shopify_US_{shopify_product_id}_{shopify_variant_id}` (note uppercase `US`)

## Key dashboard locations

- Pages: `dashboard/src/app/(dashboard)/**`
- API routes: `dashboard/src/app/api/**`
- Supabase query layer: `dashboard/src/lib/supabase/{queries.ts,types.ts}`
- Publishing libs: `dashboard/src/lib/publishing/*`
- Regeneration prompts (SINGLE SOURCE OF TRUTH): `dashboard/src/lib/regeneration/prompts.ts` (system prompt, finish list, platform context, validation). Title structure: Google/Bing = `{FINISH_NAME} [Product] [Specs] - [Collection Name] Collection - Allied Brass`; Shopify = inner core (no finish, no brand, "Collection" suffix required)
- Gold standard examples: `docs/gold-standard-examples.json` (10 examples with cross-platform title consistency)
- Regeneration API: `dashboard/src/app/api/regenerate/route.ts` (single-SKU generation with feedback; model default `gpt-5.2`)
- Regeneration core: `dashboard/src/lib/regeneration/core.ts` (shared generation logic for batch + single-SKU)
- Evidence table builder: `dashboard/src/lib/evidence/*` (builds rich product context for LLM prompts, includes search query insights)
- Search query evidence: `src/feedops/integrations/search_query_insights.py` (Python) and `dashboard/src/lib/evidence/search-queries.ts` (TypeScript)
- SKU scoring: `dashboard/src/lib/sku-scoring.ts` (tier-based selection algorithm)
- SKU selection API: `dashboard/src/app/api/sku-selection/route.ts` (scored recommendations)
- Batch generation API: `dashboard/src/app/api/sku-selection/generate/route.ts` (start batch jobs)
- Dashboard charts: `dashboard/src/components/dashboard/*.tsx`
- Competitor intelligence: `dashboard/src/app/(dashboard)/competitors/page.tsx`, `/api/competitors/*`
- Pattern extraction: `dashboard/src/lib/competitors/pattern-extraction.ts`
- Review components: `dashboard/src/components/review/*.tsx` (ProductHeroImage, LifestyleImageReview, ImageApprovalCard, SearchInsightsSummary)
- Image approval API: `dashboard/src/app/api/review/images/approve/route.ts`
- Image selection API: `dashboard/src/app/api/review/images/select/route.ts`
- Variant approvals API: `dashboard/src/app/api/variants/approvals/route.ts`, `/bulk/route.ts`
- Variant content utilities: `dashboard/src/lib/variant-content.ts` (generates variant titles/descriptions from base template)
- Variant expansion for publishing: `dashboard/src/lib/publishing/expand-variants.ts` (expands `{FINISH_NAME}` templates to 28 unique variants)
- Finish data: `dashboard/src/lib/finish-data.ts` (30 finish definitions; 28 used for content generation, excludes Military Camo and Red White and Blue)
- Pipeline API: `src/feedops/api/main.py` (FastAPI endpoints for Cloud Run)
- Pipeline client: `dashboard/src/lib/pipeline-client.ts` (TypeScript client for Cloud Run API)
- Prompt loader: `dashboard/src/lib/prompts/loader.ts` (loads gold standard examples + category guidance from Supabase; system prompt is NOT loaded from DB)
- Python prompt loader: `src/feedops/api/prompt_loader.py` (Python equivalent with fallback prompts)
- Search insights page: `dashboard/src/app/(dashboard)/search-insights/page.tsx`
- Search insights API: `dashboard/src/app/api/search-insights/*.ts` (sync triggers, job status)
- Search insights components: `dashboard/src/components/search-insights/*.tsx` (QueryTable, FinishInsights, GapAnalysis)
- Python search terms client: `src/feedops/integrations/google_ads_search_terms.py` (SearchTermsClient, KeywordPlannerClient)

## Deployment & CI/CD (ALREADY FULLY CONFIGURED — DO NOT RE-CREATE)

**IMPORTANT: All deployment infrastructure is already set up and working. DO NOT:**
- Create new GCP secrets (they already exist)
- Create new Cloud Build triggers (already exists)
- Run manual `gcloud run deploy` commands (CI/CD handles this automatically)
- Set up GitHub connections (already authorized)

### How Deployment Works

**Two auto-deploy pipelines — both trigger on push to `master`:**

1. **Cloud Run (Python pipeline)**: Push to master → Cloud Build trigger `feedops-pipeline-deploy` → builds Docker image → deploys to Cloud Run automatically
2. **Vercel (Next.js dashboard)**: Push to master → Vercel auto-deploys automatically

**You do NOT need to deploy manually. Just push to master and both services update.**

### Cloud Run Service

**Service URL:** https://feedops-pipeline-623866089882.us-east1.run.app

**Endpoints:**
- `GET /health` - Health check with Supabase status
- `POST /optimize-sku` - Single SKU content generation
- `POST /regenerate` - Content regeneration with feedback
- `POST /batch-optimize` - Batch job creation
- `GET /batch-status/{job_id}` - Batch job progress
- `POST /search-insights/sync` - Sync search terms from Google Ads (used by Search Insights page)
- `GET /search-insights/sync/{job_id}` - Get sync job status
- `POST /search-insights/enrich` - Enrich keywords with Keyword Planner data
- `GET /search-insights/terms` - Query stored search terms

### Cloud Build Trigger (ALREADY EXISTS)

- **Name**: `feedops-pipeline-deploy`
- **Source**: `bobby-andris/Allied-FeedOps` → branch `^master$`
- **Config**: `cloudbuild.yaml`
- **Build SA**: `profit-pilot-build@bobbys-project-346400.iam.gserviceaccount.com`
- **Runtime SA**: `profit-pilot-runtime@bobbys-project-346400.iam.gserviceaccount.com`

To check build status: `gcloud builds list --project=bobbys-project-346400 --limit=5`

### GCP Secrets (ALL ALREADY CREATED AND BOUND)

All secrets below already exist in Secret Manager and are already bound to the runtime service account. Do NOT try to create or re-create them:

- `feedops-openai-api-key`
- `feedops-supabase-url`
- `feedops-supabase-key`
- `feedops-google-ads-developer-token`
- `feedops-google-ads-client-id`
- `feedops-google-ads-client-secret`
- `feedops-google-ads-refresh-token`
- `feedops-google-ads-login-customer-id`

### Manual Deploy (ONLY if CI/CD is broken)

Only use this as a last resort if the Cloud Build trigger is not working:
```bash
gcloud run deploy feedops-pipeline --source . --project=bobbys-project-346400 --region=us-east1 \
  --set-secrets="OPENAI_API_KEY=feedops-openai-api-key:latest,SUPABASE_URL=feedops-supabase-url:latest,SUPABASE_KEY=feedops-supabase-key:latest,GOOGLE_ADS_DEVELOPER_TOKEN=feedops-google-ads-developer-token:latest,GOOGLE_ADS_CLIENT_ID=feedops-google-ads-client-id:latest,GOOGLE_ADS_CLIENT_SECRET=feedops-google-ads-client-secret:latest,GOOGLE_ADS_REFRESH_TOKEN=feedops-google-ads-refresh-token:latest,GOOGLE_ADS_LOGIN_CUSTOMER_ID=feedops-google-ads-login-customer-id:latest" \
  --set-env-vars="GOOGLE_ADS_CUSTOMER_ID=6253381786" \
  --service-account=profit-pilot-runtime@bobbys-project-346400.iam.gserviceaccount.com \
  --build-service-account=projects/bobbys-project-346400/serviceAccounts/profit-pilot-build@bobbys-project-346400.iam.gserviceaccount.com \
  --allow-unauthenticated --memory=2Gi --cpu=2 --timeout=900 --max-instances=10
```

## Run locally

### Dashboard

```bash
cd dashboard
npm install
npm run dev
```

### Python (pipeline/tests still in repo)

```bash
uv venv
uv pip install -e ".[dev]"
PYTHONPATH=./src .venv/bin/python -m pytest tests/ -v
```

## Publishing Workflow

**Approval → Publishing flow:**

1. **Content Generation**: Regeneration API stores templates in `generated_content.candidate_content` with `{FINISH_NAME}` placeholder
2. **Approval**: When content is approved, `candidate_content` → `approved_content` (immutable snapshot with `approved_at`, `approved_version`)
3. **Publishing**: Batch publish reads `approved_content`, validates `sku_approvals.approval_status = 'approved'`
4. **Variant Expansion**: For Google/Bing, `expand-variants.ts` replaces `{FINISH_NAME}` per variant using `variant_finish_sentences` table
5. **Google Sheets**: Updates existing rows (by `gmc_offer_id`) or appends new rows - prevents duplicate entries
6. **Audit Trail**: `publish_events` stores content snapshots (`published_title`, `published_description`) for rollback capability

**Key constraint**: Content cannot be published unless approved. Regenerating content after approval does NOT change what will be published (uses `approved_content`, not `candidate_content`).

## Generated content storage

**IMPORTANT**: Generated content (titles, descriptions, images) must now be stored in Supabase, not in git.

- `dashboard_data/` is empty (only README.md) - all evaluation data archived
- Dashboard must read from Supabase `generated_content` and `generated_images` tables
- Use regeneration API to create new content

## Historical archive

All previous data (14,000+ generated files, evaluation data, research docs) preserved in:

- **Branch**: `archive/full-snapshot-2026-02-03`
- **Tag**: `backup/pre-dashboard-cleanup-2026-02-03`

To restore archived content:

```bash
# View what's in the archive
git show archive/full-snapshot-2026-02-03:dashboard_data/

# Restore specific files
git checkout archive/full-snapshot-2026-02-03 -- dashboard_data/batch-40sku-20260130-144146/
```
