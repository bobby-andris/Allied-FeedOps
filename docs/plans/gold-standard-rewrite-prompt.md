# Gold Standard Rewrite — Agent Team Prompt

**Purpose**: Use a coordinated team of agents to research, create, validate, and deploy new gold standard examples that replace the legacy Supabase gold standards. Also revise the google-shopping-content skill and shopping_intelligence.yaml to include full-length gold standard descriptions.

**Paste this entire prompt into a new Claude Code session.**

---

## The Prompt

```
I need to completely overhaul our gold standard product content examples. The current gold standards
in Supabase were written before we developed our quality skills and rubric — they consistently
score 35-48/100 on our new 10-criterion rubric but scored 80-98 on the old compliance-based rubric.
Every iteration of prompt generation using these old gold standards has produced generic, template-
like output. We need to replace them with genuinely excellent examples.

This is a multi-agent team project. Create a team and run these agents:

---

### Agent 1: "data-researcher" (general-purpose)
**Task**: Query our actual product and performance data to inform gold standard creation.

Do this research:
1. Use ToolSearch to load `mcp__plugin_supabase_supabase__execute_sql`, then run these queries:

   a. Get the current gold standards from Supabase:
      ```sql
      SELECT id, template_type, template_data
      FROM prompt_templates
      WHERE template_type = 'gold_standard_examples'
      ```

   b. Get product details for 15 candidate SKUs across diverse categories:
      ```sql
      SELECT DISTINCT ON (category) master_sku, title, category, collection,
             material, dimensions, features, product_type, description
      FROM product_catalog
      WHERE master_sku IS NOT NULL AND category IS NOT NULL
      ORDER BY category, master_sku
      LIMIT 15
      ```

   c. Get the TOP CONVERTED search terms (actual purchases, not just impressions):
      ```sql
      SELECT search_term, SUM(conversions) as total_conversions,
             SUM(impressions) as total_impressions,
             ROUND(SUM(clicks)::numeric / NULLIF(SUM(impressions), 0) * 100, 2) as ctr_pct
      FROM search_queries
      WHERE conversions > 0
      GROUP BY search_term
      ORDER BY total_conversions DESC
      LIMIT 50
      ```

   d. Get vocabulary patterns (what shoppers actually search):
      ```sql
      SELECT search_term, SUM(impressions) as total_impressions
      FROM search_queries
      GROUP BY search_term
      ORDER BY total_impressions DESC
      LIMIT 100
      ```

2. Save all results to `/tmp/gold-standard-research-data.md` with clear section headers.

3. Write a brief analysis: Which categories need gold standards most? Which SKUs have the
   richest product data to work with? Which search terms represent genuine demand?

---

### Agent 2: "competitor-researcher" (general-purpose)
**Task**: Research what top-performing competitors are doing in Google Shopping.

Do this research:
1. Use WebSearch and WebFetch to research competitor listings:

   a. Search for "polished nickel towel bar" on Google Shopping — what do the top 5 listings
      look like? What are their title structures? How long are their descriptions?

   b. Search for "solid brass grab bar ADA" — same analysis.

   c. Search for "unlacquered brass toilet paper holder" — same analysis.

   d. Search for "wall mounted soap dispenser brass" — same analysis.

   e. For each top listing found, note:
      - Title structure and length
      - Description length (estimate character count)
      - What differentiators they lead with
      - How they handle finish/material
      - What makes their listing clickable

2. Also search for "Google Shopping product description best practices 2026" and
   "Google Merchant Center description optimization length" to find any updated guidance
   on optimal description length.

3. Search for "Google Shopping listing examples high CTR ecommerce" to find case studies
   of successful Shopping optimization.

4. Save all findings to `/tmp/gold-standard-competitor-research.md`.

---

### Agent 3: "length-researcher" (general-purpose)
**Task**: Research evidence-based best practices for product content length across platforms.

Do this research:
1. WebSearch for:
   - "Google Shopping description optimal length 2026"
   - "Google Merchant Center product description character limit"
   - "ecommerce product description length conversion rate study"
   - "product description length SEO impact research"
   - "Amazon product description length best practices" (for comparison)
   - "Bing Shopping product description character limit"
   - "Shopify product description optimal length conversion"

2. For each finding, note:
   - Source (URL, publication)
   - What length they recommend and why
   - Whether they distinguish between "displayed length" vs "indexed length"
   - Any A/B test data or conversion rate studies

3. Specifically verify: Google Merchant Center says 5,000 chars max. But what do top performers
   actually use? Is there a sweet spot? Does Google's Shopping Graph actually index beyond the
   visible preview? Find evidence.

4. Research Bing Merchant Center's actual title and description character limits from official
   Microsoft documentation.

5. Research Shopify product description best practices — what length converts best for DTC
   brands in the home goods / luxury accessories space?

6. Save all findings to `/tmp/gold-standard-length-research.md` with citations.

---

### Agent 4: "product-selector" (general-purpose)
**Task**: Choose which 10 products should be our gold standard examples.

Wait for Agent 1 (data-researcher) to complete, then:

1. Read `/tmp/gold-standard-research-data.md` for the product catalog data.

2. Select 10 SKUs that:
   - Cover at least 8 different product categories
   - Include at least 2 high-impression-share-loss categories (retractable hooks, valet rods)
   - Include at least 1 simple product (robe hook, cabinet knob)
   - Include at least 1 complex product (grab bar with ADA, mirror with magnification)
   - Have rich product data in the catalog (dimensions, features, collection info)
   - Represent SKUs where optimized content would have the most impact

3. For each selected SKU, prepare a "content brief" that includes:
   - All available product data from the catalog
   - Relevant converted search terms from the research
   - Vocabulary patterns shoppers use for this category
   - Key differentiators vs competitors for this product type
   - The buyer persona and their primary concern

4. Save the 10 product briefs to `/tmp/gold-standard-product-briefs.md`.

---

### Agent 5: "content-writer" (general-purpose)
**Task**: Write the actual gold standard content using ALL our skills.

Wait for Agents 2 (competitor-researcher), 3 (length-researcher), and 4 (product-selector)
to complete, then:

1. Read these files:
   - `/tmp/gold-standard-product-briefs.md` (the 10 selected products)
   - `/tmp/gold-standard-competitor-research.md` (what competitors do)
   - `/tmp/gold-standard-length-research.md` (optimal lengths)

2. Read ALL of these skills by invoking the Skill tool for each:
   - `google-shopping-content` — title/description architecture
   - `product-storytelling` — narrative patterns, emotional hooks
   - `allied-brass-brand-expert` — brand voice, verified truths
   - `finish-expertise` — finish language for {FINISH_SENTENCE} integration
   - `collection-storytelling` — collection DNA for cross-sell
   - `quality-evaluation` — the 10-criterion rubric (every example must score 85+)

3. For each of the 10 products, generate:
   - `google_title` (60-150 chars, using title architecture from google-shopping-content)
   - `google_short_title` (65-70 chars max)
   - `google_description` (USE THE FULL CHARACTER BUDGET based on length research findings —
     NOT 200-400 char fragments. Include: opening hook, material differentiation,
     {FINISH_SENTENCE} integration, collection coordination, extended keyword coverage,
     and customer scenario. Target the optimal length discovered by the length-researcher.)
   - `why_excellent` annotation explaining what makes this a gold standard

4. Apply the quality-evaluation rubric to EACH description. Score all 10 criteria. If any
   description scores below 85, REWRITE IT until it passes. Show the score breakdown.

5. Save all 10 gold standards with scores to `/tmp/gold-standard-final-content.md`.

---

### Agent 6: "updater" (general-purpose)
**Task**: Update Supabase, the skill files, and the config YAML.

Wait for Agent 5 (content-writer) to complete, then:

1. Read `/tmp/gold-standard-final-content.md` (the 10 scored gold standards).
   Read `/tmp/gold-standard-length-research.md` (for updating character limit guidance).

2. **Update Supabase gold standards**: Use ToolSearch to load the Supabase MCP tools, then:
   - Read the current gold_standard_examples row to understand the JSON structure
   - Format the 10 new gold standards into the same JSON structure
   - UPDATE the prompt_templates row with the new gold standards
   - Verify the update by reading the row back

3. **Update the google-shopping-content skill** at
   `.claude/skills/google-shopping-content/SKILL.md`:
   - Replace the "Gold Standard Examples" section with the new 10 examples
   - Update the "Character Budget" section with findings from the length research
   - Update descriptions in the examples to be FULL LENGTH (not 200-400 char fragments)
   - Ensure the skill's guidance matches the actual gold standard quality

4. **Update shopping_intelligence.yaml** at `src/feedops/config/shopping_intelligence.yaml`:
   - Update the description_structure rule with any new length findings
   - Verify the character guidance matches the research findings

5. **Update quality_rubric.yaml** at `src/feedops/config/quality_rubric.yaml`:
   - If the length research changes our platform compliance guidance, update it

6. Commit all changes:
   ```
   git add .claude/skills/google-shopping-content/
   git add src/feedops/config/shopping_intelligence.yaml
   git add src/feedops/config/quality_rubric.yaml
   git commit -m "feat: rewrite gold standards with research-backed content + update skill and configs

   - 10 new gold standards scoring 85+ on quality rubric (replacing legacy 35-48 scoring examples)
   - Full-length descriptions based on length research findings
   - Updated character budget guidance in skill and config
   - Competitor-informed title and description strategies

   Co-Authored-By: Claude Opus 4.6 <noreply@anthropic.com>"
   ```

7. Push the Supabase update confirmation and file changes summary to the team lead.

---

## Coordination

Agents 1, 2, and 3 can run IN PARALLEL (they're independent research tasks).
Agent 4 waits for Agent 1 only.
Agent 5 waits for Agents 2, 3, and 4.
Agent 6 waits for Agent 5.

## Key Rules for ALL Agents

- Do NOT use current impression/CTR data as optimization targets. Current data reflects
  unoptimized listings. Use CONVERTED search terms (actual purchases) as demand signals.
  Use vocabulary patterns (what words shoppers use). Use relative patterns (finish-specific
  terms outperform generic). Do NOT use impression volumes as ceilings.
- Do NOT reference or build on the old Supabase gold standards. They are being REPLACED.
- Every gold standard description must score 85+ on the quality-evaluation 10-criterion rubric.
- Gold standard descriptions must demonstrate the FULL recommended character budget.
- No cross-platform contamination — these are Google Shopping gold standards only.
- Reference docs/research/gpt52-best-practices.md for GPT-5.2 prompt considerations.
```
