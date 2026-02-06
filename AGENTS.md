# Allied FeedOps Agent Guidelines

## Core Principle: No Hallucination

**CRITICAL**: All product content MUST be grounded in actual product data. Never invent features, specifications, or benefits not present in the source data.

## Content Generation Architecture

### BALANCED Approach (Quality-First Default)

The system prompt uses a **BALANCED** approach — NOT every product needs emotional drama:

- **Quality-First (DEFAULT)**: Standard products (towel bars, hooks, shelves) — open with craftsmanship, materials, design
- **Pain-Point-First (ONLY when natural)**: Grab bars (institutional look), rollerless TP holders (spring hassle), shower caddies (scattered bottles)

**DO NOT** manufacture drama where none exists. Authenticity matters.

### Single Source of Truth

- **System prompt**: Lives in code at `dashboard/src/lib/regeneration/prompts.ts` (git-versioned, code-reviewed)
- **Gold standard examples + category guidance**: Lives in Supabase `prompt_templates` table (data, not logic)
- The DB's `system_prompt` column is **ignored** — code is authoritative

### Post-Generation Validation

Generated content is validated against hard rules before saving:
- Shopify titles: no "Allied Brass", no finish names
- All titles: minimum 30 chars, must not be just a SKU or brand name
- Google/Bing descriptions: no hardcoded finish names in base content

Violations trigger an **auto-retry** with the violation highlighted. Quality scoring applies hard penalties for violations that slip through.

### Bing Synonym Integration

Bing descriptions should use product synonyms **across different sentences** naturally:
- GOOD: "This wall-mounted towel bar keeps towels organized." ...later... "The solid brass rack coordinates with..."
- BAD: "towel bar (towel rack / towel holder)" or "16-inch / 16in / 16 inches"

## Platform Policy Guardrails (2026)

These rules prevent disapprovals and “AI text” compliance issues. If any rule conflicts with conversion copy, **policy wins**.

- **Google Merchant Center (AI text disclosure)**:
  - If titles/descriptions are generated using generative AI, submit them via **`structured_title` / `structured_description`** and set **`digital_source_type=trained_algorithmic_media`**.
  - If both structured and standard fields are present (for example, `structured_title` + `title`), Google will **only use** the standard field and the structured field will be ignored. To guarantee structured-only behavior, omit `title` (and omit `description` when using `structured_description`).
- **Google Merchant Center (AI image disclosure)**:
  - If you submit AI-generated images, ensure they include IPTC Photo Metadata `DigitalSourceType` set to **trained algorithmic media** (IPTC controlled vocabulary value: `http://cv.iptc.org/newscodes/digitalsourcetype/trainedAlgorithmicMedia`).
  - The metadata must be **preserved** from your source image through any processing pipeline; if you can’t guarantee that, do not rely on AI-generated images as primary images.
- **Google Merchant Center (images)**: Keep a clean primary image; add lifestyle images as additional images (or `lifestyle_image_link`) to test CTR lift without risking primary-image trust.
- **Google Merchant Center (consistency)**: Keep feed titles/descriptions consistent with on-site product content and the true product attributes. Large mismatches risk disapprovals and customer trust loss.
- **Google Merchant Center (short titles)**: `short_title` can be used for certain placements (for example, Demand Gen). Keep it ≤70 characters and make it readable as an overlay.
- **Avoid gimmicky punctuation** in titles (excess symbols and attention-grabbing formatting). Prefer simple separators like commas or hyphens.
- **Shopify SEO**: Search snippets have practical limits (SEO title often truncates around ~50–60 chars; meta descriptions often truncate around ~150–160 chars). Shopify’s fields can be longer, but long titles can hurt scanning and conversion.

### Operational Notes (This Repo)

- For Google supplemental feeds, set `FEEDOPS_GMC_STRUCTURED_ONLY=1` when you want GMC to use `structured_title` / `structured_description` and ignore plain `title` / `description` (implemented in `src/feedops/integrations/google_supplemental.py`).

### Policy References (Keep Current)

- Google Merchant Center: “Share information about AI-generated content” (AI text + AI image metadata guidance)
- Google Merchant Center: Title attribute docs (`structured_title` behavior when `title` is present)
- Google Shopping API: `DigitalSourceType` enum (for structured attribute `digital_source_type` values)

### Accuracy Rules

