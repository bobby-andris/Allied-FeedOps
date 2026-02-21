# Architecture

**Analysis Date:** 2026-02-20

## Pattern Overview

**Overall:** Distributed pipeline with clear separation between dashboard (Next.js frontend/API routes) and Python-based content generation engine (Cloud Run backend).

**Key Characteristics:**
- **Dual-stack architecture**: TypeScript/Next.js for UI/orchestration, Python for content generation
- **Thin proxy pattern**: Dashboard API routes act as lightweight proxies to Cloud Run
- **Modular pipeline**: Content generation broken into reusable pipeline stages (evidence, enrichment, generation, validation)
- **Event-driven**: Approval workflows, publishing, and performance tracking use Supabase as message hub
- **Data-first flow**: Evidence tables built from product catalog → fed into LLM generation → approved → published

## Layers

**Presentation Layer:**
- Purpose: Interactive UI for content review, approvals, batching, monitoring
- Location: `dashboard/src/app/(dashboard)/**` (Next.js page routes)
- Contains: React components, client-side state management, dashboard views
- Depends on: API Routes layer, Supabase client libraries
- Used by: End users (product managers, content reviewers)

**API Routes Layer (Dashboard):**
- Purpose: Orchestrate workflows, validate requests, proxy to Cloud Run backend
- Location: `dashboard/src/app/api/**` (Next.js API routes)
- Contains: HTTP endpoints for regeneration, publishing, batch jobs, image uploads, approvals
- Depends on: Supabase clients (admin + RLS), Cloud Run pipeline, Shopify/Google APIs
- Used by: Dashboard UI, external systems calling webhook endpoints
- Pattern: Routes validate input → ensure data → call Cloud Run → persist results to Supabase

**Utility/Lib Layer (Dashboard):**
- Purpose: Reusable business logic, SDK wrappers, data collection, evidence building
- Location: `dashboard/src/lib/**` (TypeScript utilities and modules)
- Contains: Publishing helpers, Supabase types, evidence builders, regeneration prompts (legacy reference), Google Sheets/Shopify SDK, multi-SKU detection
- Depends on: Supabase clients, external SDKs
- Used by: API routes, components, other utilities
- Key modules:
  - `lib/publishing/**` - Google Sheets and Shopify publishing flows
  - `lib/evidence/**` - Evidence table construction for LLM
  - `lib/regeneration/**` - Legacy TypeScript prompts (reference only, not runtime)
  - `lib/supabase/**` - Database client setup and type definitions
  - `lib/data-collection/**` - Automatic performance/search data triggers

**Backend API Layer (Cloud Run):**
- Purpose: Run expensive content generation, processing jobs asynchronously
- Location: `src/feedops/api/main.py` (FastAPI entry point) + modular routers
- Contains: HTTP endpoints for optimization, batch jobs, performance capture, search sync, backfill
- Depends on: LLM providers (OpenAI), external APIs (Google Ads, Merchant Center, Shopify), Supabase, GCP services
- Used by: Dashboard API routes (via HTTP), background job schedulers

**Pipeline Engine (Python):**
- Purpose: Multi-stage content generation with quality validation
- Location: `src/feedops/pipeline/**` (pipeline modules)
- Contains:
  - Evidence building: `evidence.py` - assembles product specs, keywords, search terms, competitor data
  - Enrichment: `enrichment.py` - adds competitive context, keyword gaps, segment strategy
  - Generation: `generator.py` - LLM-based candidate creation with structured output
  - Post-generation: Finish sentence injection, keyword placement validation, title normalization, quality scoring
  - Validation: Claims extraction, fact checking against evidence
- Depends on: Models, providers, integrations, database client
- Used by: API endpoints for single-SKU and batch optimization

**Integration Layer (Python):**
- Purpose: Fetch data from external systems, push updates back
- Location: `src/feedops/integrations/**` (integration modules)
- Contains:
  - Google: Google Ads (performance, search terms, Keyword Planner), Google Sheets, Google Feed Upload
  - Merchant Center: Product data, performance metrics, publishing
  - Shopify: Catalog data, analytics, media uploads
  - Bing: Ads performance, catalog management
  - Analytics: GA4, Apify competitor scraping
- Depends on: External SDK clients, Supabase
- Used by: Pipeline stages (evidence building, enrichment), API endpoints for direct API calls

