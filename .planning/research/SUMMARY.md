# Project Research Summary

**Project:** Allied FeedOps — v1.2 Impact Debug & Diagnostics
**Domain:** Google Shopping feed optimization — diagnostic and measurement layer for existing AI content pipeline
**Researched:** 2026-02-20
**Confidence:** HIGH

## Executive Summary

This is a diagnostic and observability milestone for a running system, not a greenfield build. The v1.1 system has a complete content generation pipeline (Cloud Run Python), approval workflow, multi-platform publishing, and performance monitoring — but the system cannot explain why optimized content is not producing measurable Google Shopping impact. Research confirms the problem is a visibility gap, not a capability gap. Before any fix can be applied, the team must answer four sequential questions: Is content actually reaching GMC? Which code path runs in production? Are feature flags wired to the active execution path? Is performance being measured after propagation, not before?

The most critical architectural finding from direct code inspection is that two separate generation paths exist with divergent capabilities. The primary path (single-SKU regeneration from the UI) does not invoke feature flags, segment strategy, or the batch generator — it uses a separate prompt-building function in `main.py`. The batch path uses `generator.py` where SEGMENT_STRATEGY_V1 is called. Two flags (PROMPT_CONTRACT_V2, INTENT_CURATOR_V1) appear to have no active call sites in any live path. This means capabilities the team believes are active may not be running during normal UI-driven regeneration. This must be verified with a static grep audit before drawing any conclusions.

The recommended approach is strictly sequential: diagnose before fixing. All diagnostic data already exists in Supabase — coverage funnel counts can be answered with SQL queries in under an hour, with no new code. The highest-probability silent impact killer is GMC disapproval: products can be silently blocked from serving regardless of content quality. The Merchant API integration to surface disapproval status is the only net-new infrastructure needed. Everything else is queries, lightweight endpoints, and one-time verification scripts against existing data.

## Key Findings

### Recommended Stack

The existing stack (google-ads>=28.4.1, gspread>=6.0, supabase>=2.0, FastAPI, Next.js) covers all diagnostic needs except GMC product status. Three new Python packages are needed: `google-shopping-merchant-products`, `google-shopping-merchant-reports`, and `google-shopping-merchant-issueresolution`. These use the same OAuth2 credentials already bound to the Cloud Run runtime service account — no new secrets needed. No dashboard changes and no new infrastructure are required for diagnostic scripts. The Content API for Shopping v2.1 should be avoided (deprecated, August 2026 shutdown).

**Core technologies:**
- `google-shopping-merchant-products` (new): Per-product GMC status and item-level issue detail — the only supported path post-Content API deprecation
- `google-shopping-merchant-reports` (new): Fast-path disapproval detection via `product_view` query filtering on `aggregated_reporting_context_status` — avoids paginating all 2,784 products
- `google-ads` (existing, v28.4.1+): GAQL `shopping_product` resource for campaign eligibility status; `shopping_performance_view` for zero-impression published SKU gap analysis
- Custom label cohort split via `custom_label_3`: Manual A/B testing approach using existing supplemental feed infrastructure — no third-party tools needed (Feedonomics-verified pattern)
- Four-layer propagation verification: Sheets write confirmation → GMC fetch status via `datasources.list` → GMC product status update → Ads serving impression confirmation

### Expected Features

Research confirms this milestone is primarily closing visibility gaps, not adding new features. Most diagnostic data exists today in Supabase with no new collection needed. The build list is queries, lightweight endpoints, and one new Merchant API integration.

**Must have (table stakes — needed to answer "is the system working?"):**
- SKU coverage funnel — count SKUs at each stage: generated, approved, published, in-feed (single SQL query against existing tables, no code change)
- Feature flag active-state API — `/runtime-state` endpoint returning which flags are live in the running Cloud Run instance (reads env vars already loaded by `runtime_controls.py`)
- Prompt hash lineage — for each published SKU, show which `generation_prompt_hash` is live (join already available across `generated_content` and `publish_events`, no new data needed)
- Search query coverage health — count of SKUs by data quality tier (0 queries vs 1-5 vs 5+ with volume data); 1,960/2,784 SKUs currently have no search data

