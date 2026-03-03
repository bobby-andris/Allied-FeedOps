# Research: Incorporating gmc-product-optimizer Skill + Claude Sonnet 4.6

**Date:** 2026-03-03
**Context:** Phase 6 blind eval showed Sonnet 4.6 scored 8.85/10 (vs GPT-5.2 at 6.15/10). User has a well-crafted `gmc-product-optimizer.skill` from prompts.chat that represents Bobby/Robert's ideal content style. Can we use this skill as the prompt for Sonnet 4.6 in the production pipeline?

## 1. What the Skill Contains

The `gmc-product-optimizer` skill is a ~163-line creative brief for generating Google Merchant Center supplemental feed content:

- **Title rules**: Collection name + product type | material/style differentiator | "Allied Brass" (pipe-separated segments)
- **Description rules**: 8-step structure (benefit hook → `{finish_sentence}` → design romance → material/durability → features → cross-sell → installation → warranty close)
- **Output format**: 2 optimized titles + 2 optimized descriptions per product
- **3 worked examples**: Towel bar, paper towel holder, tilt mirror — each with full input/output
- **Anti-patterns**: No generic openers, no filler, no thin descriptions

### Key Differences from Current Pipeline Prompts

| Aspect | Current Pipeline (prompts.py) | Skill |
|--------|-------------------------------|-------|
| Placeholder case | `{FINISH_SENTENCE}`, `{FINISH_NAME}` | `{finish_sentence}` (lowercase) |
| Title structure | `{FINISH_NAME} [Function] [Collection] [Dim] - Allied Brass` | `[Collection] [Function] \| [Material/Style] \| Allied Brass` (pipes, no finish in title) |
| Output count | 1 title + 1 description per platform | 2 titles + 2 descriptions |
| Output format | JSON with schema enforcement | Plain text markdown format |
| Finish handling | Titles start with `{FINISH_NAME}` | No finish in titles (master SKU style) |
| Description length | 700-900 chars (Google) | 800-1100 chars |
| Warranty close | Not mandatory | Always "Backed by a Limited Lifetime Warranty." |
| Cross-sell | Generic "collection coordination" | Name specific accessory types |

## 2. Critical Compatibility Issues

### 2a. Placeholder Case Mismatch

**Risk: HIGH** — The skill uses `{finish_sentence}` (lowercase). The pipeline's variant expansion system (`strip_hardcoded_finish_names`, `normalize_base_description_with_finish_placeholder`) expects `{FINISH_SENTENCE}` (uppercase). If Sonnet outputs lowercase, variant expansion breaks.

**Fix**: Simple — add a case-normalization step in the skill text when injecting it, OR add a normalization step post-generation. Both are trivial.

### 2b. Title Structure Conflict

**Risk: MEDIUM** — The skill puts collection first (`Astor Place Collection Frameless Oval Tilt Mirror | Solid Brass | Allied Brass`). The pipeline's current title formula puts `{FINISH_NAME}` first because every Google Shopping listing IS a specific finish variant.

**Resolution**: The skill was designed for a human workflow where the operator manually handles finish variants. In the pipeline, titles MUST start with `{FINISH_NAME}` because the supplemental feed produces one row per variant (28 finishes × N SKUs). This is non-negotiable — it's how Google Shopping works.

**Fix**: Modify the skill's title guidance to lead with `{FINISH_NAME}` and use the pipe-separator style for the remainder. This is an improvement — pipes are more information-dense than dashes.

### 2c. Output Format (2 variants vs 1)

**Risk: LOW** — The skill produces 2 titles and 2 descriptions. The pipeline only needs 1 of each per platform. Two options:
1. **Pick-best**: Generate 2, have a quality-gate pick the better one (adds latency/cost)
2. **Single output**: Modify the skill to produce 1 of each (simpler, preferred)

**Recommendation**: Modify to produce 1 title + 1 description. The pipeline doesn't have a multi-candidate selection mechanism, and adding one adds complexity without clear value.

### 2d. JSON Output vs Markdown

**Risk: LOW** — Sonnet 4.6 supports `output_config.format` with `json_schema` (constrained decoding). The skill currently expects markdown output, but Sonnet can easily produce JSON when instructed. The skill's guidance becomes the system prompt; the output contract becomes the JSON schema.

## 3. Integration Architecture Assessment

### Option A: Replace System Prompt Only (RECOMMENDED)

**What changes:**
- Replace `GOOGLE_BRIEF` in `prompts.py` with skill content (adapted for `{FINISH_NAME}` titles and JSON output)
- Keep all existing infrastructure: prompt_builder.py, executor.py, schema enforcement, evidence injection

**What stays the same:**
- Provider abstraction (just set `FEEDOPS_PROVIDER=claude`)
- Evidence table construction
- Keyword placement plan
- Finish sentence generation (separate call)
- JSON schema enforcement
- Post-generation normalization (hardcoded finish stripping, placeholder normalization)

