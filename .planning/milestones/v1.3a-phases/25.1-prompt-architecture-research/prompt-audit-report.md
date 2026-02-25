# Phase 25.1 Track 1: Internal Prompt Audit Report

**Date:** 2026-02-23
**SKU tested:** 920D-6 (Mercury Collection Paper Towel Holder)
**Tokenizer:** tiktoken o200k_base (GPT-5.2 encoding)
**Method:** `scripts/dump_assembled_prompt.py` -- full runtime prompt capture

---

## 1. Prompt Size Analysis (Exact Token Counts)

### Summary

| Component | Characters | Tokens | % of Total |
|-----------|-----------|--------|------------|
| **System message** | 266,242 | 57,504 | 94.7% |
| **User message** | 15,904 | 3,248 | 5.3% |
| **TOTAL** | **282,146** | **60,752** | **100%** |

### System Message Breakdown

| Component | Characters | Tokens | % of System |
|-----------|-----------|--------|-------------|
| SYSTEM_PROMPT base (prompts.py) | 6,406 | 1,328 | 2.4% |
| google-shopping-content SKILL.md | 47,555 | 10,219 | 17.9% |
| shopify-conversion-content SKILL.md | 45,811 | 10,015 | 17.2% |
| finish-expertise SKILL.md | 40,475 | 8,607 | 15.2% |
| quality-evaluation SKILL.md | 39,950 | 9,169 | 15.0% |
| bing-shopping-content SKILL.md | 36,667 | 7,760 | 13.8% |
| allied-brass-brand-expert SKILL.md | 21,480 | 4,582 | 8.1% |
| product-storytelling SKILL.md | 19,345 | 4,095 | 7.3% |
| collection-storytelling SKILL.md | 8,537 | 1,729 | 3.2% |
| **Total skills** | **259,820** | **56,176** | **97.6%** |

### Critical Finding

The system prompt is **57,504 tokens** -- 97.6% of which is SKILL.md content originally written for Claude Code, not GPT-5.2. The user prompt (the actual per-SKU data) is only **3,248 tokens** (5.3%). This is a **17.7:1 instruction-to-data ratio** -- meaning GPT-5.2 receives 17.7 tokens of instructions for every 1 token of actual product data.

For comparison, the GPT-5.2 prompting guide recommends concise, non-contradictory instructions. The target architecture should aim for ~3-4K tokens of system prompt (a 95% reduction).

---

## 2. Contradiction Map (12 Contradictions with Severity Ratings)

Each contradiction is documented with exact quotes from the dumped prompt.

### CRITICAL Severity (Directly Causes Observed Bad Output)

**C1: Competitor Material Naming vs. Prohibition**

| Source A | Source B |
|----------|----------|
| `brand_voice.yaml` (in allied-brass-brand-expert skill): "die-cast zinc with decorative plating" as competitor contrast | SYSTEM_PROMPT `<accuracy_guardrail>`: "Do NOT name competitor materials: 'die-cast zinc,' 'zinc alloy,' 'plated alternatives,' 'chrome-plated steel,' 'hollow zinc'" |
| `shopping_intelligence.yaml` (in user prompt): "Kingston Brass uses die-cast zinc" | allied-brass-brand-expert SKILL.md `## CRITICAL: Competitor Material Prohibition`: "NEVER mention competitor materials by name in ANY content" |
| storytelling_patterns.yaml concepts: "replacing builder-grade hollow zinc" | SYSTEM_PROMPT `<brand_voice>`: Banned phrases include "common die-cast zinc" |

**Impact:** 68 occurrences across the prompt. The model receives 3+ instructions TO name competitor materials and 2+ instructions NOT TO. Majority signal wins -- "die-cast zinc" appeared in 6/10 Round 2 descriptions. This is the #1 cause of rejected content.

**Severity: CRITICAL** -- Directly produced content both evaluators rejected.

---

**C2: 28 Finishes Mention vs. Suppression**

| Source A | Source B |
|----------|----------|
| allied-brass-brand-expert SKILL.md: "28+ finishes across virtually every product" | SYSTEM_PROMPT `<accuracy_guardrail>`: "Do NOT mention '28 finishes' or finish variety counts in Google/Bing descriptions" |
| brand_voice.yaml: "Available in 28 finishes -- from timeless Polished Chrome to statement-making Mediterranean Blue" | prompt_builder.py competitive_block: "Do NOT mention '28 finishes,' '28+ finishes,' or finish variety counts" |

