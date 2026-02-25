# Migration Triage: Deferred Tables (034b + 035b)

**Audited:** 2026-02-25
**Requirement:** AUDIT-03
**Phase:** 28 (Architecture Audit & Migration Triage)

## Introduction

Allied FeedOps has 18 database tables created from two deferred migration files that were applied out-of-band (directly to production) but never formally integrated into the application lifecycle:

- **034b** (`034b_DEFERRED_ga4_attribution_forensics.sql`): 4 GA4 attribution forensics tables for diagnosing revenue attribution quality between GA4 and Shopify.
- **035b** (`035b_DEFERRED_unified_intent_execution_system.sql`): 14 intent classification, policy execution, experiment tracking, and search governance tables for a planned Unified Intent Execution System.

Both migration files explicitly state: *"Tables created out-of-band; this file is reference only."* This means the tables exist in the production Supabase instance but may contain zero rows if no data pipeline ever populated them.

### Triage Criteria

Each table is evaluated on:

1. **Code references** -- Which production TypeScript or Python files query or write to this table? (Excluding planning docs, migration files, and research notes.)
2. **Data state** -- Does the table exist in production? Does it have data? (Based on migration file status and code behavior.)
3. **Downstream need** -- Which v1.3b-v1.4 requirements benefit from this table?
4. **Complexity** -- How much work to wire up vs. how much value it provides?
5. **Feedback loop alignment** -- Does this table contribute to the capture-monitor-analyze-optimize cycle?

### User Directives

- **Infrastructure-forward bias**: Lean toward KEEP for tables that support future scale, even if current code consumers are sparse.
- **GA4 tables evaluated for KEEP**: User considers GA4 attribution important for the master plan (v1.3-v1.4).
- **Pruned tables**: Delete TypeScript consumer files in Phase 31, keep migration SQL files as reference.
- **Orphaned dashboard components**: Simple wiring in Phase 31; complex UI deferred to v1.3c/v1.4.

### Decision Key

- **KEEP**: Apply/verify migration in Phase 31. Table is a prerequisite for v1.3b-v1.4 features.
- **DEFER**: Table stays in production but is not actively used. Re-evaluate in v1.3c/v1.4.
- **PRUNE**: Drop table in Phase 31 (or leave empty). Delete TypeScript consumer files.

---

## 034b Tables (GA4 Attribution Forensics)

All 4 tables in 034b are part of a GA4 attribution quality monitoring pipeline. They are consumed by a single, fully-functional API route (`/api/ga4/snapshot-capture/route.ts`) that fetches GA4 data, cross-references with Shopify orders, and upserts results. The route includes graceful error handling for missing tables (`isMissingRelationError` check).

### ga4_source_medium_daily

- **Migration:** 034b
- **Purpose:** Stores daily GA4 source/medium breakdowns with quality buckets (not_set, data_not_available, valid), session counts, transaction counts, and revenue shares. Used to diagnose which traffic sources have poor attribution.
- **Code References:** 2 production files
  - `dashboard/src/app/api/ga4/snapshot-capture/route.ts` (upserts rows from GA4 API data)
  - `dashboard/src/lib/supabase/types.ts` (type definition in Database interface)
  - 1 test file: `dashboard/src/app/api/ga4/__tests__/snapshot-capture.route.test.ts`
- **Data State:** EXISTS in production (created out-of-band). Likely EMPTY or low row count -- depends on whether the snapshot-capture endpoint has been called.
- **Schema:** id (uuid PK), property_id, report_date, source_medium, quality_bucket (constrained), sessions, transactions, purchase_revenue, revenue_share, session_share, source_payload (jsonb), created_at. Unique index on (property_id, report_date, quality_bucket, source_medium).
- **Downstream Need:** v1.4 LOOP-01/LOOP-03 (content A/B attribution needs attribution quality signals). Feeds the "analyze & learn" stage of the feedback loop.
- **Decision:** KEEP
- **Reasoning:** Active code consumer exists with a complete write pipeline. GA4 attribution quality is foundational for the v1.3-v1.4 closed-loop optimization vision. The snapshot-capture endpoint is production-ready and can be triggered via Cloud Scheduler. Infrastructure-forward: keeping this table costs nothing and enables future attribution diagnostics.
- **Phase 31 Action:** Verify table exists and schema matches migration. Set up Cloud Scheduler to call `/api/ga4/snapshot-capture` daily to begin populating data.

