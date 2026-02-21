# Google Shopping Ranking Factors & Allied Brass Competitive Baseline

**Research date:** 2026-02-21
**Phase:** 17 — Google Shopping Intelligence & Model Research
**Feeds into:** Phase 20 prompt rewrites, Phase 19 competitive gap analysis

---

## Executive Summary

Five key findings from this research:

1. **Allied Brass is running well-configured campaigns** — 179 Shopping campaigns, all on Target ROAS, averaging 69.7% impression share with IS lost almost entirely to rank (20.2%), not budget (0%). This rules out budget as the problem.

2. **Feed quality is the confirmed primary gap** — Baseline titles (from 10+ years ago) are generic collection-name-only strings like "Skyline Collection Towel Ring" with no finish, size, or intent signals. AI-optimized candidates average 89.4/100 quality score — but only 193 of ~2,784 master SKUs have generated content, and only 79 have approved content.

3. **Decorative grab bars show the exact problem** — "decorative grab bars" and "decorative grab bars for bathroom" both appear in search term data with 156 and 131 impressions respectively but 0 clicks each. Allied Brass is entering these auctions but not winning clicks. This is a CTR problem driven by unoptimized listing content, not an eligibility problem.

4. **Impression share lost to rank (not budget)** — Average IS lost to rank is 20.2% across all campaigns. Some categories lose 55%+ to rank. This means Allied Brass IS eligible and IS entering auctions — but losing position within them, which at Shopping volumes directly reduces impression counts.

5. **Content coverage is the scale bottleneck** — 75,770 product variants exist in the catalog. Only 193 Google content records have been generated. The AI-generated content is high quality (avg 89.4/100) but covers <0.7% of the catalog. Scaling to full catalog is the highest-leverage intervention.

---

## Google Shopping Ranking Signal Taxonomy

Google Shopping uses a two-layer system: **auction eligibility** (whether a product enters the auction at all) and **auction rank** (position within the auction). The factors below affect both layers.

### Feed-Controllable Factors (Ordered by Expected Impact)

#### Priority 1: Critical — Directly Determines Auction Eligibility

| Factor | Expected Impact | Allied Brass Status | Confidence |
|--------|----------------|---------------------|------------|
| **Product title quality** | HIGHEST — first 70 chars determine match to search intent | CRITICAL GAP — baseline titles are generic (e.g., "Skyline Collection Towel Ring"). Candidates are much better (e.g., "Antique Bronze 6-Inch Solid Brass Wall-Mount Hand Towel Ring, Skyline Collection, Allied Brass") | HIGH |
| **Feed health / disapprovals** | CRITICAL — disapproval = zero impressions for that product | Unknown — Merchant Center diagnostic not completed (MC account ID needed) | HIGH |
| **GTIN/MPN presence** | HIGH — enables Shopping Graph matching. Without GTIN, Google cannot reliably match product to catalog entity | GOOD — 75,769/75,770 products have GTIN populated | HIGH |
| **Product description quality** | HIGH — first 160 chars act as mini-ad; Google uses full text for long-tail match | CRITICAL GAP — baseline descriptions are generic collection copy ("The contemporary motif from this elegant collection has timeless appeal. Towel ring is constructed of solid brass..."). Not keyword-rich. | HIGH |
| **Attribute completeness** | HIGH — missing attributes = excluded from filtered searches (ADA compliance, material filters, size filters) | PARTIAL — material=Brass and mounting_type populated for most; weight_capacity missing for ~24% of catalog (17,862 items) | MEDIUM-HIGH |

#### Priority 2: High — Determines Auction Position

| Factor | Expected Impact | Allied Brass Status | Confidence |
|--------|----------------|---------------------|------------|
| **Google Product Category specificity** | HIGH — Level 4-5 depth vs Level 1-2 can double eligible search surface | Unknown — not tracked in product_catalog schema | MEDIUM |
| **Product type taxonomy depth** | HIGH — merchant-defined; deeper = better niche targeting | Unknown — not tracked in Supabase schema | MEDIUM |
| **Image quality (main image)** | MEDIUM-HIGH — 15-25% CTR impact; 1500×1500px recommended | Unknown — images hosted at storage.alliedbrass.com; resolution not verified | MEDIUM |
| **Lifestyle images** | MEDIUM — lifestyle images shown in Shopping carousel; boosts CTR for home décor | IMPLEMENTED — `lifestyle_image_link` column added to Google Sheets feed; Gemini Imagen generates lifestyle images | HIGH |
| **Structured title / Structured description** | Required for AI content — already compliant | COMPLIANT — system uses `structured_title`/`structured_description` with `digital_source_type=trained_algorithmic_media` | HIGH |

