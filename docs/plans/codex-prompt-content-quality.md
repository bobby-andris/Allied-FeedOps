# Codex Prompt: Fix Content Generation Quality Once and For All

## Why You're Reading This

We have spent 6+ iterations (Phases 25, 25.1, 25.2, 25.3) trying to make our GPT-5.2 content generation produce titles and descriptions that the business owner (Bobby) would approve on first read. Every iteration has improved something but introduced new issues or failed to clear the 8/10 human approval bar. The GSD framework's phase-plan-execute-verify loop has created overhead that obscures the simplicity of what's actually broken. This prompt gives you the full picture so you can fix it.

## The Product

Allied-FeedOps is a Google Ads feed optimization platform for alliedbrass.com, a luxury bathroom hardware manufacturer with 2,784 SKUs across ~100 master products and 28 finish variants each. We generate optimized titles and descriptions for 3 platforms:

- **Google Shopping** — variant-level (finish-specific), uses `{FINISH_NAME}` and `{FINISH_SENTENCE}` placeholders
- **Bing Shopping** — variant-level (finish-specific), same placeholders
- **Shopify** — master-SKU level (finish-agnostic), HTML format

Plus **finish sentences** — 28 short sentences (one per finish) that replace `{FINISH_SENTENCE}` during variant expansion.

## The Architecture (It's Fine — Don't Rebuild It)

The per-platform generation architecture built in Phase 25.2 is correct:

1. **System prompt** = `SYSTEM_PROMPT` + platform-specific `GOOGLE_BRIEF`/`BING_BRIEF`/`SHOPIFY_BRIEF`/`FINISH_BRIEF` (from `prompts.py`, combined in `skill_loader.py:get_platform_system_prompt()`)
2. **User prompt** = product evidence + keywords + product design story + competitive context (built in `prompt_builder.py:build_google_prompt()` etc.)
3. **Schema** = per-platform JSON strict schema with `claims` and `self_score` (in `prompts.py`)
4. **API call** = GPT-5.2 with `reasoning_effort=medium`, `response_format=json_schema` strict mode
5. **Feature flag** = `FEEDOPS_PROMPT_VERSION=v2` routes to per-platform path; `v1` is legacy single-call

This architecture is sound. The per-platform briefs were rewritten in Phase 25.3-02 based on Bobby/Robert's human feedback. **Do not redesign the architecture.**

## What's Actually Broken (3 Things)

### Problem 1: Evidence Table Contaminates the Prompt

The evidence table (built by `src/feedops/pipeline/evidence.py:build_evidence_table()`) feeds GPT-5.2 real product data from Supabase. This includes:

- **Product bullets** that contain banned words: "made of the finest solid brass materials" — the word "finest" is in the actual product data stored in Supabase
- **Search keyword data** that contains competitor brand names: "jan barboglio paper towel holder" — real search terms people use, pulled from Google Ads `search_queries` table
- **Keyword placement plans** that surface these same terms as "high-intent keywords"

GPT-5.2's grounding bias means it echoes data from the evidence over instructions telling it not to. We've told it "never mention competitor brands" in the system prompt (the `<accuracy_guardrail>` section), but when "jan barboglio" appears in the keyword data, the model uses it as a comparison point ("if you've been comparing designs like a jan barboglio paper towel holder..."). No amount of prompt engineering will fix this if the contaminated data is in the context window.

**The fix:** Sanitize the evidence before it reaches GPT-5.2. Strip competitor brand names from keyword data. Strip banned words from product bullets before including them in the prompt. This is a Python function in `evidence.py` or `prompt_builder.py`, not a prompt change.

Key files:
- `src/feedops/pipeline/evidence.py` — `build_evidence_table()`, `format_evidence_markdown()`
- `src/feedops/api/prompt_builder.py` — `_build_product_design_story()`, `build_google_prompt()`, etc.
- Banned words list: `scripts/ab_prompt_test.py` lines 43-53 (BANNED_WORDS)
- Competitor brands list: `scripts/ab_prompt_test.py` lines 55-70 (COMPETITOR_BRANDS)
- Banned phrases in system prompt: `src/feedops/pipeline/prompts.py` lines 322-324

### Problem 2: Artificial Schema Constraints Cause Empty Outputs and Fight the Model

SKUs 102 (Cabinet Knob) and 1098 (Shower Rod Brackets) return completely empty `google_title`, `google_short_title`, and `google_description` from GPT-5.2. Bing and Shopify work fine for the same SKUs.

