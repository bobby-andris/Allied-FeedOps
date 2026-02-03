# Description Optimization Investigation Prompt

Use this prompt in a **new Claude Code chat** to investigate and improve Google/Bing descriptions with an unbiased perspective.

---

## The Prompt

```
You are investigating whether the Google/Bing product descriptions for Allied Brass bathroom hardware are actually good, despite scoring 90% on internal quality metrics.

## PROBLEM STATEMENT

Current descriptions sound robotic. Example (shower basket):
"Finished in Antique Brass, shower basket, 18.75 in L x 2.25 in H x 4.13 in W, solid brass wall mount oval combination shower caddy for bathroom bath/shower storage, which features a softened, aged golden patina..."

This scores 90% internally but:
- Opens with dimension dump, not engaging prose
- Doesn't match what users actually search for
- Doesn't answer buyer questions
- Sounds like a spec sheet with keywords bolted on

## YOUR INVESTIGATION TASKS

### 1. Understand the Current System
Read these files to understand what we're working with:

- Current prompt: @src/feedops/pipeline/prompts.py (lines 134-200)
- Quality scoring: @src/feedops/quality/scoring.py
- Finish injection: @src/feedops/pipeline/finish_injection.py
- Example output: @dashboard_data/lifestyle-eval-candidate/google-patch-BSK-275LA.json

### 2. Review Existing Research
We've done deep research on product listing optimization. Read these:

- @docs/titles_descriptions_independent_research/Product Listing Optimization Research.md
- @docs/titles_descriptions_independent_research/compass_artifact_wf-f630d2a3-044d-4d0c-87af-8f3f823e6bc9_text_markdown.md
- @docs/titles_descriptions_independent_research/Youtube-video-transcript.md
- @docs/titles_descriptions_independent_research/Product Title & Description Optimization for Revenue & Ad Efficiency.docx.md

Key insights from this research:
- 95% of buying decisions are emotional (System 1), then rationalized (System 2)
- Descriptions should reduce cognitive load and uncertainty
- Match search intent, not just include keywords
- Answer the 3 questions buyers have before purchasing

### 3. Get Real Search Data
Use the Google Ads MCP to find what people ACTUALLY search for:

Customer ID: 6253381786

Query the shopping_performance_view for:
- Search terms that led to shower basket/caddy purchases
- Search terms for paper towel holders
- Search terms for towel bars

Identify the top 10-20 search queries by conversions for each category.

### 4. Compare Generated vs. Real Search Intent
- Does the generated description use the actual search terms naturally?
- Would it surface for those queries?
- Does it answer the questions a buyer has?

### 5. Evaluate the Current Prompt Philosophy
The current prompt (src/feedops/pipeline/prompts.py) has ~15 mechanical rules for Google descriptions:
- "First sentence: product type + ONE key dimension + material"
- "Keep each sentence under 80 characters"
- "Include natural synonyms shoppers search"
- etc.

Questions to answer:
- Do these rules create compliance-seeking behavior that produces robotic output?
- Does the prompt make the LLM think about buyer intent, or just follow formatting rules?
- Should we add MORE rules or FEWER rules?
- Should we include the research documents in the prompt, or keep it simple?

### 6. Provide Final Recommendation
After your investigation, provide:

1. **Diagnosis**: What's actually wrong with the current approach?

2. **Recommended Prompt Changes**: The exact text to replace in prompts.py (lines 136-152) that will produce better descriptions. Consider:
   - Intent-first thinking (what would a buyer search?)
   - Fewer mechanical rules, more strategic thinking
   - Whether to include research insights or keep it simple

3. **Scoring Changes**: Any changes needed to src/feedops/quality/scoring.py to reward better descriptions

4. **Test Plan**: How to validate the changes work (regenerate BSK-275LA and compare)

## CONSTRAINTS

- Don't assume the current approach is good just because it scores well
- Be critical and evidence-based
- Use real search data, not assumptions about what people search
- The goal is descriptions that CONVERT, not descriptions that pass internal checklists

## PROJECT CONTEXT

Read @CLAUDE.md for full project context including:
- MCP server defaults (Google Ads customer ID: 6253381786)
- File locations
- How to run the pipeline
```

---

## After Running This Investigation

The new chat should produce:
1. Evidence-based diagnosis of what's wrong
2. Specific prompt text changes for prompts.py
3. Any scoring changes for scoring.py
4. A test plan to validate improvements

Then you can review their recommendations and decide what to implement.
