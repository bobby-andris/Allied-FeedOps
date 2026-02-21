# Feature Research

**Domain:** Feed optimization diagnostic and measurement system (AI content generation for Google Shopping)
**Researched:** 2026-02-20
**Confidence:** HIGH — based on verified codebase review, architecture docs, audit traces, and current-state documentation

---

## Context: What Already Exists

This is a subsequent milestone for a running system. The v1.1 system has:
- AI content generation pipeline (Cloud Run Python) wired end-to-end
- Dashboard review/approval workflow with per-platform badges
- Publishing to Google Sheets supplemental feed, Shopify, Bing
- Performance baselines and snapshots with delta comparison UI
- Search query insights from Google Ads (10,000+ queries, 824/2,784 SKUs covered)
- Feature flags: `PROMPT_CONTRACT_V2`, `INTENT_CURATOR_V1`, `SEGMENT_STRATEGY_V1`
- Monitoring page with CTR/impressions deltas and search query deltas
- Attribution forensics page for GA4 revenue attribution

**The problem is not missing features — it is missing visibility into whether existing features are working.** The diagnostic gap is: we cannot determine WHY impact is weak without observing what actually runs in production.

---

## Feature Landscape

### Table Stakes (Required to Diagnose Impact)

Features that any team would expect in order to answer "why isn't this working?" Missing these makes the impact question unanswerable by inspection alone.

| Feature | Why Expected | Complexity | Notes |
|---------|--------------|------------|-------|
| Runtime path verification — end-to-end trace from UI click to live feed | Cannot trust that generation → approval → publish → Google feed is wired without verifying in production. Supplemental feed update lag can be 24-72h, observed up to 9 days per GMC incident reports. | MEDIUM | Codebase confirms Python is SOT and dashboard is thin proxy. Feed propagation (Google Sheets → GMC → Google Ads indexing) has never been verified with timestamps. |
| Feature flag active-state confirmation | Three flags exist in env vars but there is no dashboard surface showing which are active in the live Cloud Run instance at any given time | LOW | `PROMPT_CONTRACT_V2`, `INTENT_CURATOR_V1`, `SEGMENT_STRATEGY_V1` exist in `runtime_controls.py` but have no observability. Flag state is invisible at runtime. |
| SKU coverage funnel — generated vs approved vs published vs in-feed counts | Without this, "we optimized content" is unmeasurable. The bottleneck could be at any of four stages: generation, approval, publish, or GMC indexing | MEDIUM | All four stages have data: `generated_content`, `sku_approvals`, `publish_events`, `batch_sku_assignments`. No single view aggregates these. |
| Content propagation timestamp chain | Shows how long each SKU takes from approval to live in GMC. Identifies where delays accumulate. | MEDIUM | `publish_events.published_at` exists. GMC indexing timestamp is not tracked. Supplemental feed is Google Sheets — GMC processes on its own schedule. |
| Feed quality score surface per SKU | Google Shopping rewards completeness. Short or non-compliant titles reduce impression share silently. Users cannot tell whether generated content is high-quality or borderline. | MEDIUM | `quality_score` field exists in `generated_content` but only populated by `/optimize-sku` path. The `/regenerate` path used in the dashboard does NOT produce self-scores. Documented gap in signal audit. |
| Per-SKU impact attribution — before/after content change impressions and CTR | Without pre/post comparison, cannot confirm content changes moved metrics | MEDIUM | `performance_baselines` and `performance_snapshots` exist. Monitoring page shows deltas. Gap: only 824/2,784 SKUs have search query data, and baseline capture requires published SKUs. |
| GMC disapproval and warning visibility | Google silently disapproves products for policy violations. Disapproved products show zero impressions regardless of content quality. This is the highest-probability silent impact killer. | HIGH | Not currently tracked. Requires Merchant API `product_view` with `aggregated_reporting_context_status` and `item_issues`. |

### Differentiators (High Diagnostic Value, Not Universally Built)

Features that go beyond "what broke" to "why it broke" and "how to fix it efficiently." These distinguish a diagnostic system that guides decisions from one that only surfaces raw data.

