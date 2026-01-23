# Allied FeedOps: Platform-Specific Guidelines

## Overview

While core optimization principles apply across platforms, each channel has unique requirements and behaviors. This document covers platform-specific considerations for Google, Bing, and Shopify.

---

## Google Shopping / Performance Max

### Algorithm Characteristics

**Semantic Matching**: Google understands synonyms and intent
- "Towel bar" can match "towel rack" or "towel holder"
- Algorithm interprets meaning, not just keywords
- BUT front-loaded keywords still carry more weight

**Quality Score Impact**: Relevance affects CPC
- Better title relevance → Lower cost per click
- Higher CTR → Better ad rank at same bid
- Landing page consistency required

**PMax Behavior**: Feed is "seed prompt" for AI
- Google generates text/video assets from feed data
- Description text may appear in Display ads
- Title may become headline on YouTube
- Content must work across channels

### Title Requirements

```yaml
google_title:
  max_length: 150
  visible_length: 70  # Mobile cutoff
  
  required:
    - Product identifying information
    - Distinguishing attributes for variants
    
  recommended:
    - Brand name (at start if well-known)
    - Product type
    - Key dimension/size
    - Material
    - Functional modifiers
    
  prohibited:
    - ALL CAPS words
    - Exclamation points
    - Promotional text (Free, Sale, etc.)
    - Prices or shipping info
    - Keywords not on landing page (gray area)
```

### Description Requirements

```yaml
google_description:
  max_length: 5000
  recommended_length: 500-1000
  visible_length: 150  # In previews
  
  required:
    - Accurate product information
    - No prohibited content
    
  recommended:
    - Benefit-first opening
    - Specific, verifiable claims
    - Use-case information
    - Keywords for long-tail matching
    
  prohibited:
    - HTML (some basic allowed but risky)
    - Promotional phrases
    - Pricing/shipping info
    - External links
    - GTIN/MPN (use proper attributes)
```

### Google-Specific Optimizations

1. **Short Title Attribute**: Use `short_title` for cleaner video overlays
   ```
   title: "Allied Brass 24-Inch Towel Bar | Solid Brass | Polished Chrome | Wall Mount"
   short_title: "Allied Brass Chrome Towel Bar"
   ```

2. **Structured Data Alignment**: Match JSON-LD schema on landing page

3. **Custom Labels**: Use for margin/priority segmentation
   ```
   custom_label_0: "premium"
   custom_label_1: "optimized-2024-01"
   ```

4. **Performance Max Considerations**:
   - Ensure titles work as text ad headlines
   - Descriptions should have "snippet-worthy" phrases
   - Images must complement text (visual-text alignment)

---

## Microsoft / Bing Shopping

### Algorithm Characteristics

**More Literal Matching**: Less semantic interpretation
- "Towel bar" may not match "towel holder" as well
- Exact keyword matches carry more weight
- Include synonyms explicitly in description

**Exact Match Priority**: Keywords override ad rank
- If you bid on [exact match], it WILL serve
- More control over high-value queries
- "Snipe" specific terms with text ads

**Copilot Confidence Score**: Attribute completeness matters
- AI needs complete data to recommend products
- Missing attributes = excluded from Copilot
- Fill ALL optional fields

### Bing-Specific Requirements

```yaml
bing_title:
  max_length: 150
  visible_length: 70-100  # Desktop shows more
  
  required:
    - Brand name (REQUIRED for branded products)
    - Product identifying information
    
  recommended:
    - All fields from Google PLUS
    - Explicit synonyms where helpful
    - Model numbers if commonly searched
    
  format_notes:
    - Bing may show more characters on desktop
    - Include extra keywords after 70-char mark
```

### Bing-Specific Optimizations

1. **Always Include Brand**: Required policy for branded products

2. **Expand Synonyms in Description**:
   ```
   Google: "24-inch towel bar"
   Bing: "24-inch towel bar (towel holder, bath towel rack)"
   ```

3. **Complete All Attributes**: Copilot confidence requires:
   - All optional fields filled
   - Detailed specifications
   - Clear category mapping

