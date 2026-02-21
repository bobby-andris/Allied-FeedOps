# External Integrations

**Analysis Date:** 2026-02-20

## APIs & External Services

**E-Commerce & Product Data:**
- Google Merchant Center - Product feed sync, structured data validation
  - SDK: `googleapis` (TypeScript), `google-api-python-client` (Python)
  - Auth: Service account credentials (base64-encoded JSON in `GOOGLE_SERVICE_ACCOUNT_KEY`)
  - Integration: `dashboard/src/lib/publishing/google-sheets.ts`, `src/feedops/integrations/merchant_center.py`
  - Feed Type: Supplemental feed via Google Sheets (custom columns: title, description, lifestyle_image_link, structured_title, structured_description)

- Shopify Storefront & Admin - Product content, media management, order tracking
  - SDK: Direct GraphQL Admin API calls (v2026-01)
  - Auth: `SHOPIFY_ACCESS_TOKEN`, `SHOPIFY_STORE_URL` environment variables
  - Integration: `dashboard/src/lib/publishing/shopify.ts`, `dashboard/src/lib/publishing/shopify-images.ts`, `src/feedops/integrations/shopify_catalog.py`
  - Endpoints: Product mutations, media append (variant-level), storefront analytics (GraphQL)
  - Media: Product-level only (no variant-specific titles/descriptions); lifecycle: Supabase Storage → Shopify CDN → Google Sheets

**Advertising Platforms:**
- Google Ads API - Shopping performance, campaign data, search terms
  - SDK: `google-ads-api` (NPM v23.0.0), `google-ads` (Python v28.4.1+)
  - Auth: OAuth2 (developer token, client ID/secret, refresh token, login customer ID)
  - Integration: `dashboard/src/lib/google-ads.ts`, `src/feedops/integrations/google_ads.py`, `src/feedops/integrations/google_ads_performance.py`, `src/feedops/integrations/google_ads_search_terms.py`
  - Customer ID: `6253381786` (default)
  - Metrics: Impressions, clicks, conversions, CTR, ROAS, search terms
  - Query Language: GAQL (Google Ads Query Language)
  - Rate limiting: Max 25 offer IDs per GAQL IN() clause to prevent API hangs

- Google Ads Keyword Planner - Search volume, competition, bid data
  - SDK: `google-ads` Python client (GenerateKeywordHistoricalMetrics, GenerateKeywordIdeas)
  - Auth: Same OAuth2 as Google Ads API
  - Metrics: avg_monthly_searches, competition (LOW/MEDIUM/HIGH), competition_index (0-100), CPC bids
  - Caching: Historical metrics cached (30-day TTL); monthly updates
  - Seeds: Domain-based ideas up to 250,000 keywords

- Microsoft (Bing) Ads - Shopping performance, competitor data
  - SDK: `bingads` (v13.0.x Python SDK)
  - Auth: OAuth2 credentials (customer ID, account ID)
  - Integration: `src/feedops/integrations/bing_ads_performance.py`, `src/feedops/integrations/bing_catalog.py`
  - Metrics: ProductDimensionPerformanceReport (impressions, clicks, conversions, ROAS)
  - Status: Optional (BING_ADS_API_ENABLED env var controls activation)

**Content Generation (LLMs):**
- OpenAI GPT API - Primary content generation
  - SDK: `openai` (v4.77.0 NPM, v1.0+ Python)
  - Auth: `OPENAI_API_KEY`
  - Models: gpt-5.2 (current default)
  - Features: JSON mode for structured output, prompt caching (50% token cost reduction)
  - Integration: `src/feedops/providers/openai_provider.py` (Python), `dashboard/src/app/api/regenerate/route.ts` proxies to Cloud Run
  - Token Usage: Logged for monitoring (no secrets exposed)

- Google Gemini API - Fallback LLM provider
  - SDK: `google-genai` (v1.0+, new SDK replacing deprecated google.generativeai)
  - Auth: `GEMINI_API_KEY`
  - Models: gemini-3-flash-preview (default)
  - Integration: `src/feedops/providers/gemini_provider.py`
  - Features: JSON output parsing with cleanup, async support via client.aio
  - Usage: Fallback when OpenAI unavailable; can be forced via provider factory

- Gemini Vision API - Lifestyle image generation
  - SDK: `google-genai` (v1.0+)
  - Auth: `GEMINI_API_KEY`
  - Integration: `src/feedops/pipeline/lifestyle_images.py`
  - Quality: ~75-80/100 average, process time ~3 minutes per SKU
  - Features: Smart finish selection based on product metadata

## Data Storage

