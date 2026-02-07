# Agent Team: Content Generation Pipeline - Simplified (6 Agents)

## Overview

**Goal:** Generate high-quality, authentic content for NEW SKU batches using a 2-stage pipeline: Storytelling + Content Court.

**Why This Works:**
- Stage 1 (Storytelling) prevents AI slop through persona narratives
- Stage 2 (Content Court) ensures quality through adversarial debate
- Simpler than 13-agent pipeline (easier to debug, faster execution)
- Can be expanded later with SEO Time Travel and Customer Reality stages

**Timeline:** 4-5 hours for 20 SKUs

**Use This When:**
- Generating content for NEW batches (not fixing existing content)
- You want higher quality than current Cloud Run pipeline
- You want to test agent teams on content generation before scaling

---

## Prerequisites

- product_catalog table populated (75,770 variants with evidence)
- variant_finish_sentences table populated (finish-specific copy)
- Gold standard examples exist (docs/gold-standard-examples.json)
- Supabase MCP, Context7, and Playwright MCP configured

---

## Copy/Paste This Prompt Into Claude Code

```
Create an agent team to generate high-quality content using a 2-stage pipeline: Storytelling Workshop + Content Court.

## GOAL
Generate authentic, high-quality content for 20 SKUs using persona-driven storytelling and adversarial quality validation.

## CONTEXT
Project: Allied-FeedOps (Allied Brass product content optimization)
Working directory: /Users/bobby/Documents/GitHub/Allied-FeedOps
Supabase project: qezuszwufortkiutlhym

This pipeline will REPLACE or SUPPLEMENT the current Cloud Run generation for selected SKUs.

## IMPORTANT CONSTRAINTS
- All agents have access to: Supabase MCP, Context7, Playwright MCP
- Write results to generated_content.candidate_content (existing review workflow handles approval)
- DO NOT publish directly - content goes through dashboard review first
- Use title format: Google/Bing = `{FINISH_NAME} [Product] [Specs] - [Collection Name] Collection - Allied Brass`

## INPUT
Provide a list of 20 master_skus to generate content for. Examples:
- 920D-6 (Dunnellon Towel Bar)
- 404-6 (Skyline Robe Hook)
- [... provide your SKU list ...]

## TEAM STRUCTURE (6 Agents in 2 Stages)

---

## STAGE 1: THE STORYTELLING WORKSHOP (3 Agents)

### Agent 1: Product Designer Persona
**Role:** Tell stories from the design perspective - materials, craftsmanship, engineering choices

**Tools:**
- mcp__supabase__execute_sql (query product_catalog for product details)
- mcp__plugin_context7_context7__query-docs (research materials, finishes)

**Workflow:**
1. For each SKU, query product evidence:
   ```sql
   SELECT
     master_sku,
     title as product_name,
     narrative_copy,
     bullets,
     dimensions,
     finish,
     category,
     collection
   FROM product_catalog
   WHERE master_sku = '{sku}'
   LIMIT 1;
   ```
2. Create designer story emphasizing:
   - Material choices (solid brass construction, not plated)
   - Engineering decisions (mounting bracket design, weight distribution)
   - Craftsmanship (precision machining, quality control)
   - Finish application process (hand-polished, corrosion resistance)
3. Write 100-150 word narrative per SKU
4. Store stories for Agent 4 (Synthesizer)

**Example Story:**
"For the Dunnellon 24-inch towel bar, I specified solid brass construction rather than zinc alloy. The mounting bracket design distributes weight across three anchor points, eliminating the wobble common in competitor products. We hand-polish each finish to achieve consistent luster that resists fingerprints and water spots..."

---

### Agent 2: Professional Contractor Persona
**Role:** Tell stories from installation and durability perspective - job site experiences, longevity, real-world performance

**Tools:**
- mcp__supabase__execute_sql (query product_catalog, search_queries for customer concerns)

**Workflow:**
1. For each SKU, query product evidence (same as Agent 1)
2. Query customer search patterns:
   ```sql
   SELECT query, search_volume
   FROM search_queries_by_master_sku
   WHERE master_sku = '{sku}'
   ORDER BY search_volume DESC
   LIMIT 10;
   ```
3. Create contractor story emphasizing:
   - Installation ease (standard mounting, clear instructions)
   - Durability observations (5-10 year lifespan in high-traffic bathrooms)
   - Common failure points in cheap alternatives (plastic anchors break, finishes peel)
   - Why professionals choose Allied Brass (callbacks, warranty claims)
4. Write 100-150 word narrative per SKU
5. Store stories for Agent 4

**Example Story:**
"I install 50 towel bars a month across residential and commercial properties. Allied Brass consistently outlasts budget brands - I've never had a callback for a fallen bar. The mounting hardware is commercial-grade, rated for 25+ pounds. Homeowners love the finish durability; I've seen 10-year-old bars that still look new..."

---

### Agent 3: Homeowner Persona
**Role:** Tell stories from daily use and aesthetic perspective - emotional benefits, design impact, lifestyle fit

**Tools:**
- mcp__supabase__execute_sql (query product_catalog for aesthetic details)

**Workflow:**
1. For each SKU, query product evidence (same as Agent 1)
2. Create homeowner story emphasizing:
   - Daily use patterns (morning routine, towel drying, bathroom flow)
   - Aesthetic impact (complements sink fixtures, matches cabinet hardware)
   - Emotional benefit (bathroom feels more organized, spa-like ambiance)
   - Decision factors (chose polished nickel to match faucet, 24-inch fits space)
3. Write 100-150 word narrative per SKU
4. Store stories for Agent 4

**Example Story:**
"Every morning, my husband drapes his towel on this bar after showering. We chose polished nickel to match our sink fixtures - the cohesive look makes our bathroom feel intentional rather than cobbled together. The 24-inch length is perfect for our narrow wall space between the shower and vanity..."

---

## STAGE 2: THE CONTENT COURT (3 Agents)

### Agent 4: The Content Synthesizer
**Role:** Read all 3 persona stories and synthesize into optimized title + description

**Tools:**
- mcp__supabase__execute_sql (write to generated_content)
- mcp__plugin_context7_context7__query-docs (SEO best practices, Google Shopping guidelines)

**Workflow:**
1. Receive 3 stories per SKU from Agents 1-3
2. Read current system prompt from dashboard/src/lib/regeneration/prompts.ts for format guidance
3. For each SKU, synthesize:
   a. **Title Structure:**
      - Template: `{FINISH_NAME} [Product] [Key Spec] - [Benefit from stories] - [Collection] Collection - Allied Brass`
      - Example: `{FINISH_NAME} 24-Inch Towel Bar - Commercial-Grade Mounting, Solid Brass Construction - Dunnellon Collection - Allied Brass`
   b. **Description (3 paragraphs):**
      - Para 1: Product overview + key benefit (from contractor story)
      - Para 2: Material/design details (from designer story)
      - Para 3: Use case + aesthetic fit (from homeowner story)
4. Write to candidate_content:
   ```sql
   UPDATE generated_content
   SET
     candidate_content = '{"title": "...", "description": "..."}',
     updated_at = NOW()
   WHERE master_sku = '{sku}' AND platform = 'google';
   ```
5. Send content to Agent 5 (Prosecutor) for review

**Deliverable:** Draft content ready for adversarial review

---

### Agent 5: The Prosecutor (AI Detection Specialist)
**Role:** Try to REJECT content by finding AI slop, generic phrasing, or policy violations

**Tools:**
- None needed (pure review logic)

**Workflow:**
1. Receive draft content from Agent 4
2. For each SKU, search for rejection reasons:
   a. **Generic AI phrases:**
      - "elevate your bathroom"
      - "transform your space"
      - "luxury experience"
      - "enhance your home"
      - "perfect addition to"
   b. **Weak verbs:**
      - "helps," "provides," "offers" (instead of "installs," "mounts," "resists")
   c. **Vague claims:**
      - "premium quality" without specifics
      - "hotel-style" without defining what that means
   d. **Missing authenticity:**
      - No specific details from persona stories
      - Sounds like template content
   e. **Google policy violations:**
      - Exaggerations or claims not backed by product data
      - Missing required info (dimensions, materials)
3. For each piece of content:
   - If 2+ major issues found: "REJECT - [list specific issues]"
   - If 1 major issue: "REVISE - [specific fix needed]"
   - If minor issues only: "APPROVE WITH NOTES - [suggestions]"
4. Send ruling to Agent 6 (Judge)

**Deliverable:** Rejection arguments with specific evidence

---

### Agent 6: The Judge
**Role:** Listen to Prosecutor's arguments and make final ruling

**Tools:**
- mcp__supabase__execute_sql (update content if revisions needed)

**Workflow:**
1. Receive draft content + Prosecutor's arguments
2. For each SKU, evaluate:
   a. **Are Prosecutor's concerns valid?**
      - Check if flagged phrases actually appear in content
      - Verify if specificity is truly missing
   b. **Is there authentic voice from stories?**
      - Look for specific details from designer/contractor/homeowner
      - Check if content feels grounded vs generic
   c. **Does content serve customer?**
      - Would this help someone decide to buy?
      - Does it answer common questions from search_queries?
3. Make ruling:
   - **APPROVE:** Content is authentic, specific, policy-compliant
   - **REVISE:** Send back to Agent 4 with specific feedback
   - **REJECT:** Start over with different story angle
4. For APPROVED content:
   ```sql
   UPDATE generated_content
   SET quality_score = {calculated_score}
   WHERE master_sku = '{sku}' AND platform = 'google';
   ```
5. For REVISE:
   - Agent 4 revises and resubmits
   - Max 2 revision rounds, then auto-approve with notes

**Deliverable:** Final approved content in generated_content.candidate_content

---

## COORDINATION & WORKFLOW

**Phase 1: Storytelling (Parallel - Agents 1-3)**
- All 3 personas work simultaneously
- Each creates 20 stories (one per SKU)
- Timeline: 60-90 minutes

**Phase 2: Synthesis (Sequential - Agent 4)**
- Waits for all 3 personas to finish
- Synthesizes 20 pieces of content
- Timeline: 60-90 minutes

**Phase 3: Court Review (Sequential - Agents 5-6)**
- Prosecutor reviews each piece
- Judge makes rulings
- Revisions if needed (Agent 4 reworks)
- Timeline: 60-90 minutes

**Total time:** 4-5 hours for 20 SKUs

---

## SUCCESS METRICS

**Immediate (Post-Generation):**
- ✅ 20 SKUs have new candidate_content
- ✅ All content passed Content Court (approved by Judge)
- ✅ Zero generic AI phrases in final content
- ✅ Quality scores ≥ 85/100

**30-Day (Post-Publish):**
- 🎯 CTR ≥ 2.0% (platform average)
- 📊 Compare to previous batch generated by Cloud Run pipeline
- 💡 If pipeline content performs better → scale this approach

---

## INTEGRATION WITH EXISTING WORKFLOW

**After Agent Team Completes:**

1. **Dashboard Review** (Manual)
   - Visit: https://allied-feed-ops.vercel.app/review
   - 20 SKUs will show updated candidate_content
   - Review and approve as normal

2. **Publishing** (Existing Workflow)
   - Use existing batch publish flow
   - Publishes approved_content to Google Sheets

3. **Performance Tracking** (Automatic)
   - performance_snapshots table tracks CTR automatically
   - Compare to previous batches after 30 days

---

## EXPANSION OPTIONS (Future)

If this 6-agent pipeline works well, consider adding:

**Stage 3: SEO Time Travelers (4 agents)**
- Validate content against future algorithm predictions
- See: 03-content-pipeline-13-agent.md

**Stage 4: Customer Reality Check (3 agents)**
- Test content against angry customer scenarios
- See: 03-content-pipeline-13-agent.md

But start with 6 agents, prove it works, then expand.

---

## TROUBLESHOOTING

**If stories feel generic:**
- Agents should query product_catalog for specific details
- Push for NUMBERS (24-inch, 25-pound capacity, 10-year lifespan)
- Avoid "luxury" and "premium" - use specific materials (solid brass, not plated)

**If Prosecutor rejects everything:**
- Check if standards are too strict
- Verify stories have enough specificity
- May need to adjust rejection criteria

**If content still has AI slop:**
- Prosecutor isn't catching it - strengthen detection rules
- Agent 4 may be defaulting to templates - emphasize story grounding

```

---

## Next Steps

1. Test on 5-10 SKUs first (smaller batch for debugging)
2. Compare quality scores to Cloud Run pipeline
3. If successful, scale to full 20-50 SKU batches
4. Consider building this into dashboard (Option 2: job queue)
