# Codebase Structure

**Analysis Date:** 2026-02-11

## Directory Layout

```
Allied-FeedOps/
├── dashboard/                  # Next.js web app (TypeScript/React)
│   ├── src/
│   │   ├── app/               # Next.js App Router (pages + API routes)
│   │   ├── components/        # React components by feature
│   │   ├── lib/               # Shared utilities, business logic, types
│   │   └── hooks/             # Custom React hooks
│   ├── public/                # Static assets
│   ├── supabase/              # Database migrations
│   └── package.json           # Dependencies (Next.js, React, Supabase, etc.)
│
├── src/feedops/               # Python content generation pipeline
│   ├── api/                   # FastAPI app + route handlers (Cloud Run)
│   ├── pipeline/              # Content generation orchestration
│   ├── loaders/               # Data loading from Supabase, Shopify, CSV
│   ├── integrations/          # External API clients (Google, Shopify, etc.)
│   ├── models/                # Pydantic data models
│   ├── db/                    # Database clients and schema
│   ├── providers/             # LLM provider abstraction (OpenAI, Gemini)
│   ├── quality/               # Quality scoring and gates
│   ├── observability/         # Logging and metrics
│   ├── config/                # Configuration management
│   └── cli/                   # Command-line tools
│
├── tests/                     # Python pytest tests
│   ├── test_*.py              # Individual test files (co-located by feature)
│   └── api/                   # API-specific tests
│
├── supabase/                  # Supabase infrastructure
│   └── migrations/            # Database migration SQL files (numbered)
│
├── docs/                      # Documentation
│   ├── architecture/          # System design docs
│   ├── database/              # Database schema reference
│   ├── prompts/               # Implementation specs for features
│   ├── troubleshooting/       # Debugging guides
│   ├── audit/                 # Root cause analyses
│   └── plans/                 # Project plans and handoffs
│
├── scripts/                   # Utility scripts (Python, bash)
├── data/                      # Local test data and exports
├── exports/                   # Generated report exports
├── logs/                      # Application logs
├── samples/                   # Sample data files
│
├── pyproject.toml             # Python project config (dependencies, build)
├── CLAUDE.md                  # Project instructions for AI agents
└── .github/workflows/         # CI/CD pipeline definitions
```

## Directory Purposes

**`dashboard/src/app/`:**
- Purpose: Next.js App Router — pages and API routes
- Contains: Page components (`page.tsx`), route handlers (`route.ts`), layouts
- Structure:
  - `(dashboard)/` - Protected pages (wrapped in layout with auth)
  - `api/` - HTTP endpoints (regenerate, publish, health, etc.)
- Key files:
  - `(dashboard)/page.tsx` - Main dashboard overview
  - `(dashboard)/review/[sku]/page.tsx` - Content review UI
  - `(dashboard)/generate/page.tsx` - SKU selection and batch generation
  - `(dashboard)/batches/page.tsx` - Batch management
  - `api/health/route.ts` - Multi-service health checks
  - `api/regenerate/route.ts` - Proxy to Cloud Run pipeline

**`dashboard/src/components/`:**
- Purpose: Reusable React components organized by feature area
- Contains: UI components, form controls, feature-specific logic components
- Structure by feature:
  - `ui/` - Base shadcn components (Button, Card, Dialog, etc.)
  - `dashboard/` - Overview dashboard components (charts, stats)
  - `review/` - Content review UI (PlatformContent, ImageGallery, etc.)
  - `generate/` - SKU selection and generation components
  - `batches/` - Batch management UI
  - `performance/` - Performance data visualization
  - `search-insights/` - Search query analysis components
  - `competitors/` - Competitor intelligence components
  - `shared/` - Navigation, layout wrappers, generic utilities

