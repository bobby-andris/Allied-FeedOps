# Milestones

## v1.0: Pipeline Reliability Rewrite + Model Evaluation

**Status:** Complete (93% — Phase 7 Bing fix deferred)
**Dates:** 2026-03-01 → 2026-03-03
**Phases:** 1–6 completed, Phase 7 deferred

**Outcomes:**
- main.py decomposed from 3,737 to ~500 lines (9 extracted modules)
- All 5 GPT-5.2 bugs fixed
- Claude provider implemented with structured output
- Model evaluation: Claude Sonnet 4.6 won (84% cheaper, 2x faster, 8.85/10 blind score)
- Production go-live: FEEDOPS_PROVIDER=claude serving all traffic
- Deploy checklist workflow created

**Deferred:**
- Phase 7: Bing {FINISH_NAME} fix (96/137 titles still have hardcoded finish names)
- Dead code cleanup (generator.py legacy paths, backward-compat re-exports)
- Image support wiring in executor.py (~15 lines)
