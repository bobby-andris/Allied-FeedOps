# External Integrations

**Analysis Date:** 2026-02-11

## APIs & External Services

**Content Generation (LLM Providers):**
- OpenAI GPT-5.2 - Primary content generation model
  - SDK/Client: `openai` 4.77.0 (TypeScript in dashboard, Python via providers)
  - Auth: `OPENAI_API_KEY` (GCP Secret Manager)
  - Usage: `src/feedops/providers/openai_provider.py`
  - Features: JSON mode, structured output, token logging

- Google Gemini 3 Flash Preview - Fallback LLM provider
  - SDK/Client: `google-genai` 1.0+ (Python)
  - Auth: `GEMINI_API_KEY` (GCP Secret Manager)
  - Usage: `src/feedops/providers/gemini_provider.py`
  - Implementation: Async via `client.aio`

**Search & Advertising:**
- Google Ads API - Performance metrics, search terms, keyword research
  - SDK/Client: `google-ads-api` 23.0.0 (TypeScript) and `google-ads` 28.4.1+ (Python)
  - Auth: OAuth 2.0 + Developer Token (4 GCP Secrets):
    - `GOOGLE_ADS_CLIENT_ID`
    - `GOOGLE_ADS_CLIENT_SECRET`
    - `GOOGLE_ADS_REFRESH_TOKEN`
    - `GOOGLE_ADS_DEVELOPER_TOKEN`
  - Login Customer ID: `GOOGLE_ADS_LOGIN_CUSTOMER_ID` (Account-level access)
  - Usage: `src/feedops/integrations/google_ads.py`, `src/feedops/integrations/google_ads_performance.py`, `src/feedops/integrations/google_ads_search_terms.py`, `dashboard/src/lib/google-ads.ts`
  - Features: Product performance, search terms sync, Keyword Planner (rate-limited), keyword historical metrics
  - Default Customer ID: `6253381786` (Allied Brass account)
  - Execution modes: API mode (preferred) or MCP mode (Cursor-only, disabled in repo)

**Content Publishing:**
- Google Sheets API - GMC supplemental feed updates
  - SDK/Client: `googleapis` 171.2.0 (TypeScript) and `gspread` 6.0+ (Python)
  - Auth: Service account (base64-encoded JSON in environment)
    - Env var: `GOOGLE_SERVICE_ACCOUNT_KEY` (base64-encoded JSON)
    - Scope: Spreadsheets + Drive API
  - Usage: `dashboard/src/lib/publishing/google-sheets.ts`, `src/feedops/integrations/google_sheets.py`
  - Sheet ID: `GOOGLE_SHEETS_SPREADSHEET_ID`
  - Sheet name: `SupplementalFeedData` (default, configurable via `GOOGLE_SHEETS_SHEET_NAME_STAGING`)
  - Features: Dynamic column header mapping, grid expansion, row updates by offer ID (uppercase `shopify_US_` format), lifecycle image CDN links
  - Critical: Column mapping built from actual sheet headers (no hardcoded defaults)

**Product Catalog & Storefront:**
- Shopify Admin API - Product title/description updates, media uploads
  - SDK/Client: Native GraphQL queries via HTTP (no SDK in dependencies)
  - Auth: `SHOPIFY_ACCESS_TOKEN` (environment variable)
  - Store URL: `SHOPIFY_STORE_URL`
  - API Version: `2026-01`
  - Usage: `dashboard/src/lib/publishing/shopify.ts`, `dashboard/src/lib/storage/upload-lifestyle-image.ts`
  - Features:
    - Product update mutations (title, description)
    - Product media management (variant-level lifestyle images)
    - Tag addition for environment tracking
  - Critical pattern: Use `uploadProductImage()` (not `uploadVariantImage()`) for lifestyle images
  - CDN integration: Supabase Storage → Shopify media → Google Sheets feed

**Competitor Intelligence:**
- Apify Web Scraping Platform - SERP analysis, competitor data
  - SDK/Client: `apify-client` 2.22.0 (TypeScript in dashboard)
  - Auth: `APIFY_TOKEN` (optional, for API mode)
  - Usage: `src/feedops/integrations/apify.py` (stub implementation), `src/feedops/pipeline/competitor_evidence.py`
  - Status: Optional integration (can be enabled via `APIFY_MCP_ENABLED` env var)
  - Features: Competitor title scraping, SERP features, organic search data collection
  - Implementation: MCP-compatible but currently stubbed unless wired at runtime

## Data Storage

