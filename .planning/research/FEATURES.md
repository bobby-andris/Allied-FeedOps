# Feature Landscape: v1.3b Architecture Validation & Data Persistence

**Domain:** Feed optimization platform -- architecture validation, data persistence, content-performance feedback loops
**Researched:** 2026-02-25
**Confidence:** HIGH -- based on exhaustive codebase review of schema, migrations, service.ts, strategic assessment, and PROJECT.md

---

## Context: What Already Exists (DO NOT REBUILD)

Before categorizing new features, here is the infrastructure this milestone builds on:

| Existing Asset | Location | Status |
|---|---|---|
| Performance baselines (30-day pre-publish) | `performance_baselines` table | Working, auto-captured |
| Performance snapshots (post-publish daily) | `performance_snapshots` table with `days_since_publish`, `cohort_type` | Working, captured via API |
| Diff-in-diff impact scores | `performance_impact_scores` table with treated/control, lift %, confidence | Schema exists, needs population |
| Publish events with content snapshots | `publish_events` with `prompt_hash`, `evidence_hash`, `final_payload_hash` | Working, populated on publish |
| Regeneration history with prompt tracking | `regeneration_history` with `prompt_hash`, quality before/after, feature flags | Working |
| Prompt version aliases | `prompt_version_aliases` mapping hash to human name | Schema exists |
| Search query snapshots (post-publish delta) | `search_query_snapshots` with `publish_event_id`, `days_since_publish` | Schema exists, FK to publish_events |
| SKU bottleneck classifications | `sku_bottleneck_classifications` | Schema exists |
| service.ts live Google Ads queries | 6 parallel GAQL queries, 2-min cache | Working but ephemeral |
| Optimization control plane (033) | `query_value_scores`, `routing_recommendations`, `opportunity_clusters`, `query_intent_features` | Tables exist, EMPTY (hardcoded thresholds produce zero matches) |
| Intent execution system (035b DEFERRED) | 14 tables for policy, experiments, negatives, margins | Migration file exists, NOT applied to production |
| GA4 attribution forensics (034b DEFERRED) | 4 GA4 tables for source/medium, landing pages, attribution | Migration file exists, NOT applied, NO code references |
| Intent TypeScript code | 32 files in `dashboard/src/lib/intent/` | Code exists, dead (no backing tables) |
| Auto data collection | `ensureBaselineData()`, `ensureSkuData()` in ensure-data.ts | Working, triggers on SKU selection/regen |

---

## Table Stakes

Features this milestone MUST deliver. Without these, v1.3c (Actionable Intelligence) and v1.4 (Closed-Loop Optimization) cannot be built.

| Feature | Why Expected | Complexity | Dependencies | Notes |
|---------|-------------|------------|--------------|-------|
| Content-performance feedback view/table | The ONLY missing link between "what content was published" and "how it performed." publish_events has prompt_hash, performance_snapshots has CTR/CVR, but nothing joins them. v1.4 cannot exist without this. | Medium | `publish_events`, `performance_snapshots`, `regeneration_history` | Materialized view joining publish_events.prompt_hash + performance_snapshots metrics by master_sku/platform/date_range. Include: content text, prompt hash, quality score at publish, baseline CTR/CVR, post-publish CTR/CVR, delta. |
| Deferred migration triage (035b) | 32 TypeScript files reference tables that do not exist. Every intent-related dashboard page is dead. Must decide: apply, prune, or remove before building v1.3c on top of it. | Low (decision) / Medium (execution) | Migration file `035b_DEFERRED`, `dashboard/src/lib/intent/*.ts` | Strategic assessment Part 7 recommends applying 8 of 14 tables. Schema must be verified against TS code expectations before applying. |
| Data flow audit document | No single document maps the complete flow: Google Ads API -> service.ts -> DB -> Dashboard -> Actions -> Google Ads. Dead ends exist (empty optimization tables, orphaned components). Without this map, new features risk building on broken foundations. | Low | All existing tables and code | Output: architecture diagram with every table, every data source, every consumer, marking dead ends. |
| Historical persistence for service.ts tier data | service.ts queries 6 GAQL queries live with 2-minute cache. Zero historical data is persisted from these queries. Cannot build trend analysis, tier movement tracking, or funnel analytics without history. | Medium | `service.ts`, new `funnel_term_daily` table (or similar) | Daily snapshot of search term tier assignments, impressions, clicks, cost, conversions by custom_label_0 and tier. Cloud Scheduler cron job. |
| API quota analysis and sustainability confirmation | service.ts makes 6 GAQL queries per page load. At current usage this works, but scaling to automated daily snapshots adds load. Must confirm quota budget before building persistence. | Low | Google Ads API documentation, current usage patterns | Analysis document confirming: current daily query count, quota limits, projected usage with daily snapshots, caching strategy recommendation. |

