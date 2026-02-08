# Allied-FeedOps

## Quick Reference

**Production**:
- Dashboard: https://allied-feed-ops.vercel.app/login
- Pipeline API: https://feedops-pipeline-623866089882.us-east1.run.app
- Supabase: `qezuszwufortkiutlhym`

**Defaults**:
- Google Ads customer ID: `6253381786`
- GA4 property: Allied Brass — GA4 (Old)

## MCP Servers & Skills

**Use these before writing custom code**:

**MCP Servers**:
- `mcp__supabase__*` - Database queries, migrations, schema (`execute_sql` for quick queries)
- `mcp__google-ads-mcp__*` - Ads data, Keyword Planner
- `mcp__merchant-api-devdocs__*` - GMC product data, performance
- `mcp__Apify__*` - Web scraping, competitor analysis
- `mcp__vercel__*` - Deployment logs, management
- `mcp__gcloud__*` / `mcp__cloud-run__*` - GCP operations

**Agents** (via Task tool):
- `merchant-integrator` - Merchant API migrations and integrations

**Skills** (via Skill tool):
- `superpowers:brainstorming` - Before creative work
- `superpowers:systematic-debugging` - When encountering bugs
- `superpowers:test-driven-development` - Before implementation
- `marketing-skills:*` - Copy, SEO, marketing content

## What's Implemented

Prompts `01`-`09`, `14`, `19`-`24`:
- 01-06: Performance, batches, publishing, variant review, settings, regeneration
- 07: Dashboard overview with charts
- 08: SKU selection & generation (tier-based scoring)
- 09: Competitor intelligence (SERP analysis, Apify scraping)
- 14: Search query insights (Google Ads search terms + Keyword Planner)
- 19: Evidence table (product_catalog with vision support)
- 20: SKU review enhancements (hero images, lifestyle approval)
- 21: Variant content review (accordion UI, bulk actions)
- 22: Performance data lifecycle (baseline + snapshots)
- 23: Publishing enhancements (structured fields, Shopify CDN)
- 24: Post-publish monitoring (performance/search delta tracking)

## Content Generation

**Default: Cloud Run Pipeline**
- Location: `src/feedops/api/main.py` (FastAPI)
- Quality: ~75-80/100
- Speed: ~3 minutes per SKU
- Use for: Bulk generation (50+ SKUs)

**Experimental: 6-Agent Pipeline**
- Status: Manual execution only (not in UI)
- Quality: 87.2/100 avg (range: 82-98)
- Speed: ~6 minutes per SKU (2x slower)
- Use for: High-value SKUs, gold standard examples

**Hybrid Multi-SKU Generation** (NEW)
- Auto-detects product families (e.g., DMF-2/2X, 2/3X, 2/4X, 2/5X)
- Base SKU: Full generation
- Variants: Adaptation (60% cost savings)
- See: `docs/architecture/content-generation-hybrid.md`

## Key Database Tables

**Content & Approvals**:
- `sku_approvals` / `variant_approvals` - Approval status
- `generated_content` - Title/description (baseline_content, candidate_content, **approved_content**)
- `generated_images` - Lifestyle images (Shopify CDN lifecycle)
- `variant_finish_sentences` - Finish-specific content for variants
- `prompt_templates` - Gold standard examples (system prompt lives in code)

**Publishing**:
- `publish_batches` / `batch_sku_assignments` - Batch management
- `publish_events` - Audit log with content snapshots for rollback

**Performance**:
- `performance_baselines` - 30-day pre-publish metrics (avg impressions/clicks/CTR/CVR)
- `performance_snapshots` - Post-publish tracking with days_since_publish

**Data Pipeline**:
- `variant_index` - Maps master_sku ↔ gmc_offer_id (THE SOURCE OF TRUTH)
- `product_catalog` - 75,770 variants with full product data

**Search**:
- `search_queries` - Variant-level Google Ads search terms
- `keyword_metrics` - Keyword Planner data (cached, 30-day TTL)

**Conventions**:
- Column naming: `approval_status` (not `status`), `notes` (not `revision_notes`), `approved_by/approved_at`
- JSONB: Store as text strings, parse with `(column#>>'{}')::jsonb` before array operations
- LATERAL joins: `CROSS JOIN LATERAL jsonb_array_elements_text((item_ids#>>'{}')::jsonb)` to expand arrays
- Case-sensitive: Use `LOWER()` on both sides or `regexp_replace()` for joins

## Critical Patterns

### Multi-SKU Products ⚠️

**Multiple master_skus can share same product_id**. Example:
- DMF-2/2X, DMF-2/3X, DMF-2/4X, DMF-2/5X all share `4539975336068`

**Impact**:
- Google Ads aggregates at product_id level (not master_sku)
- Query logic must account for this (product_id-based matching)
- Content generation needs variant adaptation (not find/replace)

