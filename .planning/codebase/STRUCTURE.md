# Codebase Structure

**Analysis Date:** 2026-02-20

## Directory Layout

```
Allied-FeedOps/
├── dashboard/                          # Next.js dashboard (Vercel deployment)
│   ├── src/
│   │   ├── app/                       # App Router directory structure
│   │   │   ├── (dashboard)/           # Protected dashboard routes
│   │   │   │   ├── page.tsx           # Overview dashboard
│   │   │   │   ├── review/            # Content review workflows
│   │   │   │   ├── batches/           # Batch management (creation, publishing)
│   │   │   │   ├── performance/       # Performance metrics & snapshots
│   │   │   │   ├── monitoring/        # Real-time monitoring & alerts
│   │   │   │   ├── generate/          # SKU selection & generation UI
│   │   │   │   ├── search-insights/   # Google Ads search term analysis
│   │   │   │   └── [other routes]/    # Settings, competitors, attribution, etc.
│   │   │   ├── api/                   # API routes (Next.js serverless)
│   │   │   │   ├── regenerate/        # Content generation proxy to Cloud Run
│   │   │   │   ├── publish/           # Publishing orchestration (Google Sheets, Shopify)
│   │   │   │   ├── sku-selection/     # Batch generation & job tracking
│   │   │   │   ├── performance/       # Performance capture & analysis
│   │   │   │   ├── review/            # Content approvals & image selection
│   │   │   │   ├── ga4/               # GA4 data fetching & attribution
│   │   │   │   └── [other endpoints]/ # Health, variants, images, etc.
│   │   │   └── login/                 # Authentication page
│   │   ├── lib/                       # Shared utilities & business logic
│   │   │   ├── api/                   # API client helpers
│   │   │   ├── auth/                  # Authentication utilities
│   │   │   ├── batches/               # Batch state management
│   │   │   ├── data-collection/       # Auto-trigger data fetches (performance, search)
│   │   │   ├── evidence/              # Evidence table building for LLM
│   │   │   ├── ga4/                   # GA4 API integration
│   │   │   ├── multi-sku-detection.ts # Product family detection
│   │   │   ├── optimization/          # Quality scoring & ranking logic
│   │   │   ├── publishing/            # Google Sheets & Shopify SDK wrappers
│   │   │   ├── regeneration/          # Legacy TypeScript prompts (reference only)
│   │   │   ├── review/                # Image/variant review state
│   │   │   ├── supabase/              # Database client setup & types
│   │   │   ├── google-ads.ts          # Google Ads API helpers
│   │   │   ├── shopify/               # Shopify GraphQL helpers
│   │   │   └── [utilities]/           # master-sku.ts, sku-utils.ts, etc.
│   │   ├── components/                # Reusable React components
│   │   │   ├── ui/                    # shadcn/ui components (Card, Button, etc.)
│   │   │   ├── dashboard/             # Overview charts & stats components
│   │   │   ├── review/                # SKU review, image approval, variant browser
│   │   │   ├── batches/               # Batch creation & management UI
│   │   │   ├── attribution/           # Attribution forensics, GA4 charts
│   │   │   ├── search-insights/       # Search query tables, performance
│   │   │   └── [feature]/             # Other feature-specific components
│   │   └── styles/                    # Global CSS & Tailwind config
│   ├── next.config.js                 # Next.js build config
│   ├── tsconfig.json                  # TypeScript config
│   └── package.json                   # Dependencies: next, react, supabase, etc.
│
├── src/feedops/                       # Python pipeline (Cloud Run deployment)
│   ├── api/                           # FastAPI entry point & routers
│   │   ├── main.py                    # FastAPI app, CORS, mount routers
│   │   ├── regenerate/                # Single SKU regeneration endpoint
│   │   ├── search_insights/           # Search term sync router
│   │   ├── performance_baseline/      # Baseline capture router
│   │   ├── monitoring/                # Performance monitoring & impact scoring
│   │   ├── backfill/                  # Data backfill & validation jobs
│   │   ├── hybrid_generation/         # Multi-SKU variant adaptation
│   │   ├── sku_alias/                 # SKU resolution & canonicalization
│   │   ├── runtime_controls/          # Feature flags & generation guards
│   │   └── [routers]/                 # Other domain-specific endpoints
│   │
│   ├── pipeline/                      # Content generation stages
│   │   ├── evidence.py                # Evidence table assembly
│   │   ├── enrichment.py              # Enrichment (keywords, competitors, segments)
│   │   ├── generator.py               # LLM-based candidate generation
│   │   ├── prompts.py                 # Prompt templates & JSON schemas
│   │   ├── keyword_placement.py       # Keyword validation & placement scoring
│   │   ├── finish_injection.py        # Finish-specific sentence injection
│   │   ├── claim_extraction.py        # Claims bank building from evidence
│   │   ├── validators.py              # Post-generation validation (format, claims)
│   │   ├── quality_scoring.py         # Quality dimension scoring
│   │   ├── lifestyle_images.py        # Lifestyle image generation & management
│   │   └── [stages]/                  # Segment strategy, title normalization, etc.
│   │
│   ├── integrations/                  # External API clients
│   │   ├── google_ads.py              # Google Ads API (campaigns, account structure)
│   │   ├── google_ads_search_terms.py # Search term reporting
│   │   ├── google_ads_performance.py  # Performance & conversion data
│   │   ├── google_sheets.py           # Google Sheets API (supplemental feed)
│   │   ├── google_supplemental.py     # Supplemental feed schema mapping
│   │   ├── merchant_center.py         # Google Merchant Center API
│   │   ├── search_query_insights.py   # Search query aggregation & relevance
│   │   ├── shopify_catalog.py         # Shopify GraphQL (products, variants, media)
│   │   ├── shopify_analytics.py       # Shopify Analytics API
│   │   ├── bing_catalog.py            # Bing Catalog API
│   │   ├── bing_ads_performance.py    # Bing Ads performance
│   │   └── [integrations]/            # Apify, analytics, etc.
│   │
│   ├── db/                            # Database layer
│   │   ├── supabase_client.py         # Supabase connection & query helpers
│   │   ├── schema.py                  # Pydantic models for ALL tables
│   │   └── variant_index.py           # Master SKU ↔ offer ID mapping
│   │
│   ├── models/                        # Data models (Pydantic)
│   │   ├── parent_sku.py              # ParentSKU (product with variants)
│   │   ├── candidate.py               # Generated content + scores
│   │   ├── variant.py                 # Variant product data
│   │   ├── claim.py                   # Claim assertion
│   │   └── score.py                   # Quality score object
│   │
│   ├── providers/                     # LLM & AI vendor abstractions
│   │   ├── openai_provider.py         # OpenAI (GPT) implementation
│   │   ├── gemini_provider.py         # Google Gemini (images)
│   │   └── base.py                    # Provider interface
│   │
│   ├── jobs/                          # Background job implementations
│   │   ├── batch_optimizer.py         # Batch job executor
│   │   ├── backfill.py                # Data backfill orchestration
│   │   └── [job types]/               # Job implementations
│   │
│   ├── monitoring/                    # Performance impact tracking
│   │   ├── impact_scorer.py           # Diff-in-diff impact calculation
│   │   ├── snapshot_collector.py      # Daily snapshot capture
│   │   └── performance_tracker.py     # Performance trend analysis
│   │
│   ├── quality/                       # Quality assurance modules
│   │   ├── claim_verifier.py          # Fact-check claims against specs
│   │   └── [quality checks]/          # Format, keyword, specificity checks
│   │
│   ├── config/                        # Configuration & environment
│   │   ├── settings.py                # Settings model from env vars
│   │   └── logging.py                 # Logging setup
│   │
│   ├── observability/                 # Logging, tracing, metrics
│   │   ├── logging.py                 # Structured logging config
│   │   ├── metrics.py                 # Prometheus metrics registry
│   │   └── context.py                 # Request context & ID propagation
│   │
│   └── [other modules]/               # CLI, loaders, scripts
│
├── tests/                             # Test suites
│   ├── test_*.py                      # Test files for Python modules
│   ├── api/                           # API route tests
│   └── [test packages]/               # Grouped tests by feature
│
├── supabase/                          # Database migrations
│   ├── migrations/                    # SQL migration files
│   └── schema.yml                     # Schema documentation (auto-generated)
│
├── docs/                              # Documentation
│   ├── architecture/                  # System design docs
│   ├── database/                      # Database schema reference (SCHEMA.md)
│   ├── troubleshooting/               # Debugging guides
│   ├── audit/                         # Investigation reports
│   └── plans/                         # Phase planning & runbooks
│
├── .planning/                         # GSD project management
│   ├── phases/                        # Phase planning documents
│   ├── codebase/                      # Codebase analysis (this file's home)
│   └── config.json                    # GSD configuration
│
└── [config files]/                    # pyproject.toml, .env.vercel, Dockerfile, etc.
```

