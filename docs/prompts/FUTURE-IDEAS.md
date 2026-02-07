# FeedOps Future Ideas

This document contains feature ideas that are interesting but require additional prerequisites, have higher complexity, or need more research before implementation. These ideas are documented with enough context to be picked up later.

---

## Table of Contents

1. [6-Agent Pipeline Dashboard Integration](#1-6-agent-pipeline-dashboard-integration)
2. [6-Agent Pipeline: 4-Stage Expansion](#2-6-agent-pipeline-4-stage-expansion)
3. [Variant-Level Persona Stories](#3-variant-level-persona-stories)
4. [Agent Pipeline A/B Testing Infrastructure](#4-agent-pipeline-ab-testing-infrastructure)
5. [Vertex AI Search Integration](#5-vertex-ai-search-integration)
6. [Image Variation A/B Testing](#6-image-variation-ab-testing)
7. [Dynamic Pricing Insights](#7-dynamic-pricing-insights)
8. [Auto-Sync to Shopify](#8-auto-sync-to-shopify)
9. [Review/UGC Analysis](#9-reviewugc-analysis)
10. [Google Ads Creative Suggestions](#10-google-ads-creative-suggestions)
11. [Real-time Personalization](#11-real-time-personalization)

---

## 1. 6-Agent Pipeline Dashboard Integration

### Overview
Automate the 6-agent content pipeline so it can be triggered directly from the dashboard `/generate` page, rather than requiring manual Claude Code CLI team spawning.

### Why Maybe
- Complex agent orchestration requiring background job infrastructure
- Needs careful error handling for agent failures
- May require additional MCP servers or API endpoints
- Dashboard integration adds UI/UX complexity

### Current State
**Implemented:** ✅ 6-agent pipeline (manual execution only)
- Produces 87.2/100 avg quality (vs 75-80 for Cloud Run)
- 100% first-pass approval rate
- 0% AI slop in core content
- Takes 2x longer than Cloud Run (~1 hour for 10 SKUs)

See: `docs/prompts/24-six-agent-pipeline.md`

### Prerequisites
- Background job queue system (or leverage existing batch job infrastructure)
- Agent team spawning API endpoint
- Real-time progress updates for user
- Proper error handling for agent failures

### Potential Approach

**Option 1: Job Queue Integration**
```typescript
// Add to /generate page
<Button onClick={() => generateWithAgentPipeline(selectedSkus)}>
  Generate with 6-Agent Pipeline (High Quality)
</Button>

// API endpoint: /api/agent-pipeline/generate
POST /api/agent-pipeline/generate
{
  skus: ['1016', '1024', '1020'],
  platform: 'google'
}

Response: { jobId: 'abc-123' }
```

**Option 2: Pipeline Selector in Regenerate UI**
```typescript
// Add dropdown to existing regenerate button
<RegenerateButton
  pipelineType="cloud-run" | "6-agent"
  sku="1016"
/>
```

### Technical Requirements
- Spawn agent team via Task tool programmatically
- Stream progress updates to dashboard
- Store agent output in proper schema format (use helper function)
- Set `generation_model = '6-agent-pipeline-gpt-4'` for tracking

### UI Considerations
- Show estimated time: "~6 minutes per SKU (high quality)"
- Display progress: "Stage 1: Storytelling Workshop (2/3 agents complete)"
- Compare estimated quality: "Expected quality: 85-95 (vs 75-80 for standard)"
- Allow cancellation of long-running jobs

### When to Consider
- After proving ROI of agent pipeline (30-day CTR comparison)
- When volume of high-quality content requests increases
- If manual execution becomes a bottleneck

### Effort Estimate
**MEDIUM-HIGH** - 20-30 hours
- Job queue infrastructure: 8-12 hours
- Agent orchestration endpoint: 6-8 hours
- UI integration: 4-6 hours
- Testing and error handling: 4-6 hours

---

## 2. 6-Agent Pipeline: 4-Stage Expansion

### Overview
Expand the 6-agent pipeline from 2 stages to 4 stages by adding SEO Time Travel and Customer Reality Check agents.

### Why Maybe
- Adds complexity and execution time
- Need to validate 2-stage pipeline ROI first
- May hit diminishing returns on quality
- Requires proving value of additional perspectives

### Current State
**Current Pipeline (2 Stages):**
- Stage 1: Storytelling Workshop (Designer, Contractor, Homeowner)
- Stage 2: Content Court (Synthesizer, Prosecutor, Judge)
- Quality: 87.2/100 average

**Proposed Pipeline (4 Stages):**
- Stage 1: Storytelling Workshop (3 agents, parallel)
- Stage 2: **SEO Time Travel** (1 agent, new)
- Stage 3: **Customer Reality Check** (1 agent, new)
- Stage 4: Content Court (3 agents, sequential)

### New Agent: SEO Time Travel

**Role:** Predict future algorithm changes and proactively optimize

**Example Output:**
> Based on Google's recent Core Updates emphasizing E-E-A-T and helpful content, I predict they'll devalue generic "premium quality" claims within 12 months. This content grounds claims in specific contractor install volumes (200+ units) and longevity data (7+ years, zero callbacks)—both strong E-E-A-T signals that should remain valuable as algorithms evolve.

**Key Themes:**
- Algorithm trend analysis
- E-E-A-T signal strength
- Future-proofing content
- Search intent evolution

### New Agent: Customer Reality Check

**Role:** Test content against "angry customer" scenarios

**Example Output:**
> VULNERABILITY TEST - Bathroom renovation customer scenario:
> "I just spent $15,000 renovating my bathroom and this $40 towel ring better not disappoint."
>
> PASS - Content directly addresses durability concerns with "7+ years, zero callbacks" and "commercial-grade engineering tested to 10 pounds." The solid brass vs. zinc comparison answers the quality question preemptively.

**Key Themes:**
- High-stakes purchase scenarios
- Common objections
- Quality skepticism
- Competitor comparisons

### Prerequisites
- 2-stage pipeline ROI proven (>2x CTR improvement for 2x time)
- Budget for longer execution (2-stage: 1 hour → 4-stage: 1.5-2 hours)
- Ability to measure incremental quality improvements

### Expected Benefits
- Quality score increase: 87.2 → 90-95 average
- Better long-term SEO resilience
- Anticipate customer objections proactively
- Stronger differentiation from competitors

### When to Consider
- After 30-day CTR data confirms 2-stage pipeline ROI
- If top-performing SKUs need even higher quality
- When creating gold standard examples for training

### Effort Estimate
**MEDIUM** - 12-16 hours
- SEO Time Travel agent: 4-6 hours
- Customer Reality Check agent: 4-6 hours
- Integration and testing: 4-6 hours

---

## 3. Variant-Level Persona Stories

### Overview
Generate finish-specific persona stories to create better variant content, rather than just using finish sentences.

### Why Maybe
- 280 stories per 10 SKUs (10 SKUs × 28 finishes) = massive execution time
- May not provide enough value over finish sentences
- Finish differences are often cosmetic, not functional
- Could confuse customers if finishes described too differently

### Current State
**Current Approach:**
- Master SKU content with `{FINISH_NAME}` placeholder
- 28 finish sentences stored in `variant_finish_sentences`
- Variant content = base template + finish sentence at display time

**Proposed Approach:**
- Generate 28 full persona stories per finish
- Synthesize finish-specific content for each variant
- Store 280 content pieces (10 SKUs × 28 finishes)

### Use Case Example

**Current (Generic Finish Sentence):**
> "Available in Polished Chrome for timeless elegance."

**Variant Persona Story (Polished Chrome):**
> The Polished Chrome finish shows fingerprints easily—I always warn customers about this upfront. It's gorgeous in powder rooms with low traffic, but for family bathrooms where kids touch everything, I recommend Oil Rubbed Bronze instead. The chrome plating is durable (ASTM B456 certified), but you'll be wiping it down daily if you have teenagers.

### When It Matters
**Finishes with functional differences:**
- Oil Rubbed Bronze - Shows wear differently, patina over time
- Matte Black - Hides fingerprints better than chrome
- Unlacquered Brass - Develops natural patina, requires care

**Finishes that are just cosmetic:**
- Polished Chrome vs Polished Nickel - Functionally identical
- Satin Chrome vs Satin Nickel - Just color preference

### Potential Approach
**Hybrid Model:**
- Generate variant stories only for functionally different finishes (8-10 finishes)
- Use generic finish sentences for cosmetic-only finishes (18-20 finishes)
- Reduces execution time while adding value where it matters

### Prerequisites
- Finish characteristic database (fingerprint visibility, patina behavior, care requirements)
- Execution time budget (280 stories = 4-6 hours with current pipeline)
- Storage for 280+ content pieces per platform

### When to Consider
- After proving finish-specific content improves conversions
- If customers frequently ask about finish differences
- When building comprehensive finish comparison tools

### Effort Estimate
**HIGH** - 30-40 hours
- Finish characteristic database: 8-12 hours
- Agent prompt modifications: 6-8 hours
- Storage schema changes: 4-6 hours
- Execution time for all SKUs: 12-16 hours

---

## 4. Agent Pipeline A/B Testing Infrastructure

### Overview
Build infrastructure to properly measure ROI of 6-agent pipeline vs Cloud Run pipeline through controlled A/B testing.

### Why Maybe
- Requires attribution system (baseline capture already exists)
- Need statistical significance calculator
- Test duration must be long enough (30+ days)
- Sample size limitations with low-traffic SKUs

### Current State
**Performance Tracking Exists:**
- `performance_baselines` table (pre-publish metrics)
- `performance_snapshots` table (post-publish tracking)
- `publish_events` table (content version tracking)

**Missing:**
- Cohort assignment system
- Statistical significance testing
- ROI calculator
- Automated test analysis

### Potential Approach

**Test Design:**
```
Cohort A: 10 SKUs with 6-agent content (already generated)
Cohort B: 10 SKUs with Cloud Run content (regenerate all)
Metric: CTR improvement (30-day comparison)
Hypothesis: 6-agent content yields >2x CTR for 2x time investment
```

**Technical Requirements:**
```typescript
// Cohort tracking
interface ABTest {
  test_id: string
  cohort_a_skus: string[]  // Agent pipeline
  cohort_b_skus: string[]  // Cloud Run
  start_date: string
  end_date: string
  hypothesis: string
}

// Analysis function
function analyzeTest(testId: string) {
  // Compare performance_snapshots for both cohorts
  // Calculate statistical significance (t-test)
  // Compute ROI: (CTR_improvement / time_investment)
}
```

### Metrics to Track
- **CTR improvement** (primary metric)
- **Conversion rate** (secondary)
- **Cost per conversion** (secondary)
- **Quality score correlation** (does higher quality → higher CTR?)

### Statistical Considerations
- Minimum test duration: 30 days
- Minimum sample size: 20 SKUs per cohort
- Significance level: p < 0.05
- Account for seasonality (compare same time periods)

### When to Consider
- After generating enough agent content for test cohort (20+ SKUs)
- When baseline performance tracking is stable
- Before investing in dashboard automation

### Effort Estimate
**MEDIUM** - 16-20 hours
- Cohort assignment system: 4-6 hours
- Statistical analysis tools: 6-8 hours
- ROI calculator: 4-6 hours
- Dashboard visualization: 4-6 hours

---

## 5. Vertex AI Search Integration

## 1. Vertex AI Search Integration

### Overview
Integrate Google's Vertex AI Search for Commerce to improve product discovery on the Allied Brass storefront.

### Why Maybe
- Complex setup requiring significant data ingestion
- More relevant for storefront search than feed optimization
- Requires ongoing data pipeline maintenance
- Allied Brass storefront may not have enough traffic to justify

### Prerequisites
- Google Cloud project with Vertex AI enabled
- Product catalog data pipeline to Vertex AI
- Storefront integration (Shopify or custom)
- Minimum traffic volume for ML models to work effectively

### Potential Benefits
- AI-powered product recommendations
- Semantic search understanding ("bathroom hardware that matches my faucet")
- Personalized search results
- Browse and search analytics

### Research Links
- [Vertex AI Search for Commerce](https://cloud.google.com/solutions/retail-product-discovery)
- [Recommendations AI](https://cloud.google.com/recommendations)

### Effort Estimate
HIGH - 40+ hours for initial setup, ongoing maintenance

### When to Consider
- If Allied Brass wants to invest in storefront improvements
- If they have sufficient traffic to benefit from ML recommendations
- If they're considering moving away from Shopify default search

---

## 2. Image Variation A/B Testing

### Overview
Test different lifestyle image styles/scenes to determine which drives higher CTR and conversions.

### Why Maybe
- Difficult to measure image impact in isolation
- GMC has limitations on image testing
- Attribution is complex (was it the image or the title change?)
- Requires significant image generation investment

### Prerequisites
- Multi-variant image generation (Prompt 16) implemented
- Proper attribution system in place
- GMC supplemental feed control
- Statistical significance calculator

### Potential Approach
```
Cohort A: Modern bathroom scene
Cohort B: Traditional bathroom scene
Cohort C: Close-up product focus
Cohort D: Room context (full bathroom view)
```

### Measurement Challenges
- GMC doesn't provide image-specific metrics
- Need to isolate image changes from other variables
- Seasonal effects may confuse results
- Sample sizes may be too small per variant

### Technical Requirements
- Generate 4+ image variations per SKU
- Rotate images in GMC feed on schedule
- Track performance windows for each variation
- Build statistical comparison tools

### When to Consider
- After baseline attribution system is proven (Prompt 12)
- When image generation pipeline is stable
- If CTR improvements plateau with title/description optimization

---

## 3. Dynamic Pricing Insights

### Overview
Analyze pricing data to understand optimal price points and competitive positioning.

### Why Maybe
- Out of scope for content optimization (FeedOps focus)
- Requires pricing API integration
- Allied Brass may have established pricing strategy
- Pricing changes require business approval

### Prerequisites
- Competitive pricing data source
- Historical sales data at price points
- Pricing authority and approval workflow
- Shopify pricing API integration

### Potential Features
- Price elasticity analysis
- Competitor price monitoring
- Margin optimization suggestions
- Promotional pricing recommendations

### Data Sources Needed
- Competitor prices (Apify scrapers)
- Historical Allied Brass sales by price
- Seasonal pricing patterns
- Cost of goods data

### When to Consider
- If Allied Brass wants pricing optimization
- After content optimization is proven effective
- If competitive pressure requires pricing agility

---

## 4. Auto-Sync to Shopify

### Overview
Automatically push approved content changes to Shopify products without manual intervention.

### Why Maybe
- Risk of overwriting good content
- Requires strong approval workflow
- Need rollback capability
- Could create inconsistencies if not handled carefully

### Prerequisites
- Robust approval workflow (fully implemented)
- Content versioning system
- Rollback capability
- Audit trail for changes
- Environment separation (staging/production)

### Potential Approach
```
1. Content approved in FeedOps
2. Auto-sync to Shopify staging (draft/development theme)
3. Human QA on staging
4. Manual promotion to production
```

### Risk Mitigations
- Never auto-sync to production
- Require explicit human approval for each platform
- Maintain content history for rollback
- Rate limiting to prevent bulk mistakes

### Technical Requirements
- Shopify GraphQL mutations for product update
- Content versioning system
- Staging environment in Shopify
- Notification system for sync events

### When to Consider
- After approval workflow is battle-tested
- When volume of content changes increases
- If manual publishing becomes a bottleneck

---

## 5. Review/UGC Analysis

### Overview
Analyze customer reviews and user-generated content to inform content optimization.

### Why Maybe
- API access to reviews is limited
- Privacy concerns with customer data
- Allied Brass may not have large review volume
- Review platforms have usage restrictions

### Prerequisites
- Review platform API access (Judge.me, Yotpo, etc.)
- Customer data handling compliance
- Sentiment analysis capability
- Review volume sufficient for analysis

### Potential Insights
- Common customer questions (address in descriptions)
- Positive sentiment keywords (use in marketing)
- Product issues mentioned (fix or address)
- Use case mentions (add to lifestyle imagery)

### Data Sources
- Shopify product reviews
- Judge.me / Yotpo / Stamped reviews
- Amazon reviews (if sold there)
- Google Shopping reviews

### Privacy Considerations
- Don't expose individual customer data
- Aggregate insights only
- Comply with review platform ToS
- Get legal review if using customer quotes

### When to Consider
- If Allied Brass has significant review volume
- When review platform offers API access
- After confirming legal/privacy compliance

---

## 6. Google Ads Creative Suggestions

### Overview
Analyze Performance Max asset performance to suggest improvements.

### Why Maybe
- Separate from feed optimization (different domain)
- Requires deep Google Ads API integration
- Asset groups have different optimization goals
- May duplicate Google's own suggestions

### Prerequisites
- Performance Max campaigns running
- Google Ads API access with asset permissions
- Asset performance data access
- Creative testing framework

### Potential Features
- Asset performance analysis
- Headline suggestions based on search data
- Image recommendations from lifestyle library
- Description line suggestions

### Technical Challenges
- PMax asset attribution is limited
- Asset combinations make isolation difficult
- Google already provides some suggestions
- May require significant API quota

### When to Consider
- If running significant PMax budget
- When feed optimization is mature
- If Google's native suggestions are insufficient

---

## 7. Real-time Personalization

### Overview
Dynamically adjust content based on user context or session data.

### Why Maybe
- Too risky for feed content (consistency important)
- GMC has strict content requirements
- Personalization at feed level is limited
- Better suited for on-site experience

### Why It's Actually Bad for Feeds
- GMC requires consistent content
- Dynamic content may violate policies
- A/B testing is better approach than personalization
- Feed content must match landing page

### Where Personalization Makes Sense
- On-site product recommendations
- Email marketing content
- Retargeting ad creative
- Landing page experiences

### Alternative Approach
Instead of feed personalization, consider:
- Audience-specific landing pages
- Dynamic remarketing creative
- Personalized email flows
- On-site product recommendations

### When to Consider
- Never for feed content
- For on-site/email only when infrastructure exists

---

## Ideas Explicitly Rejected

### Building Own Recommendation Engine
**Why Bad:** Vertex AI does this better with less effort. Don't reinvent the wheel.

### Real-time Content Changes Based on Search
**Why Bad:** Too risky, can hurt consistency, may violate GMC policies.

### Automated Publishing Without Human Review
**Why Bad:** Brand risk, compliance risk, quality control is essential.

### Heavy GMC API Direct Integration
**Why Bad:** Supplemental feed approach works, less maintenance burden.

### Replacing Human Approval Entirely
**Why Bad:** AI makes mistakes, human judgment needed for brand voice.

---

## How to Pick Up These Ideas

When you're ready to implement one of these ideas:

1. **Re-evaluate Prerequisites**: Check if the prerequisites are now met
2. **Research Current State**: Technologies may have evolved
3. **Create Full Prompt**: Use the format from `docs/prompts/` for detailed implementation
4. **Add to QUICKSTART.md**: Include a quick start prompt
5. **Update This File**: Remove from FUTURE-IDEAS.md once promoted

---

## Contributing

To add a new future idea:

1. Use the template structure above
2. Include: Overview, Why Maybe, Prerequisites, Technical Requirements
3. Add "When to Consider" criteria
4. Estimate effort level
5. Include relevant research links