1. **Only include information from provided product data**
2. **If a specification is unknown, omit it rather than guessing**
3. **Verify every feature mentioned exists in source data**
4. **Cross-reference all measurements/specifications exactly**
5. **Never add marketing claims that cannot be verified**
6. **Use product images to verify visual characteristics** - if available, analyze the product image to confirm materials, colors, and features

### Output Formatting Rules

**CRITICAL**: Customer-facing content (titles and descriptions) must be CLEAN:
- ❌ **NEVER include source citations** like `(catalog_csv.Material)` in output text
- ❌ **NEVER include field references** or attribution in titles/descriptions
- ✅ Source attribution belongs ONLY in the claims/verification array
- ✅ Titles and descriptions should read naturally to customers

---

## Product Title Optimization Rules

### Character Priority Strategy

| Zone | Characters | Purpose | Priority |
|------|-----------|---------|----------|
| **Most Critical** | 1-30 | Mobile visibility cutoff | Highest - keyword anchor |
| **Critical** | 31-70 | Desktop visibility | Very High - determines clicks |
| **Extended** | 71-150 | Algorithm matching coverage | High - expands query eligibility |

**Note**: Google may rewrite or reorder product titles in some placements (Product Data Customization). Don’t rely on rewrites; front-load your highest-impact attributes.

### Channel-Specific Title Targets

- **Google Shopping / PMax**: Use up to **150 characters**; optimize **first 70** for human scanning and **71–150** for query matching coverage.
- **Bing/Microsoft Shopping**: Favor clarity and literal matching; avoid keyword stuffing in titles.
- **Shopify On-Site**: Optimize for readability and trust first; keep the on-page title concise when possible (SEO title can be shorter than the product title).

### Variant Content Generation

For Google/Bing variant content:
- **Base content** is finish-agnostic (no specific finish mentioned)
- **Finish sentences** describe the relationship between THIS product and each finish
- **28 finishes** for content generation (excludes Military Camo and Red White and Blue)
- Good: "The warm, aged patina of Antique Brass complements this traditional Carolina design"
- Bad: "Antique Brass makes a bold statement" (generic, could apply to any product)

### Title Structure Formula (Brand Recognition Based)

**For Well-Known Brands** (Nike, Apple, Samsung):
```
[Brand] + [Product Type] + [Key Attributes] + [Size/Color]
```

**For Lesser-Known Brands** (like Allied Brass):
```
[Primary Query Phrase] + [Key Dimension] + [Variant Differentiator] + [Brand]
```

**For Google/Bing Variant Titles** (finish-first for variant content):
```
{FINISH_NAME} [Product] [Key Specs] - [Differentiator] - [Collection] - Allied Brass
```

**Why finish-first for variants?** Finish name provides immediate visual/style context and matches high-intent queries like "unlacquered brass towel bar".

**Why?** People don't search for "Allied Brass towel bar" - they search for "bathroom towel bar wall mount 24 inch". Put what they search for FIRST.

### Title Rules

1. **Front-load highest-converting keywords** - First 30-70 characters must contain:
   - The terms people actually search for
   - Product type (what it IS)
   - Primary dimension (size that matters for purchase decision)
   - Primary variant differentiator (finish/size) when applicable

   **Finish-first reality check:** Many high-intent queries lead with finish/material (e.g., “unlacquered brass towel bar”). When finish is a primary query modifier, ensure it’s visible within the first ~70 characters for variant titles.

2. **Use natural query language** - Match how customers actually search:
   - ✅ "24-Inch Towel Bar" (matches user search)
   - ❌ "Towel Bar 24in" (unnatural phrasing)

3. **Include functional modifiers (only if verified)**:
   - ADA Compliant, Retractable, Wall-Mount, Concealed Mount
   - Pivoting, Tilt-Adjustable
   - Only include “solid brass” when the material is explicitly solid brass in source data.

4. **Avoid wasted characters**:
   - ❌ No promotional text ("Free Shipping!", "Sale!")
   - ❌ No ALL CAPS words
   - ❌ No internal SKU codes
   - ❌ No filler words ("high-quality", "premium" without specifics)
   - ❌ Avoid symbol-heavy separators (prefer commas/hyphens over pipes)