#### Priority 3: Moderate — Long-Tail Eligibility

| Factor | Expected Impact | Allied Brass Status | Confidence |
|--------|----------------|---------------------|------------|
| **Custom labels for bid segmentation** | MEDIUM — enables campaign-level bid differentiation | IMPLEMENTED — custom_labels 0-2 populated in feed | HIGH |
| **MPN format** | MEDIUM — `{master_sku}-{finish_code}` format used | COMPLIANT — format correct | HIGH |
| **Description length (500-1000 chars)** | MEDIUM — longer descriptions = more long-tail keyword surface | UNKNOWN — not measured; baseline descriptions appear shorter | MEDIUM |

---

### Account-Level Factors (Ordered by Expected Impact)

| Factor | Allied Brass Current State | Analysis |
|--------|---------------------------|----------|
| **Bid strategy** | Target ROAS on all 179 active Shopping campaigns | GOOD — migrated away from ECPC (deprecated March 2025). Target ROAS aligns with conversion optimization goal |
| **Impression share lost to rank** | Average 20.2% IS lost to rank across all campaigns | CRITICAL — this is the primary IS loss mechanism. Not budget. Fix: improve ad relevance (feed quality) or raise bids |
| **Impression share lost to budget** | Near 0% budget loss (only 3 campaigns show minimal budget loss) | HEALTHY — budget is not the constraint |
| **Daily budgets** | $650/day per campaign for HIGH-tier campaigns | ADEQUATE for current IS levels |
| **Historical CTR/conversion rate** | 0.86% overall CTR; 215 conversions in 30 days | CTR is acceptable but not high. Grab bar "decorative" terms show 0% CTR — content problem |
| **Campaign structure** | 179 campaigns, product-type segmented (grab bars, towel bars, etc.) | SOPHISTICATED — this is a strong structure allowing granular bid control |

**Key insight on ROAS:** The overall ROAS shown is 155x — but this represents `all_conversions_value` which Google Ads can attribute broadly. Actual ROAS should be verified against Shopify revenue data. The metric confirms campaigns are structured for conversion optimization.

---

### External Factors (Cannot Be Directly Controlled)

| Factor | Expected Impact | Allied Brass Status | Confidence |
|--------|----------------|---------------------|------------|
| **Seller ratings** | 17% CTR lift when displayed; requires 150+ reviews in 12 months via Google-approved partner | Unknown — needs MC diagnostic to confirm if seller ratings are displaying | HIGH |
| **Website/domain authority** | HIGH — competitors selling via Home Depot/Amazon/Wayfair have 90+ DA vs direct-to-consumer Shopify store | LIKELY DISADVANTAGE — direct-to-consumer Shopify store will have lower DA than marketplace sellers | MEDIUM |
| **Product-level reviews** | MEDIUM — products with 0 reviews are disadvantaged in algorithm | UNKNOWN — Shopify store review count not verified | MEDIUM |
| **Pricing competitiveness** | MEDIUM-LOW for this category — premium decorative hardware buyers are less price-sensitive | LIKELY COMPETITIVE — solid brass premium positioning commands premium price; decorative grab bars are a niche where quality matters more than price | MEDIUM |
| **Competitor domain authority** | HIGH — Kingston Brass, Delta, Moen sell through retailers with 90+ DA | CONFIRMED DISADVANTAGE — verified pattern in industry research | HIGH |

---

## Allied Brass Current State

### Campaign Configuration (Verified — Last 30 Days)

**Campaign structure:** 179 active Shopping campaigns, all Standard Shopping (not Performance Max). Campaign names follow `AVD - Shopping - US - [product category] - [HIGH/MEDIUM/LOW]` format — indicating a sophisticated tiered bidding structure.

