# Architecture

**Analysis Date:** 2026-02-11

## Pattern Overview

**Overall:** Microservice + Monorepo hybrid with decoupled frontend/backend

**Key Characteristics:**
- Next.js dashboard (TypeScript) as frontend API gateway
- Python Cloud Run FastAPI as content generation engine (source of truth)
- Supabase PostgreSQL as persistent data layer
- Multi-platform integration (Google Ads, Merchant Center, Shopify, Google Sheets)
- Event-driven data collection and publication workflows

## Layers

**Presentation (Frontend):**
- Purpose: Next.js app serving dashboard UI, API routes as proxies/controllers
- Location: `dashboard/src/app/(dashboard)/` and `dashboard/src/app/api/`
- Contains: Page components, API route handlers, form management, UI state
- Depends on: Supabase (direct reads), Python Cloud Run (proxies), Google APIs
- Used by: Browser clients via HTTPS

**API Gateway (Next.js Routes):**
- Purpose: Thin proxy to Cloud Run, Supabase mutation handler, health checks
- Location: `dashboard/src/app/api/**/*.ts`
- Contains: Request validation, error handling, data transformation between layers
- Depends on: Python Cloud Run (`POST /regenerate`, `/hybrid-generate`), Supabase admin client
- Used by: Dashboard components, external integrations (webhooks)
- Examples:
  - `dashboard/src/app/api/regenerate/route.ts` - Proxies to Cloud Run
  - `dashboard/src/app/api/health/route.ts` - Multi-service health checks
  - `dashboard/src/app/api/publish/batch/route.ts` - Batch publication controller

**Library/Utilities (TypeScript):**
- Purpose: Shared business logic, data fetching, type definitions
- Location: `dashboard/src/lib/`
- Contains: Supabase queries, publishing orchestration, evidence building, SKU selection scoring
- Depends on: Supabase, Google APIs (sheets, ads, analytics), Shopify GraphQL
- Used by: API routes, React components
- Key modules:
  - `dashboard/src/lib/evidence/` - Evidence table building for LLM prompts
  - `dashboard/src/lib/publishing/` - Google Sheets + Shopify publication logic
  - `dashboard/src/lib/supabase/` - Database client factories and queries
  - `dashboard/src/lib/data-collection/` - Auto-collection of performance/search data

**Content Generation Pipeline (Python):**
- Purpose: LLM-driven content generation, SKU optimization, multi-SKU variant handling
- Location: `src/feedops/api/main.py` (FastAPI app entry), `src/feedops/pipeline/`
- Contains: Prompt building, LLM provider abstraction, evidence processing, finish sentence handling
- Depends on: OpenAI/Gemini APIs, Supabase, Google Ads API, Merchant Center API
- Used by: Dashboard `/api/regenerate`, `/api/sku-selection/generate-hybrid`
- Key modules:
  - `src/feedops/pipeline/optimize.py` - Main optimization orchestrator
  - `src/feedops/pipeline/prompts.py` - Prompt template and guidance builder
  - `src/feedops/pipeline/evidence.py` - Product evidence extraction
  - `src/feedops/pipeline/generator.py` - LLM call + response parsing
  - `src/feedops/api/multi_sku_detection.py` - Product family grouping

**Data Loaders (Python):**
- Purpose: Product data aggregation from multiple sources
- Location: `src/feedops/loaders/`
- Contains: Supabase catalog loading, variant index resolution, status enrichment
- Depends on: Supabase, Shopify API (optional), Merchant Center snapshots
- Used by: Pipeline, batch selection
- Examples: `src/feedops/loaders/unified_loader.py` - Master loader combining catalog + status

**Integrations (Python):**
- Purpose: External API clients for data fetching and publishing
- Location: `src/feedops/integrations/`
- Contains: Google Ads performance, search terms, Merchant Center data, Shopify catalog, publishing
- Depends on: External APIs (Google Ads, Shopify, Google Sheets)
- Used by: Data collection workflows, publishing, evidence building

**UI Components (React):**
- Purpose: Reusable React components for dashboard pages
- Location: `dashboard/src/components/`
- Contains: Feature-specific components (review, batches, performance, search-insights)
- Depends on: Supabase queries, TanStack Query for async state, Zustand for client state
- Used by: Pages in `dashboard/src/app/(dashboard)/`

**Database (Supabase PostgreSQL):**
- Purpose: Single source of truth for content, approvals, performance, publishing
- Location: Schema defined in `supabase/migrations/`
- Contains: 32 tables covering SKUs, approvals, content variants, batches, performance snapshots
- Key tables:
  - `product_catalog` - Master product data with variant details
  - `generated_content` - Candidate/approved content (baseline, candidate, approved_content JSONB)
  - `sku_approvals`, `variant_approvals` - Approval workflow state
  - `publish_batches`, `batch_sku_assignments` - Batch publishing coordination
  - `performance_baselines`, `performance_snapshots` - Performance tracking pre/post-publish
  - `variant_index` - SKU ↔ GMC offer ID mapping (source of truth)

