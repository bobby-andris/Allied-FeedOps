# Task: Unify TypeScript & Python Content Generation Methodology

## Objective

Deeply investigate the divergence between TypeScript (dashboard) and Python (batch pipeline) content generation methodologies, then implement a unified approach that maximizes revenue impact and ad efficiency.

## The Problem

We have TWO systems generating product content with DIFFERENT methodologies:

| System | Location | Use Case | Current State |
|--------|----------|----------|---------------|
| **TypeScript** | `dashboard/src/app/api/regenerate/route.ts` | Real-time dashboard regeneration | Recently enhanced with variant finish sentences |
| **Python** | `src/feedops/pipeline/prompts.py` + `generator.py` | Batch generation, image generation | Original comprehensive implementation |

**Risk**: If methodologies diverge, batch-generated content (Python) will differ from dashboard-regenerated content (TypeScript), causing inconsistency and confusion.

## Phase 1: Review TypeScript Methodology Documentation

### 1.1 TypeScript Methodology Document

**IMPORTANT**: A comprehensive TypeScript methodology document already exists:

📄 **`docs/typescript-content-generation-methodology.md`**

This document covers:
- Core philosophy (context over rules)
- Two-stage architecture (LLM generation + display-time composition)
- Full regeneration API flow with code examples
- System prompt and platform-specific prompts
- Vision support implementation
- Finish sentences JSON structure
- Display-time variant content composition
- Database schema (generated_content, variant_finish_sentences, regeneration_history)
- 30 finish definitions and categories
- Example outputs

### 1.2 Key TypeScript Innovations to Understand

Before proceeding, ensure you understand these TypeScript innovations:

1. **Finish Sentences Table** - Stores 28 product+finish tailored sentences per SKU/platform
2. **Display-Time Composition** - Base content + finish sentence inserted after first sentence
3. **JSON Mode for Descriptions** - Google/Bing descriptions return `{ content, finish_sentences }`
4. **Context-Driven Prompts** - WHO/WHY/WHAT questions instead of rigid rules

### 1.3 Read the Document

```bash
# Read the full TypeScript methodology
cat docs/typescript-content-generation-methodology.md
```

Take notes on:
- What you like about this approach
- What seems missing compared to Python
- Potential issues or improvements

## Phase 2: Review Python Methodology Documentation

### 2.1 Python Methodology Document

**IMPORTANT**: A comprehensive Python methodology document already exists:

📄 **`docs/python-content-generation-methodology.md`**

This document covers:
- Architecture overview (prompts.py, generator.py, evidence.py, optimize.py)
- Full SYSTEM_PROMPT (~302 lines) with P0/P1/P2 priority rules
- CANDIDATE_SCHEMA JSON structure
- Evidence table building
- Keyword placement plan
- Category-specific guidance
- Finish injection (FINISH_CONTEXT_TEMPLATE)
- Self-scoring rubric (6 dimensions)
- Claims tracing
- Output processing and validation
- File-based patch generation

### 2.2 Key Python Strengths to Understand

Before proceeding, ensure you understand these Python strengths:

1. **Comprehensive Rules** - P0 (must follow), P1 (scored), P2 (nice to have)
2. **Good/Bad Examples** - 4 good examples, 5+ anti-patterns with explanations
3. **Self-Scoring** - LLM rates itself on 6 dimensions with checklists
4. **Claims Tracing** - Every factual claim maps to source_field + source_value
5. **Category Guidance** - Different prompts for towel storage, safety/ADA, niche/functional
6. **Structured JSON Output** - All platforms generated in one call

### 2.3 Read the Document

```bash
# Read the full Python methodology
cat docs/python-content-generation-methodology.md
```

Take notes on:
- What you like about this approach
- What seems overly complex or rigid
- Features that should be ported to TypeScript

## Phase 3: Side-by-Side Comparison

### 3.1 Create Comparison Matrix

| Aspect | TypeScript | Python | Winner | Notes |
|--------|------------|--------|--------|-------|
| **System prompt length** | ~45 lines | ~302 lines | ? | |
| **Output format** | Plain text | Structured JSON | ? | |
| **Character limits enforced** | No | Yes | ? | |
| **Examples provided** | None | 4 good, 5+ bad | ? | |
| **Anti-patterns listed** | None | Yes | ? | |
| **Self-scoring** | None | 6 dimensions | ? | |
| **Claims tracing** | None | Required | ? | |
| **Category guidance** | None | 3 categories | ? | |
| **Finish handling** | finish_sentences table | FINISH_CONTEXT_TEMPLATE | ? | |
| **Evidence table** | Via getProductEvidence() | Via prompt_builder.py | ? | |
| **Platform specifics** | Brief | Detailed | ? | |
| **Banned words list** | Basic | Comprehensive | ? | |
| **Buyer psychology** | Good | Good | ? | |
| **Vision support** | Yes (images) | Partial | ? | |

### 3.2 Analyze Quality Differences

For the same SKU (e.g., 1051), compare:
1. Generate content using TypeScript methodology
2. Generate content using Python methodology
3. Score both outputs against quality criteria
4. Identify which produces better content and why

### 3.3 Identify Strengths of Each

**TypeScript Strengths:**
- Real-time feedback during human review
- Vision support (can see product images)
- finish_sentences for consistent variant expansion
- Simpler, more focused prompts (less cognitive load on LLM?)

**Python Strengths:**
- Comprehensive rules prevent common mistakes
- Structured JSON output with claims tracing
- Self-scoring provides quality signal
- Category-specific guidance
- Explicit character limits
- Examples show desired output style