**Risk**: Very low. The system prompt is the creative brief; the infrastructure is unchanged. Sonnet doesn't have GPT-5.2's hyper-sensitivity to prompt changes.

**Effort**: ~1 hour. Write a new `GOOGLE_BRIEF_V3` constant, feature-flag it, test with curl.

### Option B: Separate "Skill Mode" Pipeline

**What changes:**
- New endpoint or mode parameter that uses the skill as-is
- Custom prompt construction bypassing prompt_builder.py
- Custom output parsing for markdown format

**Risk**: High. Creates a second codepath, doubles maintenance surface, loses all the evidence injection and normalization infrastructure.

**Verdict**: Rejected. Over-engineered, fragile.

### Option C: Inject Skill into User Prompt as Context

**What changes:**
- Append skill content to the user prompt section
- Keep existing system prompt

**Risk**: Medium. Conflicting instructions between system prompt and skill. Token waste from redundancy.

**Verdict**: Suboptimal. System prompt replacement is cleaner.

## 4. Risk Assessment at GO Stage

### What "GO stage" means
- Phases 1-5 complete (decomposition, bug fixes, Claude provider)
- 98% human approval rate on existing GPT-5.2 content
- Provider abstraction tested and working
- 222-row evaluation showing Sonnet quality superiority

### Risks of incorporating the skill

| Risk | Severity | Mitigation |
|------|----------|------------|
| Regression on approved content | LOW | We're generating for NEW SKUs (no approved content). Existing approved content is immutable in Supabase. |
| Placeholder handling breaks | LOW | Post-generation normalization already handles this (`normalize_base_description_with_finish_placeholder`) |
| Batch reliability regression | LOW | Timeout fixes just committed. Sonnet has 529/overloaded retry handling. |
| Prompt change breaks output | VERY LOW | Unlike GPT-5.2, Sonnet is not hyper-sensitive to prompt changes (Phase 27 learning was GPT-5.2-specific) |
| Cost increase | NEGATIVE RISK | Sonnet costs $0.008/call vs GPT-5.2 $0.034/call — 76% cost reduction |

### Risks of NOT incorporating

| Risk | Severity |
|------|----------|
| Continue shipping inferior GPT-5.2 content | HIGH — 6.15/10 vs 8.85/10 blind score |
| Continue paying 4x more per generation | MEDIUM — $0.034 vs $0.008 |
| Miss opportunity to use battle-tested creative brief | MEDIUM — skill represents distilled human feedback |

## 5. Optimal Integration Plan

### Step 1: Adapt skill for pipeline constraints
- Change `{finish_sentence}` → `{FINISH_SENTENCE}` throughout
- Add `{FINISH_NAME}` as mandatory title prefix
- Keep pipe-separator structure for title segments (it's better than dash separators)
- Change output to JSON (single title + description)
- Keep all description structure guidance (8-step, warranty close, cross-sell specifics)
- Keep all anti-patterns and worked examples

### Step 2: Create GOOGLE_BRIEF_V3
- New constant in `prompts.py` that merges skill guidance with existing pipeline constraints
- Include adapted worked examples (powerful for Sonnet — few-shot learning)
- Keep `SYSTEM_PROMPT` base (creative direction, brand voice, accuracy guardrails) + new `GOOGLE_BRIEF_V3`

### Step 3: Feature flag
- `FEEDOPS_GOOGLE_BRIEF_VERSION=v3` env var (default: current v2)
- Zero-risk rollback — just change the env var

### Step 4: Test with 10 evaluation SKUs
- Run same 10 SKUs with Sonnet 4.6 + skill-adapted prompt
- Compare against existing 222-row evaluation data
- Bobby/Robert review for approval readiness

### Step 5: Go live
- Set `FEEDOPS_PROVIDER=claude` + `FEEDOPS_GOOGLE_BRIEF_VERSION=v3` in Cloud Run
- Monitor first batch of 10-20 SKUs
- If quality holds, make it default

## 6. What About Bing and Shopify?

The skill is Google-focused. For Bing:
- Adapt the same description structure (spec-led opening variant)
- Same warranty close, cross-sell specifics
- Bing titles follow same `{FINISH_NAME}` pattern

For Shopify:
- The skill doesn't cover Shopify (master-SKU, finish-agnostic content)
- Current `SHOPIFY_BRIEF` is adequate
- Can adapt skill principles later if needed

## 7. Conclusion

**Incorporating the skill is LOW RISK and HIGH REWARD:**
- The provider abstraction is already built and tested
- The skill represents distilled human feedback on what makes good content
- Sonnet 4.6 produces better content AND costs 76% less
- The integration is a system prompt change with a feature flag — not an architecture change
- All existing infrastructure (evidence, keywords, schemas, normalization) stays intact
- Existing approved content is immutable — we're only generating for new SKUs

**The only question is whether the skill-adapted prompt produces better content than the current GOOGLE_BRIEF with Sonnet.** That's what the evaluation run will answer.
