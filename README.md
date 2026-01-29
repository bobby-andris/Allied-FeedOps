# Allied FeedOps

Allied FeedOps is the internal tooling that generates, reviews, and publishes **platform-specific product title/description updates** for Allied Brass across:
- Google Merchant Center / Performance Max
- Microsoft (Bing) Merchant Center
- Shopify (storefront product content)

This repo is built around a **Master SKU → many variants (finishes/options)** model. The “shippable unit” on shopping platforms is the **variant offerId/item_id**, so review and publishing are **variant-first** where possible.

## Core Concepts

### Master SKU vs Variant
- **Master SKU**: the parent identifier you optimize (for example `CL-41-18`).
- **Variant**: the purchasable option (finish/size/etc). In patch JSON, each variant includes `_meta.finish` and `_meta.option_sku` (and its own `offerId`).

### Baseline vs Candidate
The Streamlit dashboard compares:
- **Original (Live)**: current Shopify content
- **Baseline (Previous)**: previous patch exports (used for comparison)
- **Candidate (New)**: newly generated patch exports

By default:
- Baseline exports: `dashboard_data/lifestyle-eval/`
- Candidate exports: `dashboard_data/lifestyle-eval-candidate/`
- Reports live under each exports dir at `reports/`

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

## Docs

- Brand identity context: `docs/allied_brass_complete_brand_identity_v2 (4).md`
- Platform guidelines: `docs/04-platform-guidelines.md`
- Testing notes: `docs/testing-guide.md`

