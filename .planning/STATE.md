# Session State

## Project Reference

See: .planning/PROJECT.md (updated 2026-02-21)

**Core value:** Transform low-performing product feeds into high-converting assets with AI content generation informed by Google Shopping ranking intelligence
**Current focus:** v1.3a Content Generation Excellence — Phase 23: Foundation

## Position

**Milestone:** v1.3a Content Generation Excellence
**Current phase:** 23 of 25 (Foundation — GPT-5.2 bugs + gold standards + rubric)
**Current plan:** 02 complete — 23-02 gold standards + 10-criterion rubric done
**Status:** Milestone complete
**Last activity:** 2026-02-21 — 23-02 executed: 10-criterion rubric, 15 gold standards loaded into feedops_v3

Progress: [████░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░] ~10% (v1.3a)

## Performance Metrics

**Velocity (all milestones):**
- Total plans completed: 68
- Milestones shipped: 4 (Phase 0, v1.0, v1.1, v1.2)

**v1.3a plans:** 2 completed (TBD total)

| Plan | Duration | Tasks | Files | Date |
|------|----------|-------|-------|------|
| 23-01 GPT-5.2 bug fixes | 4 min | 2 | 3 | 2026-02-21 |
| 23-02 Gold standards + 10-criterion rubric | 276s | 2 | 2 | 2026-02-21 |

## Accumulated Context

### Decisions

- [23-01]: json_schema strict mode uses _build_strict_schema() helper computed once at import; sampling_params dict pattern for conditional temperature
- [23-01]: XML tags preserve all SYSTEM_PROMPT section content unchanged — only === delimiters replaced with open/close XML tags
- [v1.3a]: Phase 23 combines GPT-5.2 bug fixes WITH gold standards and quality rubric — bugs must be fixed before prompt work begins, and creative direction must be established before prompt rewrite
- [v1.3a]: Phase structure: 23 (Foundation) → 24 (Prompt Architecture) → 25 (Evaluate & Iterate)
- [v1.2]: Skills-enhanced single model (est. 85-92/100) preferred over 6-agent pipeline (87.2/100 at 3x cost)
- [v1.2]: Unified build_core_prompt() — single code path for all 4 generation paths
- [Phase 23-foundation]: 10-criterion rubric replaces 6-criterion self_score: hook_quality (15%), product_specificity (15%), competitive_diff (12%), keyword_integration (10%), customer_scenario (10%), emotional_resonance (10%), factual_accuracy (10%), platform_compliance (8%), finish_integration (5%), variety_score (5%)
- [Phase 23-foundation]: 15 gold standard examples loaded into feedops_v3 template: 10 from google-shopping-content skill, 5 improved from quality-evaluation skill, covering 15 product categories

### Open Blockers

None.

### Tech Debt Carried from v1.2

- 2 orphaned components: GmcDisapprovalBadge, PromptLineagePanel (built but not surfaced in UI)
- Pre-existing duplicate migration file numbers (026, 032, 033) — non-blocking
- 5 GPT-5.2 bugs FIXED in 23-01 (GPT52-01 through GPT52-05 all resolved)

### Key Files for v1.3a

- Prompt authority: `src/feedops/api/prompt_builder.py`
- System prompt: `src/feedops/pipeline/prompts.py`
- OpenAI provider (bugs here): `src/feedops/providers/openai_provider.py`
- Runtime configs: `src/feedops/config/*.yaml` (8 files)
- Gold standards target table: `prompt_templates` (columns: gold_standard_examples, category_guidance)

## Session Continuity

Last session: 2026-02-21
Stopped at: Completed .planning/phases/23-foundation/23-02-PLAN.md
Resume file: .planning/phases/23-foundation/23-02-SUMMARY.md