**`dashboard/src/lib/`:**
- Purpose: Business logic, data fetching, utilities shared across app
- Structure:
  - `supabase/` - Database client factories (`admin.ts`, `client.ts`, `server.ts`), queries
  - `publishing/` - Google Sheets, Shopify publication logic
  - `evidence/` - Evidence table building for LLM prompts
  - `data-collection/` - Auto-collection of performance/search data
  - `regeneration/` - Legacy regeneration helpers (most logic moved to Python)
  - `batches/` - Batch operation utilities
  - `competitors/` - Competitor data fetching
  - `prompts/` - Prompt-related utilities (legacy, moved to Python)
  - `storage/` - File upload helpers (Supabase Storage)
  - Types: `sku-utils.ts`, `google-ads.ts`, `variant-content.ts`

**`src/feedops/api/`:**
- Purpose: FastAPI HTTP layer for Cloud Run deployment
- Contains: Route handlers, request/response models, main app setup
- Key files:
  - `main.py` - FastAPI app initialization, endpoint definitions, CORS setup
  - `prompt_loader.py` - Load system prompts from Supabase (runtime authority)
  - `supabase_loader.py` - Load product data from Supabase
  - `multi_sku_detection.py` - Detect product families and group variants
  - `hybrid_generation.py` - Variant content adaptation (base SKU → variants)
  - `runtime_controls.py` - Feature flags (generation enabled, finish sentence mode)

**`src/feedops/pipeline/`:**
- Purpose: Content generation orchestration and processing
- Contains: Optimization logic, evidence building, LLM prompt construction
- Key files:
  - `optimize.py` - Main orchestrator (loads data, builds evidence, calls LLM, validates)
  - `prompts.py` - Prompt template building, guidance data assembly
  - `evidence.py` - Extract structured data from product catalog
  - `generator.py` - LLM call + JSON parsing
  - `selection.py` - Multi-candidate evaluation and best-pick selection
  - `verifier.py` - Claim validation against specifications
  - `finish_sentence_*.py` - Finish-specific content handling
  - `reporter.py` - Generate HTML reports and patch previews

**`src/feedops/loaders/`:**
- Purpose: Product data aggregation from multiple sources
- Contains: Supabase queries, data enrichment, status resolution
- Key files:
  - `unified_loader.py` - Master loader combining catalog + approval status
  - `catalog.py` - Supabase product_catalog queries
  - `catalog_resolver.py` - Resolve variant details (descriptions, specs)

**`src/feedops/integrations/`:**
- Purpose: External API clients
- Contains: Google Ads, Merchant Center, Shopify, Google Sheets, Apify integrations
- Key files:
  - `google_ads_performance.py` - Query Google Ads for impressions/clicks/CTR/CVR
  - `google_ads_search_terms.py` - Query Google Ads search terms (variant-level)
  - `google_sheets.py` - Update supplemental feed (product data, images)
  - `shopify_catalog.py` - Fetch Shopify product/variant details
  - `merchant_center.py` - Load GMC snapshot for competitor analysis
  - `apify.py` - Web scraping for competitor content

**`src/feedops/models/`:**
- Purpose: Pydantic data models for type safety and validation
- Key files:
  - `parent_sku.py` - ParentSKU (product + variants) model
  - `variant.py` - Variant details (finish, title, description, specs)
  - `candidate.py` - Generated content candidate
  - `score.py` - Quality/heuristic scores
  - `claim.py` - Extracted product claims

**`src/feedops/db/`:**
- Purpose: Database client and schema management
- Key files:
  - `supabase_client.py` - Supabase client factory, connection pooling
  - `schema.py` - Schema type hints and utilities
  - `variant_index.py` - SKU ↔ GMC offer ID mapping queries

**`src/feedops/providers/`:**
- Purpose: LLM provider abstraction
- Key files:
  - Factory: `__init__.py` exports `get_provider()` function
  - Implementations: `openai_provider.py`, `gemini_provider.py`

**`tests/`:**
- Purpose: Python test suite
- Naming: `test_*.py` (pytest convention)
- Location: Can be at root (`tests/`) or co-located with source
- Key patterns:
  - `conftest.py` - Shared fixtures
  - `test_*.py` - Individual test modules by feature
  - `api/` - API endpoint tests
