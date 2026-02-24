# New Prompt Architecture for GPT-5.2 Content Generation (v2.1 — Revised)

**Date:** 2026-02-23 (revised)
**Author:** Claude (Phase 25.1, Plans 02-03 revision)
**Status:** Ready for A/B testing with variant-level generation

---

## 1. Design Philosophy (REVISED)

### The Problem (unchanged)

The current prompt architecture injects 8 SKILL.md files (260K chars, ~57K tokens) into the system prompt. These files were designed for Claude Code agent workflows -- they contain skill metadata, invocation triggers, cross-references, and agent guidance that are pure noise for GPT-5.2. The result: a 17.7:1 instruction-to-data ratio with 12 contradictory instructions.

### The Shift (REVISED)

**From:** "Dump all skills into the system prompt and hope GPT-5.2 extracts the right guidance"
**To:** "DISTILL essential domain knowledge from all 8 skills into the prompt, purpose-built for GPT-5.2"

**CRITICAL CLARIFICATION (v2.1):** The goal is NOT to minimize prompt tokens. The goal is to produce OPTIMAL content from GPT-5.2. The 8 skills contain essential domain expertise that ENHANCES the prompt:

- **Gold standard examples** from google-shopping-content: show the model what excellent looks like
- **Title formula with {FINISH_NAME} first**: non-negotiable for Google/Bing variant content
- **{FINISH_SENTENCE} integration rules**: how to weave finish copy naturally into descriptions
- **Category-specific hooks**: what shoppers care about in each product category
- **Brand voice truths**: what makes Allied Brass different (solid brass, 41 collections, concealed mounting)
- **Interior designer perspective**: framing hardware as design choices, not commodity products
- **Competitor brand prohibition**: never name competitors even when they appear in keyword data
- **Finish expertise**: per-finish visual descriptions, design styles, search behavior

What we DO cut:
- Claude Code metadata (skill identity, when to invoke, agent guidance, rule file references)
- Full 28-finish detail in the system prompt (that goes per-variant in the user prompt via finish_context)
- Redundant/contradictory instructions (the 12 contradictions from the audit)
- The full 10-criterion scoring rubric (replaced with 3-criterion simplified score)

### Core Principles

1. **Quality over size.** If the prompt needs 18K chars to produce optimal content, that's the right size. The original 267K prompt was bad because of contradictions and noise, not because it was large.

2. **Distill, don't strip.** Every skill contains essential domain knowledge. The system prompt should distill that knowledge — not dump it verbatim, and not strip it out.

3. **One authoritative rule per topic.** Every topic has exactly ONE instruction. No contradictions.

4. **Variant-level generation for Google/Bing.** Content is ALWAYS generated for a specific finish variant, not a master SKU. {FINISH_NAME} must be the first element in every Google/Bing title.

5. **Evidence-driven generation.** The model generates from the evidence table. The prompt constrains HOW to write; the evidence provides WHAT to write about.

6. **Competitor intelligence, not competitor naming.** Keyword data may contain competitor brands. The model should use this as query-matching intelligence but NEVER include competitor names in content.

---

## 2. Architecture Diagram (REVISED)

### New Architecture (~18K chars system, ~5-15K user)

```
System Message (~18K chars, ~4.8K tokens):
+-- <context> (~500 chars) ................. Who you are, what you generate, competitive landscape
+-- <task> (~200 chars) .................... Generate content using evidence
+-- <constraints> (~11K chars) ............. Hierarchical, non-contradictory rules
|   +-- <accuracy priority="P0"> .......... Evidence-only, competitor brand prohibition
|   +-- <content_rules priority="P1"> ...... Title formula ({FINISH_NAME} first), {FINISH_SENTENCE}
|   +-- <voice priority="P2"> ............. Brand truths, designer perspective, banned words
|   +-- <platform priority="P3"> .......... Google/Bing/Shopify format rules
+-- <gold_examples> (~5K chars) ............ 5 exemplar outputs from the skill
+-- <output> (~400 chars) .................. JSON schema, claims, simplified self-score

User Message (~5-15K chars per variant):
+-- <evidence_table> ...................... Product data (runtime)
+-- <keyword_placement> ................... Keywords + competitor brand filter warning
+-- <category_guidance> ................... From shopping_intelligence.yaml (runtime)
+-- <product_design_story> ................ From product data + collection (runtime)
+-- <competitive_positioning> .............. From prompt_builder (runtime)
+-- <finish_context> ...................... Per-finish visual, style, sentence (REQUIRED for Google/Bing)
+-- <output_contract> .................... Schema reference
```

### Size Comparison

| Component | Current (v1) | Previous v2 | Revised v2.1 |
|-----------|-------------|-------------|--------------|
| System prompt | 267K chars / 57K tokens | ~8.2K chars / ~1.7K tokens | ~18K chars / ~4.8K tokens |
| Contradictions | 12 | 0 | 0 |
| Gold examples | 0 in system | 0 in system | 5 in system |
| {FINISH_NAME} in title formula | Mentioned in skill | Not enforced | FIRST element, non-negotiable |
| {FINISH_SENTENCE} rules | In skill, contradicted | Brief mention | Full integration rules + examples |
| Category hooks | In 47K skill | Absent | Distilled in P1 (via user prompt) |
| Brand truths | Scattered across skills | Brief P2 | Distilled in P2 with examples |
| Competitor brand prohibition | Not explicit | Not explicit | Explicit P0 rule |

