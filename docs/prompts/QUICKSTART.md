# FeedOps Prompt Quick Start Guide

## Execution Order

### Phase 1: Core Dashboard Foundation
1. **Prompt 10** → Dashboard Implementation (07 & 08)

### Phase 2: Content Quality Improvements (Dashboard-Only, No Infrastructure Needed)
2. **Prompt 17** → Description Quality Analyzer
3. **Prompt 13** → Competitor Intelligence Panel
4. **Prompt 14** → Search Query Insights
5. **Prompt 18** → Keyword Gap Analysis

### Phase 3: Fix Critical Quality Issues
6. **Prompt 19** → Fix Description Generation Quality (enriches prompt data)
7. **Prompt 20** → Enhance SKU Review Page (product images + lifestyle approval)

### Phase 4: Infrastructure for Heavy Processing
8. **Prompt 09** → GCP Cloud Run Setup
9. **Prompt 21** → Unify TypeScript & Python Methodology (CRITICAL)

### Phase 5: Performance Monitoring
10. **Prompt 22** → Performance Data Lifecycle (FIX Search Insights sync first!)

### Phase 6: Future-Proofing & ROI
11. **Prompt 15** → Agentic Commerce (UCP)
12. **Prompt 12** → A/B Testing Dashboard
13. **Prompt 16** → Multi-Variant Images

### Phase 7: Final Audit (ALWAYS LAST)
14. **Prompt 11** → Production Readiness Audit

After each prompt, run the **Verification & Completion Prompt** below.

---

## Quick Start: Prompt 10 (Dashboard Implementation)

**When to run:** First - implements remaining dashboard features

**Copy and paste into a new Claude Code chat:**

```
I need to implement the remaining dashboard features. Please enter plan mode and use the prompt at docs/prompts/10-complete-dashboard-implementation.md as your guide.

Key context:
- Repository: /Users/bobby/Documents/GitHub/Allied-FeedOps
- Dashboard: /dashboard (Next.js 14+)
- Live URL: https://allied-feed-ops.vercel.app
- Supabase project: qezuszwufortkiutlhym
- Google Ads customer ID: 6253381786

Goals:
1. Implement Prompt 07 (Dashboard Overview with real stats and charts)
2. Implement Prompt 08 (SKU Selection & Generation page)
3. Verify all prompts 01-08 are correctly implemented
4. Ensure build passes and no TypeScript errors

**REQUIRED WORKFLOW (superpowers skills):**

1. BEFORE any implementation decisions: `/superpowers:brainstorming` - explore requirements and design
2. BEFORE writing any code: `/superpowers:writing-plans` - create step-by-step implementation plan
3. FOR each feature/bugfix: `/superpowers:test-driven-development` - write tests first
4. FOR independent tasks: `/superpowers:dispatching-parallel-agents` - run 2+ tasks in parallel
5. FOR any bugs found: `/superpowers:systematic-debugging` - investigate before fixing
6. BEFORE claiming done: `/superpowers:verification-before-completion` - run verification commands, show evidence

Use `TaskCreate` to build a task list from the plan. Use `TaskUpdate` to mark tasks in_progress and completed.

Do NOT commit changes until the full implementation is verified with passing tests and builds.
```

---

## Quick Start: Prompt 17 (Description Quality Analyzer)

**When to run:** Priority 1 - Real-time feedback on description quality

**Copy and paste into a new Claude Code chat:**

```
I need to implement the Description Quality Analyzer for the FeedOps dashboard. Please enter plan mode and use the prompt at docs/prompts/17-description-quality-analyzer.md as your guide.

Key context:
- Repository: /Users/bobby/Documents/GitHub/Allied-FeedOps
- Dashboard: /dashboard (Next.js 14+)
- Live URL: https://allied-feed-ops.vercel.app
- Scoring dimensions are defined in AGENTS.md

Goals:
1. Create QualityAnalyzer.tsx component with 6 scoring dimensions
2. Create quality-scoring.ts library with scoring logic
3. Integrate analyzer into the SKU review page sidebar
4. Add real-time updates as content changes
5. Show issues, suggestions, and trust signal checklist

The analyzer should score:
- Specificity (concrete claims vs vague adjectives)
- Benefit Coverage (benefits in first 150 chars)
- Keyword Inclusion (target keywords in optimal positions)
- Format Adherence (character limits, structure)
- Brand Voice (confident, premium-appropriate)
- Factual Accuracy (claims traceable to product data)

**REQUIRED WORKFLOW (superpowers skills):**

1. BEFORE any implementation decisions: `/superpowers:brainstorming` - explore requirements and design
2. BEFORE writing any code: `/superpowers:writing-plans` - create step-by-step implementation plan
3. FOR each feature/bugfix: `/superpowers:test-driven-development` - write tests first
4. FOR independent tasks: `/superpowers:dispatching-parallel-agents` - run 2+ tasks in parallel
5. FOR any bugs found: `/superpowers:systematic-debugging` - investigate before fixing
6. BEFORE claiming done: `/superpowers:verification-before-completion` - run verification commands, show evidence

Use `TaskCreate` to build a task list from the plan. Use `TaskUpdate` to mark tasks in_progress and completed.

Do NOT commit changes until the full implementation is verified with passing tests and builds.
```

