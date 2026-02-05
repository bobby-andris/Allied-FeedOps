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

## Python Pipeline (Legacy)

The Python pipeline below is still available for batch processing and CLI operations.

This repo is built around a **Master SKU → many variants (finishes/options)** model. The “shippable unit” on shopping platforms is the **variant offerId/item_id**, so review and publishing are **variant-first** where possible.

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

## Prompt Philosophy: Context Over Rules

The LLM prompt system (`src/feedops/pipeline/prompts.py`) uses a **context-driven approach** rather than prescriptive rules. Instead of telling the LLM "write sentences in this pattern", we give it understanding and trust it to make good decisions.

### The Core Insight

Prescriptive rules like "FIRST SENTENCE PATTERN: [Dimension] [product] in [Finish]..." create robotic, templated output. Context-driven guidance produces descriptions that feel human-written and address real buyer questions.

### What the Prompt Provides

1. **WHO is searching** - Homeowners renovating, designers specifying, people replacing broken products
2. **WHAT questions buyers have** - "Will this look good?", "Will it match?", "Is $80 worth it vs $20?"
3. **WHAT makes Allied Brass worth it** - Style + function, 28 finishes, product innovations, solid brass durability
4. **PLATFORM context** - Google/Bing variants (first impression, make them click) vs Shopify master (already clicked, help them buy)

### Why It Works

The LLM already knows how to write compelling copy. The old approach was **blocking** that knowledge with compliance rules. By providing context instead of constraints, we let the LLM:
- Write different descriptions for different product types (grab bars focus on safety, shower baskets focus on drainage)
- Weave finish names naturally instead of using robotic patterns
- Answer the actual questions buyers have before spending $80

### Example Output Difference

**Old (rule-following):**
> "This 18.75-inch wall-mounted shower basket is crafted from solid brass. Available in Antique Brass. Antique Brass features a softened, aged golden patina..."

**New (context-driven):**
> "This 18.75-inch shower basket in Antique Brass keeps bath essentials organized with vintage-inspired warmth. Ventilated solid brass wires drain quickly and resist rust..."

### TypeScript Dashboard Content Generation

The Next.js dashboard has its own content generation system at `dashboard/src/app/api/regenerate/route.ts`. For Google/Bing, it generates:
1. **Base content** - Finish-agnostic title/description
2. **Finish sentences** - 28 product+finish tailored sentences stored in `variant_finish_sentences`

Variant content is composed at display-time by combining base content with finish-specific sentences. See `docs/prompts/21-unify-content-generation-methodology.md` for methodology comparison with Python.

## Docs

- Brand identity context: `docs/allied_brass_complete_brand_identity_v2 (4).md`
- Platform guidelines: `docs/04-platform-guidelines.md`
- Testing notes: `docs/testing-guide.md`
- Prompt redesign plan: `.claude/plans/streamed-shimmying-dove.md`