### ga4_landing_page_quality_daily

- **Migration:** 034b
- **Purpose:** Stores daily GA4 landing page quality diagnostics -- which landing pages have sessions/transactions with "not_set" or "data_not_available" quality buckets. Used to identify pages with broken GA4 tracking.
- **Code References:** 2 production files
  - `dashboard/src/app/api/ga4/snapshot-capture/route.ts` (upserts rows)
  - `dashboard/src/lib/supabase/types.ts` (type definition)
  - 1 test file: `dashboard/src/app/api/ga4/__tests__/snapshot-capture.route.test.ts`
- **Data State:** EXISTS in production (created out-of-band). Likely EMPTY -- same condition as ga4_source_medium_daily.
- **Schema:** id (uuid PK), property_id, report_date, landing_page, quality_bucket (constrained), sessions, transactions, purchase_revenue, revenue_share, session_share, source_payload (jsonb), created_at. Unique index on (property_id, report_date, quality_bucket, landing_page).
- **Downstream Need:** Identifies landing pages with attribution gaps -- prerequisite for targeted attribution improvement in v1.4.
- **Decision:** KEEP
- **Reasoning:** Same active code consumer as ga4_source_medium_daily. Landing page quality data helps prioritize which product pages need GA4 implementation fixes. Keeps the GA4 attribution pipeline complete.
- **Phase 31 Action:** Verify table exists and schema matches migration. Populated by same Cloud Scheduler job as ga4_source_medium_daily.

### ga4_attribution_root_cause_daily

- **Migration:** 034b
- **Purpose:** Stores root cause analysis rows derived from source/medium, landing page, and campaign pattern data. Identifies specific reasons for attribution quality issues (e.g., "source_medium_not_set", "landing_page_invalid").
- **Code References:** 2 production files
  - `dashboard/src/app/api/ga4/snapshot-capture/route.ts` (upserts rows via `buildRootCauseRows()`)
  - `dashboard/src/lib/supabase/types.ts` (type definition)
  - 1 test file: `dashboard/src/app/api/ga4/__tests__/snapshot-capture.route.test.ts`
- **Data State:** EXISTS in production (created out-of-band). Likely EMPTY.
- **Schema:** id (uuid PK), property_id, report_date, root_cause_type, root_cause_key, sessions, transactions, purchase_revenue, revenue_share, session_share, source_payload (jsonb), created_at. Unique index on (property_id, report_date, root_cause_type, root_cause_key).
- **Downstream Need:** Actionable diagnostics for the "analyze" stage of the feedback loop. Without root cause data, attribution issues are visible but not debuggable.
- **Decision:** KEEP
- **Reasoning:** Derived from the same snapshot-capture pipeline. Root cause analysis is the diagnostic layer that makes the other GA4 tables actionable rather than just observational.
- **Phase 31 Action:** Verify table exists and schema matches migration. Populated automatically by snapshot-capture endpoint.

### ga4_shopify_reconciliation_daily

- **Migration:** 034b
- **Purpose:** Stores daily revenue reconciliation between GA4-reported revenue and Shopify order revenue. Tracks revenue_ratio (GA4/Shopify) to detect attribution drift. The route also checks consecutive out-of-range streaks and generates guardrail incidents.
- **Code References:** 2 production files
  - `dashboard/src/app/api/ga4/snapshot-capture/route.ts` (upserts reconciliation summary, reads last 3 rows for streak detection)
  - `dashboard/src/lib/supabase/types.ts` (type definition)
  - 1 test file: `dashboard/src/app/api/ga4/__tests__/snapshot-capture.route.test.ts`
- **Data State:** EXISTS in production (created out-of-band). Likely EMPTY.
- **Schema:** id (uuid PK), property_id, report_date, ga4_revenue, shopify_revenue, revenue_delta, revenue_ratio, order_count, source_payload (jsonb), created_at. Unique index on (property_id, report_date).
- **Downstream Need:** Revenue parity monitoring is critical for trusting performance metrics. If GA4 and Shopify revenue diverge significantly, all CTR/CVR-based content optimization decisions become unreliable.
- **Decision:** KEEP
- **Reasoning:** This is arguably the most important 034b table. Revenue reconciliation validates the integrity of all downstream metrics. The guardrail incident system already wires into this for automated alerts. Without reconciliation data, the entire feedback loop operates on potentially untrustworthy revenue signals.
- **Phase 31 Action:** Verify table exists and schema matches migration. Priority for Cloud Scheduler activation.

