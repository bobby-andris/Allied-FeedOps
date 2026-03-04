# Allied-FeedOps

## Behavioral Rules

### Anti-Pattern Detection
Before executing, check if user's request matches known failure patterns:

1. **"Spawn agents to query [database]"** → Warn: MCP access issue. Offer: data-first OR ToolSearch
2. **"Just give quick answer"** (for analysis) → Warn: Fabrication risk. Offer: data-first approach
3. **"Fix and push"** / "deploy" / "push this"** → **INVOKE `deploy-checklist` skill.** No exceptions.
4. **"Use Node.js/npm for script"** → Warn: Wrong stack. Python for scripts.
5. **"Optimize N SKUs"** (no selection) → Ask: Which SKUs?
6. **"Continue where we left off"** → Check for checkpoint file
7. **"Change env var" / "update Cloud Run"** → **INVOKE `deploy-checklist` skill Phase 3.**

### Core Rules
- ❌ NEVER fabricate SKU IDs, product data, metrics, or examples — query DB first
- ❌ NEVER push without `deploy-checklist` skill — it validates build, infra, and env parity
- ✅ ALWAYS check `docs/database/SCHEMA.md` BEFORE writing ANY Supabase query
- ✅ Python for scripts/pipelines, TypeScript for dashboard only
- ✅ Feature branches → squash-merge PRs (see `CONTRIBUTING.md` for full workflow)
- ✅ Sub-agents accessing MCP: use `subagent_type: general-purpose` with explicit ToolSearch instructions

### Context Management
- ~50 messages: awareness note
- ~75 messages: recommend checkpoint
- ~100 messages: **create checkpoint** (required)
- High-burn sessions: adjust thresholds down 20-30 messages

## Quick Reference

- **Dashboard**: https://allied-feed-ops.vercel.app/login
- **Supabase project**: `qezuszwufortkiutlhym`
- **Google Ads customer ID**: `6253381786`
- **Vercel project**: `prj_00zlLdZVgbP8XjDWIEXSRdFyqDqA` / team: `team_KsEZDE8Pw0bKQDGlieBVBQVs`
- **GCP project**: `bobbys-project-346400`
- **Google Sheet**: `1qMjCn1ZPlDd0R3TkTI0kDnX6tnApIHrnfAOWfJj_QEg` (sheet: `SupplementalFeedData`)

## MCP Servers & Skills

**MCP Servers**: `mcp__supabase__*`, `mcp__google-ads-mcp__*`, `mcp__merchant-api-devdocs__*`, `mcp__Apify__*`, `mcp__vercel__*`, `mcp__gcloud__*` / `mcp__cloud-run__*`, `mcp__openaiDeveloperDocs__*`

**Key Skills**: `deploy-checklist` (mandatory pre-push), `allied-brass-brand-expert`, `quality-evaluation`, `finish-expertise`, `product-storytelling`, `collection-storytelling`, `google-shopping-content`, `bing-shopping-content`, `shopify-conversion-content`

## Roadmap

- **v1.0**: Pipeline Reliability Rewrite — COMPLETE
- **v1.1**: Dead Code Cleanup + Data Infrastructure — COMPLETE
- **Next**: TBD — run `/gsd:new-milestone`
- **Master plan**: `docs/plans/2026-02-21-strategic-milestone-assessment.md`
- **GSD roadmap**: `.planning/ROADMAP.md`

## Architecture

### Content Generation Pipeline
- **Cloud Run API**: `src/feedops/api/main.py` (FastAPI)
- **Provider**: Claude Sonnet 4.6 (`FEEDOPS_PROVIDER=claude`)
- **Prompt chain**: `prompt_builder.py` → `prompts.py` (SYSTEM_PROMPT) + `prompt_loader.py` (DB data) + `shopping_intelligence.py` (YAML config)
- **Dashboard regeneration**: `/api/regenerate/route.ts` is a thin proxy to Cloud Run — NOT a separate codepath
- **TypeScript prompts are legacy reference** — Python pipeline is the runtime authority
- **Background tasks**: Use `run_async_in_thread()` (not FastAPI BackgroundTasks — killed on scale-to-zero)

### Dual-Use Skill Architecture
Skills serve Claude Code guidance AND runtime injection via YAML configs in `src/feedops/config/`:
- `shopping_intelligence.yaml` — wired (via `shopping_intelligence.py`)
- `brand_voice.yaml`, `quality_rubric.yaml`, `finish_guide.yaml`, `storytelling_patterns.yaml`, `collection_stories.yaml`, `platform_bing.yaml`, `platform_shopify.yaml` — configs ready, pipeline wiring pending

### Deployment (Auto-Deploy on Push to Master)
1. **Cloud Run** (Python): Push → Cloud Build → Deploy
2. **Vercel** (Dashboard): Push → Vercel auto-deploy

Check build: `gcloud builds list --project=bobbys-project-346400 --limit=5`