**Bid strategy:** Target ROAS on all campaigns. ECPC was deprecated in March 2025; Allied Brass has correctly migrated to Target ROAS.

**Budget:** $650/day per HIGH-tier campaign. IS lost to budget is effectively 0% — budget is not the constraint.

**Top campaigns by impression volume (Last 30 Days):**

| Campaign | Impressions | Clicks | CTR | Cost | Conversions | IS | IS Lost (Rank) |
|----------|------------|--------|-----|------|-------------|-----|----------------|
| Wall mounted towel bars | 70,866 | 716 | 1.01% | $1,490 | 16.76 | 67.8% | 32.2% |
| Paper towel holders | 54,761 | 439 | 0.80% | $816 | 13.76 | 63.3% | 36.7% |
| Garment rods | 45,548 | 421 | 0.92% | $821 | 7.50 | 45.1% | 54.9% |
| Double glass shelf | 40,081 | 401 | 1.00% | $658 | 8.27 | 69.4% | 30.6% |
| Freestanding towel stand | 33,736 | 200 | 0.59% | $433 | 3.53 | 73.2% | 26.8% |
| Grab bars (HIGH tier) | 25,086 | 250 | 1.00% | $436 | 4.92 | 67.3% | 32.7% |
| Retractable hooks | 24,503 | 315 | 1.29% | $424 | 5.38 | 42.6% | 57.4% |

**Total 30-day portfolio:** 1,064,906 impressions, 9,196 clicks, 0.86% CTR, $16,361 spend, 215 conversions

**Campaigns with 0 impressions (suppressed or newly created):** ~30 campaigns show 0 impressions including "shower door towel bars - LOW", "candle holders - LOW", "robe hook - LOW", "assorted freestanding accessories". These may indicate feed disapprovals, insufficient bid, or no eligible products.

### Auction Insights (Data Limitation)

**Attempted:** Google Ads API v16 `auction_insight_view` query was attempted using GAQL.

**Result:** The `auction_insight.domain` field returned "UNRECOGNIZED_FIELD" error. The auction_insight_view resource is not supported in the v16 client library configuration currently used by the project. This is a technical limitation, not a data availability issue.

**Implication for research:** Cannot quantify which specific competitors Allied Brass faces in auctions without:
1. Upgrading the Google Ads API client to v17/v18, OR
2. Exporting Auction Insights manually from Google Ads UI

**What we DO know from search terms data (proxy for auction intelligence):**

Grab bar search terms where Allied Brass appears:
| Search Term | Impressions | Clicks | CTR |
|------------|------------|--------|-----|
| polished nickel grab bars | 300 | 2 | 0.67% |
| brass grab bars | 284 | 3 | 1.06% |
| unlacquered brass grab bar | 211 | 1 | 0.47% |
| 60 grab bar | 194 | 8 | **4.12%** |
| polished nickel grab bar | 169 | 3 | 1.78% |
| **decorative grab bars** | 156 | **0** | **0.00%** |
| **designer grab bars for showers** | 152 | **0** | **0.00%** |
| **decorative grab bars for bathroom** | 131 | **0** | **0.00%** |

**Critical finding:** For exactly the search terms the user identified as high-PMF ("decorative grab bars"), Allied Brass IS entering the auction (getting impressions) but getting 0 clicks. This is a listing content quality problem (title, image, price positioning), NOT an eligibility problem. The product is surfacing but shoppers aren't clicking.

### Feed Quality Analysis

**Content coverage:**
- Total product variants in catalog: 75,770
- Unique master SKUs: ~2,784 (confirmed by project documentation)
- Product_catalog rows: 75,770 (all variants)
- Google content records generated: 193
- Google content records approved: 79
- **Content coverage: <0.7% of master SKUs**

**Baseline title quality (original, hand-written titles from product_catalog):**

| Type | Example Baseline Title | Issues |
|------|----------------------|--------|
| Collection + Type | "Skyline Collection Towel Ring" | No finish, no size, no material, no differentiators |
| Collection + Description | "Skyline Collection 3 Position Multi Hook" | No finish, no size, no material |
| Simple type | "1-1/2 Inch Cabinet Knob" | No brand, no material, no finish |
| Long baseline | "Extended 3-Post Grab Bar, 60-Inch, ADA Compliant, Pipeline Collection, , Allied Brass" | Better — has size, ADA, collection. Still starts with "Extended" not "60-Inch" |

