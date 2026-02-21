# Strategic Milestone Assessment & Roadmap Recommendation

**Date:** 2026-02-21
**Author:** Claude (Opus 4.6), requested by Bobby Andris
**Status:** Draft for review

---

## Part 1: What v1.2 Actually Built

After thoroughly reviewing all 6 phase verification reports (phases 17-22) in the archived milestone, here is the honest accounting.

### Completed and Verified

| Phase | Name | Status | Key Deliverables |
|-------|------|--------|-----------------|
| 17 | Google Shopping Intelligence Research | PASSED (4/4) | Ranking factor taxonomy, competitive gap analysis (Kingston Brass deep dive), model comparison (GPT-5.2 selected at 90.0/100), 15 prompt change recommendations |
| 18 | Diagnosis — Ground Truth | PASSED (9/9) | SKU coverage funnel, code path trace (Path A/B), feature flag audit, spot-check 10/10 SKUs matched, generation-paths.md |
| 19 | Measurement Infrastructure | GAPS FOUND (3/4) | Feature flag capture, GMC disapproval surface, bottleneck classifier, prompt lineage — but migrations were pending at time of verification |
| 20 | Targeted Fixes & Intelligence | PASSED (13/13) | GPT-5.2 model switch, shopping_intelligence.yaml (15 categories), prompt_builder.py (FIX-01 parity), sku_corrections table, structured feedback UI |
| 21 | Apply Database Migrations | PASSED (6/6) | Migrations 034 + 035 applied live, SCHEMA.md updated, deferred 034b/035b renamed with reasoning |
| 22 | Fix Integration Bugs | PASSED (7/7) | prompt_builder correction_text key fix, GMC_MERCHANT_ID set, keyword_bank.json in Docker, doc gap closures |

### What Actually Exists on Master (Code Inventory)

**Intent System** — 32 files exist under `dashboard/src/lib/intent/`:
- Core: `policy.ts`, `tier-movement.ts`, `types.ts`, `persistence.ts`, `taxonomy.ts`
- Advanced: `channel-adapter.ts`, `graduation.ts`, `incident-automation.ts`, `multi-cell-experiment.ts`, `profit-forecast.ts`, `query-mining.ts`, `reviewer-calibration.ts`, `seasonality.ts`, `value-consistency.ts`, `value-signal.ts`, `executive-scorecard.ts`, `buildout-intelligence.ts`, `input-validation.ts`
- Tests: 14 test files covering all modules

**Shopping Funnel** — 11 files under `dashboard/src/lib/shopping-funnel/`:
- `service.ts` (~1600 lines) — Live Google Ads integration (6 parallel GAQL queries, 2-min cache)
- `decision-staging.ts`, `retry.ts`, `staging-snapshots.ts`, `ui-performance.ts`, `types.ts`
- 4 test files

**Optimization** — 3 files under `dashboard/src/lib/optimization/`:
- `query-intelligence.ts` (NLP decomposition + hardcoded thresholds)
- `control-center.ts` (opportunity clusters, recommendation queue, ROAS recs — hardcoded baselines)
- 1 test file

**Database Migrations on Master:**
- 032: Shopping funnel management + performance impact pipeline
- 033: Optimization control plane (12 tables) + publish event payload snapshot
- 034: Publish lineage hashes (applied live)
- 034b: GA4 attribution forensics (DEFERRED)
- 035: Measurement infrastructure schema (applied live)
- 035b: Unified intent execution system (DEFERRED — 14 tables)
- 036: SKU corrections

**Key Gap: 034b and 035b are DEFERRED** — the GA4 attribution tables and the 14-table intent execution system exist as migration files but have NOT been applied to the live Supabase database. The TypeScript intent code exists but has no backing database tables in production.

### What v1.2 Did NOT Solve

1. **Content quality** — The descriptions are still generic and monotonous (see Part 2 below)
2. **Hardcoded thresholds** — ROAS 3.6/3.1 and CVR 5%/3% still gate all recommendations
3. **Empty dashboard pages** — Shopping Funnel recommendations, Optimization Control, Intent Control, Search Governance, Experiment Lab all show zero results
4. **service.ts data is ephemeral** — 2-minute cache, no database persistence of Google Ads funnel data
5. **Deferred migrations** — 14 intent execution tables not in live database
6. **Feedback loop** — No mechanism to use performance data to improve content generation

---

## Part 2: The Content Quality Crisis (CL-28-18 Analysis)

### The Product (viewed on alliedbrass.com)

**Carolina Collection 4 Tier Ladder Towel Bar (CL-28-18)**
- 4 horizontal bars at varying heights
- Solid brass construction
- Concealed screw mounting
- Available in 25+ finishes, 4 sizes (18/24/30/36 inch)
- Wall-mounted, space-efficient vertical ladder design
- Weight capacity: 20 lbs
- Limited Lifetime Warranty
- Part of the Carolina Collection (matching accessories available)
- Price: ~$414.75 (sale from $525)

The existing Shopify description is honestly... *also* not great. It's your Dad's writing: functional, accurate, but generic ("makes efficient use of your bathroom space", "highly sophisticated and stylish"). However, it at least mentions the fun of stacking towels and the collection coordination opportunity.

### The Generated Description (Google)

```
ladder towel rack for bathroom installation. {FINISH_SENTENCE} Solid brass. 18-inch
center-to-center. Wall-mounted, 4-tier vertical ladder design provides space-efficient
towel storage with four horizontal bars at varying heights. This wall mounted towel rack
uses concealed screw mounting hardware for a clean look, and includes the ladder towel
bar plus all installation hardware. Designed in a traditional style, it supports up to
20 lb and is offered in a wide variety of lifetime designer finishes. Backed by a
Limited Lifetime Warranty.
```

### My Honest Assessment

I agree — this is not good. Here is what I see:

**Problem 1: It opens with a fragment, not a sentence.** "ladder towel rack for bathroom installation" — this is a keyword dump masquerading as an opening. It reads like a spec sheet heading, not a description that would make someone click. Compare to what a competitor might write: "Organize your bathroom with this elegant 4-tier ladder towel bar, crafted from solid brass in {Finish Name}."

**Problem 2: It follows the `shopping_intelligence.yaml` rule TOO literally.** The YAML says: *"First sentence of description: '[Finish] [Product Type] for bathroom installation. [Material]. [Key dimension]. [Key functional claim].'"* The LLM followed this as a rigid template, producing robotic output. The rule was meant to be structural guidance, but GPT-5.2 treated it as a fill-in-the-blank template.

**Problem 3: No differentiation or emotion.** The description could describe any ladder towel bar from any manufacturer. Nothing about Allied Brass's solid brass vs competitors' zinc alloy. Nothing about the Carolina Collection's coordinated design aesthetic. Nothing about the practical reality of having 4 bars at different heights for different family members. No customer scenario. No "why should I buy THIS one?"

**Problem 4: Keyword stuffing via synonym repetition.** "towel rack" → "towel storage" → "wall mounted towel rack" → "ladder towel bar" — the prompt says to include synonyms, and the LLM dutifully stuffed them in, making it feel robotic.

**Problem 5: The {FINISH_SENTENCE} placeholder.** In the generated description this reads like a broken template. While it gets expanded during variant publishing, during review it signals that the content isn't finished or polished.

**Problem 6: Self-score of 81% is misleading.** The LLM gave itself high marks (Specificity 7.8, Brand Voice 9, Factual Accuracy 8). But the scoring rubric rewards factual accuracy and format adherence over the qualities that actually drive clicks: emotional resonance, product differentiation, and compelling use-case framing.

### Root Cause Analysis

The content generation system is architecturally sound but creatively constrained:

1. **The system prompt (prompts.py) is a compliance document, not a creative brief.** It's 237 lines of rules about what NOT to do (no hype, no invented specs, no banned adjectives). There are almost no positive instructions about what GOOD content looks like, what tone to aim for, or how to differentiate products.

2. **The `shopping_intelligence.yaml` provides template-like rules rather than creative guidance.** "First sentence: [Finish] [Product Type] for bathroom installation" produces robotic output across every product.

3. **The category guidance is sparse.** Only 3 category groups are defined (niche_functional, towel_storage, safety_ada). The CL-28-18 ladder towel bar falls under towel_storage, which says "address common frustration (flimsy bars, mismatched finishes)" — but the generated description doesn't do this at all.

4. **Gold standard examples may be absent or weak.** The `format_gold_standard_examples_bundle()` tries to load from `prompt_templates`, but if no gold examples exist for this category, the LLM has no reference for what "good" looks like.

5. **No human-in-the-loop refinement.** The `sku_corrections` table exists but is empty for this SKU. There's no accumulated learning about what works.

6. **The evidence table is spec-heavy, story-light.** Evidence rows contain dimensions, materials, and specs — which produce spec-heavy descriptions. There's no "customer use case" evidence, no "competitive positioning" evidence, no "emotional trigger" evidence.

---

## Part 3: Deep Reflection — What Should Come Next?

### The Circular Feedback Loop You Described

You articulated something profoundly important:

```
capture → monitor & evaluate & analyze → learn & derive insights → optimize → repeat
```

Right now, the system is:
- **Capture**: YES — Google Ads search terms, Keyword Planner, GA4, performance baselines/snapshots
- **Monitor & Evaluate**: PARTIAL — measurement infrastructure exists but recommendations are empty (hardcoded thresholds)
- **Analyze & Learn**: NO — no feedback loop from performance data back to content generation
- **Optimize**: PARTIAL — tier movement pipeline works, but nothing feeds it (no recommendations generated)
- **Repeat**: NO — each subsystem is isolated

### The Foundation-First Argument (Content Quality)

You're right that **if the input data to platforms is flawed, all downstream optimization is limited.** This is the "garbage in, garbage out" principle applied to ad platforms. Here's why this matters specifically for Allied Brass:

1. **Google Shopping's matching algorithm** reads titles and descriptions to understand WHAT a product is and WHO it's for. If the description says "ladder towel rack for bathroom installation" as a keyword-stuffed fragment, Google's algorithm knows less about the product than if it said "Four-tier wall-mounted towel bar with solid brass bars spaced at different heights for easy access — organize your family's towels in under 2 feet of wall space."

2. **CTR is self-reinforcing.** A better description → higher CTR → Google shows the listing more → more data → better optimization signals. A bad description → low CTR → Google shows competitors → less data → optimization is flying blind.

3. **The Phase 17 competitive analysis specifically identified title/description quality as the #1 gap** — 741 impressions for "decorative grab bars" at 0% CTR. The fix was supposed to be in Phase 20, but the shopping_intelligence.yaml guidance produced template-following rather than genuinely better content.

### The Architecture-First Argument (Database & Pipeline)

Your concern about whether the architecture can support the evolving vision is valid:

1. **service.ts queries are ephemeral** — 6 GAQL queries with a 2-minute cache. Every page load re-queries Google Ads API. No historical trend data is persisted from these live queries.

2. **35b_DEFERRED migration has 14 tables** that the intent system TypeScript code references but can't use yet. This is dead code until applied.

3. **No content↔performance feedback table** — there's no table that connects "this description with this prompt_hash produced this CTR/CVR outcome." The pieces exist separately (`regeneration_history` has prompt_hash, `performance_snapshots` has metrics, `publish_events` connects them) but no materialized view or computed table links them.

4. **The optimization tables (migration 033)** — `query_value_scores`, `routing_recommendations`, `opportunity_clusters` — exist but are empty. Nothing writes to them because the scoring logic uses hardcoded thresholds that produce zero results.

### The Optimization-First Argument (v1.3 as Written)

The v1.3 milestone as currently written would:
- Replace hardcoded thresholds with distribution-based scoring (immediately shows recommendations)
- Surface revenue leakage with dollar estimates (immediate value)
- Enable one-click tier movements (immediate optimization capability)
- Build market intelligence (competitive insights, demand gaps)

This is the most immediately revenue-impactful milestone — it turns the existing infrastructure into actionable decisions.

### My Assessment: What Order?

After deeply considering all three arguments, here's what I genuinely believe:

**You're right that content quality should come first, but not as a full milestone.** Here's my reasoning:

1. **Content quality improvement has two layers:**
   - **Layer 1 (Quick):** Fix the prompts and shopping intelligence guidance so generated content is genuinely good. This is 1-2 phases of work, not a full milestone. The architecture is already there (prompt_builder.py, shopping_intelligence.yaml, gold examples, sku_corrections).
   - **Layer 2 (Long-term):** Build the feedback loop where performance data informs and continuously improves content. This requires the full optimization infrastructure from v1.3.

2. **v1.3's optimization intelligence REQUIRES good content to produce meaningful signals.** If you optimize tier placements for products with bad descriptions, you're optimizing where to show bad content. The optimization data will be noisy because CTR/CVR reflect description quality as much as placement quality.

3. **The architecture gaps are real but not blocking.** The deferred migrations (034b, 035b) should be evaluated but don't need a full milestone. The live-query-vs-persist question for service.ts is valid but can be addressed within v1.3 Phase 1.

### Recommended Milestone Order

```
Milestone 1.3a: Content Generation Excellence (2-3 phases)
    ↓
Milestone 1.3b: Architecture Validation & Data Persistence (1-2 phases)
    ↓
Milestone 1.3c: Actionable Shopping Intelligence (4 phases, current v1.3 doc)
    ↓
Milestone 1.4: Closed-Loop Optimization (content ← performance feedback)
```

---

## Part 4: Proposed Milestones with Prompts

### Milestone 1.3a: Content Generation Excellence

**Thesis:** Fix the input data before trying to optimize what we do with it. Make every generated title and description genuinely excellent — the kind of content that makes a luxury bathroom hardware brand stand out against mass-market competitors on every shopping platform.

**Prompt for Milestone Planning:**