---

## Quick Start: Prompt 13 (Competitor Intelligence)

**When to run:** Priority 1 - Learn from competitor content patterns

**Prerequisites:** Apify MCP is configured

**Copy and paste into a new Claude Code chat:**

```
I need to implement the Competitor Intelligence Panel for the FeedOps dashboard. Please enter plan mode and use the prompt at docs/prompts/13-competitor-intelligence.md as your guide.

Key context:
- Repository: /Users/bobby/Documents/GitHub/Allied-FeedOps
- Dashboard: /dashboard (Next.js 14+)
- Apify MCP: Configured and available
- Supabase project: qezuszwufortkiutlhym

Goals:
1. Apply database migration for competitor tables
2. Create /competitors page with category selector
3. Integrate Apify MCP for scraping Amazon, Wayfair, Home Depot
4. Build pattern extraction logic (title structure, keywords, benefits, trust signals)
5. Show side-by-side comparison with our content
6. Display winning patterns with frequency counts

Use the Apify MCP tools to:
- Search for appropriate scraper actors
- Configure and run scrapers for bathroom fixtures
- Store results in competitor_listings table

**REQUIRED WORKFLOW (superpowers skills):**

1. BEFORE any implementation decisions: `/superpowers:brainstorming` - explore requirements and design
2. BEFORE writing any code: `/superpowers:writing-plans` - create step-by-step implementation plan
3. FOR each feature/bugfix: `/superpowers:test-driven-development` - write tests first
4. FOR independent tasks: `/superpowers:dispatching-parallel-agents` - run 2+ tasks in parallel
5. FOR any bugs found: `/superpowers:systematic-debugging` - investigate before fixing
6. BEFORE claiming done: `/superpowers:verification-before-completion` - run verification commands, show evidence

Use `TaskCreate` to build a task list from the plan. Use `TaskUpdate` to mark tasks in_progress and completed.

Do NOT commit changes until the full implementation is verified with passing tests and builds.
```

---

## Quick Start: Prompt 14 (Search Query Insights)

**When to run:** Priority 1 - Match actual search behavior

**Prerequisites:**
- Google Ads API credentials configured
- Merchant API MCP available (`mcp__merchant-api-devdocs__*`)

**Copy and paste into a new Claude Code chat:**

```
I need to implement the Search Query Insights dashboard for FeedOps. Please enter plan mode and use the prompt at docs/prompts/14-search-query-insights.md as your guide.

Key context:
- Repository: /Users/bobby/Documents/GitHub/Allied-FeedOps
- Dashboard: /dashboard (Next.js 14+)
- Google Ads customer ID: 6253381786
- Existing integration: src/feedops/integrations/google_ads_performance.py

MCP Tools to Use:
- **Merchant API MCP** (`mcp__merchant-api-devdocs__*`): Query GMC product data
  - `query_mapi_docs` for documentation
  - `find_mapi_code_sample` for code examples
- **Google Ads MCP** (`mcp__google-ads-mcp__*`): Execute GAQL queries
- **merchant-integrator agent**: Use via Task tool for Merchant API setup

Goals:
1. Apply database migration for search_queries tables (with Keyword Planner fields)
2. Create Python integration for search_term_view GAQL query
3. Create KeywordPlannerClient for search volume enrichment
4. Create /search-insights page with query table + volume/competition columns
5. Build gap analysis component showing keyword coverage
6. Integrate Merchant API for product performance correlation
7. Track query coverage improvement over time

Key APIs:

1. Google Ads Search Terms (actual queries):
SELECT search_term_view.search_term, metrics.impressions, metrics.clicks, metrics.conversions, metrics.conversions_value, segments.product_item_id
FROM search_term_view
WHERE segments.date DURING LAST_30_DAYS AND campaign.advertising_channel_type = 'SHOPPING'

2. Keyword Planner (search volume context):
- GenerateKeywordHistoricalMetrics: avg_monthly_searches, competition_index (0-100), CPC ranges
- GenerateKeywordIdeas: discover related keywords from seeds
- Rate limited - cache results (metrics update monthly)

3. Merchant API (product feed data):
SELECT offer_id, clicks, impressions, click_through_rate FROM product_performance_view
SELECT id, offer_id, title, aggregated_reporting_context_status FROM product_view

**REQUIRED WORKFLOW (superpowers skills):**

1. BEFORE any implementation decisions: `/superpowers:brainstorming` - explore requirements and design
2. BEFORE writing any code: `/superpowers:writing-plans` - create step-by-step implementation plan
3. FOR each feature/bugfix: `/superpowers:test-driven-development` - write tests first
4. FOR independent tasks: `/superpowers:dispatching-parallel-agents` - run 2+ tasks in parallel
5. FOR any bugs found: `/superpowers:systematic-debugging` - investigate before fixing
6. BEFORE claiming done: `/superpowers:verification-before-completion` - run verification commands, show evidence

Use `TaskCreate` to build a task list from the plan. Use `TaskUpdate` to mark tasks in_progress and completed.

Do NOT commit changes until the full implementation is verified with passing tests and builds.
```