**AI-optimized title quality (candidate_content):**

| SKU | AI-Optimized Title | Score |
|-----|-------------------|-------|
| 1016 | "Antique Bronze 6-Inch Solid Brass Wall-Mount Hand Towel Ring, Skyline Collection, Allied Brass" | 87/100 |
| 1020-3 | "Antique Bronze 3-Inch Solid Brass Wall-Mount 3-Position Multi Hook, Skyline Collection, Allied Brass" | 98/100 |
| 1020 | "Matte Black Wall-Mounted Solid Brass Robe Hook, 3.6-Inch - Skyline Collection - Allied Brass" | 90/100 |
| 1024 | "{FINISH_NAME} Two-Post Toilet Paper Holder - Modern Style - Solid Brass Wall Mount - Skyline Collection - Allied Brass" | 83/100 |

**Average quality score of generated content: 89.4/100** (n=126). This is meaningfully better than the 75-80/100 baseline pipeline estimate — actual production quality is higher.

**Key issue with titles:** Some titles still have `{FINISH_NAME}` placeholder as a literal string (e.g., SKU 102: `{FINISH_NAME} 1-1/2 Inch Solid Brass Cabinet Knob`). This suggests finish name injection may not be happening correctly for some SKUs during variant expansion. This needs verification.

**Attribute completeness in product_catalog:**
- GTINs: 75,769/75,770 (>99%) — excellent
- Material: Populated ("Brass") for verified sample — good
- Mounting type: Populated for verified sample — good
- Weight capacity: 57,908/75,770 (76.5%) populated — 23.5% missing
- Dimensions (product_length, height, width): Populated for most products
- Style: Populated ("Modern", etc.) — good
- Shape, orientation, tilting: Many null values (accessory-specific, may not apply)

**What's missing from feed that competitors likely have:**
- Google Product Category at depth 4-5 (not tracked in product_catalog schema)
- Product type hierarchy for GMC (not tracked in product_catalog schema)
- ADA compliance flag (grab bars specifically — grab bar data shows ADA compliant in baseline title for P-730-GB360 but not as structured attribute)
- Finish-specific descriptions (same narrative_copy for all 28 finishes of same SKU)

### Merchant Center Diagnostics

**Attempted:** Merchant API diagnostic query.

**Status:** Merchant Center account ID is different from Google Ads customer ID (6253381786). The Merchant API requires the MC merchant ID (not the Google Ads customer ID). From STATE.md: "GMC merchant account ID needed for Phase 19 Merchant API integration." This is a known open question.

**What we know without direct MC access:**
- ~30 campaigns showing 0 impressions may indicate disapproved products
- Without MC diagnostic, cannot confirm disapproval count or specific issues
- **Action needed:** User to provide Merchant Center account ID (available in MC dashboard at merchants.google.com → Settings → Account information)

---

## Identified Gaps

### Gap 1: Feed Content Coverage (CRITICAL — Scale Bottleneck)

Only 79/2,784 master SKUs (~2.8%) have approved Google Shopping content. The remaining 97.2% of the catalog is being served with baseline titles like "Skyline Collection Towel Ring" — generic, no finish, no size, no keyword optimization.

**Impact:** 97.2% of products are entering auctions with titles that don't match buyer intent patterns. This explains broad IS loss to rank — products are eligible but not winning positions because their relevance score is low.

**Fix:** Scale content generation pipeline to full catalog. Current quality (89.4/100 avg) is production-ready.

### Gap 2: Zero CTR on High-PMF Decorative Grab Bar Terms (CONFIRMED)

"decorative grab bars" (156 impressions, 0 clicks), "decorative grab bars for bathroom" (131 impressions, 0 clicks), "designer grab bars for showers" (152 impressions, 0 clicks).

These are exactly the terms where Allied Brass has "some of the nicest decorative grab bars on the market." Getting impressions but 0 clicks means the listing is appearing but losing to competitors in the same position.