**Impact:** 147 finish-related occurrences in the system prompt. The skill provides multiple positive examples of mentioning "28 finishes" while the SYSTEM_PROMPT and prompt_builder explicitly prohibit it for Google/Bing. GPT-5.2 sees the skill examples as instruction-by-demonstration and includes finish counts despite the prohibition.

**Severity: CRITICAL** -- Google/Bing descriptions get expanded to finish-specific variants, making "28 finishes" references nonsensical on an "Antique Bronze" listing.

---

**C3: Weight Capacity Inclusion vs. Exclusion**

| Source A | Source B |
|----------|----------|
| shopping_intelligence.yaml (Glass Shelves category): "Glass thickness and weight capacity" as key differentiator | SYSTEM_PROMPT `<accuracy_guardrail>`: "Do NOT include weight capacity in descriptions -- it creates consumer doubt rather than confidence" |

**Impact:** The model includes weight capacity from category-specific rules, directly contradicting the evaluation-feedback prohibition. Glass shelf descriptions end up with "supports up to 15 pounds" despite the ban.

**Severity: CRITICAL** -- Robert specifically flagged this in Round 2 evaluation.

---

### HIGH Severity (Likely Contributes to Generic Output)

**C4: Emotional Opening vs. Factual Grounding**

| Source A | Source B |
|----------|----------|
| brand_voice.yaml: "Open with feeling or scenario, follow with proof" | SYSTEM_PROMPT `<creative_direction>`: "DO NOT invent usage scenarios, room contexts, or product features that aren't supported by the evidence table" |
| product-storytelling SKILL.md: buyer scenario patterns (bathroom renovation, guest bath upgrade) | SYSTEM_PROMPT `<accuracy_guardrail>`: "DO NOT invent usage contexts" |
| quality_rubric (self_score): `customer_scenario: "real buying situation"` scores 7-10 | SYSTEM_PROMPT: "DO NOT invent usage scenarios" |

**Impact:** The model tries to create engaging scenarios (skills tell it to) but self-censors (SYSTEM_PROMPT tells it not to), producing awkward compromises like "When upgrading your bathroom, consider..." -- generic enough to avoid prohibition but not specific enough to be engaging.

**Severity: HIGH** -- Produces the "bland compromise" pattern seen in monotonous descriptions.

---

**C5: Detailed Dimensions vs. Dimension Prohibition**

| Source A | Source B |
|----------|----------|
| shopping_intelligence.yaml: "State both width and depth dimensions" (for shelves) | SYSTEM_PROMPT `<accuracy_guardrail>`: "Do NOT include detailed dimensions (width, height, projection, depth) -- only the primary searchable dimension" |

**Impact:** Category rules push for multiple dimensions while the guardrail limits to one. The model either includes too many dimensions or omits all of them.

**Severity: HIGH** -- Creates inconsistent dimension handling across categories.

---

**C6: Two Competing Title Rule Sets**

| Source A | Source B |
|----------|----------|
| google-shopping-content SKILL.md: Extensive "Robert's Title Formula" with detailed rules, 5 variations, bad-to-good transformations (2,500+ chars) | SYSTEM_PROMPT `<platform_rules>`: Simpler title rules in ~200 chars |
| SKILL.md: "Product type in first 40 characters" | SYSTEM_PROMPT: "Product type in first 30 chars" |

**Impact:** Two title rule sets with different thresholds (30 vs 40 chars for product type placement). The model attempts to satisfy both, sometimes producing titles that satisfy neither cleanly.

**Severity: HIGH** -- 11 occurrences of title rules across the prompt.

---

**C7: Description Length Targets Disagree**

| Source A | Source B | Source C |
|----------|----------|----------|
| SYSTEM_PROMPT `<platform_rules>`: "700-900 chars target" | shopping_intelligence.yaml: "700-900 characters (approximately 800)" | CANDIDATE_SCHEMA description field: "target 600-800 characters" |

**Impact:** Three different length targets. The JSON schema says 600-800, the SYSTEM_PROMPT and YAML say 700-900. The model sees conflicting constraints in the schema it's trying to fill vs. the instructions.

