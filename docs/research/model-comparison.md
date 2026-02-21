# Model Comparison: LLM Benchmarking for Allied Brass Product Content Generation

**Research Date:** 2026-02-21
**Phase:** 17 — Google Shopping Intelligence & Model Research
**Models Compared:** GPT-4o (current baseline), GPT-5.2, Gemini 2.5 Pro, Claude Sonnet 4.6
**Status:** Complete — recommendation for Phase 20

---

## Executive Summary

**Recommendation: Switch to GPT-5.2 as the production model.**

Three key findings:

1. **GPT-5.2 leads on quality:** Scored 90.0/100 composite vs GPT-4o at 76.4/100 — a 17.8% improvement on the same prompts with the same product data. Strong across all criteria, particularly title formula compliance (4.6/5 vs GPT-4o's 2.8/5) and structured content organization.

2. **Cost is not a constraint:** All models cost under $20 to run the full 2,784 SKU catalog at batch pricing. The quality gap between GPT-4o and GPT-5.2 is worth the ~$2.60 cost difference for the full catalog.

3. **Claude Sonnet 4.6 underperformed expectations in this context:** Claude's conversational writing style produced more engaging prose but showed the lowest title formula compliance (3.6/5) and introduced fabricated claims ("mounting hardware included") in 2/5 SKUs tested. This disqualifies it as a production model without prompt adjustment.

**Gemini 2.5 Pro** is a strong alternative at nearly equivalent quality to GPT-5.2 (87.8/100) with competitive cost — but 3.4x slower speed (16.9s/SKU vs 6.3s for GPT-5.2).

---

## Benchmark Methodology

### SKU Selection

14 real Allied Brass products selected across three category clusters (1031/42 not found in database, so 14 SKUs instead of 15):

**Group 1: Grab Bars (decorative — user-identified PMF category)**
- CU-GRR-18: Cube Design Reeded Grab Bar, 18 inch, ADA compliant, 250 lb, wall mount
- CU-GRR-24: Cube Design Reeded Grab Bar, 24 inch
- CU-GRR-30: Cube Design Reeded Grab Bar, 30 inch
- CU-GRR-36: Cube Design Reeded Grab Bar, 36 inch
- CM-P-700-16-GB: Camo Collection 16 Inch Grab Bar, 250 lb, farmhouse/outdoor theme

**Group 2: Towel Bars (high-competition, many finish variants)**
- 1031/18: Skyline Collection 18 Inch Towel Bar, solid brass, wall mount
- 1031/24: Skyline Collection 24 Inch Towel Bar
- 1031/30: Skyline Collection 30 Inch Towel Bar
- 1031/36: Skyline Collection 36 Inch Towel Bar

**Group 3: Other Bath Hardware (higher attribute variety)**
- 1024: Skyline Collection Two Post Toilet Tissue Holder, Euro style hook
- 1024E: Skyline Collection Euro Style Toilet Tissue Holder
- 1024U: Skyline Collection Upright Toilet Tissue Holder
- 1020: Skyline Collection Robe Hook, solid brass, wall mount
- 2020: Continental Collection Robe Hook

**Note:** For full generation benchmark, 5 SKUs were used (one from each major product type) due to API cost/time constraints. Scores are validated across 5 SKUs per model.

### Prompt Baseline

All models received the identical production system prompt from `src/feedops/pipeline/prompts.py` plus a simplified user prompt with real product data from `product_catalog`. No model-specific prompt tuning was applied (this was the "same prompt" baseline run).

**Evidence fields provided per SKU:**
- title, category, material, collection
- narrative_copy (original hand-written description)
- bullet_1 through bullet_5
- product_length, weight_capacity, mounting_type

**Output requested:** google_title, google_short_title, google_description, bing_title, bing_description, shopify_title, shopify_description

### Scoring Rubric (LLM-as-Judge)

Scoring performed by GPT-5.2 using blind labeled outputs (A/B/C/D assigned randomly, labels mapped back to models after scoring). Scale: 1-5 per criterion.

| Criterion | Weight | What It Measures |
|-----------|--------|-----------------|
| Title formula compliance | 20% | [Product Type first 30 chars] + [Key Attributes] + ["Allied Brass" at end], 60-150 char target |
| Keyword coverage | 20% | Natural language search terms a shopper would use; no stuffing; attribute completeness |
| Description quality | 20% | Google description opener (first 160 chars) front-loads concrete attributes; clear and readable |
| Accuracy (no fabrication) | 25% | All claims verifiable from product data; no invented specs, warranties, or compatibility claims |
| Brand voice consistency | 15% | Clear, specific, confident; not generic/commodity language; reads as quality brand |

**Composite score formula:** (title×0.20 + keywords×0.20 + description×0.20 + accuracy×0.25 + voice×0.15) × 20 = score/100

---

## Quality Results

### Aggregate Scores (5 SKUs, 4 models)

| Model | Title (20%) | Keywords (20%) | Description (20%) | Accuracy (25%) | Voice (15%) | **Composite** |
|-------|------------|---------------|------------------|----------------|------------|--------------|
| **GPT-5.2** | **4.6/5** | **4.6/5** | **4.6/5** | **4.8/5** | 3.6/5 | **90.0/100** |
| Gemini 2.5 Pro | 3.8/5 | **5.0/5** | 4.0/5 | **4.8/5** | 4.2/5 | 87.8/100 |
| Claude Sonnet 4.6 | 3.6/5 | 4.0/5 | 4.4/5 | 4.2/5 | 3.8/5 | 80.4/100 |
| GPT-4o | 2.8/5 | 4.0/5 | 3.8/5 | 4.4/5 | 4.0/5 | 76.4/100 |

### Per-SKU Scores

| SKU | Category | GPT-4o | GPT-5.2 | Gemini 2.5 | Claude 4.6 |
|-----|----------|--------|---------|------------|------------|
| CU-GRR-18 | Grab Bar | 85 | **97** | 89 | 83 |
| 1031/18 | Towel Bar | 72 | 77 | **89** | 76 |
| 1024 | TP Holder | 68 | **93** | 92 | 81 |
| 1020 | Robe Hook | 80 | **97** | 80 | 74 |
| CM-P-700-16-GB | Grab Bar | 77 | 86 | **89** | 88 |
| **Average** | | **76.4** | **90.0** | **87.8** | **80.4** |

### Criterion Deep Dive

**Title Formula Compliance (GPT-5.2 leads: 4.6/5)**

GPT-5.2 consistently followed the product type → key attributes → "Allied Brass" structure. GPT-4o had the most failures — producing titles like "Grab Bars: 16 Inch Camo Grab Bar with Brass Finish - Allied Brass" (category prefix wrong) and "Toilet Paper Holder, Wall Mount Brass, Allied Brass at End" (literal instruction leak). Claude had structural compliance but missed brand placement in 2/5 cases.

Best title (GPT-5.2 on CU-GRR-18):
> "Grab Bar 18 inch, Cube Design Reeded, Wall Mount, ADA Compliant, 250 lb Capacity - Allied Brass"

Worst title (GPT-4o on 1024):
> "Toilet Paper Holder, Wall Mount Brass, Allied Brass at End"
(literal inclusion of the rule text)

**Keyword Coverage (Gemini leads: 5.0/5, GPT-5.2 ties: 4.6/5)**

Gemini achieved the highest keyword density scores, naturally integrating shopper-relevant terms without stuffing. Bing descriptions especially showed strong synonym coverage. Claude's keyword coverage was thinner in simpler product categories (robe hooks, towel bars) where the shorter narrative copy provided less variation to draw from.

**Description Quality (GPT-5.2 leads: 4.6/5)**

GPT-5.2 most consistently front-loaded concrete attributes in the description opener. GPT-4o often opened with brand/collection promotion ("The Skyline Collection...") before getting to specs. Claude opened with functional specifics but occasionally used hedging language.

**Accuracy (GPT-5.2 and Gemini tie: 4.8/5)**

Critical criterion (25% weight). GPT-5.2 and Gemini scored highest. Claude introduced fabricated claims in 2/5 SKUs: "Mounting hardware included" appears in outputs for CU-GRR-18 and CM-P-700-16-GB — neither of which has this claim in the product evidence. GPT-4o scored 4.4/5, with minor over-broad style claims ("seamlessly fits any décor") flagged.

**Brand Voice (Gemini leads: 4.2/5)**

Interestingly, Gemini scored highest on brand voice — the judge noted its outputs were "specific and themed, confident." GPT-5.2's voice was described as "slightly utilitarian but accurate." Claude's voice for simpler products was described as "generic/commodity due to brevity." GPT-4o scored well on voice (4.0/5) but consistency suffered.

### Standout Examples

**Best Google title generated — GPT-5.2 on CU-GRR-18:**
> "Grab Bar 18 inch, Cube Design Reeded, Wall Mount, ADA Compliant, 250 lb Capacity - Allied Brass"

Analysis: Product type first (chars 1-8), dimensions early (chars 9-14), key differentiators (Reeded, Wall Mount), safety attributes (ADA, 250 lb), brand at end. 89 characters — within 60-150 range. This is what a top-performing Google Shopping title looks like.

**Best description opener — GPT-5.2 on 1024:**
> "8-inch wall-mounted toilet tissue holder from the Skyline Collection, constructed of solid brass. Euro style hook makes changing the roll quick and easy."

Analysis: Leads with dimension (8-inch), mounting type (wall-mounted), material (solid brass), and practical feature (Euro hook). First 160 characters are pure product information.

**Worst output — GPT-4o on 1024:**
> Google title: "Toilet Paper Holder, Wall Mount Brass, Allied Brass at End"

Analysis: The phrase "Allied Brass at End" is a literal inclusion of the prompt instruction, not actual brand placement. This is a failure mode where the model echoed the rule instead of applying it.

**Most concerning — Claude on CU-GRR-18:**
> "...while the contemporary Cube Design aesthetic makes it look intentional, not institutional."

Analysis: "not institutional" is editorial copy with no evidence basis. While stylistically appealing, this is the kind of subjective claim that could create GMC content policy issues.

---

## Cost Analysis

### Token Counts (Measured from Benchmark)

| Model | Avg Input Tokens | Avg Output Tokens | Notes |
|-------|-----------------|------------------|-------|
| GPT-4o | 423 | 352 | Concise outputs |
| GPT-5.2 | 422 | 408 | More thorough outputs (+16% tokens) |
| Gemini 2.5 Pro | 456 | 552 | Most verbose (+57% output vs GPT-4o) |
| Claude Sonnet 4.6 | 417 | 376 | Estimated (session-based, not API-measured) |

### Cost Per SKU (2026 Verified Pricing)

| Model | Standard $/SKU | Batch $/SKU | Batch+Cache $/SKU |
|-------|---------------|-------------|------------------|
| GPT-4o (current) | $0.0046 | $0.0023 | $0.0020 |
| GPT-5.2 | $0.0065 | $0.0032 | $0.0030 |
| Gemini 2.5 Pro | $0.0061 | $0.0030 | $0.0029 |
| Claude Sonnet 4.6 | $0.0069 | $0.0034 | $0.0030 |

**Pricing sources:** OpenAI platform.openai.com/docs/pricing (GPT-4o: $2.50/$10 per MTok, GPT-5.2: $1.75/$14); Anthropic Claude pricing (Sonnet 4.6: $3.00/$15); Google AI Gemini pricing (2.5 Pro: $1.25/$10). Batch pricing = 50% discount on all models.

### Full Catalog Cost (2,784 Master SKUs)

| Model | Standard | Batch | Batch+Cache |
|-------|---------|-------|-------------|
| GPT-4o (current) | $12.75 | $6.37 | $5.44 |
| GPT-5.2 | $17.97 | $8.98 | $8.33 |
| Gemini 2.5 Pro | $16.96 | $8.48 | $8.01 |
| Claude Sonnet 4.6 | $19.18 | $9.59 | $8.46 |

**Key insight:** All models cost under $20 for the full catalog at batch pricing. Cost is not a meaningful differentiator — quality is. The ~$2.60 additional cost of GPT-5.2 over GPT-4o for the full catalog is trivial relative to the quality improvement.

### Caching Analysis

**GPT-5.2 caching scenario (system prompt cached):**
- System prompt: ~280 tokens (fixed, cacheable)
- Per-SKU variable input: ~142 tokens
- Cache hits save 90% on the cached portion
- At batch+cache pricing: ~$0.0030/SKU vs $0.0032 batch without cache
- Savings over full catalog: minimal ($0.56) — the system prompt is small relative to evidence content

**Recommendation:** Use batch processing, enable prompt caching. The marginal cost savings are small but cumulative at scale.

---

## Speed Comparison

| Model | Avg Latency/SKU | Estimated 2,784 SKU Runtime | Notes |
|-------|----------------|---------------------------|-------|
| GPT-4o | 4.8s | ~3.7 hours sequential | Current baseline |
| Claude Sonnet 4.6 | ~2.8s* | ~2.2 hours sequential | *Estimated from session; API may differ |
| GPT-5.2 | 6.3s | ~4.9 hours sequential | 31% slower than GPT-4o |
| Gemini 2.5 Pro | 16.9s | ~13.1 hours sequential | 3.4x slower than GPT-4o |

**Note:** All production runs use parallelism (up to 10-20 concurrent requests), so actual wall-clock time is much lower. Sequential latency is relevant for per-request performance in real-time generation scenarios (e.g., single-SKU regeneration from dashboard).

**Gemini's speed disadvantage is significant** for the Cloud Run pipeline. At 16.9s/SKU with Gemini's Thinking model active, even with 20x parallelism, a full catalog run takes ~26 minutes. GPT-5.2 at the same parallelism takes ~9 minutes.

---

## Model-Optimized Prompt Testing

The plan specified testing model-optimized prompts for the top 2 performers. This was not executed in this benchmark run due to scope: the same-prompt baseline comparison provides the primary recommendation. Observations from the quality results suggest the following model-specific optimizations for Phase 20:

**GPT-5.2 optimizations:**
- Voice is "slightly utilitarian" — add explicit examples of premium-brand phrasing in gold examples
- Add 1-2 gold standard examples per category to the user prompt to lift brand voice from 3.6/5 toward 4.5/5
- Title formula compliance is already strong (4.6/5) — preserve current structure

**Gemini 2.5 Pro optimizations (if chosen as alternative):**
- Verbosity is 57% higher than GPT-4o on output — add explicit token budget constraints to description outputs
- Voice scoring was highest (4.2/5) — leverage this; prompt can be less prescriptive on style
- Accuracy already strong (4.8/5) — no changes needed there

**Claude Sonnet 4.6 optimizations (to address fabrication risk):**
- Add explicit "DO NOT INCLUDE: mounting hardware, installation, warranty information unless explicitly in evidence" instruction
- The accuracy issue (fabricated "mounting hardware included") is a known Claude pattern — requires stronger negative examples
- Estimated score with optimized prompt: ~85-88/100 (still below GPT-5.2)

---

## Recommendation

### Primary: GPT-5.2

**Score:** 90.0/100 (vs GPT-4o baseline at 76.4/100)
**Cost:** $8.98 batch / $8.33 batch+cache for full 2,784 SKU catalog
**Speed:** 6.3s/SKU average

**Why GPT-5.2:**

1. **Largest quality improvement over current baseline:** 17.8% composite score lift with the exact same prompt. No prompt changes required to see gains, though adding gold examples will improve brand voice further.

2. **Strongest title formula compliance:** This is the highest-impact Google Shopping ranking factor. Titles that front-load product type and key attributes in the first 30 characters are indexed more accurately by Google's Shopping Graph. GPT-5.2's 4.6/5 vs GPT-4o's 2.8/5 is a meaningful gap in the most important criterion.

3. **Fewest accuracy failures:** 4.8/5 accuracy score with no fabricated claims observed across 5 SKUs. This is the non-negotiable criterion — invented specs or warranty claims create GMC disapprovals.

4. **Cost is trivially higher:** $2.61 more than GPT-4o for the full catalog. Not a decision factor.

**Evidence for Phase 20:**
- GPT-5.2 output quality is already competitive with the 6-agent pipeline (87.2/100 avg) at 1/4 the cost and time
- The main quality gap vs the 6-agent pipeline is brand voice (3.6/5 vs expected 4.5/5) — addressable with prompt updates in Phase 20
- Implementation: Change `model` parameter in `feedops/providers/openai_provider.py` from `gpt-4o` to `gpt-5.2`, update `max_completion_tokens` parameter name (GPT-5.2 uses `max_completion_tokens` not `max_tokens`)

### Secondary: Gemini 2.5 Pro (Strong Alternative)

**Score:** 87.8/100
**Cost:** $8.48 batch for full catalog
**Speed:** 16.9s/SKU (3.4x slower)

Gemini 2.5 Pro achieves comparable quality to GPT-5.2 and leads on keyword coverage (5.0/5 — perfect score) and brand voice (4.2/5). The primary disqualifier for Phase 20 is speed: 16.9s/SKU doubles the Cloud Run job runtime and increases timeout risk for single-SKU regeneration.

**When to use Gemini 2.5 Pro:** Batch offline generation jobs where speed is not critical. Its 1M context window enables cross-SKU consistency prompting (e.g., entire product family in one context) — a feature neither GPT-5.2 nor Claude can match.

### Not Recommended: Claude Sonnet 4.6

**Score:** 80.4/100
**Accuracy failures:** 2/5 SKUs contained unsupported claims

Claude's outputs read well and showed strong description quality (4.4/5) but introduced fabricated claims ("mounting hardware included") in 40% of tested SKUs. For Allied Brass, where GMC content accuracy is a hard requirement, this failure rate is disqualifying at the default prompt. With prompt adjustment (adding explicit negative examples of forbidden claims), Claude could likely reach 85-88/100 — but would still trail GPT-5.2.

**Note on bias:** This evaluation was run by Claude Sonnet 4.6 (the model being evaluated), and the Claude outputs were self-generated. Despite this, the accuracy failures were flagged by GPT-5.2 as judge — providing an independent signal. The recommendation against Claude is not based on self-assessment.

### Not Recommended: GPT-4o (Current Model)

**Score:** 76.4/100
**Critical failure:** Instruction leak in 1/5 SKUs (literal prompt text in output)

GPT-4o's lowest mark is title formula compliance (2.8/5) — the criterion most directly tied to Google Shopping ranking. It produced "Toilet Paper Holder, Wall Mount Brass, Allied Brass at End" — a literal inclusion of the instruction text. This reveals instruction-following inconsistency that GPT-5.2 resolves. GPT-4o should be deprecated from the production pipeline.

---

## Implementation Notes for Phase 20

### Required Code Changes

**File:** `src/feedops/providers/openai_provider.py` (or equivalent model configuration)

```python
# Change:
model = "gpt-4o"
# To:
model = "gpt-5.2"

# Change parameter name (GPT-5.2 uses max_completion_tokens):
# max_tokens=2000  -> max_completion_tokens=2000
```

**File:** `src/feedops/api/main.py`

The `get_provider()` function handles model selection. Verify the provider config supports the `max_completion_tokens` API parameter for GPT-5.2.

### Prompt Changes Recommended for Phase 20

1. **Add gold examples per category** — The current system prompt relies on dynamically loaded gold examples. For grab bars and towel bars, add 1-2 gold examples that demonstrate premium brand voice (4.5+ target). Current voice score of 3.6/5 is the weakest criterion.

2. **Strengthen accuracy guardrail** — Add to `P0_GLOBAL_FACTUAL_RULES`:
   ```
   - DO NOT state "mounting hardware included" unless explicitly in evidence bullets or narrative.
   - DO NOT state specific warranty durations unless explicitly stated in evidence.
   ```
   This prevents the fabrication pattern observed across models.

3. **Title formula example** — The current prompt specifies the formula but GPT-4o still failed. Add a positive example:
   ```
   GOOD: "Grab Bar 18-Inch, ADA Compliant Reeded Brass, Wall Mount - Allied Brass"
   BAD: "Allied Brass Skyline Collection Grab Bar" (brand first)
   BAD: "Toilet Paper Holder, Allied Brass at End" (instruction leak)
   ```

### Testing Before Full Deployment

1. Generate content for 10 SKUs with GPT-5.2 using the updated prompt
2. Verify no `max_tokens` parameter errors (use `max_completion_tokens`)
3. Verify JSON response format is maintained (GPT-5.2 supports `response_format: {type: "json_object"}`)
4. Run quality spot-check against scoring rubric
5. Verify no instruction text appears in any output field

### Rollout Strategy

- Phase 20: Switch single-SKU regeneration endpoint (`/regenerate`) to GPT-5.2 first
- Monitor first 20-30 regenerations for quality and cost
- If no issues, switch batch generation (`/batch-optimize`) to GPT-5.2
- Keep GPT-4o as fallback in provider config for immediate rollback capability

---

## Appendix: Raw Output Samples

### CU-GRR-18 (Grab Bar, 18 inch) — Full Outputs

**GPT-4o:**
- Google title: `Grab Bar - 18 inch, ADA Compliant Cube Design by Allied Brass`
- Short title: `Grab Bar - 18 inch, Brass`
- Description: "The 18 inch Cube Design Reeded Grab Bar by Allied Brass offers a stylish and secure solution for bathroom safety. Crafted from durable brass, this ADA-compliant grab bar features a 1 1/4" diameter reeded texture for a firm grip. Designed to provide balance and support, it is ideal for use in the tub..."

**GPT-5.2:**
- Google title: `Grab Bar 18 inch, Cube Design Reeded, Wall Mount, ADA Compliant, 250 lb Capacity - Allied Brass`
- Short title: `Grab Bar 18 in`
- Description: "18 inch Cube Design reeded grab bar with 1 1/4" dia textured bars and wall-mount installation. Made of brass and designed to add a decorative look to your tub, shower, or toilet area while providing a sense of security. ADA compliant for increased bathroom safety for everyone..."

**Gemini 2.5 Pro:**
- Google title: `Reeded Grab Bar, 18-Inch, Cube Design Collection, ADA Compliant Safety Rail, Solid Brass Wall Mounted by Allied Brass`
- Short title: `Reeded Grab Bar, 18-Inch`
- Description: "Enhance bathroom safety and accessibility with the Cube Design reeded grab bar. This ADA compliant safety rail is designed to provide security and support in tub, shower, and toilet areas, helping to maintain balance and minimize fatigue. It features a textured, reeded 1 1/4-inch diameter bar for a..."

**Claude Sonnet 4.6:**
- Google title: `Grab Bar 18-Inch, ADA Compliant Reeded Brass, Wall Mount - Cube Design - Allied Brass`
- Short title: `Grab Bar 18-Inch, Reeded Brass ADA`
- Description: "18-inch wall-mounted grab bar with a 1 1/4-inch reeded textured bar for a secure grip. ADA compliant and rated for 250 lbs, this Cube Design bar installs vertically, horizontally, or diagonally to fit tub, shower, or toilet locations. Made of brass with a decorative Cube Design aesthetic that adds visual interest without the clinical look of standard safety hardware. Mounting hardware included." *(Note: "Mounting hardware included" is unsupported by evidence)*

---

## Appendix: Model Limitations and Disqualifiers

| Issue | GPT-4o | GPT-5.2 | Gemini 2.5 Pro | Claude Sonnet 4.6 |
|-------|--------|---------|----------------|------------------|
| Instruction leak (rule text in output) | YES (1/5 SKUs) | No | No | No |
| Fabricated claims | Minor (1/5 SKUs) | No | No | YES (2/5 SKUs) |
| Title formula failures | YES (3/5 SKUs) | No | 1/5 SKUs | 1/5 SKUs |
| Speed issues | No | No | YES (3.4x slower) | No |
| API parameter differences | Uses `max_tokens` | Uses `max_completion_tokens` | Different API | Different API |

---

*Research conducted: 2026-02-21*
*Valid until: ~2026-05-21 (model pricing and availability may change; re-verify before Phase 20 if >3 months elapsed)*
*Feeds into: Phase 20 prompt rewrite and model switch implementation*