---

## Quick Start: Prompt 18 (Keyword Gap Analysis)

**When to run:** Priority 1 - Identify missing keywords and prioritize optimization

**Prerequisites:**
- Search Query Insights (Prompt 14) implemented
- Merchant API MCP available (`mcp__merchant-api-devdocs__*`)

**Copy and paste into a new Claude Code chat:**

```
I need to implement the Keyword Gap Analysis dashboard for FeedOps. Please enter plan mode and use the prompt at docs/prompts/18-keyword-gap-analysis.md as your guide.

Key context:
- Repository: /Users/bobby/Documents/GitHub/Allied-FeedOps
- Dashboard: /dashboard (Next.js 14+)
- Depends on: Search Query Insights (Prompt 14)

MCP Tools to Use:
- **Merchant API MCP** (`mcp__merchant-api-devdocs__*`): Query GMC product data
  - Get current titles from product_view
  - Get click_potential for prioritization
- **Google Ads MCP** (`mcp__google-ads-mcp__*`): Keyword Planner data
- **merchant-integrator agent**: Use via Task tool for Merchant API setup

Goals:
1. Apply database migration for keyword_gaps tables (with competition fields)
2. Create gap scoring algorithm with opportunity_score (factors in competition)
3. Create KeywordPlannerClient integration for search volume enrichment
4. Create /keyword-gaps page with opportunity ranking + competition badges
5. Build KeywordSuggestions component with volume/competition context
6. Add "Discover Related Keywords" using Keyword Planner GenerateKeywordIdeas
7. Integrate Merchant API click_potential for prioritization
8. Track gap closure progress over time

Key Scoring Formula:
- gap_score = monthly_volume × (1 if not in title, 0.3 if in description only)
- opportunity_score = gap_score × ((100 - competition_index) / 100)
- Boost 50% if Merchant API click_potential = 'HIGH'

Keyword Planner Integration:
- Enrich gaps with: avg_monthly_searches, competition (LOW/MEDIUM/HIGH), competition_index (0-100)
- Show CPC estimates (low_top_of_page_bid, high_top_of_page_bid) for ROI context
- Cache results - metrics only update monthly

Merchant API Integration:
- Query product_view for: title, click_potential, aggregated_reporting_context_status
- Products with HIGH click_potential + keyword gaps = top priority

**REQUIRED WORKFLOW (superpowers skills):**

1. BEFORE any implementation decisions: `/superpowers:brainstorming` - explore requirements and design
2. BEFORE writing any code: `/superpowers:writing-plans` - create step-by-step implementation plan
3. FOR each feature/bugfix: `/superpowers:test-driven-development` - write tests first
4. FOR independent tasks: `/superpowers:dispatching-parallel-agents` - run 2+ tasks in parallel
5. FOR any bugs found: `/superpowers:systematic-debugging` - investigate before fixing
6. BEFORE claiming done: `/superpowers:verification-before-completion` - run verification commands, show evidence

Use `TaskCreate` to build a task list from the plan. Use `TaskUpdate` to mark tasks in_progress and completed.

Do NOT commit changes until the full implementation is verified with passing tests and builds.
```

---

## Quick Start: Prompt 09 (GCP Cloud Run Setup)

**When to run:** After content quality prompts - sets up infrastructure for batch generation

**Prerequisites:**
- GCP project with billing enabled
- `gcloud` CLI installed
- Docker installed

**Copy and paste into a new Claude Code chat:**