**Severity: HIGH** -- Produces inconsistent description lengths.

---

### MEDIUM Severity (Potential Issue)

**C8: Product Mechanism Fabrication**

| Source A | Source B |
|----------|----------|
| storytelling_patterns.yaml: "Solid brass spring mechanism won't weaken" | SYSTEM_PROMPT `<accuracy_guardrail>`: "DO NOT invent product mechanisms (e.g., 'spring-loaded', 'quick-release') unless evidence confirms them" |

**Severity: MEDIUM** -- Only triggers for specific categories with spring mechanisms in storytelling patterns.

---

**C9: First Sentence Competition**

| Source A | Source B |
|----------|----------|
| SYSTEM_PROMPT `<creative_direction>`: "first sentence should anchor on a concrete, verifiable design detail" | SYSTEM_PROMPT `<platform_rules>`: "Lead with concrete product statement in first 160 chars" |

**Severity: MEDIUM** -- Both agree in spirit but create ambiguity about what "leads" the opening.

---

**C10: Redundant Finish Integration at Different Detail Levels**

| Source A | Source B |
|----------|----------|
| finish-expertise SKILL.md: 40,475 chars of detailed finish integration patterns | SYSTEM_PROMPT `<platform_rules>`: Brief finish rules (~100 chars) |

**Severity: MEDIUM** -- Not contradictory, but the 40K-char skill overwhelms the brief SYSTEM_PROMPT guidance.

---

**C11: Self-Score Customer Scenario vs. Scenario Prohibition**

| Source A | Source B |
|----------|----------|
| CANDIDATE_SCHEMA self_score.customer_scenario: "Real buying situation: 0=spec dump, 10=specific resonant scenario" | SYSTEM_PROMPT: "DO NOT invent usage scenarios" |

**Severity: MEDIUM** -- The model is scored on creating scenarios it's told not to create. This creates a perverse optimization incentive.

---

**C12: Scoring Rubric in Generation Prompt**

| Source A | Source B |
|----------|----------|
| quality-evaluation SKILL.md: 39,950 chars of detailed scoring rubric with anchors and examples | SYSTEM_PROMPT `<scoring_rubric>`: Brief calibration guidance |

**Severity: MEDIUM** -- The generation prompt contains the full evaluation rubric. The model optimizes for the rubric (checking boxes) rather than for shopper conversion. This is Pitfall 5 from the research doc.

---

## 3. Over-Instruction Hotspots

### Competitor Materials -- 68 occurrences

The single most over-instructed topic. Appears in:

| Location | Type | Occurrences | Signal |
|----------|------|-------------|--------|
| allied-brass-brand-expert SKILL.md | Prohibition section + competitor contrasts | ~25 | Mixed (prohibit AND provide contrast language) |
| SYSTEM_PROMPT `<accuracy_guardrail>` | Prohibition | 3 | Prohibit |
| SYSTEM_PROMPT `<brand_voice>` | Banned phrases | 2 | Prohibit |
| shopping_intelligence.yaml (via user prompt) | Category differentiation | 5 | Include (names Kingston Brass, zinc) |
| storytelling_patterns (in product-storytelling SKILL.md) | Opening patterns | ~8 | Include ("replacing hollow zinc") |
| google-shopping-content SKILL.md | Differentiation guidance | ~15 | Mixed |
| bing-shopping-content SKILL.md | Similar differentiation | ~10 | Mixed |

**Result:** The model receives ~35 signals to INCLUDE competitor materials and ~33 signals to EXCLUDE them. The near-50/50 split explains why "die-cast zinc" appears unpredictably.

### Finish Handling -- 147 occurrences

The most voluminous topic by raw occurrence count:

| Location | Characters | Notes |
|----------|-----------|-------|
| finish-expertise SKILL.md | 40,475 | Entire skill devoted to finish handling |
| SYSTEM_PROMPT platform_rules | ~200 | Brief finish requirements |
| brand_voice.yaml (in skill) | ~400 | "28+ finishes" selling point |
| prompt_builder.py finish context | ~600 | Dynamic per-request |
| prompts.py FINISH_CONTEXT_TEMPLATE | ~800 | For variant generation |

Total: ~42,475 chars (~9,000 tokens) devoted to finish handling -- 16% of the entire prompt.

### Description Length -- 20 occurrences across 3 different targets

