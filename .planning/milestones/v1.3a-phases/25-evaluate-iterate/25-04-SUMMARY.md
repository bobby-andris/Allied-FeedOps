---
phase: 25-evaluate-iterate
plan: 04
subsystem: api
tags: [gpt-5.2, prompts, content-generation, cloud-run, skills]

# Dependency graph
requires:
  - phase: 25-02
    provides: Round 1 blind evaluation results identifying 5 gaps
provides:
  - Refactored SYSTEM_PROMPT deferring to skills as creative authority
  - Product Design Story block extracting narrative_copy, bullets, mounting_type from evidence
  - Skills-deferred competitive positioning (no hardcoded checklist)
  - Finish name mandate in Google/Bing titles
  - Strengthened accuracy guardrail with explicit fabrication prohibitions
affects: [25-05, content-generation, prompt-architecture]

# Tech tracking
tech-stack:
  added: []
  patterns:
    - "Skills as single source of truth for creative direction — SYSTEM_PROMPT provides scaffolding only"
    - "Product Design Story extraction from ParentSKU model fields"
    - "Finish name placeholder pattern for Google/Bing master-SKU generation"

key-files:
  created: []
  modified:
    - src/feedops/pipeline/prompts.py
    - src/feedops/api/prompt_builder.py

key-decisions:
  - "Skills are the creative authority; hardcoded SYSTEM_PROMPT reduced to minimal structural scaffolding"
  - "Product-specific data (narrative_copy, bullets) extracted and highlighted as Product Design Story"
  - "Finish name uses {FINISH_NAME} placeholder when no finish_code provided for Google/Bing"
  - "Hardcoded competitive checklist (28 finishes, 41 collections, etc.) replaced with skills-deferred guidance"

patterns-established:
  - "Skills-first prompt architecture: SYSTEM_PROMPT scaffolds, skills provide creative substance"
  - "Product Design Story extraction: narrative_copy + bullets + mounting_type from ParentSKU"

requirements-completed: [EVAL-03, EVAL-04, EVAL-05]

# Metrics
duration: 10min
completed: 2026-02-23
---

# Phase 25 Plan 04: Gap Closure Summary

**Refactored prompt architecture to defer creative authority to skills, extract product-specific design data, mandate finish names in Google/Bing titles, and strengthen accuracy guardrails against fabrication**

## Performance

- **Duration:** 10 min
- **Started:** 2026-02-23T18:36:50Z
- **Completed:** 2026-02-23T18:47:40Z
- **Tasks:** 2
- **Files modified:** 2

## Accomplishments
- Refactored SYSTEM_PROMPT creative_direction from manufactured-scenario teaching to evidence-grounded design storytelling (Gap 3)
- Replaced hardcoded competitive checklist (5 generic bullets: brass vs zinc, 28 finishes, 41 collections, concealed mounting, lifetime warranty) with skills-deferred positioning (Gap 2, Gap 5)
- Added Product Design Story extraction pulling narrative_copy, bullet_1-4, mounting_type, weight_capacity, style from ParentSKU and evidence (Gap 2)
- Mandated finish name in Google/Bing titles via both SYSTEM_PROMPT platform_rules and prompt_builder finish context (Gap 1)
- Strengthened accuracy_guardrail with explicit fabrication prohibitions for mechanisms, usage contexts, certifications, and sensory claims (Gap 4)
- Deployed to Cloud Run with successful health check

## Task Commits

Each task was committed atomically:

1. **Task 1: Refactor SYSTEM_PROMPT** - `3c4a2038` (fix)
2. **Task 2: Refactor prompt_builder.py** - `f3de73c7` (fix)

## Files Created/Modified
- `src/feedops/pipeline/prompts.py` - Refactored SYSTEM_PROMPT (creative_direction, brand_voice, accuracy_guardrail, platform_rules) and USER_PROMPT_TEMPLATE/VARIANT_USER_PROMPT_TEMPLATE
- `src/feedops/api/prompt_builder.py` - Replaced customer_framing and competitive_positioning blocks with Product Design Story and skills-deferred competitive guidance; fixed finish context for Google/Bing

## Decisions Made
- Skills are the creative authority; SYSTEM_PROMPT reduced to minimal scaffolding that points GPT-5.2 to skills for brand voice, competitive positioning, and storytelling patterns
- Product-specific data (manufacturer description, bullets) extracted from ParentSKU model and highlighted in prompt as "Product Design Story" so GPT-5.2 has real differentiators
- When generating Google/Bing content without explicit finish_code, prompt instructs use of default/popular finish from evidence or {FINISH_NAME} placeholder for variant expansion
- Removed all hardcoded competitive checklist items that were identical for every product

## Deviations from Plan

None - plan executed exactly as written.

## Issues Encountered
None

## User Setup Required
None - no external service configuration required.

## Next Phase Readiness
- Prompt architecture refactored and deployed to Cloud Run (healthy)
- Ready for Plan 25-05: Round 2 regeneration and evaluation of the same 10 SKUs
- All 5 gaps from VERIFICATION.md have corresponding code fixes deployed

---
*Phase: 25-evaluate-iterate*
*Completed: 2026-02-23*
