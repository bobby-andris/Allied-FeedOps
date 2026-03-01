# Allied-FeedOps

## ⚠️ CRITICAL BEHAVIORAL RULES (READ FIRST)

### Anti-Pattern Detection (Check User Prompts)
**Before executing, check if user's request matches known failure patterns:**

1. **"Spawn agents to query [database]"** → Warn: MCP access issue. Offer: data-first OR ToolSearch
2. **"Just give quick answer"** (for analysis) → Warn: Fabrication risk. Offer: data-first approach
3. **"Fix and push"** / "deploy"** → Warn: No build verification. Enforce: build → lint → push workflow
4. **"Use Node.js/npm for script"** → Warn: Wrong stack. Remind: Python for scripts
5. **"Optimize N SKUs"** (no selection) → Ask: Which SKUs? Offer to query for criteria
6. **"Continue where we left off"** → Check: Checkpoint file exists? Or need context summary?

**Warning format:**
```
⚠️ Anti-Pattern: [Name]
Issue: [why it fails]
Recommend: [better approach]
Proceed with recommendation or override?
```

### Pre-Deploy Gates (MANDATORY)
Before ANY `git push` or deployment:
1. ✅ Run `cd dashboard && npm run build` - MUST pass
2. ✅ Run `npx tsc --noEmit` - MUST have zero errors
3. ✅ Run `npm run lint` - Fix all issues
4. ✅ If you removed imports during lint cleanup, `grep` for usage before committing
5. ❌ NEVER push code that hasn't passed local build verification

### Data Integrity (MANDATORY)
1. ❌ NEVER fabricate SKU IDs, product data, metrics, or examples
2. ✅ Query database FIRST, verify data is real, THEN analyze/plan
3. ✅ When presenting findings, clearly distinguish verified facts from assumptions
4. ✅ If data doesn't exist, say so explicitly and ask permission to proceed with assumptions

### Multi-Agent MCP Tool Usage
Sub-agents CAN access MCP tools when properly configured:

**Pattern that works:**
```
Task prompt: "You have access to MCP tools. FIRST use ToolSearch to load the tools you need: [list mcp__ tools]. THEN execute your task: [description]."

Use subagent_type: general-purpose (has access to all tools)
```

**For complex MCP workflows:**
1. Option A: Run all MCP queries in main context, save results to `/tmp/`, pass file paths to agents
2. Option B: Spawn agents with explicit ToolSearch instructions (see pattern above)

### Database Schema
✅ ALWAYS check `docs/database/SCHEMA.md` BEFORE writing ANY Supabase query
- Prevents column name errors (e.g., `approval_status` not `status`)
- Prevents wrong table queries
- Documents all JSONB parsing patterns

### Stack & Language Rules
- ✅ Python for standalone scripts/pipelines (NOT Node.js unless specified)
- ✅ TypeScript for dashboard/API routes
- ✅ Use existing utilities before writing new code
- ❌ NEVER switch languages without explicit user approval

### Context Management (Self-Monitoring Required)
**Track message count as context usage proxy:**
- ~50 messages (50% usage): Issue awareness note, plan checkpoints if long session
- ~75 messages (60-65% usage): Recommend checkpoint soon
- ~100 messages (70% usage): **Create checkpoint now** (required)
- ~120+ messages (80%+ usage): **Auto-checkpoint + end session** (critical)

**High-burn sessions** (multi-agent, deep research, many file reads):
- Adjust thresholds DOWN by 20-30 messages
- Checkpoint earlier and more frequently

**Proactive behavior:**
- Issue context warnings at thresholds WITHOUT user prompting
- Offer `/checkpoint` at 60-70% usage
- At 80%: Force checkpoint and recommend ending session
- Write state to `.claude/checkpoints/[topic].md` BEFORE hitting limits

## Quick Reference

**Production**:
- Dashboard: https://allied-feed-ops.vercel.app/login
- Pipeline API: use the current canonical `FEEDOPS_PIPELINE_URL` value for this environment
- Supabase: `qezuszwufortkiutlhym`

**Defaults**:
- Google Ads customer ID: `6253381786`
- GA4 property: Allied Brass — GA4 (Old)

## MCP Servers & Skills

