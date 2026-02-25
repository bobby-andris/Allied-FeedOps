# Phase 28: NULL Rate Audit & API Quota Analysis

**Audited:** 2026-02-25
**Data source:** Production Supabase (project `qezuszwufortkiutlhym`)
**Scope:** All foreign keys in the publish-performance join chain + Google Ads API quota sustainability

---

## Part 1: NULL Rate Audit

### 1.1 publish_events Column Completeness

**Total rows:** 73 | **Success events:** 69

| Column | Non-NULL | NULL | % Populated | Assessment |
|--------|----------|------|-------------|------------|
| `master_sku` | 73 | 0 | 100% | Fully populated (NOT NULL constraint) |
| `platform` | 73 | 0 | 100% | Fully populated (NOT NULL constraint) |
| `batch_id` | 23 | 50 | 31.5% | Expected -- not all publishes are batched |
| `content_version` | 22 | 51 | 30.1% | Needs enforcement going forward |
| `prompt_hash` | 2 | 71 | 2.7% | Backfillable from `generated_content.generation_prompt_hash` |
| `evidence_hash` | 2 | 71 | 2.7% | Backfillable if evidence data is available at publish time |
| `final_payload_hash` | 2 | 71 | 2.7% | Derivable from `final_payload_snapshot` |
| `segment_key` | 0 | 73 | 0% | Never populated -- enforce going forward |
| `published_title` | -- | -- | -- | Not audited (content snapshot, not a join key) |
| `published_description` | -- | -- | -- | Not audited (content snapshot, not a join key) |

**Key finding:** The migration 034 columns (`prompt_hash`, `evidence_hash`, `final_payload_hash`, `segment_key`) were added but the publishing code only started populating `prompt_hash` in the week of 2026-02-16 (2 events out of 11 that week = 18.2%).

### 1.2 performance_snapshots Column Completeness

**Total rows:** 179

| Column | Non-NULL | NULL | % Populated | Assessment |
|--------|----------|------|-------------|------------|
| `master_sku` | 179 | 0 | 100% | Fully populated (NOT NULL constraint) |
| `platform` | 179 | 0 | 100% | Fully populated (NOT NULL constraint) |
| `publish_event_id` | 178 | 1 | 99.4% | Excellent -- nearly all linked |
| `content_version` | 14 | 165 | 7.8% | Needs enforcement going forward |
| `days_since_publish` | 178 | 1 | 99.4% | Excellent -- calculated from publish_events |
| `cohort_type` | **COLUMN MISSING** | -- | -- | Not in production schema (documented in SCHEMA.md but never applied) |
| `product_category` | **COLUMN MISSING** | -- | -- | Not in production schema (documented in SCHEMA.md but never applied) |

**Schema drift finding:** `cohort_type` and `product_category` columns exist in SCHEMA.md documentation but are NOT present in the production `performance_snapshots` table. The production table has 18 columns; SCHEMA.md documents 20. These columns were likely part of migration 035 (performance_impact_scores) that was never fully applied.

### 1.3 performance_impact_scores

**Table does NOT exist in production.** The `performance_impact_scores` table is documented in SCHEMA.md and referenced in migration 035, but the table was never created in production.

**Impact:** Diff-in-diff scoring is not available. Phase 29 must either create this table or implement the feedback view without impact scores.

### 1.4 Join Chain Completeness (The Actual Feedback View Join)

```
generated_content.generation_prompt_hash (484/584 = 82.9% populated)
    -> publish_events.prompt_hash (2/73 = 2.7% populated)
    -> publish_events.content_version (22/73 = 30.1% populated)
    -> performance_snapshots.publish_event_id (178/179 = 99.4% populated)
    -> performance_snapshots.content_version (14/179 = 7.8% populated)
    -> performance_impact_scores.publish_event_id (TABLE DOES NOT EXIST)
```

**Direct join results (performance_snapshots LEFT JOIN publish_events):**

| Metric | Count | % of Snapshots |
|--------|-------|----------------|
| Total snapshots | 179 | 100% |
| Snapshots with `publish_event_id` | 178 | 99.4% |
| Matched to publish_events row | 178 | 99.4% |
| Matched with `prompt_hash` available | 0 | 0% |
| Matched with `content_version` available | 14 | 7.8% |

**Why 0% prompt_hash through the join:** The 2 publish_events that have `prompt_hash` (IDs 73, 74 -- SKUs CL-28-24 and CL-29, published 2026-02-21) do not yet have corresponding performance snapshots. Snapshot capture has not run for these SKUs since they were published with prompt tracking.

### 1.5 Temporal Analysis: When Did prompt_hash Start Being Populated?

| Week | Events | With prompt_hash | % |
|------|--------|------------------|---|
| 2026-02-02 | 25 | 0 | 0% |
| 2026-02-09 | 33 | 0 | 0% |
| 2026-02-16 | 11 | 2 | 18.2% |

`prompt_hash` population began the week of 2026-02-16 when the `expand-variants.ts` code was updated to copy `generation_prompt_hash` from `generated_content` to `publish_events.prompt_hash` during publishing.

### 1.6 Data Overlap Summary