**Root cause: we've hardcoded `maxLength: 900` on `google_description` in the JSON schema, combined with a `pattern` regex requiring `{FINISH_SENTENCE}`.** Google Shopping actually supports up to **5,000 characters** for descriptions. The 700-900 character range was an arbitrary "optimization target" from early iterations that got hardened into a strict schema constraint. When GPT-5.2 can't simultaneously satisfy the pattern regex AND stay under 900 characters, it returns empty content rather than violating the schema.

This is symptomatic of a deeper pattern across all our iterations: **we keep layering constraints that fight the model instead of letting it write good content.** The model is being asked to satisfy a `maxLength`, a `pattern` regex, a list of banned words, a list of banned phrases, placeholder requirements, title formulas, and a self-scoring rubric — all simultaneously in strict JSON mode. When constraints conflict or are too tight, the model produces worse output (truncated, empty, or awkwardly contorted to fit).

**The fix:**
1. Remove `maxLength` from all description fields in the schemas (Google, Bing, Shopify). Google supports 5,000 chars, Bing supports 5,000+, Shopify has no limit. Let the prompt brief guide length ("aim for 700-900 chars" as soft guidance), not the schema.
2. Remove the `pattern` regex from description fields. The prompt already tells the model to include `{FINISH_SENTENCE}` — enforcing it via regex in the schema is belt-and-suspenders that causes failures when the model can't satisfy both constraints.
3. Keep `maxLength` only where the platform actually enforces it: `google_title` (150 chars), `google_short_title` (70 chars), `shopify_meta_description` (160 chars).
4. Investigate the empty output SKUs: check `finish_reason` — is it `length` (token limit), `stop` (normal), or `content_filter`? Increase `max_completion_tokens` if needed.

Key files:
- `src/feedops/pipeline/prompts.py` — `GOOGLE_SCHEMA` (line 155+)
- `scripts/ab_prompt_test.py` — `generate_per_platform()` for the API call
- `src/feedops/providers/openai_provider.py` — production API call

### Problem 3: The Validation Script Has False Positives

The test harness (`scripts/ab_prompt_test.py`) calls `extract_strings(payload)` which grabs ALL string values from the JSON output, including `claims[].source_value` (which quotes the original product data verbatim). This means:

- A product bullet that says "finest solid brass" gets quoted in `claims.source_value` → flagged as banned word
- The actual title and description may be clean, but the check fails because it scans the claims too

This creates the appearance that banned words are in the generated content when they're actually just in the evidence citations. Every iteration, we see "FAILED: no_banned_words" and think the prompt needs more work, when the real content is fine.

**The fix:** Update `evaluate_platform_output()` to only scan the actual content fields (`google_title`, `google_description`, etc.), not `claims` or `self_score`. Remove the description length checks entirely — Google supports 5,000 chars, and the prompt brief already provides soft length guidance. Hard length validation in the test harness is causing false failures and wasting iteration cycles.

Key file: `scripts/ab_prompt_test.py` — `evaluate_platform_output()` function

## What Bobby/Robert Actually Want (from Round 2 Evaluation)

Read the full evaluation: `.planning/phases/25-evaluate-iterate/25-02-evaluation-results.md`

**Round 2 consensus results:** 4/10 title wins, 6/10 description wins (target: 8/10 each)

**What Bobby likes in titles:**
- {FINISH_NAME} first (this now works)
- Product function clearly stated
- Collection name with "Collection" keyword when applicable
- Dimension only when the product varies by size
- "Allied Brass" last
- NOT: keyword stuffing, detailed dimensions, "Solid Brass" in title

**What Bobby likes in descriptions:**
- Opens with a product-specific design detail (not a generic category benefit)
- Concrete and specific — what makes THIS product different from a $20 Amazon hook
- {FINISH_SENTENCE} integrated naturally, not jammed in
- No weight capacity, no detailed dimensions, no competitor material names
- Reads like an interior designer wrote it, not a database export

**What Bobby DOESN'T want:**
- "Heritage bathroom fixtures" or any invented category terms
- "28 finishes" mentioned on a variant-specific listing
- "Also searched as" or keyword list patterns
- Weight capacity (creates doubt)
- Competitor material comparisons ("unlike die-cast zinc...")

## What Success Looks Like