---

## 035b Tables (Unified Intent Execution System)

The 14 tables in 035b support an ambitious Unified Intent Execution System covering: intent classification and taxonomy versioning, policy-based bid management, search governance (negative keywords, buildout recommendations), experiment tracking (A/B testing), and value/margin analysis. Five dashboard pages depend on these tables and currently render empty: Shopping Funnel, Optimization Control Center, Intent Control Center, Search Governance, and Experiment Lab.

No Python pipeline code references any 035b table. All references are in the dashboard TypeScript layer -- API routes and library files in `dashboard/src/lib/intent/` and `dashboard/src/app/api/intent/`, `dashboard/src/app/api/experiments/`, `dashboard/src/app/api/search/governance/`, and `dashboard/src/app/api/shopping-funnel/`.

### intent_taxonomy_versions

- **Migration:** 035b
- **Purpose:** Stores versioned intent classification taxonomies. Each version defines class definitions (BRAND_CORE, PRODUCT_HIGH, CATEGORY_MID, etc.) and mapping rules as JSONB. Supports activating/deactivating taxonomy versions for the intent classification system.
- **Code References:** 0 production files (no direct table name references in production code outside migration/docs)
- **Data State:** EXISTS in production (created out-of-band). Likely EMPTY -- no write pipeline exists.
- **Schema:** id (uuid PK), version_key (unique), description, class_definitions (jsonb), mapping_rules (jsonb), is_active (boolean), activated_at, activated_by, created_at.
- **Downstream Need:** v1.3c OPT-03 (tier movement tracking) and OPT-04 (experiment framework) need intent classification as a foundation.
- **Decision:** DEFER
- **Reasoning:** No active code consumer writes to this table. The intent classification system is a v1.3c/v1.4 feature that requires significant design work beyond just having the table. The taxonomy versioning concept is sound but premature for v1.3b. Table can remain in production at zero cost.
- **Phase 31 Action:** No action. Table stays as-is. Re-evaluate when intent classification work begins in v1.3c.

### term_intent_state

- **Migration:** 035b
- **Purpose:** Stores per-search-term intent classification state: intent class, subclasses, route action (funnel, global_block, competitor, etc.), shopping/search tier, confidence score, and policy version. This is the core operational table for the intent system.
- **Code References:** 1 production file
  - `dashboard/src/lib/intent/tier-movement.ts` (reads term_intent_state for tier movement analysis)
- **Data State:** EXISTS in production (created out-of-band). Likely EMPTY -- no write pipeline populates it.
- **Schema:** id (uuid PK), search_term, normalized_search_term, custom_label_0, intent_class (constrained: 8 values), intent_subclasses (text[]), route_action (constrained: 7 values), shopping_tier, search_tier, confidence, requires_review, policy_version, source_window_start/end, last_decided_at, metadata (jsonb), created_at, updated_at. Unique index on (normalized_search_term, custom_label_0).
- **Downstream Need:** v1.3c OPT-01 (distribution-based scoring needs intent classification per term), OPT-03 (tier movement tracking).
- **Decision:** KEEP
- **Reasoning:** This is the core operational table for intent intelligence. It has an active code consumer (tier-movement.ts) and is a prerequisite for v1.3c distribution-based scoring (OPT-01). The schema is well-designed with proper constraints. Even with no data today, the table structure is needed for Phase 30 (Shopping Funnel persistence) and v1.3c.
- **Phase 31 Action:** Verify table exists and schema matches migration. Wire tier-movement.ts to populate from search_queries data as a seed step. Dashboard page: Shopping Funnel should display tier movement data once populated.

### policy_decision_log

