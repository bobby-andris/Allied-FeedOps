# Requirements: Allied FeedOps v1.3b

**Defined:** 2026-02-25
**Core Value:** Validate and prepare the data architecture so the circular feedback loop (capture → monitor → analyze → learn → optimize → repeat) can be built on a solid foundation for v1.3c and v1.4.

## v1.3b Requirements

Requirements for this milestone. Each maps to roadmap phases.

### Architecture Audit

- [x] **AUDIT-01**: Data flow audit document maps complete path from Google Ads API → service.ts → database → dashboard → actions → Google Ads, marking every dead end
- [x] **AUDIT-02**: API quota analysis confirms daily snapshot capture is sustainable within Google Ads Standard Access limits and recommends caching strategy
- [x] **AUDIT-03**: Migration triage produces KEEP/DEFER/PRUNE decision for all 18 deferred tables (035b + 034b) with documented reasoning for each
- [x] **AUDIT-04**: NULL rate audit on join chain keys (publish_events.prompt_hash, performance_snapshots.content_version) confirms feedback view will produce meaningful results
- [x] **AUDIT-05**: Circular flow validation confirms database schema can support the full loop: capture → monitor & evaluate → analyze & learn → optimize → repeat, with no missing tables or broken linkages

### Content-Performance Feedback

- [x] **FEED-01**: Content-performance feedback view/table joins publish_events + performance_snapshots + generated_content, keyed on (master_sku, platform), showing baseline vs post-publish CTR/CVR deltas at 7/14/30-day windows
- [x] **FEED-02**: Performance impact scores computed and written to existing performance_impact_scores table using diff-in-diff methodology (treated vs control cohort lift)
- [x] **FEED-03**: Search query snapshots populated after publish events, capturing which search terms gained/lost impressions after content changes
- [x] **FEED-04**: prompt_hash NOT NULL constraint enforced for new publish events to ensure content versioning linkage integrity

### Historical Persistence

- [x] **HIST-01**: funnel_snapshots_daily table persists daily search term tier data from service.ts GAQL queries with 90-day retention policy
- [x] **HIST-02**: Daily capture endpoint (write-behind, non-blocking to service.ts live queries) triggered by Cloud Scheduler
- [x] **HIST-03**: 7-day vs previous-7-day trend indicators displayed on Shopping Funnel dashboard page

### Migration & Schema Cleanup

- [x] **MIGR-01**: Subset of 035b tables applied (4-8 tables that are prerequisites for v1.3c), with schema verified against TypeScript consumer expectations
- [x] **MIGR-02**: Dead TypeScript files for pruned tables deleted or deprecated, build passes after cleanup
- [x] **MIGR-03**: Orphaned dashboard components (GmcDisapprovalBadge, PromptLineagePanel) either wired into dashboard pages or removed
- [x] **MIGR-04**: SCHEMA.md updated to reflect true production state after all migration changes

## Future Requirements (v1.3c / v1.4)

### Deferred to v1.3c

- **OPT-01**: Distribution-based scoring replaces hardcoded ROAS thresholds in optimization tables
- **OPT-02**: Revenue leakage surface with dollar estimates
- **OPT-03**: Tier movement tracking and market intelligence
- **OPT-04**: Full experiment framework UI for experiment_registry/assignments/outcomes tables

### Deferred to v1.4

- **LOOP-01**: Content A/B attribution — measure which prompt changes drove CTR improvement
- **LOOP-02**: Automated content regeneration based on performance outcomes
- **LOOP-03**: Cross-system learning (what prompt changes drove CTR improvement?)
- **LOOP-04**: Automated optimization cycles (daily/weekly/monthly)

## Out of Scope

| Feature | Reason |
|---------|--------|
| Real-time streaming from Google Ads | Daily batch collection sufficient; Google Ads data only updates daily |
| Apply ALL 18 deferred tables blindly | 034b has zero code references; 035b has 6 tables with no clear consumer |
| 034b GA4 attribution tables | No code references, no data pipeline, Google Ads covers primary use case |
| Distribution-based scoring for optimization tables | This is v1.3c Phase 1's entire scope — would duplicate work |
| Automated content regeneration | This is v1.4 — feedback loop data must exist before automation |
| Multi-account Google Ads support | Single account (6253381786), no business need |
| Redis/dbt/Airflow for caching/ETL | Scale (2,784 SKUs, ~1M rows/year) does not warrant external services |
| Bing/Shopify platform feedback | Different metric sources not currently captured; defer to v1.4 |

## Traceability

| Requirement | Phase | Status |
|-------------|-------|--------|
| AUDIT-01 | Phase 28 | Complete |
| AUDIT-02 | Phase 28 | Complete |
| AUDIT-03 | Phase 28 | Complete |
| AUDIT-04 | Phase 28 | Complete |
| AUDIT-05 | Phase 28 | Complete |
| FEED-01 | Phase 29 | Complete |
| FEED-02 | Phase 29 | Complete |
| FEED-03 | Phase 29 | Complete |
| FEED-04 | Phase 29 | Complete |
| HIST-01 | Phase 30 | Complete |
| HIST-02 | Phase 30 | Complete |
| HIST-03 | Phase 30 | Complete |
| MIGR-01 | Phase 31 | Complete |
| MIGR-02 | Phase 31 | Complete |
| MIGR-03 | Phase 31 | Complete |
| MIGR-04 | Phase 31 | Complete |

**Coverage:**
- v1.3b requirements: 16 total
- Mapped to phases: 16
- Unmapped: 0 ✓

---
*Requirements defined: 2026-02-25*
*Last updated: 2026-02-25 after initial definition*