**Use these before writing custom code**:

**Browser Automation**:

Use `agent-browser` for web automation. Run `agent-browser --help` for all commands.

Core workflow:
1. `agent-browser open <url>` - Navigate to page
2. `agent-browser snapshot -i` - Get interactive elements with refs (@e1, @e2)
3. `agent-browser click @e1` / `fill @e2 "text"` - Interact using refs
4. Re-snapshot after page changes


**MCP Servers**:
- `mcp__supabase__*` - Database queries, migrations, schema (`execute_sql` for quick queries)
- `mcp__google-ads-mcp__*` - Ads data, Keyword Planner
- `mcp__merchant-api-devdocs__*` - GMC product data, performance
- `mcp__Apify__*` - Web scraping, competitor analysis
- `mcp__vercel__*` - Deployment logs, management
- `mcp__gcloud__*` / `mcp__cloud-run__*` - GCP operations

**MCP Servers (cont.)**:
- `mcp__openaiDeveloperDocs__*` - OpenAI API docs, GPT-5.2 best practices, structured outputs, prompt caching

**Agents** (via Task tool):
- `merchant-integrator` - Merchant API migrations and integrations

**Skills** (via Skill tool):
- `superpowers:brainstorming` - Before creative work
- `superpowers:systematic-debugging` - When encountering bugs
- `superpowers:test-driven-development` - Before implementation
- `marketing-skills:*` - Copy, SEO, marketing content
- `allied-brass-brand-expert` - Brand voice guidance for content generation
- `quality-evaluation` - Content quality rubric evaluation
- `finish-expertise` - Finish-specific content guidance (28 finishes)
- `product-storytelling` - Interior-design-grade product descriptions
- `collection-storytelling` - Collection DNA for 41 named collections
- `google-shopping-content` - Google Shopping title/description optimization

### GPT-5.2 Known Issues (to fix in v1.3a)

See full research: `docs/research/gpt52-best-practices.md`

1. **BUG**: `temperature=0.7` always passed alongside `reasoning_effort` — mutually exclusive on GPT-5.2 (`openai_provider.py:168-185`)
2. **BUG**: `reasoning_effort` from env var `FEEDOPS_REASONING_EFFORT` — if unset, no reasoning sent (GPT-5.2 defaults to zero reasoning)
3. Using legacy `json_object` instead of `json_schema` strict mode — wastes tokens on retry loops
4. No `prompt_cache_retention: "24h"` — cache expires in 5-10 min during batch runs
5. Gold standard examples in user prompt break cacheable prefix
6. System prompt uses `=== ===` headers instead of XML tags (GPT-5.2 parses XML better)
7. Vague length targets ("target 600-800") instead of hard constraints

## Current Roadmap (v1.3)

**Master plan**: `docs/plans/2026-02-21-strategic-milestone-assessment.md` (10-part document)
**GSD context**: `.planning/PROJECT.md`

- **v1.3a**: Content Generation Excellence — fix prompts, wire skills, fix GPT-5.2 bugs
- **v1.3b**: Architecture Validation & Data Persistence — deferred migrations, feedback tables
- **v1.3c**: Actionable Shopping Intelligence — distribution-based scoring, revenue leakage
- **v1.4**: Closed-Loop Optimization — performance-informed regeneration

## What's Implemented (v1.2 Complete)

**Dashboard pages**: Overview, SKU review (3 variants), variant review, performance baselines/snapshots, batches/publishing, competitor intelligence, search insights, evidence table, settings, regeneration, SKU selection, post-publish monitoring
**Pipeline**: Single-SKU generation, batch generation, hybrid multi-SKU generation, lifestyle image generation, search term sync, performance capture
**Publishing**: Google Sheets (structured fields), Shopify (product-level + CDN lifecycle), variant expansion (28 finishes)
**Data collection**: Auto-triggered baselines, search terms, keyword planner (via `ensure-data.ts`)

## Content Generation

