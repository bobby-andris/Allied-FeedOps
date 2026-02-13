# Requirements: Allied FeedOps v1.0

**Defined:** 2026-02-13
**Core Value:** Transform low-performing product feeds into high-converting assets by combining real search query data with AI content generation

## v1.0 Requirements

### Job Management & Foundation

- [ ] **JOB-01**: System can create batch job records with unique IDs and initial status
- [ ] **JOB-02**: System can update job status (creating, running, complete, failed, partial)
- [ ] **JOB-03**: System can track progress metrics (SKUs processed, percentage complete, ETA)
- [ ] **JOB-04**: System can log errors with SKU ID, error type, and error message
- [ ] **JOB-05**: System can resume interrupted jobs from last checkpoint
- [ ] **JOB-06**: System implements idempotent upserts (ON CONFLICT) for all data writes
- [ ] **JOB-07**: System implements exponential backoff for API rate limit errors
- [ ] **JOB-08**: System implements token bucket rate limiting (10 QPS max)
- [ ] **JOB-09**: System creates checkpoints every 100 SKUs processed
- [ ] **JOB-10**: System limits concurrent batch jobs to 3 maximum

### Data Collection

- [ ] **DATA-01**: System can fetch search terms using campaign-join pattern (2-step query)
- [ ] **DATA-02**: System can collect 180 days of performance metrics per SKU
- [ ] **DATA-03**: System can generate Keyword Planner ideas for all 2,784 SKUs
- [ ] **DATA-04**: System can sync custom_label_0 from Google Merchant Center
- [ ] **DATA-05**: System can capture performance baselines with date range metadata
- [ ] **DATA-06**: System processes SKUs in batches of 10 for optimal throughput
- [ ] **DATA-07**: System uses explicit date ranges (YYYY-MM-DD) in all GAQL queries
- [ ] **DATA-08**: System handles lowercase offer IDs (shopify_us_) per API format
- [ ] **DATA-09**: System collects competitive metrics (impression/click share) where available
- [ ] **DATA-10**: System stores all collected data with collection timestamps

### Data Quality & Validation

- [ ] **VALID-01**: System validates completeness (actual SKU count vs expected 2,784)
- [ ] **VALID-02**: System checks data freshness (baselines <60 days, search terms <7 days)
- [ ] **VALID-03**: System detects multi-SKU families via product_id matching
- [ ] **VALID-04**: System prevents baseline capture for SKUs published in last 30 days
- [ ] **VALID-05**: System validates schema at collection time using Pydantic models
- [ ] **VALID-06**: System performs range checks (CTR 0-1, clicks <= impressions)
- [ ] **VALID-07**: System sets job status to 'partial' if success_count < 95%
- [ ] **VALID-08**: System flags aggregated data for multi-SKU families in database
- [ ] **VALID-09**: System validates date boundaries don't overlap publish events
- [ ] **VALID-10**: System detects statistical outliers in collected metrics

### Monitoring & Automation

- [ ] **MON-01**: Dashboard displays batch job status and progress
- [ ] **MON-02**: Dashboard shows coverage metrics (X/2,784 SKUs with data)
- [ ] **MON-03**: Dashboard displays data freshness heatmap
- [ ] **MON-04**: Dashboard tracks API health (latency, error rates, rate limits)
- [ ] **MON-05**: System sends email alerts on job failure
- [ ] **MON-06**: System sends Slack notifications on job completion
- [ ] **MON-07**: System automatically triggers backfill for missing SKU data
- [ ] **MON-08**: System implements incremental refresh (daily 1-day queries after initial 180-day backfill)
- [ ] **MON-09**: System logs structured events with request_id context
- [ ] **MON-10**: System exports Prometheus metrics (job progress, API latency, errors)

## v2 Requirements

Deferred to future release. Tracked but not in current roadmap.

### Optimization

- **OPT-01**: System adapts batch size based on API latency (smart batching)
- **OPT-02**: System implements dead letter queue for failed items
- **OPT-03**: System processes date ranges in parallel (parallel window processing)
- **OPT-04**: System analyzes historical trends for pattern detection
- **OPT-05**: System predicts SKU performance based on historical data

### Advanced Monitoring

- **ADV-01**: System detects anomalies in collected metrics
- **ADV-02**: System provides SLA tracking dashboards
- **ADV-03**: System generates automated quality reports
- **ADV-04**: System implements canary deployments for backfill changes

## Out of Scope

Explicitly excluded. Documented to prevent scope creep.

| Feature | Reason |
|---------|--------|
| Real-time data streaming | Keyword Planner rate-limited, data updates monthly. Batch collection sufficient. |
| Offset-based pagination | Google Ads API only supports token-based via SearchStream |
| Parallel worker architecture | Sequential completes in 5-7 min. Parallelism adds 80% effort for 20% time savings at current scale. |
| Granular job cancellation | Cloud Run background tasks don't support graceful cancellation |
| Custom retry policies per API | Google Ads SDK already implements optimal exponential backoff |
| Sub-second progress updates | Causes write amplification. Update every 10 SKUs or 5 seconds instead. |
| Multi-account management | Single account (6253381786) sufficient for v1.0 |
| Advanced ML models | Manual prompts first, defer ML to v2+ |
| Mobile app | Web dashboard sufficient for v1.0 |
| Competitive intelligence beyond own metrics | Auction insights API unavailable |

## Traceability

Which phases cover which requirements. Updated during roadmap creation.

| Requirement | Phase | Status |
|-------------|-------|--------|
| TBD | TBD | Pending |

**Coverage:**
- v1 requirements: 40 total
- Mapped to phases: 0 (roadmap not created yet)
- Unmapped: 40 ⚠️

---
*Requirements defined: 2026-02-13*
*Last updated: 2026-02-13 after research synthesis and category scoping*