---

## Differentiators

Features that elevate the milestone beyond basic plumbing. Not strictly required for v1.3c, but significantly increase the value of the feedback loop.

| Feature | Value Proposition | Complexity | Dependencies | Notes |
|---------|------------------|------------|--------------|-------|
| Content A/B attribution | Track WHICH prompt changes drove CTR improvement. When prompt_hash changes between two publish_events for the same SKU, measure the performance delta. "Prompt X produced 12% higher CTR than Prompt Y for towel bar category." | High | Content-performance feedback view, multiple publish cycles per SKU | Requires at least 2 publish events per SKU with different prompt_hashes AND enough time between them for statistical significance. v1.4 Phase 2 needs this, but the table design belongs in v1.3b. |
| Populate performance_impact_scores | The diff-in-diff scorecard table exists but is empty. Building a compute job that calculates treated vs control lift for published SKUs would make the Performance page actionable instead of placeholder. | Medium | `performance_snapshots` (populated), `performance_baselines`, `publish_events` | Compute job: for each publish_event, find treated pre/post windows, match control cohort by category, calculate lift. Write to performance_impact_scores. |
| Populate search_query_snapshots after publish | The table exists with FK to publish_events and days_since_publish column, but nothing writes to it. Populating it enables "which search terms gained/lost impressions after we changed the description?" | Medium | `search_query_snapshots` schema, `publish_events`, search term sync pipeline | Cloud Scheduler job or post-publish hook: capture search query metrics at publish time and at 7/14/30-day intervals. |
| Empty optimization table cleanup | `query_value_scores`, `routing_recommendations`, `opportunity_clusters`, `query_intent_features` are empty because hardcoded thresholds match nothing. Either populate with simple distribution-based scoring OR drop and redesign for v1.3c. | Low-Medium | Migration 033 tables, optimization TypeScript code | Recommendation: do NOT populate with hardcoded scoring. Mark tables as "v1.3c will populate with distribution-based scoring." Document the decision. Avoids wasted work. |
| Orphaned component surfacing | GmcDisapprovalBadge and PromptLineagePanel exist but are not in any page. Either wire them into the dashboard or remove them. | Low | Component code, dashboard pages | Low effort, high tidiness value. PromptLineagePanel is particularly useful for content-performance feedback visibility. |

---

## Anti-Features

Features to explicitly NOT build in this milestone.

| Anti-Feature | Why Avoid | What to Do Instead |
|--------------|-----------|-------------------|
| Real-time streaming from Google Ads | Massive overengineering. Daily batch collection is sufficient for all analytics needs. Google Ads data only updates daily anyway. | Daily Cloud Scheduler snapshot job for funnel term data. |
| Apply ALL 18 deferred tables blindly | 034b (GA4 attribution, 4 tables) has ZERO code references. 035b has 6 "nice-to-have" tables with no clear consumer. Applying unused tables adds maintenance burden and cognitive overhead. | Apply only the 8 tables from 035b that have TypeScript consumers AND are prerequisites for v1.3c. Explicitly defer 034b with documented reasoning. |
| Distribution-based scoring for optimization tables | This is v1.3c Phase 1's entire scope. Doing it in v1.3b would be scope creep and would duplicate work. | Document that optimization tables will be populated in v1.3c. Keep tables empty but validated. |
| Automated content regeneration based on performance | This is v1.4 Phase 1. The feedback loop data must exist before automated actions can use it. | Build the data layer (feedback view, historical persistence) in v1.3b. Let v1.4 build the automation. |
| GA4 data pipeline | 034b tables exist for GA4 attribution forensics but no code references them, no pipeline exists to populate them, and Google Ads data already covers the primary use case (Shopping campaign performance). | Defer 034b. If GA4 attribution debugging is needed later, it can be a focused mini-milestone. |
| Full experiment framework | experiment_registry/assignments/outcomes tables are designed for A/B testing infrastructure that requires significant UI and logic. Not needed until v1.3c Phase 3 at earliest. | Apply the 3 experiment tables (they are low-cost) but do NOT build UI or populate them. |
| Multi-account Google Ads support | Single account (6253381786). No business need for multi-account. | Keep single-account architecture. |