4. **Consider Bing Audience**:
   - Older demographic (45+)
   - More affluent on average
   - Desktop-heavy usage
   - More brand-focused searches

### Bing Feed Variant

Consider a Bing-specific feed with:
```yaml
bing_modifications:
  title:
    - Ensure brand is present
    - Add parenthetical synonyms if space permits
  description:
    - Include more explicit keywords
    - Add synonyms naturally in text
  attributes:
    - Fill ALL optional fields
    - Include model numbers
```

---

## Shopify (On-Site)

### SEO Considerations

**Title Becomes H1**: Affects organic rankings
- Product title = page H1
- Also influences title tag
- Must balance SEO with conversion

**Description Affects Meta**: Impacts search snippets
- First ~155 characters may show in Google
- Write for humans first, SEO second
- Include primary keyword naturally

### Shopify-Specific Requirements

```yaml
shopify_title:
  max_length: 255  # Shopify limit
  seo_optimal: 60-70  # For title tag
  
  considerations:
    - Works as H1 heading
    - Readable by humans browsing
    - May appear in breadcrumbs
    - Should match collection structure
    
shopify_description:
  format: HTML  # Shopify supports rich text
  
  structure:
    - First paragraph: Hook (SEO-friendly)
    - Bullet highlights: Key features
    - Detailed sections: Specs, installation
    - Trust elements: Warranty, shipping
```

### On-Site Conversion Optimizations

1. **Mobile-First Structure**:
   - Accordions over tabs for specs
   - Critical info in first 2-3 lines
   - Sticky add-to-cart button
   
2. **Reduce Cognitive Load**:
   - Clear, scannable format
   - F-pattern friendly layout
   - Benefits visible without scrolling

3. **Address Uncertainty**:
   ```html
   <div class="product-highlights">
     <p><strong>Will it fit?</strong> 24 inches - ideal for standard bath towels</p>
     <p><strong>Will it last?</strong> Solid brass, lifetime warranty</p>
     <p><strong>Easy to install?</strong> All hardware included, 10-minute setup</p>
   </div>
   ```

4. **Metafield Usage**: Store structured data for:
   - Material specifications
   - Dimensions (separate fields)
   - Certifications
   - Collection relationships

### Shopify Theme Considerations

```liquid
<!-- Product page structure -->
<div class="product-description">
  <!-- Hook: Always visible -->
  <div class="product-hook">
    {{ product.metafields.custom.hook | default: product.description | truncate: 200 }}
  </div>
  
  <!-- Highlights: Accordion on mobile -->
  <details class="product-highlights" open>
    <summary>Key Features</summary>
    {{ product.metafields.custom.highlights }}
  </details>
  
  <!-- Specs: Collapsible -->
  <details class="product-specs">
    <summary>Specifications</summary>
    {{ product.metafields.custom.specifications }}
  </details>
</div>
```

---

## Cross-Platform Consistency

### What MUST Be Consistent

1. **Core Product Identity**:
   - Brand name (spelling, capitalization)
   - Product type
   - Primary dimensions
   - Material
   - Model numbers

2. **Claims and Specifications**:
   - Weight capacity
   - Certifications (ADA, UL)
   - Warranty terms
   - What's included

3. **Pricing** (if shown):
   - Must match landing page
   - Google crawl verification

### What CAN Vary

1. **Keyword Placement**:
   - Google: semantic matching allows flexibility
   - Bing: explicit keywords more important

2. **Character Utilization**:
   - Google title visible: 70 chars
   - Bing title visible: 70-100 chars
   - Shopify: full title visible on page

3. **Description Depth**:
   - Feed: keyword-rich, plain text
   - Shopify: formatted, conversion-focused

### Feed vs. Site Content Strategy

```yaml
content_strategy:
  title:
    shopify: "Allied Brass Waverly Place 24-Inch Towel Bar"  # Clean for H1
    google_feed: "Allied Brass 24-Inch Towel Bar | Solid Brass | Polished Chrome | Wall Mount"  # Keyword-rich
    bing_feed: "Allied Brass 24-Inch Towel Bar (Towel Holder) | Solid Brass | Chrome | Wall Mount"  # With synonym
    
  description:
    shopify: Full HTML with formatting, images, accordions
    google_feed: Plain text, keyword-rich, benefit-first
    bing_feed: Plain text with explicit synonyms
```