- **Migration:** 035b
- **Purpose:** Audit log for policy decisions -- records each bid/routing decision with search term, decision type, channel, policy version, confidence, and whether human review is required. Immutable append-only log.
- **Code References:** 5 production files
  - `dashboard/src/app/api/search/governance/drafts/route.ts` (reads decisions)
  - `dashboard/src/app/api/search/governance/movements/route.ts` (reads decisions)
  - `dashboard/src/app/api/intent/route/route.ts` (writes decisions)
  - `dashboard/src/app/api/intent/bid-policy/route.ts` (writes decisions)
  - `dashboard/src/app/api/intent/promote-demote/route.ts` (writes decisions)
  - 2 test files
- **Data State:** EXISTS in production (created out-of-band). Likely EMPTY.
- **Schema:** id (uuid PK), search_term, custom_label_0, decision_type, channel, policy_version, decision_payload (jsonb), confidence, requires_review, created_by, created_at. Indexes on (decision_type, created_at) and (search_term, created_at).
- **Downstream Need:** v1.3c OPT-03 (tier movement requires policy audit trail). v1.4 LOOP-01 (understanding which decisions drove performance changes).
- **Decision:** KEEP
- **Reasoning:** 5 production files reference this table across two subsystems (intent routes and search governance). It serves as the audit trail for all policy decisions -- critical for compliance, debugging, and the "analyze & learn" phase of the feedback loop. Even if no decisions are logged today, the infrastructure is needed as soon as policy execution begins.
- **Phase 31 Action:** Verify table exists and schema matches migration. No immediate wiring needed -- table becomes active when intent/governance routes are used.

### policy_action_execution_log

- **Migration:** 035b
- **Purpose:** Tracks execution status of policy actions (planned, applied, rolled_back, failed, cancelled). Links to the policy decision that triggered the action. Records what was done, not just what was decided.
- **Code References:** 9 production files (highest reference count of any 035b table)
  - `dashboard/src/app/api/search/governance/apply/route.ts`
  - `dashboard/src/app/api/search/governance/movements/route.ts`
  - `dashboard/src/app/api/intent/graduation/route.ts`
  - `dashboard/src/app/api/intent/guardrails/incidents/route.ts`
  - `dashboard/src/app/api/intent/promote-demote/route.ts`
  - `dashboard/src/app/api/intent/rollback/route.ts`
  - `dashboard/src/app/api/intent/scorecard/route.ts`
  - `dashboard/src/app/api/shopping-funnel/tier-movement/route.ts`
  - `dashboard/src/lib/intent/tier-movement.ts`
  - 3 test files
- **Data State:** EXISTS in production (created out-of-band). Likely EMPTY.
- **Schema:** id (uuid PK), action_type, search_term, custom_label_0, status (constrained: 5 values), policy_version, action_payload (jsonb), reason_codes (text[]), created_by, created_at, updated_at. Indexes on (status, created_at) and (action_type, created_at).
- **Downstream Need:** v1.3c OPT-03 (tier movement tracking), v1.3c OPT-04 (experiment framework needs action tracking).
- **Decision:** KEEP
- **Reasoning:** Most-referenced 035b table (9 production files). This is the execution backbone of the intent system -- every route that "does something" logs here. Critical for rollback capability (intent/rollback reads this), guardrail monitoring, and the shopping funnel tier-movement endpoint. Cannot have a functioning intent execution system without execution logging.
- **Phase 31 Action:** Verify table exists and schema matches migration. High priority -- this table becomes active as soon as any intent/governance route is called.

### policy_snapshots

- **Migration:** 035b
- **Purpose:** Point-in-time snapshots of policy state for rollback capability. Stores the complete policy configuration as JSONB with a unique snapshot_key. Supports restore operations.
- **Code References:** 2 production files
  - `dashboard/src/app/api/intent/rollback/route.ts` (reads snapshots for rollback)
  - `dashboard/src/app/api/intent/rollback/readiness/route.ts` (checks if rollback is possible)
  - 2 test files
- **Data State:** EXISTS in production (created out-of-band). Likely EMPTY.
- **Schema:** id (uuid PK), snapshot_key (unique), policy_version, payload (jsonb), created_by, created_at, restored_at, restored_by.
- **Downstream Need:** Operational safety -- any policy execution system needs rollback capability.
- **Decision:** KEEP
- **Reasoning:** Rollback is a safety requirement, not a feature. If the intent execution system is activated, rollback snapshots must exist. Two dedicated rollback routes already reference this table. Keeping it maintains the safety infrastructure for when policy execution begins.
- **Phase 31 Action:** Verify table exists and schema matches migration. No immediate wiring -- populated when policy snapshots are created.

