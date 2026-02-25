# Root Cause Analysis: Why GPT-5.2 Prompt Iterations Keep Failing

**Date:** 2026-02-24
**Context:** Phase 25.1 A/B test (v2.1) showed C_Optimized is structurally better but still fails on constraint adherence

---

## The Core Problem

Every iteration of this prompt has been written by Claude Code using Claude-optimized prompting patterns. GPT-5.2 processes instructions fundamentally differently. And we've been dumping Claude Code skill files (written for an AI coding assistant) directly into GPT-5.2's system prompt without adapting them.

## Skill Architecture Problem (CRITICAL)

### What's actually happening in production

`skill_loader.py` loads ALL 8 Claude Code SKILL.md files and concatenates them into the system prompt:

```
get_system_prompt() → SYSTEM_PROMPT (6.4K) + ALL 8 SKILL.md files (257K) = 267K chars / 57K tokens
```

**File sizes:**
- google-shopping-content/SKILL.md: 47,759 chars
- shopify-conversion-content/SKILL.md: 46,036 chars
- finish-expertise/SKILL.md: 40,634 chars
- quality-evaluation/SKILL.md: 40,101 chars
- bing-shopping-content/SKILL.md: 36,753 chars
- allied-brass-brand-expert/SKILL.md: 21,554 chars
- product-storytelling/SKILL.md: 19,412 chars
- collection-storytelling/SKILL.md: 8,527 chars
- **TOTAL: ~260K chars dumped into GPT-5.2 system prompt**

### What's wrong with this

1. **These SKILL.md files were written for Claude Code** — an AI coding assistant helping Bobby interactively. They contain markdown formatting, "you the AI assistant" instructions, interactive editing guidance. They were NEVER designed for GPT-5.2 runtime consumption.

2. **All 8 skills loaded for every call regardless of platform** — `get_system_prompt()` is called with no arguments everywhere. The platform-specific skill loading (`mode="single"`, `platform="google"`) is dead code. GPT-5.2 always gets google-shopping-content AND bing-shopping-content AND shopify-conversion-content simultaneously, even though it's generating all fields in one call.

3. **No platform-specific prompting** — Because all 8 skills are dumped in, GPT-5.2 gets conflicting guidance: Google says "plain text, 700-900 chars," Shopify says "HTML, 250-400 words," Bing says "front-load specs in first 200 chars." The model tries to reconcile contradictory instructions for 8+ output fields simultaneously.

4. **The YAML config files (`src/feedops/config/*.yaml`) are separate from the skills** — They were intended as distilled runtime configs but `prompt_builder.py` ALSO loads `shopping_intelligence.yaml` via `get_shopping_intelligence_section()`. So GPT-5.2 gets BOTH the full SKILL.md AND the YAML config for some domains — redundant and contradictory.

### What the skills SHOULD be doing

The skills contain genuinely valuable domain knowledge:
- **google-shopping-content**: Title formula, CTR optimization, gold standard examples
- **finish-expertise**: 28 finishes with visual descriptions, compelling sentences
- **product-storytelling**: Interior designer perspective, buyer scenarios
- **allied-brass-brand-expert**: Brand voice, competitor prohibition
- **collection-storytelling**: Collection DNA for cross-sell

But this knowledge needs to be **distilled and restructured for GPT-5.2**, not dumped raw.

## Failure Evidence (C_Optimized, 3 representative SKUs)

| Failure | System Prompt Rule | What GPT-5.2 Did |
|---------|-------------------|-------------------|
| "finest" banned word | Line 129: explicit ban list | Ignored — echoed from evidence table |
| {FINISH_SENTENCE} as standalone | Lines 76-81: explicit good/bad examples | Produced "Finished in Satin Brass." — the exact BAD pattern |
| Keyword stuffing (mirror 17x) | Lines 83: "one synonym per sentence" | Worse than baseline — repeated core nouns excessively |
| Generic openings | Lines 134-137: "NEVER open with a sentence that could apply to any product" | "Keep your countertop clean and clutter free" — applies to anything |
| "insure" instead of "ensure" | N/A — echoed from evidence table | Copied manufacturer's grammar error verbatim |
| Missing collection in titles | Lines 45-46: title formula specifies Collection | Inconsistent — sometimes included, sometimes not |
| Empty Bing/Shopify fields (A/B) | Schema requires all fields | A_Current returned EMPTY Bing/Shopify for 2/3 SKUs |