**Database Layer (Python):**
- Purpose: Query and write Supabase tables
- Location: `src/feedops/db/**` (database clients and schema)
- Contains:
  - `supabase_client.py` - Connection management, query helpers
  - `schema.py` - Pydantic models for all Supabase tables (source-of-truth schema definitions)
  - `variant_index.py` - Master SKU ↔ GMC offer ID mapping utilities
- Depends on: supabase-py client library
- Used by: All Python modules that read/write database

**Data Models (Python):**
- Purpose: Type-safe product and content representations
- Location: `src/feedops/models/**` (Pydantic models)
- Contains:
  - `parent_sku.py` - ParentSKU with variants, merchant center items, enrichment metadata
  - `candidate.py` - Generated content (titles, descriptions, claims, self-scores)
  - `variant.py` - Variant-specific product data (master_sku, finish, gmc_offer_id)
  - `claim.py`, `score.py` - Component models for validation scoring
- Depends on: pydantic
- Used by: Pipeline stages, API endpoints, database layer

**Providers (Python):**
- Purpose: Abstract LLM/AI vendor APIs
- Location: `src/feedops/providers/**` (provider implementations)
- Contains: OpenAI (GPT generation), Gemini (image generation), and interface for extensibility
- Depends on: External API SDKs
- Used by: Pipeline generator, image generation endpoint

## Data Flow

**Single SKU Content Generation (Regeneration):**

1. User submits regeneration request via dashboard → `/api/regenerate`
2. Dashboard route validates SKU, ensures performance/search data exists, calls Cloud Run `/regenerate`
3. Cloud Run endpoint:
   - Loads ParentSKU from Supabase with variants and merchant catalog data
   - Builds evidence table: specs + search terms + competitor context + keyword gaps
   - Calls generator with LLM → receives candidate titles/descriptions + finish sentences
   - Validates claims against evidence, scores quality (specificity, keyword inclusion, etc.)
   - Returns candidates + scores to dashboard
4. Dashboard stores candidates in `generated_content.candidate_content` (JSONB array)
5. User reviews → approves a candidate → stored in `generated_content.approved_content`

**Batch Content Generation:**

1. User selects SKUs, options (platforms, content types) → dashboard `/api/sku-selection/generate`
2. Dashboard triggers data collection (non-blocking): ensures baselines + search terms exist
3. Dashboard calls Cloud Run `/batch-optimize`:
   - Creates batch job record with job_id
   - For each SKU: execute full generation pipeline in background thread
   - Multi-SKU families detected: base SKU generated fully, variants adapted (cost savings)
   - Results stored in `generated_content` with version tracking
   - Job status updated via database polls from dashboard
4. Dashboard UI polls `/api/sku-selection/jobs/{jobId}` to track progress
5. Results appear in `/review` page for approval

**Publishing Workflow:**

1. User selects approved SKUs → creates publish batch via `/api/publish/batch`
2. Batch status: `draft` → `pending` → `executing` → `published`
3. During execute:
   - Expand variants: base SKU → 28 variants (one per finish permutation)
   - Update Google Sheets: rows identified by GMC offer ID, content columns updated
   - Publish to Shopify: product-level titles/descriptions + variant-level lifecycle images
   - Audit: `publish_events` stores snapshot (immutable for rollback)
4. Post-publish monitoring:
   - Performance snapshots captured daily via `/api/performance/capture-snapshot`
   - Performance baselines (pre-publish 30-day metrics) compared against post-publish

**Search Insights Sync:**

1. Background job or manual trigger: `/performance/collect-daily` (Cloud Run)
2. Fetches Google Ads search terms for master SKUs
3. Stores in `search_queries` table with variant-level data
4. Evidence builder picks up via `fetch_search_queries_for_master_sku()`

**State Management:**

- **Approval state**: Stored in `sku_approvals`, `variant_approvals` (enum: pending, approved, rejected)
- **Content state**: `generated_content` stores baseline, candidate (versioned array), approved (immutable)
- **Publish state**: `publish_batches` tracks batch status, `publish_events` stores snapshots for audit
- **Performance state**: `performance_baselines` (pre-publish aggregate), `performance_snapshots` (daily post-publish)
- **Inventory state**: `variant_index` (canonical master_sku ↔ gmc_offer_id), `product_catalog` (all variants with specs)

## Key Abstractions

**ParentSKU (Content Generation Context):**
- Purpose: Encapsulates everything about a product needed for generation
- Examples: `src/feedops/models/parent_sku.py`
- Pattern: Loaded from Supabase `product_catalog` + enriched with search data + keyword gaps + competitor data
- Used by: Generator, evidence builder, keyword placement validator