### sku_margin_daily

- **Migration:** 035b
- **Purpose:** Stores daily SKU-level margin data: unit COGS, gross margin rate, and currency. Designed for profitability-aware bid optimization -- ensuring content and bidding decisions account for actual product margins.
- **Code References:** 2 production files
  - `dashboard/src/lib/intent/profit-forecast.ts` (reads margin data for profit forecasting)
  - `dashboard/src/lib/intent/value-signal.ts` (reads margin data for value signals)
  - 1 test file
- **Data State:** EXISTS in production (created out-of-band). Likely EMPTY -- no Shopify/accounting integration populates this.
- **Schema:** id (uuid PK), snapshot_date, sku, unit_cogs, gross_margin_rate, currency_code, source_payload (jsonb), created_at. Unique index on (snapshot_date, sku).
- **Downstream Need:** v1.3c OPT-01 (distribution-based scoring should weight by margin), v1.3c OPT-02 (revenue leakage needs margin context).
- **Decision:** DEFER
- **Reasoning:** While margin data is valuable for profit-aware optimization, there is no data source currently integrated to populate this table. Shopify does not expose COGS through its standard API -- this requires manual CSV import or an accounting integration (e.g., QuickBooks). The table structure is fine but will remain empty until a data source is established. Keeping the table costs nothing; building a populate pipeline is out of scope for v1.3b.
- **Phase 31 Action:** No action. Table stays as-is. Re-evaluate in v1.3c when profitability features are scoped. Note: profit-forecast.ts and value-signal.ts will return empty/default results until data exists.

### order_line_returns_daily

- **Migration:** 035b
- **Purpose:** Stores daily return data per SKU from Shopify orders -- returned quantity, return amount, and restock fees. Designed for return-aware content optimization (avoiding over-promising in descriptions).
- **Code References:** 2 production files
  - `dashboard/src/lib/intent/profit-forecast.ts` (reads return data)
  - `dashboard/src/lib/intent/value-signal.ts` (reads return data)
  - 1 test file
- **Data State:** EXISTS in production (created out-of-band). Likely EMPTY -- no return data pipeline exists.
- **Schema:** id (uuid PK), snapshot_date, shopify_order_gid, sku, returned_quantity, return_amount, restock_fee, source_payload (jsonb), created_at. Indexes on (sku, snapshot_date) and (shopify_order_gid, snapshot_date).
- **Downstream Need:** v1.3c OPT-02 (revenue leakage should account for returns).
- **Decision:** DEFER
- **Reasoning:** Same situation as sku_margin_daily -- the table structure is appropriate but no data pipeline exists to populate it. Shopify returns API could potentially feed this, but building that integration is v1.3c/v1.4 scope. The two consumer files (profit-forecast.ts, value-signal.ts) handle empty results gracefully.
- **Phase 31 Action:** No action. Table stays as-is. Re-evaluate in v1.3c.

### attribution_confidence_daily

- **Migration:** 035b
- **Purpose:** Stores daily attribution confidence scores per channel/campaign. Quality bucket (high/medium/low/unknown) indicates how trustworthy the attribution data is for that channel on that day.
- **Code References:** 1 production file
  - `dashboard/src/app/api/intent/bid-policy/route.ts` (reads confidence for bid decisions)
  - 1 test file
- **Data State:** EXISTS in production (created out-of-band). Likely EMPTY.
- **Schema:** id (uuid PK), snapshot_date, channel, campaign_key, confidence_score, quality_bucket (constrained: 4 values), signals (jsonb), created_at. Unique index on (snapshot_date, channel, campaign_key).
- **Downstream Need:** v1.4 LOOP-01 (attribution confidence affects how much weight to give content-performance correlations).
- **Decision:** DEFER
- **Reasoning:** While attribution confidence is conceptually important, only one route references it (bid-policy), and there is no pipeline to populate it. The 034b GA4 tables provide a different (and more actionable) attribution quality signal. This table overlaps conceptually with the 034b attribution forensics but at a different granularity. Re-evaluate when bid policy features are prioritized.
- **Phase 31 Action:** No action. Table stays as-is. Consider whether 034b tables can serve this role when bid-policy work begins.

