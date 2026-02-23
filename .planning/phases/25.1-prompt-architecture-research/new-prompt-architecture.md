# New Prompt Architecture for GPT-5.2 Content Generation

**Date:** 2026-02-23
**Author:** Claude (Phase 25.1, Plan 02)
**Status:** Ready for A/B testing in Plan 03

---

## 1. Design Philosophy

### The Problem

The current prompt architecture injects 8 SKILL.md files (260K chars, ~57K tokens) into the system prompt. These files were designed for Claude Code agent workflows -- they contain skill metadata, invocation triggers, cross-references, and agent guidance that are pure noise for GPT-5.2. The result: a 17.7:1 instruction-to-data ratio where GPT-5.2 receives 12 contradictory instructions and averages them into generic, keyword-stuffed content.

### The Shift

**From:** "Dump all skills into the system prompt and hope GPT-5.2 extracts the right guidance"
**To:** "Distill essential knowledge into a non-contradictory, hierarchical CTCO prompt purpose-built for GPT-5.2"

This is not a surgical edit. It is a complete rethink of what the model needs to generate excellent product content. The research (Plan 01 audit + GPT-5.2 prompting guide) shows that over-instruction causes the exact failure modes we observed in Rounds 1-3: keyword stuffing, monotonous structure, bland compromises between conflicting rules, and box-checking instead of genuine content quality.

### Core Principles

1. **Less is more.** A 15K-char prompt with zero contradictions outperforms a 267K-char prompt with 12 contradictions. GPT-5.2 follows instructions literally -- contradictions produce the bland intersection of all instructions.

2. **CTCO framework.** Context, Task, Constraints, Output. GPT-5.2's prompting guide: "Miss one, and quality drops." Structure the prompt architecturally, not conversationally.

3. **One authoritative rule per topic.** Every topic (competitor materials, finish handling, description length, title formula) has exactly ONE instruction. No redundancy, no conflicting guidance across sections.

4. **Constraint hierarchy with priority.** When constraints compete (e.g., "be engaging" vs "be accurate"), the priority system resolves the conflict deterministically. P0 (accuracy) always wins over P2 (voice).

5. **Evidence-driven generation.** The model generates from the evidence table, not from internalized knowledge. The prompt constrains HOW to write, the evidence provides WHAT to write about.

6. **Separate generation from evaluation.** The generation prompt focuses on generating. Scoring is simplified to 3 high-level criteria, not 10 detailed rubric dimensions that cause the model to check boxes instead of write well.

---

## 2. Architecture Diagram

### Current Architecture (267K chars, ~57K tokens system)

```
System Message (~267K chars):
+-- SYSTEM_PROMPT base (6.4K) .............. 2.4%
+-- 8 x SKILL.md files (260K) .............. 97.6%
    +-- Claude Code metadata (~95K) ........ 36% noise
    +-- Redundant instructions (~40K) ...... 15% waste
    +-- Contradictory rules (~20K) ......... 8% harmful
    +-- Useful guidance (~105K) ............ 39% signal
```

### New Architecture (12-14K chars, ~3-4K tokens system)

```
System Message (~12-14K chars):
+-- <context> (~400 chars) ................. Who you are, what you generate
+-- <task> (~300 chars) .................... Generate optimized content using evidence
+-- <constraints> (~9-11K chars) ........... Hierarchical, non-contradictory rules
|   +-- <accuracy priority="P0"> .......... Non-negotiable factual rules
|   +-- <content_rules priority="P1"> ...... Structure, length, title formula
|   +-- <voice priority="P2"> ............. Brand voice, banned words, tone
|   +-- <platform priority="P3"> .......... Google/Bing/Shopify format rules
+-- <output> (~500 chars) .................. JSON schema, claims, simplified self-score
+-- <gold_examples> (~2-3K chars) .......... 2-3 exemplar outputs (cacheable)

User Message (~5-15K chars per SKU):
+-- <evidence_table> ...................... Product data (runtime)
+-- <keyword_placement> ................... Keywords from search data (runtime)
+-- <category_guidance> ................... From shopping_intelligence.yaml (runtime)
+-- <product_design_story> ................ From product data + collection (runtime)
+-- <competitive_positioning> .............. From prompt_builder (runtime)
+-- <finish_context> (optional) ........... For variant generation (runtime)
+-- <output_contract> .................... Schema reference
```