| Source | Target |
|--------|--------|
| CANDIDATE_SCHEMA | 600-800 chars |
| SYSTEM_PROMPT | 700-900 chars |
| shopping_intelligence.yaml | 700-900 chars |
| google-shopping-content SKILL.md | 700-900 chars |

Three sources agree on 700-900, but the JSON schema the model fills says 600-800. The schema description is the closest instruction to the output format, so it often wins.

### Title Rules -- 11 occurrences with threshold disagreement

| Source | Product Type Position | Overall Length |
|--------|----------------------|----------------|
| SYSTEM_PROMPT | First 30 chars | 60-150 chars |
| google-shopping-content SKILL.md | First 40 chars | 60-150 chars |
| bing-shopping-content SKILL.md | First 30 chars | Not specified explicitly |

---

## 4. GPT-5.2 Anti-Pattern Scorecard

Scored against the GPT-5.2 Prompting Guide best practices (0-10 scale, where 10 = fully compliant).

### Scoring Methodology

Each criterion is scored based on the dumped prompt analysis. Evidence is cited for each score.

| Criterion | Score | Evidence |
|-----------|-------|----------|
| **CTCO Structure Compliance** | 3/10 | The SYSTEM_PROMPT has XML-tagged sections (good), but the massive skill injection breaks the CTCO flow. There is no clear Context-Task-Constraints-Output hierarchy. The user prompt has a `<task>` tag but constraints are buried in 260K chars of system prompt. |
| **Over-Instruction Level** | 1/10 | 57,504 tokens of system prompt is extreme over-instruction. GPT-5.2 guide: "If your instructions are sloppy, it defaults to safe, generic, low-effort output." With 12 contradictions, the model produces the bland intersection of all instructions. Target: <4K tokens. |
| **Contradiction Count** | 2/10 | 12 identified contradictions, 3 CRITICAL (directly causing rejected content), 4 HIGH (contributing to generic output). Zero contradictions is the target. |
| **Signal-to-Noise Ratio** | 4/10 | 64% signal, 36% noise (95,463 chars / 20,649 tokens of Claude-specific metadata). Even the "signal" portion contains massive redundancy (68 competitor material mentions, 147 finish mentions). Effective signal is likely 30-40%. |
| **Verbosity Control** | 2/10 | Description length target appears in 3 different values (600-800, 700-900). No use of concrete sentence counts or `text.verbosity` parameter. GPT-5.2 guide recommends "3-6 sentences" or "<=5 tagged bullets" over character ranges. |
| **Example Placement Efficiency** | 4/10 | Gold standard examples are in the user prompt (good for per-SKU variation, bad for caching). The google-shopping-content skill contains 10 full examples (~6,000+ chars) in the system prompt that ARE cached. However, these examples demonstrate patterns the SYSTEM_PROMPT then prohibits (e.g., competitor material references in examples). |

**Composite Score: 2.7/10** -- The current prompt architecture is fundamentally misaligned with GPT-5.2 best practices.

---

## 5. Claude-Specific Content Inventory (Noise for GPT-5.2)

Content in SKILL.md files that is irrelevant to GPT-5.2 runtime generation.

### By Skill

| Skill | Claude-Specific Chars | Claude-Specific Tokens | % of Skill |
|-------|----------------------|----------------------|------------|
| google-shopping-content | 25,039 | 5,418 | 52.7% |
| shopify-conversion-content | 23,279 | 5,145 | 50.8% |
| bing-shopping-content | 19,609 | 4,170 | 53.5% |
| product-storytelling | 9,129 | 1,964 | 47.2% |
| allied-brass-brand-expert | 9,038 | 1,897 | 42.1% |
| quality-evaluation | 8,540 | 1,905 | 21.4% |
| collection-storytelling | 540 | 100 | 6.3% |
| finish-expertise | 289 | 50 | 0.7% |
| **TOTAL** | **95,463** | **20,649** | **36.7%** |

### By Content Type

| Content Type | Chars | Tokens | Notes |
|--------------|-------|--------|-------|
| YAML frontmatter (---...---) | ~82,000 | ~17,500 | Skill metadata, descriptions, name fields -- all Claude Code routing |
| Companion Skills sections | ~2,800 | ~570 | Cross-references to other skills -- meaningless to GPT-5.2 |
| Skill identity preambles | ~350 | ~66 | "This skill is the source of truth for..." |
| Invocation guidance | ~10,000 | ~2,500 | "Use this skill whenever..." patterns embedded throughout |