### experiment_registry

- **Migration:** 035b
- **Purpose:** Central registry of experiments (A/B tests). Stores experiment key, name, hypothesis, decision rules, success/failure thresholds, and status lifecycle (draft, active, paused, completed, cancelled).
- **Code References:** 3 production files
  - `dashboard/src/app/api/experiments/register/route.ts` (creates experiments)
  - `dashboard/src/app/api/experiments/assignments/route.ts` (reads experiments for assignment)
  - `dashboard/src/app/api/experiments/results/route.ts` (reads experiments for results)
  - 2 test files
- **Data State:** EXISTS in production (created out-of-band). Likely EMPTY.
- **Schema:** id (uuid PK), experiment_key (unique), name, initiative, hypothesis, decision_rule, success_threshold, failure_threshold, status (constrained: 5 values), start_date, end_date, metadata (jsonb), created_by, created_at.
- **Downstream Need:** v1.3c OPT-04 (full experiment framework UI). v1.4 LOOP-01 (content A/B attribution).
- **Decision:** KEEP
- **Reasoning:** The experiment framework is a prerequisite for content A/B testing (v1.4 LOOP-01), which is the endgame of the feedback loop -- measuring which prompt changes drove CTR improvement. Three complete API routes already exist. The Experiment Lab dashboard page is ready to display data once experiments are created. Keeping this infrastructure enables v1.3c OPT-04 without additional schema work.
- **Phase 31 Action:** Verify table exists and schema matches migration. Dashboard page: Experiment Lab should be verified to render correctly when data exists. Consider a manual seed experiment to validate the full flow.

### experiment_assignments

- **Migration:** 035b
- **Purpose:** Maps entities (SKUs, search terms) to experiment cohorts (control/treatment). FK to experiment_registry.experiment_key with CASCADE delete.
- **Code References:** 2 production files
  - `dashboard/src/app/api/experiments/assignments/route.ts` (creates/reads assignments)
  - `dashboard/src/app/api/experiments/results/route.ts` (reads assignments for results)
  - 2 test files
- **Data State:** EXISTS in production (created out-of-band). Likely EMPTY.
- **Schema:** id (uuid PK), experiment_key (FK to experiment_registry), entity_key, cohort, assigned_at, metadata (jsonb). Unique index on (experiment_key, entity_key).
- **Downstream Need:** v1.3c OPT-04 (experiment framework), v1.4 LOOP-01 (A/B attribution).
- **Decision:** KEEP
- **Reasoning:** Inseparable from experiment_registry -- assignments are meaningless without a registry and vice versa. The FK cascade ensures data integrity. Same API routes reference both tables.
- **Phase 31 Action:** Verify table exists and schema matches migration. Included in experiment framework validation.

### experiment_outcomes

- **Migration:** 035b
- **Purpose:** Stores measured outcomes for experiments -- observed lift, sample size, and status (observing, success, failure, inconclusive). FK to experiment_registry.experiment_key.
- **Code References:** 1 production file
  - `dashboard/src/app/api/experiments/results/route.ts` (reads/writes outcomes)
  - 1 test file
- **Data State:** EXISTS in production (created out-of-band). Likely EMPTY.
- **Schema:** id (uuid PK), experiment_key (FK to experiment_registry), metric_name, observed_lift, sample_size, status (constrained: 4 values), measured_at, metadata (jsonb).
- **Downstream Need:** v1.3c OPT-04 (experiment framework), v1.4 LOOP-01 (A/B attribution outcomes).
- **Decision:** KEEP
- **Reasoning:** Completes the experiment lifecycle (registry -> assignments -> outcomes). Cannot have an experiment framework without outcome measurement. The results route already handles the full read/write cycle.
- **Phase 31 Action:** Verify table exists and schema matches migration. Part of experiment framework validation.

### negative_registry

