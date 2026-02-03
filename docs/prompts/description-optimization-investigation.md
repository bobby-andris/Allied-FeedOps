# Description Optimization Investigation Prompt

Use this prompt in a **new Claude Code chat** to investigate and improve Google/Bing descriptions with fresh perspective and real data.

---

## The Prompt

```
## Context
We've been optimizing product descriptions for Allied Brass (bathroom hardware)
using mechanical metrics like sentence length, attribute density, and keyword
placement. The descriptions score well on our internal metrics but may not
actually help products get found or clicked.

Example of what we're producing (shower basket):
"This 18.75-inch wall-mounted shower basket is crafted from solid brass for lasting
bathroom storage. Available in Antique Brass. Antique Brass features a softened,
aged golden patina..."

This feels wrong. It reads like a spec sheet, not something that connects with
what a shopper is actually searching for.

## Your Mission

### Phase 1: Understand Real Search Behavior
1. Use the Google Ads MCP (customer ID: 6253381786) to pull search term data:
   - What queries are people ACTUALLY using to find shower caddies/baskets?
   - What queries lead to clicks vs impressions only?
   - What's the gap between what we're writing and what people search?

2. Use Apify to scrape top-ranking competitors on Google Shopping for "shower caddy":
   - How do their descriptions read?
   - What do they lead with?
   - What attributes do they emphasize?

### Phase 2: Analyze User Intent
For each product category (shower baskets, towel bars, grab bars, etc.):
1. What PROBLEM does this product solve?
2. What QUESTIONS does a buyer have before purchasing?
3. What would make someone CLICK this result vs a competitor?

### Phase 3: Create a New Description Philosophy
Based on your research, create a simple framework for descriptions that:
1. Matches real search intent (not assumed keywords)
2. Answers the buyer's actual questions
3. Differentiates from competitors
4. Is SIMPLE - not over-engineered with rules

### Phase 4: Write Better Descriptions
Rewrite the shower basket description (SKU: BSK-275LA) using your new approach.
Then score it against the old one using REAL metrics:
- Does it contain the search terms people actually use?
- Does it answer the top 3 buyer questions?
- Would YOU click on this?

## Important Constraints
- Use REAL DATA from Google Ads and competitor research
- Don't assume you know what people search - verify it
- Prioritize clarity over keyword density
- The description should make sense to a HUMAN first

## Files to Read
- CLAUDE.md (project context)
- src/feedops/pipeline/prompts.py (current prompt instructions)
- data/finish-metadata.json (finish descriptions)
- dashboard_data/lifestyle-eval-candidate/google-patch-BSK-275LA.json (current output)

## Key Question to Answer
Are we optimizing for the wrong thing? Should descriptions be about
"attribute density for algorithm matching" or about "answering what
the buyer actually wants to know"?
```

---

## Why This Prompt Works

1. **Action-first**: Uses Google Ads MCP and Apify to get REAL data, not assumptions
2. **Clear phases**: Understand → Analyze → Create → Write is a natural discovery flow
3. **Real metrics**: "Does it contain the search terms people actually use?" beats internal scoring
4. **Not overloaded**: Lets the chat discover fresh insights rather than biasing it with prior conclusions
5. **The right question**: "Are we optimizing for the wrong thing?" cuts to the core issue

## Additional Research (Optional)

If the new chat wants deeper context, these research documents exist in `docs/titles_descriptions_independent_research/`:
- `Product Listing Optimization Research.md`
- `Youtube-video-transcript.md`
- `compass_artifact_wf-f630d2a3-044d-4d0c-87af-8f3f823e6bc9_text_markdown.md`

But the chat should prioritize REAL DATA over reading old research.
