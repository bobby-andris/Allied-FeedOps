# FeedOps Prompt Quick Start Guide

## Execution Order

### Phase 1: Core Dashboard Foundation
1. **Prompt 10** → Dashboard Implementation (07 & 08)

### Phase 2: Content Quality Improvements (Dashboard-Only, No Infrastructure Needed)
2. **Prompt 17** → Description Quality Analyzer
3. **Prompt 13** → Competitor Intelligence Panel
4. **Prompt 14** → Search Query Insights
5. **Prompt 18** → Keyword Gap Analysis

### Phase 3: Infrastructure for Heavy Processing
6. **Prompt 09** → GCP Cloud Run Setup

### Phase 4: Future-Proofing & ROI
7. **Prompt 15** → Agentic Commerce (UCP)
8. **Prompt 12** → A/B Testing Dashboard
9. **Prompt 16** → Multi-Variant Images

### Phase 5: Final Audit (ALWAYS LAST)
10. **Prompt 11** → Production Readiness Audit

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

Use the brainstorming skill before implementation decisions. Use parallel subagents where appropriate. Create a task list to track progress. Use the verification-before-completion skill before claiming any task is done.

Do NOT commit changes until the full implementation is complete and verified.
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

Use the brainstorming skill before implementation decisions. Use parallel subagents where appropriate. Create a task list to track progress. Use the verification-before-completion skill before claiming any task is done.

Do NOT commit changes until the full implementation is complete and verified.
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

Use the brainstorming skill before implementation decisions. Use parallel subagents where appropriate. Create a task list to track progress. Use the verification-before-completion skill before claiming any task is done.

Do NOT commit changes until the full implementation is complete and verified.
```

---

## Quick Start: Prompt 14 (Search Query Insights)

**When to run:** Priority 1 - Match actual search behavior

**Copy and paste into a new Claude Code chat:**

```
I need to implement the Search Query Insights dashboard for FeedOps. Please enter plan mode and use the prompt at docs/prompts/14-search-query-insights.md as your guide.

Key context:
- Repository: /Users/bobby/Documents/GitHub/Allied-FeedOps
- Dashboard: /dashboard (Next.js 14+)
- Google Ads customer ID: 6253381786
- Existing integration: src/feedops/integrations/google_ads_performance.py

Goals:
1. Apply database migration for search_queries tables
2. Create Python integration for search_term_view GAQL query
3. Create /search-insights page with query table
4. Build gap analysis component showing keyword coverage
5. Integrate search data into content generation prompts
6. Track query coverage improvement over time

The key GAQL query:
SELECT search_term_view.search_term, metrics.impressions, metrics.clicks, metrics.conversions
FROM search_term_view
WHERE segments.date DURING LAST_30_DAYS AND campaign.advertising_channel_type = 'SHOPPING'

Use the brainstorming skill before implementation decisions. Use parallel subagents where appropriate. Create a task list to track progress. Use the verification-before-completion skill before claiming any task is done.

Do NOT commit changes until the full implementation is complete and verified.
```

---

## Quick Start: Prompt 18 (Keyword Gap Analysis)

**When to run:** Priority 1 - Identify missing keywords and prioritize optimization

**Copy and paste into a new Claude Code chat:**

```
I need to implement the Keyword Gap Analysis dashboard for FeedOps. Please enter plan mode and use the prompt at docs/prompts/18-keyword-gap-analysis.md as your guide.

Key context:
- Repository: /Users/bobby/Documents/GitHub/Allied-FeedOps
- Dashboard: /dashboard (Next.js 14+)
- Depends on: Search Query Insights (Prompt 14)

Goals:
1. Apply database migration for keyword_gaps tables
2. Create gap scoring algorithm (impressions × coverage gap)
3. Create /keyword-gaps page with opportunity ranking
4. Build KeywordSuggestions component with recommended keywords
5. Track gap closure progress over time
6. Generate suggested title improvements

The scoring algorithm should:
- Compare our titles to actual search queries from Google Ads
- Identify SKUs where high-volume queries aren't in titles
- Prioritize optimization by opportunity size
- Provide specific keywords to add per SKU

Use the brainstorming skill before implementation decisions. Use parallel subagents where appropriate. Create a task list to track progress. Use the verification-before-completion skill before claiming any task is done.

Do NOT commit changes until the full implementation is complete and verified.
```

---

## Quick Start: Prompt 09 (GCP Cloud Run Setup)

**When to run:** After content quality prompts - sets up infrastructure for batch generation

**Copy and paste into a new Claude Code chat:**

```
I need to set up GCP Cloud Run for the FeedOps Python pipeline. Please enter plan mode and use the prompt at docs/prompts/09-gcp-cloud-run-setup.md as your guide.

Key context:
- Repository: /Users/bobby/Documents/GitHub/Allied-FeedOps
- Python pipeline: /src/feedops/
- Dashboard: /dashboard (needs to call Cloud Run)
- Supabase project: qezuszwufortkiutlhym

Goals:
1. Install and configure gcloud-mcp and cloud-run-mcp servers in Claude Code
2. Create Dockerfile for Python pipeline
3. Create FastAPI entry point (src/feedops/api/main.py)
4. Apply database migrations for generation_jobs tables
5. Document deployment commands (don't actually deploy without my approval)

Important:
- Do NOT store secrets in code - use environment variables or Secret Manager
- The FastAPI server should expose /health, /optimize-sku, /regenerate, /batch-optimize
- Test container locally with Docker before documenting Cloud Run deployment

Use the brainstorming skill before implementation decisions. Use parallel subagents where appropriate. Create a task list to track progress. Use the verification-before-completion skill before claiming any task is done.

Do NOT commit changes until the full implementation is complete and verified.
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

Use the brainstorming skill before implementation decisions. Use parallel subagents where appropriate. Create a task list to track progress. Use the verification-before-completion skill before claiming any task is done.

Do NOT commit changes until the full implementation is complete and verified.
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

Use the brainstorming skill before implementation decisions. Use parallel subagents where appropriate. Create a task list to track progress. Use the verification-before-completion skill before claiming any task is done.

Do NOT commit changes until the full implementation is complete and verified.
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

Use the brainstorming skill before implementation decisions. Use parallel subagents where appropriate. Create a task list to track progress. Use the verification-before-completion skill before claiming any task is done.

Do NOT commit changes until the full implementation is complete and verified.
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

Use the brainstorming skill before implementation decisions. Use parallel subagents where appropriate. Create a task list to track progress. Use the verification-before-completion skill before claiming any task is done. Use the systematic-debugging skill if issues are found.

Do NOT commit changes until I've reviewed the findings.
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
