# Allied-FeedOps (Project Memory — Keep Short)

## Canonical UI / Production

- **Next.js Dashboard (Vercel)**: `https://allied-feed-ops.vercel.app/login`
- **Supabase project**: `qezuszwufortkiutlhym`

**Access**

- Do **not** store login passwords in git. Share test credentials via a password manager / internal note.

## Defaults (for integrations / tooling)

- **Google Ads customer ID**: `6253381786`
- **GA4 property**: Allied Brass — GA4 (Old)

## What's implemented (dashboard prompts)

- **Implemented**: `docs/prompts/01`–`08`
  - 01-06: performance, batches, publishing, variant review, settings health, regeneration
  - 07: dashboard overview with charts (ApprovalChart, PlatformBreakdown, QualityDistribution, RecentActivity)
  - 08: SKU selection & generation (`/generate` page, `/api/sku-selection/*` routes, tier-based scoring)

## Supabase schema (tables we rely on)

- `sku_approvals` (SKU-level approvals)
- `variant_approvals` (per-finish approvals)
- `variant_index` (maps `master_sku` ⇄ `gmc_offer_id`, finish info)
- `publish_batches`, `batch_sku_assignments` (batch mgmt)
- `publish_events` (audit log)
- `performance_baselines`, `performance_snapshots` (performance)
- `batch_generation_jobs`, `batch_generation_job_skus` (batch content generation)

**Column naming conventions (do not drift)**

- Use `approval_status` (not `status`)
- Use `notes` (not `revision_notes`)
- Use `approved_by` / `approved_at` (not `reviewed_by` / `reviewed_at`)
- Batches use `name` / `notes` / `executed_at`

## GMC / Google policy guardrails (critical)

- **No hallucinations**: never invent specs/claims not in product data.
- **AI text compliance**: prefer `structured_title` / `structured_description` with `digital_source_type=trained_algorithmic_media`.
- **Structured-only mode**: when `FEEDOPS_GMC_STRUCTURED_ONLY=1`, omit standard `title`/`description` so Google does not ignore structured fields.

## Offer ID format (Google / Ads joins)

GMC offer IDs:
`shopify_us_{shopify_product_id}_{shopify_variant_id}` (note lowercase `us`)

## Key dashboard locations

- Pages: `dashboard/src/app/(dashboard)/**`
- API routes: `dashboard/src/app/api/**`
- Supabase query layer: `dashboard/src/lib/supabase/{queries.ts,types.ts}`
- Publishing libs: `dashboard/src/lib/publishing/*`
- Regeneration API: `dashboard/src/app/api/regenerate/route.ts` (stores prompt history; model default aligns to `gpt-5.2`)
- SKU scoring: `dashboard/src/lib/sku-scoring.ts` (tier-based selection algorithm)
- SKU selection API: `dashboard/src/app/api/sku-selection/route.ts` (scored recommendations)
- Batch generation API: `dashboard/src/app/api/sku-selection/generate/route.ts` (start batch jobs)
- Dashboard charts: `dashboard/src/components/dashboard/*.tsx`

## Run locally

### Dashboard

```bash
cd dashboard
npm install
npm run dev
```

### Python (pipeline/tests still in repo)

```bash
uv venv
uv pip install -e ".[dev]"
PYTHONPATH=./src .venv/bin/python -m pytest tests/ -v
```

## Generated content storage

**IMPORTANT**: Generated content (titles, descriptions, images) must now be stored in Supabase, not in git.

- `dashboard_data/` is empty (only README.md) - all evaluation data archived
- Dashboard must read from Supabase `generated_content` and `generated_images` tables
- Use regeneration API to create new content

## Historical archive

All previous data (14,000+ generated files, evaluation data, research docs) preserved in:

- **Branch**: `archive/full-snapshot-2026-02-03`
- **Tag**: `backup/pre-dashboard-cleanup-2026-02-03`

To restore archived content:

```bash
# View what's in the archive
git show archive/full-snapshot-2026-02-03:dashboard_data/

# Restore specific files
git checkout archive/full-snapshot-2026-02-03 -- dashboard_data/batch-40sku-20260130-144146/
```