- Examples:
  - `test_openai_provider_max_tokens.py` - LLM provider tests
  - `test_evidence_multisize.py` - Evidence table generation
  - `test_images.py` - Lifestyle image handling

**`supabase/migrations/`:**
- Purpose: Database schema versioning
- Naming: `001_initial_schema.sql`, `002_add_approvals.sql`, etc. (numbered, sequential)
- Contains: CREATE TABLE, ALTER TABLE, index creation, constraint definitions
- Key: Each migration is run once in order; immutable

**`docs/`:**
- Purpose: Documentation and knowledge base
- Structure:
  - `database/SCHEMA.md` - Complete schema reference (tables, columns, types, examples)
  - `architecture/` - System design and decision documents
  - `prompts/` - Feature specification documents (01-09.md, FUTURE-IDEAS.md)
  - `troubleshooting/` - Debugging guides and common issues
  - `audit/` - Root cause analyses and investigation results

## Key File Locations

**Entry Points:**

- `dashboard/src/app/(dashboard)/page.tsx` - Web app dashboard
- `dashboard/src/app/api/health/route.ts` - Service health checks
- `src/feedops/api/main.py` - Cloud Run API server

**Configuration:**

- `dashboard/.env.local` - Local dashboard config (development)
- `dashboard/.env.vercel` - Vercel environment variables (auto-loaded)
- `pyproject.toml` - Python dependencies and package config
- `dashboard/tsconfig.json` - TypeScript compiler options
- `dashboard/package.json` - Node.js dependencies and scripts

**Core Logic:**

- `src/feedops/pipeline/optimize.py` - Main content generation orchestrator
- `dashboard/src/app/api/regenerate/route.ts` - Dashboard proxy to Cloud Run
- `dashboard/src/lib/evidence/builder.ts` - Evidence table construction (TS port)
- `dashboard/src/lib/publishing/google-sheets.ts` - Publication to GMC feed
- `src/feedops/loaders/unified_loader.py` - Master product data loader

**Testing:**

- `tests/conftest.py` - Pytest configuration and shared fixtures
- `tests/test_*.py` - Python unit/integration tests
- `dashboard/src/components/review/__tests__/PerformanceCard.test.tsx` - React component test

**Database:**

- `supabase/migrations/` - Schema migration SQL (numbered sequentially)
- `docs/database/SCHEMA.md` - Complete schema reference with examples

## Naming Conventions

**Files:**

- **TypeScript components:** `CamelCase.tsx` (e.g., `SkuReviewClient.tsx`, `ApprovalChart.tsx`)
- **TypeScript utilities:** `kebab-case.ts` (e.g., `sku-utils.ts`, `evidence-builder.ts`)
- **Python modules:** `snake_case.py` (e.g., `optimize.py`, `supabase_client.py`)
- **API routes:** Match HTTP pattern in path (e.g., `/api/regenerate/route.ts` = POST /regenerate)
- **Migrations:** `001_description.sql`, `002_description.sql` (zero-padded numbers)
- **Tests:** `test_feature_name.py` (pytest convention)

**Directories:**

- **Feature areas:** `kebab-case` in both TS and Python (e.g., `search-insights/`, `evidence/`)
- **API route groups:** Reflect REST paths (e.g., `api/publish/batch/`, `api/regenerate/`)

## Where to Add New Code

**New Feature (e.g., New Dashboard Page):**

1. **Page component:** `dashboard/src/app/(dashboard)/feature-name/page.tsx`
2. **Feature components:** `dashboard/src/components/feature-name/*.tsx`
3. **API routes:** `dashboard/src/app/api/feature-name/route.ts` (if needed)
4. **Utilities:** `dashboard/src/lib/feature-name/*.ts`
5. **Tests:** `dashboard/src/components/feature-name/__tests__/*.test.tsx` (optional)

**New Generation Step (e.g., New Validation):**