### Key Insight

The YAML frontmatter detection is conservative -- it only catches `---..---` blocks. Much of the SKILL.md narrative content is also written for Claude Code agents (explaining when and how to apply guidance) rather than providing direct instructions to an LLM generating content. A manual review suggests the true Claude-specific noise is closer to **40-50%** of the skill content, not the 36.7% detected by pattern matching.

---

## 6. Top 5 Highest-Impact Changes (Ranked by Expected Quality Improvement)

### 1. Replace SKILL.md Injection with Purpose-Built GPT-5.2 Prompt (CRITICAL)

**Expected impact:** Eliminates 12 contradictions, removes 95K chars of noise, reduces system prompt from 57K tokens to ~3-4K tokens.

**What to do:** Build a new system prompt from scratch using CTCO framework. Distill the essential guidance from all 8 skills into ~12-15K chars of non-contradictory, hierarchically-organized instructions. Use YAML configs (already exist at `src/feedops/config/*.yaml`) as the distilled injection source.

**Why highest priority:** Every other improvement is marginal if the model still receives 260K chars of contradictory instructions. Over-instruction is the root cause of generic, keyword-stuffed output -- not missing rules.

### 2. Resolve All Contradictions to Single Authoritative Instructions (CRITICAL)

**Expected impact:** Eliminates the "bland compromise" pattern where GPT-5.2 averages conflicting instructions.

**Key resolutions needed:**
- Competitor materials: ONE instruction -- "frame solid brass positively, never name competitor materials"
- 28 finishes: ONE instruction -- context-dependent (OK for Shopify, prohibited for Google/Bing)
- Description length: ONE target -- 700-900 chars for Google/Bing, remove conflicting 600-800 from schema
- Title rules: ONE product-type threshold -- first 30 chars (standardize)
- Scenarios: ONE policy -- "use scenarios from evidence only, do not invent" (resolve the generate-vs-prohibit conflict)

### 3. Separate Generation from Evaluation (HIGH)

**Expected impact:** Eliminates the "checking boxes" pattern where GPT-5.2 optimizes for its own scoring rubric rather than for shopper conversion.

**What to do:** Remove self_score from the generation prompt. Remove quality-evaluation SKILL.md (39,950 chars) from the generation system prompt entirely. Use a separate evaluation pass (different API call) if scoring is needed.

**Why important:** With self_score in the prompt, the model writes descriptions that score well on 10 criteria rather than descriptions that make shoppers click. This is Pitfall 5 from the research doc. The quality-evaluation skill alone consumes 9,169 tokens (15% of system prompt).

### 4. Move Category-Specific Guidance to User Prompt, Gold Examples to System Prompt (HIGH)

**Expected impact:** Improves cache hit rates and ensures per-SKU context is correctly scoped.

**What to do:**
- Gold standard examples: Move to system prompt (static, cacheable across all SKUs)
- Category-specific rules: Keep in user prompt (varies per SKU)
- Shopping intelligence: Keep in user prompt (varies per category)

**Why important:** Currently, gold examples are in the user prompt (breaks cache), while category rules that should be per-SKU-dynamic are partially baked into skills (cached incorrectly). Reversing this improves both cache efficiency and instruction relevance.

### 5. Use Concrete Verbosity Controls Instead of Character Ranges (MEDIUM)

**Expected impact:** More consistent description lengths with fewer "padding" sentences.

**What to do:** Replace "target 700-900 characters" with specific structural requirements: "Google description: 3-5 sentences. First sentence: product hook with key dimension. Sentences 2-3: construction and design details. Final sentence: collection coordination or keyword synonym."

**Why important:** Character ranges cause GPT-5.2 to pad content to hit minimums. Sentence-count constraints produce tighter, more purposeful writing. The GPT-5.2 guide recommends "3-6 sentences" over vague character targets.

---

## Appendix: Prompt Dump Locations

- Full system prompt: `/tmp/prompt_dump_system.txt` (266,242 chars)
- Full user prompt: `/tmp/prompt_dump_user.txt` (15,904 chars)
- Dump script: `scripts/dump_assembled_prompt.py` (reusable for future audits)
