# Requirements: Allied-FeedOps v1.1

**Defined:** 2026-03-03
**Core Value:** The pipeline produces high-quality product content reliably at scale, backed by accurate performance data that maps seamlessly across Google Ads, Shopify, and Merchant Center.

## v1 Requirements

Requirements for v1.1 milestone. Each maps to roadmap phases.

### Dead Code

- [ ] **DEAD-01**: Remove 8 orphaned functions with zero callers (`_payload_value_lengths`, `_schema_hash`, `_prompt_hash`, `_generate_with_provider_compat` in generator.py; `_provider_label` re-export in finish_processing.py; 3 finish processing re-exports in generation.py)
- [ ] **DEAD-02**: Update 5 test files to import from actual extracted module locations instead of main.py re-exports
- [ ] **DEAD-03**: Remove ~130-line backward-compat re-export block from main.py after test imports updated
- [ ] **DEAD-04**: Remove generator.py duplicate functions already copied to executor.py/hybrid_generation.py (6 functions)
- [ ] **DEAD-05**: Remove ~500 lines of variant generation code behind never-enabled `FEEDOPS_VARIANT_AT_LLM_TIME` feature flag
- [ ] **DEAD-06**: Consolidate duplicate `_require_request_id()` and `GenerationBudgetExceededError` to single shared location

### Schema

- [x] **SCHM-01**: Add missing unique constraint on `performance_snapshots(master_sku, platform, environment, snapshot_date)` with dedup of existing 179 rows in same migration
- [x] **SCHM-02**: Audit all data import tables for missing or incorrect constraints (performance_baselines, search_queries, keyword_metrics, funnel_snapshots_daily, performance_impact_scores)
- [x] **SCHM-03**: Add CHECK constraints on platform columns across data tables to enforce valid values
- [x] **SCHM-04**: Add FK constraint on `performance_snapshots.publish_event_id` referencing `publish_events`

### Entity Mapping

- [ ] **ENTM-01**: Create shared offer ID normalization utility for case-insensitive matching between DB (lowercase) and GMC (uppercase)
- [ ] **ENTM-02**: Apply offer ID normalization consistently across all data codepaths (performance baselines, search terms, snapshots, backfill)
- [ ] **ENTM-03**: Document entity relationship map showing variant_index as hub linking Google Ads ↔ Shopify ↔ GMC with correct join keys

### Data Coverage

- [ ] **DATA-01**: Implement throttled bulk baseline capture for all ~2,500 master SKUs with Google Ads quota management (50-SKU test gate before full sweep)
- [ ] **DATA-02**: Verify daily snapshot capture works end-to-end after constraint fix — Slack reports success instead of 42P10 error
- [ ] **DATA-03**: Verify impact score population works after snapshots are collecting correctly

### Image Support

- [ ] **IMG-01**: Wire image input through executor.py modern generation path so all per-platform generation endpoints receive product images

## v2 Requirements

Deferred to future milestone. Tracked but not in current roadmap.

### Bing Content Fix

- **BING-01**: Regenerate 96 Bing titles that have hardcoded finish names instead of `{FINISH_NAME}` placeholder
- **BING-02**: Verify variant expansion produces correct finish-specific Bing titles after regeneration

### Data Expansion

- **DEXP-01**: Add Bing/Shopify platform data collection (columns exist, no data)
- **DEXP-02**: Include Performance Max campaigns in search term sync
- **DEXP-03**: Implement product-level search term attribution (currently campaign-level approximation)

### Optimization Loop

- **OPT-01**: Performance-informed regeneration (use post-publish metrics to trigger content updates)
- **OPT-02**: A/B testing framework for generated content

## Out of Scope

| Feature | Reason |
|---------|--------|
| Prompt content rewriting | Phase 27 proved GPT-5.2 hyper-sensitive; now on Claude but incremental only |
| Dashboard UI changes | Pipeline-only milestone |
| v1.3c tier intelligence redesign | PAUSED — separate milestone |
| v1.4 closed-loop optimization | Future milestone — depends on v1.1 data infrastructure |
| Deferred migrations (034b, 035b) | GA4 attribution + intent execution — not yet evaluated |
| optimize.py CLI retirement | Needs explicit decision on whether legacy path is still used |
| New content generation modes | Focus on data reliability before new features |

## Traceability

Which phases cover which requirements. Updated during roadmap creation.

| Requirement | Phase | Status |
|-------------|-------|--------|
| DEAD-01 | Phase 9 | Pending |
| DEAD-02 | Phase 11 | Pending |
| DEAD-03 | Phase 11 | Pending |
| DEAD-04 | Phase 11 | Pending |
| DEAD-05 | Phase 9 | Pending |
| DEAD-06 | Phase 13 | Pending |
| SCHM-01 | Phase 8 | Complete |
| SCHM-02 | Phase 8 | Complete |
| SCHM-03 | Phase 8 | Complete |
| SCHM-04 | Phase 8 | Complete |
| ENTM-01 | Phase 12 | Pending |
| ENTM-02 | Phase 12 | Pending |
| ENTM-03 | Phase 12 | Pending |
| DATA-01 | Phase 12 | Pending |
| DATA-02 | Phase 12 | Pending |
| DATA-03 | Phase 12 | Pending |
| IMG-01 | Phase 10 | Pending |

**Coverage:**
- v1 requirements: 17 total
- Mapped to phases: 17
- Unmapped: 0 ✓

---
*Requirements defined: 2026-03-03*
*Last updated: 2026-03-03 — traceability mapped to phases 8-13*