---

## 3. What Changed from v2 to v2.1

### Problem: v2 stripped essential domain knowledge

Bobby identified 7 critical issues with the v2 prompt:

1. **Gold standard examples were missing.** The google-shopping-content skill has 10 excellent examples that demonstrate the quality target. v2 cut them. v2.1 includes 5 in the system prompt.

2. **{FINISH_NAME} not enforced as first title element.** Google/Bing content is variant-level — every listing has a specific finish. v2 mentioned it but didn't enforce it. v2.1 makes it non-negotiable with explicit examples.

3. **{FINISH_SENTENCE} integration rules were missing.** The google-shopping-content skill has specific rules for how to weave {FINISH_SENTENCE} into descriptions. v2 cut them. v2.1 includes good/bad examples.

4. **Category-specific hooks were stripped.** Each product category has different shopper intent and different differentiation strategies. v2 removed them. v2.1 keeps them in the user prompt (per-category from shopping_intelligence.yaml).

5. **Brand voice truths were stripped.** What makes Allied Brass different (solid brass, 41 collections, concealed mounting, Louisa VA, Limited Lifetime Warranty) was barely mentioned. v2.1 distills these in the P2 voice section.

6. **Interior designer perspective was missing.** The product-storytelling skill teaches framing hardware as design choices, not commodity products. v2.1 distills this in P2.

7. **Competitor brand names leaked into content.** Keyword data contains competitor brands (e.g., "jan barboglio paper towel holder"). Without explicit prohibition, GPT-5.2 included them. v2.1 adds explicit P0 prohibition.

### What stayed from v2

- CTCO structure (Context, Task, Constraints, Output)
- P0-P3 constraint hierarchy
- Zero contradictions
- Simplified 3-criterion self-score
- Removal of Claude Code metadata
- Separation of generation from evaluation

---

## 4. A/B Test Model (REVISED)

### v1 test was master-SKU level — wrong for Google/Bing

The v1 A/B test generated content at master-SKU level without specifying a finish. This is wrong because:
- Google/Bing content is ALWAYS expanded to finish-specific variants
- Titles without a finish name miss all finish-specific search queries (2-3x CTR penalty)
- Descriptions without {FINISH_SENTENCE} can't be expanded to variant listings

### v2.1 test uses variant-level generation

Each test SKU gets a specific finish assigned:
- Evidence data includes the finish context
- Title must start with the finish name
- Description must include {FINISH_SENTENCE} or finish-specific content
- Competitor brand detection: flag if any competitor brand appears in generated content

### Validation criteria

1. **Title starts with finish name** (or {FINISH_NAME} placeholder)
2. **Description contains finish-specific content** (not generic)
3. **No competitor brand names in content** (even if in keyword data)
4. **No competitor material names in content**
5. **No banned words or phrases**
6. **700-900 chars for Google/Bing descriptions**
7. **Content quality matches gold standard patterns**

---

## 5. Constraint Hierarchy (unchanged from v2)

### P0: Accuracy (Non-Negotiable)
Every claim traces to evidence. NEVER include weight capacity, detailed dimensions, competitor materials, competitor brands, invented terms, keyword dumps, finish counts in Google/Bing.

### P1: Content Rules (Structure and Substance)
Title formula with {FINISH_NAME} first. Description structure (hook/substance/synonyms). {FINISH_SENTENCE} integration. Length targets.

### P2: Voice and Style
Brand truths. Interior designer perspective. Prove don't claim. Banned words. Competitor prohibition. Opening variety.

### P3: Platform-Specific
Google/Bing: variant-aware, plain text. Shopify: master-SKU, HTML, finish-agnostic. Field isolation.

---

## 6. Migration Plan (updated)

### Files to Change

#### `src/feedops/pipeline/prompts.py`
- Replace `SYSTEM_PROMPT` with new CTCO prompt (~18K chars)
- Update `CANDIDATE_SCHEMA` description length from "600-800" to "700-900"
- Simplify self_score to 3 criteria

#### `src/feedops/api/prompt_loader.py`
- Add `prompt_version` parameter to `get_system_prompt()`
- v2 path: return new system prompt directly (no skill injection)
- v1 path: existing behavior (backward compatible)

#### `src/feedops/api/prompt_builder.py`
- Ensure finish_context is ALWAYS provided for Google/Bing generation
- Add competitor brand filtering warning to keyword_placement section
- Pass prompt_version through to get_system_prompt()

#### `scripts/ab_prompt_test.py`
- Use variant-level generation (specific finish per SKU)
- Include finish_context in user prompt
- Add competitor brand detection in analysis
- Validate title starts with finish name

---

*Architecture revised based on Bobby's feedback identifying 7 critical gaps in v2. Philosophy: distill essential knowledge for optimal content, not minimize tokens.*