**Should have (needed to confirm fixes are working):**
- Content propagation timestamp chain — `approved_at` → `published_at` → estimated GMC processing window → first performance snapshot date
- GMC feed row spot checker — compare live Google Sheets rows vs `approved_content` in Supabase for 10-20 recently-published SKUs (Sheets API already integrated for writes; read path is the addition)
- Feed quality score on `/regenerate` path — currently only `/optimize-sku` produces self-scores; adding to `/regenerate` enables quality distribution analysis
- GMC disapproval visibility — Merchant API `product_view` integration to surface disapproved products and `item_issues`; highest-priority unknown and most likely silent impression killer
- Bottleneck classifier — synthesizes funnel + propagation + GMC status into a per-SKU diagnosis label

**Defer (v2+ or blocked until prerequisites exist):**
- Feature flag impact segmentation — requires per-generation flag-state logging which does not exist; unbuildable until `feature_flags_active` column is added to `regeneration_history`
- Content quality regression detector — requires self-score on `/regenerate` path first (prerequisite not yet met)
- GMC price competitiveness dashboard — useful for pricing strategy, not content optimization; premature until content impact is confirmed
- Real-time GMC status polling — rate limits and batch-processing nature of supplemental feeds make this architecturally inappropriate; use scheduled daily capture instead

### Architecture Approach

The diagnostic layer is purely additive. No changes to existing generation paths until root cause is confirmed by evidence. The build sequence is: coverage SQL queries (zero code) → static flag call-site audit (grep) → single-SKU path trace (one `log_event()` addition) → propagation verification (existing Sheets API read path) → GMC disapproval integration (new). New files go in `src/feedops/diagnostics/` and `dashboard/src/app/api/diagnostics/`. `main.py` gets a minor addition: `generation_path` field in existing `log_event()` calls, non-breaking.

**Major components:**
1. `src/feedops/diagnostics/coverage_queries.py` (NEW) — read-only SQL queries for funnel counts; zero risk, immediate answers without deployment
2. `src/feedops/api/diagnostics.py` (NEW) — FastAPI router for `/diagnostics/flags` and `/diagnostics/feed-audit` endpoints
3. `src/feedops/integrations/gmc_product_audit.py` (NEW) — Merchant API integration for disapproval detection and item-level issue surfacing
4. `dashboard/src/app/api/diagnostics/` (NEW) — Next.js routes proxying diagnostic data to dashboard UI
5. Supabase migrations (NEW, deferred) — `flag_snapshot JSONB` and `generation_path TEXT` columns on `regeneration_history`, added only after root cause is confirmed

### Critical Pitfalls

Research identified 12 pitfalls grounded in documented investigation history within this codebase, not generic best practices.

1. **Coverage vs. quality confusion** — Optimizing prompt quality when <10% of catalog is published moves total CTR by fractions of a percent. Establish published SKU count before any quality work. If under 10% of 2,784 SKUs are live with optimized content, fix coverage first, not prompts.

2. **Assuming feature flags are active when they default to True** — PROMPT_CONTRACT_V2 and INTENT_CURATOR_V1 likely have no active call sites despite being defined with `default=True` in `feature_flags.py`. The absence of an env var uses the default (often True), which is the opposite of the expected opt-in convention. Verify with static grep before assuming any flag affects production behavior.

3. **Treating `core.ts` as the active single-SKU generation path** — `dashboard/src/lib/regeneration/core.ts` has zero imports in the entire codebase. Reading it to understand generation behavior is wasted effort. The active single-SKU path is Python `main.py /regenerate`, confirmed by tracing from `RegenerateButton.tsx` → `route.ts` → Cloud Run.

