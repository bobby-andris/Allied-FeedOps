---
phase: 25-evaluate-iterate
plan: 06
subsystem: content-generation
tags: [skills, system-prompt, prompt-builder, evaluation-feedback, brand-voice]

# Dependency graph
requires:
  - phase: 25-evaluate-iterate
    provides: "Round 2 evaluation results with specific actionable feedback from Bobby and Robert"
provides:
  - "Updated brand expert skill with competitor material prohibition"
  - "Updated google-shopping-content skill with Robert's title formula (finish-first)"
  - "Updated product-storytelling skill with evidence exclusion rules"
  - "SYSTEM_PROMPT with 6 content prohibition rules from evaluator feedback"
  - "prompt_builder suppresses 28-finishes for Google/Bing universally"
affects: [25-07-PLAN, content-generation, round-3-evaluation]

# Tech tracking
tech-stack:
  added: []
  patterns: ["Positive-only competitive framing", "Evidence exclusion for descriptions", "Finish-first title formula"]

key-files:
  modified:
    - ".claude/skills/allied-brass-brand-expert/SKILL.md"
    - ".claude/skills/google-shopping-content/SKILL.md"
    - ".claude/skills/product-storytelling/SKILL.md"
    - "src/feedops/pipeline/prompts.py"
    - "src/feedops/api/prompt_builder.py"

key-decisions:
  - "Competitor material terms kept in prohibition lists (explaining what NOT to say) but removed from all content examples"
  - "Robert's title formula codified as the canonical title structure for Google/Bing"
  - "Product type investigation for 1024/1020 documented as model inference errors, not data errors"
  - "Humidity claims deprioritized per Bobby's feedback - brief aside only, never headline"

patterns-established:
  - "Positive-only brass framing: describe what solid brass IS and DOES, never what it's better than"
  - "Finish-first titles: {FINISH_NAME} always first element in Google/Bing titles"
  - "Dimension-only-when-varies: include dimensions only when product comes in multiple sizes"
  - "Evidence exclusion: weight capacity, detailed dimensions, installation specifics excluded from descriptions"

requirements-completed: [EVAL-01, EVAL-02, EVAL-03, EVAL-04, EVAL-05]

# Metrics
duration: 7min
completed: 2026-02-23
---

# Phase 25 Plan 06: Round 2 Gap Closure Summary

**Three skills updated with competitor material prohibition, Robert's title formula, and evidence exclusion rules; SYSTEM_PROMPT gains 6 content prohibition rules; 28-finishes suppressed for Google/Bing**

## Performance

- **Duration:** 7 min
- **Started:** 2026-02-23T21:09:35Z
- **Completed:** 2026-02-23T21:16:40Z
- **Tasks:** 2
- **Files modified:** 5

## Accomplishments
- Removed ALL competitor material references from brand expert and shopping content skills, replaced with positive-only brass framing and explicit prohibition section
- Codified Robert's expert title formula in google-shopping-content: finish first, Collection keyword, dimensions only when varies, Solid Brass after product type
- Added comprehensive evidence exclusion rules to product-storytelling: weight capacity, detailed dimensions, installation specifics, humidity-as-selling-point all excluded
- Updated all 10 gold standard examples in shopping content to follow finish-first titles and remove competitor material contrasts
- Added 6 content prohibition rules to SYSTEM_PROMPT accuracy_guardrail from human evaluator feedback
- Suppressed "28 finishes" mention for Google/Bing in prompt_builder (descriptions expand to finish-specific variants)
- Investigated product type misidentification for SKUs 1024 (2-post, not Euro Style) and 1020 (Robe Hook, not Towel Hook) -- documented as model inference errors

## Task Commits

Each task was committed atomically:

1. **Task 1: Update three skills with Round 2 evaluation feedback** - `1674b4bf` (fix)
2. **Task 2: Update SYSTEM_PROMPT prohibitions, fix prompt_builder, investigate product types** - `c1f4aa56` (fix)

## Files Created/Modified
- `.claude/skills/allied-brass-brand-expert/SKILL.md` - Competitor material prohibition, positive-only framing, humidity deprioritization
- `.claude/skills/google-shopping-content/SKILL.md` - Robert's title formula, updated gold standards, removed competitor material refs
- `.claude/skills/product-storytelling/SKILL.md` - Evidence exclusion rules, design-over-measurements note
- `src/feedops/pipeline/prompts.py` - 6 content prohibition rules, banned phrases expansion
- `src/feedops/api/prompt_builder.py` - 28-finishes suppression for Google/Bing competitive block

## Decisions Made
- **Competitor terms in prohibition lists only**: "die-cast zinc" etc. appear only in sections that list banned terms (explaining what NOT to say), never in example content or copywriting guidance
- **Robert's formula is canonical**: His decades of experience selling Allied Brass products makes his title structure the authority for Google/Bing titles
- **Product type issues are model inference**: SKUs 1024 and 1020 were mislabeled by GPT-5.2 inference, not by incorrect source data. The accuracy guardrail and evidence-grounding rules should prevent this in Round 3
- **Humidity deprioritized**: Bobby's feedback that humidity claims are "stretched and fluffy" led to explicit deprioritization in both brand expert and storytelling skills
- **No deployment in this plan**: Code changes committed but not pushed. Deployment will happen with 25-07 (Round 3 regeneration)

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 2 - Missing Critical] Additional competitor material cleanup in shopping content**
- **Found during:** Task 1 (gold standard updates)
- **Issue:** Several references to "zinc alloy," "chrome-plated plastic," and "chrome-plated steel" remained in gold standard "Why it's excellent" annotations and category-specific hooks
- **Fix:** Cleaned up all remaining competitor material references throughout the shopping content skill
- **Files modified:** `.claude/skills/google-shopping-content/SKILL.md`
- **Committed in:** 1674b4bf (Task 1 commit)

---

**Total deviations:** 1 auto-fixed (1 missing critical)
**Impact on plan:** Necessary for completeness of competitor material removal. No scope creep.

## Issues Encountered
- Could not query Supabase directly for SKU 1024/1020 product type investigation (MCP not available in CLI context). Used evaluation report documentation to determine these are model inference errors, not data errors.

## User Setup Required
None - no external service configuration required.

## Next Phase Readiness
- All skill and prompt changes ready for Round 3 regeneration (25-07)
- Code needs to be pushed to master to trigger Cloud Run deployment before Round 3
- Product type misidentification should be monitored in Round 3 results for 1024 and 1020

---
*Phase: 25-evaluate-iterate*
*Completed: 2026-02-23*