### Size Comparison

| Component | Current | New | Reduction |
|-----------|---------|-----|-----------|
| System prompt | 267K chars / 57K tokens | ~12-14K chars / ~3-4K tokens | 95% |
| User prompt | ~16K chars / ~3K tokens | ~8-15K chars / ~2-4K tokens | ~0-50% |
| **Total** | **~282K chars / ~60K tokens** | **~20-29K chars / ~5-8K tokens** | **~90%** |
| Contradictions | 12 | 0 | 100% |
| Instruction:Data ratio | 17.7:1 | ~1.5:1 | 92% |

---

## 3. Constraint Hierarchy

### P0: Accuracy (Non-Negotiable)

Accuracy overrides everything. If a constraint at P1/P2/P3 conflicts with accuracy, accuracy wins.

**Scope:** Evidence-only claims, prohibited fabrications, banned content patterns.

**Key rules:**
- Every factual claim must trace to the evidence table
- Omitting a detail is always better than fabricating one
- NEVER include: weight capacity, detailed dimensions (only primary searchable dimension), competitor material names, invented category terms, keyword lists, finish counts in Google/Bing

### P1: Content Rules (Structure and Substance)

Content rules define WHAT goes into the output -- structure, length, title formula, description organization.

**Key rules:**
- Title formula: Finish first, Collection + "Collection", product function, primary dimension (only when varies), "Allied Brass" last
- Description structure: first 160 chars = hook, 160-500 = substance, 500-900 = synonyms
- Description length: 700-900 chars for Google/Bing (one target, no conflicting ranges)
- Shopify: HTML format, 250-400 words, finish-agnostic

### P2: Voice and Style

Voice rules define HOW to write. They defer to P0 (never sacrifice accuracy for engagement) and P1 (never break structure for tone).

**Key rules:**
- Confident but not arrogant, specific and concrete
- Prove with evidence, not adjectives
- Banned words: premium, luxurious, finest, exceptional, unparalleled, superior, exquisite, ultimate, exclusive
- Frame solid brass positively; never contrast with competitor materials
- No invented scenarios -- use evidence-supported scenarios only

### P3: Platform-Specific

Platform rules define WHERE the content goes. Lowest priority because platform format should never override content accuracy or quality.

**Key rules:**
- Google/Bing: plain text, variant-aware (finish in title)
- Shopify: HTML, finish-agnostic, master-SKU level
- Field isolation: never apply Shopify HTML to Google/Bing; never apply feed keyword density to Shopify

### Conflict Resolution Examples

| Scenario | P0 | P1 | P2 | Resolution |
|----------|----|----|----|----|
| Category guidance says "include weight capacity" | Do NOT include weight capacity | -- | -- | P0 wins: omit weight capacity |
| Voice says "open with scenario" but no evidence scenario | Evidence-only claims | -- | No invented scenarios | P0 wins: open with evidence-grounded detail |
| Title would be 155 chars to include all P1 elements | -- | 60-150 char title | -- | P1 enforced: trim to fit limit |
| Shopify description has great keyword but in HTML | -- | -- | -- | P3: HTML is required for Shopify |

---

## 4. What Was Distilled from Each YAML Config

### brand_voice.yaml (33 lines)

**Kept:**
- Core voice attributes: "confident but not arrogant, specific and concrete" (P2 voice)
- Banned words list (P2 voice)
- "Prove, don't claim" principle with good/bad examples (P2 voice)
- Brand truths about solid brass, concealed mounting, Louisa VA heritage (moved to evidence-only -- only include when product evidence supports it)

**Cut:**
- `competitor_contrasts` section entirely -- this is the root cause of contradiction C1 (competitor material naming). The new prompt PROHIBITS all competitor material references. The positive framing of solid brass is kept.
- `one_two_punch` -- Claude-specific marketing summary, not an LLM instruction
- "28+ designer finishes" truth -- moved to Shopify-only mention. Google/Bing descriptions are finish-specific variants where finish counts are nonsensical.
- "Open with feeling or scenario, follow with proof" -- this directly contradicted the accuracy guardrail's "DO NOT invent usage scenarios." Replaced with "Open with an evidence-grounded product detail, not a spec dump."