4. **Measuring impact before verifying GMC propagation** — The supplemental feed chain has four independently-failable steps. Checking that Google Sheets was updated is only step one. GMC must fetch the sheet (on its own schedule, typically daily), process the product, and approve it before impressions can reflect new content. This takes 24-72 hours typically, up to 9 days observed. Never conclude a fix failed without confirming GMC shows the new title.

5. **Applying multiple fixes simultaneously** — Deploying several changes at once makes improvement unattributable and regressions impossible to isolate. One fix per 14-28 day measurement window. Use `performance_snapshots` to capture pre-fix baseline before each deployment, not just the first one.

## Implications for Roadmap

All four research files converge on the same message: root cause is unknown and must be verified before any fix is applied. Fixing before diagnosing is the highest-risk anti-pattern identified.

### Phase 1: Diagnose — Establish Ground Truth

**Rationale:** Coverage, flag wiring, path execution, and propagation can all be checked with zero or minimal code changes. This phase has the highest ROI of any work in the milestone. All data exists in Supabase today. Operational basics (GMC UI checks) must precede any engineering work.

**Delivers:**
- SKU coverage funnel: exact count of how many of 2,784 SKUs have content at each funnel stage
- Confirmed feature flag call-site inventory: which flags actually run in which generation paths
- Confirmed active generation path for single-SKU UI regeneration (Path A vs B vs C)
- Feed propagation verification for 10-20 recently-published SKUs via live Sheets read
- Evidence completeness check: which SKUs were generated without search query data

**Addresses (from FEATURES.md):** SKU Coverage Funnel (P1), Feature Flag Active-State API (P1), Prompt Hash Lineage (P1), Search Query Coverage Health (P1)

**Avoids (from PITFALLS.md):** Coverage vs. quality confusion (Pitfall 1), dead code path confusion (Pitfall 3), over-engineered diagnostics before basics (Pitfall 9), query logic vs. pipeline failure confusion (Pitfall 6)

**Build sequence within Phase 1:**
1. Coverage SQL query (30 min, zero code, run via Supabase MCP)
2. Static flag grep audit (30 min, zero code — `grep -rn "is_prompt_contract_v2_enabled\|is_intent_curator_v1_enabled" src/feedops/`)
3. Operational basics checklist: GMC UI feed fetch schedule, product approval status, sheet accessibility (30 min, no code)
4. `/runtime-state` endpoint in Python (1-2 hours, reads existing env vars from `runtime_controls.py`)
5. Propagation spot-check: read live Sheets rows and compare to `approved_content` in DB (2-3 hours, existing Sheets API)

### Phase 2: Measure — Confirm What's Broken

**Rationale:** Once coverage and propagation are confirmed, the measurement infrastructure must be validated before fixes are applied. Baseline contamination (re-publish events shifting baseline anchor) and too-early measurement are documented pitfalls that produce false negatives — conclusions that fixes did not work when they actually did.

**Delivers:**
- Propagation timestamp chain for published SKUs (elapsed time per pipeline stage)
- Baseline integrity audit: identify SKUs with multiple publish events that contaminate the baseline anchor
- GMC disapproval visibility: Merchant API integration showing which published SKUs are blocked from serving
- Feed quality score added to `/regenerate` path (prerequisite for quality distribution analysis)
- Bottleneck classifier: per-SKU root cause label synthesizing all Phase 1 and 2 data

**Addresses (from FEATURES.md):** Content Propagation Timestamp Chain (P1), GMC Disapproval Visibility (P2), GMC Feed Row Spot Checker (P2), Feed Quality Score on /regenerate (P2), Bottleneck Classifier (P2)

**Uses (from STACK.md):** `google-shopping-merchant-reports` (fast-path disapproval filter), `google-shopping-merchant-products` (per-product issue detail), GAQL `shopping_product` resource (campaign eligibility status)