## Data Flow

**Content Generation Flow:**

1. User selects SKU(s) from dashboard → `POST /api/sku-selection/generate`
2. Dashboard API loads product data via `ensureSkuData()` (auto-collects performance/search)
3. Dashboard API calls Cloud Run `POST /regenerate` with master_sku + feedback
4. Python pipeline:
   - Loads ParentSKU + variants from Supabase via `load_parent_sku_unified_with_status()`
   - Detects multi-SKU families via `detect_multi_sku_families()` (e.g., DMF-2/2X, 2/3X...)
   - Builds evidence table from product_catalog + search terms
   - Constructs prompt using `build_category_guidance()` + gold standard examples
   - Calls OpenAI/Gemini with evidence + prompt
   - Validates claims via `verify_claims()`, normalizes finish sentences
   - Returns optimized candidate content
5. Dashboard stores in `generated_content.candidate_content` (JSONB)
6. User reviews and approves → `PUT sku_approvals.approval_status = 'approved'`
7. Approved content moves to `generated_content.approved_content` (immutable)

**Publication Flow:**

1. User creates batch → `POST /api/publish/batch`
2. Batch status: `draft` → `pending`
3. Batch execution:
   - Reads `approved_content` for each SKU
   - Expands variants (e.g., {FINISH_NAME} → ABR, BRG, ...)
   - Publishes to Google Sheets (GMC supplemental feed) - transforms offer IDs to uppercase
   - (Optional) Publishes lifestyle images to Shopify CDN
   - Updates Shopify product descriptions if applicable
4. Batch status: `pending` → `executing` → `published`
5. Audit trail: `publish_events` stores content snapshots for rollback

**Performance Data Collection:**

1. Dashboard auto-triggers on generation start: `ensureSkuData()` → `POST /api/performance/capture-baseline`
2. Cloud Run queries Google Ads for 30-day pre-publish metrics (impressions, clicks, CTR, CVR)
3. Stores in `performance_baselines`
4. Post-publish, Cloud Scheduler or manual trigger: `POST /api/performance/capture-snapshot`
5. Calculates `days_since_publish` from `publish_events.published_at`
6. Stores in `performance_snapshots` (keyed by `master_sku`, `platform`, `days_since_publish`)

**Search Query Sync Flow:**

1. Dashboard auto-triggers: `POST /search-insights/sync`
2. Cloud Run queries Google Ads search terms for variants
3. Stores in `search_queries` (variant-level, GMC offer ID)
4. Also triggers Keyword Planner for related keywords
5. Caches in `keyword_metrics` (30-day TTL)

**State Management:**

- **Database state:** Authoritative (Supabase)
- **Client state:** Transient UI state (Zustand stores in `dashboard/src/lib/*/store.ts`)
- **Content versions:** Immutable chain: `baseline_content` → `candidate_content` → `approved_content`
- **Approval workflow:** Single source: `sku_approvals.approval_status` enum (`pending`, `approved`, `rejected`, `draft`)

## Key Abstractions

**ParentSKU Model:**
- Purpose: Represents product with finish-specific variants
- Examples: `src/feedops/models/parent_sku.py`, dashboard type in API responses
- Pattern: Aggregates variant data (finish codes, titles, descriptions) + parent-level specs (material, shape, dimensions)
- Used by: Pipeline for content generation, dashboard for variant expansion

**Candidate Selection:**
- Purpose: Multi-candidate generation and scoring to select best variant
- Examples: `src/feedops/pipeline/selection.py`, dashboard reviewer UI
- Pattern: LLM generates N candidates, human scores + LLM heuristic selection combine
- Used by: `/optimize-sku` endpoint, batch regeneration

**Evidence Table:**
- Purpose: Structured data extracted from product_catalog for LLM prompt context
- Examples: `src/feedops/pipeline/evidence.py` (Python), `dashboard/src/lib/evidence/builder.ts` (TS)
- Pattern: Builds field-value pairs with source metadata (catalog, shopify, google_ads, etc.)
- Used by: LLM prompt construction, audit/traceability

**Multi-SKU Detection:**
- Purpose: Group related SKUs (product families) for batch processing
- Examples: `src/feedops/api/multi_sku_detection.py`
- Pattern: Identifies shared `product_id` across multiple `master_sku` entries (e.g., DMF-2/2X, DMF-2/3X)
- Used by: Hybrid generation (base SKU full generation, variants adapted via `adapt_variant_content()`)