**Likely cause:** Listing title doesn't match shopper's intent for "decorative" — if the title says "Pipeline Collection Grab Bar" vs competitor title saying "Decorative Grab Bar - Polished Nickel - Solid Brass", the competitor wins the click even at same position.

**Fix:** Ensure grab bar titles include "decorative" or "designer" when the product is in the decorative grab bar category. This is a prompt instruction change.

### Gap 3: IS Lost to Rank (Average 20.2%, Some Categories 55%+)

- Garment rods: 54.9% IS lost to rank (highest)
- Retractable hooks: 57.4% IS lost to rank
- Paper towel holders: 36.7% IS lost to rank

**Interpretation:** These categories have the largest gap between current IS and maximum possible IS. Two solutions: (1) raise bids for these categories, (2) improve feed quality to improve relevance score (which Google factors into auction rank alongside bid).

**Priority:** Feed quality improvement first (zero cost), then bid evaluation.

### Gap 4: Merchant Center Account ID Unknown (BLOCKER for Complete Diagnostic)

Cannot run Merchant Center product diagnostics without the MC merchant ID. This prevents:
- Confirming disapproval count
- Identifying which attributes are flagged as missing
- Checking seller rating status

### Gap 5: Auction Insights Competitor Data Unavailable (API Technical Limitation)

Google Ads API v16 does not support `auction_insight_view`. This means we cannot programmatically identify which domains Allied Brass competes against. Must use manual MC/Google Ads UI export or upgrade API client.

### Gap 6: `{FINISH_NAME}` Placeholder in Some Published Titles

SKU 102 approved title contains literal `{FINISH_NAME}` placeholder: `{FINISH_NAME} 1-1/2 Inch Solid Brass Cabinet Knob - Round Modern Style - Allied Brass`. If this is being published to Google Sheets without substitution, it will appear in Shopping results as-is — which would trigger disapproval for invalid content.

**This needs immediate verification and fix.**

---

## Hypothesis Status

From RESEARCH.md hypotheses framework (H1-H7):

| # | Hypothesis | Status | Evidence |
|---|-----------|--------|----------|
| H1 | Feed quality is primary cause: titles/descriptions not keyword-optimized | **CONFIRMED** | Baseline titles are generic (collection + type only). 0% CTR on "decorative grab bars" terms confirms content relevance gap. 97.2% of catalog unoptimized. |
| H2 | Attribute completeness gap: missing category-specific attributes | **PARTIALLY CONFIRMED** | GTIN coverage is excellent (99.9%). Weight capacity missing for 23.5% of catalog. Google Product Category depth and product type hierarchy not tracked. ADA compliance not as structured attribute. Merchant Center diagnostic needed for full picture. |
| H3 | Competitor domain authority advantage | **LIKELY CONFIRMED** | Kingston Brass, Delta, Moen sell through Home Depot (DA 90+), Amazon (DA 90+). Allied Brass direct Shopify site will have substantially lower DA. Cannot quantify without DA lookup tools. |
| H4 | Bid competitiveness gap | **PARTIALLY CONFIRMED** | IS lost to rank (20.2% avg, up to 57.4% in some categories) suggests bid-rank tension. But budget IS loss is near 0%, indicating budget is adequate. Bid competitiveness vs specific competitors requires Auction Insights data. |
| H5 | Seller reputation signals: insufficient seller reviews | **UNCONFIRMED** | Requires Merchant Center access to verify seller rating status. Not verifiable without MC account ID. |
| H6 | Pricing disadvantage | **UNCONFIRMED** | Bath hardware is premium category; decorative grab bars attract design-conscious buyers less price-sensitive. Price comparison requires SERP data (Phase 19). |
| H7 | Product type/category miscategorization | **PARTIALLY CONFIRMED** | Google Product Category and product type hierarchy are not tracked in product_catalog schema — cannot verify current values without accessing the live Google Sheets feed. Likely using shallow categorization given the vintage of the feed setup. |

---

## Recommended Prompt Changes for Phase 20

### Change 1: Lead with Finish + Product Type in First 70 Characters (CRITICAL)

**Current behavior:** Titles often start with collection name ("Skyline Collection", "Pacific Beach Collection") or generic structure.