---

## Feature Dependencies

```
Data Flow Audit Document
  |
  v
API Quota Analysis -----> Historical Persistence (funnel_term_daily)
  |                              |
  v                              v
Deferred Migration Triage --> Apply 035b subset
  |                              |
  v                              v
Content-Performance Feedback View <-- publish_events + performance_snapshots
  |
  v
[v1.3c] Distribution-based scoring populates optimization tables
  |
  v
[v1.4] Content A/B attribution, automated regeneration
```

**Critical path:** Data Flow Audit -> Migration Triage -> Feedback View -> Historical Persistence

The audit must come first because it reveals which tables actually have data, which are dead, and which connections are missing. Migration triage depends on the audit findings. The feedback view can be built in parallel with historical persistence since they use different data sources.

---

## MVP Recommendation

**Phase 1 (Architecture Audit):**
1. Data flow audit document (table stakes, Low complexity)
2. API quota analysis (table stakes, Low complexity)
3. Deferred migration triage decision (table stakes, Low complexity for decision)

**Phase 2 (Critical Schema Updates):**
1. Apply 035b subset -- 8 prerequisite tables (table stakes, Medium complexity)
2. Content-performance feedback materialized view (table stakes, Medium complexity)
3. Historical persistence table + daily snapshot job (table stakes, Medium complexity)

**Phase 3 (Validation and Cleanup):**
1. Populate performance_impact_scores (differentiator, Medium)
2. Populate search_query_snapshots (differentiator, Medium)
3. Wire orphaned components or remove them (differentiator, Low)
4. End-to-end data flow validation: verify no dead ends remain

**Defer to v1.3c:**
- Distribution-based scoring for optimization tables
- Full experiment framework UI

**Defer to v1.4:**
- Content A/B attribution analysis
- Automated regeneration based on performance

**Defer indefinitely:**
- 034b GA4 attribution tables (no code references, no clear need)

---

## Detailed Feature Specifications

### Content-Performance Feedback View

**Purpose:** The missing link. Joins content generation decisions to their measured outcomes.

**Data sources (all existing):**
- `publish_events`: master_sku, platform, published_at, prompt_hash, evidence_hash, quality_score, published_title, published_description
- `performance_baselines`: avg_ctr, avg_cvr, avg_impressions (pre-publish)
- `performance_snapshots`: ctr, cvr, impressions, days_since_publish (post-publish)
- `regeneration_history`: prompt_hash, feedback_text, quality_score_before/after

**Output schema (materialized view or computed table):**
```
content_performance_feedback:
  master_sku text
  platform text
  publish_event_id bigint
  published_at timestamptz
  prompt_hash text
  prompt_alias text (from prompt_version_aliases)
  quality_score_at_publish real
  published_title text
  published_description text
  baseline_ctr real
  baseline_cvr real
  baseline_impressions real
  post_7d_ctr real
  post_7d_cvr real
  post_7d_impressions real
  post_30d_ctr real
  post_30d_cvr real
  post_30d_impressions real
  ctr_delta_7d real
  cvr_delta_7d real
  ctr_delta_30d real
  cvr_delta_30d real
```

**Complexity:** Medium -- the join logic is straightforward but requires careful handling of:
- Multiple publish events per SKU (use most recent)
- Missing baselines (SKUs published without baseline capture)
- Insufficient post-publish data (< 7 days since publish)
- Multi-SKU products sharing product_id in Google Ads

### Historical Persistence (Funnel Term Daily)

**Purpose:** Persist the ephemeral service.ts GAQL data so trend analysis and tier movement tracking become possible.