See: `docs/architecture/multi-sku-pattern.md`

### Offer ID Format

GMC offer IDs: `shopify_US_{product_id}_{variant_id}` (uppercase `US`)

**IMPORTANT**: Database stores lowercase format, but publishing to Google Sheets requires uppercase US.
**Fix applied**: `google-sheets.ts` transforms on publish: `shopify_us_` → `shopify_US_`

### SKU Format Handling

**Database**: Slash separators (`WP-2/16-GAL`, `DMF-2/2X`)
**URLs**: Hyphens only (`/review/DMF-2-2X`)
**Conversion**: Use `getSkuCandidates` in `dashboard/src/lib/sku-utils.ts`

### GMC Policy Guardrails

**Critical**: Never invent specs/claims not in product data
**AI content**: Use `structured_title`/`structured_description` with `digital_source_type=trained_algorithmic_media`
**Structured-only mode**: When `FEEDOPS_GMC_STRUCTURED_ONLY=1`, omit standard title/description

### Component Patterns (Dashboard)

**Card rendering**: Components like SearchInsightsCard render Card internally - don't wrap in additional Card
**Grid layouts**: Use `grid-cols-1 lg:grid-cols-2` for 50/50 split (mobile stacks, desktop side-by-side)
**TypeScript**: `ContentRecord` interface duplicated in page.tsx and SkuReviewClient.tsx - must match exactly
**Optional chaining**: Use `?.property ?? null` when component expects `string | null`

## Key Locations

**Dashboard**:
- Pages: `dashboard/src/app/(dashboard)/**`
- API routes: `dashboard/src/app/api/**`
- Regeneration core: `dashboard/src/lib/regeneration/core.ts`
- Prompts (SINGLE SOURCE): `dashboard/src/lib/regeneration/prompts.ts`
- Evidence builder: `dashboard/src/lib/evidence/*`
- Multi-SKU detection: `dashboard/src/lib/multi-sku-detection.ts`
- Hybrid generation: `dashboard/src/app/api/sku-selection/generate-hybrid/route.ts`

**Python Pipeline**:
- Cloud Run API: `src/feedops/api/main.py`
- Google Ads: `src/feedops/integrations/google_ads_performance.py`
- Search terms: `src/feedops/integrations/google_ads_search_terms.py`

**Publishing**:
- Google Sheets: `dashboard/src/lib/publishing/google-sheets.ts`
- Shopify: `dashboard/src/lib/publishing/shopify.ts`
- Variant expansion: `dashboard/src/lib/publishing/expand-variants.ts`

## Deployment (Auto-Deploy on Push to Master)

**Two pipelines auto-deploy**:
1. **Cloud Run** (Python): Push → Cloud Build trigger → Deploy
2. **Vercel** (Dashboard): Push → Vercel auto-deploy

**Check build status**:
```bash
gcloud builds list --project=bobbys-project-346400 --limit=5
```

**Service accounts**:
- Build: `profit-pilot-build@bobbys-project-346400.iam.gserviceaccount.com`
- Runtime: `profit-pilot-runtime@bobbys-project-346400.iam.gserviceaccount.com`

**GCP secrets** (all 8 already exist, bound to runtime SA):
- feedops-openai-api-key
- feedops-supabase-url / feedops-supabase-key
- feedops-google-ads-developer-token / client-id / client-secret / refresh-token / login-customer-id

## Cloud Run Service

**Service URL**: https://feedops-pipeline-623866089882.us-east1.run.app

**Endpoints**:
- `GET /health` - Health check with Supabase status
- `POST /optimize-sku` - Single SKU content generation
- `POST /regenerate` - Content regeneration with feedback
- `POST /batch-optimize` - Batch job creation
- `GET /batch-status/{job_id}` - Batch job progress
- `POST /performance/capture-baseline` - Capture performance baselines
- `POST /search-insights/sync` - Sync search terms from Google Ads
- `POST /hybrid-generate` - Hybrid multi-SKU generation (base + variants)

**CRITICAL: Cloud Run Background Task Pattern**

FastAPI `BackgroundTasks` are killed when containers scale to zero or during deployments.

**Solution**: Use `run_async_in_thread()` helper in `src/feedops/api/main.py`
- Pattern: Non-daemon threads with dedicated asyncio event loops that survive HTTP response
- Used by: `/hybrid-generate`, `/search-insights/sync`, `/batch-optimize`
- **Limitation**: Jobs still terminate during deployments (expected behavior)
- See: `docs/audit/background-task-fix-2026-02-08.md` for full analysis

**Pattern**:
```python
# Replace this (killed by container lifecycle)
background_tasks.add_task(process_job, job_id=job_id)

# With this (survives until completion or deployment)
run_async_in_thread(process_job, job_id=job_id)
```

