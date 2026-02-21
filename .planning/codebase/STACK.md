# Technology Stack

**Analysis Date:** 2026-02-20

## Languages

**Primary:**
- TypeScript 5 - Next.js dashboard (`dashboard/src/**/*.ts`, `dashboard/src/**/*.tsx`)
- Python 3.11 - Cloud Run pipeline (`src/feedops/**/*.py`)

**Secondary:**
- JavaScript (Node.js) - Build tooling, scripts
- SQL - Supabase queries and migrations

## Runtime

**Environment:**
- Node.js (LTS) - Dashboard dev server and build
- Python 3.11 - Content generation pipeline
- Cloud Run (containerized Python FastAPI) - Production pipeline

**Package Manager:**
- npm (Node.js) - Dashboard dependencies
- uv/pip (Python) - Python dependencies
- Lockfiles: `package-lock.json` (npm), `pyproject.toml` (Python hatch)

## Frameworks

**Core:**
- Next.js 16.1.6 - Full-stack React framework for dashboard (`dashboard/src/app/**`)
  - App Router (file-based routing)
  - Server Components and API Routes
- FastAPI 0.109.0+ - API framework for Cloud Run pipeline (`src/feedops/api/main.py`)
- React 19.2.3 - UI framework (dashboard)

**UI/Styling:**
- Tailwind CSS 4 - Utility-first CSS framework
- Radix UI 1.4.3 - Headless component library
- Tremor 3.18.7 - Analytics dashboard components
- Recharts 3.7.0 - Chart library for performance dashboards
- Lucide React 0.563.0 - Icon library
- Sonner 2.0.7 - Toast notifications
- Zustand 5.0.11 - Client-side state management

**Testing:**
- Vitest 3.2.4 - Unit/integration test runner (`dashboard/vitest.config.ts`)
- Playwright 1.58.2 - E2E testing framework
- Testing Library (React) 16.3.0 - Component testing utilities

**Build/Dev:**
- TypeScript 5 - Type checking
- ESLint 9 - Code linting (flat config)
- Tailwind CSS PostCSS 4 - CSS processing
- Vite/esbuild - Bundling (via Next.js)

## Key Dependencies

**Critical:**
- @supabase/supabase-js 2.94.0 - Database client (`dashboard/src/lib/supabase/**`)
- @supabase/ssr 0.8.0 - Server-side session management (Next.js)
- openai 4.77.0 (dashboard), 1.0+ (Python) - LLM client for content generation
- google-genai 1.0+ - Google Gemini API client (fallback LLM provider)
- google-ads-api 23.0.0 - Google Ads API wrapper for shopping performance
- google-api-python-client 2.0+ - Google APIs (Sheets, Drive, etc.)
- googleapis 171.2.0 (TypeScript) - Google API client for Sheets integration
- gspread 6.0+ - Google Sheets Python client

**Data Handling:**
- pandas 2.0+ - Data manipulation and analysis (Python)
- pydantic 2.0+, pydantic-settings 2.0+ - Data validation (Python)
- csv-parse 5.6.0 - CSV parsing (dashboard)
- date-fns 4.1.0 - Date manipulation (dashboard)

**Infrastructure:**
- uvicorn[standard] 0.27.0+ - ASGI server for Cloud Run
- httpx 0.25+ - Async HTTP client (Python)
- supabase 2.0+ - Python Supabase client
- bingads 13.0.x - Bing Ads SDK for performance metrics

**Async/HTTP:**
- @tanstack/react-query 5.90.20 - Server state management (dashboard)
- python-multipart 0.0.6+ - Multipart form parsing (FastAPI)

**Utilities:**
- python-dotenv 1.0+ - Environment variable loading (Python)
- typer 0.9+ - CLI framework (Python)
- rich 13.0+ - Terminal output formatting (Python)
- prometheus-client 0.20+ - Metrics collection (Python pipeline)
- streamlit 1.30+ - Analytics UI (optional, legacy)

## Configuration

**Environment:**
- `.env.local` (dashboard) - Next.js dev server configuration
- `.env` files - Environment variable management (local development only)
- GCP Secrets Manager - Cloud Run runtime secrets (production)
  - `feedops-openai-api-key`
  - `feedops-supabase-url`, `feedops-supabase-key`
  - `feedops-google-ads-*` (developer-token, client-id, client-secret, refresh-token, login-customer-id)
  - `feedops-gemini-api-key`
  - `feedops-slack-webhook-url`

**Build:**
- `dashboard/tsconfig.json` - TypeScript configuration with path aliases (`@/*`)
- `dashboard/eslint.config.mjs` - ESLint flat config (Next.js core-web-vitals + TypeScript)
- `dashboard/vitest.config.ts` - Vitest configuration for unit testing
- `.python-version` - Python 3.11 version specification
- `pyproject.toml` - Python project metadata and dependencies (hatchling build backend)
- `Dockerfile` - Cloud Run container definition (Python 3.11-slim base)
- `cloudbuild.yaml` - GCP Cloud Build pipeline configuration

**Runtime Secrets:**
- `NEXT_PUBLIC_SUPABASE_URL` - Supabase project URL (public)
- `NEXT_PUBLIC_SUPABASE_ANON_KEY` - Supabase anonymous key (public, safe for browser)
- `SUPABASE_SERVICE_ROLE_KEY` - Supabase service role (server-only, elevated permissions)
- `GOOGLE_SERVICE_ACCOUNT_KEY` - Base64-encoded GCP service account JSON (Google Sheets integration)
- `OPENAI_API_KEY` - OpenAI API key
- `GEMINI_API_KEY` - Google Gemini API key
- `GOOGLE_ADS_*` - Google Ads OAuth2 credentials (developer token, client ID/secret, refresh token, login customer ID)

## Platform Requirements

**Development:**
- Node.js LTS (tested with current LTS)
- Python 3.11+
- npm or yarn
- uv or pip for Python
- Git

**Production (Cloud Run):**
- Python 3.11-slim container
- 2 GB memory allocation
- 2 CPU allocation
- 900 second timeout
- Max 10 concurrent instances
- Region: us-east1

**Dashboard Deployment:**
- Vercel (automatic deployment on push to master)
- Next.js 16.1.6 compatible
- Server Components and API Routes supported

---

*Stack analysis: 2026-02-20*