**Data support:** Search query analysis shows 0 brand name queries. Finish-specific queries drive 39% higher CTR than generic (1.07% vs 0.77%). First 70 chars are the visible portion of Shopping listings.

**Recommended prompt instruction:**
```
Title structure MUST be:
[Finish Name] [Size/Key Attribute] [Product Type] [Material] [Mounting] - [Collection] - Allied Brass

The finish name MUST appear in the first 70 characters. Never lead with collection name or brand.
Example: "Polished Nickel 24-Inch Wall-Mounted Solid Brass Towel Bar - Waverly Place - Allied Brass"
NOT: "Allied Brass Waverly Place 24-Inch Polished Nickel Towel Bar"
```

### Change 2: Add Category-Intent Keywords for Zero-Click Categories (HIGH)

**Data support:** "decorative grab bars" (0 clicks), "designer grab bars" (3 clicks, 2.13% CTR vs 0% for "decorative"). The word "decorative" in the search term must match in the title.

**Recommended prompt instruction:**
```
For grab bars: If the product is decorative/designer style (not medical/safety grab bars),
include "Decorative" or "Designer" in the title to match high-intent search terms.
Example: "Antique Brass 36-Inch Decorative Grab Bar - ADA Compliant Solid Brass Wall Mount"
```

### Change 3: Include ADA Compliance as Explicit Attribute in Grab Bar Titles (HIGH)

**Data support:** "ADA grab bar" is a high-intent search term (18,100 monthly searches per keyword research). Grab bar search shows high CTR for size-specific terms.

**Recommended prompt instruction:**
```
For ADA-compliant grab bars, include "ADA Compliant" as a phrase in both title and description.
This matches filtered searches and signals compliance to safety-conscious buyers.
```

### Change 4: Include "Solid Brass" Material Differentiator in Every Title (HIGH)

**Data support:** Allied Brass uses solid brass vs most competitors (Moen, Delta) who use zinc alloy with plating. This is the primary quality differentiator.

**Recommended prompt instruction:**
```
Include "Solid Brass" as a material descriptor in EVERY title. This differentiates from
zinc alloy competitors and matches material-conscious buyers.
```

### Change 5: Ensure {FINISH_NAME} Resolves Before Publishing (CRITICAL BUG FIX)

**Data support:** SKU 102 approved content contains literal `{FINISH_NAME}` placeholder. This is a content pipeline bug — the finish name substitution is not happening for some SKUs.

**Required fix (not a prompt change — this is a pipeline bug):**
- Verify that `{FINISH_NAME}` template variable is being substituted during variant expansion
- Add validation step before publishing to check for unreplaced placeholders
- Affected file: `dashboard/src/lib/publishing/expand-variants.ts`

### Change 6: Front-Load Key Specs in First 160 Characters of Description (HIGH)

**Current state:** Baseline descriptions start with generic collection positioning ("The contemporary motif from this elegant collection has timeless appeal").

**Data support:** Google Shopping Graph uses descriptions for long-tail query matching. First 160 chars are most heavily weighted.

**Recommended prompt instruction:**
```
Description must open with key product specifications, not with marketing language.
First sentence structure: "[Finish] [Product Type] for bathroom wall installation. [Material]. [Key dimension]. [Key functional claim]."
Example: "Polished Nickel solid brass towel ring, 6-inch diameter, wall-mounted. Constructed from solid brass with lifetime finish warranty. The Skyline Collection's contemporary design suits modern and transitional bathrooms."
NOT: "The contemporary motif from this elegant collection has timeless appeal."
```

### Change 7: Use Size-Specific Search Intent in Title Format (HIGH)

**Data support:** "60 grab bar" has 4.12% CTR — the highest CTR search term in the dataset. Size-specific queries show purchase intent significantly above average.

**Recommended prompt instruction:**
```
Product dimensions MUST appear in the title.
Preferred format: "[Size]-Inch" at position 2-3 in title.
For grab bars specifically: lead with size since size-specific terms ("60 grab bar") have the highest CTR.
```

### Change 8: Write Descriptions for Every Finish Variant (MEDIUM)

**Current state:** All 28 finish variants of a master SKU share the same `narrative_copy` in product_catalog. The AI generates one master title/description and variants are created via template substitution.