```
I need to set up GCP Cloud Run for the FeedOps Python pipeline. Please enter plan mode and use the prompt at docs/prompts/09-gcp-cloud-run-setup.md as your guide.

Key context:
- Repository: /Users/bobby/Documents/GitHub/Allied-FeedOps
- Python pipeline: /src/feedops/
- Dashboard: /dashboard (needs to call Cloud Run)
- Supabase project: qezuszwufortkiutlhym
- Existing migration: supabase/migrations/006_batch_generation_jobs.sql (already applied)

CRITICAL - Use Context7 MCP for Documentation:
Before writing any FastAPI or GCP code, use the Context7 MCP server to fetch current documentation:
- mcp__plugin_context7_context7__resolve-library-id("fastapi")
- mcp__plugin_context7_context7__resolve-library-id("google-cloud-run")
- mcp__plugin_context7_context7__query-docs(library_id, "async endpoints")
- mcp__plugin_context7_context7__query-docs(library_id, "deployment")

Goals:
1. Install and configure gcloud-mcp and cloud-run-mcp servers in Claude Code
2. Create Dockerfile for Python pipeline (include data/ directory for catalog)
3. Create FastAPI entry point (src/feedops/api/main.py) with proper Pydantic v2 models
4. Create TypeScript client (dashboard/src/lib/pipeline-client.ts)
5. Test container locally with Docker before Cloud Run deployment
6. Document deployment commands (don't actually deploy without my approval)

Endpoints to expose:
- GET / - API info
- GET /health - Health check with catalog + Supabase status
- POST /optimize-sku - Single SKU optimization
- POST /regenerate - Content regeneration with feedback
- POST /batch-optimize - Batch job creation
- GET /batch-status/{job_id} - Batch job progress

Important:
- Do NOT store secrets in code - use Secret Manager
- Use existing batch_generation_jobs table (migration 006)
- Match Python function signatures exactly (optimize_parent_sku needs catalog_path)

**REQUIRED WORKFLOW (superpowers skills):**

1. BEFORE any implementation decisions: `/superpowers:brainstorming` - explore requirements and design
2. BEFORE writing any code: `/superpowers:writing-plans` - create step-by-step implementation plan
3. FOR each feature/bugfix: `/superpowers:test-driven-development` - write tests first
4. FOR independent tasks: `/superpowers:dispatching-parallel-agents` - run 2+ tasks in parallel
5. FOR any bugs found: `/superpowers:systematic-debugging` - investigate before fixing
6. BEFORE claiming done: `/superpowers:verification-before-completion` - run verification commands, show evidence

Use `TaskCreate` to build a task list from the plan. Use `TaskUpdate` to mark tasks in_progress and completed.

Do NOT commit changes until the full implementation is verified with passing tests and builds.
```

---

## Quick Start: Prompt 15 (Agentic Commerce - UCP)

**When to run:** Priority 2 - Future-proof with AI agent discovery

**Prerequisites:** Shopify Plus account required for Agentic Storefronts

**Copy and paste into a new Claude Code chat:**

```
I need to implement Agentic Commerce (UCP) integration for FeedOps. Please enter plan mode and use the prompt at docs/prompts/15-agentic-commerce-ucp.md as your guide.

Key context:
- Repository: /Users/bobby/Documents/GitHub/Allied-FeedOps
- Dashboard: /dashboard (Next.js 14+)
- Shopify Plus required for full UCP features
- UCP announced by Shopify + Google January 2026

Goals:
1. Document Shopify Plus Agentic Storefronts configuration
2. Create /agents dashboard page for agent traffic monitoring
3. Apply database migration for agent_sessions tracking
4. Build product readiness scoring for agent discovery
5. Create agent-optimized metafields structure
6. Track agent traffic and conversion funnel

This enables AI agents (ChatGPT, Gemini, Copilot, Perplexity) to:
- Discover Allied Brass products programmatically
- Read detailed product information
- Complete purchases on behalf of users

**REQUIRED WORKFLOW (superpowers skills):**

1. BEFORE any implementation decisions: `/superpowers:brainstorming` - explore requirements and design
2. BEFORE writing any code: `/superpowers:writing-plans` - create step-by-step implementation plan
3. FOR each feature/bugfix: `/superpowers:test-driven-development` - write tests first
4. FOR independent tasks: `/superpowers:dispatching-parallel-agents` - run 2+ tasks in parallel
5. FOR any bugs found: `/superpowers:systematic-debugging` - investigate before fixing
6. BEFORE claiming done: `/superpowers:verification-before-completion` - run verification commands, show evidence

Use `TaskCreate` to build a task list from the plan. Use `TaskUpdate` to mark tasks in_progress and completed.

Do NOT commit changes until the full implementation is verified with passing tests and builds.
```

---

## Quick Start: Prompt 12 (A/B Testing Dashboard)

**When to run:** Priority 3 - Prove ROI of optimizations

**Copy and paste into a new Claude Code chat:**

