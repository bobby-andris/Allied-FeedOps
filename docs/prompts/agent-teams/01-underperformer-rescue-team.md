# Agent Team: Underperformer Rescue Team (5 Agents)

## Overview

**Goal:** Identify and fix the top 20 SKUs with high impressions but low CTR, using performance data from Prompt 22.

**Why This Works:**
- High impressions = Google already ranks these products
- Low CTR = something is wrong with the title/description
- Fixing these = immediate revenue impact (more clicks = more sales)
- Fast feedback loop (results visible in 2-3 weeks)

**Timeline:** 3-4 hours for agent team to complete

**Expected ROI:** If CTR improves from 0.5% → 2.0% on SKUs with 10K impressions/month = 150 extra clicks/month per SKU

---

## Prerequisites

- Prompt 22 implemented (performance_baselines and performance_snapshots tables exist)
- Supabase MCP configured and connected
- Google Ads MCP configured (for keyword data)
- Apify MCP configured (for competitor scraping)

---

## Copy/Paste This Prompt Into Claude Code

```
Create an agent team to rescue underperforming SKUs using performance data from Prompt 22.

## GOAL
Identify the top 20 SKUs with high impressions but low CTR, diagnose why they're underperforming, and generate improved content.

## CONTEXT
Project: Allied-FeedOps (Allied Brass product content optimization)
Working directory: /Users/bobby/Documents/GitHub/Allied-FeedOps
Supabase project: qezuszwufortkiutlhym
Google Ads customer ID: 6253381786

## IMPORTANT CONSTRAINTS
- All agents have access to: Supabase MCP, Google Ads MCP, Apify MCP, Playwright MCP, Context7
- Write results ONLY to generated_content.candidate_content (existing review workflow handles approval)
- DO NOT modify: sku_approvals, variant_approvals, or publish_events tables
- DO NOT publish directly - write to candidate_content for dashboard review

## TEAM STRUCTURE (5 Agents)

### Agent 1: Performance Detective
**Goal:** Identify top 20 underperforming SKUs using Prompt 22 performance data

**Tools:**
- mcp__supabase__execute_sql (query performance_baselines)
- mcp__supabase__list_tables (verify schema if needed)

**Workflow:**
1. Query performance_baselines table:
   ```sql
   SELECT
     master_sku,
     platform,
     avg_impressions,
     avg_ctr,
     avg_impressions * (0.02 - avg_ctr) as opportunity_score
   FROM performance_baselines
   WHERE avg_impressions > 5000
     AND avg_ctr < 0.015
     AND platform = 'google'
   ORDER BY opportunity_score DESC
   LIMIT 20;
   ```
2. For each SKU, calculate potential impact:
   - Current clicks = impressions * current_ctr
   - Target clicks = impressions * 0.02 (2% target CTR)
   - Opportunity = target_clicks - current_clicks
3. Create prioritized list with reasoning
4. Share findings with team

**Deliverable:** List of 20 master_skus with current metrics and opportunity scores

---

### Agent 2: Competitor Intelligence Analyst
**Goal:** For each underperforming SKU, scrape top 3 competitors and identify what they're doing better

**Tools:**
- mcp__Apify__search-actors (find scraping actors)
- mcp__Apify__call-actor (run scraper)
- mcp__merchant-api-devdocs__query_mapi_docs (GMC competitive data if available)
- mcp__google-ads-mcp__search (check competitor ad copy)

**Workflow:**
1. Receive list of 20 SKUs from Agent 1
2. For each SKU (focus on top 10 if time-constrained):
   a. Query product_catalog for product details:
      ```sql
      SELECT title, description, category, collection
      FROM product_catalog
      WHERE master_sku = '{sku}'
      LIMIT 1;
      ```
   b. Search Google Shopping for same product (use Apify or manual research)
   c. Identify top 3 ranking competitors
   d. Extract patterns:
      - Title structure (what keywords come first?)
      - Description length and format
      - Benefit emphasis (durability? aesthetics? installation?)
      - Keywords they use that we don't
3. Create competitive intelligence report per SKU

**Deliverable:** Competitive analysis showing what winners emphasize

---

### Agent 3: Content Diagnostician
**Goal:** Analyze current content for each underperforming SKU and identify specific weaknesses

**Tools:**
- mcp__supabase__execute_sql (query generated_content, search_queries)
- greptile (search codebase for quality rubric if needed)

**Workflow:**
1. Receive list of 20 SKUs from Agent 1
2. For each SKU:
   a. Query current content:
      ```sql
      SELECT baseline_content, quality_score, platform
      FROM generated_content
      WHERE master_sku = '{sku}' AND platform = 'google';
      ```
   b. Query search terms data:
      ```sql
      SELECT query, search_volume, clicks
      FROM search_queries_by_master_sku
      WHERE master_sku = '{sku}'
      ORDER BY search_volume DESC
      LIMIT 10;
      ```
   c. Run diagnostic checks:
      - Generic AI phrases ("elevate," "transform," "luxury experience")
      - Missing high-volume keywords from search_queries
      - Weak verbs ("helps," "provides" vs "installs," "mounts")
      - Title structure issues (finish placement, specs, brand)
      - Description structure (benefits vs features balance)
   d. Assign severity: CRITICAL, HIGH, MEDIUM, LOW
3. Create diagnostic report per SKU with specific issues

**Deliverable:** Content audit showing specific weaknesses per SKU

---

### Agent 4: Storytelling Rewriter
**Goal:** Generate improved content using product evidence, competitor insights, and diagnostic feedback

**Tools:**
- mcp__supabase__execute_sql (read product_catalog, variant_finish_sentences, write to generated_content)
- mcp__plugin_context7_context7__query-docs (lookup React/writing best practices if needed)

**Workflow:**
1. Receive inputs from Agents 2 & 3:
   - Competitive intelligence (what winners emphasize)
   - Content diagnostics (specific issues to fix)
2. For each SKU:
   a. Query product evidence:
      ```sql
      SELECT
        pc.narrative_copy,
        pc.bullets,
        pc.dimensions,
        pc.category,
        pc.collection,
        vfs.finish_sentence
      FROM product_catalog pc
      LEFT JOIN variant_finish_sentences vfs
        ON pc.master_sku = vfs.master_sku
      WHERE pc.master_sku = '{sku}'
      LIMIT 1;
      ```
   b. Use storytelling approach (from Idea 2):
      - Product Designer perspective: "I engineered the mounting bracket to..."
      - Contractor perspective: "I install 50 of these a month because..."
      - Homeowner perspective: "Every morning my towel hangs here..."
   c. Synthesize into title + description:
      - Incorporate competitor winning patterns
      - Fix all issues from diagnostician
      - Include high-volume keywords from search data
      - Use authentic voice (no AI slop)
   d. Write to Supabase:
      ```sql
      UPDATE generated_content
      SET
        candidate_content = '{new_content_json}',
        updated_at = NOW()
      WHERE master_sku = '{sku}' AND platform = 'google';
      ```
3. Keep running quality score to validate improvements

**Deliverable:** Updated content in generated_content.candidate_content for all 20 SKUs

---

### Agent 5: A/B Test Coordinator
**Goal:** Set up tracking to measure improvement and document methodology

**Tools:**
- mcp__supabase__execute_sql (create tracking records)

**Workflow:**
1. Create tracking table entry (if table doesn't exist, create it):
   ```sql
   CREATE TABLE IF NOT EXISTS content_optimization_experiments (
     id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
     experiment_type TEXT NOT NULL,
     start_date TIMESTAMPTZ DEFAULT NOW(),
     skus_updated TEXT[] NOT NULL,
     baseline_metrics JSONB,
     target_metrics JSONB,
     status TEXT DEFAULT 'running',
     results JSONB,
     created_at TIMESTAMPTZ DEFAULT NOW()
   );

   INSERT INTO content_optimization_experiments (
     experiment_type,
     skus_updated,
     baseline_metrics,
     target_metrics
   ) VALUES (
     'underperformer_rescue_v1',
     ARRAY[{list_of_20_skus}],
     '{baseline_ctr_data}',
     '{"target_avg_ctr": 0.02, "measurement_window_days": 30}'
   );
   ```
2. Document methodology in CLAUDE.md:
   - Add section: "## Content Optimization Experiments"
   - Note: Agent team used, date, SKUs targeted, hypothesis
3. Set reminder to check results after 30 days:
   ```sql
   SELECT
     master_sku,
     AVG(ctr) as avg_ctr_post_optimization
   FROM performance_snapshots
   WHERE master_sku = ANY(ARRAY[{list_of_20_skus}])
     AND created_at >= '{optimization_date}'
     AND days_since_publish <= 30
   GROUP BY master_sku;
   ```

**Deliverable:** Experiment tracking setup + documentation

---

## COORDINATION & WORKFLOW

**Phase 1: Discovery (Parallel)**
- Agent 1 identifies underperformers
- Agents 2 & 3 can work in parallel once they have the SKU list

**Phase 2: Content Generation (Sequential)**
- Agent 4 waits for Agents 2 & 3 to complete
- Agent 4 generates improved content

**Phase 3: Tracking Setup (Final)**
- Agent 5 sets up experiment tracking

**Total time:** 3-4 hours

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
   - Check results after 14-30 days

---

## SUCCESS METRICS

**Immediate (Post-Generation):**
- ✅ 20 SKUs updated with new candidate_content
- ✅ Quality scores improved (check avg quality_score)
- ✅ Competitive intelligence documented
- ✅ Content diagnostics show issues fixed

**30-Day (Post-Publish):**
- 🎯 Average CTR improvement: 0.5% → 2.0% (target: 4x)
- 💰 Revenue impact: More clicks = more sales
- 📊 Compare pre/post CTR using performance_snapshots

---

## TROUBLESHOOTING

**If agents can't find underperformers:**
- Check performance_baselines table exists and has data
- Verify Prompt 22 baseline capture ran before publish
- Lower impressions threshold (try 1000 instead of 5000)

**If competitor scraping fails:**
- Use manual research (Google Shopping search)
- Focus on title/description patterns, not full scrape

**If quality scores don't improve:**
- Review diagnostic findings - were all issues addressed?
- Compare to competitor patterns - did we incorporate winning elements?

---

## NEXT STEPS AFTER SUCCESS

1. **Scale:** Run rescue team monthly on new underperformers
2. **Automate:** Build dashboard trigger (Option 2 from integration discussion)
3. **Expand:** Apply winning patterns to NEW content generation (Content Pipeline)
```

---

## File Locations After Agent Team Runs

**Updated Tables:**
- `generated_content.candidate_content` - 20 SKUs with improved content
- `content_optimization_experiments` - Tracking record for this experiment

**Next Action:**
Visit dashboard → Review page → Approve updated SKUs → Publish
