# Session State

## Project Reference

See: .planning/PROJECT.md

## Position

**Milestone:** v1.3a Content Generation Excellence
**Current phase:** 26 (Human Evaluation & Test Batch)
**Current Plan:** 26-03 (human evaluation and test batch publish)
**Status:** 10 test SKUs generated with v2 pipeline. Blind A/B comparison ready for Bobby + Robert. Awaiting human evaluation.
**Progress:** [█████████░] 92% (23/25 requirements satisfied, 2 EVAL requirements remain)

## What's Done

All content generation code work is complete and pushed to master:
- GPT-5.2 bugs fixed (Phase 23)
- Prompt architecture rewritten (Phase 24)
- 2 rounds of human evaluation with iteration (Phase 25)
- Prompt architecture research + audit (Phase 25.1)
- Per-platform generation with schemas + feature flag (Phase 25.2)
- Per-platform prompts rewritten as GPT-5.2 creative briefs (Phase 25.3)
- Production impact audit + Score model alignment (Phase 25.4)
- Skills updated with Round 2 feedback (Phase 25 Plan 06)
- Automated checks: 120/120 canonical, 63/63 unseen, 49 unit tests pass

## What's Left

1. **Phase 26:** Generate 10 SKUs with v2, Bobby + Robert gut-check review (8/10 threshold), publish test batch
2. **Phase 27:** Set FEEDOPS_PROMPT_VERSION=v2 in production, close milestone

**Quick code fixes that may be needed during Phase 26:**
- v2 Score model wiring (self_score -> Score model in generate_per_platform)
- shopping_intelligence wiring in v2 per-platform builders

## Decisions

- Skills are the creative authority for content generation; SYSTEM_PROMPT provides scaffolding only
- Product-specific data (narrative_copy, bullets) extracted as Product Design Story in prompts
- Finish name uses {FINISH_NAME} placeholder when no finish_code for Google/Bing
- Competitor material references prohibited in all content (positive-only brass framing)
- Robert's title formula codified: finish first, Collection keyword, dimension only when varies
- Evidence exclusion rules: weight capacity, detailed dimensions, installation specifics excluded
- Per-platform generation: separate GPT-5.2 calls for Google, Bing, Shopify, finish sentences
- prompt_version feature flag routes v1 (legacy single-call) vs v2 (per-platform multi-call)
- Per-platform prompts are ~8-10K creative briefs (down from 57K skill dump)
- Production now on v2 — FEEDOPS_PROMPT_VERSION=v2 set on Cloud Run (revision feedops-pipeline-00222-gc4)
- v2 per-platform self-score uses 3-criterion rubric (accuracy, specificity, engagement) not 10-criterion legacy rubric
- Score model uses 10-criterion rubric with composite denominator of 100 (legacy v1 only)
- Description length standardized to 700-900 chars
- "28 finishes" suppressed for Google/Bing (descriptions expand to variant-specific)
- [Phase 26]: v2 self-score uses 3-criterion rubric (accuracy/specificity/engagement), adapted quality scoring accordingly

## Session Log

- 2026-02-24: Phase 26-02 complete. Generated v2 content for all 10 test SKUs (Google + Bing). Zero constraint violations. Avg self-score 80.5/100. Blind A/B comparison document ready for Bobby + Robert evaluation.
- 2026-02-24: Phase 26-01 complete. Set FEEDOPS_PROMPT_VERSION=v2 on Cloud Run. Smoke test passed: SKU 1016 title + description + 28 finish sentences all correct via v2 per-platform pipeline.
- 2026-02-24: Found critical v1 bug: _extract_content_from_schema_response() discards content (returns "" → {FINISH_SENTENCE}). Fix: `if field_key and field_key in response:` at main.py:460. Restructured Phase 26 to 3 waves: bugfix → v2 generation → human eval.
- 2026-02-24: Roadmap cleanup — consolidated 10 completed phases under collapsible details, removed duplicate phases 25.5-25.7, renumbered remaining work to Phase 26 (human eval) and Phase 27 (deploy)
- Previous session: Phase 25.4 audit complete, all code pushed to master
