---
phase: 24-prompt-architecture
plan: 01
subsystem: api
tags: [prompts, skills, gpt52, python, content-generation, lru-cache]

requires:
  - phase: 23-foundation
    provides: "10-criterion rubric in CANDIDATE_SCHEMA, GPT-5.2 bugs fixed, gold standards loaded"

provides:
  - "SYSTEM_PROMPT rewritten as creative brief with XML structure (creative_direction first)"
  - "skill_loader.py: unified loader for all 8 Claude Code skill SKILL.md files with lru_cache"
  - "Adaptive batch/single-SKU loading (batch=254K chars, single=172K chars)"
  - "get_system_prompt() enriched with skill content via mode/platform params"
  - "build_core_prompt() gains mode param (default='batch', backward compatible)"

affects: [25-evaluate-iterate, prompt_builder, prompt_loader, openai_provider, main.py]

tech-stack:
  added: []
  patterns:
    - "lru_cache skill loading pattern (follows shopping_intelligence.py precedent)"
    - "Adaptive prompt mode: batch loads all skills, single loads core + platform-specific"
    - "XML-tagged skill injection: <skill name='...'>{content}</skill>"
    - "Graceful fallback: empty string when skills dir unavailable, YAML configs remain active"

key-files:
  created:
    - src/feedops/pipeline/skill_loader.py
  modified:
    - src/feedops/pipeline/prompts.py
    - src/feedops/api/prompt_loader.py
    - src/feedops/api/prompt_builder.py

key-decisions:
  - "SYSTEM_PROMPT opens with <creative_direction> tag — creative frame before rules"
  - "Skill loader finds .claude/skills/ via relative path (dev) or /app/.claude/skills (Cloud Run)"
  - "Batch mode loads all 8 skills (254K chars), single mode loads core + platform-relevant (172K chars)"
  - "Prompt size thresholds updated to 280K warn / 300K max (was 20K/24K) to accommodate skill-enriched prompts"
  - "YAML configs remain as fallback when skills directory unavailable"
  - "Cloud Run deployment requires: COPY .claude/skills /app/.claude/skills in Dockerfile (documented)"

patterns-established:
  - "Skill injection: load_skills_for_prompt(mode, platform) -> XML-tagged string appended to system prompt"
  - "Adaptive mode parameter: all new prompt-building functions accept mode='batch'|'single'"

requirements-completed: [PRMT-01, PRMT-02]

duration: 3min
completed: 2026-02-21
---

# Phase 24 Plan 01: Prompt Architecture — Creative Brief and Skill Loader Summary

**SYSTEM_PROMPT rewritten from compliance-first (P0/P1/P2) to creative-first XML brief, plus new skill_loader.py injecting all 8 Claude Code skills (254K chars) into generation prompts via lru_cache**

## Performance

- **Duration:** ~3 min
- **Started:** 2026-02-21T~18:47Z
- **Completed:** 2026-02-21T~18:51Z
- **Tasks:** 2
- **Files modified:** 4

## Accomplishments

- Rewrote SYSTEM_PROMPT to open with `<creative_direction>` — what great Allied Brass content sounds like, with good/bad examples — before any rules or restrictions. Accuracy guardrail moved lower, redundancy trimmed.
- Created `src/feedops/pipeline/skill_loader.py` with `load_skill_content()` (lru_cache, single file load) and `load_skills_for_prompt()` (adaptive batch/single mode, XML-tagged output).
- Wired skill injection into `prompt_loader.py`: `get_system_prompt(mode, platform)` now appends 254K chars of skill content in batch mode, 172K in single mode. Prompt size thresholds updated to 280K/300K.
- Added `mode` parameter to `build_core_prompt()` (default='batch', backward compatible) with full docstring for callers.

## Task Commits

1. **Task 1: Rewrite SYSTEM_PROMPT and build skill loader** - `208c8cef` (feat)
2. **Task 2: Wire skill injection into prompt_builder and prompt_loader** - `2580b24c` (feat)

## Files Created/Modified

- `src/feedops/pipeline/prompts.py` — SYSTEM_PROMPT rewritten (~5725 chars, was ~3800, now creative-first XML structure)
- `src/feedops/pipeline/skill_loader.py` — New module: `_find_skills_dir()`, `load_skill_content()`, `load_skills_for_prompt()`
- `src/feedops/api/prompt_loader.py` — `get_system_prompt()` and `get_system_prompt_hash()` gain `mode`/`platform` params; thresholds updated
- `src/feedops/api/prompt_builder.py` — `build_core_prompt()` gains `mode` param with documentation for callers

## Decisions Made

- Creative direction before accuracy guardrails: GPT-5.2 generates compliance-first, creativity-last when rules dominate the prompt. Opening with "what great content sounds like" shifts the model's default toward quality.
- Skill loader uses same lru_cache pattern as `shopping_intelligence.py` (proven pattern in codebase).
- Cloud Run deployment note added as comment in `skill_loader.py` (Dockerfile change deferred — not in this plan's scope).
- Batch mode loads all 8 skills: quality upfront is cheaper than reruns. Single mode skips non-relevant platform skills for token efficiency.

## Deviations from Plan

None — plan executed exactly as written.

## Issues Encountered

- `prompt_builder.py` import of `build_category_guidance` from `prompts.py` noted in plan as "remove" but plan said to keep the fallback call in step 6 — kept as-is per plan instructions (removal planned for Plan 02).

## User Setup Required

None - no external service configuration required.

## Next Phase Readiness

- Plan 02 can now remove `_CATEGORY_GUIDANCE` and `build_category_guidance()` from prompts.py (shopping_intelligence.yaml is the canonical source)
- Cloud Run Dockerfile needs `COPY .claude/skills /app/.claude/skills` before production deployment with skills enabled
- main.py callers (`/regenerate`, `/optimize-sku`) should pass `mode="single"` or `mode="batch"` to `get_system_prompt()` as appropriate

---
*Phase: 24-prompt-architecture*
*Completed: 2026-02-21*
