# Agent Team: Content Generation Pipeline - Full (13 Agents)

## Overview

**Goal:** Generate the highest-quality, future-proof, return-resistant content using a 4-stage pipeline: Storytelling + SEO Time Travel + Content Court + Customer Reality.

**Why This Works:**
- Stage 1 (Storytelling) creates authentic narratives
- Stage 2 (SEO Time Travel) ensures future-proof optimization
- Stage 3 (Content Court) validates quality through adversarial debate
- Stage 4 (Customer Reality) prevents returns and negative reviews

**Timeline:** 6-8 hours for 20 SKUs

**Use This When:**
- You've validated the 6-agent pipeline works
- You want maximum quality for high-value SKUs
- You're willing to invest more time for better outcomes
- You want to future-proof against algorithm changes

---

## Prerequisites

- 6-agent pipeline tested successfully
- All MCP servers configured (Supabase, Google Ads, Apify, Context7, Playwright)
- Comfortable with longer agent team sessions
- Performance tracking in place (to measure ROI of extra complexity)

---

## Copy/Paste This Prompt Into Claude Code

```
Create an agent team to generate the highest-quality content using a 4-stage pipeline: Storytelling + SEO Time Travel + Content Court + Customer Reality.

## GOAL
Generate authentic, future-proof, return-resistant content for 20 SKUs using persona storytelling, algorithm prediction, adversarial validation, and customer scrutiny.

## CONTEXT
Project: Allied-FeedOps (Allied Brass product content optimization)
Working directory: /Users/bobby/Documents/GitHub/Allied-FeedOps
Supabase project: qezuszwufortkiutlhym
Google Ads customer ID: 6253381786

This is the FULL pipeline - use for high-value SKUs or when you want maximum quality.

## IMPORTANT CONSTRAINTS
- All agents have access to: Supabase MCP, Google Ads MCP, Context7, Playwright MCP
- Write results to generated_content.candidate_content (existing review workflow handles approval)
- DO NOT publish directly - content goes through dashboard review first
- Use title format: Google/Bing = `{FINISH_NAME} [Product] [Specs] - [Collection Name] Collection - Allied Brass`

## INPUT
Provide a list of 20 master_skus to generate content for.

## TEAM STRUCTURE (13 Agents in 4 Stages)

---

## STAGE 1: THE STORYTELLING WORKSHOP (3 Agents)

### Agent 1: Product Designer Persona
[Same as 6-agent pipeline - see 02-content-pipeline-6-agent.md]

### Agent 2: Professional Contractor Persona
[Same as 6-agent pipeline - see 02-content-pipeline-6-agent.md]

### Agent 3: Homeowner Persona
[Same as 6-agent pipeline - see 02-content-pipeline-6-agent.md]

**Output from Stage 1:** 3 authentic stories per SKU (60 stories total for 20 SKUs)

---

## STAGE 2: THE SEO TIME TRAVELERS (4 Agents)

**Purpose:** Validate content will rank well NOW and in the FUTURE (2027+)

### Agent 4: The Algorithm Historian
**Role:** Analyze past Google algorithm updates to identify ranking trends

**Tools:**
- mcp__plugin_context7_context7__query-docs (research algorithm updates)
- WebSearch (if needed for Google update history)

**Workflow:**
1. Research major Google algorithm updates 2018-2025:
   - Panda (thin content penalties)
   - Penguin (link spam)
   - Helpful Content Update (Nov 2022 - reward first-hand experience)
   - EEAT emphasis (Experience, Expertise, Authoritativeness, Trust)
   - Core updates (quality focus, anti-spam)
2. Identify meta-trends:
   - Google increasingly rewards first-hand experience
   - Generic content gets penalized ("me too" content)
   - AI detection becoming more sophisticated
   - Product pages need specific, verifiable details
3. Extract ranking factors that have STRENGTHENED over time:
   - Specificity (exact dimensions, materials, specs)
   - Authenticity markers (contractor stories, real use cases)
   - Visual proof (images, videos showing product)
   - Review integration (customer testimonials)
4. Share findings with Agent 6 (Futurist)

**Deliverable:** Historical trend analysis showing what Google increasingly rewards

---

### Agent 5: The AI Researcher
**Role:** Study Google's AI detection capabilities and predict future content requirements

**Tools:**
- mcp__plugin_context7_context7__query-docs (research Google AI initiatives)
- WebSearch (search for Google patents, research papers)

**Workflow:**
1. Research Google's AI initiatives:
   - Search Generative Experience (SGE) rollout
   - Gemini integration into Search
   - Google's stance on AI-generated content
   - Content authenticity initiatives
2. Read Google's official guidance:
   - "Creating helpful content" documentation
   - AI-generated content policies
   - Merchant Center AI disclosure requirements
3. Study detection techniques:
   - What signals indicate AI-generated content?
   - How does Google validate authenticity?
   - What makes content "demonstrably human"?
4. Predict future requirements (2026-2027):
   - Hypothesis: "Google will require proof of first-hand product experience"
   - Hypothesis: "Generic benefit claims will be penalized"
   - Hypothesis: "AI disclosure requirements will expand"
5. Share predictions with Agent 6 (Futurist)

**Deliverable:** AI detection insights + future requirement predictions

---

### Agent 6: The Futurist
**Role:** Combine Historian + AI Researcher insights to create future-proof content strategy

**Tools:**
- None (synthesis role)

**Workflow:**
1. Receive inputs from Agents 4 & 5:
   - Historical trends (what Google has increasingly rewarded)
   - AI detection insights (what will be penalized)
2. Create future-proof content checklist:
   - ✅ Must include first-hand expertise signals (contractor story)
   - ✅ Must avoid generic AI phrases (no "elevate," "transform")
   - ✅ Must include specific, verifiable details (dimensions, materials)
   - ✅ Must demonstrate authentic knowledge (installation tips, durability insights)
   - ✅ Must serve customer intent (answer search queries)
3. Score persona stories from Stage 1:
   - Current SEO compatibility (does it rank well today?)
   - Future-proof score (will it survive 2027 algorithm changes?)
   - Risk areas (what might get penalized?)
4. Provide guidance to Agent 7 (Synthesizer):
   - "Emphasize contractor installation experience - signals expertise"
   - "Include specific 24-inch dimension - verifiable detail"
   - "Avoid 'luxury' claim - generic and unverifiable"
5. Share future-proof checklist with Agent 7

**Deliverable:** Future-proof content strategy + scoring of Stage 1 stories

---

### Agent 7: The Content Synthesizer (with SEO Guidance)
**Role:** Create optimized title + description using stories + future-proof guidance

**Tools:**
- mcp__supabase__execute_sql (write to generated_content)
- mcp__google-ads-mcp__search (validate keyword strategy)

**Workflow:**
1. Receive inputs:
   - 3 persona stories per SKU (from Stage 1)
   - Future-proof checklist (from Agent 6)
   - Historical ranking factors (from Agent 4)
   - AI detection insights (from Agent 5)
2. Query search volume data:
   ```sql
   SELECT query, search_volume, competition
   FROM keyword_metrics
   WHERE query LIKE '%{product_category}%'
   ORDER BY search_volume DESC
   LIMIT 20;
   ```
3. For each SKU, synthesize:
   a. **Title Structure:**
      - Include high-volume keywords from keyword_metrics
      - Follow future-proof checklist (specific details, no generic phrases)
      - Template: `{FINISH_NAME} [Product + Keyword] [Specific Benefit] - [Collection] Collection - Allied Brass`
      - Example: `{FINISH_NAME} 24-Inch Towel Bar - Commercial-Grade Mounting for High-Traffic Bathrooms - Dunnellon Collection - Allied Brass`
   b. **Description (3 paragraphs):**
      - Para 1: Open with contractor expertise signal (future-proof)
      - Para 2: Specific materials/engineering details (verifiable)
      - Para 3: Real use case from homeowner (authentic)
4. Validate against checklist:
   - ✅ First-hand expertise? (contractor story referenced)
   - ✅ Specific details? (24-inch, solid brass, commercial-grade)
   - ✅ No AI slop? (no "elevate," "transform," "luxury experience")
   - ✅ Serves search intent? (high-volume keywords included)
5. Write to candidate_content:
   ```sql
   UPDATE generated_content
   SET
     candidate_content = '{"title": "...", "description": "..."}',
     updated_at = NOW()
   WHERE master_sku = '{sku}' AND platform = 'google';
   ```
6. Send content to Stage 3 (Content Court)

**Deliverable:** Future-proof content ready for adversarial review

---

## STAGE 3: THE CONTENT COURT (3 Agents)

### Agent 8: The Prosecutor
[Same as 6-agent pipeline - see 02-content-pipeline-6-agent.md]

**Additional check:** Validate against future-proof checklist from Agent 6

### Agent 9: The Defense Attorney
**Role:** Argue why content should be APPROVED

**Tools:**
- None (pure argument logic)

**Workflow:**
1. Receive draft content + Prosecutor's arguments
2. Build defense case:
   a. **Counter generic phrase claims:**
      - Show where specific details override generic intro
      - Point to contractor story grounding
      - Highlight verifiable specs (24-inch, solid brass)
   b. **Demonstrate authenticity:**
      - Reference persona stories as evidence source
      - Show first-hand expertise signals
      - Point to specific use case details
   c. **Prove customer value:**
      - Content answers high-volume search queries
      - Helps customer make informed decision
      - Specific benefits vs vague claims
3. For each Prosecutor objection:
   - ACCEPT if valid (generic phrase with no specificity)
   - CHALLENGE if invalid (specific detail mischaracterized as generic)
   - NEGOTIATE if borderline (suggest minor revision)
4. Present defense argument to Judge

**Deliverable:** Defense arguments with evidence from stories

---

### Agent 10: The Judge
[Same as 6-agent pipeline - see 02-content-pipeline-6-agent.md]

**Additional consideration:** Weight future-proof score from Agent 6

**Output from Stage 3:** Court-approved content with debate transcript

---

## STAGE 4: THE CUSTOMER REALITY CHECK (3 Agents)

**Purpose:** Test if content survives real-world customer scrutiny (prevents returns/bad reviews)

### Agent 11: The Returns Desk Manager
**Role:** Identify overpromises that lead to returns

**Tools:**
- mcp__supabase__execute_sql (query product_catalog for actual specs)

**Workflow:**
1. Receive court-approved content from Stage 3
2. For each SKU:
   a. Query actual product specs:
      ```sql
      SELECT dimensions, materials, weight_capacity, finish_type
      FROM product_catalog
      WHERE master_sku = '{sku}';
      ```
   b. Read title + description
   c. Identify expectation mismatches:
      - Does "commercial-grade" match actual specs?
      - Does "heavy-duty" match weight capacity?
      - Does "rust-proof" match material (brass oxidizes, not rust but tarnish)?
      - Does "hotel quality" set unrealistic expectations?
   d. For each potential mismatch:
      - "RETURN RISK: Title says 'commercial-grade' but no weight capacity spec listed"
      - "RETURN RISK: Description implies 'lifetime durability' but finish requires maintenance"
   e. Calculate return risk score: HIGH / MEDIUM / LOW
3. Send concerns to Agent 13 (Product Manager)

**Deliverable:** Return risk assessment with specific claims to revise

---

### Agent 12: The Amazon 1-Star Reviewer
**Role:** Write negative reviews for any misleading claims

**Tools:**
- None (pure critical review)

**Workflow:**
1. Receive court-approved content from Stage 3
2. For each SKU, role-play as disappointed customer:
   a. Read title + description
   b. Imagine receiving product
   c. Write 1-star review for ANY:
      - Exaggerations ("premium" but feels basic)
      - Misleading claims ("rust-proof" but finish tarnished)
      - Missing context ("easy installation" but required tools not mentioned)
      - Unmet expectations ("hotel quality" but doesn't match Ritz-Carlton)
3. Example reviews:
   - "Title said 'commercial-grade' but this feels like home-depot quality. Misleading!"
   - "Description said 'lifetime durability' but finish started tarnishing after 6 months."
   - "'Easy installation' they said. Took me 2 hours and I had to buy extra anchors!"
4. Send negative reviews to Agent 13

**Deliverable:** Potential negative reviews highlighting misleading claims

---

### Agent 13: The Product Manager (Defender + Reviser)
**Role:** Receive negative feedback and revise content to be defensible

**Tools:**
- mcp__supabase__execute_sql (update generated_content if revisions needed)

**Workflow:**
1. Receive inputs:
   - Return risk concerns (from Agent 11)
   - Negative reviews (from Agent 12)
   - Original content (from Stage 3)
2. For each concern:
   a. **Assess validity:**
      - Is "commercial-grade" defensible? (check actual product specs)
      - Is "rust-proof" accurate? (brass doesn't rust but can tarnish - revise)
      - Is "easy installation" fair? (most customers can do it, but clarify tools needed)
   b. **Decide action:**
      - DEFEND: Claim is accurate and defensible
      - REVISE: Change claim to be more specific/honest
      - REMOVE: Delete unsupported claim entirely
3. Make revisions:
   - Change "rust-proof" → "corrosion-resistant brass (natural tarnishing over time)"
   - Change "premium quality" → "solid brass construction (not plated zinc alloy)"
   - Add context: "easy installation (basic tools required: drill, level, screwdriver)"
4. Re-submit to Returns Manager + Reviewer:
   - "Can you still write a 1-star review for this revised version?"
   - If NO: Content is defensible, APPROVE
   - If YES: Make further revisions, max 2 rounds
5. Write final approved content:
   ```sql
   UPDATE generated_content
   SET
     candidate_content = '{final_content}',
     quality_score = {calculated_score}
   WHERE master_sku = '{sku}' AND platform = 'google';
   ```

**Deliverable:** Return-resistant, honest, defensible content in generated_content.candidate_content

---

## COORDINATION & WORKFLOW

**Phase 1: Storytelling (Parallel - 60-90 min)**
- Agents 1-3 work simultaneously

**Phase 2: SEO Time Travel (Parallel + Sequential - 90-120 min)**
- Agents 4-5 research in parallel
- Agent 6 synthesizes findings
- Agent 7 creates content with SEO guidance

**Phase 3: Content Court (Sequential - 60-90 min)**
- Agents 8-10 debate each piece

**Phase 4: Customer Reality (Sequential - 60-90 min)**
- Agents 11-12 identify issues
- Agent 13 revises until defensible

**Total time:** 6-8 hours for 20 SKUs

---

## SUCCESS METRICS

**Immediate (Post-Generation):**
- ✅ 20 SKUs with final candidate_content
- ✅ All content passed Content Court
- ✅ All content passed Customer Reality Check
- ✅ Zero generic AI phrases
- ✅ Zero misleading claims
- ✅ Future-proof score ≥ 90/100
- ✅ Quality scores ≥ 90/100

**30-Day (Post-Publish):**
- 🎯 CTR ≥ 2.5% (higher than 6-agent pipeline)
- 📉 Return rate ≤ baseline (honest descriptions prevent returns)
- ⭐ Review ratings maintained (no "misleading description" complaints)
- 🔮 Content survives future algorithm updates (validate in 12 months)

**ROI Calculation:**
- Compare 13-agent pipeline vs 6-agent pipeline vs Cloud Run baseline
- Is the extra 2-3 hours of agent time worth the quality improvement?
- If CTR improves 2.0% → 2.5% on high-volume SKUs = significant revenue

---

## INTEGRATION WITH EXISTING WORKFLOW

**After Agent Team Completes:**

1. **Dashboard Review** (Manual)
   - Visit: https://allied-feed-ops.vercel.app/review
   - 20 SKUs will show updated candidate_content
   - Content has been through 4 stages of validation
   - Review and approve as normal

2. **Publishing** (Existing Workflow)
   - Use existing batch publish flow
   - Publishes approved_content to Google Sheets

3. **Performance Tracking** (Automatic)
   - performance_snapshots table tracks CTR automatically
   - Compare to 6-agent pipeline and Cloud Run baseline after 30 days

---

## WHEN TO USE 13-AGENT VS 6-AGENT

**Use 13-Agent Pipeline When:**
- High-value SKUs (top performers, high margin)
- New product launch (want maximum quality)
- Previous content underperformed (need stronger content)
- Willing to invest 6-8 hours for best possible output

**Use 6-Agent Pipeline When:**
- Standard SKU batches (routine content generation)
- Time-constrained (need faster turnaround)
- Testing agent team approach for first time
- ROI of extra 2 hours not justified by volume

**Use Cloud Run Pipeline When:**
- Bulk generation (100+ SKUs at once)
- Time-critical (need content today)
- Agent teams not available

---

## TROUBLESHOOTING

**If Stage 2 (SEO Time Travel) feels speculative:**
- Focus on documented trends (EEAT, first-hand experience)
- Validate predictions against Google's official guidance
- If uncertain, skip future predictions and focus on current best practices

**If Stage 4 (Customer Reality) is too harsh:**
- Returns Manager may flag valid concerns - don't ignore them
- Amazon Reviewer role-play prevents real negative reviews
- Better to catch overpromises NOW than after returns spike

**If pipeline takes longer than 8 hours:**
- Consider running Stages 1-2 in one session, 3-4 in another
- Or use 6-agent pipeline instead (80% of value, 50% of time)

```

---

## Scaling Strategy

**Month 1:** Run 13-agent pipeline on 20 high-value SKUs
**Month 2:** Compare performance to 6-agent and baseline
**Month 3:** If ROI justifies complexity, scale to 50 SKUs
**Month 4+:** Build automation or stick with 6-agent for routine batches

Start with quality, then scale what works.
