# Technology Stack

**Analysis Date:** 2026-02-11

## Languages

**Primary:**
- TypeScript 5 - Next.js dashboard, API routes, client components
- Python 3.11 - Cloud Run pipeline, integrations, data processing
- JavaScript - NPM dependency resolution, tooling

## Runtime

**Environment:**
- Node.js (via Next.js 16.1.6) - Dashboard and API routes
- Python 3.11 (via Docker container) - Cloud Run pipeline
- Uvicorn 0.25+ (async Python server) - FastAPI runtime

**Package Managers:**
- npm/Node.js - Dashboard dependencies
- uv (Python) - Python dependency management
  - Lockfile: `uv.lock` (present, committed)

## Frameworks

**Core:**
- Next.js 16.1.6 - React meta-framework, API routes, SSR/SSG
- FastAPI - Python async web framework for Cloud Run pipeline
- React 19.2.3 - UI component library
- React DOM 19.2.3 - React rendering

**UI & Styling:**
- TailwindCSS 4 - Utility-first CSS framework
- Radix UI 1.4.3 - Headless component library
- Lucide React 0.563.0 - SVG icon library
- class-variance-authority 0.7.1 - Component variant management
- clsx 2.1.1 - Class name utility
- tailwind-merge 3.4.0 - Tailwind class merging

**Charting & Visualization:**
- Recharts 3.7.0 - React charting library
- Victory (via node_modules) - Alternative charting via Recharts dependencies

**Data & State:**
- TanStack React Query 5.90.20 - Server state management, API caching
- Zustand 5.0.11 - Client state management
- Pydantic 2.0+ - Python data validation and settings
- Pandas 2.0+ - Python data manipulation

**Testing:**
- pytest 7.0+ - Python test runner
- pytest-asyncio 0.21+ - Async test support for pytest
- Playwright/Playwright Test - Browser automation (in `.playwright-mcp` for agent access)

**Build & Dev:**
- Turbopack - Next.js bundler (monorepo root stability)
- Tailwind CSS PostCSS 4 - CSS preprocessing
- ESLint 9 - TypeScript/JavaScript linting
  - Config: `eslint-config-next` (Next.js defaults + web vitals + TypeScript)
  - File: `dashboard/eslint.config.mjs` (flat config format)
- TypeScript 5 - Type checking (`npx tsc --noEmit`)
- Ruff 0.1+ - Python linting and formatting
- mypy 1.0+ - Python type checking
- Rich 13.0+ - Python terminal formatting

## Key Dependencies

**Critical (Content Generation):**
- openai 4.77.0 - OpenAI API client (GPT-5.2 via gpt-5.2 model)
- google-genai 1.0+ - Google Gemini API client (fallback LLM provider)

**Google Integrations:**
- googleapis 171.2.0 - Google APIs (Sheets v4, Drive)
- google-ads-api 23.0.0 - Google Ads API client (JavaScript)
- google-ads 28.4.1+ - Google Ads API client (Python)
- google-auth 2.48.0+ - Google OAuth authentication
- gspread 6.0+ - Google Sheets Python client (alternative to googleapis)
- google-api-python-client 2.0+ - Google APIs Python client

**Database & Storage:**
- @supabase/supabase-js 2.94.0 - Supabase client (TypeScript)
- @supabase/ssr 0.8.0 - Supabase SSR utilities for Next.js
- supabase 2.0+ - Supabase client (Python)

**Shopify:**
- No dedicated SDK in dependencies; uses GraphQL queries via HTTP

**Data Scraping & Competitor Analysis:**
- apify-client 2.22.0 - Apify web scraping platform client (optional integration)

**Utilities:**
- date-fns 4.1.0 - Date manipulation
- csv-parse 5.6.0 - CSV parsing
- typer 0.9+ - CLI framework (Python)
- streamlit 1.30+ - Python data app framework (alternative UI, not production)
- python-dotenv 1.0+ - Environment variable loading
- httpx 0.25+ - Async HTTP client (Python)

**API & Web:**
- next-themes 0.4.6 - Next.js dark mode support
- sonner 2.0.7 - Toast notifications

## Configuration Files

**TypeScript/JavaScript:**
- `dashboard/tsconfig.json` - Strict mode, ES2017 target, path alias `@/*`
- `dashboard/next.config.ts` - Turbopack monorepo root stabilization
- `dashboard/eslint.config.mjs` - Flat format, Next.js web vitals + TypeScript rules

**Python:**
- `pyproject.toml` - Project metadata, dependencies (hatchling build), pytest/ruff/mypy config
- `.python-version` - Python 3.11
- `setup.cfg` or inline tools.* - Ruff/mypy configuration in pyproject.toml

**Docker:**
- `Dockerfile` - Multi-stage Python 3.11 build for Cloud Run
  - Base: `python:3.11-slim`
  - CMD: `uvicorn feedops.api.main:app --host 0.0.0.0 --port 8080`
  - Health check: HTTP GET to `/health` endpoint

**Cloud Build & Deployment:**
- `cloudbuild.yaml` - GCP Cloud Build trigger (push to master)
  - Docker build → Artifact Registry → Cloud Run deploy
  - Memory: 2Gi, CPU: 2, Timeout: 900s, Max instances: 10
  - Secrets: 9 GCP Secret Manager bindings (all env vars)

**Ignore/Exclude:**
- `.gitignore` - Standard Node/Python ignores
- `.gcloudignore` - Excludes large files from Cloud Build (e.g., node_modules, .venv)

## Platform & Deployment

**Development:**
- Local: Node.js (npm), Python 3.11 (uv), Docker (optional)
- Dashboard: `npm run dev` (Next.js dev server on http://localhost:3000)
- Pipeline: `python -m feedops.api.main` or Docker container

**Production - Dashboard:**
- Vercel (Next.js hosting)
- Deployment: Auto-deploy on push to master via Vercel GitHub integration
- Project ID: `prj_00zlLdZVgbP8XjDWIEXSRdFyqDqA`
- Team ID: `team_KsEZDE8Pw0bKQDGlieBVBQVs`
- URL: https://allied-feed-ops.vercel.app

**Production - Pipeline:**
- Google Cloud Run (us-east1)
- Service: `feedops-pipeline`
- Trigger: Cloud Build on push to master
- Artifact Registry: `us-east1-docker.pkg.dev/bobbys-project-346400/cloud-run-source-deploy`
- URL: https://feedops-pipeline-623866089882.us-east1.run.app
- Service Account (runtime): `profit-pilot-runtime@bobbys-project-346400.iam.gserviceaccount.com`

**Build Infrastructure:**
- GCP Project: `bobbys-project-346400`
- Cloud Build trigger: `feedops-pipeline-deploy`
- Build Service Account: `profit-pilot-build@bobbys-project-346400.iam.gserviceaccount.com`
- Artifact Registry location: `us-east1` region

## Platform Requirements

**Development:**
- Node.js 18+ with npm or equivalent
- Python 3.11+
- Docker (optional, for Cloud Run local testing)
- Git

**Production Dashboard:**
- Node.js runtime (managed by Vercel)
- Environment variables: Supabase URL/key, Shopify credentials, Google/OpenAI API keys

**Production Pipeline:**
- Cloud Run runtime (managed by GCP)
- Docker container registry (GCP Artifact Registry)
- 9 GCP Secrets (see INTEGRATIONS.md)

## Build Verification

**Before deployment:**
```bash
# TypeScript check
cd dashboard && npx tsc --noEmit

# Linting
npm run lint  # Runs ESLint

# Build
npm run build  # Next.js production build
```

---

*Stack analysis: 2026-02-11*
