# Task 25: Content Generation Optimization — Validate Methodology Before Scaling

## Objective

**Validate and optimize our content generation methodology BEFORE scaling** by comparing against industry best practices, competitor analysis, and platform guidelines.

**Critical Context**:
- We have published only **ONE SKU** (FT-16) to both Google Shopping and Shopify
- We have **~2-3% approval rate** on generated content (high quality scores but low approval volume)
- Publishing infrastructure is **confirmed working** (FT-16 proves this)
- This is **PROACTIVE validation** ("is our methodology optimal?") not **REACTIVE analysis** ("why did we fail?")

**Two-Surface Optimization**:
1. **Google Shopping (GMC)**: Titles and descriptions that maximize CTR and CVR in Shopping ads
2. **Shopify storefront**: Product page copy that maximizes add-to-cart and purchase rates after visitor lands

This is a research-first task. Validate our current methodology against industry standards and identify improvements BEFORE we scale up publishing to thousands of SKUs.

## Approach

Use agent teams to parallelize the research phase. This task has multiple independent research streams that benefit from concurrent investigation.

### Team Structure

**Team name**: `content-optimization`

**Agents**:
1. `ads-researcher` (general-purpose) — Analyze Google Ads performance data, search query patterns, and competitor titles to find optimization opportunities for Shopping ads
2. `cro-researcher` (general-purpose) — Analyze Shopify on-site patterns, product page copy best practices, and conversion optimization opportunities
3. `prompt-engineer` (general-purpose) — Audit the current generation prompt, scoring system, and evidence pipeline to identify gaps and propose improvements

## Phase 1: Research (Parallel Agents)

### Agent 1: Google Shopping Best Practices & Competitor Research

**Goal**: Research industry best practices for Google Shopping titles/descriptions and analyze what top competitors in bathroom hardware are doing.

**CRITICAL**: You are NOT analyzing our own performance data (we only have 1 published SKU). You ARE researching what the industry and successful competitors do.

**Tasks**:

1. **Research Google Shopping title optimization best practices (2026)**:
   - **MUST USE**: `marketing-skills:paid-ads` skill to get expert guidance on Google Shopping optimization
   - Ask the skill: "What are the best practices for Google Shopping product titles and descriptions for bathroom hardware in 2026? Focus on: 1) Title structure and keyword placement, 2) Description length and format, 3) What drives CTR in this category, 4) Common mistakes to avoid."
   - Use `WebSearch` to find recent (2025-2026) articles on Google Shopping optimization
   - Focus on: Title character limits, keyword front-loading, spec inclusion, price point messaging

2. **Research GMC structured data and AI content guidelines**:
   - Use `mcp__merchant-api-devdocs__query_mapi_docs` to understand GMC's latest guidance on:
     - `structured_title` vs standard `title` field
     - `structured_description` vs standard `description` field
     - `digital_source_type=trained_algorithmic_media` for AI-generated content
   - What are the official GMC best practices for AI-generated product content?