1. Run generation for these 10 test SKUs: 1025U, 1016, 102, 1020-3, 1024, 1020, DMF-2/2X, WP-2/16-GAL, 1098, CL-22
2. All 10 produce non-empty content across all 4 platforms (Google, Bing, Shopify, Finish)
3. Zero competitor brand names in any generated title or description
4. Zero banned words in any generated title or description (not counting claims.source_value)
5. Bobby reads the titles and descriptions and says "yes, this is good" for at least 8/10

Criterion 5 is the only one that matters. The others are prerequisites.

## Files You Need to Touch

**Must fix (evidence sanitization):**
- `src/feedops/pipeline/evidence.py` — Add sanitization to strip competitor brands and banned words from evidence before it reaches the prompt
- OR `src/feedops/api/prompt_builder.py` — Sanitize in the prompt builder before assembling the user prompt

**Must investigate (empty outputs):**
- `src/feedops/pipeline/prompts.py` — GOOGLE_SCHEMA constraints (maxLength, pattern regex)
- `scripts/ab_prompt_test.py` — Add logging for finish_reason and refusal on empty responses

**Must fix (false positive validation):**
- `scripts/ab_prompt_test.py` — `evaluate_platform_output()` to scan only content fields, not claims

**May need to tune (prompt quality):**
- `src/feedops/pipeline/prompts.py` — SYSTEM_PROMPT, GOOGLE_BRIEF, BING_BRIEF, SHOPIFY_BRIEF, FINISH_BRIEF
- `src/feedops/api/prompt_builder.py` — User prompt assembly

**Test harness:**
- `scripts/batch_ab_test.py` — Batch runner for all 10 SKUs (already exists, just written)
- `scripts/ab_prompt_test.py` — Single SKU runner with constraint checks

## How to Test

```bash
# Activate the Python environment
cd /path/to/Allied-FeedOps
source .venv/bin/activate
set -a && source .env.vercel && set +a

# Run single SKU test
PYTHONPATH=./src python scripts/ab_prompt_test.py --sku 1025U --platform all

# Run batch test (all 10 SKUs)
PYTHONPATH=./src python scripts/batch_ab_test.py

# Run Python tests
PYTHONPATH=./src python -m pytest tests/ -v -k "prompt"
```

## What NOT to Do

1. **Do NOT redesign the architecture.** Per-platform calls with dedicated briefs is correct.
2. **Do NOT add post-processing.** If GPT-5.2 produces bad content, fix the prompt or the input data, not a regex layer after.
3. **Do NOT optimize for constraint check pass rate.** Optimize for Bobby reading the output and saying "yes."
4. **Do NOT add more phases or plans.** Fix the 3 problems listed above, test, iterate.
5. **Do NOT remove the claims or self_score from the schema.** These are useful for debugging and audit. Just don't validate banned words against them.
6. **Do NOT change the feature flag mechanism.** `FEEDOPS_PROMPT_VERSION=v2` routing works.

## Context Files (Read These)

- `CLAUDE.md` — Full project context, database schema, deployment, conventions
- `src/feedops/pipeline/prompts.py` — All schemas, SYSTEM_PROMPT, platform briefs
- `src/feedops/api/prompt_builder.py` — User prompt assembly for all 4 platforms
- `src/feedops/pipeline/evidence.py` — Evidence table builder
- `src/feedops/pipeline/skill_loader.py` — System prompt assembly
- `scripts/ab_prompt_test.py` — Test harness with constraint checks
- `scripts/batch_ab_test.py` — Batch test runner
- `.planning/phases/25-evaluate-iterate/25-02-evaluation-results.md` — Bobby/Robert's Round 2 human evaluation feedback
- `docs/plans/2026-02-21-strategic-milestone-assessment.md` — Part 2 "The Content Quality Crisis" for full root cause analysis

## The Strategic Picture

This is Milestone v1.3a: Content Generation Excellence. The master plan (`docs/plans/2026-02-21-strategic-milestone-assessment.md`) establishes that content quality must be fixed BEFORE we can build optimization intelligence (v1.3c) or closed-loop optimization (v1.4). Bad content → bad CTR → noisy optimization signals → garbage in, garbage out.

The prompt and architecture are 90% there. What's left is plumbing (sanitize evidence), debugging (empty outputs), and validation accuracy (false positives in the test harness). These are engineering problems, not creative problems. Fix them, generate the 10 test SKUs, and get Bobby's approval.
