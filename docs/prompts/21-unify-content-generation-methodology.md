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

## Phase 1: Document Current TypeScript Methodology

### 1.1 Read and Document TypeScript Implementation

Files to analyze:
```
dashboard/src/app/api/regenerate/route.ts      # Main regeneration logic
dashboard/src/lib/evidence.ts                   # Evidence table builder
dashboard/src/lib/variant-content.ts            # Variant content expansion
dashboard/src/lib/supabase/queries.ts           # Data queries including finish_sentences
```

Document for each file:
- What data is fetched/used
- How prompts are constructed
- What the output format is
- How finish/variant handling works

### 1.2 Document TypeScript Prompt Structure

Extract and document:
1. **SYSTEM_PROMPT** - The full system prompt text
2. **User prompt construction** - How the dynamic prompt is built
3. **Evidence table format** - What product data is included
4. **Finish sentences** - How variant-specific content is generated
5. **Platform context** - Google/Bing/Shopify differences

### 1.3 Document Recent Enhancements

From the user's recent changes:
- `variant_finish_sentences` table schema
- How finish sentences are stored and retrieved
- How variant content is expanded from master template

## Phase 2: Document Current Python Methodology

### 2.1 Read and Document Python Implementation

Files to analyze:
```
src/feedops/pipeline/prompts.py                 # SYSTEM_PROMPT, USER_PROMPT_TEMPLATE
src/feedops/pipeline/generator.py               # Candidate generation logic
src/feedops/pipeline/prompt_builder.py          # Evidence table construction
src/feedops/pipeline/optimize.py                # Full optimization pipeline
src/feedops/db/evidence_tables.py               # Product data assembly (if exists)
```

Document for each file:
- What data is fetched/used
- How prompts are constructed
- What the output format is (JSON schema)
- How finish/variant handling works

### 2.2 Document Python Prompt Structure

Extract and document:
1. **SYSTEM_PROMPT** - The full system prompt text (~302 lines)
2. **CANDIDATE_SCHEMA** - JSON schema for structured output
3. **USER_PROMPT_TEMPLATE** - Dynamic prompt template
4. **FINISH_CONTEXT_TEMPLATE** - Variant-specific generation
5. **_CATEGORY_GUIDANCE** - Category-specific hints
6. **build_category_guidance()** - How category hints are selected

### 2.3 Document Python Scoring System

The Python implementation includes self-scoring:
- 6 scoring dimensions (specificity, benefit_coverage, etc.)
- Scoring checklist for each dimension
- Claims tracing (source_field, source_value)

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