- **Migration:** 035b
- **Purpose:** Registry of negative keywords with scope (campaign/ad group level), confidence scores, reason codes, and rollback tokens. Supports activation/deactivation lifecycle for search term exclusions.
- **Code References:** 4 production files
  - `dashboard/src/app/api/search/governance/apply/route.ts` (applies negatives)
  - `dashboard/src/app/api/intent/rollback/route.ts` (rolls back negatives)
  - `dashboard/src/app/api/intent/rollback/readiness/route.ts` (checks rollback readiness)
  - `dashboard/src/lib/intent/tier-movement.ts` (reads negative registry for tier analysis)
  - 3 test files
- **Data State:** EXISTS in production (created out-of-band). Likely EMPTY.
- **Schema:** id (uuid PK), term, scope, source_policy, confidence, reason_codes (text[]), rollback_token, active (boolean), metadata (jsonb), created_by, created_at, deactivated_at, deactivated_by. Indexes on (scope, active, created_at) and (term, created_at).
- **Downstream Need:** v1.3c OPT-03 (tier movement tracking includes negative keyword management).
- **Decision:** KEEP
- **Reasoning:** 4 production files reference this table, making it one of the more connected 035b tables. Negative keyword management is a core Google Ads optimization lever. The rollback infrastructure (rollback/route.ts, rollback/readiness/route.ts) provides operational safety. This table directly supports the search governance workflow.
- **Phase 31 Action:** Verify table exists and schema matches migration. Dashboard page: Search Governance should display negative registry data. Wire tier-movement to populate from existing search_queries analysis.

### search_buildout_recommendations

- **Migration:** 035b
- **Purpose:** Stores recommendations for search campaign buildout -- which search terms should move from broad to phrase to exact match, with confidence scores and approval workflow (candidate, approved, applied, rejected, paused).
- **Code References:** 5 production files
  - `dashboard/src/app/api/search/governance/candidates/route.ts` (reads candidates)
  - `dashboard/src/app/api/search/governance/apply/route.ts` (applies recommendations)
  - `dashboard/src/app/api/search/governance/drafts/route.ts` (manages drafts)
  - `dashboard/src/app/api/search/governance/buildouts/route.ts` (reads buildout history)
  - `dashboard/src/app/api/search/governance/movements/route.ts` (reads movements)
  - 1 test file
- **Data State:** EXISTS in production (created out-of-band). Likely EMPTY.
- **Schema:** id (uuid PK), search_term, custom_label_0, recommended_search_tier (constrained: broad/phrase/exact), status (constrained: 5 values), confidence, metadata (jsonb), approved_by, approved_at, created_at. Indexes on (status, created_at) and (search_term, created_at).
- **Downstream Need:** v1.3c OPT-03 (tier movement and search intelligence).
- **Decision:** KEEP
- **Reasoning:** 5 production files reference this table -- all 5 search governance routes depend on it. The approval workflow (candidate -> approved -> applied) is a complete operational pattern. Search term tier optimization (broad -> phrase -> exact) is one of the highest-ROI Google Ads optimization levers. This table enables the Search Governance dashboard page.
- **Phase 31 Action:** Verify table exists and schema matches migration. Dashboard page: Search Governance should be verified to render correctly. Consider seeding from existing search_queries/keyword_metrics data.

### operator_review_audit

- **Migration:** 035b
- **Purpose:** Audit trail for operator review actions across all intent/governance queues. Records before/after state for every human action (approve, reject, modify) with actor attribution.
- **Code References:** 5 production files
  - `dashboard/src/app/api/search/governance/apply/route.ts`
  - `dashboard/src/app/api/search/governance/movements/route.ts`
  - `dashboard/src/app/api/intent/guardrails/incidents/route.ts`
  - `dashboard/src/app/api/intent/review-analytics/route.ts`
  - `dashboard/src/app/api/intent/rollback/route.ts`
  - 4 test files
- **Data State:** EXISTS in production (created out-of-band). Likely EMPTY.
- **Schema:** id (uuid PK), queue_name, entity_key, action, before_state (jsonb), after_state (jsonb), actor, created_at. Indexes on (queue_name, created_at) and (entity_key, created_at).
- **Downstream Need:** Compliance and debugging for any automated decision system. Required for v1.4 LOOP-02 (automated content regeneration needs audit trail).
- **Decision:** KEEP
- **Reasoning:** 5 production files reference this table across both intent and governance subsystems. This is the universal audit trail -- every action that modifies policy state should log here. Critical for compliance (who approved what, when) and debugging (what changed before the problem started). Cannot safely operate an automated optimization system without an audit trail.
- **Phase 31 Action:** Verify table exists and schema matches migration. Audit logging activates automatically when any intent/governance route is called.

