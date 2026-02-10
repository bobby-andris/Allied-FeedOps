# Google Shopping Research: Bathroom Hardware Optimization

**Date**: 2026-02-10
**Author**: ads-researcher agent
**Context**: Allied Brass sells bathroom hardware (towel bars, soap dishes, grab bars, glass shelves, robe hooks). Only 1 published SKU (FT-16, glass shelf). This is proactive research to validate methodology BEFORE scaling.

---

## 1. Google Shopping Title Best Practices

### Title Structure Formula for Hardware

The recommended structure for home/hardware products is:

```
Brand + Product Type + Material + Finish + Key Attribute (size/mounting) + Collection
```

**Example for Allied Brass**:
```
Allied Brass Waverly Place 16-Inch Glass Shelf with Towel Bar - Polished Nickel
```

### Key Rules (Data-Backed)

1. **Use all 150 characters** - The non-visible portion still influences Google's matching algorithm. Google shows ~70 characters in most placements, but the full 150 characters affect which queries trigger the ad.

2. **Front-load the most important keywords** - The first 70 characters are visible in most Shopping placements. Put product type + finish first since those are what customers search for most (see Section 4).

3. **Include finish in the title** - Our data shows finish-specific searches have the HIGHEST CTR (1.07%) vs generic product (0.77%), mounting-specific (0.76%), and room-specific (0.62%). This is a 39% CTR advantage.

4. **Include dimensions** - Searches like "60 grab bar" have the highest CTR (4.15%) in our data. Size-specific searches show high purchase intent.

5. **Avoid promotional text** - No "free shipping", "best seller", "sale", etc. Google will disapprove these.

6. **Natural capitalization** - Title case or sentence case. No ALL CAPS or gimmicky characters.

7. **Match landing page** - Title must accurately reflect the product on the landing page.

### Title Structure by Product Category

| Category | Recommended Formula | Example |
|----------|-------------------|---------|
| Towel Bars | Brand + Product + Size + Material + Finish | Allied Brass 24-Inch Solid Brass Wall Mount Towel Bar - Unlacquered Brass |
| Glass Shelves | Brand + Product + Size + Material + Finish + Feature | Allied Brass 16-Inch Tempered Glass Bathroom Shelf with Towel Bar - Polished Nickel |
| Grab Bars | Brand + Product + Size + Material + Finish + ADA | Allied Brass 36-Inch Solid Brass Grab Bar - Oil Rubbed Bronze |
| Soap Dishes | Brand + Product + Mounting + Material + Finish | Allied Brass Wall Mounted Solid Brass Soap Dish - Satin Chrome |
| Robe Hooks | Brand + Product + Mounting + Material + Finish + Collection | Allied Brass Prestige Skyline Double Robe Hook - Antique Pewter |

### Three-Tier Optimization Model

1. **Compliant** (baseline): Product name only, minimal attributes. Low performance.
2. **Optimized**: Structured formula with all key attributes. Strong performance.
3. **AI-Optimized**: Natural language with long-tail keyword variations and contextual language. Best performance (33% increase in non-branded visibility per FeedOps case study, 139% increase in organic Shopping revenue).

---

## 2. GMC Structured Data Guidelines for AI Content

### structured_title vs standard title

| Attribute | Use When | Max Length | Schema.org |
|-----------|----------|------------|------------|
| `title` [title] | Human-written titles | 150 chars | Yes |
| `structured_title` [structured_title] | AI/algorithmically generated titles | 150 chars | No |

**Rule**: Use ONE of `title` or `structured_title`, not both. For AI-generated content, use `structured_title`.

### structured_description vs standard description

| Attribute | Use When | Max Length | Schema.org |
|-----------|----------|------------|------------|
| `description` [description] | Human-written descriptions | 5,000 chars | Yes |
| `structured_description` [structured_description] | AI/algorithmically generated descriptions | 5,000 chars | No |

### digital_source_type Values

| Value | Meaning |
|-------|---------|
| `trained_algorithmic_media` | Content created using generative AI (models trained on sampled content) |
| `default` | Content NOT created using generative AI |
| (omitted) | Defaults to `default` |

### Format in Google Sheets Feed

```
trained_algorithmic_media:"Your AI-generated title text here"
```

### AI Content Guidelines Summary

1. **Always declare AI content** - Use `digital_source_type: trained_algorithmic_media` for any AI-generated titles/descriptions
2. **Images too** - AI-generated images must contain IPTC `DigitalSourceType` metadata tag `TrainedAlgorithmicMedia`
3. **Match landing page** - AI-generated content must still accurately describe the product and match the landing page
4. **No fabricated claims** - Never invent specs, materials, or features not present in the actual product data
5. **Google Product Studio** - Google's own tool uses the same `trained_algorithmic_media` tag

### Current Allied Brass Implementation