## Directory Purposes

**dashboard/src/app/(dashboard)/**
- Purpose: User-facing pages for content management workflows
- Contains: Page components, server/client components for features
- Key files:
  - `page.tsx` - Dashboard overview with stats
  - `review/[sku]/page.tsx` - Single SKU review & approval
  - `batches/page.tsx` - Batch management UI
  - `performance/page.tsx` - Performance analytics & snapshots

**dashboard/src/app/api/**
- Purpose: HTTP endpoints that orchestrate workflows
- Contains: Next.js API route handlers
- Pattern: Validate input → ensure prerequisites → call Cloud Run or Supabase → return response
- Key subdirectories:
  - `regenerate/` - Content generation proxy
  - `publish/` - Publishing orchestration
  - `sku-selection/` - Batch generation jobs
  - `performance/` - Performance data capture

**dashboard/src/lib/**
- Purpose: Shared business logic, SDK wrappers, utilities
- Contains: Reusable functions, client setup, type definitions
- Key subdirectories:
  - `publishing/` - Google Sheets & Shopify publishing flows
  - `supabase/` - Database client & types
  - `evidence/` - Evidence table building
  - `data-collection/` - Auto-trigger data fetches

**dashboard/src/components/**
- Purpose: Reusable React components for UI
- Contains: Presentational and container components
- Pattern: Components in feature directories (review/, batches/, etc.) wrap shadcn/ui base components
- Key subdirectories:
  - `ui/` - Base shadcn/ui components (Card, Button, Dialog, etc.)
  - `review/` - SKU review, image approval components
  - `dashboard/` - Overview charts and stat cards

**src/feedops/api/**
- Purpose: Cloud Run HTTP endpoints
- Contains: FastAPI router definitions
- Pattern: Each endpoint performs one workflow (optimize, batch, publish, monitor)
- Entry point: `main.py` - FastAPI app with CORS, routers, metrics endpoint

**src/feedops/pipeline/**
- Purpose: Modular content generation stages
- Contains: Functions that process product data through generation stages
- Pattern: Each module exports functions called in sequence by generator/optimizer
- Key modules:
  - `evidence.py` - Assembles product context for LLM
  - `enrichment.py` - Adds competitive & keyword insights
  - `generator.py` - LLM-based candidate creation
  - `validators.py` - Post-generation quality checks

**src/feedops/integrations/**
- Purpose: External API clients and data fetching
- Contains: Wrapper functions around external SDKs
- Pattern: Each module handles one system (Google Ads, Shopify, etc.)
- Key modules:
  - `google_ads*.py` - Google Ads API (performance, search terms)
  - `shopify_catalog.py` - Shopify product & media data
  - `merchant_center.py` - Google Merchant Center API
  - `search_query_insights.py` - Search term aggregation & scoring

**src/feedops/db/**
- Purpose: Database access layer
- Contains: Supabase client setup, schema models, query helpers
- Key files:
  - `supabase_client.py` - Connection & query helpers
  - `schema.py` - Pydantic models for all Supabase tables (source-of-truth)

**src/feedops/models/**
- Purpose: Data type definitions
- Contains: Pydantic models for products, candidates, scores
- Pattern: Used by database layer, pipeline, API endpoints

**tests/**
- Purpose: Test coverage for Python modules
- Contains: pytest test files
- Pattern: Mirrors src/ structure (test_integrations/, test_pipeline/, etc.)

**supabase/migrations/**
- Purpose: Database schema changes
- Contains: SQL migration files (numbered sequentially)
- Pattern: Each migration is atomic, applies a single schema change

## Key File Locations

**Entry Points:**

- `dashboard/src/app/(dashboard)/page.tsx` - Dashboard overview (accessed after login)
- `dashboard/src/app/login/page.tsx` - Authentication entry point
- `src/feedops/api/main.py` - Python pipeline FastAPI app entry point

**Configuration:**

- `dashboard/.env.local` - Dashboard environment variables (local dev)
- `dashboard/next.config.js` - Next.js build configuration
- `src/feedops/config/settings.py` - Python settings from env vars
- `pyproject.toml` - Python package definition & dependencies
- `supabase/migrations/` - Database schema version history

**Core Logic:**

- `src/feedops/pipeline/generator.py` - LLM-based content generation core
- `src/feedops/integrations/google_ads_search_terms.py` - Search term aggregation
- `dashboard/src/lib/publishing/google-sheets.ts` - Google Sheets publishing logic
- `dashboard/src/lib/regeneration/core.ts` - Legacy TypeScript regeneration (reference only)

**Testing:**

- `tests/` - Test files (mirrors src/ structure)
- `tests/test_pipeline/` - Pipeline unit tests
- `tests/api/` - API integration tests
- `dashboard/src/app/api/regenerate/batch/__tests__/` - Dashboard route tests

## Naming Conventions

**Files:**

- TypeScript: `camelCase.ts` (e.g., `google-sheets.ts`, `evidence-builder.ts`)
- Python: `snake_case.py` (e.g., `generator.py`, `google_ads.py`)
- React components: `PascalCase.tsx` (e.g., `SkuReviewClient.tsx`, `ReviewCard.tsx`)
- Migrations: `NNN_description.sql` (e.g., `001_initial_schema.sql`, `025_fix_publish_batches_status_enum.sql`)

**Directories:**

- Feature domains: `lowercase` (e.g., `publishing/`, `evidence/`, `integrations/`)
- Utility collections: `lowercase` (e.g., `lib/`, `utils/`, `helpers/`)
- UI components: `lowercase` (e.g., `ui/`, `components/`)

**Functions & Variables:**

- TypeScript: `camelCase` (e.g., `getSkuData()`, `publishBatch()`)
- Python: `snake_case` (e.g., `build_evidence_table()`, `fetch_parent_sku()`)
- Constants: `UPPER_SNAKE_CASE` (e.g., `CANDIDATE_SCHEMA`, `PLATFORM_CONTEXT`)
- React components: `PascalCase` (e.g., `SkuReview`, `ReviewCard`)
- Database models: `PascalCase` (e.g., `ParentSKU`, `GeneratedContent`)

## Where to Add New Code

**New Feature (API endpoint + UI):**

1. API endpoint:
   - Location: `dashboard/src/app/api/[domain]/[feature]/route.ts` (if dashboard orchestration needed)
   - Or: `src/feedops/api/[router_name].py` (if backend processing needed)
   - Tests: `tests/api/test_[feature].py` (Python) or `dashboard/src/app/api/[domain]/[feature]/__tests__/route.test.ts` (TypeScript)

2. UI page:
   - Location: `dashboard/src/app/(dashboard)/[feature]/page.tsx`
   - Components: `dashboard/src/components/[feature]/` subdirectory

3. Utilities:
   - Location: `dashboard/src/lib/[domain]/` (if feature-specific) or `dashboard/src/lib/[utility].ts` (if shared)

**New Pipeline Stage (Python):**

- Implementation: `src/feedops/pipeline/[stage_name].py`
- Export function: Should be importable by `generator.py` or relevant orchestrator
- Tests: `tests/test_pipeline/test_[stage_name].py`
- Pattern: Function takes `ParentSKU` or `Evidence` as input, returns enriched version

**New Integration (External API):**

- Implementation: `src/feedops/integrations/[system_name].py`
- Pattern: Wrap external SDK, return typed results
- Tests: `tests/test_integrations/test_[system_name].py`
- Register: Import in pipeline modules that need the data

**Database Schema Change:**

- Migration: `supabase/migrations/NNN_description.sql` (number sequentially)
- Pattern: Single responsibility (add table, add column, create index)
- Update schema docs: `docs/database/SCHEMA.md`

**New Component (React):**

- Location: `dashboard/src/components/[feature]/[ComponentName].tsx`
- Pattern: Use shadcn/ui base components, follow existing patterns in directory
- Props: Interface defining props with clear types
- Example: `dashboard/src/components/review/SkuReviewClient.tsx`

## Special Directories

**dashboard/.next/**
- Purpose: Build output from Next.js compilation
- Generated: Yes
- Committed: No (in .gitignore)
- Action: Ignore, regenerate on build

**src/feedops/__pycache__/**
- Purpose: Python bytecode cache
- Generated: Yes
- Committed: No (in .gitignore)
- Action: Ignore, regenerate on import

**.env files (.env.vercel, .env.local)**
- Purpose: Environment configuration & secrets
- Generated: No
- Committed: No (in .gitignore)
- Action: Never commit; manage via GCP Secrets Manager or Vercel Secrets UI

**exports/, dashboard_data/, data/**
- Purpose: Generated data exports, CSVs, temporary files
- Generated: Yes
- Committed: No (in .gitignore)
- Action: Can be cleaned safely; regenerate as needed

**.planning/**
- Purpose: GSD phase management & codebase analysis
- Generated: Partially (user-created phases, auto-created codebase docs)
- Committed: Yes (but not secrets)
- Action: Track phase progress, codebase mapping documents

**docs/architecture/, docs/audit/**
- Purpose: System design docs, investigation reports
- Generated: No (manually written)
- Committed: Yes
- Action: Update when architecture changes or major bugs are discovered

---

*Structure analysis: 2026-02-20*