3. **Competitor title analysis** (bathroom hardware category):
   - Use `mcp__Apify__*` OR `mcp__claude-in-chrome__*` to scrape Google Shopping results for:
     - "bathroom towel bar brass" (high-volume category)
     - "bathroom glass shelf" (FT-16's category for comparison)
     - "bathroom grab bar" (safety category)
   - Analyze top 10 competitors in each category:
     - Title structure patterns (what comes first? brand, material, or product type?)
     - Keyword usage (what terms appear most frequently?)
     - Spec inclusion (dimensions, material, finish mentioned in title?)
     - Brand positioning (where does brand name appear?)

4. **Search query → title alignment research**:
   - Use `mcp__supabase__execute_sql` to check what search queries are showing our products:
     ```sql
     SELECT query_text, SUM(impressions) as total_impressions,
            SUM(clicks) as total_clicks, COUNT(DISTINCT master_sku) as sku_count
     FROM search_queries
     GROUP BY query_text
     ORDER BY total_impressions DESC
     LIMIT 50;
     ```
   - Compare these actual search queries against industry best practices:
     - Are customers using room context ("bathroom shelf" vs just "shelf")?
     - Are they including material ("brass towel bar")?
     - Are they brand-aware or feature-focused?
   - **Key question**: What's the gap between what customers search for and what our titles emphasize?

5. **Keyword opportunity analysis**:
   - Use `mcp__google-ads-mcp__search` with Keyword Planner to find high-volume keywords in bathroom hardware
   - NOT to analyze our performance, but to understand market demand
   - Categories to research: towel bars, soap dishes, grab bars, glass shelves, robe hooks
   - Identify: High search volume + low competition keywords we should target

**Deliverable**: Report comparing our current title methodology against industry best practices and competitor patterns. Include specific recommendations for title structure, keyword inclusion, and content formatting.

### Agent 2: Shopify CRO Best Practices & Methodology Validation

**Goal**: Research Shopify product page CRO best practices and validate our current content methodology against industry standards.

**CRITICAL**: We have only ONE approved and published SKU (FT-16). Use this as a reference point to validate methodology, not to analyze performance.

**Tasks**:

1. **Research Shopify product page CRO best practices (2026)**:
   - **MUST USE**: `marketing-skills:page-cro` skill for expert product page optimization guidance
   - Visit FT-16 live page: https://www.alliedbrass.com/products/ft-16
   - Ask the skill to analyze this page against CRO best practices for bathroom hardware e-commerce
   - **MUST USE**: `marketing-skills:copywriting` skill to evaluate title and description quality
   - Focus on:
     - Description length and structure (benefits-first vs specs-first vs hybrid)
     - Use of bullet points vs prose
     - Trust signals (warranty, Made in USA)
     - Mobile-first formatting
     - Conversion psychology for mid-market fixtures ($30-$200 price point)

2. **Competitor Shopify page analysis**:
   - Use `WebSearch` to find top bathroom hardware e-commerce sites (competitors to Allied Brass)
   - Use `mcp__claude-in-chrome__*` to visit 5-10 competitor product pages
   - Document successful patterns:
     - How do competitors structure product descriptions?
     - What information comes first?
     - How do they handle technical specs vs benefits?
     - What trust signals do they use?
     - How do they handle variant selection (finishes)?

3. **Validate our FT-16 content against best practices**:
   - Query FT-16's current content from database:
     ```sql
     SELECT platform, content_type,
            baseline_content as old_content,
            candidate_content as new_content,
            approved_content,
            quality_score
     FROM generated_content
     WHERE master_sku = 'FT-16'
     ORDER BY platform, content_type;
     ```
   - Compare OLD vs NEW content:
     - **MUST USE**: `marketing-skills:copywriting` skill to objectively evaluate which is better and why
     - What specific improvements were made from OLD to NEW?
     - Do these improvements align with CRO best practices?
   - Is our approved content (what's live) following industry best practices?

4. **Cross-surface messaging consistency**:
   - Customer journey: Google Shopping ad → clicks → Shopify product page
   - Research best practices: Should the Shopify description reinforce the ad's message?
   - Message match: What's the risk of disconnect between surfaces?
   - Platform differentiation: How should Google title differ from Shopify title?

5. **Research bathroom hardware buyer decision factors**:
   - Use `WebSearch` to research what information buyers need before purchasing bathroom fixtures
   - Key questions to answer:
     - What objections do buyers have? (installation difficulty, quality concerns, matching existing fixtures)
     - What information reduces purchase anxiety? (dimensions, return policy, warranty)
     - What drives impulse vs considered purchases in this category?
   - **Validate**: Does our description structure address these decision factors?

6. **Mobile-first content evaluation**:
   - Use `mcp__claude-in-chrome__*` to view FT-16 on mobile viewport
   - What appears above the fold?
   - Is the description scannable on mobile?
   - Research: What's the mobile conversion best practices for product pages?

**Deliverable**: CRO analysis report comparing our current Shopify content methodology against industry best practices. Include specific recommendations for content structure, messaging hierarchy, and conversion optimization.

### Agent 3: Methodology Audit Against Best Practices

**Goal**: Audit our current generation system (prompts, scoring, evidence pipeline) against the best practices discovered by Agents 1 and 2.

**CRITICAL**: This is NOT about "does our scoring correlate with performance" (we don't have enough data). This IS about "does our methodology align with industry standards and competitor patterns."

**Tasks**:

1. **Audit system prompt against best practices**:
   - Read the FULL system prompt: `dashboard/src/lib/regeneration/prompts.ts` (272 lines)
   - **Wait for Agents 1 and 2** to complete their research on best practices
   - Compare our prompt instructions against discovered best practices:
     - Google Shopping guidelines: Does our prompt follow GMC structured data best practices?
     - Competitor patterns: Are we instructing the LLM to use winning title structures?
     - CRO principles: Does the prompt guide toward conversion-optimized descriptions?
   - Identify gaps:
     - What instructions are missing that would align with best practices?
     - What instructions conflict with industry standards?
     - What instructions are vague when they should be specific?

2. **Audit quality scoring system against validation principles**:
   - Read the FULL scoring system: `dashboard/src/lib/quality-scoring.ts` (887 lines)
   - **NOT asking**: "Does high score predict performance?" (can't validate with 1 SKU)
   - **ARE asking**: "Does the scoring system measure the RIGHT things based on best practices?"
   - Evaluate each dimension:
     - **CTR Proxy**: Is zone-based analysis aligned with Google Shopping best practices?
     - **CVR Proxy**: Is description length the right proxy according to CRO research?
     - **Brand Voice**: Does "premium positioning" match our market segment?
     - **Readability**: Are we optimizing for the right reading level?
   - Compare against Agent 1 and 2 findings:
     - Are we scoring for what actually matters according to research?
     - Are we missing dimensions that competitors optimize for?

3. **Audit evidence pipeline for completeness**:
   - Read evidence builder: `dashboard/src/lib/evidence/builder.ts` (322 lines)
   - Read search queries formatter: `dashboard/src/lib/evidence/search-queries.ts` (302 lines)
   - **NOT asking**: "Why isn't performance data being used?" (we don't have it yet)
   - **ARE asking**: "What available data should be used according to best practices?"
   - Check what data is surfaced to the LLM:
     - Search query data: Is it formatted to guide keyword selection?
     - Product catalog data: Are the right attributes emphasized?
     - Competitor data: Could we surface this? Should we?
     - Keyword volume/competition: Is CPC data visible to guide prioritization?
   - Identify evidence gaps based on Agent 1 and 2 research:
     - What data exists in our database but isn't surfaced?
     - What data SHOULD exist based on competitor analysis?

4. **Validate platform differentiation strategy**:
   - Compare Google vs Bing vs Shopify title/description instructions
   - Based on Agent 1 and 2 findings:
     - Is the differentiation appropriate?
     - Should Google titles be more keyword-focused?
     - Should Shopify titles emphasize different attributes?
     - Are we optimizing for the right intent on each platform?

5. **Audit gold standard examples**:
   - Query `prompt_templates` table for existing examples
   - Compare against best practices from Agent 1 and 2:
     - Do our gold standards follow winning patterns from competitor analysis?
     - Do they reflect Google Shopping optimization principles?
     - Do they demonstrate CRO-optimized descriptions?
   - **Recommendation**: Should we create new gold standards based on research findings?

6. **Validate content quality assumptions**:
   - Our average quality score: ~75-80/100 from Cloud Run pipeline
   - FT-16 approved content: Check its score and compare against best practices
   - **Key question**: If we're scoring 75-80 but only approving 2-3%, is the issue:
     - Score doesn't measure what matters? (scoring misalignment)
     - Approval threshold too high? (workflow issue)
     - Content quality genuinely not good enough? (generation issue)

**Deliverable**: Comprehensive audit report identifying specific gaps between our current methodology and industry best practices. Prioritized recommendations for prompt improvements, scoring recalibration, and evidence pipeline enhancements.

## Phase 2: Synthesis & Validation

After all three agents complete research, synthesize findings into a comprehensive validation report:

1. **Methodology Validation Summary**:
   - What are we doing RIGHT? (aligned with best practices)
   - What are we doing WRONG? (conflicts with industry standards)
   - What are we MISSING? (gaps compared to competitors)

2. **Priority Matrix**: Impact (alignment with best practices) vs Effort (implementation complexity)

3. **Quick Wins** (high alignment impact, low effort):
   - Prompt instruction improvements based on Google Shopping guidelines
   - Evidence pipeline additions (surfacing existing data better)
   - Title structure adjustments to match competitor patterns

4. **Medium-Term** (high impact, medium effort):
   - Scoring system recalibration to measure what matters
   - Gold standard example updates based on research
   - Platform-specific prompt differentiation

5. **Long-Term** (requires new capabilities):
   - Competitor data integration
   - Performance feedback loops (once we have data)
   - A/B testing infrastructure for content validation

## Phase 3: Implementation

Based on approved plan from Phase 2:

### Prompt Improvements
- File: `dashboard/src/lib/regeneration/prompts.ts`
- Update system prompt with research findings
- Add new platform-specific instructions
- Update gold standard examples

### Scoring Calibration
- File: `dashboard/src/lib/quality-scoring.ts`
- Recalibrate dimensions based on performance correlation
- Add new metrics that better predict revenue impact
- Consider: Should we score against search query alignment?

### Evidence Pipeline
- File: `dashboard/src/lib/evidence/builder.ts`
- Add missing data sources
- Better structure for LLM consumption
- Search query → keyword priority mapping

### Testing
- `cd dashboard && npm run build && npm run lint`
- Generate new content for 5-10 SKUs with known performance data
- Compare quality scores and content against previous versions
- Use `superpowers:verification-before-completion` skill before claiming done

## Key Files

| File | Purpose |
|------|---------|
| `dashboard/src/lib/regeneration/prompts.ts` | System prompt (SINGLE SOURCE) |
| `dashboard/src/lib/regeneration/core.ts` | Generation orchestration |
| `dashboard/src/lib/quality-scoring.ts` | 6-dimension scoring (887 lines) |
| `dashboard/src/lib/evidence/builder.ts` | Evidence table builder |
| `dashboard/src/lib/data-collection/ensure-data.ts` | Auto data collection |
| `docs/database/SCHEMA.md` | Full database schema reference |

## MCP Tools & Skills

**MCP Servers** (use freely — no restrictions):
- `mcp__google-ads-mcp__search` — Google Ads performance data, Keyword Planner
- `mcp__merchant-api-devdocs__*` — GMC docs, product data, price competitiveness
- `mcp__supabase__execute_sql` — Database queries (ALWAYS check SCHEMA.md first)
- `mcp__Apify__*` — Competitor scraping, Google Shopping SERP analysis
- `mcp__claude-in-chrome__*` — Live site analysis, product page review
- `mcp__plugin_context7_context7__*` — Up-to-date library documentation

**Skills** (use as appropriate):
- `superpowers:brainstorming` — Before creative decisions on prompt structure
- `marketing-skills:seo-audit` — Shopify organic search optimization
- `marketing-skills:page-cro` — Product page conversion optimization
- `marketing-skills:copywriting` — Copy improvement patterns
- `marketing-skills:ab-test-setup` — Testing methodology for content changes
- `marketing-skills:analytics-tracking` — Measurement setup for new metrics
- `marketing-skills:paid-ads` — Google Shopping ad optimization patterns
- `marketing-skills:content-strategy` — Content approach across platforms
- `superpowers:verification-before-completion` — Before finalizing changes

## Critical Context & Common Pitfalls

### What We Have
- **Published SKUs**: Only FT-16 (both Google Shopping and Shopify)
- **Generated content**: ~72,000+ SKUs have candidate content generated
- **Approval rate**: ~2-3% of generated content is approved
- **Current quality**: ~75-80/100 average from Cloud Run pipeline
- **Publishing infrastructure**: CONFIRMED WORKING (FT-16 proves this)

### What We DON'T Have
- **Performance data to analyze**: Only 1 published SKU = insufficient for statistical validation
- **Failed optimization to debug**: We haven't started scaling yet
- **Infrastructure problems**: Publishing works, approval workflow works

### Research Focus (DO)
- ✅ Compare our methodology against Google Shopping best practices (2026)
- ✅ Analyze competitor title/description patterns in bathroom hardware
- ✅ Research Shopify CRO principles for product pages
- ✅ Validate our prompts against industry standards
- ✅ Use marketing skills (page-cro, copywriting, paid-ads) for evaluation
- ✅ Identify gaps between our approach and what successful competitors do

### Research Anti-Patterns (DON'T)
- ❌ Assume we have performance data to correlate with scores (we don't)
- ❌ Try to validate scoring system against CTR/CVR (only 1 published SKU)
- ❌ Debug "why aren't we performing well" (we haven't scaled yet)
- ❌ Analyze "what's broken in publishing" (it works - FT-16 proves it)
- ❌ Compare performance of OLD content vs scores of NEW content (invalid)

### Success Metrics
- **Goal**: Validate methodology is aligned with industry best practices BEFORE we scale from 1 to 1,000+ published SKUs
- **Outcome**: Confidence that our generation system follows winning patterns from the market
- **NOT**: Correlation between our scores and our own performance (insufficient data)

### Database Reference
- **Schema**: ALWAYS read `docs/database/SCHEMA.md` before writing SQL
- **Google Ads customer ID**: `6253381786`
- **Supabase project**: `qezuszwufortkiutlhym`
- **Offer ID format**: Database = lowercase `shopify_us_`, GMC = uppercase `shopify_US_`
- **Multi-SKU products**: Multiple master_skus can share same product_id
