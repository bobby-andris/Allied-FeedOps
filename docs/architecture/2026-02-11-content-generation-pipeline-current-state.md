# Content Generation Pipeline (Current State)

Last updated: 2026-02-11  
Scope: Current production-oriented pipeline behavior, traceability, and rule enforcement in this repo.

## Purpose

This document captures how content is generated **today** across dashboard + Python API + Supabase, including:

- Canonical prompt authority path.
- Request and persistence flow.
- Where rules are hard-enforced vs prompt-guided.
- Why some outputs can still look off (for example, finish placement drift or awkward Shopify phrasing).

This is a baseline artifact to guide future improvements without guessing.

## Source Of Truth Contract

Canonical runtime prompt authority is Python:

- Canonical system prompt: `src/feedops/pipeline/prompts.py` (`SYSTEM_PROMPT`)
- Prompt retrieval + hashing: `src/feedops/api/prompt_loader.py`
  - `get_system_prompt()`
  - `get_system_prompt_hash()` (SHA256 short hash, first 16 chars)

Supabase `prompt_templates` is data-only guidance (examples/category/platform guidance), not system prompt authority:

- `src/feedops/api/prompt_loader.py`
- `dashboard/src/app/api/regenerate/route.ts` enforces `prompt_hash` response contract from Python.

## End-To-End Generation Flow

```mermaid
flowchart TD
  U[Dashboard UI] --> R1[/api/regenerate<br/>dashboard route]
  R1 --> P1[/Python API /regenerate]
  P1 --> L1[Load ParentSKU from Supabase]
  P1 --> E1[Build evidence table<br/>build_evidence_table + format_evidence_markdown]
  P1 --> K1[Build user prompt<br/>_build_generation_user_prompt]
  K1 --> S1[System prompt from Python canonical<br/>get_system_prompt]
  P1 --> G1[LLM generate content]
  G1 --> V1{Variant description<br/>google/bing?}
  V1 -- Yes --> F1[Generate finish_sentences JSON]
  F1 --> F2[normalize_and_validate_finish_sentences]
  V1 -- No --> P2[Skip finish sentences]
  F2 --> W1[Write generated_content<br/>generation_model + generation_prompt_hash]
  P2 --> W1
  W1 --> W2[Write regeneration_history<br/>prompt_hash + prompts + model]
  W2 --> W3[Upsert variant_finish_sentences if present]
  W3 --> R2[Return content + prompt_hash + model]
  R2 --> R1
  R1 --> D1[Dashboard validates prompt_hash exists]
  D1 --> D2[Dashboard upserts generated_content metadata]
  D2 --> U
```

## Hybrid Multi-SKU Flow

```mermaid
flowchart TD
  U[SKU Selection UI] --> H0[/api/sku-selection/generate-hybrid]
  H0 --> H1[/Python API /hybrid-generate]
  H1 --> H2[Detect multi-SKU families]
  H2 --> H3{Base or Variant?}
  H3 -- Base SKU --> B1[Full generation path<br/>same canonical prompt + evidence flow]
  H3 -- Variant SKU --> V1[adapt_variant_content]
  V1 --> V2[Load base generated_content]
  V2 --> V3[Build adaptation prompt<br/>base -> variant spec delta]
  V3 --> V4[Use canonical system prompt + prompt hash]
  V4 --> V5[Validate adapted content<br/>validate_candidate_content]
  V5 --> V6[Write generated_content + regeneration_history + finish sentences]
  B1 --> H4[Job status aggregation]
  V6 --> H4
  H4 --> U
```

## Traceability And Metadata

Traceability fields persisted by Python:

- `generated_content.generation_model`
- `generated_content.generation_prompt_hash`
- `regeneration_history.model_version`
- `regeneration_history.prompt_hash`
- `regeneration_history.system_prompt` (truncated for DB)
- `regeneration_history.user_prompt` (truncated for DB)

Dashboard-side contract guard:

- `dashboard/src/app/api/regenerate/route.ts` fails if Python response lacks `prompt_hash`.
- Dashboard updates `generated_content` using returned `prompt_hash` and `model`.
- Dashboard intentionally does not duplicate `regeneration_history` (Python is authoritative writer for history).

## Rule Layers (What Is Actually Enforced)

### Layer 1: Prompt-guided behavior (soft)

Prompt rules strongly guide model behavior, including:

- Google/Bing finish-aware variant framing.
- Shopify finish-agnostic framing.
- Brand placement conventions.
- Benefit-first and policy language constraints.

Primary files:

- `src/feedops/pipeline/prompts.py`
- `src/feedops/api/main.py` (`_build_generation_user_prompt`)
- `src/feedops/api/hybrid_generation.py` (`build_variant_adaptation_prompt`)

### Layer 2: Deterministic keyword planning (module available, partial runtime wiring)

- Keyword planning/validation utilities exist:
  - `src/feedops/pipeline/keyword_placement.py`
- In current API runtime paths (`/regenerate`, `/optimize-sku`), prompt assembly is evidence-first but does not currently inject an explicit keyword placement section.
- Practical impact: keyword quality is mainly prompt-guided + model behavior in these endpoints, not a strict keyword-plan gate.

### Layer 3: Hard validation (blocking)

Hard validation is path-dependent:

- `/regenerate` and `/optimize-sku`:
  - Finish sentence payload is hard-validated (for Google/Bing descriptions when enabled).
  - Main title/description content is not currently blocked by `validate_candidate_content` in this path.
- `/hybrid-generate` variant adaptation path:
  - Adapted content is hard-validated using `validate_candidate_content` before persistence.

Finish sentence hard validation:

- `normalize_and_validate_finish_sentences(...)`
- Requires canonical finish coverage and quality checks before persistence.

Primary files:

- `src/feedops/pipeline/finish_sentence_validation.py`
- `src/feedops/api/main.py`
- `src/feedops/api/hybrid_generation.py`

## Why The Pipeline Is Strong (Current Optimization Logic)

1. Canonical prompt authority is centralized in Python, reducing dashboard prompt drift risk.
2. Evidence-first prompting grounds generation in structured product + query context, not freeform copywriting.
3. Cross-platform context is explicit: variant-aware (Google/Bing) vs master-facing (Shopify).
4. Prompt hash + model metadata create auditable lineage for each generated artifact.
5. Finish sentence generation is separated and validated, which reduces generic finish boilerplate.
6. Hybrid path improves consistency/cost for families by adapting from validated base outputs.

## Known Gaps Explaining Current “Weird” Outputs

These are current-state realities, not assumptions:

1. Finish-first in Google/Bing titles is not globally hard-enforced.
  - It is strongly requested in prompt text.
  - Full `/regenerate` path does not currently enforce a hard “finish-first token order” validator.
  - Result: some titles may be compliant but not finish-first.

2. Shopify phrasing can feel awkward when model follows many constraints but lacks stricter template shaping.
  - Shopify has hard exclusions (no specific finish names, no “Allied Brass” in title).
  - Tone/structure quality is mostly prompt-guided; hard validators do not fully enforce readability style patterns.

3. Hybrid adaptation relies on base-content adaptation + policy validation.
  - It preserves consistency and spec changes well.
  - It can still carry over awkward base sentence rhythms because adaptation is constrained to keep structure.

4. Validation strictness differs by path.
  - Hybrid variant adaptation has stronger blocking validation than standard `/regenerate`.
  - This can produce inconsistent quality enforcement across flows.

## Exact Routes And Components In Play

Dashboard entry points:

- `dashboard/src/components/review/RegenerateButton.tsx`
- `dashboard/src/app/api/regenerate/route.ts`
- `dashboard/src/app/api/sku-selection/generate-hybrid/route.ts`

Python API endpoints:

- `src/feedops/api/main.py`
  - `/regenerate`
  - `/optimize-sku`
  - `/batch-optimize`
  - `/hybrid-generate`

Hybrid adaptation:

- `src/feedops/api/hybrid_generation.py` (`adapt_variant_content`)

## Runtime Controls

Kill switches:

- `FEEDOPS_DISABLE_GENERATION`
- `FEEDOPS_DISABLE_FINISH_SENTENCE_REGEN`

File:

- `src/feedops/api/runtime_controls.py`

## Improvement Readiness (Next-Step Guidance)

Before changing behavior, improvements should target explicit layers:

1. Add hard validator for finish-leading title format on variant Google/Bing paths.
2. Add Shopify style-shape checks (not only policy checks) to catch awkward but policy-compliant prose.
3. Add path-specific tests for:
  - finish-first enforcement
  - Shopify title/description readability templates
  - hybrid adaptation preserving factual deltas without stylistic degradation

This document should be treated as the baseline architecture snapshot for post-Phase 8 prompt/quality tuning.