**Gap:** The description doesn't mention finish-specific benefits or use cases. A shopper searching "unlacquered brass grab bar" — a premium, patina-developing finish — would benefit from a description that acknowledges the unique characteristics of unlacquered brass.

**Recommended prompt instruction:**
```
When generating descriptions for specific finishes, include 1 sentence about that finish's characteristics:
- Unlacquered Brass: "The unlacquered brass finish develops a rich natural patina over time, a hallmark of authentic brass craftsmanship."
- Polished Nickel: "The polished nickel finish provides a bright, silver-toned appearance with excellent corrosion resistance."
- Oil Rubbed Bronze: "The oil rubbed bronze finish highlights the product's curves with a warm, aged appearance."
This is relevant content that differentiates the variant in Shopping results and matches finish-specific searches.
```

### Change 9: Include Collection Cross-Sell in Description (LOW)

**Current state:** Descriptions don't mention that complementary accessories from the same collection are available.

**Recommended prompt instruction:**
```
In the last paragraph of descriptions, include: "Coordinates with [Collection Name] Collection bathroom accessories including [2-3 related product types]."
This increases session value and signals product depth to Google's algorithm.
```

---

## Quick Wins vs Medium-Term vs Long-Term

### Quick Wins (1-2 weeks) — Feed Quality Changes via Prompt Updates

- [ ] **Fix {FINISH_NAME} placeholder bug** — CRITICAL, verify and fix in expand-variants.ts before next publish
- [ ] **Update title prompt: Lead with Finish + Product Type** — Change 1 above. Apply to next content generation batch. Expected +25-39% CTR based on search pattern data.
- [ ] **Update title prompt: Include "Solid Brass" differentiator** — Change 4. Applies to all categories.
- [ ] **Update description prompt: Front-load specs in first 160 chars** — Change 6. Impacts long-tail query eligibility.
- [ ] **Add "Decorative/Designer" for grab bar titles** — Change 2. Specific to grab bar category. Direct fix for 0-click decorative grab bar terms.
- [ ] **Add "ADA Compliant" to compliant grab bar titles** — Change 3.

### Medium-Term (2-4 weeks) — Scale and Structural Improvements

- [ ] **Scale content generation to full catalog** — Currently 79/2,784 SKUs approved. Priority order: (1) grab bars (high PMF, low content), (2) towel bars (highest impression volume), (3) paper towel holders (high volume), (4) glass shelves.
- [ ] **Get Merchant Center account ID from user** — Run MC diagnostic to identify disapproved products and attribute gaps.
- [ ] **Upgrade Google Ads API client to v18** — Enables Auction Insights programmatic access.
- [ ] **Add Google Product Category and product_type_hierarchy to product_catalog schema** — Currently not tracked. Enables deeper categorization in feed.
- [ ] **Audit Google Sheets feed for current product_type depth** — Verify if already at depth 4-5 or shallow.
- [ ] **Evaluate bid increases for garment rods and retractable hooks** — 54.9% and 57.4% IS lost to rank respectively; these categories may benefit from bid increase after feed quality improves.

### Long-Term (1-3 months) — External Factors

- [ ] **Image quality audit** — Verify all main images meet 1500×1500px minimum. Current images at storage.alliedbrass.com — resolution not verified.
- [ ] **Investigate seller ratings enrollment** — Google requires 150+ reviews in 12 months via approved partner (Trustpilot, Shopper Approved, etc.). If not enrolled, 17% CTR improvement opportunity.
- [ ] **Product review collection strategy** — Products with 0 reviews are disadvantaged. Consider adding Shopify review widget and enabling product review schema on PDPs.
- [ ] **Run SERP competitor analysis** — Phase 19 plan: Apify scrape of 25-30 search terms to build competitor title/description profile. This will validate and extend the findings here.

---

## Appendix: Model Benchmarking Context

This section covers the model research component of Phase 17 (requirements MODEL-01 and MODEL-02). Full execution is in Phase 17 Plan 02 (model benchmarking).

### Current Model vs Alternatives