**Databases:**
- Supabase (PostgreSQL 15+)
  - Project ID: `qezuszwufortkiutlhym`
  - Connection: Environment variables `NEXT_PUBLIC_SUPABASE_URL` (public), `SUPABASE_SERVICE_ROLE_KEY` (elevated)
  - Client: `@supabase/supabase-js` (TypeScript), `supabase` (Python v2.0+)
  - Auth: Supabase built-in JWT + Row-Level Security (RLS) policies
  - Use: All state (content, approvals, publishing, performance baselines, search terms, backfill jobs)
  - Migrations: SQL files in `supabase/migrations/`
  - Real-time: Subscriptions supported for live updates

**File Storage:**
- Supabase Storage - Lifestyle images before CDN publication
  - Lifecycle: Generated → Stored in Supabase → Migrated to Shopify CDN → Published to Google Sheets
  - Bucket: `product_images` (inferred from publish flow)
  - Integration: `src/feedops/pipeline/lifestyle_images.py` (generation), `dashboard/src/lib/publishing/shopify-images.ts` (upload)

- Google Drive - Supplemental feed spreadsheet (persistent, collaborative editing)
  - File: Supplemental feed sheet (production ID: `1qMjCn1ZPlDd0R3TkTI0kDnX6tnApIHrnfAOWfJj_QEg`)
  - Columns: id, mpn, product_type, pattern, custom_label_0-2, title, google_product_category, description, custom_label_4, lifestyle_image_link, structured_title, structured_description
  - Auth: Service account with Sheets & Drive scopes
  - Integration: `dashboard/src/lib/publishing/google-sheets.ts`, `src/feedops/integrations/google_sheets.py`

**Caching:**
- None detected - Query results cached in-memory during request lifetime only

## Authentication & Identity

**Auth Provider:**
- Supabase Auth (built-in)
  - Implementation: Session management via cookies + JWT tokens
  - Dashboard integration: `dashboard/src/lib/supabase/server.ts` (server-side), `dashboard/src/lib/supabase/client.ts` (client-side)
  - Middleware: `@supabase/ssr` for server-side session refresh
  - RLS: Row-level security policies on all tables (enforced at database level)

**Service Accounts:**
- GCP Service Account (GCS, Sheets, Drive)
  - Email: `profit-pilot-runtime@bobbys-project-346400.iam.gserviceaccount.com`
  - Format: Base64-encoded JSON in `GOOGLE_SERVICE_ACCOUNT_KEY`
  - Scopes: Sheets, Drive, Cloud Run (runtime permissions)

- Google Ads OAuth2
  - Flow: Refresh token-based (not browser redirect flow)
  - Credentials: Developer token, client ID/secret, refresh token, login customer ID
  - Storage: GCP Secrets Manager (Cloud Run), environment variables (local dev)

## Monitoring & Observability

**Error Tracking:**
- Slack Webhook - Job lifecycle alerts
  - Endpoint: `SLACK_WEBHOOK_URL`
  - Integration: `src/feedops/observability/alerts.py` (send_slack_notification, notify_job_event)
  - Usage: Backfill job status, pipeline failures (fire-and-forget)

**Logs:**
- Cloud Run logs - Python pipeline execution
  - Aggregator: GCP Cloud Logging
  - Access: `gcloud run services logs read feedops-pipeline --project=bobbys-project-346400`
  - Format: JSON structured logs (FastAPI/Uvicorn)

- Vercel logs - Dashboard (Next.js) execution
  - Aggregator: Vercel dashboard
  - Browser console: Client-side errors and warnings

- Application logging: `logging` module (Python), `console` (JavaScript)
  - Level: INFO (production), configurable per module

**Metrics:**
- Prometheus client - Python pipeline metrics
  - Integration: `src/feedops/observability/metrics.py`
  - Registry: `prometheus-client` 0.20+
  - Exposed on: `/metrics` endpoint (Cloud Run)
  - Metrics: Token usage (cached vs. uncached), generation latency, error rates

## CI/CD & Deployment

**Hosting:**
- Cloud Run (Python pipeline)
  - Region: us-east1
  - Memory: 2 GB
  - CPU: 2
  - Timeout: 900 seconds
  - Max instances: 10
  - Auto-scaling: Managed by Cloud Run
  - Service account: `profit-pilot-runtime@bobbys-project-346400.iam.gserviceaccount.com`
  - Health check: `GET /health` with Supabase status

- Vercel (Next.js dashboard)
  - Auto-deploy on push to master branch
  - Project ID: `prj_00zlLdZVgbP8XjDWIEXSRdFyqDqA`
  - Team ID: `team_KsEZDE8Pw0bKQDGlieBVBQVs`
  - Custom domain: `allied-feed-ops.vercel.app`