| Feature | Value Proposition | Complexity | Notes |
|---------|-------------------|------------|-------|
| Bottleneck classifier — code-path vs auction vs coverage vs propagation | Pinpoints root cause category without manual investigation. The four failure modes are: (1) content not approved; (2) approved but not published; (3) published but not indexed in GMC; (4) indexed but auction dynamics prevent impressions | MEDIUM | Requires combining: coverage funnel counts + propagation timestamps + GMC status + performance delta. No single system does all four today. |
| Prompt hash lineage — which prompt version produced which live content | If content quality is the issue, knowing whether current live content was generated with old or new prompt is critical for attribution. The answer to "did we ship the fix?" is currently a manual investigation. | LOW | `generated_content.generation_prompt_hash` exists. `publish_events` stores content snapshots. A join between them shows which prompt version is live for each SKU. Already 90% of the data exists. |
| Search query coverage health per SKU — count, recency, volume quality | Signal audit confirmed: SKUs without search query data get weaker content. 1,960/2,784 SKUs have no search data today. Shows which SKUs will generate weak content before generation happens. | LOW | `search_query_sync_jobs` tracks recency. `search_queries_by_master_sku` has counts. A simple aggregation query surfaces this. Exists in data; missing from UI. |
| GMC feed row verification — confirm supplemental feed row matches approved content | The pipeline (generate → approve → publish → Google Sheets row) can silently diverge. Column mapping bugs are a documented historical failure mode (2026-02-06 bug corrupted production data by writing to wrong columns). | MEDIUM | Google Sheets API is already integrated in `google-sheets.ts`. `publish_events` stores `final_payload_snapshot`. A spot-check reads the live sheet and compares to `approved_content` in DB. |
| Feature flag impact segmentation — delta metrics for flag-on vs flag-off SKUs | The three feature flags have no experiment tracking. Cannot measure whether `INTENT_CURATOR_V1` actually improves CTR without knowing which SKUs had content generated under each flag state. | HIGH | Requires: (a) flag-state logging at generation time — not currently done; (b) performance deltas for those SKUs. Flags are env vars, not tracked per generation run. Unbuildable until logging exists. |
| Content quality regression detector — compares self-score across prompt versions | Catches prompt changes that degrade quality before they propagate widely | MEDIUM | Self-scores only exist for `/optimize-sku` path (not `/regenerate`). Adding self-score to `/regenerate` response is the prerequisite. |

### Anti-Features (Commonly Requested, Often Problematic)

| Feature | Why Requested | Why Problematic | Alternative |
|---------|---------------|-----------------|-------------|
| Real-time GMC status polling | "Is my content live?" is the obvious question | GMC API rate limits and supplemental feed processing is batch, not real-time. Polling 2,784 SKUs repeatedly would exhaust quota. Polling does not change when GMC processes the feed — that is external. | Scheduled daily status capture to a `gmc_status` table. Alert when disapproval rate crosses a threshold. |
| Automatic content re-generation when metrics drop | Seems like a logical feedback loop | CTR can drop for auction reasons (bid changes, competitor entry, seasonality) completely unrelated to content. Auto-regeneration would waste Cloud Run budget and generate noise without confirming content is actually the issue. | Manual trigger with an evidence panel showing WHY a SKU's metrics dropped before regeneration |
| A/B testing framework at SKU level | Standard CRO instinct | Google Shopping does not support controlled A/B experiments at the SKU level within the same campaign. Controlled tests require separate campaigns with the same products at different bid levels — complex to set up and control for. | Segment-level holdout rollout: optimize one `custom_label_0` category, keep another as control for 2-week windows. Already planned in post-optimization plan. |
| Full new audit log UI for content changes | Compliance instinct | `regeneration_history` and `publish_events` already store this. Building a new audit log UI before fixing the actual diagnostic gap is scope creep. | Use `publish_events.payload_snapshot` for rollback and `regeneration_history` for history. Surface in existing review UI where needed. |
| GMC price competitiveness dashboard | Merchant API provides benchmark prices | Price competitiveness is useful for pricing strategy, not content optimization. Titles and descriptions cannot contain price claims. Adding this before content impact is proven is a distraction from diagnosing the current gap. | Defer until content impact is confirmed and the next growth lever needs identification. |

---

## Feature Dependencies

```
[SKU Coverage Funnel]
    └──requires──> [generated_content + sku_approvals + publish_events joined]
                       └──requires──> [consistent publish_event writes for all paths]

[Bottleneck Classifier]
    └──requires──> [SKU Coverage Funnel]
    └──requires──> [Content Propagation Timestamp Chain]
    └──requires──> [GMC Disapproval Visibility]

[Feature Flag Impact Segmentation]
    └──requires──> [Feature Flag State Logging at Generation Time]
                       └──blocks──> [any flag experiment measurement until logging exists]

[Prompt Hash Lineage View]
    └──enhances──> [Bottleneck Classifier] (identifies content-quality bottleneck vs other bottlenecks)
    └──requires──> [generation_prompt_hash in publish_events or joinable via generated_content]

[Content Quality Regression Detector]
    └──requires──> [self_score added to /regenerate path] (currently missing — only /optimize-sku has it)

[GMC Feed Row Verification]
    └──requires──> [Google Sheets API read access] (already exists in codebase)
    └──requires──> [publish_events.final_payload_snapshot] (migration 033 planned)

[Search Query Coverage Health]
    └──enhances──> [SKU Coverage Funnel] (adds signal-quality dimension to coverage)
    └──requires──> [search_query_sync_jobs + search_queries_by_master_sku] (already populated)
```