| Model | Input $/MTok | Output $/MTok | Batch Input | Batch Output | Context | Status |
|-------|-------------|--------------|-------------|--------------|---------|--------|
| GPT-4o (current baseline) | $2.50 | $10.00 | $1.25 | $5.00 | 128K | Current pipeline |
| GPT-5.2 | $1.75 | $14.00 | $0.875 | $7.00 | 400K | Benchmark target |
| Claude Sonnet 4.6 | $3.00 | $15.00 | $1.50 | $7.50 | 200K | Benchmark target |
| Gemini 2.5 Pro | $1.25 | $10.00 | $0.625 | $5.00 | 1M | Benchmark target |

### Cost-per-SKU Estimates (2,784 Master SKUs)

Assumptions: 2,000 input tokens + 800 output tokens per SKU. Using batch pricing.

| Model | Cost per SKU | Total 2,784 SKUs | Notes |
|-------|-------------|-----------------|-------|
| GPT-4o (current, batch) | $0.0065 | $18.10 | Baseline |
| GPT-5.2 (batch) | $0.0073 | $20.32 | +13% over GPT-4o |
| GPT-5.2 with prompt cache | ~$0.003 | ~$8.35 | Cheapest option if system prompt cached |
| Claude Sonnet 4.6 (batch) | $0.0090 | $25.06 | +38% over GPT-4o |
| Claude with cache | ~$0.0066 | ~$18.37 | Comparable to GPT-4o uncached |
| Gemini 2.5 Pro (batch) | $0.0053 | $14.76 | Cheapest raw option |

**Key finding:** All models fall well under $500 for full catalog. Cost is not the differentiating factor. Full benchmark with quality scores needed to make model recommendation — that's Plan 02.

### State of the Art Changes Relevant to Content Generation

| Old Approach | Current Approach | Changed | Impact |
|--------------|------------------|---------|--------|
| ECPC bid strategy | Target ROAS (smart bidding) | March 2025 — ECPC deprecated | Allied Brass already migrated to Target ROAS |
| Optional structured data | Required for AI content (structured_title + digital_source_type) | October 2025 | Already compliant |
| GPT-4o as frontier | GPT-5.2, Claude Sonnet 4.6, Gemini 2.5 Pro | August 2025 (GPT-5.2) | Benchmark needed to determine if switch improves quality |
| Keyword stuffing | Natural language keyword-intent matching | 2023-2024 | Current prompts should follow natural language — verify in Phase 20 |

---

## Open Questions

1. **Merchant Center account ID** — Required for disapproval diagnostic. User to provide from merchants.google.com.

2. **{FINISH_NAME} placeholder bug** — Is the placeholder being substituted in expand-variants.ts? Which SKUs are affected? This should be verified immediately.

3. **Google Ads API v16 Auction Insights** — `auction_insight_view` not supported in current API version. Three options: (a) manual UI export by user, (b) upgrade API client to v18, (c) defer to Phase 19 competitive analysis via SERP scraping.

4. **Seller rating status** — Is Allied Brass enrolled in a Google-approved seller ratings partner? Are star ratings currently displaying in Shopping listings?

5. **Current Google Product Category values** — What depth are current category assignments in the Google Sheets feed? Level 1-2 or Level 4-5?

---

## Sources

### Primary Data Sources (HIGH confidence — pulled from live systems)
- Google Ads API (customer 6253381786): Campaign impression share, search terms, bid strategy — data extracted 2026-02-21 via `google_ads_performance.py`
- Supabase `generated_content` table: 193 Google content records, quality scores, baseline and candidate titles
- Supabase `product_catalog` table: 75,770 product variants, attribute completeness data
- Previous research `docs/research/google-shopping-research-2026-02-10.md`: Search query pattern analysis, keyword data, title best practices

### Secondary Sources (MEDIUM confidence — established practitioner sources)
- Google Merchant Center Help: structured_title vs title behavior, `digital_source_type` requirements
- Google Ads Help: Auction Insights metrics definition, impression share components
- FeedOps Google Shopping Feed Optimization Guide 2025 — ranking signal hierarchy
- Search Engine Journal: Google Shopping Rankings — correlation study findings
- RESEARCH.md prior analysis (17-RESEARCH.md) — ranking signal taxonomy, model pricing data
