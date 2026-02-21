# Requirements: Allied FeedOps v1.3a

**Defined:** 2026-02-21
**Core Value:** Transform low-performing product feeds into high-converting assets with AI content generation informed by Google Shopping ranking intelligence

## v1.3a Requirements

Requirements for Content Generation Excellence milestone. Each maps to roadmap phases.

### GPT-5.2 Integration

- [ ] **GPT52-01**: Pipeline does not pass temperature alongside reasoning_effort params (mutually exclusive on GPT-5.2)
- [ ] **GPT52-02**: Pipeline uses a sensible reasoning_effort default (not zero) when env var is unset
- [ ] **GPT52-03**: Pipeline uses json_schema strict mode instead of legacy json_object response format
- [ ] **GPT52-04**: Pipeline sets prompt_cache_retention for batch runs to avoid cache expiration between SKUs
- [ ] **GPT52-05**: System prompt uses XML tags instead of === headers for GPT-5.2 parsing reliability

### Prompt Architecture

- [ ] **PRMT-01**: SYSTEM_PROMPT rewritten from compliance document to creative brief with positive examples of excellent content
- [ ] **PRMT-02**: All 8 runtime YAML configs loaded and injected into generation prompts by prompt_builder.py
- [ ] **PRMT-03**: Category guidance expanded from 3 groups to cover at minimum the top-20 revenue product categories
- [ ] **PRMT-04**: Prompts include customer use case framing (who buys this, why, what problem it solves)
- [ ] **PRMT-05**: Prompts include competitive positioning evidence (how this product compares to alternatives)

### Gold Standards & Quality

- [ ] **GOLD-01**: At least 15 gold standard description examples stored in prompt_templates table
- [ ] **GOLD-02**: Gold standards cover major product categories (towel bars, grab bars, shower accessories, mirrors, etc.)
- [ ] **GOLD-03**: Quality scoring rubric rewritten to reward differentiation and emotional resonance over rule compliance
- [ ] **GOLD-04**: Quality evaluation can be run at scale across multiple SKUs (not just manual one-by-one)

### Evaluation & Iteration

- [ ] **EVAL-01**: Content regenerated for 10 representative SKUs spanning different product categories
- [ ] **EVAL-02**: Old vs new descriptions compared side-by-side with human evaluation
- [ ] **EVAL-03**: Human evaluator rates new descriptions as "significantly better" for at least 8/10 test SKUs
- [ ] **EVAL-04**: New descriptions pass differentiation test (identifiable as Allied Brass, not generic)
- [ ] **EVAL-05**: Quality scores on new rubric average >85% across test SKUs
- [ ] **EVAL-06**: Test batch published for CTR/CVR delta measurement

## v1.3b+ Requirements

Deferred to future milestones. Tracked but not in current roadmap.

### Architecture (v1.3b)

- **ARCH-01**: Evaluate and selectively apply deferred migrations (034b, 035b)
- **ARCH-02**: Create content-performance feedback table linking generated content to CTR/CVR outcomes
- **ARCH-03**: Persist daily snapshots of service.ts Google Ads funnel queries
- **ARCH-04**: Populate empty optimization tables with real computed data

### Intelligence (v1.3c)

- **INTL-01**: Replace hardcoded thresholds with distribution-based scoring
- **INTL-02**: Surface revenue leakage with dollar estimates
- **INTL-03**: Enable tier movements and market intelligence

## Out of Scope

| Feature | Reason |
|---------|--------|
| Multi-agent pipeline (6-agent) | Skills-enhanced single model gives better ROI (est. 85-92/100 at 1.5x cost vs 3x for agents) |
| A/B testing infrastructure | Requires architecture work (v1.3b) before meaningful A/B tests |
| Automated regeneration triggers | Need feedback loop (v1.4) before auto-triggering regeneration |
| Shopify storefront content changes | v1.3a focuses on feed content (Google/Bing); Shopify content is separate optimization |
| Evidence table restructuring | Evidence builder works; adding new evidence types (use cases, competitive) via prompt, not schema |

## Traceability

| Requirement | Phase | Status |
|-------------|-------|--------|
| GPT52-01 | — | Pending |
| GPT52-02 | — | Pending |
| GPT52-03 | — | Pending |
| GPT52-04 | — | Pending |
| GPT52-05 | — | Pending |
| PRMT-01 | — | Pending |
| PRMT-02 | — | Pending |
| PRMT-03 | — | Pending |
| PRMT-04 | — | Pending |
| PRMT-05 | — | Pending |
| GOLD-01 | — | Pending |
| GOLD-02 | — | Pending |
| GOLD-03 | — | Pending |
| GOLD-04 | — | Pending |
| EVAL-01 | — | Pending |
| EVAL-02 | — | Pending |
| EVAL-03 | — | Pending |
| EVAL-04 | — | Pending |
| EVAL-05 | — | Pending |
| EVAL-06 | — | Pending |

**Coverage:**
- v1.3a requirements: 20 total
- Mapped to phases: 0
- Unmapped: 20 (pending roadmap creation)

---
*Requirements defined: 2026-02-21*
*Last updated: 2026-02-21 after initial definition*