**CI Pipeline:**
- GCP Cloud Build
  - Trigger: `feedops-pipeline-deploy` (push to master on GitHub)
  - Build config: `cloudbuild.yaml`
  - Steps:
    1. Docker build (Python 3.11-slim)
    2. Push to Artifact Registry (`us-east1-docker.pkg.dev`)
    3. Deploy to Cloud Run with secrets injection
  - Build SA: `profit-pilot-build@bobbys-project-346400.iam.gserviceaccount.com`
  - Secrets injected at deploy time (9 total secrets)
  - Logs: GCP Cloud Build console

**Docker Registry:**
- GCP Artifact Registry (`us-east1-docker.pkg.dev`)
  - Images: `feedops-pipeline:$COMMIT_SHA`, `feedops-pipeline:latest`
  - Build Backend: hatchling (Python)

## Environment Configuration

**Required env vars (Production - GCP Secrets):**
- `OPENAI_API_KEY` - OpenAI API key
- `GEMINI_API_KEY` - Google Gemini API key
- `SUPABASE_URL` - Supabase project URL (can use NEXT_PUBLIC variant)
- `SUPABASE_KEY` - Supabase service role key (can use SUPABASE_SERVICE_ROLE_KEY)
- `GOOGLE_ADS_DEVELOPER_TOKEN` - Google Ads API developer token
- `GOOGLE_ADS_CLIENT_ID` - Google Ads OAuth2 client ID
- `GOOGLE_ADS_CLIENT_SECRET` - Google Ads OAuth2 client secret
- `GOOGLE_ADS_REFRESH_TOKEN` - Google Ads OAuth2 refresh token
- `GOOGLE_ADS_LOGIN_CUSTOMER_ID` - Google Ads manager account ID (optional, for multi-account)
- `SLACK_WEBHOOK_URL` - Slack incoming webhook for alerts

**Required env vars (Dashboard - .env.local):**
- `NEXT_PUBLIC_SUPABASE_URL` - Supabase project URL (public)
- `NEXT_PUBLIC_SUPABASE_ANON_KEY` - Supabase anonymous key (public)
- `SUPABASE_SERVICE_ROLE_KEY` - Service role key (server-only)
- `GOOGLE_SERVICE_ACCOUNT_KEY` - Base64-encoded GCP service account JSON (server-only)
- `SHOPIFY_STORE_URL` - Shopify store domain
- `SHOPIFY_ACCESS_TOKEN` - Shopify Admin API access token
- `GOOGLE_ADS_*` - Google Ads credentials (same as Cloud Run)

**Optional env vars:**
- `FEEDOPS_OPENAI_MODEL` - OpenAI model override (default: gpt-5.2)
- `FEEDOPS_GMC_STRUCTURED_ONLY=1` - Omit standard title/description, use structured fields only
- `BING_ADS_API_ENABLED=1` - Enable Bing Ads integration (default: disabled)
- `GOOGLE_ADS_API_ENABLED=1` - Enable Google Ads API (default: enabled on Cloud Run)
- `GOOGLE_ADS_MCP_ENABLED=1` - Use MCP server instead of native SDK (Cursor-only, experimental)

**Secrets location:**
- Development: `.env.local` (dashboard), `.env` (Python local)
- Production: GCP Secret Manager (Cloud Run), Vercel Secrets (dashboard)
- Never committed to git (`.env` in `.gitignore`)

## Webhooks & Callbacks

**Incoming:**
- `POST /api/regenerate` - Content regeneration endpoint (dashboard proxies to Cloud Run `/regenerate`)
- `POST /api/publish/batch` - Batch publishing trigger
- `POST /api/performance/capture-snapshot` - Performance metrics collection
- `POST /api/search-insights/sync` - Google Ads search term sync job start
- `POST /backfill/start` - Backfill job creation
- Health checks: `GET /health` on both dashboard and Cloud Run

**Outgoing:**
- Slack webhooks - Job completion notifications (Cloud Run → Slack)
- Google Sheets API - Feed updates written to supplemental sheet
- Shopify GraphQL mutations - Product updates (title, description, media, tags)
- Google Ads uploads - Not webhooks; sheet-based feed sync (GMC pulls from sheet)

**Job Completion:**
- Synchronous: Endpoint waits for response (batch operations timeout at 900s on Cloud Run)
- Asynchronous: Background task pattern using `run_async_in_thread()` in Python for long-running operations (image generation, backfill)
  - Pattern: Non-daemon threads with dedicated asyncio event loops survive HTTP response and container scaling-to-zero
  - Limitation: Jobs terminate during Cloud Run deployments (expected behavior, can be resumed)

---

*Integration audit: 2026-02-20*