**What service.ts queries (6 parallel GAQL queries):**
1. Enabled shopping campaigns (campaign.id, campaign.name)
2. Enabled shopping ad groups (campaign.name, ad_group.id, ad_group.name)
3. Negative shared sets (shared_set.id, shared_set.name)
4. Campaign negative keywords (campaign.name, keyword.text, match_type)
5. Ad group negative keywords (campaign.name, ad_group.name, keyword.text, match_type)
6. Shopping search terms with metrics (campaign.name, ad_group.name, search_term, impressions, clicks, cost_micros, conversions, conversions_value)

**What to persist (query 6 is the high-value target):**
```
funnel_term_daily:
  id bigint
  snapshot_date date
  search_term text
  custom_label_0 text
  source_tier text (HIGH/MEDIUM/LOW, parsed from campaign name)
  impressions integer
  clicks integer
  cost_micros bigint
  conversions numeric
  conversions_value numeric
  ctr numeric
  cvr numeric
  fetched_at timestamptz
```

**Collection method:** Cloud Scheduler daily cron -> Cloud Run endpoint or Vercel cron that calls a dedicated snapshot function. NOT from service.ts (which is a dashboard page handler), but from a dedicated data collection pipeline.

**Complexity:** Medium -- requires new table, new collection endpoint, Cloud Scheduler setup. The GAQL query already exists in service.ts and can be extracted.

### Migration Triage (035b)

**8 tables to APPLY (prerequisites for v1.3c per strategic assessment Part 7):**
1. `intent_taxonomy_versions` -- policy version management
2. `term_intent_state` -- intent classification per term
3. `policy_decision_log` -- policy evaluation audit trail
4. `policy_action_execution_log` -- execution action audit trail
5. `experiment_registry` -- experiment definitions
6. `experiment_assignments` -- term-to-experiment cohort assignments
7. `experiment_outcomes` -- experiment results
8. `negative_registry` -- negative keyword governance with rollback

**6 tables to DEFER (nice-to-have, no clear consumer in v1.3c):**
1. `policy_snapshots` -- point-in-time snapshots (no TS consumer identified)
2. `sku_margin_daily` -- requires Shopify margin data pipeline that does not exist
3. `order_line_returns_daily` -- requires Shopify returns data pipeline that does not exist
4. `attribution_confidence_daily` -- complex attribution quality scoring, premature
5. `search_buildout_recommendations` -- can be created when search governance is built
6. `operator_review_audit` -- audit trail for human review, premature

**Before applying:** Verify that the 8 table schemas match what the 32 TypeScript files in `dashboard/src/lib/intent/` expect. Look for column name mismatches, missing columns, type mismatches.

**4 tables from 034b to DEFER indefinitely:**
- `ga4_source_medium_daily`, `ga4_landing_page_quality_daily`, `ga4_attribution_root_cause_daily`, `ga4_shopify_reconciliation_daily`
- Reason: No code references, no data pipeline, Google Ads data covers primary use case

---

## Sources

All findings based on local codebase review:
- `/Users/bobby/Documents/GitHub/Allied-FeedOps/docs/database/SCHEMA.md` -- complete schema reference
- `/Users/bobby/Documents/GitHub/Allied-FeedOps/docs/plans/2026-02-21-strategic-milestone-assessment.md` -- Part 7 migration analysis
- `/Users/bobby/Documents/GitHub/Allied-FeedOps/.planning/PROJECT.md` -- current state and roadmap
- `/Users/bobby/Documents/GitHub/Allied-FeedOps/supabase/migrations/035b_DEFERRED_unified_intent_execution_system.sql` -- 14 table definitions
- `/Users/bobby/Documents/GitHub/Allied-FeedOps/supabase/migrations/034b_DEFERRED_ga4_attribution_forensics.sql` -- 4 GA4 table definitions
- `/Users/bobby/Documents/GitHub/Allied-FeedOps/supabase/migrations/033_optimization_control_plane.sql` -- optimization tables
- `/Users/bobby/Documents/GitHub/Allied-FeedOps/dashboard/src/lib/shopping-funnel/service.ts` -- 6 GAQL queries, 2-min cache
- `/Users/bobby/Documents/GitHub/Allied-FeedOps/dashboard/src/lib/data-collection/ensure-data.ts` -- auto data collection
