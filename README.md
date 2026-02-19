# Allied FeedOps

Allied FeedOps is the internal tooling that generates, reviews, and publishes **platform-specific product title/description updates** for Allied Brass across:
- Google Merchant Center / Performance Max
- Microsoft (Bing) Merchant Center
- Shopify (storefront product content)

## Primary Interface

The **Next.js Dashboard** at `https://allied-feed-ops.vercel.app` is the primary interface for:
- Reviewing and approving content (`/review`, `/review/[sku]`)
- Generating new content (`/generate`)
- Managing batches (`/batches`)
- Competitor intelligence (`/competitors`)
- Performance tracking (`/performance`)

For dashboard setup and local development, see the [CLAUDE.md](./CLAUDE.md) file.

## Python Pipeline (Runtime Canonical)

The Python pipeline is the runtime source of truth for prompt logic, generation, validation, and scoring.
The dashboard is the primary operator UI and should proxy generation to Python endpoints.

This repo is built around a **Master SKU → many variants (finishes/options)** model. The “shippable unit” on shopping platforms is the **variant offerId/item_id**, so review and publishing are **variant-first** where possible.

## Dashboard Approval + Publish Readiness (2026-02-11)

The dashboard approval and publish model now uses deterministic, platform-specific readiness instead of a single global publish gate.

### What changed

- Approval UI now has one explicit platform approval action per tab (`Google`, `Bing`, `Shopify`).
- Variant approval controls are explicitly labeled as **variant scope** (`Google/Bing variant content`).
- Publish supports platform subsets independently (`google`, `bing`, `shopify`, or combinations) when those platforms are ready.
- Publish is fail-closed per requested platform with actionable blockers.

### Deterministic readiness model

Platform readiness is computed from stored state (no hidden UI state):

- Content approval:
  - `generated_content.approved_content` for platform `title` and `description`
- Variant content readiness (Google/Bing):
  - `variant_approvals` has all finishes approved for title+description
- Variant image readiness (Bing only):
  - `variant_lifestyle_images` has one approved + user-selected image per finish
- Shopify image readiness:
  - Optional (no blocking gate for publish readiness)

### Publish API behavior

`POST /api/publish/sku` no longer hard-blocks all publishing on `sku_approvals.approval_status='approved'`.
It now computes readiness and validates only the requested platform subset.

- Success: requested platforms that are ready can publish independently.
- Failure: returns `409` with:
  - `code: "publish_platform_not_ready"`
  - `step: "platform_readiness"`
  - `readiness_errors[]` containing `platform`, `code`, `reason`, `actionableMessage`

### Review visibility indicators

The review UI now surfaces platform progress at both list and detail levels using deterministic stored-state checks:

- Review Queue (`/review`) shows per-SKU, per-platform status badges:
  - `Published` (with date), `Ready`, or `Needs action`
- SKU detail (`/review/[sku]`) shows a platform summary panel with:
  - readiness state
  - blocker reason when blocked
  - latest production publish timestamp
  - latest published title/description snapshot

Progress state is derived from:

- `generated_content.approved_content`
- `variant_approvals`
- `variant_lifestyle_images`
- latest successful production `publish_events`

### Manual base content overrides (Google/Bing/Shopify)

When regenerate-with-feedback cannot produce the exact result you need, the review page supports manual base edits:

- `Edit Base Title` in the Title block (Google/Bing):
  - locked token: `{FINISH_NAME}`
  - applies template updates across all variants
  - blocks hardcoded finish names
  - clears `approved_content` for title so re-approval is required
- `Edit Base Description` in the Description block (Google/Bing):
  - locked token: `{FINISH_SENTENCE}` (legacy `[FINISH_SENTENCE]` is normalized on save)
  - applies template updates across all variants
  - blocks hardcoded finish names
  - clears `approved_content` for description so re-approval is required
- `Edit Title` in the Title block (Shopify):
  - freeform product-level title editor (no finish token UI)
  - blocks hardcoded finish names and `Allied Brass` in Shopify title content
  - clears `approved_content` for title so re-approval is required
- `Edit Description` in the Description block (Shopify):
  - freeform product-level description editor (no finish sentence token UI)
  - blocks hardcoded finish names and finish placeholders
  - clears `approved_content` for description so re-approval is required

### Approval API behavior

- `PATCH /api/approvals`
  - Supports optional `platform` to snapshot approved content per platform.
  - Platform-scoped approve requests still transition approved content even if global booleans were already true.