**Default: Cloud Run Pipeline (GPT-5.2)**
- Location: `src/feedops/api/main.py` (FastAPI)
- **Model**: GPT-5.2 (`gpt-5.2` in `openai_provider.py`) — reasoning_effort from env `FEEDOPS_REASONING_EFFORT` (unset = no reasoning)
- **Dashboard regeneration proxies to this pipeline** — `route.ts` is a thin proxy, NOT a separate codepath
- **Prompt authority chain**: `src/feedops/api/prompt_builder.py` (orchestrator) → `prompts.py` (SYSTEM_PROMPT) + `prompt_loader.py` (DB data) + `shopping_intelligence.py` (loads `config/shopping_intelligence.yaml`)
- TypeScript prompt logic is legacy/reference during migration and must not be treated as runtime source-of-truth
- Finish sentence generation is being consolidated into Python; avoid adding new TS-side prompt behavior
- Quality: ~75-80/100 (pre-v1.3a; target 85-92 after skill wiring)
- Speed: ~3 minutes per SKU
- Use for: Bulk generation (50+ SKUs)

**Experimental: 6-Agent Pipeline**
- Status: Manual execution only (not in UI)
- Quality: 87.2/100 avg (range: 82-98)
- Speed: ~6 minutes per SKU (2x slower)
- Use for: High-value SKUs, gold standard examples

**Hybrid Multi-SKU Generation** (NEW)
- Auto-detects product families (e.g., DMF-2/2X, 2/3X, 2/4X, 2/5X)
- Base SKU: Full generation
- Variants: Adaptation (60% cost savings)
- See: `docs/architecture/content-generation-hybrid.md`

## Dual-Use Skill Architecture

Skills serve two layers — Claude Code guidance AND GPT-5.2 runtime injection:

| Skill | Claude Code Skill | Runtime Config | Wired into pipeline |
|-------|:-:|:-:|:-:|
| Shopping Intelligence | `.claude/skills/google-shopping-content` | `config/shopping_intelligence.yaml` | Yes (via `shopping_intelligence.py`) |
| Brand Voice | `.claude/skills/allied-brass-brand-expert` | `config/brand_voice.yaml` | Skill + config ready, wiring pending (v1.3a Phase 24) |
| Quality Rubric | `.claude/skills/quality-evaluation` | `config/quality_rubric.yaml` | Skill + config ready, wiring pending (v1.3a Phase 23) |
| Finish Expertise | `.claude/skills/finish-expertise` | `config/finish_guide.yaml` | Skill + config ready, wiring pending (v1.3a Phase 24) |
| Product Storytelling | `.claude/skills/product-storytelling` | `config/storytelling_patterns.yaml` | Skill + config ready, wiring pending (v1.3a Phase 24) |
| Collection Stories | `.claude/skills/collection-storytelling` | `config/collection_stories.yaml` | Skill + config ready, wiring pending (v1.3a Phase 24) |
| Platform: Bing | `.claude/skills/bing-shopping-content` | `config/platform_bing.yaml` | Skill + config ready, wiring pending (v1.3a Phase 24) |
| Platform: Shopify | `.claude/skills/shopify-conversion-content` | `config/platform_shopify.yaml` | Skill + config ready, wiring pending (v1.3a Phase 24) |

**Key files**: `src/feedops/api/prompt_builder.py` (orchestrator), `src/feedops/pipeline/shopping_intelligence.py` (loads YAML), `src/feedops/config/` (YAML configs)

## Key Database Tables

**Content & Approvals**:
- `sku_approvals` / `variant_approvals` - Approval status
- `generated_content` - Title/description (baseline_content, candidate_content, **approved_content**)
- `generated_images` - Lifestyle images (Shopify CDN lifecycle)
- `variant_finish_sentences` - Finish-specific content for variants
- `prompt_templates` - Gold examples/guidance data (`gold_standard_examples`, `category_guidance`, `platform_rules`); do not use DB `system_prompt` as runtime authority

**Publishing**:
- `publish_batches` / `batch_sku_assignments` - Batch management
- `publish_events` - Audit log with content snapshots for rollback

**Performance**:
- `performance_baselines` - 30-day pre-publish metrics (avg impressions/clicks/CTR/CVR)
- `performance_snapshots` - Post-publish tracking with days_since_publish
- **Snapshot endpoint**: `/api/performance/capture-snapshot` (already exists)
  - Usage: `POST /api/performance/capture-snapshot?master_sku=920D-6&platform=google`
  - Calculates `days_since_publish` from `publish_events.published_at`
  - Regular collection: Set up GCP Cloud Scheduler or call from Cloud Run pipeline