**Databases:**
- Supabase (PostgreSQL) - Primary database
  - Connection: `SUPABASE_URL` (project URL), `SUPABASE_KEY` (anon key for client, service role for admin)
  - Client (TypeScript): `@supabase/supabase-js` 2.94.0 with `@supabase/ssr` 0.8.0
  - Client (Python): `supabase` 2.0+
  - Usage:
    - Dashboard: `dashboard/src/lib/supabase/*` (client queries, RLS-protected)
    - Pipeline: `src/feedops/db/supabase_client.py` (service role, admin operations)
  - Key Tables:
    - `generated_content` - Baseline, candidate, approved product content
    - `sku_approvals` / `variant_approvals` - Content approval workflow
    - `performance_baselines` - Pre-optimization 30-day metrics
    - `performance_snapshots` - Post-publish tracking with delta calculations
    - `product_catalog` - All variants with full product data
    - `variant_index` - Master SKU ↔ GMC offer ID mapping (source of truth)
    - `publish_batches` / `batch_sku_assignments` - Publishing workflow
    - `publish_events` - Audit log with content snapshots for rollback
    - `search_queries` - Google Ads variant-level search terms
    - `keyword_metrics` - Keyword Planner cached data
    - `product_lifestyle_images` - Product-level lifestyle images
    - `variant_lifestyle_images` - Variant-level lifestyle images with finish mapping
    - `prompt_templates` - Gold standard examples, category guidance, platform rules
  - Retry logic: Built-in with 3 retries, 0.5s delay for transient errors
  - Health check: `src/feedops/db/supabase_client.py` provides `is_supabase_available()`

**File Storage:**
- Supabase Storage - Lifestyle image temporary staging
  - Bucket: Lifestyle images before CDN migration to Shopify
  - Integration: `dashboard/src/lib/storage/upload-lifestyle-image.ts`
  - Lifecycle: Storage → Shopify CDN → Google Sheets feed reference

**Caching:**
- React Query (TanStack) - In-memory client-side data caching
  - Config: Default 5-minute stale time, no background refetching
  - Usage: Dashboard API routes and data fetching components

- Supabase Realtime (optional) - Not currently integrated, available for live updates

## Authentication & Identity

**Auth Provider:**
- Custom OAuth via Supabase Auth (optional, user authentication)
- Service-to-service: GCP service account authentication
  - Build time: `profit-pilot-build` service account
  - Runtime: `profit-pilot-runtime` service account with secrets bound
  - Scopes: Sheets, Drive, Cloud Run management

**Authorization:**
- Supabase RLS (Row-Level Security) - Dashboard API protection
  - Policy: User ID-based filtering on sensitive tables
- Cloud Run: Allow unauthenticated access (public endpoints, no user auth required)

## Monitoring & Observability

**Error Tracking:**
- Custom logging (no Sentry/Rollbar integration)
  - Python: `logging` module with structured format
  - TypeScript: `console.error()` for client-side, NextResponse for error handling
  - File: `src/feedops/observability/` (log_event, metrics_registry)

**Logs:**
- Python: Structured logs to stdout (picked up by Cloud Run logs)
  - Command: `gcloud run services logs read feedops-pipeline --limit=50`
- Dashboard: Vercel function logs (accessible via Vercel dashboard or MCP)
- Metrics: Basic prometheus-compatible metrics via `metrics_registry` in observability module

**Request Tracing:**
- Correlation ID: `get_request_id()` in observability module
- Context: `request_context` for tracking across async operations

## CI/CD & Deployment

**Hosting:**
- Dashboard: Vercel (Next.js managed hosting)
- Pipeline: Google Cloud Run (containerized Python service)

**CI Pipeline:**
- GitHub Actions (optional, supplementary to Vercel/Cloud Build)
  - Directory: `.github/workflows/` (minimal, auto-deploy is primary)

- Vercel auto-deploy: Push to master → Automatic deployment
  - No manual approval required
  - Config: Managed via Vercel project settings

- Google Cloud Build: Push to master → Automated build and deploy
  - Trigger: `feedops-pipeline-deploy` (cloud-native build)
  - Config: `cloudbuild.yaml` (Docker build → Artifact Registry → Cloud Run)

**Pre-Deployment Checks:**
Required before push (enforced via local development workflow):
1. `cd dashboard && npm run build` - TypeScript compilation + Next.js build
2. `npx tsc --noEmit` - Strict type checking
3. `npm run lint` - ESLint validation
4. Python: `pytest tests/ -v` - Unit test execution

## Environment Configuration

