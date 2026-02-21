---
phase: 24-prompt-architecture
plan: 02
subsystem: api
tags: [prompts, yaml, category-guidance, customer-framing, competitive-positioning, python, content-generation]

requires:
  - phase: 24-prompt-architecture
    plan: 01
    provides: "SYSTEM_PROMPT rewritten as creative brief, skill_loader.py built, 8 skills injected"

provides:
  - "shopping_intelligence.yaml expanded from 17 to 24 categories covering top revenue categories"
  - "USER_PROMPT_TEMPLATE and VARIANT_USER_PROMPT_TEMPLATE include customer_framing and competitive_positioning XML blocks"
  - "build_core_prompt() injects Customer Framing and Competitive Positioning sections into every generated prompt"
  - "Legacy _CATEGORY_GUIDANCE dict and build_category_guidance() fully removed — shopping_intelligence.yaml is sole canonical source"

affects: [25-evaluate-iterate, prompt_builder, generator, main, prompts]

tech-stack:
  added: []
  patterns:
    - "customer_framing block: GPT-5.2 reasons buyer scenario from evidence + category + skills (not a template fill-in)"
    - "competitive_positioning block: GPT-5.2 weaves brass vs zinc, 28 finishes, 41 collections naturally into copy"
    - "DB-query-driven YAML expansion: query product_catalog for top categories by variant count, add missing entries"

key-files:
  created: []
  modified:
    - src/feedops/config/shopping_intelligence.yaml
    - src/feedops/pipeline/prompts.py
    - src/feedops/api/prompt_builder.py
    - src/feedops/api/main.py
    - src/feedops/pipeline/generator.py

key-decisions:
  - "Customer framing as reasoning prompt (not template fill-in): block tells GPT-5.2 HOW to think about the buyer, not WHAT to write — produces specific scenarios vs generic 'upgrade your bathroom'"
  - "Competitive positioning contrast material/approach not companies: 'solid brass vs die-cast zinc' not 'Allied Brass vs Kingston Brass' — maintains brand voice, avoids policy issues"
  - "Option A for prompt_builder (section-based over template format): keeps existing manually-built sections pattern, avoids template migration that would touch generator.py templates"
  - "DB query to drive YAML expansion: queried product_catalog variant counts, identified 7 high-volume missing categories (guest towel holders 2800, wood shelves 2786, tumbler toothbrush holders 1860, soap dishes 1804, multi hooks 1236, paper towel holders 1154, freestanding toilet tissue stands 908)"
  - "Rule 3 auto-fix: generator.py and main.py had stale build_category_guidance references that would cause ImportError — removed and replaced with get_category_guidance from prompt_loader"

patterns-established:
  - "New customer_context placeholder: extracted from parent_sku.category + collection (provides GPT-5.2 concise category hint)"
  - "New competitive_context placeholder: extracted from evidence material field (confirms solid brass when present)"
  - "Template placeholder parity: all new template placeholders added to all format() call sites (USER_PROMPT_TEMPLATE and VARIANT_USER_PROMPT_TEMPLATE)"

requirements-completed: [PRMT-03, PRMT-04, PRMT-05]

duration: 5min
completed: 2026-02-21
---

# Phase 24 Plan 02: Category Expansion and Customer/Competitive Prompt Blocks Summary

**24 YAML categories (was 17), customer framing and competitive positioning blocks in every prompt, legacy build_category_guidance() fully removed**

## Performance

- **Duration:** ~5 min
- **Started:** 2026-02-21T19:34:07Z
- **Completed:** 2026-02-21T19:39:23Z
- **Tasks:** 2
- **Files modified:** 5

## Accomplishments