5. **Brand placement logic** (UPDATED per industry research):
   - IF brand is household name (Nike, Apple) → Brand FIRST
   - IF brand is niche/unknown (Allied Brass for many shoppers) → Benefits/Keywords FIRST, Brand at END
   - If brand-modified queries are meaningful (for example, “Allied Brass towel bar”), test a brand-forward variant; don’t assume brand-last is always best.

### Title Examples by Category

**Grab Bar (Safety-Focused, Benefit-First)**:
```
ADA-Compliant 18-Inch Grab Bar, 500 lb Capacity, Solid Brass, Satin Nickel, Allied Brass
```

**Towel Bar (Commodity, Benefit-First)**:
```
24-Inch Wall Mount Towel Bar, Solid Brass, Oil Rubbed Bronze, Allied Brass
```

**Mirror (Design-Focused)**:
```
Oval Tilt Vanity Mirror, Solid Brass Frame, Antique Pewter, Allied Brass Waverly Place
```

### Title and Description Work Together

**Titles and descriptions are complementary outputs from unified research.**

The research phase (gathering evidence, analyzing the product, identifying keywords, understanding customer intent) is done ONCE. Both title and description are generated from that same research to maximize revenue:

| Output | Purpose | Success Metric |
|--------|---------|----------------|
| **Title** | Capture attention, match search queries | Click-through rate (CTR) |
| **Description** | Build trust, provide details, address objections | Conversion rate (CVR) |

**Do NOT deprioritize descriptions.** A great title that drives clicks to a weak description wastes ad spend. Both must be excellent.

---

## Product Description Optimization Rules

### Character Priority Strategy

| Zone | Characters | Purpose |
|------|-----------|---------|
| **Hook** | 1-150 | Visible in previews/snippets - MUST contain value proposition |
| **Body** | 151-500 | Detailed features and benefits |
| **Extended** | 500+ | Often improves conversion when properly structured |

### Description Structure: Benefits → Features → Trust

```
[Opening Hook: 1-2 sentences with primary benefit + key spec]

[Key Highlights: 3-5 bullet points]
• Benefit 1 + supporting feature
• Benefit 2 + supporting feature  
• Benefit 3 + supporting feature

[Detail Section: Specifications, installation, warranty]
```

### Description Rules

1. **First 150 characters are CRITICAL**:
   - Lead with the primary benefit (what problem it solves)
   - Include the key differentiating spec
   - Make it standalone compelling (this may be all users see)

2. **Structure for scanners** (most users scan, not read):
   - Use bullet points for key highlights
   - Use short paragraphs (2-3 sentences max)
   - Bold key terms if format allows

3. **Benefits before features**:
   - ✅ "Solid brass construction ensures your towel bar will never corrode, peel, or tarnish"
   - ❌ "Made of solid brass" (feature without benefit)

4. **Use concrete, verifiable language**:
   - ✅ "Supports up to 500 lbs" (specific, testable)
   - ❌ "Premium quality construction" (vague, unverifiable)

5. **Address buyer uncertainty**:
   - Will it fit? → Include dimensions
   - Will it last? → Material specs + warranty
   - Is it easy to install? → Installation details
   - Will it match my decor? → Finish coordination info

6. **Avoid disallowed content**:
   - ❌ No pricing or shipping info
   - ❌ No ALL CAPS
   - ❌ No promotional language ("BEST!", "Amazing!")
   - ❌ No URLs in description text

### Description Examples

**Towel Bar Opening Hook** (first 150 chars):
```
Crafted from solid brass that will never corrode, peel, or tarnish, this 24-inch
towel bar brings enduring elegance to your bathroom with wall-mounted convenience.
```

**Grab Bar Full Description**:
```
Protect your loved ones with this ADA-compliant grab bar engineered to support up
to 500 pounds. Solid brass construction provides the strength needed for confident
daily use.

• 500lb weight capacity - exceeds ADA requirements for safety
• Knurled grip surface - secure hold even with wet hands
• Concealed mounting hardware - clean, decorator-friendly appearance
• Satin nickel finish - coordinates with modern bathroom fixtures

Includes all mounting hardware for easy installation. Backed by Allied Brass's
lifetime warranty on construction and 5-year finish guarantee.
```

---

## Content Scoring Rubric

Rate each output 0-10 on six dimensions. Target: **80%+ composite score** before publishing. Flag outputs below 70% for human review.

### 1. Specificity Score (0-10)
- 10: All claims are specific and verifiable (dimensions, materials, capacities)
- 5: Mix of specific and vague claims
- 0: All claims are generic ("high-quality", "premium", "best")