- `POST /api/variants/approvals/bulk`
  - Supports optional `platform` (currently `google | bing`) for clearer scope and messaging.
- `POST /api/review/manual-title`
  - Manual title override for Google/Bing variant templates and Shopify product-level title content.
- `POST /api/review/manual-description`
  - Manual description override for Google/Bing variant templates and Shopify product-level description content.

### Lifestyle image semantics

- Google: variant image approval/selection remains finish-level in review, but is **not required** for Google publish readiness.
- Bing: variant image approval/selection remains finish-level and is required for readiness.
- Shopify: master image selection is product-level and optional for publish readiness.
  - Selecting a Shopify master image can clone a previously approved+selected variant image into `product_lifestyle_images` when needed, without requiring a second hidden approval flow.
- Variant image fallback for publish selection is deterministic:
  - `user_selected` image first
  - fallback to `ai_selected` image (default Google Ads-driven generation path)
  - fallback to most recent generated image
- Lifestyle image generation is idempotent on rerun:
  - `product_lifestyle_images` writes now upsert on `(master_sku, variation_index)`
  - `variant_lifestyle_images` writes now upsert on `(gmc_offer_id, variation_index)`
- Lifestyle image generation now retries transient `RESOURCE_EXHAUSTED`/`429` errors with backoff.
- If all image variations fail, the API message now includes per-variation error details for debugging.

See `docs/architecture/2026-02-11-platform-approval-publish-readiness.md` for full details.
See `docs/architecture/2026-02-13-lifestyle-image-optional-gates-and-idempotent-generation.md` for the latest image readiness + generation updates.
See `docs/architecture/2026-02-13-review-platform-progress-indicators.md` for queue/detail platform progress indicators.
See `docs/architecture/2026-02-19-shopify-manual-overrides-and-lifestyle-retry-debugging.md` for Shopify manual edit behavior and the lifestyle generation retry/debugging update.
For operations, incident response, and rollback procedures, use:
`docs/troubleshooting/2026-02-11-platform-readiness-ops-runbook.md`.

## Core Concepts

### Master SKU vs Variant
- **Master SKU**: the parent identifier you optimize (for example `CL-41-18`).
- **Variant**: the purchasable option (finish/size/etc). In patch JSON, each variant includes `_meta.finish` and `_meta.option_sku` (and its own `offerId`).

### Current (Live) vs Candidate
The Next.js dashboard compares:
- **Current (Live)**: actual content from Shopify (`product_catalog.title`, `product_catalog.narrative_copy`)
- **Candidate**: AI-generated content stored in `generated_content.candidate_content`

The Python pipeline (Streamlit) uses different terminology:
- **Baseline**: previous patch exports in `dashboard_data/lifestyle-eval/`
- **Candidate**: newly generated patch exports in `dashboard_data/lifestyle-eval-candidate/`

Defaults are defined in `src/feedops/cli/defaults.py`.

### Patch JSON (source of truth)
Patch JSON is the source of truth for what the dashboard previews and what the Google/Bing supplemental feeds publish.

Example keys from `dashboard_data/lifestyle-eval-candidate/google-patch-CL-41-18.json`:
- Top-level: `offerId`, `title`, `description`, `short_title`, `_meta`, `variants`
- Each `variants[]` entry: its own `offerId`, `title`, `description`, `_meta.finish`, `_meta.option_sku`

## Performance Tracking

The dashboard tracks content performance through two phases:

### Pre-Publish Baseline
Before publishing optimized content, the system captures a 30-day baseline from Google Ads:
- Stored in `performance_baselines` table
- Metrics: impressions, clicks, CTR, conversions, CVR
- Used for before/after comparison on `/performance` and `/review/[sku]` pages

### Post-Publish Snapshots
After publishing, the `/api/performance/capture-snapshot` endpoint captures ongoing performance:
- Stored in `performance_snapshots` table with `days_since_publish` tracking
- Called manually or via scheduled job (GCP Cloud Scheduler recommended)
- Aggregated into trend charts on SKU review pages

**Example:**
```bash
# Capture snapshot for all published SKUs
curl -X POST https://allied-feed-ops.vercel.app/api/performance/capture-snapshot

# For specific SKU
curl -X POST "https://allied-feed-ops.vercel.app/api/performance/capture-snapshot?master_sku=920D-6"
```