```
# GSD Milestone v1.3a: Content Generation Excellence

## Context

You are working on Allied-FeedOps, a feed optimization dashboard for alliedbrass.com (luxury
bathroom accessories). The content generation pipeline (Cloud Run Python) produces titles and
descriptions for Google Shopping, Bing Shopping, and Shopify.

### The Problem

Despite substantial infrastructure (GPT-5.2 model, shopping_intelligence.yaml, prompt_builder.py,
evidence tables, keyword placement), the generated content is GENERIC and MONOTONOUS:

- Descriptions open with keyword-stuffed fragments ("ladder towel rack for bathroom installation")
- The shopping_intelligence.yaml rules are followed as rigid templates, not creative guidance
- No product differentiation — descriptions could apply to any competitor's product
- No emotional resonance or customer scenario framing
- Self-scoring (81%) is misleading — measures compliance, not quality
- Every description across the entire catalog follows the same sentence pattern

### What Exists (DO NOT REBUILD)

1. **Pipeline**: `src/feedops/api/prompt_builder.py` — canonical prompt construction
2. **System Prompt**: `src/feedops/pipeline/prompts.py` — 237-line compliance-focused prompt
3. **Shopping Intelligence**: `src/feedops/config/shopping_intelligence.yaml` — 15 categories
4. **Category Guidance**: `prompts.py::_CATEGORY_GUIDANCE` — only 3 category groups defined
5. **Gold Examples**: `prompt_templates` table in Supabase — format_gold_standard_examples_bundle()
6. **Evidence Builder**: `dashboard/src/lib/evidence/` — product evidence assembly
7. **Corrections**: `sku_corrections` table — persistent per-SKU corrections
8. **Keyword Placement**: `src/feedops/pipeline/keyword_placement.py` — keyword integration
9. **Segment Strategy**: `src/feedops/pipeline/segment_strategy.py` — segment-specific guidance
10. **Feedback Modal**: `dashboard/src/components/review/FeedbackModal.tsx` — structured feedback UI

### What's Wrong

1. **System prompt is all rules, no craft.** 237 lines of "don't do this" with almost no
   positive examples of what EXCELLENT content looks like.
2. **shopping_intelligence.yaml provides templates, not creative direction.**
   "First sentence: [Finish] [Product Type] for bathroom installation" produces robotic output.
3. **Category guidance covers only 3 of 59 product groups.** Most products get zero category-specific
   direction.
4. **Gold standard examples are likely empty or insufficient.** Without strong examples,
   the LLM defaults to safe, generic output.
5. **Evidence table is spec-heavy, story-light.** Dimensions and materials but no competitive
   positioning, customer use cases, or emotional triggers.
6. **Quality scoring rewards compliance over quality.** 81% for a bad description because it
   followed the rules.
7. **No A/B testing of prompt strategies.** No way to know if changes improve conversion.

### Goal

Transform the content generation system so every output is:
1. **Specific** — clearly about THIS product, not any generic towel bar
2. **Differentiated** — highlights solid brass vs zinc alloy, Allied Brass quality vs mass-market
3. **Emotionally resonant** — frames the product in a real customer scenario
4. **Search-optimized** — keywords integrated naturally, not stuffed
5. **Platform-appropriate** — Google Shopping feed-fuel vs Shopify conversion copy
6. **Measurably better** — quality score reflects actual content quality, not rule compliance

### Phase Structure

**Phase 1: Establish Excellence Standards**
- Research what top-performing Google Shopping descriptions look like across bathroom hardware
- Scrape/analyze top-performing competitor listings (Kingston Brass, Moen, Signature Hardware)
- Create 10-15 gold standard description examples covering major product categories
- Store in prompt_templates table for use by format_gold_standard_examples_bundle()
- Rewrite the quality scoring rubric to reward differentiation and emotional resonance

**Phase 2: Rewrite Prompt Architecture**
- Rewrite SYSTEM_PROMPT in prompts.py to be a creative brief, not just a compliance document
- Rewrite shopping_intelligence.yaml to provide creative direction, not fill-in-the-blank templates
- Expand _CATEGORY_GUIDANCE to cover ALL 59 product categories (or at minimum the top 20 by revenue)
- Add "competitive positioning" evidence to the evidence builder (how does THIS product compare?)
- Add "customer use case" framing to the prompt (WHO buys this, WHY, WHAT problem does it solve?)

**Phase 3: Generate, Evaluate, and Iterate**
- Regenerate content for 10 representative SKUs across different categories
- Compare old vs new side-by-side with human evaluation
- Publish to a test batch and measure CTR/CVR delta after 7-14 days
- Iterate on prompt based on results
- Build the quality evaluation pipeline so we can measure improvement at scale

### Success Criteria
- [ ] Human evaluator rates new descriptions as "significantly better" for 8/10 test SKUs
- [ ] New descriptions pass differentiation test: can you tell which company made this product?
- [ ] Google Shopping title format compliance maintained (product type in first 30 chars, etc.)
- [ ] Quality scores on new rubric average >85% (with the new rubric measuring actual quality)
- [ ] At least 15 gold standard examples stored in prompt_templates
- [ ] Category guidance exists for all top-20 revenue product categories

### Technical Notes
- Python pipeline is runtime source of truth — all prompt changes are in Python
- Dashboard /api/regenerate is thin proxy to Cloud Run /regenerate
- Evidence markdown is assembled in evidence.py and passed to prompt_builder.py
- prompt_builder.py::build_core_prompt() is called by ALL generation paths
- shopping_intelligence.yaml is loaded at container startup via lru_cache
- Test locally: regenerate a SKU and compare old vs new output
```

### Milestone 1.3b: Architecture Validation & Data Persistence

**Thesis:** Ensure the database schema, data pipeline, and API architecture can support the evolving optimization intelligence vision before building on top of them.

**Prompt for Milestone Planning:**