## Local Development

### Dashboard

```bash
cd dashboard
npm install
npm run dev  # http://localhost:3000
npm run build  # Verify TypeScript before deploy
npm run lint
```

**Environment** (`.env.local`):
```
NEXT_PUBLIC_SUPABASE_URL=
NEXT_PUBLIC_SUPABASE_ANON_KEY=
SUPABASE_SERVICE_ROLE_KEY=
SHOPIFY_STORE_URL=
SHOPIFY_ACCESS_TOKEN=
```

### Python Pipeline

```bash
uv venv
uv pip install -e ".[dev]"
PYTHONPATH=./src .venv/bin/python -m pytest tests/ -v
```

## Common Workflows

### Test Before Commit

```bash
cd dashboard && npm run build && npm run lint
```

### Check Deployment

```bash
# Vercel logs
# Use Vercel MCP or dashboard

# Cloud Run logs
gcloud run services logs read feedops-pipeline --project=bobbys-project-346400 --limit=50
```

### Database Queries

```typescript
// Use Supabase MCP for quick queries
mcp__supabase__execute_sql

// Check schema
SELECT column_name, data_type
FROM information_schema.columns
WHERE table_name = 'performance_baselines';
```

## Data Pipeline

**Flow**: Acatalog.csv → variant_index → Google Sheets → GMC → Google Ads

**Key facts**:
- GMC does NOT auto-sync from Shopify (custom feed via Google Sheets)
- variant_index is source of truth (72,023 rows)
- 99.7% of "missing data" issues are query logic problems (not data sync)

See: `docs/architecture/data-pipeline.md`

## Publishing Workflow

1. **Generate**: Regeneration API → `candidate_content`
2. **Approve**: User approval → `approved_content` (immutable)
3. **Publish**: Batch publish reads `approved_content`
4. **Expand**: Google/Bing get {FINISH_NAME} → 28 variants
5. **Update**: Google Sheets rows updated by gmc_offer_id
6. **Audit**: `publish_events` stores snapshots for rollback

**Shopify**:
- Product-level content only (no variant-specific titles/descriptions)
- Lifestyle images: variant-specific via `productVariantAppendMedia`
- CDN lifecycle: Supabase Storage → Shopify CDN → Google Sheets

## Automated Data Collection

SKU selection, regeneration, and batch generation APIs **automatically** trigger data collection:
- **Performance baselines**: 30-day pre-optimization metrics (if missing/stale >60 days)
- **Search query data**: Google Ads search terms + Keyword Planner (if stale >7 days)
- **Non-blocking**: Operations continue even if collection fails
- **Evidence-driven**: Auto-feeds into evidence table for content generation

Functions: `ensureSkuData()`, `ensureAllData()` in `dashboard/src/lib/data-collection/ensure-data.ts`

## Content Storage

**IMPORTANT**: Generated content stored in **Supabase only** (not git)
- `dashboard_data/` is empty (all evaluation data archived)
- Historical data: Branch `archive/full-snapshot-2026-02-03`
- Use regeneration API to create new content

## Git Conventions

```bash
# Format: type: description
git commit -m "fix: resolve baseline capture query logic

Co-Authored-By: Claude Sonnet 4.5 <noreply@anthropic.com>"

# Push triggers auto-deploy
git push origin master
```

## Troubleshooting

**Baseline capture issues**: See `docs/troubleshooting/baseline-capture.md`
- Most common: offer ID case mismatch (uppercase vs lowercase)
- Second: missing campaign type in query
- Third: multi-SKU product query logic

**Dashboard issues**:
- Vercel logs via MCP or dashboard
- Browser console for client errors
- Test: `/api/health`

**Pipeline issues**:
- Cloud Run logs: `gcloud run services logs read feedops-pipeline --project=bobbys-project-346400 --limit=50`
- Test: `curl https://feedops-pipeline-623866089882.us-east1.run.app/health`

## Documentation

**Architecture** (how systems work):
- `docs/architecture/multi-sku-pattern.md` - Product families, query logic
- `docs/architecture/data-pipeline.md` - Complete pipeline flow
- `docs/architecture/content-generation-hybrid.md` - Multi-SKU generation

**Troubleshooting** (when things break):
- `docs/troubleshooting/baseline-capture.md` - Performance capture debugging

**Investigation History** (root cause analyses):
- `docs/audit/SUMMARY-2026-02-08.md` - Baseline capture investigation
- `docs/audit/variant-id-mismatch-root-cause-2026-02-08.md` - Multi-SKU discovery
- `docs/audit/hybrid-generation-implementation-2026-02-08.md` - Hybrid generation

**Prompts** (implementation specs):
- `docs/prompts/01-09.md` - Implemented features
- `docs/prompts/FUTURE-IDEAS.md` - Backlog