**Contradictions resolved:**
- C1 (competitor materials): Removed competitor_contrasts. ONE rule: "frame solid brass positively, never name competitor materials."
- C2 (28 finishes): ONE rule: "do NOT mention finish counts in Google/Bing descriptions" (they become per-finish variants). Shopify CAN mention 28 finishes as a cross-sell signal.
- C4 (emotional vs factual opening): ONE rule: "open with a concrete, evidence-grounded product detail or design story -- not a manufactured scenario and not a spec dump."
- C10 (scenarios vs prohibition): ONE rule: "buyer scenarios must come from evidence context or category guidance, never invented."

### quality_rubric.yaml (33 lines)

**Kept:**
- Three high-level criteria for simplified self-score (see Section 5):
  1. Accuracy (all claims evidence-backed)
  2. Specificity (could ONLY describe this product)
  3. Engagement (would a shopper click or keep scrolling)

**Cut:**
- Full 10-criterion scoring rubric with weights -- this is Pitfall 5 (optimizing for rubric rather than quality). The detailed rubric remains available for a SEPARATE evaluation pass.
- scoring_rules (calibration guidance for evaluators, not generators)
- grade_thresholds (evaluation infrastructure, not generation guidance)

**Contradictions resolved:**
- C11 (customer_scenario vs scenario prohibition): Removed customer_scenario from self-score. The simplified 3-criterion score doesn't ask the model to evaluate its own scenarios.
- C12 (rubric in generation prompt): Removed the full rubric from generation. Keep only 3 high-level criteria as a sanity check, not a 10-dimensional optimization target.

### shopping_intelligence.yaml (655 lines)

**Kept (in user prompt, per-category):**
- Category-specific `intent_keywords` (valuable for keyword integration)
- Category-specific `title_instruction` (valuable for product-type-specific title optimization)
- Category-specific `description_instruction` (valuable for category-specific content guidance)
- `allied_brass_usp` section distilled into system prompt brand context

**Cut:**
- `universal_rules.material_differentiator` -- named Kingston Brass, Moen, Delta by material. This feeds contradiction C1. Replaced with positive brass framing in system prompt.
- `universal_rules.description_structure` example: "not the hollow zinc tubing that loosens" -- violates competitor material prohibition. Removed.
- `universal_rules.accuracy_guardrail` -- redundant with system prompt P0 accuracy section.
- Category-level `differentiation` blocks that name competitor materials (e.g., towel bars "solid brass vs die-cast zinc")
- Category `note` fields with impression data -- useful for humans, noise for generation LLM
- `is_lost_to_rank_pct` and `monthly_impressions` -- analytics metadata, not generation guidance

**Contradictions resolved:**
- C3 (shopping_intelligence "solid brass vs die-cast zinc" vs prohibition): Removed all competitor material naming from category rules. The category guidance now says "emphasize solid brass construction" without naming what competitors use.
- C5 (weight capacity in glass shelves): Removed "weight capacity" from glass shelf description_instruction. Replaced with "glass thickness and tempered safety" as trust signals.
- C6 (two title rule sets, 30 vs 40 chars): Standardized to "product type in first 30 characters" everywhere.
- C7 (description length 600-800 vs 700-900): Standardized to "700-900 characters" in the system prompt. The JSON schema description will also be updated to "700-900 characters" to eliminate the conflict.

### finish_guide.yaml (384 lines)

**Kept:**
- Per-finish `visual`, `design_style`, `search_keywords` fields -- these provide essential context for finish integration in variant content
- Per-finish `avoid` warnings -- concise, directly useful

**Cut:**
- Per-finish `sentences` (4 examples per finish, 28 finishes = 112 example sentences) -- these are for finish SENTENCE generation (a separate task), not for full description generation. Including them bloats the prompt without helping the main generation task.
- The entire Finish Comparison Quick Reference section -- this is reference material for Claude Code, not needed in the generation prompt