### Cloud Run Environment
| Env Var | Value | Purpose |
|---------|-------|---------|
| `FEEDOPS_PROVIDER` | `claude` | Active LLM provider |
| `FEEDOPS_GOOGLE_BRIEF_VERSION` | `v3` | Brief version |
| `FEEDOPS_CLAUDE_MODEL` | `claude-sonnet-4-6` | Model ID |
| `FEEDOPS_ENV_CONTRACT_STRICT` | `1` | Env contract enforcement |

Secrets bound to runtime SA: `feedops-openai-api-key`, `feedops-supabase-url/key`, `feedops-google-ads-*` (5), `feedops-gemini-api-key`, `feedops-anthropic-api-key`

### Endpoints
`/health`, `/optimize-sku`, `/regenerate`, `/batch-optimize`, `/batch-status/{job_id}`, `/performance/capture-baseline`, `/search-insights/sync`, `/hybrid-generate`, `/generate-images`

## Critical Patterns

### Offer ID Format
- **DB**: `shopify_us_` (lowercase) → **GMC**: `shopify_US_` (uppercase)
- Transform at publish time. Wrong format = duplicate rows in Google Sheets.

### Multi-SKU Products
Multiple master_skus share same product_id (e.g., DMF-2/2X through 2/5X). Google Ads aggregates at product_id level.

### SKU Format
DB uses slashes (`WP-2/16-GAL`), URLs use hyphens (`DMF-2-2X`). Convert via `getSkuCandidates` in `dashboard/src/lib/sku-utils.ts`.

### GMC Policy
Never invent specs. Use `structured_title`/`structured_description` with `digital_source_type=trained_algorithmic_media`.

### Deferred Migrations (DO NOT APPLY)
`034b` (GA4, 4 tables) and `035b` (intent execution, 14 tables) exist but are NOT in production. 32 TS files reference 035b tables — pages show zero results (expected). Do not apply without user approval.

### Database Conventions
- Column: `approval_status` (not `status`), `notes` (not `revision_notes`)
- JSONB: `(column#>>'{}')::jsonb` before array operations
- LATERAL: `CROSS JOIN LATERAL jsonb_array_elements_text((col#>>'{}')::jsonb)`
- Case: `LOWER()` on both sides for joins

## Key Locations

**Dashboard**: Pages in `dashboard/src/app/(dashboard)/**`, API routes in `dashboard/src/app/api/**`
**Pipeline**: `src/feedops/api/` (main, prompt_builder, prompt_loader), `src/feedops/pipeline/` (prompts, optimize), `src/feedops/providers/`, `src/feedops/integrations/`, `src/feedops/config/*.yaml`
**Publishing**: `dashboard/src/lib/publishing/` (google-sheets.ts, shopify.ts, expand-variants.ts)

## Key Database Tables

- `generated_content` — titles/descriptions (baseline → candidate → **approved_content**)
- `sku_approvals` / `variant_approvals` — approval status
- `variant_index` — source of truth for SKU↔offer ID mapping (72K rows)
- `product_catalog` — all variants with full product data
- `publish_batches` / `batch_sku_assignments` / `publish_events` — publishing + audit
- `performance_baselines` / `performance_snapshots` — pre/post-publish metrics
- `search_queries` / `keyword_metrics` — search intelligence
- `product_lifestyle_images` / `variant_lifestyle_images` — lifestyle images (dedup by image_url)
- `variant_finish_sentences` — finish-specific content
- `prompt_templates` — gold examples, category guidance (not runtime system prompt)

## Publishing Workflow

Generate → Approve (immutable `approved_content`) → Batch Publish → Expand variants ({FINISH_NAME} → 28 finishes) → Update Google Sheets by gmc_offer_id → Audit via `publish_events`

**Shopify**: Product-level content only. Lifestyle images via `uploadProductImage()` (not `uploadVariantImage()`).

**Google Sheets columns**: id (A), mpn (B), product_type (C), pattern (D), custom_label_0-2 (E-G), title (H), google_product_category (I), description (J), custom_label_4 (K), lifestyle_image_link (L), structured_title (M), structured_description (N)

## Data Pipeline

**Flow**: Acatalog.csv → variant_index → Google Sheets → GMC → Google Ads
- GMC does NOT auto-sync from Shopify (custom feed via Google Sheets)
- Auto-triggered data collection: baselines (if stale >60d), search terms (if stale >7d) via `ensure-data.ts`
- Content stored in Supabase only (not git)

## Local Development

**Dashboard**: `cd dashboard && npm install && npm run dev` (port 3000). Copy `.env.vercel` to `.env.local`.
**Pipeline**: `uv venv && uv pip install -e ".[dev]" && PYTHONPATH=./src pytest tests/ -v`
**Pre-commit**: `cd dashboard && npm run build && npm run lint`

## Troubleshooting

See `docs/troubleshooting/` for detailed guides. Key patterns:
- **Offer ID mismatches**: uppercase vs lowercase (most common)
- **Dashboard**: Vercel MCP logs, `/api/health`
- **Pipeline**: `gcloud run services logs read feedops-pipeline --project=bobbys-project-346400 --limit=50`
- **Batch publish stuck**: May need manual status update via Supabase (serverless timeout)