For setup details, see [CLAUDE.md](./CLAUDE.md#performance).

## Setup

### Python environment
This repo targets Python 3.11+ (`pyproject.toml`).

Using `uv` (recommended):
```bash
uv venv
uv pip install -e ".[dev]"
```

### Configuration
Copy `.env.example` to `.env` and set the values you have. At minimum you need **one** LLM provider:
- `OPENAI_API_KEY` or `GEMINI_API_KEY`

Other integrations are used for richer product data and publishing (Shopify + Merchant Center).

Catalog resolution order is implemented in `src/feedops/loaders/catalog_resolver.py`. The default catalog path is:
`data/catalog/Product Catalog.csv`

## Common Workflows

### 1) Sanity check
```bash
PYTHONPATH=./src .venv/bin/python -m feedops.cli.main healthcheck
```

### 2) Optimize a single Master SKU (generates candidate report + patches)
```bash
PYTHONPATH=./src .venv/bin/python -m feedops.cli.main optimize --parent-sku "CL-41-18" --no-dry-run --candidates 1
```

This writes:
- Report: `dashboard_data/lifestyle-eval-candidate/reports/sku-CL-41-18-*.md`
- MasterSKU patch JSON (platform previews):
  - `dashboard_data/lifestyle-eval-candidate/google-patch-CL-41-18.json`
  - `dashboard_data/lifestyle-eval-candidate/bing-patch-CL-41-18.json`
  - `dashboard_data/lifestyle-eval-candidate/shopify-patch-CL-41-18.json`
- Per-variant patch JSON (finish/option specific):
  - `dashboard_data/lifestyle-eval-candidate/variants/CL-41-18/google-CL-41-18-ABR.json`
  - `dashboard_data/lifestyle-eval-candidate/variants/CL-41-18/bing-CL-41-18-ABR.json`
  - `dashboard_data/lifestyle-eval-candidate/variants/CL-41-18/shopify-CL-41-18-ABR.json`

Per-variant files are written by `src/feedops/pipeline/optimize.py`. The dashboard primarily previews the **top-level patch file**, including its embedded `variants[]`.

### 3) Review in the Streamlit dashboard
```bash
PYTHONPATH=./src .venv/bin/python -m feedops.cli.main review-dashboard
```

Dashboard behavior is implemented in `src/feedops/quality/review_dashboard.py`.

Notes:
- For **Google/Bing**, the dashboard is **variant-first**: it lets you select a finish and compares the per-variant `title/description` from the patch JSON.
- The patch’s top-level `title/description` (the “primary item payload”) is available under an “Advanced” expander.
- “Reasoning Inputs” render from the latest SKU report markdown in the `reports/` directories.

### 4) (Optional) Copy candidate exports to baseline
If baseline exports are missing (or you want to reset baseline), use:
```bash
PYTHONPATH=./src .venv/bin/python src/feedops/pipeline/copy_to_baseline.py --dry-run
PYTHONPATH=./src .venv/bin/python src/feedops/pipeline/copy_to_baseline.py --overwrite
```

This logic lives in `src/feedops/pipeline/copy_to_baseline.py`.

### 5) Publish / rollback
Publishing is exposed via CLI subcommands. See:
```bash
PYTHONPATH=./src .venv/bin/python -m feedops.cli.main publish --help
PYTHONPATH=./src .venv/bin/python -m feedops.cli.main rollback --help
```

## Google Merchant Center “structured-only” mode (AI text disclosure)

If you are submitting AI-generated text to Google Merchant Center, you can publish via `structured_title` / `structured_description` and omit plain `title` / `description`.

Set:
```bash
export FEEDOPS_GMC_STRUCTURED_ONLY=1
```

The supplemental feed builder (`src/feedops/integrations/google_supplemental.py`) will then emit `<g:structured_title>` / `<g:structured_description>` (with `digital_source_type`, defaulting to `trained_algorithmic_media`) and omit `<g:title>` / `<g:description>`.

## Testing

Run the full suite:
```bash
PYTHONPATH=./src .venv/bin/python -m pytest -q
```

## Content Generation Architecture (Python Canonical)

The content generation system uses a **BALANCED approach**:
- **Quality-first by default** for standard products.
- **Pain-point-first only when natural** (grab bars, rollerless holders, etc.).

### Prompt Source Of Truth

- Runtime system prompt is canonical in Python: `src/feedops/pipeline/prompts.py`.
- Prompt loading/versioning is enforced by: `src/feedops/api/prompt_loader.py`.
- Supabase `prompt_templates` is data-only (gold examples/guidance), not runtime system prompt authority.

### Master vs Variant Behavior

- **Google/Bing**: variant-facing outputs (finish-aware context).
- **Shopify**: master-facing outputs (finish-agnostic base copy).
- Channel rules and validator constraints are applied in the Python pipeline before persistence.

### Runtime Prompt/Data Flow

```mermaid
flowchart TD
  subgraph UI["Dashboard (Next.js)"]
    A["Review/Generate UI"] --> B["`/api/regenerate` route"]
    B --> C["Cloud Run API (`src/feedops/api/main.py`)"]
  end

  subgraph PY["Python Generation Pipeline"]
    C --> D["Load product + variants from Supabase (`product_catalog`, `variant_index`)"]
    D --> E["Build evidence (`src/feedops/pipeline/evidence.py`)"]
    E --> F["Load canonical system prompt (`src/feedops/pipeline/prompts.py`)"]
    C --> G["Load data assets (`prompt_templates`, finish list, category guidance) via `prompt_loader.py`"]
    F --> H["Compose runtime prompt (platform + master/variant rules)"]
    G --> H
    H --> I["LLM provider call (`src/feedops/providers/*`)"]
    I --> J["Schema/validation + scoring"]
  end

  subgraph DB["Supabase Writes"]
    J --> K["`generated_content` (candidate + score + prompt hash)"]
    J --> L["`regeneration_history` (prompt/user context + mode)"]
    J --> M["`variant_finish_sentences` (Google/Bing finish map)"]
  end
```

### Why Fixtures Still Exist

- Python (Cloud Run pipeline) is the runtime logic source-of-truth for prompt + generation + validation behavior.
- Supabase is the runtime data/evidence source-of-truth for product rows, search insights, and persisted generation outputs.
- Fixture SKU files in `samples/eval-skus*.json` are deterministic offline regression baskets for repeatable tests/CI when environment or network varies.

## 6-Agent Pipeline Content (Experimental)

The 6-agent pipeline is an experimental content generation approach using persona-driven storytelling and adversarial review. It produces higher quality content than the default Cloud Run pipeline but takes 2x longer.

### What Was Generated

**Date:** 2026-02-07
**SKUs:** 10 products (1016, 1024, 1024E, 102, 1020, 1026, MC-60, WP-1/16, 1020-3, 1025U)
**Quality:** Average 87.2/100 (range: 82-98)
**Gold Standard:** SKU 1020-3 scored 98/100

### Pipeline Architecture

**Stage 1: Storytelling Workshop** (3 agents, parallel)
- Designer Persona - Engineering and material details
- Contractor Persona - Installation volume and durability data
- Homeowner Persona - Daily use patterns and emotional benefits

**Stage 2: Content Court** (3 agents, sequential)
- Synthesizer - Blends 3 perspectives into cohesive content
- Prosecutor - Reviews for AI slop and generic phrases
- Judge - Final quality scoring and approval

### Backup & Restore

The 6-agent pipeline content is backed up in git to prevent accidental loss during "Regenerate All" operations.

**Backup Files:**
- `6-agent-pipeline-content-backup.json` - Structured backup with all titles/descriptions
- `restore-6-agent-content.sql` - One-click SQL restore script

**How to Restore:**

Via Supabase SQL Editor:
```bash
# 1. Open: https://supabase.com/dashboard/project/qezuszwufortkiutlhym/sql/new
# 2. Copy contents of restore-6-agent-content.sql
# 3. Execute
# 4. Verify: All 10 SKUs will show purple "6-Agent Pipeline" badges
```

Or tell Claude: "restore the 6-agent content" to run via Supabase MCP.

**Identifying Agent Content:**

The review page (`/review/[sku]`) displays a badge next to the SKU name:
- 🟣 **Purple "6-Agent Pipeline"** - High-quality agent-generated content
- 🔵 **Blue "Cloud Run"** - Default pipeline content

**Important:** Clicking "Regenerate" on agent-generated SKUs will overwrite with Cloud Run content. Restore from backup if needed.

### When to Use 6-Agent Pipeline

**Use for:**
- High-value SKUs (top performers, new products)
- Content requiring exceptional quality (gold standard examples)
- Testing new content strategies

**Use Cloud Run for:**
- Bulk generation (50+ SKUs)
- Lower-priority products
- Speed over quality scenarios

## Docs

- Brand identity context: `docs/allied_brass_complete_brand_identity_v2 (4).md`
- Platform guidelines: `docs/04-platform-guidelines.md`
- Testing notes: `docs/testing-guide.md`
- Prompt redesign plan: `.claude/plans/streamed-shimmying-dove.md`