**Data Pipeline**:
- `variant_index` - Maps master_sku ↔ gmc_offer_id (THE SOURCE OF TRUTH)
- `product_catalog` - All variants with full product data

**Lifestyle Images**:
- `product_lifestyle_images` - Product-level (no finish columns, requires shopify_product_id)
- `variant_lifestyle_images` - Variant-level (has finish/finish_code, gmc_offer_id)
- **Dedup**: Same image exists in both tables; page.tsx deduplicates by image_url (prefer variant records)
- **Generation**: Cloud Run `/generate-images` → Supabase Storage → both DB tables

**Search**:
- `search_queries` - Variant-level Google Ads search terms
- `keyword_metrics` - Keyword Planner data (cached, 30-day TTL)

**CRITICAL**: ALWAYS check `docs/database/SCHEMA.md` BEFORE writing ANY Supabase query — prevents column name errors.

**Conventions**:
- Column naming: `approval_status` (not `status`), `notes` (not `revision_notes`), `approved_by/approved_at`
- JSONB: Store as text strings, parse with `(column#>>'{}')::jsonb` before array operations
- LATERAL joins: `CROSS JOIN LATERAL jsonb_array_elements_text((item_ids#>>'{}')::jsonb)` to expand arrays
- Case-sensitive: Use `LOWER()` on both sides or `regexp_replace()` for joins

## Critical Patterns

### Multi-SKU Products ⚠️

**Multiple master_skus can share same product_id**. Example:
- DMF-2/2X, DMF-2/3X, DMF-2/4X, DMF-2/5X all share `4539975336068`

**Impact**:
- Google Ads aggregates at product_id level (not master_sku)
- Query logic must account for this (product_id-based matching)
- Content generation needs variant adaptation (not find/replace)

See: `docs/architecture/multi-sku-pattern.md`

### Offer ID Format

**GMC Format**: `shopify_US_{product_id}_{variant_id}` (uppercase "US")
**Database Format**: `shopify_us_{product_id}_{variant_id}` (lowercase "us")

**CRITICAL**: Database has lowercase, but GMC requires uppercase. Publishing code MUST transform.

**Implementation**:
- **Write to sheet**: Transform to uppercase via `.replace('shopify_us_', 'shopify_US_')`
- **Lookup existing rows**: Use lowercase for case-insensitive matching (sheet may have mixed case)
- **Affected file**: `dashboard/src/lib/publishing/google-sheets.ts` (line 757)

**Impact**: Incorrect format breaks GMC sync - rows append as duplicates instead of updating existing rows.

### SKU Format Handling

**Database**: Slash separators (`WP-2/16-GAL`, `DMF-2/2X`)
**URLs**: Hyphens only (`/review/DMF-2-2X`)
**Conversion**: Use `getSkuCandidates` in `dashboard/src/lib/sku-utils.ts`

### GMC Policy Guardrails

**Critical**: Never invent specs/claims not in product data
**AI content**: Use `structured_title`/`structured_description` with `digital_source_type=trained_algorithmic_media`
**Structured-only mode**: When `FEEDOPS_GMC_STRUCTURED_ONLY=1`, omit standard title/description

### Deferred Migrations (DO NOT APPLY)

Two migration files exist but are NOT applied to production Supabase:
- `034b` — GA4 attribution (4 tables)
- `035b` — Intent execution (14 tables)

**32 TypeScript files** reference 035b tables that don't exist. These pages show zero results (not bugs — tables don't exist).
**DO NOT** apply these migrations without explicit user approval. They will be evaluated in v1.3b.

### Component Patterns (Dashboard)