**Evidence Table (LLM Input):**
- Purpose: Structured markdown representation of product specs → fed to LLM as user message
- Examples: `src/feedops/pipeline/evidence.py`, `build_evidence_table()`
- Pattern: Sections for specs, keywords, search terms, finish context, competitor insights, claims bank
- Used by: Generator prompt construction, validation scorers

**Pipeline Routers (Modular Processing):**
- Purpose: Break generation into pluggable stages
- Examples: `src/feedops/api/main.py` includes routers from `search_insights.py`, `performance_baseline.py`, `monitoring.py`
- Pattern: Each router handles one domain (search, performance, monitoring)
- Used by: Cloud Run app mounting

**Candidate with Score (Output Format):**
- Purpose: Generated content + validation scores for human review
- Examples: `src/feedops/models/candidate.py`
- Pattern: Stores title, description, claims with sources, self-scores across 6 dimensions
- Used by: Dashboard review page, approval workflow

## Entry Points

**Dashboard Page Routes:**
- Location: `dashboard/src/app/(dashboard)/[feature]/page.tsx`
- Triggers: User navigation
- Responsibilities: Render UI, fetch data, dispatch actions (approve, publish, regenerate)
- Examples:
  - `page.tsx` - Overview dashboard with stats and charts
  - `review/[sku]/page.tsx` - Content review and approval for single SKU
  - `batches/page.tsx` - Batch creation and monitoring
  - `monitoring/page.tsx` - Performance tracking and insights

**Dashboard API Routes:**
- Location: `dashboard/src/app/api/[domain]/route.ts`
- Triggers: HTTP requests from frontend, external webhooks
- Responsibilities: Validate input, call Cloud Run, manage Supabase state
- Examples:
  - `GET /api/health` - System status check
  - `POST /api/regenerate` - Single SKU content generation (thin proxy)
  - `POST /api/publish/batch` - Batch publish execution
  - `POST /api/performance/capture-snapshot` - Snapshot data collection

**Cloud Run API Endpoints:**
- Location: `src/feedops/api/main.py` (FastAPI app)
- Triggers: HTTP requests from dashboard routes, scheduled jobs
- Responsibilities: Heavy lifting (LLM generation, batch processing, data collection)
- Examples:
  - `POST /optimize-sku` - Single SKU full pipeline
  - `POST /batch-optimize` - Multi-SKU background job
  - `POST /regenerate` - Content regeneration with feedback
  - `POST /performance/capture-baseline` - Baseline data collection
  - `POST /search-insights/sync` - Search term sync job

## Error Handling

**Strategy:** Fail fast on validation, graceful degradation on external API failures

**Patterns:**

- **Validation errors**: Return 400 with clear field/reason (dashboard shows error message)
  - Example: SKU not found, invalid platform, missing required field
  - Location: Route validation logic before Cloud Run call

- **External API failures**: Log warning, continue (non-blocking)
  - Example: Search term fetch fails → generation still completes with baseline evidence
  - Location: Pipeline stages wrap integrations in try-catch

- **LLM generation failures**: Return structured error with retry guidance
  - Example: Token limit exceeded, malformed response, safety filter triggered
  - Location: Generator returns `{ success: false, error: "...", retry_after: 60 }`

- **Database write failures**: Explicit transaction rollback, return error
  - Example: Approval write fails on stale approval_status → user sees "Status changed, refresh and try again"
  - Location: Route endpoint performs transaction validation

- **Long-running jobs**: Timeout, resume capability
  - Example: Batch job takes >25 min, Cloud Run returns job_id for polling
  - Location: Batch job runs in background thread, stores state in database

## Cross-Cutting Concerns

**Logging:**
- Dashboard: Built-in Node.js console (captured by Vercel)
- Python: Python logging module with structured JSON format
- Location: `src/feedops/observability/` for centralized config
- Pattern: Request ID propagation for tracing across systems

**Validation:**
- Content validation: Pydantic models in Python (database layer)
- Business rule validation: Route-level checks (e.g., SKU exists, user has access)
- LLM output validation: `src/feedops/pipeline/validators.py` checks claims, keyword placement, format adherence
- Location: Pipeline stages validate before writing to database

**Authentication:**
- Dashboard: Supabase RLS + API key headers for server routes
- Cloud Run: Service account identity via GCP (no explicit token passing)
- External APIs: Credentials from GCP Secrets Manager injected at runtime
- Location: Middleware in `src/feedops/api/main.py` for request validation

---

*Architecture analysis: 2026-02-20*