```
I need to implement the A/B Testing & Performance Attribution dashboard for FeedOps. Please enter plan mode and use the prompt at docs/prompts/12-ab-testing-dashboard.md as your guide.

Key context:
- Repository: /Users/bobby/Documents/GitHub/Allied-FeedOps
- Dashboard: /dashboard (Next.js 14+)
- Google Ads customer ID: 6253381786
- Existing tables: performance_baselines, performance_snapshots

Goals:
1. Apply database migration for optimization_cohorts tables
2. Create /ab-testing page with cohort management
3. Build statistical significance calculator (two-proportion z-test)
4. Create performance comparison table (before/after metrics)
5. Visualize lift with confidence intervals
6. Calculate aggregate program ROI

The dashboard should:
- Organize optimized SKUs into cohorts
- Track baseline vs post-optimization metrics (CTR, CVR, ROAS)
- Calculate lift percentage with statistical significance
- Show overall program ROI estimation

**REQUIRED WORKFLOW (superpowers skills):**

1. BEFORE any implementation decisions: `/superpowers:brainstorming` - explore requirements and design
2. BEFORE writing any code: `/superpowers:writing-plans` - create step-by-step implementation plan
3. FOR each feature/bugfix: `/superpowers:test-driven-development` - write tests first
4. FOR independent tasks: `/superpowers:dispatching-parallel-agents` - run 2+ tasks in parallel
5. FOR any bugs found: `/superpowers:systematic-debugging` - investigate before fixing
6. BEFORE claiming done: `/superpowers:verification-before-completion` - run verification commands, show evidence

Use `TaskCreate` to build a task list from the plan. Use `TaskUpdate` to mark tasks in_progress and completed.

Do NOT commit changes until the full implementation is verified with passing tests and builds.
```

---

## Quick Start: Prompt 16 (Multi-Variant Images)

**When to run:** Priority 4 - Complete product coverage with finish-specific images

**Copy and paste into a new Claude Code chat:**

```
I need to implement Multi-Variant Lifestyle Image Generation for FeedOps. Please enter plan mode and use the prompt at docs/prompts/16-multi-variant-images.md as your guide.

Key context:
- Repository: /Users/bobby/Documents/GitHub/Allied-FeedOps
- Dashboard: /dashboard (Next.js 14+)
- Existing: src/feedops/pipeline/lifestyle_images.py
- Allied Brass has 28 finish options

Goals:
1. Apply database migration for variant_images tables
2. Create variant_lifestyle_images.py for multi-finish generation
3. Create shopify_media_upload.py for Shopify GraphQL media API
4. Create /images page for variant image management
5. Generate finish-specific prompts with correct color descriptions
6. Apply IPTC metadata to all generated images
7. Push images to Shopify variant media

The generator should:
- Identify all finish variants for each master SKU
- Generate lifestyle images showing each finish in context
- Upload to GCS with CDN URLs
- Push to Shopify variant media via GraphQL

**REQUIRED WORKFLOW (superpowers skills):**

1. BEFORE any implementation decisions: `/superpowers:brainstorming` - explore requirements and design
2. BEFORE writing any code: `/superpowers:writing-plans` - create step-by-step implementation plan
3. FOR each feature/bugfix: `/superpowers:test-driven-development` - write tests first
4. FOR independent tasks: `/superpowers:dispatching-parallel-agents` - run 2+ tasks in parallel
5. FOR any bugs found: `/superpowers:systematic-debugging` - investigate before fixing
6. BEFORE claiming done: `/superpowers:verification-before-completion` - run verification commands, show evidence

Use `TaskCreate` to build a task list from the plan. Use `TaskUpdate` to mark tasks in_progress and completed.

Do NOT commit changes until the full implementation is verified with passing tests and builds.
```

---

## Quick Start: Prompt 11 (Production Readiness Audit)

**When to run:** ALWAYS LAST - Final verification before production

**Copy and paste into a new Claude Code chat:**

```
I need to run a production readiness audit on the FeedOps dashboard. Please enter plan mode and use the prompt at docs/prompts/11-production-readiness-audit.md as your guide.

Key context:
- Repository: /Users/bobby/Documents/GitHub/Allied-FeedOps
- Dashboard: /dashboard (Next.js 14+)
- Live URL: https://allied-feed-ops.vercel.app
- Supabase project: qezuszwufortkiutlhym

Goals:
1. Security audit (auth, env vars, input validation, CORS)
2. Performance audit (bundle size, query optimization, caching)
3. Error handling audit (boundaries, logging, monitoring)
4. Accessibility audit (WCAG, responsive design)
5. Manual QA checklist verification
6. Documentation completeness check

Generate a summary report of all findings with:
- Critical issues (must fix)
- Warnings (should fix)
- Recommendations (nice to have)

**REQUIRED WORKFLOW (superpowers skills):**

1. BEFORE any implementation decisions: `/superpowers:brainstorming` - explore requirements and design
2. BEFORE writing any code: `/superpowers:writing-plans` - create step-by-step implementation plan
3. FOR each feature/bugfix: `/superpowers:test-driven-development` - write tests first
4. FOR independent tasks: `/superpowers:dispatching-parallel-agents` - run 2+ tasks in parallel
5. FOR any issues found: `/superpowers:systematic-debugging` - investigate before proposing fixes
6. BEFORE claiming done: `/superpowers:verification-before-completion` - run verification commands, show evidence

Use `TaskCreate` to build a task list from the plan. Use `TaskUpdate` to mark tasks in_progress and completed.

Do NOT commit changes until I've reviewed the findings.
```

---

## Quick Start: Prompt 19 (Fix Description Generation Quality)

**When to run:** Priority 2 - After content quality prompts, before Cloud Run