1. **Pipeline module:** `src/feedops/pipeline/new_step.py`
2. **Integration into `optimize.py`:** Add step to orchestration
3. **Tests:** `tests/test_new_step.py`

**New API Integration (e.g., New Ads Platform):**

1. **Integration module:** `src/feedops/integrations/new_platform.py`
2. **Query module:** Export functions for data fetching
3. **Model types:** Add Pydantic models in `src/feedops/models/` if new structures
4. **Pipeline integration:** Call from appropriate orchestrator
5. **Tests:** `tests/test_new_platform.py`

**New Database Table:**

1. **Migration file:** `supabase/migrations/NNN_description.sql`
2. **Python model:** Add corresponding Pydantic model in `src/feedops/models/`
3. **Query helpers:** `src/feedops/db/table_name.py` (if complex queries)
4. **Documentation:** Update `docs/database/SCHEMA.md`

**Shared Utility (e.g., New Formatter):**

- **Python:** `src/feedops/pipeline/utility_name.py` or `src/feedops/lib/utility_name.py`
- **TypeScript:** `dashboard/src/lib/utility-name.ts` (co-located with usage or `dashboard/src/lib/shared/`)

## Special Directories

**`.planning/codebase/`:**
- Purpose: Generated by `/gsd:map-codebase` — architecture and quality analysis
- Generated: Yes (by agent)
- Committed: Yes (part of codebase analysis)
- Contains: `ARCHITECTURE.md`, `STRUCTURE.md`, `CONVENTIONS.md`, `TESTING.md`, `STACK.md`, `INTEGRATIONS.md`, `CONCERNS.md`

**`dashboard/.next/`:**
- Purpose: Next.js build cache and compiled code
- Generated: Yes (by `npm run build`)
- Committed: No (in `.gitignore`)

**`supabase/.temp/`:**
- Purpose: Temporary Supabase CLI files
- Generated: Yes (by Supabase CLI)
- Committed: No

**`exports/` and `data/`:**
- Purpose: Local test data and report exports
- Generated: Yes (by scripts and pipeline)
- Committed: No (but directories exist for development)

**`docs/screenshots/`:**
- Purpose: UI screenshots and diagrams for documentation
- Generated: No (manually created)
- Committed: Yes

## Path Aliases

**TypeScript (`dashboard/tsconfig.json`):**

```json
"paths": {
  "@/*": ["./src/*"]
}
```

Usage:
- Import from `src/lib/supabase/client.ts` as `import { ... } from '@/lib/supabase/client'`
- Simplifies paths and allows easy refactoring

**Python:**
- No aliases; import from root package: `from feedops.pipeline.optimize import ...`
- Install package in editable mode: `pip install -e .` or `uv pip install -e .`

## Database Schema

**Authoritative Reference:** `docs/database/SCHEMA.md`

**Key Tables:**

- `product_catalog` - Master product + variant data (shopify_product_id, variant_id, master_sku, finish_code, title, description, specs)
- `sku_approvals`, `variant_approvals` - Approval workflow (master_sku/variant_id, approval_status enum, approved_by, approved_at, notes)
- `generated_content` - Content versions (master_sku, platform, baseline_content JSONB, candidate_content JSONB, approved_content JSONB)
- `variant_index` - SKU mapping (master_sku, gmc_offer_id, shopify_product_id, variant_id)
- `publish_batches`, `batch_sku_assignments` - Batch coordination (batch_id, status enum, sku assignments)
- `performance_baselines` - Pre-publish metrics (master_sku, platform, avg_impressions, avg_clicks, avg_ctr, avg_cvr)
- `performance_snapshots` - Post-publish tracking (master_sku, platform, days_since_publish, impressions, clicks, ctr, cvr)
- `search_queries` - Google Ads search terms (variant_id, gmc_offer_id, query, clicks, impressions)
- `keyword_metrics` - Keyword Planner cache (keyword, search_volume, competition, bid_range)

---

*Structure analysis: 2026-02-11*