### Dependency Notes

- **Feature flag impact segmentation is currently unbuildable.** Flags are env vars, not tracked per generation run. The flags have no logging at the `regeneration_history` write step. Building measurement requires adding `feature_flags_active` to `regeneration_history` first.
- **GMC disapproval visibility is the hardest item and the highest priority unknown.** It requires a new Merchant API integration. This is the most likely silent killer of impressions — disapproved products show zero impressions regardless of content quality.
- **SKU Coverage Funnel is the prerequisite for everything else.** Once the funnel is visible, all other diagnostics have a baseline to work against. It is also the fastest to build.
- **Content propagation timestamps** depend on the supplemental feed processing being a Google Sheets fetch-on-schedule process. GMC processes the sheet on its own schedule. The timestamp chain must account for this external latency (24-72h typical, up to 9 days observed).
- **Prompt hash lineage is 90% built** from existing data. The join is: `publish_events` → `batch_sku_assignments` → `generated_content.generation_prompt_hash`. No new data needed, just a query and a UI surface.

---

## Prioritized Diagnostic Build List

This milestone is primarily about closing visibility gaps, not building new features. The priority ordering answers: "what must we verify first to diagnose weak impact?"

### Phase 1: Verify the Path (Answer: Is the system actually working end-to-end?)

All data exists. These are query + lightweight UI additions, not new infrastructure.

- [ ] **SKU Coverage Funnel** — query joining `generated_content`, `sku_approvals`, `batch_sku_assignments`, `publish_events` → show counts at each stage. Answers: how many SKUs are actually live with optimized content? Estimated complexity: LOW (single SQL query + summary card on existing dashboard page).
- [ ] **Feature Flag Active-State API** — add a `/runtime-state` endpoint to `main.py` that returns which feature flags are active in the live Cloud Run instance. Answers: are the flags we think are on actually on? Estimated complexity: LOW (one new endpoint, reads env vars already loaded by `runtime_controls.py`).
- [ ] **Prompt Hash Lineage** — for published SKUs, show which `generation_prompt_hash` is in the live `publish_events`. Answers: was live content generated with current or old prompt? Estimated complexity: LOW (join query, add column to existing monitoring page).
- [ ] **Search Query Coverage Health summary** — count SKUs by search data quality tier (0 queries, 1-5 queries, 5+ queries with volume data). Answers: how many SKUs will get weak content because search data is missing? Estimated complexity: LOW (aggregation query, summary card).

### Phase 2: Measure the Bottleneck (Answer: Where exactly is impact blocked?)

Requires Phase 1 data to be meaningful.

- [ ] **Content Propagation Timestamp Chain** — for published SKUs, show: `approved_at` → `published_at` → estimated GMC processing window → first performance snapshot date. Answers: how long is the lag between publishing and measuring impact? Estimated complexity: MEDIUM (join across tables + estimated GMC window column).
- [ ] **Feed Quality Score added to /regenerate path** — add `quality_score` and self-score dimensions to `/regenerate` path response (matches what `/optimize-sku` produces), surface aggregate quality distribution in review UI. Answers: are we generating high-quality content or borderline content? Estimated complexity: MEDIUM (modify Python `/regenerate` to include self-score; the schema and scoring rubric already exist in the codebase for the other path).
- [ ] **GMC Feed Row Spot Checker** — read N rows from the live Google Sheet and compare `id` + `title` + `description` to `approved_content` in DB. Answers: does the live feed actually contain our optimized content? Estimated complexity: MEDIUM (Google Sheets API read already integrated, add diff logic).

### Phase 3: Attribute Impact (Answer: Did content changes actually move metrics?)

Requires Phases 1 and 2 data to contextualize.

- [ ] **GMC Disapproval Visibility** — fetch `product_view` from Merchant API for published SKUs, flag disapproved products and surface `item_issues`. Answers: are products being blocked from serving silently? Estimated complexity: HIGH (new Merchant API integration, schema for status tracking, sync job).
- [ ] **Bottleneck Classifier summary** — synthesize Phase 1+2 data into a single diagnostic view: for each published SKU, classify the bottleneck as (generation missing | approval missing | publish missing | not in feed | in feed but no data yet | in feed with data and metrics). Estimated complexity: MEDIUM (classification logic over existing data, new view in dashboard).
- [ ] **Feature Flag State Logging** — add `feature_flags_active` JSON field to `regeneration_history` at write time. Enables future flag-impact segmentation. Estimated complexity: LOW to add logging, HIGH to build experiment analysis (defer analysis to future milestone).

---

## Feature Prioritization Matrix