**Copy and paste into a new Claude Code chat:**

```
I need to fix the poor quality descriptions being generated for Google and Bing. Please enter plan mode and use the prompt at docs/prompts/19-fix-description-generation-quality.md as your guide.

Key context:
- Repository: /Users/bobby/Documents/GitHub/Allied-FeedOps
- Dashboard: /dashboard (Next.js 14+)
- Regenerate API: dashboard/src/app/api/regenerate/route.ts
- Python pipeline prompts: src/feedops/pipeline/prompts.py

The Problem:
The dashboard's regeneration passes only 5 basic fields (master_sku, product_title, category, finish, dimensions) to the LLM. The Python pipeline builds a rich evidence table with product specs, features, bullets, images, keywords, and collection context. That's why Shopify descriptions are good but Google/Bing are robotic.

CRITICAL DATA SOURCES TO USE:

1. PRIMARY - Product Catalog CSV (data/Acatalog.csv):
   - 75,773 rows of rich product data
   - Contains: narrative_copy (full descriptions!), 6 bullet points, high-res image URLs
   - Has GMCID mapping, collection info, all specs
   - LOAD THIS INTO SUPABASE as product_catalog table

2. Shopify Dev MCP Server:
   - Use shopify-dev-mcp tools to look up Shopify Admin API documentation
   - introspect_graphql_schema, learn_shopify_api, search_docs_chunks
   - For fetching live product data if needed

3. Google Merchant Center:
   - Current feed data via Google Ads MCP
   - variant_index.gmc_offer_id for mapping

Goals:
1. Use Playwright MCP to inspect current "Prompt used" section on review page
2. Apply migration to create product_catalog table (migration 010)
3. Import Acatalog.csv into Supabase (75K+ products)
4. Build TypeScript evidence table builder that queries product_catalog
5. Update regenerate API to pass comprehensive context including:
   - narrative_copy (baseline description from CSV)
   - All 6 bullet points
   - High-res product image URL (for vision)
   - Collection name, material, style, mounting type
6. Add variant-specific finish context for Google/Bing

**REQUIRED WORKFLOW (superpowers skills):**

1. BEFORE any implementation decisions: `/superpowers:brainstorming` - explore requirements and design
2. BEFORE writing any code: `/superpowers:writing-plans` - create step-by-step implementation plan
3. FOR each feature/bugfix: `/superpowers:test-driven-development` - write tests first
4. FOR independent tasks: `/superpowers:dispatching-parallel-agents` - run 2+ tasks in parallel
5. FOR any bugs found: `/superpowers:systematic-debugging` - investigate before fixing
6. BEFORE claiming done: `/superpowers:verification-before-completion` - run verification commands, show evidence

Use `TaskCreate` to build a task list from the plan. Use `TaskUpdate` to mark tasks in_progress and completed.

Do NOT commit changes until the full implementation is verified with passing tests and builds.
```

---

## Quick Start: Prompt 20 (Enhance SKU Review Page)

**When to run:** Priority 2 - After Prompt 19

**Copy and paste into a new Claude Code chat:**

```
I need to enhance the SKU review page with product images and better lifestyle image approval. Please enter plan mode and use the prompt at docs/prompts/20-enhance-sku-review-page.md as your guide.

Key context:
- Repository: /Users/bobby/Documents/GitHub/Allied-FeedOps
- Dashboard: /dashboard (Next.js 14+)
- Review page: dashboard/src/components/review/SkuReviewClient.tsx

Two Critical Fixes:

1. ADD PRODUCT HERO IMAGE
   - Reviewers can't see the product they're reviewing
   - Need to display the product's main image prominently
   - Add zoom/enlarge capability
   - Show variant-specific images when a finish is selected

2. ENHANCE LIFESTYLE IMAGE APPROVAL
   - Current section is minimal and only shows when images exist
   - Need clear separation of master SKU vs variant-level images
   - Add approval workflow (approve/reject with reasons)
   - Add "select for publishing" functionality
   - Track approval status at correct level (master vs variant)

Goals:
1. Create ProductHeroImage.tsx component
2. Create enhanced LifestyleImageReview.tsx component
3. Create ImageApprovalCard.tsx for individual image cards
4. Add image approval API endpoints
5. Update SkuReviewClient to include new components
6. Add database schema for image approval tracking

**REQUIRED WORKFLOW (superpowers skills):**

1. BEFORE any implementation decisions: `/superpowers:brainstorming` - explore requirements and design
2. BEFORE writing any code: `/superpowers:writing-plans` - create step-by-step implementation plan
3. FOR each feature/bugfix: `/superpowers:test-driven-development` - write tests first
4. FOR independent tasks: `/superpowers:dispatching-parallel-agents` - run 2+ tasks in parallel
5. FOR any bugs found: `/superpowers:systematic-debugging` - investigate before fixing
6. BEFORE claiming done: `/superpowers:verification-before-completion` - run verification commands, show evidence

Use `TaskCreate` to build a task list from the plan. Use `TaskUpdate` to mark tasks in_progress and completed.

Do NOT commit changes until the full implementation is verified with passing tests and builds.
```