Our system correctly uses `structured_title` and `structured_description` with `digital_source_type=trained_algorithmic_media` in the Google Sheets supplemental feed (columns M and N). This is compliant with GMC requirements.

---

## 3. Search Query Pattern Analysis

### What Our Customers Actually Search For

Analysis of 714 unique search queries from our Google Ads data reveals clear patterns:

#### Search Pattern Distribution

| Pattern | Unique Queries | Impressions | Clicks | CTR |
|---------|---------------|-------------|--------|-----|
| **Finish-specific** (e.g., "polished nickel towel bar") | 276 | 182,924 | 1,954 | **1.07%** |
| **Generic product** (e.g., "towel bar", "paper towel holder") | 230 | 155,974 | 1,195 | 0.77% |
| **Mounting-specific** (e.g., "wall mounted soap dish") | 103 | 91,583 | 699 | 0.76% |
| **Room-specific** (e.g., "bathroom shelf", "shower squeegee") | 105 | 89,639 | 557 | 0.62% |

**Key Insight**: Finish-specific searches drive 39% higher CTR than generic searches. Customers who know what finish they want are more likely to click and convert.

#### Top Product Categories by Search Volume

| Category | Unique Queries | Impressions | Clicks | CTR |
|----------|---------------|-------------|--------|-----|
| Paper towel holders | 91 | 95,198 | 971 | 1.02% |
| Toilet paper holders | 82 | 81,052 | 712 | 0.88% |
| Towel bars/racks | 129 | 76,697 | 648 | 0.84% |
| Valet rods | 32 | 48,392 | 371 | 0.77% |
| Squeegees | 24 | 26,421 | 129 | 0.49% |
| Mirrors | 41 | 22,816 | 148 | 0.65% |
| Towel rings | 19 | 19,952 | 172 | 0.86% |
| Shower rods | 22 | 19,232 | 168 | 0.87% |
| Shelves | 28 | 15,341 | 83 | 0.54% |
| Soap dishes | 13 | 7,426 | 93 | **1.25%** |
| Grab bars | 20 | 6,178 | 71 | **1.15%** |
| Hooks | 20 | 9,750 | 92 | 0.94% |

**Key Insights**:
- **Soap dishes and grab bars have the highest CTR** despite lower volume - high purchase intent
- **Paper towel holders dominate volume** - our most visible category
- **Valet rods are a strong niche** - 48K impressions from only 32 unique queries (highly concentrated)

#### Top Performing Queries by CTR (min 500 impressions)

| Query | Impressions | Clicks | CTR |
|-------|-------------|--------|-----|
| 60 grab bar | 675 | 28 | 4.15% |
| countertop toilet paper holder | 719 | 27 | 3.76% |
| polished nickel valet rod | 673 | 22 | 3.27% |
| unlacquered brass paper towel holder | 2,227 | 68 | 3.05% |
| unlacquered brass appliance pull | 881 | 26 | 2.95% |
| polished nickel hand towel stand | 1,064 | 29 | 2.73% |
| polished nickel towel rack | 1,711 | 46 | 2.69% |
| polished nickel shower rod | 1,897 | 48 | 2.53% |

**Key Pattern**: The highest-CTR queries combine **finish + product type** or **size + product type**. This validates including both in titles.

#### Brand Awareness: ZERO

Zero search queries contained "Allied Brass" or any competitor brand name. This market is **entirely feature/attribute-driven, not brand-driven**. Customers search by:
1. Finish (unlacquered brass, polished nickel, etc.)
2. Product type (towel bar, paper towel holder, etc.)
3. Mounting style (wall mounted, freestanding, recessed)
4. Size (24 inch, 60 inch, etc.)

**Implication**: Brand name should NOT be the first word in titles. Product type + finish should lead.

---

## 4. Keyword Opportunities

### High-Volume Keywords (from Google Ads Keyword Planner)

| Keyword | Monthly Searches | Competition | CPC Range |
|---------|-----------------|-------------|-----------|
| toilet paper holder | 60,500 | HIGH | $0.30-$1.65 |
| paper towel holder | 40,500 | HIGH | $0.24-$1.13 |
| shower curtain rod | 40,500 | HIGH | $0.24-$1.18 |
| bathroom shelves | 40,500 | HIGH | $0.30-$1.35 |
| toothbrush holder | 27,100 | HIGH | $0.25-$1.02 |
| towel rack | 22,200 | HIGH | $0.27-$1.27 |
| toilet paper holder wall mount | 18,100 | HIGH | $0.28-$1.41 |
| grab bars for shower | 18,100 | HIGH | $0.34-$2.98 |
| curved shower curtain rod | 14,800 | HIGH | $0.26-$1.14 |
| towel bar | 9,900 | HIGH | $0.40-$3.46 |
| glass shelves | 9,900 | HIGH | $0.45-$2.61 |
| hand towel holder | 8,100 | HIGH | $0.30-$1.29 |