| Feature | Diagnostic Value | Implementation Cost | Priority |
|---------|-----------------|---------------------|----------|
| SKU Coverage Funnel | HIGH — baseline for all other diagnostics | LOW | P1 |
| Feature Flag Active-State API | HIGH — confirms flags are actually running | LOW | P1 |
| Prompt Hash Lineage | HIGH — confirms live content version | LOW | P1 |
| Search Query Coverage Health | HIGH — explains content quality variance | LOW | P1 |
| Content Propagation Timestamp Chain | HIGH — reveals attribution lag | MEDIUM | P1 |
| GMC Feed Row Spot Checker | HIGH — verifies end-to-end wiring | MEDIUM | P2 |
| Feed Quality Score (add to /regenerate) | MEDIUM — improves signal quality | MEDIUM | P2 |
| GMC Disapproval Visibility | HIGH — most likely silent impression killer | HIGH | P2 |
| Bottleneck Classifier | HIGH — synthesizes all diagnostic data | MEDIUM | P2 |
| Feature Flag State Logging | MEDIUM — enables future experiments | LOW | P2 |
| Feature Flag Impact Segmentation | HIGH — proves flag value | HIGH | P3 (blocked until flag logging exists) |
| Content Quality Regression Detector | MEDIUM — prevents regressions | MEDIUM | P3 |
| Impression Share Gap by Category | LOW — secondary signal | MEDIUM | P3 |

**Priority key:**
- P1: Must have to diagnose current impact gap — answers whether the system is working
- P2: Should have to confirm fixes are working — answers whether fixes moved metrics
- P3: Nice to have for ongoing optimization — not needed to diagnose the current gap

---

## What Existing Infrastructure Already Supports (No New Build Needed)

The instinct to "build more features" is often the wrong response when diagnostic gaps can be closed with queries and small additions.

| Diagnostic Need | Already Available | Where |
|----------------|-------------------|-------|
| How many SKUs generated content | YES | `generated_content` table count |
| How many SKUs approved | YES | `sku_approvals` with `approval_status` |
| How many SKUs published | YES | `publish_events` count |
| What prompt version produced content | YES | `generated_content.generation_prompt_hash` |
| When was each SKU published | YES | `publish_events.published_at` |
| Performance delta since publish | YES | Monitoring page already exists with delta view |
| Search query count per SKU | YES | `search_queries_by_master_sku` |
| Search query data freshness | YES | `search_query_sync_jobs` |
| Content quality score (optimize path only) | PARTIAL | `generated_content.quality_score` — null for regenerate path |
| Live feed content verification | PARTIAL | Google Sheets API integrated for writes; read-path for verification not built |
| GMC approval status | NO | Requires new Merchant API integration |
| Feature flag state in Cloud Run | NO | Flags are env vars with no observability surface |
| Prompt hash in published content | YES (joinable) | `generated_content.generation_prompt_hash` + `publish_events` |

---

## Sources

- Codebase verified (HIGH confidence): `docs/audit/signal-audit-2026-02-11/prompt-wiring-map.md` — prompt traceability confirmed, regenerate vs optimize-sku schema difference confirmed
- Codebase verified (HIGH confidence): `docs/audit/signal-audit-2026-02-11/external-signals-assessment.md` — keyword planner wiring confirmed, cold-start gap documented
- Codebase verified (HIGH confidence): `docs/architecture/2026-02-11-content-generation-pipeline-current-state.md` — `/regenerate` path lacks self-score confirmed as known gap
- Codebase verified (HIGH confidence): `docs/architecture/prompt-contract.md` — prompt hash persistence contract confirmed
- Codebase verified (HIGH confidence): `docs/plans/2026-02-20-feedops-post-custom-label0-optimization.md` — segment rollout strategy and final-payload observability planned
- Codebase verified (HIGH confidence): `docs/database/SCHEMA.md` — table structure and column names confirmed
- Codebase verified (HIGH confidence): `.planning/PROJECT.md` — v1.2 milestone goals, feature flag names, known issues
- External (MEDIUM confidence): GMC supplemental feed propagation timing — 24-72h typical, up to 9-day delay observed per [ppc.land incident report](https://ppc.land/google-merchant-centers-24-hour-update-promise-fails-by-nine-days/)
- External (MEDIUM confidence): Feed optimization impact measurement — title optimization highest CTR impact per [Store Growers guide](https://www.storegrowers.com/product-feed-optimization/)
- External (MEDIUM confidence): GMC product view for disapproval tracking — available via [Merchant API ReportService](https://developers.google.com/shopping-content/reference/rest/v2.1/reports/search)

---

*Feature research for: Feed optimization diagnostics and impact measurement*
*Researched: 2026-02-20*
*Context: v1.2 milestone — diagnose why existing generation and publishing is not producing measurable Google Shopping impact*