---

## Verification & Completion Prompt

**When to run:** After EACH prompt implementation is complete

**Copy and paste into the SAME chat where you just implemented a prompt:**

```
The implementation appears complete. Before we commit and push, I need you to:

## 1. VERIFICATION CHECKLIST

Run these checks and report results:

### Build Verification
- Run `cd dashboard && npm run build` - report exit code
- Run `cd dashboard && npx tsc --noEmit` - report any errors
- Run `cd dashboard && npm run lint` - report any warnings/errors

### Python Tests (if Python code was modified)
- Run `source .venv/bin/activate && PYTHONPATH=./src python -m pytest tests/ -v --tb=short` - report pass/fail count

### Implementation Completeness
- List each feature/task from the prompt
- For each, confirm: ✅ Implemented, ⚠️ Partial, ❌ Not done
- If any are not ✅, explain what's missing

## 2. VISUAL INSPECTION WITH PLAYWRIGHT

First, ensure the local dev server is running: `cd dashboard && npm run dev`

Use the Playwright MCP server to visually verify the implementation on localhost:

1. Navigate to http://localhost:3000/login
2. Take a screenshot of the login page
3. Navigate to each page that was modified/created in this implementation
4. Take screenshots of each page
5. Report any visual issues, broken layouts, or missing elements

Note: We test locally because changes aren't on production until after we push.

If Playwright can't launch (browser already running), verify the build passes and manually describe what was implemented.

## 3. GIT STATUS & DIFF REVIEW

Run `git status` and `git diff --stat` to show:
- All files that were modified
- All files that were created
- Confirm no sensitive files (.env, credentials) are staged

## 4. DOCUMENTATION UPDATES

Based on what was implemented, determine if updates are needed to:

### CLAUDE.md (project memory for AI agents)
Add/update if:
- New pages or routes were added
- New API endpoints were created
- New environment variables are required
- New database tables were created
- Important architectural decisions were made

### README.md (human documentation)
Add/update if:
- Setup instructions changed
- New commands are available
- New features need user documentation

### AGENTS.md (content generation guidelines)
Add/update if:
- New content policies were implemented
- Platform-specific rules changed
- Scoring or validation rules changed

Propose the specific additions/changes needed for each file.

## 5. COMMIT & PUSH

Once I approve the verification results and documentation updates:

1. Stage all relevant files (excluding any sensitive data)
2. Create a descriptive commit message summarizing what was implemented
3. Push to origin master
4. Report the commit hash and confirm push succeeded

## 6. FINAL SUMMARY

Provide a summary including:
- What was implemented
- What documentation was updated
- Any known limitations or follow-up tasks
- Next recommended action

---

Please proceed with steps 1-4 now. Wait for my approval before step 5.
```

---

## Post-Completion: Update Memory Files

After pushing changes, if significant updates were made, you may want to run this to ensure documentation is comprehensive:

```
Review the current state of CLAUDE.md, README.md, and AGENTS.md. Based on the recent changes pushed to the repository, ensure these files accurately reflect:

1. CLAUDE.md:
   - All implemented dashboard pages and their routes
   - All API endpoints and their purposes
   - Current database schema (tables we rely on)
   - Environment variables required
   - Key file locations

2. README.md:
   - Accurate setup instructions
   - All available CLI commands
   - Feature descriptions that match current implementation

3. AGENTS.md:
   - Any new content policies
   - Updated platform guidelines
   - Current scoring rubrics

Make minimal, focused updates. Don't rewrite sections that are already accurate. Show me the proposed changes before committing.
```

---

## Quick Start: Prompt 21 (Unify Content Generation Methodology)

**When to run:** After Prompt 09 (Cloud Run) - CRITICAL for consistency

**Prerequisites:** Cloud Run deployed (if choosing Option B - Python as source of truth)

**Copy and paste into a new Claude Code chat:**