**Formula**: (Specific Claims / Total Claims) × 10

### 2. Benefit Coverage (0-10)
- 10: Primary benefits addressed in first 150 characters
- 5: Benefits mentioned but not in opening
- 0: Only features listed, no benefits stated

**Check**: Can a reader immediately understand WHY they should buy?

### 3. Keyword Inclusion (0-10)
- 10: All target keywords in optimal positions (title front-loaded, description natural)
- 5: Keywords present but suboptimal placement
- 0: Missing critical keywords

**Title**: Product Type + Key Dimension + Variant differentiator in first 70 chars?
**Description**: Primary keyword in first sentence?

### 4. Format Adherence (0-10)
- 10: Perfect compliance with character limits and structure
- 5: Minor violations (slightly over/under limits)
- 0: Major violations (exceeds limits, wrong structure)

**Checklist**:
- [ ] Title ≤150 characters
- [ ] Description ≥500 characters (recommended)
- [ ] First 150 chars contain value proposition
- [ ] Bullets used for highlights

### 5. Brand Voice Match (0-10)
- 10: Confident, specific, premium-appropriate tone
- 5: Neutral tone, neither premium nor budget
- 0: Uses superlatives, marketing fluff, or budget language

**Premium indicators (only if verifiable)**: solid brass, concealed mounting, precision-fit, corrosion-resistant materials/finishes, warranty terms
**Avoid**: Amazing, incredible, best-ever, cheap, budget

### 6. Factual Accuracy (0-10)
- 10: Every claim traceable to product data
- 5: Some claims inferred but reasonable
- 0: Contains invented specs or unverifiable claims

**CRITICAL**: This score cannot be below 8 for publication

### Composite Score Calculation

```
Composite = (Specificity + Benefits + Keywords + Format + Voice + Accuracy) / 6 × 10

≥80%: Approved for publication
70-79%: Minor revisions needed
<70%: Major revision or human review required
```

---

## Platform-Specific Considerations

### Google Shopping / Performance Max
- Semantic matching - algorithm understands synonyms
- Feed is "seed prompt" for PMax AI asset generation
- Title + Description used across Search, Display, YouTube, Gmail
- Ensure content works standalone as text overlay

### Bing/Microsoft Shopping
- More literal keyword matching than Google
- Include explicit synonyms in description
- Exact Match keywords override Ad Rank
- Copilot requires high "confidence score" from complete attributes

### Shopify On-Site
- Title becomes H1 and affects organic SEO
- Description must support both SEO and conversion
- Mobile: Use accordions over tabs for specs
- Desktop: Optimize for F-pattern scanning

---

## Cognitive Psychology Principles

### Why These Rules Work

1. **System 1 vs System 2**: Many purchases start with fast, intuitive evaluation (benefits) and are confirmed with rational details (specs, installation, warranty).

2. **Cognitive Fluency**: Matching title to search query creates "this is exactly what I want" recognition. Reduces mental effort.

3. **Uncertainty Reduction**: Detailed, specific descriptions answer questions before they're asked. Reduces purchase friction.

4. **Concreteness Effect**: Concrete terms ("solid brass") activate both verbal AND visual processing. Abstract claims ("premium") only activate verbal.

5. **Brand-Modified Queries**: Often convert higher because familiarity reduces perceived risk and speeds decision-making.

6. **Functional Modifiers**: Often lift CVR because they signal product-problem fit for high-intent shoppers.

---

## Quick Reference Card

### Title Checklist
- [ ] ≤150 characters total
- [ ] Critical info in first 70 characters
- [ ] Product Type + Key Dimension + variant differentiator upfront
- [ ] Functional modifier if applicable
- [ ] No promotional text or ALL CAPS
- [ ] Matches natural search language

### Description Checklist
- [ ] Benefit-focused opening in first 150 characters
- [ ] ≥500 characters total (recommended)
- [ ] 3-5 bullet highlights
- [ ] Specific, verifiable claims only
- [ ] Dimensions, materials, capacity stated
- [ ] Installation/warranty info included
- [ ] No pricing, shipping, or URLs

### Red Flags (Immediate Rejection)
- ❌ Invented specifications
- ❌ Claims not in source data
- ❌ ALL CAPS words
- ❌ Promotional language in feed
- ❌ Generic-only descriptions ("great quality product")