**Avoids (from PITFALLS.md):** Measuring too early (Pitfall 5), contaminated baselines (Pitfall 12), feed propagation not verified before measurement (Pitfall 4), runtime prompt vs. source code confusion (Pitfall 8)

### Phase 3: Fix — Apply Targeted Interventions

**Rationale:** Fixes are selected based on what Phases 1 and 2 reveal. Fix candidates are conditional — only apply the ones that match confirmed findings. Each fix deploys independently with its own pre-fix baseline capture and 14-28 day measurement window.

**Conditional fix candidates (apply only if evidence confirms the finding):**

| Finding | Fix |
|---------|-----|
| Coverage <10% published | Run batch generation + approval workflow for top N SKUs by impression volume |
| PROMPT_CONTRACT_V2 has no call sites | Wire it to Path A (`_build_generation_user_prompt()`) or remove the dead flag |
| Path A missing segment_strategy | Add `_resolve_segment_strategy()` call to `main.py /regenerate` |
| Propagation gap (Sheets content stale) | Fix case normalization (shopify_us_ → shopify_US_) or row-matching in `google-sheets.ts` |
| Evidence thin for low-volume SKUs | Run search term backfill first; confirm keyword bank in Cloud Run; re-generate after data is populated |
| GMC disapproval found | Surface `item_issues` in SKU review UI; address specific disapproval categories |

**Avoids (from PITFALLS.md):** Regression from simultaneous fixes (Pitfall 10), breaking existing workflows during fix application (Pitfall 7), fix-before-diagnosis anti-pattern (Pitfall 9)

**Delivers:** One independently measurable fix per measurement window; feature flag state logging added to `regeneration_history` as low-cost addition enabling future experiment analysis

### Phase Ordering Rationale

- Phase 1 is all zero-code or minimal-code work. It runs before Phase 2 because baseline integrity depends on knowing which SKUs are actually published and which path generated their content.
- GMC disapproval integration (Phase 2) is the only net-new infrastructure in the milestone. It belongs in Phase 2, not Phase 1, because it requires code and deployment while Phase 1 is zero-code verification.
- Fix application (Phase 3) is deliberately last. Applying fixes before diagnosis confirmed is the primary anti-pattern identified across all research files.
- Feature flag impact segmentation is excluded entirely from this milestone. It requires `feature_flags_active` logging to exist first (a Phase 3 addition). Segmentation analysis is a v1.3 item.

### Research Flags

**Phase 1 — No additional research needed.** All data and APIs are known quantities. Coverage queries use existing Supabase tables. Flag audit is a grep. Path trace adds one log line. Standard patterns with existing tooling.

**Phase 2 — GMC disapproval integration may need research during planning.** The Merchant API Python client libraries are new to this codebase. The `product_view` query pattern is documented in STACK.md, but the specific `item_level_issues` field structure and severity enum behavior should be validated against a live Allied Brass account before the schema for storing GMC status is finalized.

**Phase 3 — No additional research needed.** Fix candidates are fully scoped from Phase 1+2 findings. Code paths for each conditional fix are already understood from ARCHITECTURE.md direct code inspection.

## Confidence Assessment

| Area | Confidence | Notes |
|------|------------|-------|
| Stack | HIGH | Existing packages verified in production. Three new Merchant API packages confirmed on PyPI with official Python client library docs. Same OAuth2 credentials reuse confirmed. One uncertainty: Merchant API beta package API stability — use latest pinned version. |
| Features | HIGH | Based on direct codebase inspection of 32 Supabase tables, audit docs, and confirmed execution paths. Feature flag call-site finding needs static grep verification to be fully confirmed — classified HIGH-probability but not yet ground truth. |
| Architecture | HIGH | Based on direct code inspection of `main.py`, `generator.py`, `feature_flags.py`, `runtime_controls.py`, `route.ts`, and `core.ts`. Three-path generation architecture confirmed, not inferred. Observability layer (in-memory only) confirmed. |
| Pitfalls | HIGH | 12 pitfalls documented, all grounded in either direct code inspection or documented investigation history within this codebase (audit docs from 2026-02-08 and 2026-02-11). Not inferred from generic patterns. |