```
I need to unify the TypeScript and Python content generation methodologies to ensure consistency. Please enter plan mode and use the prompt at docs/prompts/21-unify-content-generation-methodology.md as your guide.

Key context:
- Repository: /Users/bobby/Documents/GitHub/Allied-FeedOps
- TypeScript regeneration: dashboard/src/app/api/regenerate/route.ts
- Python prompts: src/feedops/pipeline/prompts.py
- Recent TypeScript enhancements: variant_finish_sentences, evidence table builder

The Problem:
TypeScript (dashboard) and Python (batch) use DIFFERENT prompts and methodologies. This causes inconsistency between:
- Real-time dashboard regeneration
- Batch generation for publishing

Goals:
1. Document BOTH methodologies in detail (prompts, data, output format)
2. Create side-by-side comparison matrix
3. Identify strengths of each approach
4. Decide on architecture (TypeScript as truth, Python as truth, or hybrid)
5. Implement unified methodology
6. Verify consistency (same SKU → same output regardless of system)

Recent TypeScript enhancements to preserve:
- finish_sentences table for variant-specific content
- Evidence table builder with product_catalog data
- Vision support for product images

Python strengths to consider:
- Comprehensive 302-line SYSTEM_PROMPT with P0/P1/P2 priorities
- Structured JSON output with claims tracing
- Self-scoring (6 dimensions)
- Category-specific guidance
- Explicit examples and anti-patterns

**REQUIRED WORKFLOW (superpowers skills):**

1. BEFORE any implementation decisions: `/superpowers:brainstorming` - explore requirements and design
2. BEFORE writing any code: `/superpowers:writing-plans` - create step-by-step implementation plan
3. FOR each feature/bugfix: `/superpowers:test-driven-development` - write tests first
4. FOR independent tasks: `/superpowers:dispatching-parallel-agents` - run 2+ tasks in parallel
5. FOR any bugs found: `/superpowers:systematic-debugging` - investigate before fixing
6. BEFORE claiming done: `/superpowers:verification-before-completion` - run verification commands, show evidence

Use `TaskCreate` to build a task list from the plan. Use `TaskUpdate` to mark tasks in_progress and completed.

Do NOT commit changes until the full implementation is verified with passing tests and builds.
```

---

## Quick Start: Prompt 22 (Performance Data Lifecycle)

**When to run:** After Search Insights sync is fixed - investigates and implements performance monitoring

**Prerequisites:**
- Google Ads credentials configured in Cloud Run (see CRITICAL PREREQUISITE section in prompt)
- Search Insights "Sync Data" button works without error

**Copy and paste into a new Claude Code chat:**

```
I need to investigate and implement the performance data lifecycle for FeedOps. Please enter plan mode and use the prompt at docs/prompts/22-performance-data-lifecycle.md as your guide.

Key context:
- Repository: /Users/bobby/Documents/GitHub/Allied-FeedOps
- Dashboard: /dashboard (Next.js 14+)
- Cloud Run service: https://feedops-pipeline-623866089882.us-east1.run.app
- Google Ads customer ID: 6253381786

CRITICAL PREREQUISITE - FIX SEARCH INSIGHTS SYNC FIRST:
The "Sync Data" button on Search Insights page fails with:
"[Errno 2] No such file or directory: '/root/google-ads.yaml'"

This is because Cloud Run is missing Google Ads credentials. The prompt contains full instructions to:
1. Create Google Ads secrets in GCP Secret Manager
2. Grant runtime service account access
3. Redeploy Cloud Run with updated --set-secrets

Do NOT proceed with performance investigation until Search Insights sync works.

MCP Tools to Use:
- **Supabase MCP** (`mcp__supabase__execute_sql`): Query tables directly
- **Vercel MCP** (`mcp__vercel__get_runtime_logs`): Debug API issues
- **Playwright MCP** (`mcp__plugin_playwright_playwright__*`): Visual verification
- **Google Ads MCP** (`mcp__google-ads-mcp__*`): Test API queries

Goals:
1. FIX Cloud Run Google Ads credentials (critical prerequisite)
2. Verify Search Insights sync works
3. Investigate performance data tables (performance_baselines, performance_snapshots)
4. Determine if baseline capture happens before publishing
5. Determine if snapshots are being scheduled
6. Design and implement complete performance monitoring lifecycle

**REQUIRED WORKFLOW (superpowers skills):**

1. BEFORE any implementation decisions: `/superpowers:brainstorming` - explore requirements and design
2. FOR the search insights sync issue: `/superpowers:systematic-debugging` - root cause already documented in prompt
3. BEFORE writing any code: `/superpowers:writing-plans` - create step-by-step implementation plan
4. FOR each feature/bugfix: `/superpowers:test-driven-development` - write tests first
5. FOR independent tasks: `/superpowers:dispatching-parallel-agents` - run 2+ tasks in parallel
6. BEFORE claiming done: `/superpowers:verification-before-completion` - run verification commands, show evidence

Use `TaskCreate` to build a task list from the plan. Use `TaskUpdate` to mark tasks in_progress and completed.

Do NOT commit changes until the full implementation is verified with passing tests and builds.
```

---

## Troubleshooting

### Playwright won't launch
Chrome is probably already running. Either:
- Close Chrome and retry
- Use WebFetch instead to verify pages load

### Build fails
Check the error message for:
- Missing dependencies → `npm install`
- TypeScript errors → Fix type issues
- Environment variables → Ensure they're set in Vercel

### Tests fail
- Read the failure message carefully
- Check if the test is testing removed functionality
- Use systematic-debugging skill to investigate

### Push rejected
- Pull latest: `git pull origin master --rebase`
- Resolve conflicts if any
- Push again
