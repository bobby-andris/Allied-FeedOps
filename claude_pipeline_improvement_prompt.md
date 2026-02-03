# Pipeline Improvement Plan: Allied-FeedOps

## Context

This is the Allied-FeedOps project. It generates optimized titles and descriptions for Google Shopping, Bing Shopping, and Shopify for Allied Brass bathroom/kitchen hardware products.

### Pipeline overview
1. Fetches product data from Shopify API + Google Merchant Center
2. Sends product evidence (specs, images, keywords) to GPT-5.2 to generate platform-specific titles and descriptions
3. Scores each candidate using a heuristic scoring system (CTR proxy, CVR proxy, brand voice)
4. Selects the best of N candidates
5. Injects finish-specific content for each of the 28 finish variants per product
6. Outputs patch JSON files per platform per finish variant

### Recent pilot results
- 40-SKU pilot with 3 candidates per SKU
- Average heuristic score: 78.6%, range: 65.8% to 84.8%
- Top performers: towel bars, soap dishes (83-85%)
- Bottom performers: retractable hooks, freestanding items, cabinet pulls (65-72%)
- Latest batch report: `dashboard_data/lifestyle-eval-candidate/reports/batch-40sku-3cand-20260130-050228.json`
- Previous batch report (1 candidate): `dashboard_data/lifestyle-eval-candidate/reports/batch-40sku-20260130-042117.json`

---

## Your task

Create an implementation plan to improve the pipeline's content quality and revenue impact. A previous audit identified 10 findings (listed below). Your job is to:

1. **Validate findings with real data** before planning fixes
2. **Resolve a key architectural question** about prompt rigidity (detailed below)
3. **Produce a prioritized implementation plan** with concrete code changes

---

## Phase 1: Data gathering (do this BEFORE planning any changes)

Use the available MCP tools to gather real performance data that should inform your decisions:

### Google Ads (customer ID: 6253381786)
- Pull Shopping campaign performance data by product type (towel bars, soap dishes, cabinet pulls, retractable hooks, freestanding items, glass shelves, robe hooks)
- Get click-through rates, conversion rates, and impression share by product category
- Identify which product types have the highest and lowest ROAS
- Pull search term reports to see what queries shoppers actually use for each product type

### Google Analytics (use Allied Brass - GA4 (Old) property)
- Pull product-level or category-level conversion data from the ecommerce reports
- Identify which product categories have the highest/lowest add-to-cart and purchase rates
- Look at landing page performance for product pages if available

### Apify (optional, use if helpful)
- If you need to scrape competitor product listings on Google Shopping to see how top-ranking competitors structure their titles and descriptions for categories where we underperform, use Apify

Use this data to validate or challenge the audit findings. For example, if Google Ads data shows cabinet pulls actually convert well despite low heuristic scores, that changes priorities.

---

## Phase 2: Resolve the prompt rigidity question

This is a critical architectural question that must be answered before implementing changes:

**Are our prompts too rigid?** By being overly prescriptive (exact character counts, strict zone rules, formulaic structure requirements), we may be constraining the LLM's ability to write genuinely compelling copy -- especially for:

1. **Unique/niche products** that don't fit generic templates (retractable garment rods, towel bars with hooks, double glass shelf with towel bar, etc.)
2. **Finish variants** where the injection system produces mail-merge-style output instead of natural language

Investigate this by:
- Reading the current prompt in `src/feedops/pipeline/prompts.py` and identifying every hard constraint vs. soft guidance
- Reading 10-15 actual variant JSON outputs across different product types and platforms in `dashboard_data/lifestyle-eval-candidate/variants/` -- compare the best outputs to the worst and identify what the prompt's rigidity cost us
- Consider whether loosening specific constraints while keeping others would let the LLM produce better output for unusual products while still maintaining quality for standard products
- Consider whether the scoring system's expectations are creating a feedback loop where the prompt must be rigid to score well, but rigidity produces worse content

The answer should NOT be "make everything flexible" or "keep everything rigid." Find the right balance: which constraints are genuinely necessary for feed compliance and which are suppressing creative quality?

---

## Phase 3: Plan implementation based on the validated findings

The previous audit identified these 10 findings. Use your data gathering and rigidity analysis to decide which to implement, modify, or skip:

### HIGH impact findings (implement these)

**Finding 1: Google/Bing CVR scoring ceiling at 8/10** (`scoring.py:527-646`)
- Description score maxes at ~8/10 for Google/Bing while Shopify can reach 10/10
- Creates false negatives where good Google content scores low
- Proposed fix: add 1-2 scoring dimensions to reach 10/10 theoretical max

**Finding 2: No product-type-specific prompt guidance** (`prompts.py`)
- All product types get identical prompt instructions
- Cabinet pulls need center-to-center + projection emphasis; freestanding items need stability + footprint; retractable hooks need load capacity + extension length
- Proposed fix: add product-type-specific guidance section to the prompt
- **Important**: validate this against the rigidity question -- adding MORE prompt constraints could make the problem worse. Consider whether giving the LLM product-type context (what matters to buyers) is different from giving it product-type templates (how to write it)

**Finding 3: Template-sounding finish injection** (`finish_injection.py:155-184, 410-468`)
- Every variant follows "{base} in {Finish Name}, which {functional_description}" pattern
- All 1,120+ variants (40 SKUs x 28 finishes) use near-identical grammatical structures
- Proposed fixes: (a) rotate sentence structures, (b) have LLM generate finish-forward versions for top finishes during candidate generation
- **Important**: this is the strongest evidence that rigidity is hurting output quality

### MEDIUM impact findings (implement selectively)

**Finding 4: Brand voice scoring rewards stuffing** (`scoring.py:725-744`)
- LLM can hit 10/10 by inserting "precision-crafted", "engineered", "solid brass", "lifetime warranty" everywhere
- No penalty for cliched openers ("Introducing...", "Discover...", "Elevate...")
- Proposed fix: add penalties for hollow marketing phrases, cap premium cues bonus

**Finding 5: Disproportionate soft-gate penalty** (`scoring.py:858-862`)
- Each miss costs -2 points via `weighted_misses * 2.0` multiplier
- Google/Bing have fewer gates than Shopify, making each miss proportionally harsher
- Cabinet pulls/knobs often miss dimension check due to non-standard formats
- Proposed fix: reduce multiplier to 1.5, add alternative dimension patterns

**Finding 6: Shopify size-specific inconsistency** (`finish_injection.py:561-564`)
- Size injection skipped for Shopify but LLM bakes in size references during generation
- Creates factually incorrect descriptions (says "30-inch" when variant is "18-inch")
- Proposed fix: make Shopify descriptions explicitly size-agnostic OR inject correct size

**Finding 7: Keyword plan not influencing selection** (`selection.py`, `optimize.py:162-167`)
- keyword_plan is passed to selection but doesn't affect heuristic score
- Proposed fix: add keyword_alignment bonus (0-2 points) to scoring composite

### LOW-MEDIUM impact findings (implement if time allows)

**Finding 8: Same length scoring for Google vs Bing** (`scoring.py:558-566`)
- Google truncates at ~500 chars in SERP; Bing shows more
- Both scored identically for 600-1000 char range
- Proposed fix: split scoring by platform

**Finding 9: Formulaic variant keyword generation** (`finish_injection.py:738-787`)
- Keywords use full finish names instead of color families and textures
- Misses high-volume terms like "polished chrome towel bar"
- Proposed fix: add color-family and texture-based keyword variants

**Finding 10: Post-normalization zone scoring mismatch** (`reporter.py:74-109`)
- Title zone scoring runs pre-normalization but export is post-normalization
- Proposed fix: normalize titles before scoring

---

## Constraints

- Do NOT suggest switching LLM providers
- Do NOT suggest UI/dashboard changes
- Do NOT focus on infrastructure/performance optimization
- Do NOT suggest changes that only increase the heuristic score without improving actual content quality -- the whole point is revenue, not score-gaming
- Every proposed change should be justified with data or concrete reasoning about shopper behavior

## Output format

Produce a plan with:
1. Data findings from MCP tools (what did the real performance data reveal?)
2. Rigidity analysis conclusion (what should be loosened, what should stay strict?)
3. Ordered implementation steps with:
   - What to change (specific files and functions)
   - Why (backed by data or shopper behavior reasoning)
   - How (concrete approach, not vague direction)
   - What to test (how to verify the change improved output quality)