---

## Platform Compliance Checklist

### Google Merchant Center

```markdown
## Pre-Submission Checklist

### Title
- [ ] ≤150 characters
- [ ] No ALL CAPS words
- [ ] No promotional text (Free!, Sale!, etc.)
- [ ] No exclamation points
- [ ] Brand matches landing page
- [ ] Product type identifiable

### Description
- [ ] ≤5000 characters
- [ ] No HTML (or minimal, properly formatted)
- [ ] No promotional language
- [ ] No pricing or shipping info
- [ ] Accurate product information

### Landing Page Alignment
- [ ] Title matches page content
- [ ] Price matches exactly
- [ ] Product available for purchase
- [ ] Images match actual product
```

### Microsoft Merchant Center

```markdown
## Pre-Submission Checklist

### Title
- [ ] ≤150 characters
- [ ] Brand name INCLUDED (required)
- [ ] No ALL CAPS
- [ ] No promotional text
- [ ] Category-appropriate structure

### Description
- [ ] ≤5000 characters
- [ ] No URLs
- [ ] Complete product information
- [ ] Synonyms included naturally

### Attribute Completeness
- [ ] All required attributes filled
- [ ] Optional attributes completed
- [ ] Category taxonomy correct
- [ ] GTIN/MPN if available
```

### Shopify SEO

```markdown
## Pre-Publish Checklist

### Title (H1/SEO)
- [ ] Primary keyword included
- [ ] Readable and clear
- [ ] ≤70 characters (title tag)
- [ ] Unique across products

### Description
- [ ] First 155 chars optimized for meta
- [ ] Primary keyword in first paragraph
- [ ] Structured for scanning
- [ ] No duplicate content

### Technical
- [ ] Clean URL slug
- [ ] Alt text on images
- [ ] Proper schema markup
- [ ] Mobile-friendly layout
```

---

## Troubleshooting Guide

### Google Disapprovals

| Issue | Cause | Solution |
|-------|-------|----------|
| Mismatched data | Title/price differs from page | Ensure feed = landing page |
| Policy violation | Promotional text detected | Remove "Free", "Sale", etc. |
| Invalid formatting | ALL CAPS or special chars | Clean up title format |
| Missing identifier | GTIN required for category | Add GTIN or request exemption |

### Bing Issues

| Issue | Cause | Solution |
|-------|-------|----------|
| Low Copilot visibility | Missing attributes | Fill all optional fields |
| Brand policy | Brand not in title | Add brand name |
| Low impressions | Keyword mismatch | Add explicit synonyms |

### Shopify SEO Issues

| Issue | Cause | Solution |
|-------|-------|----------|
| Duplicate content | Same description variants | Unique descriptions per variant |
| Thin content | Description too short | Expand with specifications |
| Poor rankings | Missing keywords | Optimize title and first paragraph |
| High bounce | Mismatch with search intent | Align content with query intent |

---

## Performance Benchmarks

### Expected Metrics by Platform

| Metric | Google | Bing | Shopify Organic |
|--------|--------|------|-----------------|
| CTR (Shopping) | 1-3% | 2-4% | N/A |
| CVR | 2-4% | 2-4% | 1-3% |
| Bounce Rate | 40-60% | 40-60% | 40-50% |

### Optimization Impact Expectations

| Optimization | Expected Lift | Timeframe |
|--------------|---------------|-----------|
| Title restructure | +10-30% CTR | 1-2 weeks |
| Description expansion | +1-2pp CVR | 2-4 weeks |
| Functional modifiers | +50-200% CVR (segment) | 1-2 weeks |
| Brand inclusion | +20-50% branded CTR | Immediate |

### Measurement Approach

1. **Baseline**: 2 weeks pre-optimization metrics
2. **Holdout**: Keep control group if possible
3. **Tracking**: Daily metrics for first month
4. **Attribution**: Account for seasonality and external factors
5. **Significance**: Minimum 1000 clicks before conclusions