**Dashboard Environment Variables** (`.env.local` for development, Vercel project for production):
- `NEXT_PUBLIC_SUPABASE_URL` - Supabase project URL (public)
- `NEXT_PUBLIC_SUPABASE_ANON_KEY` - Supabase anon key (public, client-side)
- `SUPABASE_SERVICE_ROLE_KEY` - Service role key (private, server-side only)
- `SHOPIFY_STORE_URL` - Shopify storefront URL
- `SHOPIFY_ACCESS_TOKEN` - Shopify API access token
- `FEEDOPS_PIPELINE_URL` - Cloud Run pipeline endpoint (default: https://feedops-pipeline-623866089882.us-east1.run.app)
- `GOOGLE_SERVICE_ACCOUNT_KEY` - Base64-encoded Google service account JSON
- `GOOGLE_SHEETS_SPREADSHEET_ID` - Production sheet ID
- `GOOGLE_ADS_CUSTOMER_ID` - Google Ads account ID

**Pipeline Environment Variables** (Cloud Run secrets + env vars):
All 9 secrets injected via `--set-secrets` in Cloud Build:
1. `OPENAI_API_KEY` → feedops-openai-api-key
2. `SUPABASE_URL` → feedops-supabase-url
3. `SUPABASE_KEY` → feedops-supabase-key (service role)
4. `GOOGLE_ADS_DEVELOPER_TOKEN` → feedops-google-ads-developer-token
5. `GOOGLE_ADS_CLIENT_ID` → feedops-google-ads-client-id
6. `GOOGLE_ADS_CLIENT_SECRET` → feedops-google-ads-client-secret
7. `GOOGLE_ADS_REFRESH_TOKEN` → feedops-google-ads-refresh-token
8. `GOOGLE_ADS_LOGIN_CUSTOMER_ID` → feedops-google-ads-login-customer-id
9. `GEMINI_API_KEY` → feedops-gemini-api-key

Set via `--set-env-vars` in Cloud Build:
- `GOOGLE_ADS_CUSTOMER_ID=6253381786`
- `GOOGLE_ADS_API_ENABLED=1`

**Optional Toggles** (runtime feature flags):
- `FEEDOPS_GMC_STRUCTURED_ONLY=1` - Use structured title/description only (omit standard fields)
- `GOOGLE_ADS_MCP_ENABLED=1` - Enable Apify/Google Ads MCP mode (not recommended for production)
- `APIFY_MCP_ENABLED=1` - Enable Apify MCP integration (optional)

**Secrets Location:**
- Production: GCP Secret Manager (bound to Cloud Run service account)
- Development: `.env` file (local, not committed) or `.env.vercel` file (team-shared, also not committed)

## Webhooks & Callbacks

**Incoming Webhooks:**
- Google Sheets → No incoming webhooks (pull model via Sheets API)
- Shopify → No incoming webhooks currently (pull model)
- Google Ads → No incoming webhooks (API polling for metrics)

**Outgoing Webhooks:**
- Dashboard → Cloud Run Pipeline: `POST /regenerate`, `POST /optimize-sku`, `POST /batch-optimize`, `POST /hybrid-generate`, `POST /generate-images`
- Dashboard → Cloud Run Pipeline: `POST /performance/capture-baseline`, `POST /search-insights/sync`
- Cloud Run Pipeline → Supabase: Direct database updates (no webhook format)
- Cloud Run Pipeline → Google Sheets: Direct API updates (no webhook format)

**Callback Patterns:**
- Polling via job IDs: `/batch-status/{job_id}`, `/search-insights/sync/{job_id}`
- Background tasks: Non-daemon async threads survive HTTP response, managed by `run_async_in_thread()` helper
- CORS: Cloud Run allows requests from `https://allied-feed-ops.vercel.app` and `http://localhost:3000`

## Data Integration Flow

**Content Generation Pipeline:**
1. Dashboard (`/api/regenerate` route) → Cloud Run `/regenerate` endpoint
2. Cloud Run executes Python pipeline (OpenAI/Gemini LLM)
3. Results written to Supabase `generated_content` table
4. Dashboard polls for updates via React Query

**Publishing Workflow:**
1. User approves content in dashboard
2. Batch creation triggers publish sequence
3. Desktop → Google Sheets (Google Sheets API) — updates supplemental feed
4. Dashboard → Shopify (GraphQL mutations) — product title/description, media uploads
5. Audit trail written to `publish_events` table

**Performance Tracking:**
1. Auto-capture baselines before optimization (30-day pre-publish data)
2. Capture snapshots post-publish (daily/weekly via Cloud Scheduler or manual trigger)
3. Analytics dashboards consume `performance_baselines` and `performance_snapshots`

**Search Insights:**
1. Scheduled sync: `/search-insights/sync` endpoint triggers background task
2. Queries Google Ads Search Terms report
3. Runs Keyword Planner for keyword volume/competition data
4. Results cached in `search_queries` and `keyword_metrics` tables
5. Evidence table auto-populated for content generation

---

*Integration audit: 2026-02-11*