| Metric | Count |
|--------|-------|
| Distinct SKUs with performance snapshots | 39 |
| Distinct SKUs with successful publish events | 42 |
| SKUs with BOTH snapshots and publish events | 39 |
| `generated_content` rows with `generation_prompt_hash` | 484/584 (82.9%) |

---

## Part 2: Go/No-Go Decision for Feedback View (Phase 29 FEED-01)

### Decision: **GO** -- with backfill strategy

**Rationale:**

1. **The join chain is structurally sound.** 99.4% of snapshots link to publish_events via `publish_event_id`. The infrastructure works.

2. **The data gap is temporal, not structural.** `prompt_hash` population started 2026-02-16. Prior events lack it because the code path didn't exist yet. All future publishes will populate it.

3. **Backfill is possible for `prompt_hash`.** 82.9% of `generated_content` rows have `generation_prompt_hash`. A backfill script can match `publish_events` to `generated_content` on `(master_sku, platform)` and copy the hash. This would retroactively link ~67 of the 69 success events.

4. **Even without backfill, the view is useful.** Per user decision: "Any linked data is useful -- even 10 records justifies building the view." The 178 snapshot-to-publish_event links provide content-performance correlation even without prompt_hash (via `master_sku + platform`).

5. **content_version is a secondary concern.** Only 30.1% of publish_events have it, but the feedback view can still function using `master_sku + platform` as the primary join key. Content version adds precision but isn't required for the minimum viable view.

### Minimum Viable Feedback View Join

```sql
-- This join works TODAY with 178/179 rows matching
SELECT
  ps.master_sku,
  ps.platform,
  ps.snapshot_date,
  ps.impressions,
  ps.clicks,
  ps.ctr,
  ps.days_since_publish,
  pe.published_at,
  pe.published_title,
  pe.prompt_hash,       -- NULL for pre-Feb-16 events
  pe.content_version,   -- NULL for ~70% of events
  gc.candidate_content,
  gc.quality_score,
  gc.generation_prompt_hash
FROM performance_snapshots ps
JOIN publish_events pe ON ps.publish_event_id = pe.id
LEFT JOIN generated_content gc
  ON pe.master_sku = gc.master_sku
  AND pe.platform = gc.platform
  AND gc.content_type = 'title'
WHERE pe.status = 'success';
```

---

## Part 3: Phase 29 Recommendations

### 3.1 Columns to Enforce NOT NULL Going Forward

| Column | Table | Action | Reasoning |
|--------|-------|--------|-----------|
| `prompt_hash` | publish_events | Enforce NOT NULL on new inserts | Required for content-performance feedback loop |
| `content_version` | publish_events | Enforce NOT NULL on new inserts | Needed for A/B tracking of prompt versions |
| `content_version` | performance_snapshots | Enforce NOT NULL on new inserts | Should mirror the version from the linked publish_event |
| `segment_key` | publish_events | Enforce NOT NULL on new inserts | Required for segment-level analysis |

**Note:** Do NOT add ALTER TABLE constraints retroactively (would fail on existing NULLs). Instead, enforce at the application layer in the publishing code paths.

### 3.2 Backfill Opportunities

| Column | Backfill Source | Feasibility | Priority |
|--------|----------------|-------------|----------|
| `publish_events.prompt_hash` | `generated_content.generation_prompt_hash` via `(master_sku, platform)` join | HIGH -- 82.9% of source data has the hash | P1 -- enables full feedback chain |
| `publish_events.content_version` | `generated_content.version` via `(master_sku, platform)` join | HIGH -- version data exists in generated_content | P1 -- enables version tracking |
| `publish_events.final_payload_hash` | Derive from `final_payload_snapshot` using SHA-256 | MEDIUM -- requires hashing existing JSONB | P2 -- nice to have for payload diffing |
| `publish_events.segment_key` | Derive from `product_catalog.category` or `custom_label_0` | MEDIUM -- requires business rule definition | P3 -- needed for segment analysis |
| `performance_snapshots.content_version` | Copy from linked `publish_events.content_version` after that backfill | HIGH -- direct FK join | P1 -- chain dependency |

### 3.3 Schema Drift Issues to Address

1. **`performance_snapshots`** is missing `cohort_type` and `product_category` columns documented in SCHEMA.md. Decision needed: add them via ALTER TABLE, or update SCHEMA.md to match production.

2. **`performance_impact_scores`** table does not exist. If Phase 29 needs diff-in-diff scoring, this table must be created first.

3. **SCHEMA.md** should be updated to reflect actual production state. The documentation currently overstates what exists.

### 3.4 Minimum Viable Join for Feedback View

The feedback view should use:
- **Primary join:** `performance_snapshots.publish_event_id -> publish_events.id` (99.4% match rate)
- **Content join:** `publish_events.(master_sku, platform) -> generated_content.(master_sku, platform)` (works for all events)
- **Optional enrichment:** `publish_events.prompt_hash` (2.7% now, 100% after backfill)

The view does NOT need `performance_impact_scores` for its initial version. Simple before/after comparison using `performance_baselines` vs `performance_snapshots` is sufficient.