**ESLint**: Underscore prefix (`_unused`) does NOT suppress `no-unused-vars` — use `// eslint-disable-next-line` or remove the variable
**Card rendering**: Components like SearchInsightsCard render Card internally - don't wrap in additional Card
**Grid layouts**: Use `grid-cols-1 lg:grid-cols-2` for 50/50 split (mobile stacks, desktop side-by-side)
**Multiple variants**: SkuReviewClient has 3 variants (main, magazine, original) - update all when changing props
**Import cleanup**: Each SkuReviewClient variant uses DIFFERENT subsets of imports — always `grep` for usage before removing
**localStorage SSR**: Use `useState(() => { if (typeof window === 'undefined') return default; ... })` lazy initializer, NOT useEffect+setState
**Platform tabs**: SkuReviewClient persists selected platform in URL search params (`?platform=bing`) — sticky positioned at `top-[57px]`
**Nested components**: PlatformContent sub-component needs data threaded through parent component
**TypeScript**: `ContentRecord` interface duplicated in page.tsx and SkuReviewClient.tsx - must match exactly
**Performance types**: `PerformanceBaseline`/`PerformanceSnapshot` duplicated across files - include ALL nullable fields
**Optional chaining**: Use `?.property ?? null` when component expects `string | null`

## Key Locations

**Dashboard**:
- Pages: `dashboard/src/app/(dashboard)/**`
- API routes: `dashboard/src/app/api/**`
- Regeneration route: `dashboard/src/app/api/regenerate/route.ts` (thin proxy to Cloud Run `/regenerate`)
- Regeneration core (legacy, used by batch): `dashboard/src/lib/regeneration/core.ts`
- Legacy prompt reference: `dashboard/src/lib/regeneration/prompts.ts` (not runtime source-of-truth)
- Evidence builder: `dashboard/src/lib/evidence/*`
- Multi-SKU detection: `dashboard/src/lib/multi-sku-detection.ts`
- Hybrid generation: `dashboard/src/app/api/sku-selection/generate-hybrid/route.ts`

**Python Pipeline**:
- Cloud Run API: `src/feedops/api/main.py`
- Prompt builder (orchestrator): `src/feedops/api/prompt_builder.py`
- System prompt: `src/feedops/pipeline/prompts.py`
- DB data loader: `src/feedops/api/prompt_loader.py`
- OpenAI provider: `src/feedops/providers/openai_provider.py`
- Optimization pipeline: `src/feedops/pipeline/optimize.py`
- Runtime configs: `src/feedops/config/*.yaml`
- Google Ads: `src/feedops/integrations/google_ads_performance.py`
- Search terms: `src/feedops/integrations/google_ads_search_terms.py`

**Publishing**:
- Google Sheets: `dashboard/src/lib/publishing/google-sheets.ts`
- Shopify: `dashboard/src/lib/publishing/shopify.ts`
- Variant expansion: `dashboard/src/lib/publishing/expand-variants.ts`

## Deployment (Auto-Deploy on Push to Master)

**Vercel IDs** (for MCP tools):
- Project: `prj_00zlLdZVgbP8XjDWIEXSRdFyqDqA`
- Team: `team_KsEZDE8Pw0bKQDGlieBVBQVs`

**Two pipelines auto-deploy**:
1. **Cloud Run** (Python): Push → Cloud Build trigger → Deploy
2. **Vercel** (Dashboard): Push → Vercel auto-deploy

**Check build status**:
```bash
gcloud builds list --project=bobbys-project-346400 --limit=5
```

**Service accounts**:
- Build: `profit-pilot-build@bobbys-project-346400.iam.gserviceaccount.com`
- Runtime: `profit-pilot-runtime@bobbys-project-346400.iam.gserviceaccount.com`

**GCP secrets** (all 9 already exist, bound to runtime SA):
- feedops-openai-api-key
- feedops-supabase-url / feedops-supabase-key
- feedops-google-ads-developer-token / client-id / client-secret / refresh-token / login-customer-id
- feedops-gemini-api-key

## Cloud Run Service

**Endpoints**:
- `GET /health` - Health check with Supabase status
- `POST /optimize-sku` - Single SKU content generation
- `POST /regenerate` - Content regeneration with feedback
- `POST /batch-optimize` - Batch job creation
- `GET /batch-status/{job_id}` - Batch job progress
- `POST /performance/capture-baseline` - Capture performance baselines
- `POST /search-insights/sync` - Sync search terms from Google Ads
- `POST /hybrid-generate` - Hybrid multi-SKU generation (base + variants)
- `POST /generate-images` - Lifestyle image generation (Gemini Imagen, ~3 min, smart finish selection)