### Finish-Specific Keyword Opportunities

| Keyword | Monthly Searches | Competition |
|---------|-----------------|-------------|
| brass toilet paper holder | 2,900 | HIGH |
| gold paper towel holder | 1,900 | HIGH |
| brass towel bar | 1,300 | HIGH |
| polished nickel toilet paper holder | 1,000 | HIGH |
| brass paper towel holder | 1,000 | HIGH |
| brass shower curtain rod | 1,000 | HIGH |
| oil rubbed bronze toilet paper holder | 880 | HIGH |
| gold glass shelf | 880 | HIGH |
| chrome towel bar | 880 | HIGH |
| brass towel ring | 720 | HIGH |
| polished nickel shower curtain rod | 590 | HIGH |
| polished nickel towel bar | 590 | HIGH |

**Key Insight**: Finish-specific keywords have lower search volume but MUCH higher purchase intent. Our data shows 1.07% CTR for finish-specific vs 0.77% for generic. These are the queries where Allied Brass has the strongest competitive advantage (28 finish options).

### Untapped Keyword Gaps

Based on comparing search queries vs keyword planner data:

1. **"unlacquered brass"** - High CTR (3.05%) in our data, no keyword planner match. This is a premium/niche finish that attracts design-conscious buyers.
2. **"hotel style towel rack"** - 2.14% CTR. Aspirational/lifestyle language could boost visibility.
3. **"glass shelf with towel bar"** - 4,254 impressions. Combination queries show high intent.
4. **"ADA grab bar"** - Not in our search data but massive market (grab bars: 18,100 monthly searches). Accessibility compliance is a selling point.

---

## 5. Competitor Title Analysis

### Competitor Title Patterns Observed

Based on Google Shopping results for bathroom hardware:

#### Pattern A: Brand-First (Common for Established Brands)
```
Moen 24-Inch Towel Bar, Brushed Nickel
Kohler Purist 24" Towel Bar in Vibrant Brushed Nickel
Delta Trinsic 24 in. Towel Bar in Champagne Bronze
```

#### Pattern B: Feature-First (Common for Mid-Market)
```
24-Inch Solid Brass Wall Mount Towel Bar - Polished Nickel
Brushed Nickel Bathroom Glass Shelf with Towel Bar, Stainless Steel
Wall Mounted Soap Dish Holder in Chrome Finish
```

#### Pattern C: Descriptive/Long-Tail (Marketplaces & Specialty)
```
SFGSOWOR Glass Bathroom Shelf with Towel Bar, Stainless Steel Tempered Towel bar/Track Glass Bathroom Shelves Wall Mount Over The Toilet (Brushed Nickel, 20-inch)
```

### What Top Competitors Include in Titles

| Element | Moen/Kohler/Delta | Wayfair/Amazon | Specialty (Signature HW, Allied) |
|---------|-------------------|----------------|----------------------------------|
| Brand | Always first | Varies | Sometimes |
| Product type | Always | Always | Always |
| Size | Usually | Usually | Sometimes |
| Material | Rarely | Sometimes | Often (selling point) |
| Finish | Always | Always | Always |
| Collection name | Sometimes | Never | Sometimes |
| Mounting type | Rarely | Sometimes | Sometimes |

### Key Competitive Differentiators for Allied Brass

1. **Solid brass construction** - Most mass-market competitors (Moen, Delta) use zinc alloy with plating. Allied Brass uses solid brass. This is a major quality differentiator that should be prominent.
2. **28 finish options** - Most competitors offer 3-5 finishes. This variety is a massive competitive advantage for finish-specific searches.
3. **Collection coherence** - Named collections (Waverly Place, Prestige Skyline, etc.) allow coordinated bathroom design. This appeals to design-conscious buyers.
4. **"Unlacquered brass"** - This finish is rarely available from mass-market brands. It commands high CTR (3.05%) and signals premium/heritage quality.

---

## 6. Specific Recommendations for Our Methodology

### Title Generation Recommendations

#### Priority 1: Lead with Finish + Product Type (HIGH IMPACT)

**Current risk**: If titles lead with brand name, we waste the visible 70 characters on "Allied Brass" which no one searches for (zero brand queries).

**Recommendation**: For Google Shopping titles (structured_title), lead with the most-searched attribute combination:

```
[Finish] [Product Type] [Size] - [Material] [Mounting] | Allied Brass [Collection]
```

Example:
```
Polished Nickel 24-Inch Towel Bar - Solid Brass Wall Mount | Allied Brass Waverly Place
```

This puts the highest-CTR keywords ("polished nickel towel bar") in the first 70 visible characters.

#### Priority 2: Always Include Material ("Solid Brass") (MEDIUM IMPACT)