**Rationale:** Finish context is already injected per-variant via the FINISH_CONTEXT_TEMPLATE in the user prompt. The system prompt needs only the principle ("weave finish naturally into first sentence, never 'Available in X. X features...'") not 112 example sentences.

### storytelling_patterns.yaml (102 lines)

**Kept:**
- Per-category `design_hooks` -- concise, evocative framing
- Per-category `feature_benefit` -- maps features to benefits
- Per-category `opening_pattern` guidance -- helps vary description openings

**Cut:**
- `customer_scenarios` -- most include invented scenarios that conflict with the accuracy guardrail. Replaced with evidence-only scenario guidance in P2 voice.
- "replacing builder-grade hollow zinc" in towel bar opening_pattern -- contradiction C4 (names competitor material). Replaced with "upgrading the hardware anchoring the room."
- "Solid brass spring mechanism won't weaken" in toilet paper holders -- contradiction C8 (mechanism fabrication). Replaced with "solid brass construction built for daily use."
- All references to "hollow zinc," "chrome-plated steel," "plastic cores" throughout -- contradiction C1.

**Contradictions resolved:**
- C4 (storytelling "replacing hollow zinc" vs prohibition): Removed all competitor material references from storytelling patterns. Opening patterns now reference positive attributes only.
- C8 (spring mechanism): Removed specific mechanism claims. Category guidance now says "mention construction quality" without naming specific mechanisms unless evidence confirms them.

### collection_stories.yaml (485 lines)

**Kept:**
- `collection_preamble` concept (distilled): "Allied Brass offers 41 coordinated collections. Use collection identity to differentiate and suggest coordination."
- Per-collection `design_aesthetic` -- the most useful field for unique descriptions
- Per-collection `style_category` -- helps position the product

**Cut:**
- Per-collection `target_buyer` -- this is marketing persona data for Claude Code, not useful for GPT-5.2 generation
- Per-collection `content_examples` -- these are Claude Code reference examples, not GPT-5.2 injection content. The gold standard examples from Supabase serve this purpose better.
- The preamble's mention of "28 finishes" -- per contradiction C2 resolution