**CRITICAL: Cloud Run Background Task Pattern**

FastAPI `BackgroundTasks` are killed when containers scale to zero or during deployments.

**Solution**: Use `run_async_in_thread()` helper in `src/feedops/api/main.py`
- Pattern: Non-daemon threads with dedicated asyncio event loops that survive HTTP response
- Used by: `/hybrid-generate`, `/search-insights/sync`, `/batch-optimize`, `/generate-images`
- **CORS**: `main.py` has CORSMiddleware allowing `allied-feed-ops.vercel.app` and `localhost:3000`
- **Limitation**: Jobs still terminate during deployments (expected behavior)
- See: `docs/audit/background-task-fix-2026-02-08.md` for full analysis

**Pattern**:
```python
# Replace this (killed by container lifecycle)
background_tasks.add_task(process_job, job_id=job_id)

# With this (survives until completion or deployment)
run_async_in_thread(process_job, job_id=job_id)
```

## Local Development

### Dashboard

```bash
cd dashboard
npm install
npm run dev  # http://localhost:3000
npm run build  # Verify TypeScript before deploy
npm run lint
```

**Environment** (`.env.local`):
```
NEXT_PUBLIC_SUPABASE_URL=
NEXT_PUBLIC_SUPABASE_ANON_KEY=
SUPABASE_SERVICE_ROLE_KEY=
SHOPIFY_STORE_URL=
SHOPIFY_ACCESS_TOKEN=
```

**Local testing**: Copy ALL credentials from `.env.vercel` to `dashboard/.env.local` for accurate testing
**Dev server cleanup**: If port 3000 conflicts, use `pkill -f "next dev"` and remove `.next/cache/fetch-cache/lock`

### Python Pipeline

```bash
uv venv
uv pip install -e ".[dev]"
PYTHONPATH=./src .venv/bin/python -m pytest tests/ -v
```

## Common Workflows

### Test Before Commit

```bash
cd dashboard && npm run build && npm run lint
```

### Capture Performance Snapshots

```bash
# Via dashboard API (requires auth)
curl -X POST https://allied-feed-ops.vercel.app/api/performance/capture-snapshot

# For specific SKU
curl -X POST "https://allied-feed-ops.vercel.app/api/performance/capture-snapshot?master_sku=920D-6"

# For specific platform
curl -X POST "https://allied-feed-ops.vercel.app/api/performance/capture-snapshot?platform=google"
```

**Automation**: Set up GCP Cloud Scheduler to call endpoint daily/weekly for trend tracking

### Run Python Maintenance Scripts

```bash
cd /path/to/Allied-FeedOps
source .venv/bin/activate
set -a && source .env.vercel && set +a
python scripts/script_name.py
```

### Check Deployment

```bash
# Vercel logs
# Use Vercel MCP or dashboard

# Cloud Run logs
gcloud run services logs read feedops-pipeline --project=bobbys-project-346400 --limit=50
```

### Database Queries

```typescript
// Use Supabase MCP for quick queries
mcp__supabase__execute_sql

// Check schema
SELECT column_name, data_type
FROM information_schema.columns
WHERE table_name = 'performance_baselines';
```

## Data Pipeline

**Flow**: Acatalog.csv → variant_index → Google Sheets → GMC → Google Ads

**Key facts**:
- GMC does NOT auto-sync from Shopify (custom feed via Google Sheets)
- variant_index is source of truth for SKU↔offer ID mapping
- 99.7% of "missing data" issues are query logic problems (not data sync)

See: `docs/architecture/data-pipeline.md`

## Publishing Workflow

1. **Generate**: Regeneration API → `candidate_content`
2. **Approve**: User approval → `approved_content` (immutable)
3. **Publish**: Batch publish reads `approved_content`
4. **Expand**: Google/Bing get {FINISH_NAME} → 28 variants
5. **Update**: Google Sheets rows updated by gmc_offer_id
6. **Audit**: `publish_events` stores snapshots for rollback

**Shopify**:
- Product-level content only (no variant-specific titles/descriptions)
- Lifestyle images: variant-specific via `productVariantAppendMedia`
- CDN lifecycle: Supabase Storage → Shopify CDN → Google Sheets