**Overall confidence:** HIGH

### Gaps to Address

- **Feature flag call-site verification:** ARCHITECTURE.md found no call sites for PROMPT_CONTRACT_V2 and INTENT_CURATOR_V1 from code inspection, but static grep must confirm before the "flag-is-dead" conclusion drives any fix decisions. This is the first action in Phase 1.

- **Coverage funnel actual numbers:** The funnel structure and required tables are documented, but the actual counts (how many of 2,784 SKUs are at each stage) are unknown until the SQL query runs. These numbers determine which phase of work gets prioritized in Phase 3.

- **GMC merchant ID for Merchant API:** The Merchant API integration requires a GMC merchant account ID. Verify this is stored in GCP secrets or accessible before Phase 2 coding begins. The existing Google Ads customer ID (`6253381786`) is not the same as the merchant ID.

- **Campaign type for A/B experiments:** STACK.md notes that Google Ads Shopping experiments may require Performance Max campaigns (not standard Shopping). Verify which campaign type Allied Brass uses before investing in cohort-split A/B infrastructure in Phase 3.

- **Keyword bank deployment:** PITFALLS.md flags that `data/keyword-bank.json` may be gitignored and absent from Cloud Run. Verify presence in deployed container before concluding that cold-start evidence is missing for low-volume SKUs.

- **Measurement window calibration:** The 14-28 day measurement window assumes Allied Brass impression volumes are sufficient for statistical significance. If published SKU coverage is low (finding from Phase 1), this window may need to be longer. Validate against actual impression counts before setting the measurement protocol.

## Sources

### Primary (HIGH confidence)
- Direct code inspection: `src/feedops/api/main.py`, `generator.py`, `feature_flags.py`, `runtime_controls.py` — generation path architecture confirmed, three paths identified
- Direct code inspection: `dashboard/src/app/api/regenerate/route.ts`, `dashboard/src/lib/regeneration/core.ts` — proxy pattern and dead code confirmed
- `docs/database/SCHEMA.md` — 32 tables, all column names and constraints verified
- `docs/audit/signal-audit-2026-02-11/prompt-wiring-map.md` — dead code identification, runtime path verification, search data coverage (824/2,784 SKUs)
- `docs/audit/signal-audit-2026-02-11/external-signals-assessment.md` — evidence completeness for low-volume SKUs
- `docs/audit/SUMMARY-2026-02-08.md` — query logic vs. pipeline failure root cause (match rate 0.3% bug)
- `docs/audit/gmc-feed-investigation-2026-02-08.md` — GMC feed propagation verification pattern
- Google Ads API official docs: `shopping_product` resource, `shopping_performance_view`, impression share fields (verified Feb 2026)
- Google Merchant API official docs: `product_view` table, `item_level_issues`, Python client library (verified Feb 2026)

### Secondary (MEDIUM confidence)
- GMC supplemental feed propagation timing (24-72h typical, 9-day observed) — ppc.land incident report
- Feed optimization impact measurement (title optimization highest CTR lever) — Store Growers guide
- A/B testing via custom labels — Feedonomics blog (verified industry source)
- Google Ads Shopping experiments require Performance Max — Search Engine Land 2024 (verify campaign type before implementing)

### Tertiary (LOW confidence — verify before relying on)
- GMC feed fetch schedule behavior (daily vs. weekly vs. monthly defaults) — Jumpfly blog; verify in GMC UI before assuming the fetch is running at expected frequency
- Impression share measurement window for statistical significance — industry consensus; validate against actual Allied Brass impression volume before setting hard window cutoff

---
*Research completed: 2026-02-20*
*Ready for roadmap: yes*