## Phase 4: Design Unified Methodology

### 4.1 Core Principles to Preserve

1. **Buyer psychology focus** - Both have this, preserve it
2. **Platform-specific content** - Google/Bing/Shopify differences matter
3. **Factual accuracy** - No invented claims
4. **Brand voice** - Confident, specific, premium-appropriate

### 4.2 Choose Best Approach for Each Aspect

For each aspect in the comparison matrix, decide:
- Which implementation to use
- Whether to combine approaches
- Implementation effort required

### 4.3 Decide on Architecture

**Option A: TypeScript as Source of Truth**
- Port Python's best features TO TypeScript
- Dashboard regeneration = batch generation methodology
- Simpler architecture (one codebase)
- Loses Python's image generation capabilities

**Option B: Python as Source of Truth**
- TypeScript calls Cloud Run (Python) for all generation
- Perfect consistency guaranteed
- More complex architecture
- Requires Cloud Run deployment (Prompt 09)

**Option C: Hybrid with Shared Prompt Module**
- Extract prompts to shared location (Supabase? Git submodule?)
- Both systems read from same source
- TypeScript and Python parse differently but use same rules
- Medium complexity

**Recommended Decision Criteria:**
1. Which produces better content quality?
2. Which is easier to maintain long-term?
3. Which supports our use cases (real-time + batch)?

## Phase 5: Implementation Plan

### 5.1 If TypeScript as Source of Truth (Option A)

Tasks:
1. Port CANDIDATE_SCHEMA to TypeScript (structured output)
2. Port all examples (good and anti-patterns) to TypeScript
3. Port scoring rubric to TypeScript
4. Port category guidance to TypeScript
5. Port comprehensive banned words list
6. Add character limit enforcement
7. Update Python to call TypeScript methodology OR
8. Update Python to use identical prompts

### 5.2 If Python as Source of Truth (Option B)

Prerequisites:
- Prompt 09 (Cloud Run) must be deployed

Tasks:
1. Ensure Cloud Run `/regenerate` endpoint uses full Python prompts
2. Update TypeScript to call Cloud Run instead of OpenAI directly
3. Preserve TypeScript's vision support by passing image URLs to Python
4. Preserve finish_sentences integration
5. Add endpoint for structured output parsing

### 5.3 If Hybrid (Option C)

Tasks:
1. Create shared prompts table in Supabase
2. Store SYSTEM_PROMPT, examples, rules in database
3. Version control prompts in Supabase
4. TypeScript reads prompts from Supabase
5. Python reads prompts from Supabase
6. Both generate with identical instructions

## Phase 6: Testing & Validation

### 6.1 A/B Quality Test

1. Select 5 representative SKUs across categories
2. Generate content with OLD methodology
3. Generate content with NEW unified methodology
4. Human review: which is better?
5. Score against quality dimensions

### 6.2 Consistency Test

1. Generate content for same SKU via dashboard (TypeScript)
2. Generate content for same SKU via batch (Python)
3. Compare outputs - should be nearly identical
4. If different, investigate and fix

### 6.3 Regression Test

1. Generate content for SKUs that were previously "good"
2. Verify new methodology doesn't make them worse
3. Check for any anti-pattern violations

## Success Criteria

1. [ ] TypeScript and Python methodologies documented in detail
2. [ ] Side-by-side comparison matrix completed
3. [ ] Architecture decision made with clear rationale
4. [ ] Implementation plan created with task list
5. [ ] Unified methodology implemented
6. [ ] Quality test shows improvement or no regression
7. [ ] Consistency test passes (TypeScript ≈ Python output)
8. [ ] Documentation updated (CLAUDE.md, AGENTS.md)

## Key Files Reference

### TypeScript (Dashboard)
```
dashboard/src/app/api/regenerate/route.ts       # Main regeneration
dashboard/src/lib/evidence.ts                   # Evidence table builder
dashboard/src/lib/variant-content.ts            # Variant expansion
dashboard/src/lib/supabase/queries.ts           # DB queries
dashboard/src/components/review/VariantContentGrid.tsx  # UI
```

### Python (Pipeline)
```
src/feedops/pipeline/prompts.py                 # SYSTEM_PROMPT, templates
src/feedops/pipeline/generator.py               # LLM calls
src/feedops/pipeline/prompt_builder.py          # Build prompts
src/feedops/pipeline/optimize.py                # Orchestration
src/feedops/providers/openai_provider.py        # OpenAI API
```

### Database
```
supabase/migrations/XXX_variant_finish_sentences.sql  # Finish sentences schema
```

## Revenue Impact Considerations

When deciding on methodology, consider these business goals:

1. **CTR Improvement**: Titles that match search intent get more clicks
   - Python's keyword placement plan may help
   - TypeScript's vision support may help verify product accuracy

2. **CVR Improvement**: Descriptions that answer buyer questions convert better
   - Both have buyer psychology focus
   - Python's examples show what good looks like

3. **ROAS Improvement**: Better matching = lower CPA
   - Structured output with claims tracing = auditable accuracy
   - Character limits = optimal feed fuel

4. **Consistency**: Same product should sound the same everywhere
   - This is the primary driver for unification

## Notes

- This prompt should be run AFTER Prompt 09 (Cloud Run) is complete if Option B is likely
- The user has recently enhanced TypeScript with finish_sentences - preserve this work
- The goal is not to pick a "winner" but to create the best unified approach
