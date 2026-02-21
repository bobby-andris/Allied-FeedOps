# Session State

## Project Reference

See: .planning/PROJECT.md (updated 2026-02-21)

**Core value:** Transform low-performing product feeds into high-converting assets with AI content generation informed by Google Shopping ranking intelligence
**Current focus:** v1.3a Content Generation Excellence — Phase 23: Foundation

## Position

**Milestone:** v1.3a Content Generation Excellence
**Current phase:** 23 of 25 (Foundation — GPT-5.2 bugs + gold standards + rubric)
**Current plan:** Not started (context gathered)
**Status:** Context gathered — ready to plan
**Last activity:** 2026-02-21 — Phase 23 context gathered (skills cover all creative direction)

Progress: [░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░] 0% (v1.3a)

## Performance Metrics

**Velocity (all milestones):**
- Total plans completed: 68
- Milestones shipped: 4 (Phase 0, v1.0, v1.1, v1.2)

**v1.3a plans:** 0 completed (TBD total)

## Accumulated Context

### Decisions

- [v1.3a]: Phase 23 combines GPT-5.2 bug fixes WITH gold standards and quality rubric — bugs must be fixed before prompt work begins, and creative direction must be established before prompt rewrite
- [v1.3a]: Phase structure: 23 (Foundation) → 24 (Prompt Architecture) → 25 (Evaluate & Iterate)
- [v1.2]: Skills-enhanced single model (est. 85-92/100) preferred over 6-agent pipeline (87.2/100 at 3x cost)
- [v1.2]: Unified build_core_prompt() — single code path for all 4 generation paths

### Open Blockers

None.

### Tech Debt Carried from v1.2

- 2 orphaned components: GmcDisapprovalBadge, PromptLineagePanel (built but not surfaced in UI)
- Pre-existing duplicate migration file numbers (026, 032, 033) — non-blocking
- 5 known GPT-5.2 bugs to fix in Phase 23 (see REQUIREMENTS.md GPT52-01 through GPT52-05)

### Key Files for v1.3a

- Prompt authority: `src/feedops/api/prompt_builder.py`
- System prompt: `src/feedops/pipeline/prompts.py`
- OpenAI provider (bugs here): `src/feedops/providers/openai_provider.py`
- Runtime configs: `src/feedops/config/*.yaml` (8 files)
- Gold standards target table: `prompt_templates` (columns: gold_standard_examples, category_guidance)

## Session Continuity

Last session: 2026-02-21
Stopped at: Phase 23 context gathered — ready to run /gsd:plan-phase 23
Resume file: .planning/phases/23-foundation/23-CONTEXT.md