"Solid brass" is a key differentiator vs zinc alloy competitors. Include it in every title to:
- Differentiate from cheaper alternatives in Shopping results
- Signal quality/durability to price-sensitive buyers
- Match material-specific searches

#### Priority 3: Include Size When Available (MEDIUM IMPACT)

Size-specific queries have the highest CTR in our data (4.15% for "60 grab bar"). Always include dimensions:
- Towel bars: "24-Inch" or "18-Inch"
- Shelves: "16-Inch"
- Grab bars: "36-Inch" (also mention ADA compliance if applicable)

#### Priority 4: Use Variant-Specific Titles (HIGH IMPACT at Scale)

Since we expand to 28 finish variants per SKU, each variant's structured_title should contain that specific finish name. This directly matches the finish-specific queries that drive our highest CTR.

### Description Generation Recommendations

1. **First 150-500 characters matter most** - Front-load key specs, material, finish, and primary use case
2. **Use up to 5,000 characters** - Include detailed specs, dimensions, installation method, care instructions, and collection cross-sell
3. **Include search terms naturally** - Weave in high-volume keywords: "bathroom shelf", "wall mounted", "solid brass", the specific finish name
4. **Answer common questions** - Installation type (wall mount, freestanding), weight capacity, what's included in the box
5. **Avoid promotional language** - No "best seller", "premium quality", "luxury" without substantiation

### Feed-Level Recommendations

1. **google_product_category**: Use the most specific category available (e.g., "Home & Garden > Bathroom Accessories > Towel Racks & Holders" rather than just "Home & Garden")
2. **custom_labels**: Use for segmenting Shopping campaigns by:
   - `custom_label_0`: Product category (towel_bar, glass_shelf, grab_bar)
   - `custom_label_1`: Price tier (premium, standard)
   - `custom_label_2`: Finish family (brass, nickel, chrome, bronze)
3. **MPN field**: Continue using `{master_sku}-{finish_code}` format
4. **lifestyle_image_link**: Continue populating - lifestyle images improve CTR in Shopping results

### Methodology Validation Summary

| Aspect | Current Approach | Best Practice | Status |
|--------|-----------------|---------------|--------|
| structured_title usage | Yes, with trained_algorithmic_media | Required for AI content | COMPLIANT |
| structured_description | Yes, with trained_algorithmic_media | Required for AI content | COMPLIANT |
| Title length | Needs audit | Use full 150 chars | NEEDS AUDIT |
| Keyword front-loading | Needs audit | Product type + finish first | NEEDS AUDIT |
| Material inclusion | Needs audit | Always include "solid brass" | NEEDS AUDIT |
| Size in title | Needs audit | Always include dimensions | NEEDS AUDIT |
| Finish in title | Yes (variant expansion) | Critical for CTR | COMPLIANT |
| Brand position | Needs audit | Not first (zero brand searches) | NEEDS AUDIT |
| Description depth | Needs audit | Use 500-2000 chars minimum | NEEDS AUDIT |
| Lifestyle images | Yes (Gemini Imagen) | Improves CTR | COMPLIANT |
| MPN format | Yes ({sku}-{finish_code}) | Required for identification | COMPLIANT |

### Top 3 Quick Wins

1. **Reorder title structure** to lead with finish + product type instead of brand (estimated +39% CTR based on search pattern data)
2. **Add "Solid Brass" to every title** to differentiate from zinc alloy competitors
3. **Include dimensions in every title** where available (estimated +2-4x CTR for size-specific queries)

---

## Sources

- [Google Shopping Title Optimization (FeedOps)](https://feedops.com/google-shopping-product-title-optimization/)
- [10 Rules for Google Shopping Titles (DataFeedWatch)](https://www.datafeedwatch.com/blog/improve-google-shopping-product-titles)
- [Product Title Optimization Research (Store Growers)](https://www.storegrowers.com/product-title-optimization/)
- [Google Shopping Feed Optimization 2026 (AdNabu)](https://blog.adnabu.com/google-shopping-feed/google-shopping-feed-optimization/)
- [Google Shopping Title Optimization (WebAppick)](https://webappick.com/google-shopping-title-optimization/)
- [Google Shopping Description Guide (AdNabu)](https://blog.adnabu.com/google-shopping-feed/google-shopping-feed-description/)
- [Google Merchant Center Product Data Specification](https://support.google.com/merchants/answer/7052112)
- [Merchant API ProductAttributes Reference](https://developers.google.com/api/reference/rest/products_v1/ProductAttributes.html)
- [Google Shopping Title & Structured Title (Google Help)](https://support.google.com/merchants/answer/6324415?hl=en)
- Internal data: Allied Brass search_queries table (714 unique queries), keyword_metrics table (Google Ads Keyword Planner)