```
# GSD Milestone v1.3b: Architecture Validation & Data Persistence

## Context

You are working on Allied-FeedOps. The system has evolved from a simple title/description
generator into a full optimization intelligence platform. The current architecture was designed
for the original simpler use case and may have gaps.

### Known Concerns

1. **Ephemeral Google Ads Data**: `service.ts` queries 6 GAQL queries live with a 2-minute cache.
   No historical data is persisted from these queries. Every page load re-queries the API.
   Questions to answer:
   - Should we persist daily snapshots of funnel term data?
   - What's the API quota impact of live queries vs caching?
   - Can we build trend analysis without historical data?

2. **Deferred Migrations**: Two migration files exist but are NOT applied to live Supabase:
   - `034b_DEFERRED_ga4_attribution_forensics.sql` — 4 GA4 tables
   - `035b_DEFERRED_unified_intent_execution_system.sql` — 14 intent execution tables
   The TypeScript code in `dashboard/src/lib/intent/` references these tables.
   Questions to answer:
   - Are these 18 tables actually needed? Or were they over-engineered?
   - Which ones are prerequisites for v1.3c (Actionable Intelligence)?
   - Can we prune before applying?

3. **Content ↔ Performance Feedback Loop**: No table or view connects:
   - Generated content (prompt_hash, content text) to
   - Performance outcomes (CTR, CVR, revenue) to
   - Optimization actions taken
   This is the missing link for the circular feedback loop.

4. **Data Flow Gaps**:
   - `query_value_scores`, `routing_recommendations`, `opportunity_clusters` tables exist but
     nothing writes to them (hardcoded thresholds produce zero results)
   - `search_queries` + `keyword_metrics` are populated by Python pipeline but not connected
     to the TypeScript optimization libraries

5. **Schema Evolution**: Original schema designed for content generation CMS. Now needs to support:
   - Real-time campaign optimization
   - Historical trend analysis
   - Experiment tracking
   - Content quality feedback loops
   - Cross-platform performance comparison

### What Exists (relevant files)
- `docs/database/SCHEMA.md` — 32+ tables fully documented
- `supabase/migrations/030-036` — all migration files
- `dashboard/src/lib/shopping-funnel/service.ts` — live Google Ads integration
- `dashboard/src/lib/intent/*.ts` — 32 files, 14 tests (code exists, DB tables deferred)
- `dashboard/src/lib/optimization/*.ts` — query intelligence + control center
- `dashboard/src/lib/data-collection/ensure-data.ts` — auto data collection triggers

### Goal

Validate and prepare the architecture so that v1.3c (Actionable Intelligence) and v1.4
(Closed-Loop Optimization) can be built on a solid foundation.

### Phase Structure

**Phase 1: Architecture Audit**
- Map the complete data flow from Google Ads → Database → Dashboard → Actions → Google Ads
- Identify every point where data is lost (ephemeral queries, missing persistence, etc.)
- Document which of the 18 deferred tables are actually needed vs over-engineered
- Assess service.ts API quota usage and recommend caching/persistence strategy
- Design the content↔performance feedback table/view

**Phase 2: Critical Schema Updates**
- Apply the subset of deferred migrations that are prerequisites for v1.3c
- Create the content-performance feedback materialized view or table
- Add daily snapshot persistence for key service.ts query results
- Ensure all optimization tables have proper indexes for query performance

**Phase 3: Data Pipeline Validation**
- Verify end-to-end data flow: Google Ads → service.ts → database → optimization → execution
- Populate empty optimization tables with real computed data (even with simple scoring)
- Validate that the feedback loop can work: publish → measure → learn → improve

### Success Criteria
- [ ] Architecture document showing complete data flow with no dead ends
- [ ] Deferred migrations evaluated — applied or removed with documented reasoning
- [ ] Historical data persistence for at minimum daily tier performance snapshots
- [ ] Content↔performance feedback linkage exists (even if not yet populated)
- [ ] All optimization tables either populated or removed
- [ ] API quota analysis confirms live query approach is sustainable
```

### Milestone 1.3c: Actionable Shopping Intelligence

**Thesis:** Same as the current v1.3 document, but now built on the foundation of excellent content and validated architecture.

**Prompt:** Use the existing document at `docs/plans/2026-02-21-gsd-milestone-v1.3-actionable-intelligence.md` — it's comprehensive and well-structured. The only updates needed after 1.3a and 1.3b are:
- Remove outdated references to things fixed in 1.3a/1.3b
- Add dependencies on new feedback tables from 1.3b
- Update the "What Exists" section to reflect 1.3a/1.3b deliverables

### Milestone 1.4: Closed-Loop Optimization

**Thesis:** Close the feedback loop so the system continuously improves. Performance data from optimization actions feeds back into content generation. Content quality drives optimization quality. The whole system becomes self-reinforcing.

**Prompt for Milestone Planning:**

```
# GSD Milestone v1.4: Closed-Loop Optimization

## Context

You are working on Allied-FeedOps. Previous milestones have established:
- v1.2: Infrastructure (funnel management, intent engine, measurement, database)
- v1.3a: Excellent content generation (differentiated, emotionally resonant, platform-optimized)
- v1.3b: Validated architecture (data persistence, schema readiness, feedback tables)
- v1.3c: Actionable intelligence (revenue leakage, demand gaps, automated optimization)

### The Vision

Build the circular feedback loop:
capture → monitor & evaluate & analyze → learn & derive insights → optimize → repeat

Each cycle should produce:
1. Better content (informed by what keywords/phrases drive performance)
2. Better placement (informed by which tiers convert best for which terms)
3. Better targeting (informed by which audience segments respond to which products)
4. Better spend allocation (informed by real ROAS by product group, not guesses)

### What This Milestone Builds

**Phase 1: Performance-Informed Content Regeneration**
- When a published SKU underperforms, automatically identify WHY (title mismatch?
  description gap? wrong keywords?) using the content↔performance feedback table
- Surface "content improvement opportunities" — SKUs where changing the description
  could improve CTR/CVR based on search term analysis
- Enable "regenerate with performance context" — feed the LLM not just product evidence
  but also "these search terms drive traffic to this product, and your current description
  has a X% CTR for them"

**Phase 2: Cross-System Learning**
- When tier movements improve ROAS for a product group, capture what changed and why
- When content regeneration improves CTR for a product, identify which prompt changes drove it
- Build a "what works" knowledge base that accumulates learning over time
- Feed this learning back into prompt construction (prompt_builder.py) automatically

**Phase 3: Automated Optimization Cycles**
- Daily: Capture performance snapshots, identify underperformers
- Weekly: Generate content improvement recommendations, surface tier rebalancing opportunities
- Monthly: Evaluate content quality trends, regenerate bottom-performing descriptions
- Quarterly: Full review of optimization strategy effectiveness

### Success Criteria
- [ ] Content regeneration uses performance data as input (not just product specs)
- [ ] System can explain WHY a SKU underperforms (content gap vs placement gap vs market gap)
- [ ] Optimization actions create measurable performance improvements (>5% avg CTR lift)
- [ ] The system accumulates learning — each cycle performs better than the last
- [ ] Operator workload decreases over time as automation handles routine optimizations
```

---

## Part 5: What to Update in the Current v1.3 Document

The current `docs/plans/2026-02-21-gsd-milestone-v1.3-actionable-intelligence.md` needs these updates:

### Remove or Correct

1. **Line 17-19**: "However, the user-facing pages... render empty tables" — This is still true, keep it, but clarify that 034b/035b migrations are still deferred
2. **Lines 140-158**: The Intent Execution System tables (migration 035) — these are listed but migration 035b is DEFERRED. Update to note this clearly and distinguish from the measurement infrastructure tables (035) that ARE applied
3. **Lines 75-84**: "These already work" for policy.ts and tier-movement.ts — code exists but backing tables (035b) are not in live database. Update to reflect actual state

### Add

1. **Content quality prerequisite note** at the top: "This milestone assumes content generation quality has been addressed (v1.3a). Optimizing placement for poor-quality content yields limited returns."
2. **Architecture validation prerequisite**: "This milestone assumes data persistence gaps have been addressed (v1.3b), particularly historical funnel data and content↔performance feedback linkage."
3. **Deferred migration status section**: Clearly document which tables exist in live Supabase vs which are deferred

### Keep As-Is

- The technical specification for Phases 1-4 is thorough and well-structured
- The data flow architecture and data sources priority are correct
- The key files to modify/create/not-break lists are accurate
- The performance considerations are valid

---

## Part 6: Where I Agree, Disagree, and What I'd Do Differently

### I Fully Agree

- **Content quality is the foundation.** The "garbage in, garbage out" principle absolutely applies. If our descriptions are generic keyword dumps, Google's algorithm can't understand our products well enough to show them to the right shoppers. Every downstream optimization is limited by input quality.

- **The system works in silos, not as a unit.** Content generation, search term analysis, tier optimization, and performance monitoring are completely disconnected. There's no feedback loop.

- **v1.2 built infrastructure, not outcomes.** 30+ tables, 32 intent files, a measurement infrastructure — all impressive architecture. But the dashboard pages are still empty and the generated content is still generic.

### I Partially Disagree

- **On whether v1.3 (Optimization Intelligence) should wait entirely for content quality fixes.** I think content quality is a 2-3 phase effort, not a full milestone. The current v1.3 scope is 4 phases. We can do content quality first (1.3a) and then immediately build the intelligence system (1.3c). They don't need to be months apart.

- **On whether the architecture needs a full investigation milestone.** The architecture concerns you raised are valid, but most are answerable questions (service.ts persistence, deferred migration evaluation) that can be resolved in 1-2 focused phases rather than a full milestone. I'd keep it as 1.3b (2 phases) rather than blowing it up into a major effort.

### What I'd Do Differently

If I were making the call, I'd merge 1.3a and 1.3b into a single pre-work milestone (call it "v1.3-prep") with 3-4 phases:

1. **Phase A**: Content excellence research + gold examples
2. **Phase B**: Prompt rewrite + category guidance expansion
3. **Phase C**: Architecture audit + critical schema updates
4. **Phase D**: Validation — regenerate 10 SKUs, verify architecture, confirm feedback path

Then proceed directly to v1.3c (the current v1.3 doc) with confidence that the foundation is solid.

---

---

## Part 7: The Deferred Migration (035b) — Why and Should We Apply It?

### Why It Was Deferred

Reading the migration file header, the reasoning is explicit:

> **"Not in v1.2 milestone scope (phases 17-22). The Unified Intent Execution System (bidding policy, search governance, experiment tracking) is a major feature set requiring dedicated implementation work beyond measurement infrastructure."**

In other words: Phase 21 (Apply Database Migrations) had a clear scope — apply the migrations needed for **measurement infrastructure** (034, 035). The intent execution system (035b) was a different, much larger feature set that would create 14 tables for capabilities not yet being used. Applying empty tables to production adds no value and creates maintenance burden.

Interestingly, the deferral note also says: **"Tables were applied out-of-band in a previous session"** and **"STATUS: Tables created out-of-band; this file is reference only."** This suggests the tables MAY have been applied manually at some point during development but the migration was still formally deferred to keep the milestone scope clean.

### What the 14 Tables Are For

| Table | Purpose | Needed for v1.3c? |
|-------|---------|-------------------|
| `intent_taxonomy_versions` | Policy version management | Yes — needed for intent classification |
| `term_intent_state` | Current intent classification per term | Yes — needed for tier movement recommendations |
| `policy_decision_log` | Every policy evaluation logged | Yes — needed for audit trail |
| `policy_action_execution_log` | Every execution action logged | Yes — needed for impact tracking |
| `policy_snapshots` | Point-in-time snapshots | Nice-to-have |
| `sku_margin_daily` | Margin data for ROAS calculations | Yes — needed for true profitability |
| `order_line_returns_daily` | Return data for true profitability | Nice-to-have |
| `attribution_confidence_daily` | Attribution confidence tracking | Nice-to-have |
| `experiment_registry` | Experiment definitions | Yes — needed for A/B testing (Phase 3) |
| `experiment_assignments` | Term-to-experiment assignments | Yes — needed for A/B testing |
| `experiment_outcomes` | Experiment results | Yes — needed for A/B testing |
| `negative_registry` | All negative keywords with audit trail | Yes — critical for tier movement undo |
| `search_buildout_recommendations` | Campaign expansion suggestions | Nice-to-have |
| `operator_review_audit` | Operator action audit trail | Nice-to-have |

### My Recommendation

**Apply 035b during the Architecture Validation phase (1.3b), but selectively.** Here's why:

1. **8 of the 14 tables are prerequisites for v1.3c** (Actionable Intelligence). Without them, the tier movement pipeline, experiment framework, and policy engine can't persist their work.

2. **The TypeScript code already references these tables.** 32 files in `dashboard/src/lib/intent/` are built to work with them. Applying the tables turns dead code into working code.

3. **However**, we should evaluate whether some tables need schema changes before applying. The migration was written months ago — do the table definitions still match what the TypeScript code expects?

4. **The GA4 tables (034b) are lower priority.** The GA4 attribution forensics tables are nice-to-have for v1.3c but not blocking. Evaluate during 1.3b but can be deferred further.

**Bottom line: Apply 035b as part of 1.3b (Architecture Validation), after verifying the schema matches the TypeScript code expectations. This unblocks v1.3c without needing workarounds.**

---

## Part 8: Agent Skills & Multi-Agent Architecture — Honest Assessment

### What I Researched

1. **Agent Skills** (agentskills.io) — An open format originally developed by Anthropic for giving agents specialized capabilities. Skills are folders with a `SKILL.md` file containing instructions, plus optional scripts, references, and assets. Supported by Claude Code, Cursor, Gemini CLI, VS Code, and 25+ other tools.

2. **OpenAI Agents SDK** (openai-agents-python) — A Python framework for building multi-agent systems with agents, handoffs, guardrails, and sessions. Supports 100+ LLMs, not just OpenAI.

3. **Your existing skills** — You already have 6 skills (`preflight`, `checkpoint`, `data-first`, `wrapup`, `verify-deploy`, `repo-audit`) and 1 agent (`merchant-integrator`). The skills framework is already part of your workflow.

### Your Idea: Skills for Content Generation

You suggested:
- Skills for optimal title/description generation per platform (Google, Bing, Shopify)
- Skills for competitor research
- Agents using these skills to complete tasks and report back
- Creative agents (e.g., professional interior designer for design concepts)

### My Honest Assessment

**Skills: Absolutely yes. This is the right tool for the job.**

Skills are the natural solution to the content quality problem identified in Part 2. Here's why:

1. **The content quality problem IS a skills problem.** The generated descriptions are bad because the LLM (GPT-5.2) doesn't have enough context about what "excellent" looks like for each platform and product category. A skill packages that context — creative direction, gold examples, platform rules, customer scenarios, competitive positioning — into a reusable, version-controlled format.

2. **Skills solve the "compliance document vs creative brief" problem.** The current `SYSTEM_PROMPT` in `prompts.py` is 237 lines of rules. A skill can provide creative direction WITH rules, with examples showing what the rules produce when applied well. The LLM doesn't just know what not to do — it knows what good looks like.

3. **Skills are already in your workflow.** You have 6 skills and use them regularly. Adding content generation skills is a natural extension, not a new paradigm.

4. **Skills are portable across tools.** They work in Claude Code, Cursor, VS Code, and other tools. If you ever change your development environment, the skills travel with you.

Here are the skills I'd recommend creating:

| Skill | Purpose | How It's Used |
|-------|---------|---------------|
| `google-shopping-content` | Generate optimal Google Shopping titles and descriptions | Loaded during content generation; provides platform-specific creative direction, title structure rules, description templates, and gold examples for Google Shopping |
| `bing-shopping-content` | Generate optimal Bing Shopping titles and descriptions | Same structure for Bing — longer descriptions, synonym coverage strategy, Bing-specific ad format rules |
| `shopify-conversion-content` | Generate Shopify product pages that convert | HTML structure, buyer psychology hooks, collection coordination, SEO meta descriptions, conversion-optimized copy |
| `competitor-research` | Research and analyze competitor product listings | How to scrape competitor data, what to look for, how to extract positioning insights, competitive advantage identification |
| `product-storytelling` | Turn product specs into compelling narratives | The "interior designer" angle — how to frame a towel bar as a bathroom design element, how to tell the story of solid brass craftsmanship, how to connect features to customer benefits |
| `feed-optimization` | Optimize supplemental feed data for maximum visibility | Custom labels, product types, category optimization, structured data best practices |

**Each skill would include:**
- Creative direction (not just rules — "here's what excellent looks like")
- 5-10 gold standard examples for that platform
- Common mistakes to avoid (with bad→good transformations)
- Category-specific hooks (towel bars, grab bars, soap dispensers, etc.)
- Competitive differentiation guidance
- The `references/` folder with detailed examples and templates

### Multi-Agent Architecture: More Nuanced

**For the content generation pipeline (Cloud Run Python): No, not yet.**

Here's why I'm cautious about adding a full multi-agent framework to the generation pipeline:

1. **Cost multiplication.** Your current pipeline calls GPT-5.2 once per SKU (standard) or ~6 times (6-agent experimental). The OpenAI Agents SDK makes it easy to spawn agents that each make LLM calls. A 3-agent pipeline (researcher → writer → editor) triples your API costs per SKU. At $6-12/1K tokens for frontier models, generating 1,000+ SKUs gets expensive fast.

2. **Latency multiplication.** Each agent handoff is another LLM round-trip. Standard generation is ~3 minutes/SKU. A multi-agent pipeline could be 6-10 minutes/SKU. For batch generation of 50+ SKUs, this adds hours.

3. **Complexity without clear benefit YET.** The content quality problem isn't that we need multiple agents arguing about the description. The problem is that the single agent doesn't have good enough instructions and context. **Skills solve this more efficiently than agents.** Give one agent excellent instructions and examples, and it produces excellent output.

4. **You already HAVE a 6-agent pipeline.** It scored 87.2/100 average (vs 75-80 for standard). But it's 2x slower and only used manually. The quality gain wasn't transformative enough to justify the cost/speed tradeoff. Better instructions would close more of the gap than more agents.

**However, there ARE places where agents would add value:**

| Use Case | Why Agents Help | Implementation |
|----------|----------------|----------------|
| **Competitor research pipeline** | Scraping, analyzing, and summarizing competitor data is genuinely multi-step work that benefits from specialization | Apify Actor → Data extraction agent → Analysis agent → Summary agent |
| **Content quality review** | A separate "editor" agent reviewing generated content catches issues the generator misses | Post-generation review agent with different instructions |
| **Performance analysis** | Analyzing Google Ads data, identifying patterns, and generating recommendations benefits from parallel specialized analysis | Revenue analysis agent + Query analysis agent + Competitive analysis agent |
| **Feedback synthesis** | Combining performance data, search term data, and content quality data into actionable recommendations | Multi-source integration agent |

### The Sweet Spot: Skills Now, Agents Later

Here's what I'd genuinely recommend:

**Phase 1 (v1.3a — Content Excellence): Build skills.**
- Create the 6 content generation skills listed above
- Integrate them into the Python pipeline's `prompt_builder.py` (the skill content becomes part of the prompt context)
- This is low-cost, low-complexity, and directly addresses the content quality problem
- Test and iterate on a small batch of SKUs

**Phase 2 (v1.3b — Architecture): Design the agent framework.**
- Design but don't build the multi-agent architecture
- Define which tasks benefit from agents vs skills vs simple functions
- Set up the evaluation framework so we can measure agent quality vs non-agent quality

**Phase 3 (v1.3c or v1.4 — when optimization is live): Introduce agents selectively.**
- Start with a content review agent (post-generation quality check)
- Add a competitor research agent (Apify-powered)
- Add a performance analysis agent (for the weekly digest)
- Measure cost vs quality improvement for each

### Cost Analysis

| Approach | Cost per SKU | Quality (estimated) | Speed |
|----------|-------------|-------------------|-------|
| Current (GPT-5.2, basic prompt) | ~$0.03-0.08 | 75-81/100 | ~3 min |
| Skills-enhanced (GPT-5.2, rich prompt) | ~$0.05-0.12 | 85-92/100 (est) | ~3.5 min |
| 2-agent (generator + reviewer) | ~$0.10-0.20 | 88-95/100 (est) | ~6 min |
| 3-agent (researcher + generator + reviewer) | ~$0.15-0.30 | 90-97/100 (est) | ~9 min |
| Current 6-agent experimental | ~$0.30-0.60 | 87/100 (measured) | ~6 min |

**Skills give the best quality/cost ratio.** The jump from 75→90 happens mostly from better instructions, not more agents. Adding agents on top of good instructions provides diminishing returns at 2-3x the cost.

### The Interior Designer Idea

I love this idea. A `product-storytelling` or `interior-design-perspective` skill would:
- Frame products as design elements in a room, not just hardware
- Provide scenario-based descriptions: "Picture this towel bar in a Mediterranean-inspired bathroom..."
- Bring the emotional dimension that's completely missing from current descriptions
- Could include references to design trends, color psychology, room layout considerations

This is a SKILL, not an agent. It's instructions and examples that any content generation call can load when needed. And it's the kind of creative direction that transforms "ladder towel rack for bathroom installation" into something that makes a shopper click.

### Can We Do This Programmatically?

Yes, 100%. Skills are just folders with markdown files. Creating them is a writing task, not a coding task. Here's how:

1. **Create skill files** in `.claude/skills/` — each skill is a folder with `SKILL.md`
2. **Reference in prompt pipeline** — the skill content can be loaded by `prompt_builder.py` during generation
3. **Version control** — skills are files in git, so they're versioned and reviewable
4. **Iterate** — update skill content based on generation quality, commit, redeploy

For the Python pipeline specifically, the skill content would be injected into the prompt the same way `shopping_intelligence.yaml` is today — loaded at startup, injected per-SKU based on category/platform. The difference is that skills would contain CREATIVE direction and GOLD EXAMPLES, not just compliance rules.

---

## Part 9: Complete Skill Catalog with Creation Prompts

Each skill below includes a detailed prompt you can paste directly into Claude Code (Opus 4.6) to create the skill. The prompts are designed to produce research-backed, data-driven skills that draw on the existing codebase, competitive intelligence, and real product data.

**Important**: These prompts instruct Claude to research first, then build the skill. Each prompt references the actual files and data in your codebase so the skills are grounded in reality, not generic templates.

### How Skills Fit the Architecture — Dual-Use System

**Skills path: `.claude/skills/`** — This directory IS in your project repo. Existing skills (data-first, preflight, checkpoint, etc.) are already git-tracked here. New skills need `git add -f .claude/skills/<name>/` because the directory is in `.gitignore` by default (Claude Code convention to avoid tracking auto-generated files), but we force-add the ones we want to keep.

**The Dual-Use Approach**: Skills serve TWO purposes, and we should build BOTH layers:

**Layer 1: Claude Code Skills (`.claude/skills/`)** — Full, rich versions with research instructions, anti-patterns, examples, philosophy. Claude (Opus 4.6) reads these when helping you iterate on prompt architecture, evaluate content quality, or build new features. These contain too much meta-guidance and nuance for a runtime prompt.

**Layer 2: Runtime Config Files (`src/feedops/config/`)** — Distilled, concise versions extracted from the skills. Loaded by `prompt_builder.py` and injected DIRECTLY into GPT-5.2's prompt during every content generation. This is the more impactful layer — GPT-5.2 reads the brand voice, finish expertise, platform rules, and quality rubric itself.

The pattern already exists in the codebase:

| Existing Config | Loaded By | Injected Into |
|---|---|---|
| `shopping_intelligence.yaml` | `prompt_builder.py` | Every Google Shopping prompt |
| `segment_strategy.py` | `prompt_builder.py` | Per-segment prompts |
| `collection_descriptions.py` | `prompt_builder.py` | Per-collection prompts |
| `keyword_bank.py` | `prompt_builder.py` | Per-category prompts |

New configs to create from skills:

| New Config | Source Skill | Injected Into |
|---|---|---|
| `brand_voice.yaml` | `allied-brass-brand-expert` | **Every** prompt (universal) |
| `finish_guide.yaml` | `finish-expertise` | Per-finish (variant expansion) |
| `quality_rubric.yaml` | `quality-evaluation` | Self-scoring section |
| `platform_rules.yaml` | google/bing/shopify skills | Per-platform |
| `collection_stories.yaml` | `collection-storytelling` | Per-collection |
| `storytelling_patterns.yaml` | `product-storytelling` | Per-category |

**The flow for each skill:**

```
1. Create Claude Code skill (.claude/skills/) — full version with research, philosophy, examples
2. Extract distilled runtime config (src/feedops/config/) — concise rules GPT-5.2 can use
3. Update prompt_builder.py to load and inject the new config
4. GPT-5.2 generates content with the new knowledge baked into every prompt
```

**Why dual-use?** The Claude Code skill has instructions like "web search for competitor listings" and "query the database for top search terms" — meta-guidance that only makes sense for an AI assistant helping you code. The runtime config has the RESULTS of that research distilled into rules like "always mention solid brass construction as a differentiator" and "for towel bars, lead with the 4-tier design benefit, not the dimensions."

Both layers reinforce each other: Claude uses the skill to IMPROVE the runtime config, and the runtime config ensures GPT-5.2 generates excellent content even without Claude's involvement.

---

### Skill 1: `google-shopping-content`

**Purpose**: Generate Google Shopping titles and descriptions that maximize CTR and conversion by matching how shoppers actually search for bathroom hardware on Google.

**Prompt to create this skill:**

```
I need you to create an Agent Skill at `.claude/skills/google-shopping-content/SKILL.md` for
generating optimal Google Shopping titles and descriptions for Allied Brass products.

DUAL OUTPUT REQUIRED: In addition to the Claude Code skill, UPDATE the existing runtime config
at `src/feedops/config/shopping_intelligence.yaml` to incorporate the creative direction,
gold examples, and platform-specific rules from your research. The current YAML has 15 categories
with template-like rules — rewrite them with genuine creative guidance while preserving the
structure that `prompt_builder.py` expects. This file is loaded at container startup and injected
into every Google Shopping generation prompt that GPT-5.2 executes.

Before writing anything, research the following:

1. Read `src/feedops/config/shopping_intelligence.yaml` — this is our current Google Shopping
   guidance. Understand what rules exist and what's MISSING.

2. Read `src/feedops/pipeline/prompts.py` — this is the current system prompt. Understand the
   P1_GOOGLE_BING_FEED_RULES section and identify where it produces generic/template-like output.

3. Read `docs/research/google-shopping-ranking-factors.md` — this is our Phase 17 research on
   what Google Shopping actually rewards. Extract the key insights.

4. Read `docs/research/competitive-gap-analysis.md` — this is our competitive analysis against
   Kingston Brass, Moen, etc. Extract what competitors do better.

5. Read `docs/research/model-comparison.md` — understand the model capabilities we're working with.

6. Query the `product_catalog` table to get 5-10 real product examples across different categories
   (towel bars, grab bars, soap dispensers, glass shelves, robe hooks). Use these as the basis
   for gold standard examples.

7. Query the `search_queries` table to find the top 20 highest-impression search terms. These
   are what real shoppers type — the skill must teach content to match these queries.

8. Web search for "best Google Shopping title optimization 2026" and "Google Shopping description
   best practices" to get the latest platform guidance.

Now create the skill with these sections:

## SKILL.md Structure

### Frontmatter
- name: google-shopping-content
- description: Generate Google Shopping titles and descriptions optimized for CTR, query matching,
  and conversion. Covers title structure, description architecture, keyword integration, and
  competitive differentiation for luxury bathroom hardware.

### Creative Direction (NOT just rules)
- What makes a shopper CLICK on a Google Shopping listing (not just comply with specs)
- The psychology of Shopping ad browsing — shoppers scan titles in 1-2 seconds
- How to differentiate Allied Brass (solid brass, 28+ finishes, lifetime warranty) from
  mass-market competitors (Kingston Brass zinc alloy, Moen chrome-plated steel, Delta plastic)
- The importance of the first 70 characters (visible in most Shopping placements)
- How to naturally integrate keywords without stuffing

### Title Architecture
- Provide a FLEXIBLE framework, not a rigid template
- Show 5+ variations of excellent titles for the SAME product to demonstrate variety
- Explain WHY each variation works (what search intent it matches)
- Include specific rules: product type in first 30 chars, dimension before char 70, etc.
- Show bad→good transformations with explanation

### Description Architecture
- First 160 characters are critical (visible in Shopping preview)
- How to open with a SENTENCE, not a fragment (fix the "ladder towel rack for bathroom
  installation" problem)
- How to weave in {FINISH_SENTENCE} placeholder naturally
- How to include specs without being a spec dump
- How to address the buyer's actual question: "Is this the right product for my bathroom?"

### Gold Standard Examples
Create 10 gold standard examples across categories:
- Towel Bars (most competitive category, 70,866 impressions/month)
- Grab Bars (741 impressions at 0% CTR — language mismatch problem)
- Glass Shelves, Soap Dispensers, Robe Hooks, Toilet Paper Holders
- For each: show the title, description, and WHY it's excellent

### Category-Specific Hooks
For each of the top 15 product categories (from shopping_intelligence.yaml), provide:
- The primary search intent for this category
- 3-5 differentiating phrases that set Allied Brass apart
- Common shopper objections and how to preemptively address them
- Keyword synonyms to integrate naturally

### Common Mistakes (with fixes)
- Template-following: "X for bathroom installation" → show the fix
- Keyword stuffing: "towel rack towel bar towel holder" → show natural integration
- Generic descriptions that could apply to any brand
- Missing the emotional/practical hook

### references/ folder
Create `references/top-search-terms.md` with the actual top search terms from the database.
Create `references/competitor-analysis.md` with competitive positioning notes.

The skill should be comprehensive enough that ANY LLM reading it would produce significantly
better Google Shopping content than what our current system produces. It should feel like a
senior e-commerce copywriter wrote the brief.
```

---

### Skill 2: `bing-shopping-content`

**Purpose**: Generate Bing Shopping titles and descriptions optimized for Bing's longer description format, synonym coverage strategy, and the Microsoft Shopping audience (often slightly older, higher household income).

**Prompt to create this skill:**

```
I need you to create an Agent Skill at `.claude/skills/bing-shopping-content/SKILL.md` for
generating optimal Bing Shopping titles and descriptions for Allied Brass products.

DUAL OUTPUT REQUIRED: Also create a runtime config at `src/feedops/config/platform_bing.yaml`
that contains Bing-specific rules, synonym coverage maps, and description structure guidance.
This will be loaded by `prompt_builder.py` and injected into GPT-5.2's prompt when generating
Bing content. Keep under 50 lines — concise rules, not verbose guidance.

Before writing anything:

1. Read the google-shopping-content skill — understand the structure and quality bar, but do
   NOT copy Google-specific rules or data. Focus on what's DIFFERENT about Bing.

2. Read `src/feedops/pipeline/prompts.py` — understand the current Bing-specific rules.

3. **BING LIMITS (pre-researched Feb 2026 from official Microsoft API docs)**:
   - Title: 150 chars max (same as Google). Sweet spot: 50-80 chars.
   - Description: **10,000 chars max** (NOT 5,000 — that was Google's limit misapplied by feed tools).
     Source: https://learn.microsoft.com/en-us/advertising/shopping-content/products-resource
   - Same 700-900 char sweet spot as Google applies (diminishing returns beyond 1,000).
   - Front-load key details in first 150-200 chars (similar preview truncation as Google).
   - Microsoft states descriptions "should not contain HTML, symbols such as $ or quotation marks,
     capital letters, or any promotional text."
   - Bing rewards synonym coverage more than Google — use the extra budget for natural synonym
     integration (towel bar/towel rack/towel holder/towel rail in one description).
   Use these findings directly — do NOT re-research limits unless you find contradicting info.

4. Read `src/feedops/pipeline/segment_strategy.py` — understand the synonym_priority system
   that's already built for Bing's longer description format.

5. Read the companion skills that this skill should reference (NOT duplicate):
   - `.claude/skills/allied-brass-brand-expert/SKILL.md` (brand voice)
   - `.claude/skills/quality-evaluation/SKILL.md` (quality rubric — gold standards must score 85+)
   - `.claude/skills/finish-expertise/SKILL.md` (finish language)
   - `.claude/skills/product-storytelling/SKILL.md` (narrative patterns)
   - `.claude/skills/collection-storytelling/SKILL.md` (collection DNA)

CRITICAL MISTAKES TO AVOID (learned from Google skill creation):

- Do NOT include any Google Shopping data, impression counts, CTR percentages, or Google-specific
  search terms. This is Bing-only. No cross-platform data contamination.
- Do NOT assume character limits from other platforms — research Bing's actual limits independently.
- Do NOT treat current Allied Brass performance data as optimization targets. Our current titles
  and descriptions are unoptimized, so all impression/CTR data reflects bad listings. Use data
  DIRECTIONALLY only: vocabulary patterns (what shoppers search) and converted terms (actual
  purchases) are useful. Impression volumes are NOT ceilings and CTR percentages are NOT targets.
- Do NOT rely on legacy gold standard examples from the Supabase `prompt_templates` table. These
  were written before our quality rubric existed and consistently scored 35-48 on the new rubric.
  Create NEW gold standards using the quality-evaluation skill (must score 85+).
- Gold standard descriptions must demonstrate the FULL character budget, not short 200-400 char
  fragments. If Bing allows longer descriptions, the examples should USE that length.

Create the skill with these sections:

### How Bing Differs from Google
- Research and state actual Bing character limits for titles and descriptions
- Different audience demographics (Microsoft Edge users, higher household income, slightly older)
- Bing rewards synonym coverage more than Google (include towel bar/towel rack/towel holder)
- Less competition = opportunity for broader keyword coverage
- Bing often shows more description text in results

### Description Strategy for Bing
- Use the character budget for NATURAL synonym coverage, not keyword stuffing
- Include product use-case scenarios
- Address secondary search intents (installation ease, gift-worthiness, bathroom renovation)
- More room for the "why Allied Brass" story
- Integrate brand voice from allied-brass-brand-expert skill

### Title Optimization for Bing
- Research Bing-specific title requirements
- Include secondary dimensions or features that don't fit in Google titles
- How Bing's matching algorithm differs from Google's

### Gold Standard Examples
- 8 examples showing the Bing-specific approach (descriptions must be FULL length, not fragments)
- Side-by-side comparison: same product, Google title vs Bing title, Google desc vs Bing desc
- Each gold standard must score 85+ on the quality-evaluation rubric
- Highlight what's different and why

### Synonym Coverage Framework
For each product category, provide a synonym map:
- Primary term → all natural synonyms
- Example: "towel bar" → "towel rack", "towel holder", "towel rail", "bath towel bar"
- Show how to weave 3-4 synonyms naturally into a single description paragraph

### Data Caveat
Include a "Garbage In, Garbage Out" section explaining that current performance data reflects
unoptimized listings. Use converted search terms directionally. Use vocabulary patterns. Do not
use impression volumes as ceilings or CTR percentages as targets.

The skill should enable content that is clearly optimized for Bing's platform rather than
being a copy-paste of Google content with minor tweaks.
```

---

### Skill 3: `shopify-conversion-content`

**Purpose**: Generate Shopify product titles, descriptions, and meta descriptions that convert browsers into buyers on the alliedbrass.com storefront.

**Prompt to create this skill:**

```
I need you to create an Agent Skill at `.claude/skills/shopify-conversion-content/SKILL.md`
for generating Shopify product page content that converts.

DUAL OUTPUT REQUIRED: Also create a runtime config at `src/feedops/config/platform_shopify.yaml`
that contains Shopify-specific voice rules, HTML structure patterns, meta description templates,
and conversion copy principles. Loaded by `prompt_builder.py` when generating Shopify content
for GPT-5.2. Keep under 50 lines.

Before writing anything:

1. Read `src/feedops/pipeline/prompts.py` — understand the P1_SHOPIFY_CONVERSION_RULES section.

2. Read `src/feedops/pipeline/collection_descriptions.py` — understand how collection data is
   loaded and used. Read the CSV at `data/Collection_Descriptions_Complete_All_41_20260124.csv`
   to understand what collection descriptions exist.

3. Use Claude in Chrome to visit https://www.alliedbrass.com and browse 3-4 product pages
   (towel bar, grab bar, soap dispenser, glass shelf). Note the current page layout, what
   content appears where, and how the description is displayed.

4. **SHOPIFY LENGTH BEST PRACTICES (pre-researched Feb 2026)**:
   - No hard character limit for product descriptions.
   - Meta title: 60-70 chars (Google SERP display limit). Meta description: 155-160 chars.
   - Description sweet spot: **250-400 words (1,250-2,000 chars)** with a two-tier structure:
     * Above the fold: 2-3 sentences, lifestyle-focused, benefit-driven hook
     * Below the fold: Specs (bullet points), finish details, dimensions, mounting, collection story
   - Luxury/home goods specifically: "You might need longer copy for certain luxury items, because
     you may be making a case for lifestyle benefits." (Source: Stellar Content)
   - Minimum for SEO benefit: 200-300 words (confirmed by multiple sources).
   - Conversion lift from well-structured descriptions: **10-30%** (published A/B test data).
   - Readability and scannability matter MORE than word count — use headers and bullets.
   - "Cutting text length by 54% not only made readers able to find and remember information more
     easily, but also scored it as more complete than the longer version." (Source: AirOps)
   Use these findings directly — do NOT re-research lengths unless you find contradicting info.

5. Query the `product_catalog` table to understand what product data is available (title,
   description, category, collection, dimensions, specs).

6. Study the existing Shopify descriptions on alliedbrass.com — identify patterns, strengths,
   and weaknesses in the current copy.

7. Read the companion skills that this skill should reference (NOT duplicate):
   - `.claude/skills/allied-brass-brand-expert/SKILL.md` (brand voice)
   - `.claude/skills/quality-evaluation/SKILL.md` (quality rubric — gold standards must score 85+)
   - `.claude/skills/finish-expertise/SKILL.md` (finish language)
   - `.claude/skills/product-storytelling/SKILL.md` (narrative patterns)
   - `.claude/skills/collection-storytelling/SKILL.md` (collection DNA)

CRITICAL MISTAKES TO AVOID (learned from Google skill creation):

- Do NOT include any Google Shopping or Bing data, impression counts, CTR percentages, or feed-
  specific search terms. Shopify is a different context entirely — on-site conversion, not ad CTR.
- Do NOT assume character limits from Google or Bing. Research Shopify-specific optimal lengths.
- Do NOT treat current Allied Brass performance data as optimization targets. Current content is
  unoptimized — all metrics reflect bad listings. Use data directionally only.
- Do NOT rely on legacy gold standard examples from Supabase `prompt_templates`. These scored
  35-48 on the quality rubric. Create NEW gold standards (must score 85+ on quality-evaluation).
- Gold standard descriptions must demonstrate the FULL recommended length, not short fragments.
- Shopify allows HTML — this is fundamentally different from Shopping feeds (plain text only).

Create the skill with these sections:

### The Shopify Buyer Journey
- Someone on alliedbrass.com is already past the discovery phase (they found you)
- They're comparing you against 2-3 other options they have open in tabs
- The description must answer: "Why THIS product from THIS company?"
- Different from Shopping ads — this is conversion copy, not discovery copy

### HTML Structure That Converts
- Opening <p> with a buyer scenario or pain point (not a product spec)
- <ul><li> blocks for scannable features and benefits
- Trust signals (material quality, warranty, what's included)
- Collection coordination hook (when applicable)
- Size/installation context that reduces purchase anxiety
- Research and state the optimal description length for Shopify product pages

### Title Strategy (H1 on product page)
- Finish-agnostic (master SKU level)
- Must NOT include "Allied Brass" (brand is already in header)
- Should include collection name and product type
- H1-friendly: reads well as a page heading, not a search query

### Meta Description Strategy
- 140-155 characters, standalone (may appear in Google organic results)
- Must include primary keyword naturally
- Must include a clear value proposition
- Should create curiosity or urgency without hype

### Gold Standard Examples
- 8 examples showing the full Shopify output: title, description HTML, meta description
- Each gold standard must score 85+ on the quality-evaluation rubric
- For each, annotate WHY each section works for conversion
- Show the "buyer objection → answer" mapping in each example
- Descriptions must demonstrate full recommended length, not short fragments

### Collection Coordination
- When collection data exists, how to use it as a design-story hook
- "Complete the look" framing — suggest other pieces from the same collection
- How to reference the collection's design aesthetic without being generic

### Data Caveat
Include a section explaining that current performance data reflects unoptimized listings.
Shopify conversion rates, bounce rates, and engagement metrics from current pages do NOT
represent what optimized content can achieve. Use patterns directionally only.

### The Allied Brass Shopify Voice
- Confident and specific (not "luxurious" or "premium" — show, don't tell)
- Practical expertise ("solid brass means it won't corrode in humid bathrooms")
- Design-aware ("coordinates with modern transitional and traditional styles")
- Helpful ("includes all mounting hardware for standard drywall installation")
- Must align with brand voice from allied-brass-brand-expert skill
```

---

### Skill 4: `product-storytelling`

**Purpose**: Transform product specifications into compelling narratives that connect features to real customer scenarios, design aesthetics, and emotional benefits. This is the "interior designer" perspective.

**Prompt to create this skill:**

```
I need you to create an Agent Skill at `.claude/skills/product-storytelling/SKILL.md` that
teaches AI to write about bathroom hardware as a professional interior designer would — with
design context, customer scenarios, and emotional resonance.

DUAL OUTPUT REQUIRED: Also create a runtime config at `src/feedops/config/storytelling_patterns.yaml`
that contains per-category narrative frameworks (customer scenarios, design style hooks, feature-
to-benefit translations) that GPT-5.2 can use directly. Organized by product category so
`prompt_builder.py` can inject the relevant section per SKU. Keep each category to 5-8 lines.

This is NOT about SEO or platform compliance. This skill is about CRAFT — turning a spec sheet
into a story that makes someone want to buy.

Before writing anything:

1. Web search for "interior design bathroom hardware trends 2026", "bathroom renovation
   inspiration", "luxury bathroom accessories design", and "how interior designers describe
   hardware".

2. Visit alliedbrass.com using Claude in Chrome and look at the collection pages — understand
   the design aesthetics of different collections (Carolina, Waverly Place, Montero, etc.).

3. Read the collection descriptions CSV at
   `data/Collection_Descriptions_Complete_All_41_20260124.csv` to understand each collection's
   design language.

4. Web search for how competitors like Restoration Hardware, Pottery Barn, and West Elm describe
   their bathroom hardware. These brands excel at lifestyle storytelling.

5. Search for "bathroom design styles" (traditional, transitional, modern, coastal, farmhouse,
   industrial) and how each style uses hardware differently.

Create the skill with these sections:

### The Interior Designer's Perspective
- A professional designer doesn't see a "towel bar" — they see a design element that anchors
  the bathroom's visual language
- How to frame hardware as an intentional design choice, not a commodity purchase
- The concept of "jewelry for the bathroom" — how finish selection is a personal expression
- How different materials (solid brass vs zinc, chrome vs nickel) create different room moods

### Customer Scenario Library
For each major product category, provide 3-4 customer scenarios:
- The renovator: "You're finally updating that builder-grade bathroom..."
- The designer: "When every detail matters..."
- The practical buyer: "You need a towel bar that holds up to daily family use..."
- The gift buyer: "Looking for a housewarming gift that makes an impression..."
Show how the same product is described differently for each scenario.

### Design Style Hooks
For each major design style, provide language and framing:
- **Traditional**: Timeless elegance, classical proportions, enduring style
- **Transitional**: Clean meets classic, versatile, bridges modern and traditional
- **Modern/Contemporary**: Minimal lines, understated, sculptural simplicity
- **Coastal**: Relaxed sophistication, corrosion-resistant (solid brass!), breezy
- **Farmhouse/Rustic**: Warm tones, handcrafted character, durable construction
- **Industrial**: Exposed hardware aesthetic, raw material honesty, robust construction

### Finish as Design Language
For each of the 28 Allied Brass finishes, provide:
- What design styles it complements
- What room moods it creates
- What other fixtures/hardware it pairs with
- 1-2 sentences showing how to describe the finish in context (not "Available in Polished
  Nickel" but "The Polished Nickel finish reflects light to brighten smaller bathrooms while
  coordinating with chrome-tone fixtures")

### Feature-to-Benefit Translation
A reference table turning specs into stories:
| Spec | Feature | Benefit | Story |
|------|---------|---------|-------|
| Solid brass | Premium material | Won't corrode or tarnish | "Solid brass construction means this towel bar will look the same in ten years as the day you installed it" |
| Concealed mounting | Clean installation | No visible screws | "Concealed mounting hardware keeps the focus on the design, not the installation" |
| 20 lb capacity | Strong | Holds wet towels | "Engineered to hold the real weight of damp bath sheets, not just display towels" |
| Lifetime warranty | Durability guarantee | Buy once | "Backed by a limited lifetime warranty — one less thing to replace" |

### The Art of the Opening Sentence
- 20 examples of opening sentences that AREN'T "X for bathroom installation"
- Organized by approach: scenario-first, benefit-first, design-first, problem-first
- Each with annotation explaining why it works

### What NOT to Do (Anti-Patterns)
- "This beautiful towel bar..." (vague adjective)
- "Available in Polished Nickel" as a sentence (boring)
- "Upgrade your bathroom" (generic, tells nothing about THIS product)
- Starting every description the same way
```

---

### Skill 5: `lifestyle-image-generation`

**Purpose**: Generate AI lifestyle images that show products in realistic, aspirational bathroom and kitchen settings with accurate finish rendering and composition.

**Prompt to create this skill:**

```
I need you to create an Agent Skill at `.claude/skills/lifestyle-image-generation/SKILL.md`
for generating optimal AI lifestyle images for Allied Brass products.

DUAL OUTPUT REQUIRED: Also UPDATE the existing runtime module at
`src/feedops/pipeline/lifestyle_images.py` — specifically enhance the FINISH_LIGHTING dict
with richer rendering guidance and expand CATEGORY_SCENE with more specific scene direction
based on your research. This module is used directly by Gemini Imagen API during image
generation. Also create `src/feedops/config/image_scenes.yaml` if the guidance exceeds what
fits cleanly in the Python dict.

Before writing anything:

1. Read `src/feedops/pipeline/lifestyle_images.py` — this is the current image generation
   module using Gemini Imagen API. Understand the FINISH_LIGHTING dict (28 finishes),
   CATEGORY_SCENE dict, and _build_enhanced_image_prompt() function.

2. Read `src/feedops/pipeline/collection_descriptions.py` — understand how collection design
   language is used in image generation.

3. Read the Phase 20 verification report at
   `.planning/milestones/v1.2-phases/20-targeted-fixes-intelligence-application/20-VERIFICATION.md`
   — understand the image generation improvements that were already made (PRODUCT FIDELITY as
   first non-negotiable).

4. Web search for "AI product photography best practices 2026", "lifestyle product photography
   for e-commerce", "Google Merchant Center image requirements", and "Gemini Imagen API best
   practices".

5. Query `product_lifestyle_images` and `variant_lifestyle_images` tables to understand what
   images have been generated and their current quality.

6. Visit alliedbrass.com product pages to see how lifestyle images are currently displayed.

Create the skill with these sections:

### Image Generation Philosophy
- Product must be RECOGNIZABLE and ACCURATE — this is the #1 rule
- The setting tells a story: "where does this product live?"
- Finish accuracy is non-negotiable — Polished Chrome looks different from Polished Nickel
- Aspirational but believable — a real bathroom, not a CGI showroom

### Finish Rendering Guide
For each of the 28 finishes, provide:
- Lighting direction and color temperature
- Background materials and colors that complement the finish
- Common rendering failures and how to avoid them in prompts
- Reference to the existing FINISH_LIGHTING dict in lifestyle_images.py

### Category Scene Guide
For each product category:
- Optimal room context (master bath, guest bath, powder room, kitchen)
- Recommended camera angle and composition
- What other elements to include in the scene (towels, plants, decor)
- What to EXCLUDE (competing products, brand logos, text overlays)

### Google Merchant Center Image Requirements
- Image quality standards (resolution, background, borders)
- What Google allows/disallows for AI-generated product images
- digital_source_type compliance requirements
- How lifestyle images differ from product-only images in GMC

### Prompt Engineering for Imagen
- How to structure prompts for Gemini Imagen specifically
- Positive prompting (describe what you WANT, not what you don't want)
- Finish-specific prompt modifiers that produce accurate results
- Composition terms that produce good product-in-context shots
- Common failure modes and prompt fixes

### Quality Evaluation Criteria
- Product accuracy: Is it recognizably the correct product?
- Finish accuracy: Is the finish rendered correctly?
- Scene plausibility: Does the bathroom/kitchen setting look real?
- Composition: Is the product prominently featured without being awkward?
- Lighting: Does the lighting enhance the product and finish?

### references/ folder
Create `references/finish-lighting-guide.md` with detailed finish-by-finish guidance.
Create `references/category-scenes.md` with scene direction per product type.
```

---

### Skill 6: `competitor-research`

**Purpose**: Research and analyze competitor product listings, pricing, and positioning to inform content strategy and competitive differentiation.

**Prompt to create this skill:**

```
I need you to create an Agent Skill at `.claude/skills/competitor-research/SKILL.md` for
conducting systematic competitor research for Allied Brass product optimization.

Before writing anything:

1. Read `docs/research/competitive-gap-analysis.md` — this is our Phase 17 competitive analysis.
   Understand what was already discovered about Kingston Brass, Moen, Signature Hardware, etc.

2. Read `src/feedops/pipeline/competitor_evidence.py` — understand the existing competitor
   evidence pipeline.

3. Read `dashboard/src/lib/optimization/query-intelligence.ts` — understand the 16 competitor
   tokens already identified in the NLP decomposition.

4. Web search for "bathroom hardware market competitors 2026", "Kingston Brass vs Allied Brass",
   "luxury bathroom accessories brands comparison".

5. Check what Apify Actors are available for scraping Google Shopping, Amazon, and Home Depot
   product listings.

Create the skill with these sections:

### Competitor Landscape
Map of all known competitors with positioning:
- **Direct competitors**: Kingston Brass, Elements of Design, Barclay Products
- **Mass-market competitors**: Moen, Delta, Kohler, Glacier Bay
- **Premium competitors**: Signature Hardware, Restoration Hardware, Pottery Barn
- For each: price tier, material quality, distribution channels, key differentiators

### Research Methodology
Step-by-step process for competitive research:
1. Identify the product category and specific Allied Brass SKU
2. Find competitor equivalents (Google Shopping search, Amazon search)
3. Extract: title structure, description content, pricing, reviews, images
4. Analyze: What do they highlight that we don't? What do we offer that they don't?
5. Synthesize: Competitive positioning recommendations for content generation

### Using Apify for Research
- Which Apify Actors to use for Google Shopping scraping
- How to search Amazon for competing products
- How to scrape Home Depot and Wayfair listings
- Rate limiting and cost considerations

### Competitive Intelligence Framework
For each competitor product found:
- Title analysis: What keywords do they lead with?
- Description analysis: What benefits do they emphasize?
- Image analysis: How do they present the product?
- Review mining: What do THEIR customers praise/complain about?
- Pricing comparison: How do we compare on value?

### Turning Research into Content Advantage
- How to use competitor weaknesses as Allied Brass strengths
- "They use zinc alloy, we use solid brass" — how to position this
- "They don't mention warranty, we have lifetime warranty" — trust signals
- "Their descriptions are generic too" — where we can differentiate first-mover

### Data Storage and Reuse
- How to store competitor research for reuse across SKUs
- Integration with the evidence builder for content generation
- Keeping research current (recommended refresh cadence)
```

---

### Skill 7: `feed-optimization`

**Purpose**: Optimize supplemental feed data (product types, custom labels, structured data, categories) for maximum visibility across Google Shopping and Bing Shopping.

**Prompt to create this skill:**

```
I need you to create an Agent Skill at `.claude/skills/feed-optimization/SKILL.md` for
optimizing the Google Merchant Center supplemental feed data.

Before writing anything:

1. Read `dashboard/src/lib/publishing/google-sheets.ts` — understand the current supplemental
   feed structure (columns A-N).

2. Read `dashboard/src/lib/publishing/expand-variants.ts` — understand how variant expansion works.

3. Read the CLAUDE.md section on "Google Sheets Feed Structure" for the current column layout.

4. Read `docs/research/google-shopping-ranking-factors.md` for feed-controllable ranking factors.

5. Web search for "Google Merchant Center feed optimization 2026", "structured_title and
   structured_description best practices", "Google Shopping product_type taxonomy", and
   "custom_label optimization strategies".

6. Query the `variant_index` table to understand the current product catalog structure
   (how many products, categories, finishes).

Create the skill with these sections:

### Feed Architecture Overview
- What each supplemental feed column does and why it matters
- How the supplemental feed interacts with Shopify's primary feed
- What Google prioritizes: structured_title > title, structured_description > description
- The role of custom_label_0 through custom_label_4 in campaign management

### Product Type Taxonomy
- Best practices for google_product_category selection
- How to build a product_type hierarchy (Home & Garden > Bathroom > Towel Racks > Towel Bars)
- Impact of category accuracy on auction eligibility

### Structured Fields Strategy
- When to use structured_title vs regular title
- structured_description format with digital_source_type
- How structured fields interact with AI-generated content declarations

### Custom Label Strategy
- custom_label_0: Product group (campaign structure mapping)
- custom_label_1-4: Available for additional segmentation
- Ideas: margin tier, seasonality flag, competitive priority, content quality score

### MPN Best Practices
- Format: {master_sku}-{finish_code}
- Why MPN matters for product matching and deduplication
- Handling new rows vs existing rows

### Feed Health Monitoring
- Common disapproval reasons and how to prevent them
- Data quality checks to run before publishing
- How to use GMC diagnostics to identify feed issues

### Pattern Column Optimization
- What goes in the "pattern" column for bathroom hardware
- How pattern data helps Google match products to queries
```

---

### Skill 8: `finish-expertise`

**Purpose**: Deep expertise on all 28+ Allied Brass finishes — how to describe them compellingly, what design styles they complement, and how to differentiate them in content. This is a critical knowledge gap because finish descriptions are currently handled by a simple {FINISH_SENTENCE} placeholder.

**Prompt to create this skill:**

```
I need you to create an Agent Skill at `.claude/skills/finish-expertise/SKILL.md` that provides
deep expertise on Allied Brass finishes for content generation.

DUAL OUTPUT REQUIRED: Also create a runtime config at `src/feedops/config/finish_guide.yaml`
containing per-finish entries with: visual description, design style fit, compelling sentence
examples (3-4 varied options per finish), and search keywords. This is loaded by
`prompt_builder.py` and injected per-finish during variant expansion so GPT-5.2 generates
unique, compelling finish sentences instead of generic "{FINISH_SENTENCE}" placeholders.

This is critical because: finish is the PRIMARY variant differentiator for Allied Brass. Every
master SKU has 17-28 finish variants. The {FINISH_SENTENCE} placeholder in descriptions is
supposed to be expanded per-variant, but currently produces generic sentences. Each finish
variant competes separately in Google Shopping — the finish description IS the differentiator.

Before writing anything:

1. Read `src/feedops/pipeline/lifestyle_images.py` — extract the complete FINISH_LIGHTING dict
   with all 28 finish descriptions.

2. Read `src/feedops/pipeline/finish_injection.py` — understand how finish sentences are
   currently generated and injected.

3. Read `src/feedops/pipeline/finish_sentence_validation.py` — understand finish sentence rules.

4. Visit alliedbrass.com and look at how finishes are displayed on product pages. Note the
   finish swatch images and descriptions.

5. Web search for "bathroom hardware finish guide", "polished nickel vs brushed nickel",
   "oil rubbed bronze bathroom", "brass bathroom fixtures trend 2026" — understand how
   real shoppers think about and search for finishes.

6. Query the `variant_index` table to get a count of how many variants exist per finish
   across the catalog.

Create the skill with these sections:

### Why Finish Expertise Matters
- Finish is the #1 variant differentiator in Google Shopping
- "polished nickel towel bar" and "oil rubbed bronze towel bar" are DIFFERENT queries
  with different buyer intent
- Most competitors use the same generic finish descriptions — opportunity to differentiate
- Finish choice is deeply personal — it reflects design taste, existing fixtures, room mood

### The 28 Finishes — Complete Guide
For EACH of the 28 Allied Brass finishes, provide:

**[Finish Name]**
- **Visual description**: What it actually looks like (color, sheen, texture)
- **Design style fit**: Which bathroom styles it complements best
- **Pairs with**: Other fixture finishes/materials it coordinates with
- **Popular with**: Who buys this finish (new construction, renovation, designer, etc.)
- **Search behavior**: How shoppers search for this finish (keywords, synonyms)
- **Compelling sentence**: 2-3 sentence examples of how to describe this finish in context
- **Avoid**: Common mistakes when describing this finish

Group finishes by family:
- Classic metals: Polished Brass, Satin Brass, Unlacquered Brass, Antique Brass
- Chrome family: Polished Chrome, Satin Chrome
- Nickel family: Polished Nickel, Satin Nickel, Antique Pewter
- Bronze family: Antique Bronze, Brushed Bronze, Oil Rubbed Bronze, Venetian Bronze
- Copper: Antique Copper
- Modern: Matte Black, Matte Gray, Matte White
- Designer colors: Fire Engine Red, Lavender, Mediterranean Blue, Pink, Golden Yellow,
  Flat Troll Blue, Sea Foam Green, Autumn Sparkle, Glokzin Teal, Shaded Beige, Spanish Gold

### Finish Sentence Templates (NOT rigid templates)
For each finish family, provide 5-8 varied sentence starters that describe the finish
naturally in context. The goal is VARIETY — no two products with the same finish should
have identical finish sentences.

### Finish Comparison Language
How to subtly differentiate finishes from each other:
- Polished Chrome vs Polished Nickel (the most common customer confusion)
- Satin Brass vs Unlacquered Brass (living finish vs static)
- Oil Rubbed Bronze vs Venetian Bronze (dark warm vs medium warm)

### references/ folder
Create `references/finish-visual-guide.md` with the complete 28-finish reference.
Create `references/finish-search-keywords.md` with search term data per finish.
```

---

### Skill 9: `quality-evaluation`

**Purpose**: Evaluate generated content quality using a rubric that measures what actually matters for performance (not just compliance). Replaces the current self-scoring system that gives 81% to bad descriptions.

**Prompt to create this skill:**

```
I need you to create an Agent Skill at `.claude/skills/quality-evaluation/SKILL.md` for
evaluating the quality of generated product content.

DUAL OUTPUT REQUIRED: Also create a runtime config at `src/feedops/config/quality_rubric.yaml`
that contains the new 10-criterion scoring rubric with weights and anchor descriptions.
This replaces the current 6-criterion self_score section in CANDIDATE_SCHEMA (prompts.py).
GPT-5.2 uses this to score its own output — the rubric must be concise enough to fit in
the prompt but specific enough to prevent the current problem of 81% scores for bad content.
Keep under 40 lines.

The current quality scoring system in our pipeline gives an 81% score to descriptions like
"ladder towel rack for bathroom installation. {FINISH_SENTENCE} Solid brass. 18-inch
center-to-center..." — which is terrible content. The scoring rubric rewards compliance
(did you follow the rules?) rather than quality (would a shopper click this?).

Before writing anything:

1. Read `src/feedops/pipeline/prompts.py` — look at the CANDIDATE_SCHEMA self_score section
   to understand the current 6-criterion rubric.

2. Read the CL-28-18 analysis in `docs/plans/2026-02-21-strategic-milestone-assessment.md`
   Part 2 to understand WHY 81% is a misleading score.

3. Web search for "content quality evaluation for e-commerce", "Google Shopping ad copy
   testing", "product description A/B testing metrics", "CTR prediction from ad copy quality".

4. Query the `generated_content` table to find 10 examples of generated descriptions across
   different categories. Read them and evaluate them honestly.

5. Think about what predicts a CLICK in Google Shopping — what makes a shopper choose one
   listing over another when the product image and price are similar.

Create the skill with these sections:

### Why the Current Scoring Fails
- The 6 current criteria (specificity, benefit_coverage, keyword_inclusion, format_adherence,
  brand_voice, factual_accuracy) measure compliance, not quality
- format_adherence (10/10) and brand_voice (9/10) inflate scores for bad content
- Missing: differentiation, emotional resonance, opening hook quality, competitive positioning

### The New Quality Framework (10 criteria)
1. **Hook Quality** (0-10): Does the opening sentence make you want to read more?
   - 0: Fragment or keyword dump
   - 5: Grammatically correct but generic opener
   - 10: Specific, engaging opening that identifies the product and its value
2. **Product Specificity** (0-10): Could this description ONLY describe this exact product?
   - 0: Could describe any towel bar from any brand
   - 5: Mentions brand/collection but still generic features
   - 10: Uniquely identifies this product with specific dimensions, design details, use context
3. **Competitive Differentiation** (0-10): Does it explain why THIS product over alternatives?
   - 0: No differentiation at all
   - 5: Mentions solid brass or warranty but generically
   - 10: Clear competitive advantages woven naturally into the narrative
4. **Keyword Integration** (0-10): Are search terms included naturally?
   - 0: No relevant keywords OR obvious keyword stuffing
   - 5: Keywords present but awkwardly inserted
   - 10: Keywords flow naturally within compelling copy
5. **Customer Scenario** (0-10): Does it connect to a real buying situation?
   - 0: Pure spec dump, no human context
   - 5: Generic "upgrade your bathroom" type framing
   - 10: Specific scenario (renovation, guest bath, matching fixtures) that resonates
6. **Emotional Resonance** (0-10): Does it make you FEEL something about the product?
   - 0: Reads like a database export
   - 5: Pleasant but forgettable
   - 10: Creates desire, confidence, or excitement about ownership
7. **Factual Accuracy** (0-10): Are all claims verifiable from evidence?
   - Binary: 10 if accurate, 0 if any fabricated claims
8. **Platform Compliance** (0-10): Does it meet platform-specific requirements?
   - Title length, description format, HTML structure (Shopify), etc.
9. **Finish Integration** (0-10): Is the finish described naturally and compellingly?
   - 0: "{FINISH_SENTENCE}" placeholder or "Available in X"
   - 5: Finish mentioned but generically
   - 10: Finish woven into the description as a design choice
10. **Variety Score** (0-10): Is this description noticeably different from others in the catalog?
    - 0: Identical sentence structure to other product descriptions
    - 5: Different words, same pattern
    - 10: Unique structure, voice, and approach

### Scoring Methodology
- Each criterion scored 0-10 with specific anchors
- Overall quality = weighted average:
  - Hook Quality: 15% (most impactful for CTR)
  - Product Specificity: 15%
  - Competitive Differentiation: 12%
  - Keyword Integration: 10%
  - Customer Scenario: 10%
  - Emotional Resonance: 10%
  - Factual Accuracy: 10% (binary pass/fail inflated to weight)
  - Platform Compliance: 8%
  - Finish Integration: 5%
  - Variety Score: 5%
- Grade thresholds: <60 = Reject, 60-74 = Needs Work, 75-84 = Acceptable, 85-94 = Good, 95+ = Excellent

### Evaluation Process
Step-by-step guide for evaluating a generated description:
1. Read the description cold — what's your gut reaction?
2. Score each criterion independently
3. Identify the #1 weakness and #1 strength
4. Generate specific improvement suggestions
5. Compare against the gold standard for this category

### Bad → Good Examples
10 real examples (from actual generated content) showing:
- The original (with scores per criterion)
- What's wrong (specific, actionable critique)
- The improved version (with new scores)
- What changed and why it matters
```

---

### Skill 10: `collection-storytelling`

**Purpose**: Leverage Allied Brass's 41 collections as a design-story differentiator. Collections (Carolina, Waverly Place, Montero, Continental, etc.) are a major competitive advantage that's completely underutilized in current content.

**Prompt to create this skill:**

```
I need you to create an Agent Skill at `.claude/skills/collection-storytelling/SKILL.md` for
leveraging Allied Brass's collection system in content generation.

DUAL OUTPUT REQUIRED: Also create a runtime config at `src/feedops/config/collection_stories.yaml`
with per-collection entries (all 41) containing: design aesthetic (2-3 sentences), style category,
target buyer, and 2 content integration examples. This is loaded by `prompt_builder.py` and
injected per-collection so GPT-5.2 weaves collection identity into product descriptions.
This supplements the existing `collection_descriptions.py` CSV with storytelling guidance.

Allied Brass has 41 named collections, each with a distinct design aesthetic. This is a MAJOR
competitive advantage — Kingston Brass, Moen, and Delta don't offer coordinated collections
of bathroom accessories. But our current content barely mentions collections.

Before writing anything:

1. Read `data/Collection_Descriptions_Complete_All_41_20260124.csv` — get the full list of
   41 collections with their existing descriptions.

2. Read `src/feedops/pipeline/collection_descriptions.py` — understand how collection data
   is currently loaded and used.

3. Visit alliedbrass.com using Claude in Chrome and browse 3-4 collection pages to understand
   how collections are merchandised on the site.

4. Web search for "bathroom accessories coordinated collection", "matching bathroom hardware
   set", "bathroom renovation coordinating fixtures" — understand how shoppers think about
   collections.

5. Query the `product_catalog` table to understand which collections have the most products
   and which are most popular.

Create the skill with these sections:

### Why Collections Matter for Content
- Coordinated design is a premium buyer expectation
- "Complete the look" is one of the strongest conversion hooks in home decor
- Collections solve the "will this match?" anxiety that kills conversions
- Competitors don't offer this — it's a genuine differentiator

### Collection Profiles
For each of the 41 collections, provide:
- **Design aesthetic**: 2-3 sentence description of the collection's visual language
- **Style category**: Traditional, transitional, modern, contemporary, etc.
- **Target buyer**: Who gravitates toward this collection
- **Key design elements**: What makes this collection visually distinctive
- **Coordination hook**: How to mention other products in the same collection
- **1-2 content examples**: How to weave the collection story into a product description

### Collection Integration Patterns
Different ways to mention collections in content:
1. **Opening hook**: "Part of the Carolina Collection, this towel bar brings traditional warmth..."
2. **Closing coordination**: "Coordinates with other Carolina Collection pieces for a unified look"
3. **Design story**: "The Montero Collection draws from mid-century modern lines..."
4. **Problem-solution**: "Tired of mismatched bathroom accessories? The Waverly Place Collection..."
5. **Subtle mention**: "...in the signature clean lines of the Continental Collection"

### When NOT to Mention Collections
- Google Shopping descriptions where character count is tight
- If no collection data exists for the product
- If the collection name doesn't add meaningful design context
- Don't force collection mentions — they should feel natural

### Cross-Selling Language
How to suggest related products WITHOUT being pushy:
- "Pairs beautifully with the matching towel ring and robe hook"
- "Part of a full bathroom accessory collection"
- "Designed to coordinate with matching accessories in the same finish"
```

---

### Skill 11: `allied-brass-brand-expert`

**Purpose**: Encode the soul of Allied Brass — what makes this company special, why customers become loyal, and how to make every piece of content carry the passion of the world's #1 Allied Brass fan. This skill applies marketing psychology principles (emotional anchoring, authority, reciprocity, social proof) to create content that subconsciously builds brand loyalty and emotional connection.

**Why this skill is foundational**: Every other skill (Google Shopping, Bing, Shopify, storytelling) needs a unified brand voice and brand truth to draw from. Without this, each platform skill optimizes in isolation. WITH this, every piece of content carries the same authentic conviction regardless of platform.

**Prompt to create this skill:**

```
I need you to create an Agent Skill at `.claude/skills/allied-brass-brand-expert/SKILL.md` that
transforms any AI writing about Allied Brass products into content that reads like it was written
by the world's most passionate, knowledgeable brand advocate — someone who genuinely believes
Allied Brass makes the best bathroom hardware available and can articulate WHY in a way that
creates emotional connection and subconscious brand loyalty.

This is NOT a marketing template. This is about TRUTH — finding what is genuinely special about
Allied Brass and expressing it so compellingly that customers feel it.

CRITICAL: This skill must also produce a RUNTIME CONFIG file. In addition to the Claude Code
skill at `.claude/skills/allied-brass-brand-expert/SKILL.md`, create a distilled runtime config
at `src/feedops/config/brand_voice.yaml` that `prompt_builder.py` can load and inject into
every GPT-5.2 prompt. The runtime config should contain:
- 5-8 core brand truths (concise, factual, differentiated)
- Brand voice rules (3-5 rules, with positive examples and anti-patterns)
- The "one-two punch" framework distilled into a 2-sentence injection
- 3-4 competitor contrast points (without naming competitors negatively)
Keep the runtime config under 40 lines — it needs to fit in a prompt without bloating token count.

Before writing anything, research deeply:

0. **FIRST AND MOST IMPORTANT**: Read the founder's brand identity document at
   `docs/brand/allied-brass-brand-identity.md` — this was written by Bobby Andris when he
   first joined the company and captures his raw, authentic understanding of what makes
   Allied Brass special. Key insights from this document:
   - The "one-two punch": functionality wrapped in style + unparalleled finish variety
   - The Amazon comparison: competitors sell utilitarian products, Allied Brass sells design
   - ALL products in ALL finishes across ALL collections — unprecedented customization
   - The goal is to SUBTLY EMBED the message, not directly repeat it
   - "We aim to stand so tall that our competitors' punches don't register"
   This document is the emotional foundation. Everything else is research to validate and
   expand on these instincts.

1. Visit alliedbrass.com using Claude in Chrome. Read the About page, browse multiple product
   categories, look at the collection pages, read any brand story content. Understand what the
   company says about itself.

2. Read `data/Collection_Descriptions_Complete_All_41_20260124.csv` — these 41 collection
   descriptions contain design language and aesthetic vision that reveal brand identity.

3. Read `src/feedops/pipeline/lifestyle_images.py` — the FINISH_LIGHTING dict with 28 finishes
   reveals the breadth and depth of the product line. No competitor offers this many finishes.

4. Read `src/feedops/pipeline/prompts.py` — identify every brand-related instruction and assess
   whether it captures brand truth or just states generic "premium quality" claims.

5. Web search for:
   - "Allied Brass company history" and "Allied Brass reviews" — find what real customers say
   - "solid brass vs zinc alloy bathroom hardware" — understand the material advantage
   - "bathroom hardware brands comparison" and "luxury bathroom accessories brands"
   - "marketing psychology emotional branding" and "brand loyalty psychology principles"
   - "Robert Cialdini influence principles marketing" and "emotional anchoring in e-commerce"
   - "how luxury brands create emotional connection" and "brand storytelling frameworks"

6. Search competitor sites (Kingston Brass, Moen, Delta, Kohler) to understand what they
   claim and where Allied Brass genuinely differentiates. Find the REAL advantages, not
   invented ones.

7. Query the `product_catalog` table to understand the full scope: how many SKUs, how many
   categories, how many finishes, price range. The scale of the catalog IS a differentiator.

8. Read any customer reviews or testimonials available on alliedbrass.com or third-party sites.

Create the skill with these sections:

### The Allied Brass Truth
What is GENUINELY special about this company. Not marketing fluff — verifiable truths:
- Solid brass construction (most competitors use zinc alloy with plated finish)
- 28+ designer finishes (competitors offer 3-8)
- 41 coordinated collections (competitors offer individual pieces)
- Limited Lifetime Warranty (many competitors offer 1-5 year)
- American heritage brand with decades of manufacturing
- Price-to-quality ratio (premium materials at mid-market pricing)
- Concealed mounting hardware across the line (attention to design detail)

For each truth, provide:
- The FACT (verifiable claim)
- WHY it matters to the customer (benefit)
- HOW to express it (not "we use solid brass" but "built from the same solid brass used in
  marine hardware — it won't corrode, pit, or tarnish even in the steamiest bathroom")
- The COMPETITOR CONTRAST (what they do instead, without naming them negatively)

### Marketing Psychology Principles for Brand Content
Apply these principles naturally (never explicitly — the best psychology is invisible):

**Emotional Anchoring**
- First impression of the product description sets an emotional anchor
- Open with a feeling, scenario, or aspiration — not a spec
- "Picture your guest bathroom with matching accessories in warm Venetian Bronze..."
- The anchor should be aspirational but achievable

**Authority & Expertise**
- Position Allied Brass as the experts through specificity, not claims
- Instead of "premium quality" (claim), say "solid brass core with 7-layer finish process" (proof)
- Reference material science, design principles, installation best practices
- The reader should feel "these people know what they're talking about"

**Social Proof (implicit)**
- Reference popularity without fake urgency: "one of our most popular collections"
- Frame design choices as intentional: "designers choose this finish because..."
- When real customer feedback exists, incorporate language patterns from actual reviews
- "Customers love..." is weak. "Fits perfectly in smaller guest bathrooms" is strong social proof

**Reciprocity**
- Give the reader useful information (installation tips, design advice, care instructions)
- Content that HELPS the reader builds goodwill that converts
- "Pro tip: measure 48 inches from the floor for the ideal towel bar height"
- The reader feels they've received something valuable before they've bought anything

**Commitment & Consistency**
- Once someone sees themselves as a "person who appreciates quality hardware," they'll act
  consistently with that identity
- Frame the reader as someone who "knows the difference" and "values craftsmanship"
- "For those who notice the details — the concealed mounting hardware keeps the focus on design"
- Subtle identity framing: "You're the kind of person who..."

**Loss Aversion**
- Frame not-buying as missing out on the quality difference
- "Every day with builder-grade hardware is a day your bathroom doesn't feel like yours"
- Emphasize what they'd lose by choosing a cheaper alternative (without being aggressive)
- Lifetime warranty = never having to replace it

### The Allied Brass Voice
Define the brand's voice as if you were describing a person:
- Confident but not arrogant (we know we're good, we don't need to shout it)
- Knowledgeable but accessible (explain without condescending)
- Design-aware but practical (beautiful AND functional)
- Specific and concrete (never vague platitudes)
- Warm and inviting (this is your home, we want to make it better)

### Voice Anti-Patterns
Things that violate the Allied Brass voice:
- "Premium" and "luxury" as standalone adjectives (show, don't tell)
- "Upgrade your bathroom" (generic, every brand says this)
- "High-quality construction" (what does that mean? Be specific)
- Hyperbolic claims ("the finest in the world")
- Price-focused language ("affordable luxury")
- Feature lists without benefits

### Brand Story Hooks by Context
Provide 15-20 different ways to introduce Allied Brass's brand truth naturally:
- For a towel bar: the solid brass weight you feel when you hang a towel
- For a grab bar: safety doesn't mean sacrificing style (ADA + designer finishes)
- For a soap dispenser: the small touch that tells guests you care about details
- For a collection: the satisfaction of a bathroom where everything matches
- For a finish: personal expression in hardware (28 options because you deserve choice)

### How Other Skills Should Reference This One
- google-shopping-content should pull brand differentiation language from here
- bing-shopping-content should use the fuller character count for brand story
- shopify-conversion-content should weave brand identity throughout conversion copy
- product-storytelling should use the customer scenario framing from here
- quality-evaluation should score brand voice consistency using principles from here
- This skill is the "source of truth" for brand identity across all platform-specific skills

### references/ folder
Create `references/brand-truths.md` with the complete verified claims about Allied Brass.
Create `references/psychology-playbook.md` with the principles mapped to content patterns.
Create `references/voice-examples.md` with 20+ before/after examples of brand voice.

The skill should be written with such genuine conviction and specific knowledge that anyone
reading it would BELIEVE in Allied Brass products. Not because it uses persuasion tricks,
but because the truths are compelling and the expression is authentic. The psychology
principles are the delivery mechanism for genuine truths — not manipulation of falsehoods.
```

---

### Additional Skills Worth Considering (Future)

| Skill | Purpose | When to Create |
|-------|---------|----------------|
| `search-intent-mapping` | Map search queries to buyer intent stages (awareness → consideration → purchase) and tailor content accordingly | After v1.3c when search term data drives content |
| `seasonal-content` | Adjust content emphasis based on seasonal demand patterns (bathroom renovation peaks in spring, holiday gift season in Q4) | After seasonal data is analyzed |
| `ada-compliance-content` | Specialized skill for ADA-compliant grab bars and safety products — different buyer psychology, regulatory language, trust signals | When grab bar content is prioritized |
| `multi-sku-variant-content` | Generate base + variant content efficiently for product families (DMF-2/2X through DMF-2/5X) | When batch generation is improved |
| `content-ab-testing` | Design and evaluate A/B tests for content variations — hypothesis formation, test design, statistical evaluation | After experiment framework is live (v1.3c Phase 3) |

---

---

## Part 10: Complete Implementation Roadmap

This is the exact step-by-step plan for implementing everything in this document. Each step includes the specific command or prompt to use, whether to use GSD, and what the expected output is.

### Overview Timeline

```
Step 0: Document Updates ..................... [30 min, Now, No GSD]
Step 1: Create Foundation Skills ............ [2-4 hours, Claude Code sessions]
Step 2: Milestone 1.3a - Content Excellence . [GSD, 3 phases, ~1-2 weeks]
Step 3: Create Remaining Skills ............. [1-2 hours, Claude Code sessions]
Step 4: Milestone 1.3b - Architecture ....... [GSD, 2-3 phases, ~1 week]
Step 5: Milestone 1.3c - Intelligence ....... [GSD, 4 phases, ~2-3 weeks]
Step 6: Milestone 1.4 - Feedback Loop ....... [GSD, 2-3 phases, ~2 weeks]
```

---

### Step 0: Document Updates (Do Now)

**What**: Update the existing v1.3 milestone document with corrections from Part 5 of this assessment.

**Use GSD?** No — this is a document edit, not a code phase.

**Use Claude?** Yes — paste this prompt in Claude Code:

```
Read the strategic assessment at docs/plans/2026-02-21-strategic-milestone-assessment.md,
specifically Part 5 ("What to Update in Current v1.3 Document"). Then read the current v1.3
document at docs/plans/2026-02-21-gsd-milestone-v1.3-actionable-intelligence.md.

Apply ALL corrections identified in Part 5:
1. Add a prerequisite section noting that 1.3a (content quality) should be completed first
2. Note that deferred migrations 034b/035b status should be resolved in 1.3b before 1.3c
3. Update the "What Exists Today" section to reflect Phase 22 bug fixes
4. Add a note about service.ts data being ephemeral and the need for persistence (from 1.3b)
5. Cross-reference the skills catalog — note which skills are prerequisites for which phases

Do NOT rewrite the document — make surgical edits that add the missing context.
```

**Expected output**: Updated v1.3 document with prerequisite notes and cross-references.

---

### Step 1: Create Foundation Skills (Before Milestone 1.3a)

**What**: Create the skills that will be used during content quality work. Create in this order because later skills reference earlier ones.

**Use GSD?** No — skill creation is best done as individual Claude Code sessions, not GSD phases. Each skill needs web research, database queries, and creative writing that don't fit the GSD atomic-commit pattern.

**Use Agent Teams?** No — skills should be created sequentially because later skills reference earlier ones (e.g., google-shopping-content references allied-brass-brand-expert).

**IMPORTANT — Dual Output**: Each skill creation session should produce TWO outputs:
1. **Claude Code skill** at `.claude/skills/<name>/SKILL.md` — full version for Claude
2. **Runtime config** at `src/feedops/config/<name>.yaml` — distilled version for GPT-5.2 injection

The skill creation prompts (Part 9) now include instructions for both outputs. After all skills are created, Step 2 (Milestone 1.3a Phase 2) will wire the runtime configs into `prompt_builder.py`.

**Creation Order** (dependency-aware):

#### 1a. `allied-brass-brand-expert` (Skill 11) — CREATE FIRST
**Why first**: Every other content skill draws from the brand truth and voice defined here.

**Key input**: Bobby's brand identity document at `docs/brand/allied-brass-brand-identity.md` — the authentic "one-two punch" framework (design + finishes) and the philosophy of subtle embedding.

**Prompt**: Copy the full prompt from Skill 11 section above and paste into a new Claude Code session.

**Dual output**:
- `.claude/skills/allied-brass-brand-expert/SKILL.md` + `references/` folder
- `src/feedops/config/brand_voice.yaml` (runtime injection for GPT-5.2)

**After creation**: `git add -f .claude/skills/allied-brass-brand-expert/ src/feedops/config/brand_voice.yaml && git commit -m "feat: add allied-brass-brand-expert skill + runtime brand voice config"`

**Verify**: Run `ls .claude/skills/allied-brass-brand-expert/` — should see `SKILL.md` and `references/` folder. Run `cat src/feedops/config/brand_voice.yaml` — should be under 40 lines.

#### 1b. `quality-evaluation` (Skill 9) — CREATE SECOND
**Why second**: Establishes how we measure quality BEFORE we start generating. The new 10-criterion rubric replaces the broken 6-criterion compliance rubric.

**Prompt**: Copy the full prompt from Skill 9 section above.

**Dual output**:
- `.claude/skills/quality-evaluation/SKILL.md`
- `src/feedops/config/quality_rubric.yaml` (replaces current 6-criterion self_score in CANDIDATE_SCHEMA)

**After creation**: `git add -f .claude/skills/quality-evaluation/ src/feedops/config/quality_rubric.yaml && git commit -m "feat: add quality-evaluation skill + runtime rubric config"`

#### 1c. `finish-expertise` (Skill 8) — CREATE THIRD
**Why third**: Finish is the primary variant differentiator. Needed before platform-specific skills because all platforms need finish language.

**Prompt**: Copy the full prompt from Skill 8 section above.

**Dual output**:
- `.claude/skills/finish-expertise/SKILL.md` + `references/`
- `src/feedops/config/finish_guide.yaml` (per-finish language injected during variant expansion)

**After creation**: `git add -f .claude/skills/finish-expertise/ src/feedops/config/finish_guide.yaml && git commit -m "feat: add finish-expertise skill + runtime finish guide"`

#### 1d. `product-storytelling` (Skill 4) — CREATE FOURTH
**Why fourth**: Establishes the narrative framework before platform-specific skills add constraints.

**Prompt**: Copy the full prompt from Skill 4 section above.

**Dual output**:
- `.claude/skills/product-storytelling/SKILL.md`
- `src/feedops/config/storytelling_patterns.yaml` (per-category narrative frameworks)

**After creation**: `git add -f .claude/skills/product-storytelling/ src/feedops/config/storytelling_patterns.yaml && git commit -m "feat: add product-storytelling skill + runtime storytelling patterns"`

#### 1e. `collection-storytelling` (Skill 10) — CREATE FIFTH
**Why fifth**: Builds on product-storytelling with collection-specific design language.

**Prompt**: Copy the full prompt from Skill 10 section above.

**Dual output**:
- `.claude/skills/collection-storytelling/SKILL.md`
- `src/feedops/config/collection_stories.yaml` (per-collection design language for all 41 collections)

**After creation**: `git add -f .claude/skills/collection-storytelling/ src/feedops/config/collection_stories.yaml && git commit -m "feat: add collection-storytelling skill + runtime collection stories"`

#### 1f. `google-shopping-content` (Skill 1) — CREATE SIXTH
**Why sixth**: Now has all foundation skills to draw from (brand, quality, finish, storytelling, collections).

**Prompt**: Copy the full prompt from Skill 1 section above. **Add this line to the top of the prompt**: "Before creating this skill, read the already-created skills at `.claude/skills/allied-brass-brand-expert/SKILL.md`, `.claude/skills/quality-evaluation/SKILL.md`, `.claude/skills/finish-expertise/SKILL.md`, `.claude/skills/product-storytelling/SKILL.md`, and `.claude/skills/collection-storytelling/SKILL.md` — this skill should reference and build on them, not duplicate them."

**Dual output**:
- `.claude/skills/google-shopping-content/SKILL.md` + `references/`
- Updates to `src/feedops/config/shopping_intelligence.yaml` (rewrite template rules with creative direction)

**After creation**: `git add -f .claude/skills/google-shopping-content/ src/feedops/config/shopping_intelligence.yaml && git commit -m "feat: add google-shopping-content skill + rewrite shopping intelligence config"`

#### 1g. `bing-shopping-content` (Skill 2) — CREATE SEVENTH

**Prompt**: Copy the full prompt from Skill 2 section above.

**Dual output**:
- `.claude/skills/bing-shopping-content/SKILL.md`
- `src/feedops/config/platform_bing.yaml` (Bing-specific rules and synonym maps)

**After creation**: `git add -f .claude/skills/bing-shopping-content/ src/feedops/config/platform_bing.yaml && git commit -m "feat: add bing-shopping-content skill + runtime Bing platform config"`

#### 1h. `shopify-conversion-content` (Skill 3) — CREATE EIGHTH

**Prompt**: Copy the full prompt from Skill 3 section above.

**Dual output**:
- `.claude/skills/shopify-conversion-content/SKILL.md`
- `src/feedops/config/platform_shopify.yaml` (Shopify voice, HTML structure, conversion patterns)

**After creation**: `git add -f .claude/skills/shopify-conversion-content/ src/feedops/config/platform_shopify.yaml && git commit -m "feat: add shopify-conversion-content skill + runtime Shopify platform config"`

**Total for Step 1**: 8 skills + 8 runtime configs, ~8 Claude Code sessions (one per skill), ~2-4 hours depending on research depth.

**Checkpoint**: After all 8 skills are created, verify:
- `ls .claude/skills/` — should show 14 entries (6 existing + 8 new)
- `ls src/feedops/config/` — should show new YAML files: `brand_voice.yaml`, `quality_rubric.yaml`, `finish_guide.yaml`, `storytelling_patterns.yaml`, `collection_stories.yaml`, `platform_bing.yaml`, `platform_shopify.yaml`, plus updated `shopping_intelligence.yaml`

---

### Step 2: Milestone 1.3a — Content Generation Excellence (GSD)

**What**: Use the skills to actually transform the content generation system.

**Use GSD?** YES — this is multi-phase implementation work with verification.

**Use Agent Teams?** Yes for Phase 1 research (parallel competitor scraping + database analysis + web research). No for Phase 2 (prompt rewriting is sequential and needs human review). Maybe for Phase 3 (parallel SKU regeneration).

**How to start**: Open a new Claude Code session and run:

```
/gsd:new-milestone
```

When prompted, provide this context:

```
Milestone: v1.3a — Content Generation Excellence

Use the full milestone prompt from Part 4 of the strategic assessment document at
docs/plans/2026-02-21-strategic-milestone-assessment.md (section "Milestone 1.3a:
Content Generation Excellence").

IMPORTANT CONTEXT:
- CRITICAL GPT-5.2 BUGS TO FIX FIRST (Phase 1):
  - openai_provider.py passes temperature=0.7 alongside reasoning_params — mutually exclusive on GPT-5.2
  - reasoning_effort defaults to none (env var only) — model runs with zero reasoning for content quality
  - Uses legacy json_object mode instead of json_schema strict mode — wastes tokens on retry loops
  - No prompt_cache_retention="24h" — losing cache hits on batch runs
  - System prompt uses === headers instead of XML tags — GPT-5.2 parses XML more reliably
  - Full analysis: docs/research/gpt52-best-practices.md
- OpenAI dev docs MCP server is available: use mcp__openaiDeveloperDocs__search_openai_docs
  and mcp__openaiDeveloperDocs__fetch_openai_doc when researching GPT-5.2 API changes
- 8 Claude Code skills have already been created under .claude/skills/ — these skills
  should be referenced during implementation, not rebuilt
- 8 RUNTIME CONFIG FILES have also been created under src/feedops/config/ — these are
  the distilled versions that GPT-5.2 uses directly during generation:
  - brand_voice.yaml (universal — inject into every prompt)
  - quality_rubric.yaml (replaces current 6-criterion self_score)
  - finish_guide.yaml (per-finish injection during variant expansion)
  - storytelling_patterns.yaml (per-category narrative frameworks)
  - collection_stories.yaml (per-collection design language)
  - shopping_intelligence.yaml (UPDATED — creative direction, not templates)
  - platform_bing.yaml (Bing-specific rules and synonym maps)
  - platform_shopify.yaml (Shopify voice and conversion patterns)
- The Python pipeline (src/feedops/pipeline/prompts.py, src/feedops/api/prompt_builder.py)
  needs to be updated to LOAD and INJECT these new config files
- GPT-5.2 is the generation model — it reads the runtime configs directly in its prompt
- Use /quality-evaluation skill when assessing generated content
- Use /allied-brass-brand-expert skill when writing brand-related content
```

**Phase breakdown** (GSD will plan these, but here's the expected structure):

**Phase 1: Fix GPT-5.2 Integration Bugs + Establish Excellence Standards** (~3-5 days)

CRITICAL: Before rewriting any prompts, fix these confirmed bugs in the GPT-5.2 integration
(discovered via OpenAI developer docs research, 2026-02-21):

**Bug fixes (do FIRST — these affect all generation quality):**
- **BUG: temperature/reasoning_effort conflict** — `openai_provider.py` always passes `temperature=0.7`
  alongside `**reasoning_params`. On GPT-5.2, temperature is ONLY supported when `reasoning_effort=none`.
  If reasoning_effort is set to low/medium/high, the API will error. Fix: omit temperature when
  reasoning_effort is set.
- **BUG: reasoning_effort defaults to none** — `optimize.py` line 148 only reads from env var
  `FEEDOPS_REASONING_EFFORT`. GPT-5.2 defaults to `reasoning_effort: none` = zero internal reasoning.
  For content quality, this should default to `medium`. We're running the model in "fast mode" when
  we want "quality mode."
- **Switch json_object → json_schema strict mode** — `openai_provider.py` uses legacy
  `response_format={"type": "json_object"}`. Switch to `json_schema` with `strict: true` and our
  CANDIDATE_SCHEMA. This eliminates the entire JSON decode retry loop (lines 214-237) since strict
  mode guarantees schema-compliant output. Add `additionalProperties: false` to all schema objects.
- **Enable 24h prompt cache retention** — Add `prompt_cache_retention="24h"` to API calls. Default
  in-memory caching only lasts 5-10 minutes. For batch runs of 50+ SKUs, this ensures cache hits
  across the entire batch (up to 80% latency reduction, 90% input cost reduction).
- **Convert === headers to XML tags** — SYSTEM_PROMPT uses `=== P0_GLOBAL_FACTUAL_RULES ===` style
  headers. GPT-5.2 prompting guide recommends XML tags (`<p0_global_factual_rules>`) for more
  reliable section parsing.
- **Strengthen length constraints** — Change "target 600-800 characters" to "MUST be between 600
  and 800 characters" — GPT-5.2's lower default verbosity + conservative bias interprets vague
  targets as optional.

**Reference**: Full analysis at `docs/research/gpt52-best-practices.md` (to be saved from /tmp)

**Excellence standards (after bug fixes):**
- Research competitor listings (use Apify scraping + web search)
- Analyze top-performing search terms from database
- Create 10-15 gold standard examples in `prompt_templates` table
- Rewrite quality scoring rubric per quality-evaluation skill
- **Agent teams**: Yes — spawn parallel researchers for competitor analysis, search term analysis, and gold example creation

**Phase 2: Wire Runtime Configs + Rewrite Prompt Architecture** (~3-5 days)

This is the most critical phase — it connects the runtime config files created in Step 1 to GPT-5.2's actual prompt.

**GPT-5.2 prompt caching optimization (do FIRST in this phase):**
- Move gold standard examples from user prompt INTO the system prompt — they change infrequently
  but currently break the cacheable prefix on every request. The OpenAI docs are explicit: "static
  content first, dynamic content last." Examples should be after rules but before per-SKU evidence.
- Move category guidance into system prompt (or second system message) for same caching reason
- Add `reasoning_effort: medium` as default for base SKU generation, `low` for variant adaptation
- Add `text.verbosity: medium` for descriptions (new GPT-5.2 parameter controlling output length)
- **Future consideration**: Migrate from Chat Completions API to Responses API for higher cache hit
  rates and ability to pass chain-of-thought between retries (medium priority, not blocking)

**Wire runtime configs into `prompt_builder.py`**:
  - Add loader for `brand_voice.yaml` → inject brand truths into EVERY prompt (universal section)
  - Add loader for `finish_guide.yaml` → inject per-finish language during variant expansion
  - Add loader for `storytelling_patterns.yaml` → inject per-category narrative framework
  - Add loader for `collection_stories.yaml` → inject per-collection design language (supplements existing `collection_descriptions.py`)
  - Add platform-specific loader for `platform_bing.yaml` and `platform_shopify.yaml` → inject when generating for those platforms
  - `shopping_intelligence.yaml` was already rewritten in Step 1f — verify it loads correctly
- **Replace `quality_rubric.yaml` into `prompts.py`**:
  - Update CANDIDATE_SCHEMA self_score section to use the new 10-criterion rubric
  - Update scoring weights per the quality-evaluation skill
- Rewrite `SYSTEM_PROMPT` in `prompts.py` using brand-expert + storytelling skills (shift from compliance document to creative brief)
- Expand `_CATEGORY_GUIDANCE` to top 20 revenue categories using storytelling_patterns.yaml data
- **Agent teams**: No — this is core prompt work that needs sequential human review
- **CRITICAL**: After each config is wired, regenerate 2-3 test SKUs and evaluate with /quality-evaluation skill. Compare scores on old rubric vs new rubric to validate the new rubric catches problems the old one missed.

**Phase 3: Generate, Evaluate, Iterate** (~3-5 days)
- Regenerate content for 10 representative SKUs
- Human evaluation: old vs new side-by-side
- Publish test batch and measure CTR/CVR delta after 7-14 days
- Iterate based on results
- **Agent teams**: Maybe — parallel SKU regeneration is possible

**How to execute each phase**: After `/gsd:new-milestone` creates the roadmap:
```
/gsd:plan-phase    # Plan each phase
/gsd:execute-phase # Execute with atomic commits
/gsd:verify-work   # Verify each phase before moving on
```

---

### Step 3: Create Remaining Skills (Between 1.3a and 1.3b)

**What**: Create the skills needed for later milestones that weren't prerequisites for 1.3a.

**Use GSD?** No.

#### 3a. `lifestyle-image-generation` (Skill 5)
**Prompt**: Copy from Skill 5 section above.
**After**: `git add -f .claude/skills/lifestyle-image-generation/ && git commit -m "feat: add lifestyle-image-generation skill"`

#### 3b. `competitor-research` (Skill 6)
**Prompt**: Copy from Skill 6 section above.
**After**: `git add -f .claude/skills/competitor-research/ && git commit -m "feat: add competitor-research skill"`

#### 3c. `feed-optimization` (Skill 7)
**Prompt**: Copy from Skill 7 section above.
**After**: `git add -f .claude/skills/feed-optimization/ && git commit -m "feat: add feed-optimization skill"`

**Total**: 3 more skills, ~1-2 hours.

---

### Step 4: Milestone 1.3b — Architecture Validation & Data Persistence (GSD)

**What**: Validate and prepare the architecture for optimization intelligence.

**Use GSD?** YES.

**Use Agent Teams?** Yes for Phase 1 (parallel architecture audit across different subsystems).

**How to start**: New Claude Code session:

```
/gsd:new-milestone
```

Provide the milestone prompt from Part 4 ("Milestone 1.3b: Architecture Validation & Data Persistence"). Add:

```
Additional context:
- Skills created: competitor-research, feed-optimization, lifestyle-image-generation
  (available for reference during architecture work)
- The deferred migration 035b creates 14 tables — evaluate which are actually needed
  (see Part 7 of the strategic assessment). Recommendation: apply 8 of 14 tables that
  are prerequisites for v1.3c, skip the 6 that can wait.
- Content-performance feedback table is the KEY deliverable — this links generated content
  to CTR/CVR outcomes for the closed-loop system in v1.4
```

**Phase breakdown**:

**Phase 1: Architecture Audit** (~2-3 days)
- Map complete data flow
- Evaluate deferred migrations
- Design feedback table
- **Agent teams**: Yes — spawn parallel auditors (database auditor, API auditor, data flow auditor)

**Phase 2: Critical Schema Updates** (~2-3 days)
- Apply subset of 035b migration
- Create content-performance feedback view
- Add persistence layer for service.ts data
- **Agent teams**: No — database migrations are sequential

**Phase 3: Data Pipeline Validation** (~1-2 days)
- End-to-end flow verification
- Populate empty optimization tables
- **Agent teams**: No

---

### Step 5: Milestone 1.3c — Actionable Shopping Intelligence (GSD)

**What**: The existing v1.3 document, now with solid foundations underneath it.

**Use GSD?** YES.

**Use Agent Teams?** Yes for Phase 1 (parallel scoring engine + revenue leakage + market intelligence).

**How to start**: The v1.3 document already exists at `docs/plans/2026-02-21-gsd-milestone-v1.3-actionable-intelligence.md`. Use it directly:

```
/gsd:new-milestone
```

Reference the existing document as the milestone spec. Add:

```
Prerequisites completed:
- Milestone 1.3a: Content quality is now excellent (gold examples, new prompt architecture)
- Milestone 1.3b: Architecture validated (deferred migrations applied, feedback table exists,
  data persistence in place)
- Skills available: all 11 skills created, especially competitor-research and feed-optimization
  which are relevant to market intelligence phases
```

This milestone follows the existing v1.3 document's 4-phase structure exactly. No changes needed beyond the prerequisite acknowledgments.

---

### Step 6: Milestone 1.4 — Closed-Loop Optimization (GSD)

**What**: Build the feedback loop that connects performance data back to content generation.

**Use GSD?** YES.

**Use Agent Teams?** Yes — this milestone benefits most from multi-agent coordination (performance analysis agent, content optimization agent, experiment management agent).

**How to start**: When 1.3c is complete, new Claude Code session:

```
/gsd:new-milestone
```

Provide the milestone prompt from Part 4 ("Milestone 1.4: Closed-Loop Optimization").

This is the most agent-appropriate milestone — the feedback loop involves multiple independent systems that need to coordinate. Consider:
- A "performance analyst" agent that monitors CTR/CVR trends
- A "content optimizer" agent that proposes prompt changes based on performance data
- An "experiment manager" agent that designs and evaluates A/B tests

These agents would be built during 1.4, not before. The skill foundation from earlier milestones provides the domain knowledge they'll use.

---

### When to Use What — Quick Reference

| Task Type | Use GSD? | Use Teams? | Use Claude? | Notes |
|-----------|----------|------------|-------------|-------|
| Create a skill | No | No | Yes, one session per skill | Skills need research + creative writing |
| Update a document | No | No | Yes | Simple edit task |
| Plan a milestone | Yes (`/gsd:new-milestone`) | No | Yes | GSD manages planning |
| Execute a phase | Yes (`/gsd:execute-phase`) | Sometimes | Yes | Teams for parallel research |
| Verify a phase | Yes (`/gsd:verify-work`) | No | Yes | GSD verification protocol |
| Regenerate test SKUs | No | Maybe | Yes | Use skills during regeneration |
| Evaluate content quality | No | No | Yes | Use quality-evaluation skill |
| Database migration | Yes (within a phase) | No | Yes | Sequential, needs verification |
| Competitor research | No (or within phase) | Yes | Yes | Parallel scraping with Apify |
| Debug an issue | Yes (`/gsd:debug`) | No | Yes | GSD debug protocol |
| Track progress | No | No | No | Update Notion page manually or ask Claude |

### Estimated Total Timeline

| Step | Duration | Prerequisites |
|------|----------|---------------|
| Step 0: Document updates | 30 min | None |
| Step 1: Foundation skills (8) | 2-4 hours | None |
| Step 2: Milestone 1.3a | 1-2 weeks | Step 1 |
| Step 3: Remaining skills (3) | 1-2 hours | Step 2 |
| Step 4: Milestone 1.3b | 1 week | Step 2 |
| Step 5: Milestone 1.3c | 2-3 weeks | Steps 3+4 |
| Step 6: Milestone 1.4 | 2 weeks | Step 5 |
| **Total** | **~7-9 weeks** | |

Note: Steps 3 and 4 can run in parallel after Step 2 is complete.

---

### Notion as Source of Truth

This document will be published to a Notion page that serves as the project tracking hub. The Notion page should be updated:

- **After each skill is created**: Check off the skill in the catalog
- **After each GSD phase completes**: Update milestone status with phase completion date
- **After each milestone completes**: Mark milestone complete, add lessons learned
- **When new work is identified**: Add new tasks or skills to the roadmap
- **Weekly**: Quick status update noting what was accomplished and what's next

The Notion page is for YOUR tracking — GSD handles the technical project state in `.planning/`. Both systems should agree, but Notion gives you the bird's-eye view without opening a terminal.

---

## Summary

The path forward is clear and actionable:

1. **Create 11 skills** — encoding brand truth, platform expertise, quality standards, and creative direction into reusable knowledge that Claude draws from when crafting GPT-5.2 prompts
2. **Fix content quality** (1.3a) — the most urgent gap, using skills as the creative brief for prompt architecture rewrite
3. **Validate architecture** (1.3b) — ensure database and data pipeline support the optimization vision
4. **Build actionable intelligence** (1.3c) — turn existing infrastructure into revenue-generating decisions
5. **Close the feedback loop** (1.4) — make the system self-reinforcing with agents for ongoing optimization

**On skills**: Skills are the strategy layer. They encode what "excellent" looks like for Allied Brass content so that every Claude session and every GPT-5.2 generation draws from the same well of brand truth, design expertise, and platform knowledge. The `allied-brass-brand-expert` skill is the soul — everything else is a platform-specific expression of that soul.

**On GPT-5.2**: Claude (via skills) crafts the prompts. GPT-5.2 executes them. Skills make Claude a better prompt engineer for GPT-5.2 — they don't replace the generation model.

**On GSD vs. no-GSD**: Use GSD for multi-phase implementation milestones (1.3a-1.4). Don't use GSD for skill creation (research-heavy creative work) or document updates (simple edits).

**On agent teams**: Use teams for parallel research (competitor scraping, database auditing) and for the closed-loop system in 1.4. Don't use teams for skill creation or prompt rewriting — those need sequential, thoughtful work.

**On Notion**: Your personal source of truth for tracking progress. Updated alongside GSD's `.planning/` state but designed for human consumption — the view from 30,000 feet.
