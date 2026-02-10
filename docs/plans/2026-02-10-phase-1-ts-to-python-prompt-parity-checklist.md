# Phase 1 TS-to-Python Prompt Parity Checklist

## Purpose

This checklist inventories the three TypeScript prompt-generation paths that existed in the dashboard and maps each behavior to Python as `adopt`, `adapt`, or `drop`.

Phase 1 objective: one runtime prompt authority in Python, with no hidden prompt logic drift.

## Canonical Decision

- Runtime prompt authority: `src/feedops/pipeline/prompts.py`
- Runtime prompt loading/versioning: `src/feedops/api/prompt_loader.py`
- Runtime prompt composition: `src/feedops/api/main.py` (`_build_generation_user_prompt`)
- Supabase `prompt_templates`: data-only (`gold_standard_examples`, `category_guidance`, `platform_rules`)
- Supabase `prompt_templates.system_prompt`: non-authoritative at runtime

## Source Files Reviewed

- `dashboard/src/lib/regeneration/prompts.ts`
- `dashboard/src/lib/regeneration/core.ts`
- `dashboard/src/app/api/regenerate/route.ts`
- `src/feedops/pipeline/prompts.py`
- `src/feedops/api/prompt_loader.py`
- `src/feedops/api/main.py`
- `src/feedops/api/hybrid_generation.py`
- `src/feedops/pipeline/keyword_placement.py`

## Parity Matrix

| TS Source | Behavior | Python Target | Decision | Phase 1 Status |
|---|---|---|---|---|
| `prompts.ts` | Balanced quality-first vs pain-point-first framing | `pipeline/prompts.py` system prompt guidance | `adopt` | implemented |
| `prompts.ts` | No hallucination / evidence-only claims | `pipeline/prompts.py` + validators | `adopt` | implemented |
| `prompts.ts` | Search-query usage guardrails | `pipeline/prompts.py` + evidence/keyword pipeline | `adapt` | implemented (pipeline wording differs) |
| `prompts.ts` | Google/Bing variant context vs Shopify master context | `_build_generation_user_prompt` in `api/main.py` | `adopt` | implemented |
| `prompts.ts` | Shopify title forbids finish + brand | `keyword_placement.py` + prompt rules | `adopt` | implemented |
| `prompts.ts` | 28 canonical finish vocabulary | `prompt_loader.py:get_finish_list` + `hybrid_generation.py` | `adopt` | implemented |
| `prompts.ts` | Bing anti-stuffing/synonym rules | `pipeline/prompts.py` constraints | `adopt` | implemented |
| `prompts.ts` | TS `validateGeneratedContent` hard checks | Python validation stack | `adapt` | partially implemented (full consolidation in later phase) |
| `core.ts` | Build enhanced prompt from evidence + examples + category guidance | `_build_generation_user_prompt` + `prompt_loader.py` helpers | `adopt` | implemented |
| `core.ts` | Simple fallback prompt path when catalog unavailable | API fallback path in Python | `adopt` | implemented |
| `core.ts` | Variant description JSON contract with `finish_sentences` map | Python generation contract | `adapt` | implemented in Phase 2 (`/regenerate` returns optional `finish_sentences`) |
| `core.ts` | Prompt hashing for traceability | `get_system_prompt_hash` + DB write fields | `adapt` | implemented (canonical prompt hash) |
| `core.ts` | TS-side OpenAI direct generation behavior | Python Cloud Run runtime only | `drop` | implemented for regeneration path in Phase 2 |
| `route.ts` | Thin proxy from dashboard to Cloud Run | `dashboard` API route -> Python `/regenerate` | `adopt` | implemented |
| `route.ts` | TS-side finish sentence OpenAI call | Python finish sentence pipeline | `drop` | implemented in Phase 2 |
| `route.ts` | Feedback presets + feedback-mode mapping | route request shaping + Python feedback field | `adapt` | implemented |
| `route.ts` | Synthetic timestamp-based prompt hash | canonical hash from Python prompt loader | `drop` | implemented |

## Phase 1 Required Assertions

1. Python ignores DB `prompt_templates.system_prompt` for runtime generation.
2. Prompt hash fields persist from Python canonical prompt hash:
   - `generated_content.generation_prompt_hash`
   - `regeneration_history.prompt_hash`
3. Platform/entity behavior remains explicit:
   - Google/Bing = variant-facing context
   - Shopify = master-facing context

## Tests That Must Stay Green

- `tests/test_prompt_loader.py`
- `tests/test_hybrid_generation_prompt.py`
- `tests/test_keyword_placement.py`
- `tests/api/test_multi_sku_detection.py`

## Notes On Deferred Items

- Full replacement of TS-side content validation helpers is deferred until dashboard prompt execution paths are fully retired.
