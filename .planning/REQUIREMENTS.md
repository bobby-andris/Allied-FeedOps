# Requirements: Allied FeedOps v1.1

**Defined:** 2026-02-18
**Core Value:** Transform low-performing product feeds into high-converting assets by combining real search query data with AI content generation

## v1.0 Requirements (Complete — Archived)

All 40 v1.0 requirements (JOB-01–10, DATA-01–10, VALID-01–10, MON-01–10) were completed in phases 5–8. See MILESTONES.md for details.

## v1.1 Requirements

### SKU Review (SKUR)

- [x] **SKUR-01**: User sees a stats summary bar at the top of the SKU review page showing counts by status and platform (approved, pending, not started — per Google/Bing)
- [x] **SKUR-02**: SKUs display in a compact list format where status is visible without per-SKU vertical scrolling
- [x] **SKUR-03**: Per-platform approval status (Google / Bing) is visible inline for each SKU row in the list
- [x] **SKUR-04**: User can click into a SKU to expand full detail while keeping list context visible
- [x] **SKUR-05**: User can filter the SKU list by status (needs review, approved, all) and by platform

### Image Workflow (IMG)

- [ ] **IMG-01**: User can manually select which finish/variant to use when generating a lifestyle image for a SKU
- [ ] **IMG-02**: When no variant is manually selected, system auto-selects the Google Ads variant with the most impressions (not a fixed heuristic like "first finish" or "fire engine red")
- [ ] **IMG-03**: User can see which Google Ads variants for a SKU have an associated lifestyle image vs. are missing one
- [ ] **IMG-04**: Image generation uses user-selected variant instead of overriding with auto-selection logic

### Performance Page (PERF)

- [ ] **PERF-01**: Performance page shows a clear before/after comparison (baseline vs. latest snapshot) per published SKU
- [ ] **PERF-02**: User can see days-since-publish alongside metric deltas (CTR, impressions, clicks, CVR)
- [ ] **PERF-03**: Page visually surfaces which SKUs are trending up vs. down since publish

### Dashboard Audit (DASH)

- [ ] **DASH-01**: Each dashboard page either displays useful, current data or surfaces a clear next action — no dead-end empty states
- [ ] **DASH-02**: Pages with stale or broken data are identified and fixed
- [ ] **DASH-03**: Pages or features that don't serve current workflow are simplified or removed

### Visual Verification (VER)

- [x] **VER-01**: All UI changes are visually inspected using browser automation (agent-browser) before being marked complete — executor must confirm changes render correctly and features work end-to-end in the live dashboard

## v2 Requirements

### Image Coverage
- **IMG-05**: Every Google Ads variant for published SKUs has an associated lifestyle image
- **IMG-06**: Bulk image generation with per-variant targeting across catalog

### Advanced Performance
- **PERF-04**: Performance trend charts over time (7d, 30d, 90d windows)
- **PERF-05**: Automated alerts when a published SKU underperforms baseline

## Out of Scope

| Feature | Reason |
|---------|--------|
| Batch management redesign | Rarely used — only simplify/remove if audit flags it |
| Mobile app / native integrations | Web dashboard sufficient |
| New content generation features | Separate milestone scope |
| Multi-account Google Ads | Single account: 6253381786 |
| Real-time data streaming | Batch collection sufficient |

## Traceability

Which phases cover which requirements. Updated during roadmap creation.

| Requirement | Phase | Status |
|-------------|-------|--------|
| SKUR-01 | Phase 9 | Complete |
| SKUR-02 | Phase 9 | Complete |
| SKUR-03 | Phase 9 | Complete |
| SKUR-04 | Phase 9 | Complete |
| SKUR-05 | Phase 9 | Complete |
| IMG-01 | Phase 10 | Pending |
| IMG-02 | Phase 10 | Pending |
| IMG-03 | Phase 10 | Pending |
| IMG-04 | Phase 10 | Pending |
| PERF-01 | Phase 11 | Pending |
| PERF-02 | Phase 11 | Pending |
| PERF-03 | Phase 11 | Pending |
| DASH-01 | Phase 12 | Pending |
| DASH-02 | Phase 12 | Pending |
| DASH-03 | Phase 12 | Pending |
| VER-01 | All phases (9–12) | Complete |

**Coverage:**
- v1.1 requirements: 16 total
- Mapped to phases: 16/16 (100% coverage)
- Unmapped: 0

---
*Requirements defined: 2026-02-18*
*Last updated: 2026-02-18 — traceability filled in after roadmap creation*