## Root Causes

### 1. GPT-5.2 at reasoning_effort=medium skims constraint lists

18K chars of nuanced rules with priority levels (P0/P1/P2/P3), good/bad examples, integration patterns. At medium reasoning, GPT-5.2 allocates limited reasoning tokens to parse instructions. It picks up broad patterns from gold examples but **skims** the constraint sections.

### 2. Gold examples are surface-copied, not abstracted

GPT-5.2 at medium reasoning doesn't abstract patterns — it **imitates surface features**. Phrases like "ideal use of space" and "crafted from the finest solid brass materials" get copied across multiple outputs.

### 3. Evidence table contains poison pills

The manufacturer's existing descriptions in the evidence table contain:
- Banned words ("finest solid brass materials")
- Bad grammar ("insure" instead of "ensure")
- Competitor names in keyword data ("jan barboglio")

GPT-5.2's "conservative grounding bias" preferentially echoes evidence data over system prompt constraints.

### 4. {FINISH_SENTENCE} is a publishing-pipeline concept with no JSON mechanism

The output schema has `google_description` as a plain string. GPT-5.2 can't output a literal `{FINISH_SENTENCE}` placeholder — it interprets "integrate the finish" as "describe the finish" → produces "Finished in [name]."

### 5. Generating 8+ fields in one call is fundamentally flawed

The schema requires: google_title, google_short_title, google_description, bing_title, bing_description, shopify_title, shopify_description, shopify_meta_description, claims[], self_score{}. Each field has different rules. GPT-5.2 can't apply google-shopping-content rules to google fields AND bing-shopping-content rules to bing fields AND shopify-conversion-content rules to shopify fields — all in one generation call.

### 6. No atomic validation was ever done

We've designed complex prompts theoretically and tested end-to-end. We don't know which instructions GPT-5.2 actually follows vs ignores.

## Why Each Iteration Failed

| Iteration | Approach | Why It Failed |
|-----------|----------|---------------|
| Production (267K) | Dump all 8 SKILL.md files | Skills designed for Claude Code, not GPT-5.2. 57K tokens of noise, 12 contradictions |
| v2 (8K) | Strip to minimal | Lost essential knowledge. Tested at master-SKU level (wrong scenario) |
| v2.1 (18K) | CTCO with gold examples | Claude-optimized structure. Evidence poison pills. No atomic validation |

## What Phase 25.2 Must Do Differently

### Fundamental rethinking required

1. **How should the prompt be constructed?** — Not "how do we compress 267K into 18K" but "what does GPT-5.2 need to produce a perfect title and description for one product on one platform?"

2. **How should product information be passed?** — The evidence table is a raw data dump. Should it be pre-processed? Should different fields go to different prompts? Should we extract only what's relevant per platform?

3. **Should generation be split by platform?** — Google, Bing, and Shopify have different goals, different formats, different rules. One call trying to serve all three may be the wrong architecture.

4. **How should skill knowledge be distilled?** — The skills contain valuable domain expertise. But each skill is relevant to specific outputs. google-shopping-content should inform Google fields. shopify-conversion-content should inform Shopify fields. Not all dumped together.

### Tactical steps

5. **Verify against actual OpenAI docs** — Use `mcp__openaiDeveloperDocs__*` MCP tools
6. **Audit API call parameters** — reasoning_effort, temperature, json_schema, max_completion_tokens, text.verbosity
7. **Atomic testing** — test individual constraints in isolation before combining
8. **Sanitize evidence inputs** — strip banned words/grammar before they reach GPT-5.2
9. **Rethink {FINISH_SENTENCE}** — either schema field or separate generation step
10. **Test reasoning_effort levels** — medium may be insufficient
11. **Build prompt bottom-up** — start simple, add constraints incrementally, validate each
12. **Run local tests for every change** — actual GPT-5.2 API calls, not dry-runs