**Finish Sentence Handling:**
- Purpose: Dynamic finish-specific descriptions (e.g., "Antique Brass", "Brushed Nickel")
- Examples: `src/feedops/pipeline/finish_sentence_placeholder.py`, `src/feedops/pipeline/finish_sentence_validation.py`
- Pattern: Base description has `{FINISH_NAME}` placeholder; normalized and validated per-variant
- Used by: Google/Bing variant expansion, publication

**Provider Abstraction:**
- Purpose: Unified LLM interface (OpenAI, Gemini)
- Examples: `src/feedops/providers/` directory
- Pattern: `get_provider()` factory selects based on `FEEDOPS_LLM_PROVIDER` env var
- Used by: All generation pipelines

## Entry Points

**Dashboard Web App:**
- Location: `dashboard/src/app/(dashboard)/page.tsx`
- Triggers: User navigates to `/` after login
- Responsibilities: Main dashboard overview with stats, approval queue, performance charts

**SKU Selection/Generation:**
- Location: `dashboard/src/app/(dashboard)/generate/page.tsx`
- Triggers: User clicks "Generate Content"
- Responsibilities: SKU selection UI, batch job creation, progress tracking

**Content Review:**
- Location: `dashboard/src/app/(dashboard)/review/[sku]/page.tsx`
- Triggers: User clicks SKU to review generated content
- Responsibilities: Side-by-side comparison, platform-specific approval, variant review

**Batch Publishing:**
- Location: `dashboard/src/app/(dashboard)/batches/page.tsx`
- Triggers: User selects approved content for batch publish
- Responsibilities: Batch creation, execution status, publish preview

**API Health Check:**
- Location: `dashboard/src/app/api/health/route.ts`
- Triggers: External monitoring, dashboard startup
- Responsibilities: Check all dependent services (Supabase, Google Ads, Shopify, Google Sheets)

**Cloud Run Content Generation:**
- Location: `src/feedops/api/main.py` FastAPI app
- Triggers: Dashboard calls `POST /regenerate`, `/hybrid-generate`, `/batch-optimize`
- Responsibilities: Orchestrate LLM generation, store results to Supabase, return optimized content

**Cloud Run Performance Capture:**
- Location: `src/feedops/api/main.py` endpoint `POST /performance/capture-baseline`
- Triggers: Dashboard auto-triggers during SKU selection, manual via API
- Responsibilities: Query Google Ads, store baseline metrics, cache results

## Error Handling

**Strategy:** Layered error handling with graceful degradation

**Patterns:**

- **TypeScript API routes:** Return `NextResponse.json({ error: string, code?: string, details?: string }, { status: number })`
- **Python endpoints:** Return JSON with `error` key, HTTP status codes (400 bad request, 500 server error)
- **Database queries:** Explicit error checking; Supabase errors include `code`, `message`, `details`, `hint`
- **LLM calls:** Retry logic for transient failures, fallback to previous approved content
- **Validation:** Input validation at route handler level; Pydantic for Python request bodies
- **Timeout handling:** Concurrent operations wrapped with `withTimeout()` in health checks, non-blocking background tasks with `run_async_in_thread()`

**Common Patterns:**

```typescript
// TypeScript: Structured error response
if (!supabase) {
  return NextResponse.json(
    { error: 'Database unavailable' },
    { status: 503 }
  )
}

// TypeScript: Error context in logs
logSupabaseError('query_context', error)

// Python: Pydantic validation errors caught by FastAPI
class RegenerateRequest(BaseModel):
  master_sku: str
  content_type: Literal['title', 'description']
```

## Cross-Cutting Concerns

**Logging:**
- Python: `logging` module with structured context via `request_context` (request ID, user)
- TypeScript: `console.log`/`error` (Vercel captures to logs)
- Observability: GCP Cloud Logging aggregates both Cloud Run and Cloud Function logs

**Validation:**
- Input: Pydantic (Python), Next.js request handlers (TypeScript)
- Content: Claim verification via `verify_claims()` in Python pipeline
- Data: Schema constraints in Supabase (enums for status fields, NOT NULL constraints)

**Authentication:**
- Dashboard: Supabase Auth (JWT tokens via `@supabase/ssr`)
- Cloud Run: Unauthenticated (protected by default credentials via Cloud IAM; CORS allows only `allied-feed-ops.vercel.app`, `localhost:3000`)
- Google APIs: Service accounts (base64-encoded JSON in env vars)
- Shopify: Access token in env var

**Rate Limiting:** Not explicitly implemented; relies on upstream API rate limits (Google Ads, OpenAI)

---

*Architecture analysis: 2026-02-11*