- Expanded shopping_intelligence.yaml from 17 to 24 categories by querying product_catalog for top revenue categories by variant count — identified 7 high-volume gaps (guest towel holders, wood shelves, tumbler toothbrush holders, soap dishes, multi hooks, paper towel holders, freestanding toilet tissue stands)
- Added `<customer_framing>` XML block to both USER_PROMPT_TEMPLATE and VARIANT_USER_PROMPT_TEMPLATE — guides GPT-5.2 to reason out concrete buyer scenarios (specific problem, room context, renovation vs replacement) rather than generic "upgrade your bathroom" language
- Added `<competitive_positioning>` XML block to both templates — guides GPT-5.2 to weave brass vs zinc, 28 finishes, 41 collections, concealed mounting, lifetime warranty naturally into copy without naming competitors
- Wired customer framing and competitive positioning into build_core_prompt() — extracts category + collection (customer context) and material confirmation from evidence (competitive context)
- Fully removed legacy _CATEGORY_GUIDANCE dict and build_category_guidance() from prompts.py — shopping_intelligence.yaml is now the sole canonical source for category guidance

## Task Commits

1. **Task 1: Expand category guidance and add customer/competitive prompt blocks** - `b3c725e4` (feat)
2. **Task 2: Wire customer framing and competitive positioning into prompt_builder.py** - `3b8eeb14` (feat)

## Files Created/Modified

- `src/feedops/config/shopping_intelligence.yaml` — Added 7 new category entries (guest towel holders, wood shelves, tumbler toothbrush holders, soap dishes, multi hooks, paper towel holders, freestanding toilet tissue stands) — now 24 total categories
- `src/feedops/pipeline/prompts.py` — Removed _CATEGORY_GUIDANCE and build_category_guidance(); added customer_framing and competitive_positioning XML blocks to USER_PROMPT_TEMPLATE and VARIANT_USER_PROMPT_TEMPLATE
- `src/feedops/api/prompt_builder.py` — Added Customer Framing and Competitive Positioning sections (steps 8 and 9); removed build_category_guidance import and fallback; category guidance section updated to YAML-only
- `src/feedops/api/main.py` — Removed stale unused import of build_category_guidance (Rule 3 auto-fix)
- `src/feedops/pipeline/generator.py` — Replaced build_category_guidance with get_category_guidance; added customer_context and competitive_context args to template format calls (Rule 3 auto-fix)

## Decisions Made

- Customer framing as a reasoning prompt, not a template: the block tells GPT-5.2 HOW to think about the buyer rather than providing a fill-in sentence. This is the key pattern for customer_scenario and emotional_resonance score improvements.
- Option A for prompt_builder implementation: section-based approach consistent with existing manually-built sections pattern. Avoids template migration that would have required touching more files.
- Queried product_catalog via Supabase to identify real missing categories by variant count — data-driven expansion rather than guessing.

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 3 - Blocking] Fixed stale build_category_guidance references in generator.py and main.py**
- **Found during:** Task 2 (wiring prompt_builder)
- **Issue:** After removing build_category_guidance from prompts.py, generator.py still imported and called it in 3 places; main.py had an unused import — both would cause ImportError at runtime
- **Fix:** Replaced build_category_guidance with get_category_guidance (from prompt_loader) in generator.py; removed unused import from main.py; added customer_context="" and competitive_context="" to generator.py template format() calls to satisfy new template placeholders
- **Files modified:** src/feedops/pipeline/generator.py, src/feedops/api/main.py
- **Verification:** `PYTHONPATH=./src python3 -c "from feedops.api.main import app; from feedops.pipeline.generator import build_split_prompt; print('All imports OK')"` — clean
- **Committed in:** 3b8eeb14 (Task 2 commit)

---

**Total deviations:** 1 auto-fixed (1 blocking — stale import references)
**Impact on plan:** Required fix — generator.py would fail to start without this. No scope creep.

## Issues Encountered

None beyond the auto-fixed blocking issue above.

## User Setup Required

None - no external service configuration required.

## Next Phase Readiness

- Phase 25 (Evaluate & Iterate) can now test content quality with the expanded 24-category YAML and customer/competitive framing blocks active
- customer_scenario and competitive_diff self_score fields should improve (currently 1-4/10, target 6-9/10 with these blocks)
- Cloud Run deployment requires skills directory in container (documented in 24-01 SUMMARY) — same Dockerfile change applies here
- main.py callers should pass mode="single" or mode="batch" to get_system_prompt() — this was documented in 24-01 as a next-step

## Self-Check: PASSED

All files present. All commits verified.

---
*Phase: 24-prompt-architecture*
*Completed: 2026-02-21*
