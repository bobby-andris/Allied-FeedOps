# Requirements: Allied FeedOps v1.2

**Defined:** 2026-02-20
**Core Value:** Diagnose why existing feed optimization isn't producing measurable Google Shopping impact, apply evidence-backed fixes, and upgrade generation intelligence based on deep understanding of Google's ranking mechanisms.

## v1.2 Requirements

### Diagnosis

- [ ] **DIAG-01**: System can report SKU coverage funnel (total catalog → generated → approved → published → confirmed in GMC) via SQL queries against existing Supabase data
- [x] **DIAG-02**: Execution path for single-SKU UI regeneration is traced and documented, confirming which Python functions are invoked and which are bypassed (Path A vs Path B)
- [x] **DIAG-03**: Feature flag call-site audit confirms which flags (PROMPT_CONTRACT_V2, INTENT_CURATOR_V1, SEGMENT_STRATEGY_V1) have active call sites in production code paths
- [ ] **DIAG-04**: Propagation spot-check verifies whether published content actually reached Google Sheets rows and GMC feed (read-back verification)

### Measurement

- [ ] **MEAS-01**: Each content generation records which feature flags were active at generation time (feature_flags_active field in regeneration_history)
- [ ] **MEAS-02**: GMC disapproval visibility — system can query Merchant API to identify disapproved/not-serving products and surface issues (the one silent impact killer)
- [ ] **MEAS-03**: Prompt hash lineage tracking connects generated content to the exact prompt version that produced it
- [ ] **MEAS-04**: Bottleneck classifier categorizes impact issues as code-path, auction/bid, query relevance, coverage gap, or propagation failure — with evidence for each classification

### Fixes

- [ ] **FIX-01**: UI single-SKU regeneration path (/regenerate) uses the same rich prompt construction as batch path (segment strategy, keyword plan, gold examples from generator.py)
- [ ] **FIX-02**: Unwired feature flags (PROMPT_CONTRACT_V2, INTENT_CURATOR_V1) are connected to active generation code paths with observable activation

### Model Optimization

- [x] **MODEL-01**: Research GPT-5.2 capabilities, pricing, and best practices for product content generation — compare against current model (GPT-4o or equivalent) on quality, speed, and cost per SKU
- [x] **MODEL-02**: Evaluate alternative models (Claude, Gemini, open-source) for cost-effective feed content generation with quality benchmarks
- [ ] **MODEL-03**: If a superior model is identified, implement model switch in Python pipeline with A/B quality comparison on sample SKUs

### Google Shopping Intelligence

- [x] **GOOG-01**: Deep research into Google Shopping ranking factors — what signals drive product surfacing in Shopping results (feed quality, bid strategy, seller ratings, product data completeness, structured data, historical performance, landing page quality)
- [x] **GOOG-02**: Competitive analysis methodology — understand why competitors show 5x for search terms where Allied Brass products are better suited (analyze: auction dynamics, impression share, product data gaps, category targeting, bid strategies)
- [x] **GOOG-03**: Generate actionable checklist of Google Shopping optimization factors with priority ranking — which factors are within feed control vs require account-level changes
- [ ] **GOOG-04**: Update content generation prompts to incorporate Google Shopping ranking intelligence — titles, descriptions, and structured data should reflect what Google's algorithm actually rewards
- [ ] **GOOG-05**: Image generation guidance updated to reflect Google Shopping visual ranking factors (product clarity, lifestyle context, image quality signals that affect CTR and Quality Score)

## Future Requirements (v1.3+)

### Advanced Measurement

- **AMEAS-01**: A/B cohort tracking via custom_label_3 in supplemental feed
- **AMEAS-02**: Staged rollout framework with per-cohort measurement windows (14-28 day minimum)
- **AMEAS-03**: Content quality self-scoring added to /regenerate path (not just /optimize-sku)

### Coverage Expansion

- **COV-01**: Automated bulk regeneration pipeline for uncovered SKU segments
- **COV-02**: Priority queue for high-impression low-CTR SKUs

## Out of Scope

| Feature | Reason |
|---------|--------|
| Real-time feed monitoring | Overkill for diagnostic milestone — batch checks sufficient |
| Full Content API → Merchant API migration | Content API works until Aug 2026 — only add diagnostic queries via Merchant API |
| Mobile dashboard | Not relevant to impact diagnosis |
| Multi-account Google Ads | Single account (6253381786) |
| Native Google Shopping experiments | Only works with Performance Max, not standard Shopping campaigns |

## Traceability

| Requirement | Phase | Status |
|-------------|-------|--------|
| GOOG-01 | Phase 17 | Complete |
| GOOG-02 | Phase 17 | Complete |
| GOOG-03 | Phase 17 | Complete |
| MODEL-01 | Phase 17 | Complete |
| MODEL-02 | Phase 17 | Complete |
| DIAG-01 | Phase 18 | Pending |
| DIAG-02 | Phase 18 | Complete |
| DIAG-03 | Phase 18 | Complete |
| DIAG-04 | Phase 18 | Pending |
| MEAS-01 | Phase 19 | Pending |
| MEAS-02 | Phase 19 | Pending |
| MEAS-03 | Phase 19 | Pending |
| MEAS-04 | Phase 19 | Pending |
| FIX-01 | Phase 20 | Pending |
| FIX-02 | Phase 20 | Pending |
| GOOG-04 | Phase 20 | Pending |
| GOOG-05 | Phase 20 | Pending |
| MODEL-03 | Phase 20 | Pending |

**Coverage:**
- v1.2 requirements: 18 total
- Mapped to phases: 18
- Unmapped: 0

---
*Requirements defined: 2026-02-20*
*Last updated: 2026-02-20 — traceability complete, phases 17-20 assigned*