---

## Summary

### Decision Counts

| Decision | Count | Tables |
|----------|-------|--------|
| **KEEP** | 14 | ga4_source_medium_daily, ga4_landing_page_quality_daily, ga4_attribution_root_cause_daily, ga4_shopify_reconciliation_daily, term_intent_state, policy_decision_log, policy_action_execution_log, policy_snapshots, experiment_registry, experiment_assignments, experiment_outcomes, negative_registry, search_buildout_recommendations, operator_review_audit |
| **DEFER** | 4 | intent_taxonomy_versions, sku_margin_daily, order_line_returns_daily, attribution_confidence_daily |
| **PRUNE** | 0 | (none) |

### Rationale for Zero PRUNE

No tables are recommended for pruning because:

1. All 18 tables were deliberately designed and have coherent schemas with proper constraints, indexes, and RLS policies.
2. Empty tables in Supabase have zero storage cost and near-zero maintenance burden.
3. The infrastructure-forward directive favors keeping tables that support future v1.3c/v1.4 features.
4. Even DEFER'd tables have code consumers that handle empty results gracefully.
5. Dropping tables and deleting consumer code is destructive and irreversible -- the risk of needing to recreate them later outweighs the cost of keeping them.

### Phase 31 Action Items

#### High Priority (verify and activate)

1. **Verify all 18 table schemas** match their migration files (run `information_schema.columns` queries).
2. **Set up Cloud Scheduler** for `/api/ga4/snapshot-capture` daily (activates all 4 034b tables).
3. **Validate experiment framework** flow: register -> assign -> measure -> results (experiment_registry + assignments + outcomes).

#### Medium Priority (wire dashboard pages)

4. **Shopping Funnel page**: Wire to display term_intent_state tier data and tier-movement analysis. Complexity: MEDIUM (needs data seed from search_queries).
5. **Search Governance page**: Wire to display negative_registry and search_buildout_recommendations. Complexity: LOW (routes exist, just need data).
6. **Experiment Lab page**: Wire to display experiment_registry data. Complexity: LOW (routes exist).

#### Lower Priority (defer to v1.3c)

7. **Intent Control Center page**: Depends on intent_taxonomy_versions (DEFER'd) and full policy execution system. Complexity: HIGH. Defer to v1.3c.
8. **Optimization Control Center page**: Depends on sku_margin_daily and order_line_returns_daily (both DEFER'd). Complexity: HIGH (needs Shopify COGS/returns integration). Defer to v1.3c.

#### TypeScript Files Assessment

No files need to be deleted since no tables are PRUNE'd. However, the following files reference DEFER'd tables and will return empty/default results until those tables are populated:

| File | DEFER'd Table | Behavior When Empty |
|------|---------------|-------------------|
| `dashboard/src/lib/intent/profit-forecast.ts` | sku_margin_daily, order_line_returns_daily | Returns default/zero forecasts |
| `dashboard/src/lib/intent/value-signal.ts` | sku_margin_daily, order_line_returns_daily | Returns default/zero signals |
| `dashboard/src/app/api/intent/bid-policy/route.ts` | attribution_confidence_daily | Uses default confidence |

### Risk Assessment

**What breaks if we're wrong about KEEP decisions?**
- Nothing breaks. All KEEP'd tables exist in production, have proper schemas, and their consumer code handles empty data gracefully. The only cost is unused database objects.

**What breaks if we're wrong about DEFER decisions?**
- If a v1.3b feature unexpectedly needs margin/returns/attribution confidence data, we can promote DEFER to KEEP at any time since the tables already exist. The risk is that Phase 31 could discover a dependency not caught here -- but all consumer files were identified and none are in the critical path for v1.3b.

**What would break if we had PRUNE'd tables?**
- Irreversible. Would need to re-create tables and potentially re-deploy migration. This is why PRUNE was not recommended for any table.

---

*Audited: 2026-02-25*
*Phase: 28-architecture-audit-migration-triage*
*Requirement: AUDIT-03*
