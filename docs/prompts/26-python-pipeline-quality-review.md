# Python Content Generation Pipeline - Deep Quality Review

## Goal

Allied Brass sells bathroom hardware (towel bars, soap dishes, grab bars, glass shelves, robe hooks, paper towel holders, mirrors) at the $30-$200 mid-market price point on Shopify. We generate optimized product titles and descriptions for Google Shopping, Bing Shopping, and Shopify product pages using a Python Cloud Run pipeline. **The ultimate goal is increasing revenue and sales** by improving click-through rates from Shopping ads and conversion rates on product pages.

The Python pipeline (`src/feedops/`) is now the **single source of truth** for all content generation — the dashboard regeneration button proxies directly to it. Any improvements here immediately impact all generated content.

## Your Mission

Deeply review and investigate the Python generation pipeline to identify improvements that will increase output quality, with the specific goal of generating content that **maximizes clicks from Google/Bing Shopping and maximizes conversions on Shopify**.

## Context & Architecture

### Pipeline Files to Review

**Core generation flow** (review these thoroughly):
- `src/feedops/api/main.py` — FastAPI endpoints (`/regenerate`, `/optimize-sku`, `/batch-optimize`, `/hybrid-generate`)
- `src/feedops/pipeline/prompts.py` — SYSTEM_PROMPT and CANDIDATE_SCHEMA (the most impactful file)
- `src/feedops/pipeline/evidence.py` — Evidence table builder (product data → LLM context)
- `src/feedops/pipeline/enrichment.py` — On-the-fly enrichment (design style, competitive edge, features)
- `src/feedops/pipeline/generation.py` — LLM call orchestration
- `src/feedops/pipeline/finish_injection.py` — Finish sentence generation and injection

**Prompt loading & templates**:
- `src/feedops/api/prompt_loader.py` — Loads system prompt (Supabase `prompt_templates` table or fallback)
- The Supabase `prompt_templates` table stores gold standard examples per category

**Supporting infrastructure**:
- `src/feedops/pipeline/scoring.py` — Content quality scoring
- `src/feedops/pipeline/validation.py` — Content validation rules
- `src/feedops/integrations/google_ads_search_terms.py` — Search query data integration

### How Content is Generated

1. **Evidence table** is built from `product_catalog` (75,770 variants) — includes dimensions, materials, bullets, collection, category, search queries, competitive edge
2. **System prompt** provides writing guidelines (formatting, tone, platform rules)
3. **User prompt** combines platform context + evidence table + any feedback
4. **LLM generates** title and/or description
5. **Finish injection** adds variant-specific finish sentences for Google/Bing descriptions
6. **Validation** checks content against hard rules (length, banned words, format)

### What We Know About Quality

Current quality scores average 75-80/100. Testing revealed these specific issues:
- Some descriptions still contain "designer finishes" language even though the evidence builder was fixed — check if the Python enrichment or prompts still inject this
- Competitive positioning ("crafted from brass not zinc alloy") appears formulaically in many descriptions instead of naturally
- Bing descriptions sometimes have keyword stuffing (slash-separated alternatives)
- Google titles don't always front-load the most important search terms in the first 70 characters
- Shopify descriptions sometimes include finish-specific language or "Allied Brass" when they shouldn't

### Revenue-Driving Priorities

**What actually drives clicks on Google Shopping:**
1. Title keyword relevance (does the title match what the shopper searched?)
2. Title specificity (dimensions, material, key feature visible in truncated title)
3. Description that reinforces the click decision (confirms this is the right product)

**What actually drives Shopify conversions:**
1. Clear product identity (what is this, what does it look like)
2. Key specs upfront (dimensions, material, mounting type)
3. Confidence builders (warranty, quality signals, what's included)
4. Finish variety as a benefit (28 options to match your decor)

## What to Investigate

### 1. System Prompt Effectiveness (`prompts.py`)
- Is the prompt actually producing the best possible output for revenue?
- Are the P0/P1/P2 priority levels working or causing confusion?
- Is the "balanced approach" (quality-first vs pain-point-first) leading to better content than a simpler strategy would?
- Are there missing instructions that would help (e.g., CTR-optimizing title patterns)?
- Compare our prompt against best practices from Google Shopping optimization research

### 2. Evidence Table Completeness (`evidence.py`, `enrichment.py`)
- Are we giving the LLM everything it needs to write great content?
- Is search query data being used effectively?
- Are we missing any product attributes that would improve content?
- Is the competitive_edge field still causing formulaic output?
- Is the evidence table format (markdown table) optimal for LLM comprehension?

### 3. Search Query Integration
- How are actual Google Ads search terms being integrated into the evidence table?
- Are we matching the language customers actually use?
- Could we better leverage search volume data to prioritize which terms appear in titles?

### 4. Platform-Specific Optimization
- **Google**: Are titles optimally structured for Shopping ads? First 70 chars are critical (mobile truncation)
- **Bing**: Is synonym integration working naturally or causing stuffing?
- **Shopify**: Are descriptions converting browsers to buyers? Is HTML formatting effective?

### 5. Finish Sentence Quality (`finish_injection.py`)
- Are finish sentences product-specific or generic?
- Is the stripping of "designer finishes" boilerplate working?
- Could finish sentences be more compelling for conversion?

### 6. Content Scoring & Validation
- Does the scoring formula correlate with actual performance (CTR/CVR)?
- Are validation rules catching real problems or being too strict/lenient?

### 7. Gold Standard Examples (`prompt_templates` table)
- Query the table via Supabase MCP: `SELECT * FROM prompt_templates LIMIT 10`
- Are gold standard examples high quality? Do they match what we want the LLM to produce?
- Should we add more examples for underperforming categories?

### 8. Model & Parameters
- What model is being used? (Check `generation.py`)
- Are temperature/max_tokens optimal?
- Would structured output (JSON mode) improve consistency?

## How to Approach This

1. **Read all pipeline files** listed above thoroughly
2. **Query the database** for sample generated content and gold standard examples
3. **Compare generated vs ideal** — pick 3-5 SKUs and evaluate what the pipeline produces vs what would be optimal
4. **Research best practices** — use web search to find current Google Shopping title/description optimization research
5. **Identify the highest-impact changes** — rank improvements by expected revenue impact
6. **Write a concrete plan** with specific code changes, ordered by impact

## Output

Produce a detailed plan document at `docs/plans/YYYY-MM-DD-pipeline-quality-improvements.md` with:
1. **Current state assessment** — what's working, what's not
2. **Ranked improvement list** — ordered by expected revenue impact
3. **Specific code changes** — file, line numbers, before/after
4. **Sample outputs** — show before/after for 3-5 SKUs
5. **Measurement plan** — how to verify improvements (A/B testing approach, metrics to track)

## Important Notes

- Read `CLAUDE.md` first for full project context
- Read `docs/database/SCHEMA.md` before writing any Supabase queries
- Use `mcp__supabase__execute_sql` to query real data
- Use web search to research current Google Shopping optimization best practices
- The Python pipeline is the ONLY content generation path — improvements here affect everything
- Focus on changes that will measurably increase CTR and conversion, not cosmetic improvements