**Rationale:** Collection context is already injected per-SKU via `customer_context` in the user prompt (from prompt_builder.py's collection narrative). The system prompt needs only the principle ("use collection identity as a differentiator") not 41 collection profiles.

### platform_bing.yaml (49 lines)

**Kept:**
- Bing-specific title rules: include synonym variant not in Google title, style descriptors
- Bing-specific description rules: front-load specs in first 200 chars, mention warranty
- `synonym_coverage` dictionary -- useful for keyword variation

**Cut:**
- `audience_signals` -- marketing persona data, not generation instructions
- `prohibited` list -- redundant with P0 accuracy section in system prompt

**Rationale:** Bing rules are consolidated into the P3 platform section of the system prompt. Only the DIFFERENCES from Google need to be stated.

### platform_shopify.yaml (48 lines)

**Kept:**
- Shopify-specific format rules: HTML required, finish-agnostic, no "Allied Brass" in title
- Description target: 250-400 words (different from Google/Bing 700-900 chars)
- Meta description rules: 140-155 chars, standalone summary
- Voice rules: "Conversion copy, not ad copy. Buyer is already on the page."

**Cut:**
- `prohibited` list -- redundant with P0 accuracy section
- "No promotional language" -- already in P0

**Rationale:** Shopify rules are consolidated into the P3 platform section of the system prompt.

---

## 5. Self-Score Decision

### Recommendation: Keep simplified self-score (3 criteria, not 10)

**Reasoning:**

The GPT-5.2 prompting guide recommends "re-scan outputs for unstated assumptions." Self-score serves this verification function. However, the current 10-criterion rubric with weights causes the model to optimize for the rubric (checking boxes) rather than for content quality (Pitfall 5, confirmed by audit finding C12).

**New self-score structure:**

```json
"self_score": {
  "accuracy": { "type": "integer", "min": 0, "max": 10,
    "description": "All claims traceable to evidence? 10=every claim sourced, 0=fabricated content" },
  "specificity": { "type": "integer", "min": 0, "max": 10,
    "description": "Could this ONLY describe this exact product? 10=unmistakable, 0=any competitor's listing" },
  "engagement": { "type": "integer", "min": 0, "max": 10,
    "description": "Would a shopper click or keep scrolling? 10=compelling, 0=invisible" }
}
```

**Why 3 and not 10:**
- 3 criteria provide a useful sanity check without becoming an optimization target
- These 3 map to the most important dimensions: factual correctness, product differentiation, and conversion potential
- The 7 removed criteria (hook_quality, competitive_diff, keyword_integration, customer_scenario, emotional_resonance, platform_compliance, finish_integration, variety_score) either overlap with these 3 or are better evaluated in a separate pass
- customer_scenario is removed entirely because it conflicted with the scenario prohibition (C11)

**Separate evaluation pass (deferred to v1.3a implementation):**
The full 10-criterion rubric should be used as a SEPARATE API call after generation. This separates the "generate" and "evaluate" concerns, eliminating the perverse incentive to write content that scores well on a rubric rather than content that converts shoppers.

---

## 6. Gold Examples Placement

### Recommendation: Gold examples in system prompt (static, cacheable)

**Reasoning:**

Per GPT-5.2 best practices, the system prompt is cached by OpenAI across requests. Gold examples are static (they don't change per SKU), so placing them in the system prompt:

1. **Caching benefit:** The cached prefix includes the examples, so they're processed once and reused across all SKUs in a batch. Moving them from the user prompt (where they were) to the system prompt saves reprocessing cost on every request.

2. **Consistency:** All SKUs see the same examples, creating consistent quality anchoring.

3. **Size budget:** 2-3 gold examples at ~800 chars each = ~2.4K chars. This fits comfortably within our 15K system prompt budget.

**Implementation:**

Gold examples are fetched from Supabase `prompt_templates` table (field: `gold_standard_examples`). They should be formatted as:

```xml
<gold_examples>
<example sku="920D-6" platform="google">
<title>Satin Brass Mercury Collection Paper Towel Holder - Wall Mount Solid Brass - Allied Brass</title>
<description>[Full gold standard description here]</description>
</example>
[2-3 examples total, covering different categories]
</gold_examples>
```

**Note:** If gold examples are placed in the system prompt, the `{gold_examples}` placeholder in the user prompt template should be removed. The user prompt template in this plan still includes it as a fallback -- the implementation in Phase 24 should choose one location.

**Update for implementation:** Given that gold examples are currently loaded dynamically from Supabase per-request (they may be updated), a pragmatic first step is to keep them in the user prompt but test a system-prompt variant in A/B testing. If the cache hit rate improves meaningfully, migrate permanently.

---

## 7. Migration Plan

### Files to Change

#### `src/feedops/pipeline/prompts.py`

**Change:** Replace `SYSTEM_PROMPT` constant with the new CTCO-structured prompt (~12-14K chars). Replace `CANDIDATE_SCHEMA` self_score section with simplified 3-criterion version. Update `google_description` schema field from "target 600-800 characters" to "target 700-900 characters" to eliminate contradiction C7.

**Change:** Update `USER_PROMPT_TEMPLATE` to remove `{segment_strategy_guidance}` placeholder (absorbed into system prompt) and optionally remove `{gold_examples}` if placed in system prompt.

#### `src/feedops/api/prompt_loader.py`

**Change:** Modify `get_system_prompt()` to STOP calling `load_skills_for_prompt()` when using the new prompt architecture. Add a feature flag or prompt version parameter to support A/B testing:

```python
def get_system_prompt(mode="batch", platform=None, prompt_version="v2"):
    if prompt_version == "v2":
        return NEW_SYSTEM_PROMPT  # From prompts.py, ~12-14K chars
    else:
        # Legacy: base + skills injection
        prompt = CANONICAL_SYSTEM_PROMPT
        skill_content = load_skills_for_prompt(mode=mode, platform=platform)
        if skill_content:
            prompt = prompt + "\n\n" + skill_content
        return prompt
```

#### `src/feedops/api/prompt_builder.py`

**Change:** Minimal changes. The user prompt assembly logic remains largely the same since it's already well-structured. Key changes:
- Remove `segment_strategy_guidance` from the competitive positioning block (absorbed into system prompt)
- Update `competitive_block` to remove all competitor material references (positive-only brass framing)
- Pass `prompt_version` parameter through to `get_system_prompt()`

#### `src/feedops/pipeline/skill_loader.py`

**Change:** No changes to the file itself. The skill loader is bypassed (not called) when `prompt_version="v2"`. It remains available for the legacy path and for Claude Code agent workflows where SKILL.md files are genuinely useful.

### A/B Testing Strategy

**Three variants for Plan 03:**

1. **Control (current):** Full SKILL.md injection, 267K system prompt, 10-criterion self-score
2. **New v2:** CTCO prompt, ~12-14K system prompt, 3-criterion self-score, gold examples in user prompt
3. **New v2 + system examples:** Same as v2 but gold examples moved to system prompt

**Implementation:** The `prompt_version` parameter controls which path is used. No code is deleted -- both paths coexist for the A/B test period.

**SKU selection for A/B test (Plan 03):**
- 3 representative SKUs from evaluation set (different failure modes)
- 3-5 unseen SKUs (not in the 10 evaluation SKUs) for generalization testing

### Backward Compatibility

- The old prompt path is preserved behind `prompt_version="v1"` (default during rollout)
- No production behavior changes until the A/B test confirms improvement
- skill_loader.py, all SKILL.md files, and all YAML configs remain unchanged
- The new system prompt is added alongside, not replacing, the existing constants

---

## 8. Robert's Concerns Checklist

Every concern from evaluation Rounds 1-3 is mapped to a specific section in the new prompt.

| Robert's Concern | Source | New Prompt Section | How Addressed |
|---|---|---|---|
| Competitor material references ("die-cast zinc") | Round 2: 6/10 descriptions | P0 Accuracy: explicit prohibition | Single authoritative rule: "NEVER name competitor materials." All contradictory sources (brand_voice, shopping_intelligence, storytelling_patterns) stripped of competitor names. |
| Weight capacity in descriptions | Round 2: glass shelf SKUs | P0 Accuracy: explicit prohibition | "Do NOT include weight capacity -- creates doubt, not confidence." Removed from glass shelf category guidance. |
| Excessive dimensions | Round 2: multiple SKUs | P0 Accuracy: explicit prohibition | "Only the primary searchable dimension (e.g., length for towel bars, diameter for mirrors)." Category guidance no longer says "state both width and depth." |
| "Heritage bathroom fixtures" and invented terms | Round 2: multiple SKUs | P0 Accuracy: explicit prohibition | Banned phrase in P0. Not in any positive instruction anywhere. |
| Keyword stuffing ("also searched as" patterns) | Rounds 1-3: pervasive | P0 Accuracy: explicit prohibition + P1 Content: keyword integration rule | "All keywords must be integrated naturally, one per sentence, distributed across the copy. NEVER use 'also searched as' or keyword list patterns." |
| Monotonous structure (cookie-cutter templates) | Rounds 1-3: pervasive | P2 Voice: variety requirement + simplified self-score | Over-instruction was the root cause. With 95% fewer instructions, the model has room to vary its output. The 3-criterion self-score doesn't enforce a rigid structure. |
| Product type accuracy (1024/1020 misidentified) | Round 2: specific SKUs | P0 Accuracy: evidence-only rule | "Product type must come from evidence table, not inference." This was a model inference error, not a data error. |
| Finish count mentions in per-finish variants | Round 2: multiple SKUs | P0 Accuracy: explicit prohibition | "Do NOT mention '28 finishes' or finish variety counts in Google/Bing descriptions -- these are expanded to finish-specific variants." |
| Title formula not followed | Rounds 1-3: inconsistent | P1 Content: single title formula | ONE authoritative title formula: "Finish first, Collection + Collection, product function, primary dimension (only when varies), Allied Brass last." No competing SKILL.md title rules. |
| Filler sentences / word count padding | Rounds 1-3: pervasive | Design philosophy: less is more + P1 Content: structural requirements | Instead of character range targets, descriptions have structural requirements (hook in first 160 chars, substance in 160-500, synonyms in 500-900). Each section has a purpose. |
| Generic openings ("This [product]...") | Rounds 1-3: pervasive | P1 Content: opening rule | "NEVER open with 'This [product type]...' followed by a dimension. Open with WHY the shopper should care -- a concrete design detail or product story from the evidence." |
| Self-score inflation (consistently 85+) | Rounds 1-2: observed | Self-score simplification | Reduced from 10 criteria to 3. Removed customer_scenario (conflicted with prohibition). Calibration: "A description that follows rules but is generic scores 4-5, not 8+." |

---

## Appendix A: Contradiction Resolution Summary

| # | Contradiction | Severity | Resolution | Winner |
|---|---|---|---|---|
| C1 | Competitor material naming vs prohibition | CRITICAL | Removed all competitor material references from brand_voice, shopping_intelligence, storytelling_patterns. ONE rule in P0: never name competitor materials. | Prohibition wins |
| C2 | 28 finishes mention vs suppression | CRITICAL | Google/Bing: prohibited (variants are finish-specific). Shopify: allowed (master-SKU, cross-sell context). Platform-specific resolution. | Context-dependent |
| C3 | Shopping intelligence "solid brass vs zinc" vs prohibition | CRITICAL | Removed competitor material naming from category rules. Category guidance says "emphasize solid brass construction" without naming alternatives. | Prohibition wins |
| C4 | Emotional opening vs factual grounding | HIGH | ONE rule: "open with evidence-grounded product detail or design story." Scenarios allowed only when evidence-supported. | Evidence-first |
| C5 | Detailed dimensions vs dimension prohibition | HIGH | ONE rule: "only primary searchable dimension." Removed multi-dimension guidance from glass shelf and towel shelf categories. | Prohibition wins |
| C6 | Two competing title rule sets | HIGH | ONE title formula in P1. Standardized "product type in first 30 characters." Removed competing SKILL.md title rules. | SYSTEM_PROMPT formula wins |
| C7 | Description length 600-800 vs 700-900 | HIGH | ONE target: "700-900 characters" for Google/Bing. Schema description updated to match. | 700-900 wins |
| C8 | Product mechanism fabrication | MEDIUM | ONE rule: "do NOT claim specific mechanisms unless evidence confirms them." Removed "spring mechanism" from storytelling patterns. | Prohibition wins |
| C9 | First sentence competition | MEDIUM | ONE rule: "first sentence: concrete product detail with key dimension and material." No competing first-sentence rules. | Merged into one |
| C10 | Redundant finish integration at different detail levels | MEDIUM | ONE principle in P2: "weave finish naturally into first sentence." Detailed per-finish context provided in user prompt only for variants. | System prompt principle + user prompt detail |
| C11 | Self-score customer scenario vs scenario prohibition | MEDIUM | Removed customer_scenario from self-score. 3-criterion simplified score. | Prohibition wins |
| C12 | Scoring rubric in generation prompt | MEDIUM | Removed full 10-criterion rubric from generation. Simplified to 3 criteria. Full rubric reserved for separate evaluation pass. | Separation of concerns |

---

## Appendix B: Token Budget Allocation

| Section | Target Chars | Target Tokens | % of System Prompt |
|---------|-------------|---------------|-------------------|
| `<context>` | 400 | ~100 | 3% |
| `<task>` | 300 | ~75 | 2% |
| `<constraints>` total | 9-11K | ~2,500-3,000 | 72% |
| -- P0 Accuracy | 2,000 | ~500 | 15% |
| -- P1 Content Rules | 3,500 | ~900 | 27% |
| -- P2 Voice | 1,500 | ~400 | 12% |
| -- P3 Platform | 2,500 | ~650 | 19% |
| `<output>` | 500 | ~125 | 4% |
| `<gold_examples>` (if included) | 2,500 | ~625 | 19% |
| **Total** | **~13-15K** | **~3,400-3,900** | **100%** |

---

*Architecture designed from scratch for GPT-5.2 based on Plan 01 audit findings and GPT-5.2 prompting guide best practices.*
