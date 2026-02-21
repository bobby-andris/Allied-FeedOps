# Phase 17: Google Shopping Intelligence & Model Research - Research

**Researched:** 2026-02-20
**Domain:** Google Shopping ranking algorithms, competitive intelligence methodology, LLM model benchmarking for product content generation
**Confidence:** MEDIUM-HIGH (ranking factors well-documented by practitioners; model pricing verified; specific Allied Brass competitive data requires live data collection in execution)

---

<user_constraints>
## User Constraints (from CONTEXT.md)

### Locked Decisions

**Competitive Analysis Scope**
- Start with Kingston Brass as known competitor, then discover additional competitors from SERP scraping
- Primary focus: impression share gap (why Allied Brass doesn't show), secondary: CTR differences when both appear
- The "5x competitor visibility" gap is from manual incognito browsing observation — this research must quantify it with data
- Critical finding from user: even for niche terms like "decorative grab bar" where Allied Brass has strong product-market fit, they appear on page 5 of Shopping results
- Full listing comparison: titles, descriptions, images, pricing position, structured attributes, reviews/ratings
- Also compare competitor landing pages (product page quality, structured data) — not just Shopping listings
- User manages Google Ads directly — include bid strategy recommendations alongside feed optimization
- User strongly suspects feed quality is the primary issue: 75K+ variant GMC IDs, master SKU descriptions written 10+ years ago by hand, many similar/undifferentiated descriptions

**Research Output Format**
- Insights with recommendations: present evidence/findings, then include "recommended prompt changes" section for Phase 20
- Optimization checklist categorized by two dimensions: (1) controllability (feed-controllable vs account-level vs external) AND (2) priority ranking within each category by expected impact
- Model comparison: clear recommendation with full supporting data so user can sanity check
- Quick wins vs medium-term vs long-term investments identified

**Data Sources & Methodology**
- Allied Brass data: Google Ads API (existing integration) + Merchant API (existing MCP + pipeline)
- Competitor data: Apify SERP scraping of Google Shopping results
- Use Google Ads Auction Insights for impression share, overlap rate, outranking share vs competitors
- General US-based scraping (no specific geo-targeting)
- Web research on ranking factors: official Google docs supplemented by industry practitioner insights (Claude's discretion on source selection)

**Model Benchmarking Approach**
- Compare: GPT-5.2, Claude (Sonnet 4.6), Gemini 2.5 Pro (three frontier families as specified)
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

### Deferred Ideas (OUT OF SCOPE)
None — discussion stayed within phase scope
</user_constraints>

---

<phase_requirements>
## Phase Requirements

| ID | Description | Research Support |
|----|-------------|-----------------|
| GOOG-01 | Deep research into Google Shopping ranking factors — what signals drive product surfacing in Shopping results (feed quality, bid strategy, seller ratings, product data completeness, structured data, historical performance, landing page quality) | Covered in Architecture Patterns sections 1-4: Shopping Graph signals, auction dynamics, feed quality hierarchy, account-level factors |
| GOOG-02 | Competitive analysis methodology — understand why competitors show 5x for search terms where Allied Brass products are better suited (analyze: auction dynamics, impression share, product data gaps, category targeting, bid strategies) | Covered in Architecture Patterns section 5: Auction Insights methodology, Apify SERP scraping approach, hypothesis framework |
| GOOG-03 | Generate actionable checklist of Google Shopping optimization factors with priority ranking — which factors are within feed control vs require account-level changes | Covered in Architecture Patterns section 6: complete factor taxonomy with controllability and priority tiers |
| MODEL-01 | Research GPT-5.2 capabilities, pricing, and best practices for product content generation — compare against current model (GPT-4o or equivalent) on quality, speed, and cost per SKU | Covered in Standard Stack section: pricing tables, quality benchmarks, cost-per-SKU calculations |
| MODEL-02 | Evaluate alternative models (Claude, Gemini, open-source) for cost-effective feed content generation with quality benchmarks | Covered in Standard Stack section: full model comparison table with verified 2026 pricing |
</phase_requirements>

---

## Summary

Phase 17 is a pure research phase with two tracks: Google Shopping ranking intelligence and model benchmarking. Both tracks produce documents that directly inform Phase 20 prompt rewrites and potential model switch.

**Track 1 — Google Shopping Intelligence:** Google's Shopping Graph is the primary algorithmic system determining product surfacing. It combines product feed quality, seller trust signals, pricing competitiveness, bid dynamics, and increasingly, on-page structured data. The Allied Brass visibility problem almost certainly stems from a combination of feed quality deficiencies (10-year-old undifferentiated descriptions, no keyword optimization, likely missing/incomplete optional attributes) compounded by lower bid competitiveness against established retailers. Seller ratings may also be a factor — Google requires 150+ reviews to display seller ratings, which affect CTR by up to 17%. The research execution plan (SERP scraping + Auction Insights + Merchant Center diagnostic) will produce data-driven evidence for each hypothesis.

**Track 2 — Model Benchmarking:** The model landscape has shifted significantly since GPT-4o was selected as the pipeline baseline. GPT-5.2 is now available at comparable or lower input cost with substantially better reasoning. Claude Sonnet 4.6 (the current Claude Sonnet model) is optimized for writing quality and instruction-following — characteristics directly relevant to product content generation. Gemini 2.5 Pro offers a different cost profile. A structured benchmark across 10-20 real Allied Brass SKUs using standardized evaluation criteria (keyword density, title formula compliance, description quality, brand voice) will produce a defensible recommendation.

**Primary recommendation:** Execute two parallel research workstreams — (1) pull Auction Insights + Merchant Center diagnostics for Allied Brass, then run Apify SERP scrapes on 20-30 representative search terms to build competitor profiles; (2) run a structured model benchmark on 15 SKUs across 4 models with a scoring rubric tied to Google Shopping ranking factors. Both outputs feed directly into Phase 20 prompt rewrites.

---

## Standard Stack

### Core (for research execution)

| Tool | Version/Access | Purpose | Why Standard |
|------|----------------|---------|--------------|
| Google Ads API (existing) | `src/feedops/integrations/google_ads_performance.py` | Pull Auction Insights (impression share, overlap rate, outranking share) | Already integrated; Shopping campaigns surface Auction Insights at ad group/campaign level |
| Google Ads MCP | `mcp__google-ads-mcp__search` | Query Auction Insights, search term performance, competitive overlap | Available in main context; faster for ad-hoc queries |
| Merchant API MCP | `mcp__merchant-api-devdocs__query_mapi_docs` + `src/feedops/integrations/merchant_center.py` | Surface disapproved/low-quality products, attribute completeness gaps | Existing integration for product diagnostic |
| Apify Google Shopping Scraper | `mcp__Apify__call-actor` — actor: `consummate_mandala/google-shopping-scraper` or `damilo/google-shopping-apify` | SERP scraping for competitor listing analysis | Project already has Apify MCP configured; pay-per-event ~$0.0015/result |
| Supabase MCP | `mcp__supabase__execute_sql` | Query existing performance data, search term coverage, variant_index | Already integrated; source of truth for coverage analysis |
| OpenAI API (existing pipeline) | `gpt-4o` (current), `gpt-5.2` (benchmark target) | Model benchmark execution | Pipeline Python code already calls OpenAI |
| Claude API | `claude-sonnet-4-6` | Model benchmark — Claude track | Anthropic API available |
| Gemini API (existing pipeline) | `gemini-2.5-pro` | Model benchmark — Gemini track | `feedops-gemini-api-key` already exists as GCP secret |

### Supporting

| Tool | Purpose | When to Use |
|------|---------|-------------|
| Google Keyword Planner (existing MCP) | Pull search volume data for representative search terms to select SERP scrape targets | Before SERP scraping — prioritize terms with actual search volume |
| `search_queries` Supabase table | Identify what terms Allied Brass products currently appear for vs targeted terms | Cross-reference with SERP competition findings |
| `performance_baselines` + `performance_snapshots` | Establish pre-research baseline metrics to compare against post-Phase-20 results | Evidence for eventual impact measurement |
| agent-browser skill | Navigate Google Shopping manually for qualitative competitive observations | Supplement SERP data with visual audit |

### Research Output Storage

**Recommendation (Claude's Discretion): Store as markdown docs in `docs/research/` within the repo.**

Rationale: Downstream agents (Phase 20 prompt rewriter) need to read these documents. Repo docs are directly accessible via `Read` tool with no authentication. Notion requires MCP calls and is harder for agents to consume systematically. Format: one doc per track, structured for machine readability (tables, clear sections, bullet points).

```
docs/research/
├── google-shopping-ranking-factors.md     # GOOG-01, GOOG-03 output
├── competitive-gap-analysis.md            # GOOG-02 output
└── model-comparison.md                    # MODEL-01, MODEL-02 output
```

---

## Architecture Patterns

### Pattern 1: Google Shopping Ranking Signal Taxonomy

**What:** Google Shopping ranking is determined by a two-layer system: (1) auction eligibility (whether a product enters the auction at all) and (2) auction rank (position within the auction). Feed quality primarily determines eligibility and relevance; bids + quality signals determine rank.

**The Shopping Graph:** Google's Shopping Graph aggregates 45B+ product listings. It normalizes product data across merchants using GTIN/MPN as primary identifiers, then scores products on data completeness, seller reputation, pricing accuracy, and review signals. This is the "index" — products not well-represented in the Shopping Graph get fewer auction eligibility opportunities.

**Confirmed ranking signal hierarchy (HIGH confidence, multiple practitioner sources + Google official docs):**

**Feed-Controllable Factors:**
1. **Product title quality** — Highest-impact feed element. First 70 chars determine match to search intent. Format: `[Brand] [Product Type] [Key Attribute 1] [Key Attribute 2] — [Differentiator]`. Google weights front-loaded terms most heavily. Allied Brass titles are hand-written from 10 years ago — likely not keyword-optimized, not structured for modern Shopping intent patterns.
2. **Product description quality** — First 160-180 chars act as a mini-ad. Keywords at front rank higher. 500-1000 char sweet spot. Allied Brass descriptions are "similar, not e-commerce optimized" — this is the primary addressable gap.
3. **Attribute completeness** — GTIN/MPN presence enables better product matching. For bath hardware: material, finish, dimensions, mounting type, ADA compliance, weight capacity are all category-relevant attributes. Missing attributes reduce eligibility for attribute-filtered searches.
4. **Google Product Category specificity** — Targeting to Level 4-5 depth improves relevance matching. Shallow categorization = competing in too-broad buckets.
5. **Product type taxonomy** — Merchant-defined; deepest level possible. "Bath Hardware > Grab Bars > Decorative Grab Bars" vs just "Bath Hardware" changes what searches the product is eligible for.
6. **Structured title / Structured description** — Required when using AI-generated content (`digital_source_type=trained_algorithmic_media`). **Critical: if both `title` and `structured_title` are submitted, Google uses ONLY `title`.** Allied FeedOps already uses structured fields correctly per CLAUDE.md.
7. **Image quality** — Minimum 800×800px (1500×1500px recommended). White background for main image. 15-25% CTR impact from image quality. Allied Brass product images may be lower resolution from older catalog.
8. **Feed health / Merchant Center errors** — Any disapprovals silently suppress products. Zero tolerance — every disapproval needs resolution.

**Account-Level Factors:**
1. **Bid strategy and bid levels** — Determines position within auction once eligible. Target ROAS is recommended once 30+ conversions exist. Manual CPC gives control during initial optimization. Under-bidding = showing in positions below fold where CTR collapses.
2. **Impression share lost to rank vs budget** — Two different problems requiring different solutions. Lost IS (rank) = raise bids or improve feed quality. Lost IS (budget) = increase daily budget.
3. **Historical CTR and conversion rate** — Google's algorithm uses historical performance signals to predict future CTR. Products with poor historical performance enter fewer auctions.
4. **Campaign structure** — Ad group organization affects bid granularity. Product-type-level ad groups allow bid differentiation between high-margin and low-margin items.

**External Factors (cannot be directly controlled via feed):**
1. **Seller ratings** — 150+ reviews in past 12 months required to display. Verified 17% CTR lift when displayed. Need third-party review aggregator (Trustpilot, Shopper Approved, etc.) enrolled with Google.
2. **Website authority and backlinks** — Product pages with more backlinks rank higher. Allied Brass direct-to-consumer Shopify site may have lower domain authority than Home Depot / Wayfair / Amazon.
3. **Pricing competitiveness** — Google Shopping Graph tracks price history. Products priced significantly above category average get fewer impressions even with strong feeds.
4. **Reviews at product level** — Product-level ratings (not just seller ratings) are a ranking input. Products with zero reviews are disadvantaged.
5. **Competitor domain authority** — Kingston Brass, Signature Hardware, Delta Faucet all sell via Home Depot and Amazon which have 90+ Domain Authority — explains why they appear on page 1 even for niche terms.

### Pattern 2: Auction Insights Methodology

**What:** Google Ads provides Auction Insights reports for Shopping campaigns showing impression share, overlap rate, and outranking share vs specific competitors. This is the primary quantitative data source for the competitive gap analysis.

**Available metrics (Shopping campaigns only):**
- `Impression Share`: % of eligible impressions received. Target: >30% to be considered visible.
- `Overlap Rate`: % of auctions where both you and competitor appeared. High overlap + low outranking = competitor consistently wins same auctions.
- `Outranking Share`: % of shared auctions where your ad ranked above theirs or appeared when theirs didn't.

**Limitation:** Auction Insights only shows competitors Allied Brass actually competes with in auctions. If Allied Brass has very low impression share (entering few auctions), the competitor list may be incomplete — which itself is diagnostic.

**Query approach using existing Google Ads API integration:**
```python
# Google Ads GAQL query for Auction Insights (Shopping campaign)
# Use shopping_performance_view for product-level metrics
# Use auction_insight_view for competitor comparison
SELECT
  auction_insight.domain,
  metrics.auction_insight_search_impression_share,
  metrics.auction_insight_search_overlap_rate,
  metrics.auction_insight_search_outranking_share
FROM auction_insight_view
WHERE campaign.advertising_channel_type = 'SHOPPING'
  AND segments.date DURING LAST_30_DAYS
```

**Note:** `auction_insight_view` must be available in the existing Google Ads API client. If not already implemented, it's a GAQL query addition to `google_ads_performance.py`.

### Pattern 3: SERP Scraping for Competitor Intelligence

**What:** Apify Google Shopping scraper extracts live Shopping tab listings for target search terms. Returns: title, description, price, seller, rating, GTIN/MPN, images. Enables direct comparison of Allied Brass listings vs competitors for the same query.

**Apify actor options (confirmed available):**
- `consummate_mandala/google-shopping-scraper` — Most feature-complete, structured output
- `damilo/google-shopping-apify` — Alternative option
- `epctex/google-shopping-scraper` — Google Shopping Data Extractor

**Cost:** ~$0.0015 per result. 20 search terms × 30 results each = 600 results = ~$0.90. Budget is not a concern.

**Target search terms for Allied Brass (Claude's Discretion — 25-30 terms recommended):**

Tier 1 — Decorative grab bars (user-identified case study with strong PMF):
- "decorative grab bar"
- "decorative bathroom grab bar"
- "grab bar chrome bathroom"
- "designer grab bar shower"
- "grab bar towel bar combo"

Tier 2 — Allied Brass core product categories:
- "brass toilet paper holder"
- "bathroom robe hook brass"
- "towel bar antique brass"
- "bathroom accessories set brass"
- "oil rubbed bronze grab bar"

Tier 3 — High commercial intent category terms:
- "ADA grab bar bathroom"
- "shower grab bar chrome"
- "polished brass bath accessories"
- "satin nickel towel bar"
- "bathroom hardware set"

**Competitor extraction approach:**
For each search term, capture all visible listings (top 10-15). Aggregate by domain/seller to identify who appears most frequently. Compare Allied Brass listing structure (title format, attributes shown, price position) vs top competitors.

**Landing page comparison:** For top 3 competitors per category, use agent-browser to capture: product page structured data, image quality, review count, description length, attribute completeness.

### Pattern 4: Merchant Center Diagnostic Methodology

**What:** Google Merchant Center surfaces product-level quality issues: disapprovals, limited performance items, missing attributes, price mismatches. Accessing this data via the existing Merchant API integration identifies silent suppressions.

**Key diagnostic queries using Merchant API:**
```sql
-- Products with disapprovals (item_issues field)
SELECT id, offer_id, title, aggregated_reporting_context_status, item_issues
FROM product_view
WHERE aggregated_reporting_context_status != 'ELIGIBLE'

-- Product attribute completeness audit
SELECT id, offer_id, title,
  (SELECT COUNT(*) FROM item_issues) as issue_count
FROM product_view
ORDER BY issue_count DESC
LIMIT 100
```

**Attribute completeness check:** Compare required vs recommended attributes across catalog. Bath hardware recommended attributes not commonly submitted: `material`, `pattern`, `finish_type`, `item_weight`, `product_length`, `product_width`.

### Pattern 5: Allied Brass Competitive Gap Hypothesis Framework

**What:** Before executing data collection, define testable hypotheses so data collection is purposeful. Evidence should either confirm or disconfirm each hypothesis.

**Hypotheses (ranked by prior probability based on user context):**

| # | Hypothesis | Prior Probability | Evidence Needed |
|---|-----------|-------------------|-----------------|
| H1 | Feed quality is primary cause: titles/descriptions not keyword-optimized, descriptions undifferentiated across variants, missing intent signals that determine auction eligibility | HIGH | Auction Insights: low impression share on terms Allied Brass should win. SERP: competitor titles contain explicit keywords Allied Brass titles lack. |
| H2 | Attribute completeness gap: missing category-specific attributes reduce eligibility for filtered searches | HIGH | Merchant Center diagnostic: flag missing recommended attributes. SERP: competitor listings show attributes Allied Brass doesn't submit. |
| H3 | Competitor domain authority advantage: Kingston Brass, Delta, etc. sell via Home Depot/Amazon which have 90+ DA; Allied Brass Shopify site may have lower authority affecting organic Shopping and landing page quality scores | MEDIUM | Compare domain authority of competitor domains appearing in Shopping results. Direct-to-consumer sites will consistently have lower DA than marketplace listings. |
| H4 | Bid competitiveness gap: Allied Brass bids may not be competitive enough to win above-fold positions even when product is eligible | MEDIUM | Auction Insights: is impression share lost to budget vs rank? Outranking share vs specific competitors. |
| H5 | Seller reputation signals: Allied Brass may not have sufficient seller reviews to display star ratings, reducing CTR and indirectly affecting Quality Score | MEDIUM | Check Google Merchant Center seller rating status. 150 reviews/12 months required threshold. |
| H6 | Pricing disadvantage: Allied Brass premium decorative hardware priced above category average for Google's pricing model | LOW-MEDIUM | Compare prices in SERP results. Bath hardware is a premium category; price may not be disqualifying. |
| H7 | Product type/category miscategorization: products assigned to shallow category levels, missing niche category targeting | LOW | Review current product_type and google_product_category values in supplemental feed. |

### Pattern 6: Optimization Factor Checklist (Research Output Template)

The research execution phase must produce a checklist in this format for GOOG-03:

```markdown
## Feed-Controllable Factors (Ordered by Expected Impact)

### Priority 1: Quick Wins (1-2 weeks)
- [ ] **Title keyword optimization** — Rewrite titles using [Brand] [Type] [Finish] [Key Feature] format, front-load high-intent terms. Expected impact: HIGH. All SKUs.
- [ ] **Description rewrite** — First 160 chars = keyword-rich summary. Full 500-1000 chars for long-tail coverage. Expected impact: HIGH. All SKUs.
- [ ] **Merchant Center error resolution** — Fix all disapproved products. Expected impact: CRITICAL (disapprovals = zero impressions). Immediate.

### Priority 2: Medium Term (1-4 weeks)
- [ ] **Attribute completeness** — Add material, dimensions, finish_type, weight_capacity for grab bars. Expected impact: MEDIUM.
- [ ] **Product type depth** — Deepen to Level 4-5. Expected impact: MEDIUM.
- [ ] **Google Product Category specificity** — Audit and correct shallow categorizations.

### Priority 3: Longer Term (1-3 months)
- [ ] **Image quality upgrade** — Ensure 1500×1500px minimum for all hero images.
- [ ] **Product review acquisition** — Enable product reviews in Merchant Center, add review schema to PDPs.

## Account-Level Factors (Ordered by Expected Impact)

### Priority 1: Quick Wins
- [ ] **Impression share audit** — Is IS loss from rank or budget? Different fix for each.
- [ ] **Bid adjustment for decorative grab bars** — Increase bids for highest PMF products to win above-fold.

### Priority 2: Medium Term
- [ ] **Campaign restructure** — Split high-margin products into separate ad groups with higher bids.
- [ ] **Target ROAS** — Switch from manual CPC once conversion data sufficient (30+ conversions).

## External Factors (Cannot Be Directly Controlled)

- [ ] **Seller ratings** — Investigate enrollment in Google-approved review partner (e.g., Shopper Approved).
- [ ] **Domain authority** — Long-term content strategy; not addressable in v1.2.
- [ ] **Competitor pricing** — Monitor, respond where pricing is uncompetitive.
```

---

## Model Comparison Research

### Current State (2026-02-20)

| Model | Input $/MTok | Output $/MTok | Batch Discount | Prompt Cache | Context Window |
|-------|-------------|--------------|---------------|--------------|----------------|
| GPT-4o (current baseline) | $2.50 | $10.00 | 50% | 90% input | 128K |
| GPT-5.2 (benchmark target) | $1.75 | $14.00 | 50% | 90% input | 400K |
| Claude Sonnet 4.6 | $3.00 | $15.00 | 50% | 90% input | 200K |
| Gemini 2.5 Pro | $1.25 | $10.00 | 50% | N/A | 1M |

**Source confidence:** GPT-5.2 pricing from OpenAI API pricing page (HIGH). Claude Sonnet 4.6 from Anthropic platform docs (HIGH). Gemini 2.5 Pro from Google AI for Developers pricing (HIGH). GPT-4o from OpenAI pricing page (HIGH).

### Cost-per-SKU Estimates

**Assumptions:** Allied Brass SKU generation = ~2,000 input tokens (system prompt + evidence + product data) + ~800 output tokens (title + description + attributes). Using batch API pricing.

| Model | Batch Input Cost | Batch Output Cost | Cost per SKU | Cost for 2,784 SKUs |
|-------|-----------------|-------------------|-------------|---------------------|
| GPT-4o (current) | $1.25/MTok | $5.00/MTok | $0.0065 | $18.10 |
| GPT-5.2 | $0.875/MTok | $7.00/MTok | $0.0073 | $20.32 |
| GPT-5.2 with cache | $0.175/MTok cached input | $7.00/MTok | ~$0.003 | ~$8.35 |
| Claude Sonnet 4.6 | $1.50/MTok | $7.50/MTok | $0.0090 | $25.06 |
| Claude with cache | $0.30/MTok cached input | $7.50/MTok | ~$0.0066 | ~$18.37 |
| Gemini 2.5 Pro | $0.625/MTok | $5.00/MTok | $0.0053 | $14.76 |

**Key insight:** All models fall well under $500 for the full catalog at batch pricing. Cost is not the differentiating factor — quality is. The model benchmark should focus on quality scoring.

**GPT-5.2 vs GPT-4o tradeoff:** GPT-5.2 has higher output cost but better reasoning and instruction-following. For product content where output quality directly affects revenue, the ~13% cost increase (without caching) is justified if quality improves meaningfully. With caching (reusable system prompt), GPT-5.2 is actually cheaper than GPT-4o.

### Model Quality Signals for Product Content (from research)

**Claude Sonnet 4.6 strengths (MEDIUM confidence — multiple practitioner sources):**
- Superior writing quality and instruction-following precision
- More consistent voice/style across outputs
- Outputs read as "human-written" — important for avoiding AI content penalties
- Optimized for writing-intensive, review-intensive workflows

**GPT-5.2 strengths (MEDIUM confidence):**
- Strong reasoning for complex product attribute extraction
- 400K context window useful if processing large product data alongside examples
- Better at following structured output formats (JSON with specific schema)
- More aggressively priced than GPT-4 generation

**Gemini 2.5 Pro strengths (MEDIUM confidence):**
- 1M context window — could include full product catalog context for cross-SKU consistency
- Lowest raw cost per token
- Caveat: verbosity issue documented — often generates 30-40% more tokens than Claude/GPT for equivalent output, partially eroding cost advantage

**Current model (GPT-4o) weaknesses relevant to this use case (LOW confidence — inferred from practitioner comparisons):**
- Less consistent instruction-following than GPT-5.2 or Claude Sonnet 4.6
- Older training data (pre-2026 Shopping algorithm changes)
- More expensive than GPT-5.2 at current pricing

### Model Benchmark Execution Plan

**SKU selection for benchmark (Claude's Discretion — 15 SKUs recommended):**

Select 5 SKUs per category cluster to test model performance across product complexity:
- 5 grab bars (decorative, different finishes — user-identified PMF category)
- 5 towel/bath accessory SKUs (mid-tier complexity, many finish variants)
- 5 faucet-adjacent hardware SKUs (higher attribute complexity)

**Evaluation rubric (tied to Google Shopping ranking factors):**

| Criterion | Weight | How to Measure |
|-----------|--------|----------------|
| Title formula compliance | 20% | Does title follow [Brand] [Type] [Finish] [Key Attribute] structure? First 70 chars optimized? |
| Keyword density (appropriate) | 20% | Does title+description contain the natural language keywords for this product type? No stuffing? |
| Description quality (first 160 chars) | 20% | Does the opener answer implicit shopper questions? Front-load key attributes? |
| Accuracy (no fabrication) | 25% | Are all claims verifiable from product_catalog data? Any invented specs? |
| Brand voice consistency | 15% | Matches Allied Brass premium positioning? Not generic/commodity language? |

**Scoring approach:**
- Human scoring (user) on 1-5 scale per criterion × weights = composite score
- LLM-as-judge for scale: use one model (Claude) to score outputs from other models using rubric
- Blind evaluation: label outputs by letter (A/B/C/D) not model name during scoring

---

## Don't Hand-Roll

| Problem | Don't Build | Use Instead | Why |
|---------|-------------|-------------|-----|
| SERP data collection | Custom web scraper | Apify Google Shopping actors | Apify handles bot detection, proxies, pagination, rate limiting. Custom scraper would need all of this |
| Auction Insights data | Manual CSV export | Google Ads API GAQL query | Existing `google_ads_performance.py` already has client setup; just need new GAQL query |
| Model quality scoring at scale | Custom evaluation framework | LLM-as-judge pattern (Claude evaluates outputs) | Established methodology; prevents subjective bias; reproducible |
| Competitor domain authority | Custom link analysis | Moz/Ahrefs third-party lookup or simple search | DA is an external signal; not worth building tooling to measure |

---

## Common Pitfalls

### Pitfall 1: Auction Insights Shows No Competitors
**What goes wrong:** If Allied Brass impression share is extremely low (<5%), the Auction Insights report may be empty or show very few competitors because Allied Brass enters so few auctions that the data is statistically insufficient.
**Why it happens:** Auction Insights requires minimum auction participation to report. Very low impression share = insufficient sample.
**How to avoid:** Check impression share FIRST. If IS < 5%, the competitive gap isn't being measured by Auction Insights — it means Allied Brass is barely in the auction at all. This is actually the most important diagnostic finding: the problem is eligibility (feed quality/disapprovals) not position within auctions.
**Warning signs:** Empty Auction Insights report, "–" values for all competitors.

### Pitfall 2: SERP Scraping Misses Geo/Personalization Effects
**What goes wrong:** Google Shopping results vary significantly by location, search history, and device. Scraped results may not match what users in Allied Brass's target markets see.
**Why it happens:** Shopping Graph personalizes results using location signals, prior purchase behavior, and device context.
**How to avoid:** Run scrapes with US-based proxies (Apify supports US geo-targeting). Accept that scrape results are a directional signal, not exact user experience. Document geo assumption in research output.
**Warning signs:** Competitors showing in scraped results that don't appear in manual incognito tests, or vice versa.

### Pitfall 3: Model Benchmark Evaluates Wrong Quality Signals
**What goes wrong:** Models are scored on general content quality (fluency, coherence) rather than Google Shopping-specific signals (keyword coverage, attribute completeness, title formula).
**Why it happens:** Generic LLM evaluation frameworks optimize for human preference, not Shopping ranking factors.
**How to avoid:** Use the rubric defined in Architecture Pattern section above. Weight accuracy (no fabrication) at 25% — this is non-negotiable for product data integrity.
**Warning signs:** A model that writes beautiful prose but invents specs scores high generically but would fail in production.

### Pitfall 4: structured_title vs title Confusion in Feed
**What goes wrong:** Submitting both `structured_title` and `title` attributes — Google silently uses only `title`, ignoring `structured_title`.
**Why it happens:** Google's Merchant Center documentation distinguishes these fields but the behavior is counterintuitive (structured_title exists for compliance tracking, not as a replacement).
**How to avoid:** Allied FeedOps already handles this correctly (CLAUDE.md notes the `FEEDOPS_GMC_STRUCTURED_ONLY=1` flag behavior). Document in research output that Phase 20 must preserve this pattern.
**Warning signs:** Content appearing in `structured_title` field not showing in Shopping listings.

### Pitfall 5: Assuming Feed Quality is the Only Problem
**What goes wrong:** Research focuses entirely on feed optimization while ignoring bid strategy, and results are disappointing after Phase 20 because the bid gap wasn't addressed.
**Why it happens:** Feed quality is the most controllable variable, so it gets over-weighted.
**How to avoid:** Research must quantify the bid competitiveness gap from Auction Insights (outranking share). If Allied Brass consistently loses to same-eligibility competitors, bid strategy is part of the fix alongside feed quality.
**Warning signs:** High impression share for categories where Allied Brass does appear but low outranking share = bid problem, not feed problem.

---

## Code Examples

### Auction Insights GAQL Query (Google Ads API)

```python
# Add to src/feedops/integrations/google_ads_performance.py or new google_ads_auction.py
# Source: Google Ads API GAQL reference (auction_insight_view)

AUCTION_INSIGHTS_QUERY = """
SELECT
  auction_insight.domain,
  metrics.auction_insight_search_impression_share,
  metrics.auction_insight_search_overlap_rate,
  metrics.auction_insight_search_outranking_share,
  campaign.name
FROM auction_insight_view
WHERE campaign.advertising_channel_type = 'SHOPPING'
  AND segments.date DURING LAST_30_DAYS
ORDER BY metrics.auction_insight_search_impression_share DESC
"""

# Use existing _load_client() pattern from google_ads_performance.py
def fetch_auction_insights(customer_id: str) -> list[dict]:
    client = _load_client()
    ga_service = client.get_service("GoogleAdsService")
    response = ga_service.search(
        customer_id=customer_id,
        query=AUCTION_INSIGHTS_QUERY
    )
    results = []
    for row in response:
        results.append({
            "domain": row.auction_insight.domain,
            "impression_share": row.metrics.auction_insight_search_impression_share,
            "overlap_rate": row.metrics.auction_insight_search_overlap_rate,
            "outranking_share": row.metrics.auction_insight_search_outranking_share,
            "campaign": row.campaign.name
        })
    return results
```

### Apify SERP Scrape via MCP

```python
# Use mcp__Apify__call-actor in main context
# Actor: consummate_mandala/google-shopping-scraper
# Input schema:
{
  "queries": [
    "decorative grab bar",
    "decorative bathroom grab bar chrome",
    "towel bar brass bathroom"
    # ... up to 30 terms
  ],
  "countryCode": "US",
  "maxItems": 30  # per query
}
# Returns: title, price, seller, url, rating, images, GTIN/MPN per listing
```

### LLM-as-Judge Scoring Pattern

```python
# Use Claude Sonnet 4.6 to evaluate model outputs against rubric
# Run after collecting outputs from all 4 models for same SKU

JUDGE_PROMPT = """
You are evaluating AI-generated Google Shopping product content for quality.

Product data: {product_data}

Content to evaluate:
{content}

Score each criterion 1-5:
1. Title formula (Brand + Type + Finish + Key Attribute in first 70 chars): __/5
2. Keyword coverage (natural language terms a shopper would use, no stuffing): __/5
3. Description opener quality (first 160 chars front-loads key attributes): __/5
4. Accuracy (all claims verifiable from product data, nothing invented): __/5
5. Brand voice (premium positioning, not generic/commodity): __/5

Weighted score: (title×0.20 + keywords×0.20 + description×0.20 + accuracy×0.25 + voice×0.15) × 20 = __/100

Justify each score in 1 sentence.
"""
```

---

## State of the Art

| Old Approach | Current Approach | When Changed | Impact |
|--------------|------------------|--------------|--------|
| Keyword stuffing in titles | Keyword-intent matching (natural language) | 2023-2024 algorithm updates | Stuffed titles now penalized; natural language titles that match search intent are rewarded |
| Single main image | Multiple images + lifestyle images | 2024-2025 | Additional images shown in Shopping carousel; lifestyle images boost CTR for home décor categories |
| Optional structured data | Required for AI content (structured_title + digital_source_type) | October 2025 | AI-generated content MUST use structured_title attribute |
| Generic product descriptions | Attribute-rich descriptions with category-specific keywords | Ongoing | Google Shopping Graph uses descriptions as knowledge base input for AI Overviews |
| Enhanced CPC bid strategy | Target ROAS (smart bidding) | March 31, 2025 (ECPC deprecated) | ECPC removed; campaigns that weren't migrated defaulted to Manual CPC |
| GPT-4o as frontier model | GPT-5.2, Claude Sonnet 4.6, Gemini 2.5 Pro | August 2025 (GPT-5.2 release) | GPT-4o is now a mid-tier model; frontier alternatives offer better quality or lower cost |

**Deprecated/outdated:**
- Enhanced CPC (ECPC): Deprecated March 2025, campaigns defaulted to Manual CPC — check if Allied Brass campaigns were migrated
- Content API: Still works until August 2026, but Merchant API is the forward path — no urgency but document
- GPT-4o as "best" model: GPT-5.2 released August 2025 with better reasoning at comparable/lower batch cost

---

## Open Questions

1. **Allied Brass Merchant Center account ID**
   - What we know: Google Ads customer ID is `6253381786` (confirmed in CLAUDE.md)
   - What's unclear: Merchant Center account ID (different from Google Ads ID) — needed for Merchant API diagnostic queries
   - Recommendation: User to provide MC account ID before executing Phase 17 research tasks. Check STATE.md note: "GMC merchant account ID needed for Phase 19 Merchant API integration"

2. **Current campaign type (Standard Shopping vs Performance Max)**
   - What we know: Auction Insights for Shopping campaigns only works with Standard Shopping campaigns
   - What's unclear: Whether Allied Brass is running Standard Shopping, Performance Max, or both
   - Recommendation: User to confirm before Auction Insights pull. If Performance Max only, different reporting approach needed.

3. **Current bid strategy on Shopping campaigns**
   - What we know: ECPC deprecated March 2025; campaigns may have defaulted to Manual CPC
   - What's unclear: What bid strategy is currently active
   - Recommendation: Document current bid strategy as part of Phase 17 execution — baseline for any bid recommendations

4. **Seller rating status**
   - What we know: 150+ reviews in 12 months required to display seller ratings
   - What's unclear: Does Allied Brass currently display seller ratings? How many reviews does the Shopify store have?
   - Recommendation: Check Google Merchant Center seller ratings section during execution

5. **GPT-5.2 availability for API calls**
   - What we know: GPT-5.2 was released August 2025; pricing confirmed at $1.75/$14 per MTok
   - What's unclear: Is GPT-5.2 accessible via the project's existing OpenAI API key? Rate limits?
   - Recommendation: Test API access before designing benchmark; fall back to GPT-4o-based comparison if access is blocked

---

## Sources

### Primary (HIGH confidence)
- OpenAI API Pricing page (platform.openai.com/docs/pricing) — GPT-4o and GPT-5.2 pricing
- Anthropic Claude pricing (platform.claude.com/docs/en/about-claude/pricing) — Claude Sonnet 4.6 pricing
- Google AI for Developers Gemini API pricing (ai.google.dev/gemini-api/docs/pricing) — Gemini 2.5 Pro pricing
- Google Merchant Center Help (support.google.com/merchants/answer/6324415) — structured_title vs title behavior
- Google Ads Help (support.google.com/google-ads/answer/2579754) — Auction Insights metrics for Shopping campaigns

### Secondary (MEDIUM confidence, verified against multiple practitioner sources)
- [Google's Shopping Graph Explained](https://www.appearonline.co.uk/blog/google-shopping-graph-explained) — Shopping Graph signal taxonomy
- [FeedOps Google Shopping Feed Optimization Guide 2025](https://feedops.com/guide/google-shopping-feed-optimization-guide/) — Feed optimization patterns
- [Search Engine Journal: Google Shopping Rankings](https://www.searchenginejournal.com/google-shopping-rankings-key-factors-for-retailers/537492/) — Correlation study findings
- [WebAppick: Google Shopping Visibility 2026](https://webappick.com/how-to-increase-visibility-on-google-shopping/) — Impression share troubleshooting
- [Claude Sonnet 4.6 pricing — Apidog](https://apidog.com/blog/claude-sonnet-4-6-pricing/) — Pricing verification
- [VentureBeat: Claude Sonnet 4.6](https://venturebeat.com/technology/anthropics-sonnet-4-6-matches-flagship-ai-performance-at-one-fifth-the-cost) — Quality benchmark context
- [Apify Google Shopping Scraper](https://apify.com/consummate_mandala/google-shopping-scraper) — Actor capability and pricing

### Tertiary (LOW confidence — directional only)
- Model quality comparisons (Cosmic, DataStudios, GetPassionFruit) — Multiple practitioner comparison articles; quality assessments are subjective and vary by use case; treat as directional signals only, not authoritative benchmarks
- [180 Marketing correlation study](https://www.180marketing.com/google-shopping-ranking-factors/) — Content body not accessible; summary from SEJ secondary citation only

---

## Metadata

**Confidence breakdown:**
- Google Shopping ranking signals: HIGH — core factors confirmed by Google official docs + multiple practitioner sources citing consistent hierarchy
- Competitive analysis methodology: HIGH — Auction Insights API and Apify scraping approach are well-documented with existing project integrations
- Model pricing: HIGH — pulled from official pricing pages for all four models
- Model quality benchmarks: MEDIUM — practitioner sources agree on general quality hierarchy but specific product content generation benchmarks require empirical testing
- Cost-per-SKU estimates: MEDIUM — calculated from real pricing with reasonable token count assumptions; actual costs will vary by prompt length

**Research date:** 2026-02-20
**Valid until:** 2026-03-22 (model pricing changes frequently; re-verify before execution if >2 weeks elapsed)