**Shopify Media Upload**:
- ALWAYS use `uploadProductImage()` for lifestyle images (not `uploadVariantImage()` — fails with "variant already has media")
- `findExistingMedia()` checks alt text to prevent duplicates; images must reach READY status before CDN URL is available

## Google Sheets Feed Structure

**Production Sheet ID**: `1qMjCn1ZPlDd0R3TkTI0kDnX6tnApIHrnfAOWfJj_QEg`
**Sheet Name**: `SupplementalFeedData`

**Column Layout** (as of 2026-02-08):
- A: `id` (GMC offer ID - MUST be uppercase `shopify_US_`)
- B: `mpn` (Manufacturer Part Number: `{master_sku}-{finish_code}`)
- C: `product_type`
- D: `pattern`
- E: `custom_label_0`
- F: `custom_label_1`
- G: `custom_label_2`
- H: `title`
- I: `google_product_category`
- J: `description`
- K: `custom_label_4`
- L: `lifestyle_image_link` (added 2026-02-08)
- M: `structured_title` (added 2026-02-08)
- N: `structured_description` (added 2026-02-08)

**MPN Requirements**:
- **New rows**: Populate MPN as `{master_sku}-{finish_code}` (e.g., `FT-16-ABR`)
- **Existing rows**: Preserve current MPN value (don't overwrite)
- **Implementation**: Check if row exists before setting MPN field

## Automated Data Collection

SKU selection, regeneration, and batch generation APIs **automatically** trigger data collection:
- **Performance baselines**: 30-day pre-optimization metrics (if missing/stale >60 days)
- **Search query data**: Google Ads search terms + Keyword Planner (if stale >7 days)
- **Non-blocking**: Operations continue even if collection fails
- **Evidence-driven**: Auto-feeds into evidence table for content generation

Functions: `ensureSkuData()`, `ensureAllData()` in `dashboard/src/lib/data-collection/ensure-data.ts`

## Content Storage

**IMPORTANT**: Generated content stored in **Supabase only** (not git). Use regeneration API to create new content.

## Git Conventions

```bash
# Format: type: description
git commit -m "fix: resolve baseline capture query logic

Co-Authored-By: Claude Opus 4.6 <noreply@anthropic.com>"

# Push triggers auto-deploy
git push origin master
```

## Troubleshooting

**Baseline capture issues**: See `docs/troubleshooting/baseline-capture.md`
- Most common: offer ID case mismatch (uppercase vs lowercase)
- Second: missing campaign type in query
- Third: multi-SKU product query logic

**Dashboard issues**:
- Vercel logs via MCP or dashboard
- Browser console for client errors
- Test: `/api/health`

**Pipeline issues**:
- Cloud Run logs: `gcloud run services logs read feedops-pipeline --project=bobbys-project-346400 --limit=50`
- Test: `curl "$FEEDOPS_PIPELINE_URL/health"`

**Shopify media issues**:
- Duplicate lifestyle images: Check Shopify product media via GraphQL (see `scripts/cleanup_duplicate_media.py`)
- CDN migration failing: Verify `migrateImagesForPublish()` not using `uploadVariantImage()`
- Storefront not updating: Hard refresh (cmd+shift+r) to bypass CDN cache
- Use /systematic-debugging skill for media upload errors instead of guessing fixes

**Batch publishing issues**:
- **Stuck "executing" status**: Final batch status UPDATE fails silently (possible timeout or missing error handling)
- **Workaround**: Manually update via Supabase: `UPDATE publish_batches SET status = 'published', success_count = N WHERE batch_id = 'batch-id'`
- **Root cause**: Status update happens after long-running Google Sheets/Shopify operations, may exceed serverless function timeout

## Documentation

**Key docs** (use Glob for others in `docs/`):
- `docs/plans/2026-02-21-strategic-milestone-assessment.md` - Master v1.3 plan (10 parts)
- `.planning/PROJECT.md` - GSD context (read by all GSD agents)
- `docs/database/SCHEMA.md` - Complete DB schema reference
- `docs/research/gpt52-best-practices.md` - GPT-5.2 optimization findings
