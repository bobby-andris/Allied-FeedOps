# Phase 17: Google Shopping Intelligence & Model Research - Context

**Gathered:** 2026-02-20
**Status:** Ready for planning

<domain>
## Phase Boundary

Pure research phase producing actionable documents that inform Phase 20 (prompt updates and model switch). Two tracks: (1) Google Shopping ranking intelligence — what signals drive product surfacing, why competitors outperform Allied Brass, and what feed changes will improve visibility; (2) Model comparison — benchmark GPT-5.2, Claude, and Gemini for product content generation with a clear recommendation. No code changes or deployments in this phase.

</domain>

<decisions>
## Implementation Decisions

### Competitive Analysis Scope
- Start with Kingston Brass as known competitor, then discover additional competitors from SERP scraping
- Primary focus: impression share gap (why Allied Brass doesn't show), secondary: CTR differences when both appear
- The "5x competitor visibility" gap is from manual incognito browsing observation — this research must quantify it with data
- Critical finding from user: even for niche terms like "decorative grab bar" where Allied Brass has strong product-market fit, they appear on page 5 of Shopping results
- Full listing comparison: titles, descriptions, images, pricing position, structured attributes, reviews/ratings
- Also compare competitor landing pages (product page quality, structured data) — not just Shopping listings
- User manages Google Ads directly — include bid strategy recommendations alongside feed optimization
- User strongly suspects feed quality is the primary issue: 75K+ variant GMC IDs, master SKU descriptions written 10+ years ago by hand, many similar/undifferentiated descriptions

### Research Output Format
- Insights with recommendations: present evidence/findings, then include "recommended prompt changes" section for Phase 20
- Optimization checklist categorized by two dimensions: (1) controllability (feed-controllable vs account-level vs external) AND (2) priority ranking within each category by expected impact
- Model comparison: clear recommendation with full supporting data so user can sanity check
- Quick wins vs medium-term vs long-term investments identified

### Data Sources & Methodology
- Allied Brass data: Google Ads API (existing integration) + Merchant API (existing MCP + pipeline)
- Competitor data: Apify SERP scraping of Google Shopping results
- Use Google Ads Auction Insights for impression share, overlap rate, outranking share vs competitors
- General US-based scraping (no specific geo-targeting)
- Web research on ranking factors: official Google docs supplemented by industry practitioner insights (Claude's discretion on source selection)

### Model Benchmarking Approach
- Compare: GPT-5.2, Claude, Gemini (three frontier families as specified in requirements)
- Current baseline: GPT-4o (what pipeline uses today)
- Test on real Allied Brass SKUs (10-20 products across categories)
- Quality scoring priorities: ranking performance (impressions + CTR) most important, but also accuracy, keyword targeting, brand voice, persuasiveness
- Cost target: under $500 for full catalog (2,784 master SKUs) if possible, show quality-cost tradeoff
- Speed is secondary to quality and cost
- Prompt testing: same prompt baseline across all models first, then model-optimized prompts for top 2 performers
- Output: clear model recommendation with full comparison data

### Claude's Discretion
- Research document storage format (repo docs vs Notion — recommend whatever works best for downstream agents)
- Web research source selection for ranking factors
- Exact number of search terms to investigate for SERP scraping (enough to be statistically meaningful)
- Geo-targeting approach for SERP scraping
- Which specific SKUs to use for model benchmarking sample

</decisions>

<specifics>
## Specific Ideas

- "We have some of the nicest decorative grab bars on the market and all of our customers tell us this" — decorative grab bars as a case study for the competitive gap analysis (strong product-market fit, terrible Shopping visibility)
- The core project purpose: optimize feed quality through AI-rewritten titles and descriptions to increase visibility and sales on Shopify
- 75K+ unique GMC IDs across ~2,784 master SKUs with 28 finish variants each
- Descriptions written 10+ years ago by one person (user's father) — many similar, not e-commerce optimized for modern landscape

</specifics>

<deferred>
## Deferred Ideas

None — discussion stayed within phase scope

</deferred>

---

*Phase: 17-google-shopping-intelligence-model-research*
*Context gathered: 2026-02-20*
