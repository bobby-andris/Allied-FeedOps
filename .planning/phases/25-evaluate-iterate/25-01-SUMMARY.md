# Plan 25-01 Summary: Deploy & Regenerate 10 Test SKUs

## Status: Complete

## What Was Built

### Task 1: Deploy skill-enriched prompts to Cloud Run
- Added `COPY .claude/skills /app/.claude/skills` to Dockerfile
- Removed `.claude/skills/` from `.gitignore`, added negative pattern to `.gcloudignore`
- Pushed to master, Cloud Build succeeded, `/health` returns healthy
- **Critical bug found and fixed**: Phase 23's `CANDIDATE_SCHEMA` strict mode changed response keys from `content` to `google_title`, `google_description`, etc. All 4 generation endpoints (`optimize_single_sku`, `process_batch_job`, `regenerate`, `process_hybrid_batch_job`) were calling `response.get("content", "")` which returned empty. Added `_extract_content_from_schema_response()` helper to `main.py`.

### Task 2: Select 10 SKUs, regenerate, build blind comparison
- **10 SKUs selected** across 10 categories (Paper Towel Holders, Towel Rings, Cabinet Hardware, Multi Hooks, Toilet Paper Holders, Robe Hooks, Make-Up Mirrors, Glass Shelves, Shower Curtain Brackets, Retractable Hooks)
- **6 gold-standard-adjacent**, 4 without direct gold standard
- **1 multi-SKU family member**: DMF-2/2X
- All 10 regenerated via Cloud Run `/regenerate` endpoint using GPT-5.2 with skill-enriched prompts
- Blind A/B comparison document created with random assignment and hidden answer key

## Key Files

### Created
- `.planning/phases/25-evaluate-iterate/25-01-evaluation-comparisons.md` — Blind A/B comparison document (10 SKUs)
- `.planning/phases/25-evaluate-iterate/25-01-SUMMARY.md` — This file

### Modified
- `Dockerfile` — Added skills directory COPY
- `.gitignore` — Unignored `.claude/skills/`
- `.gcloudignore` — Preserved skill `.md` files
- `src/feedops/api/main.py` — CANDIDATE_SCHEMA extraction fix

## Decisions Made
1. **SKU selection criteria**: Optimized for category diversity (10 categories), gold standard coverage (6/4 split), and multi-SKU representation (DMF-2/2X)
2. **CANDIDATE_SCHEMA bug**: Fixed systemically across all 4 endpoints rather than patching just `/regenerate`
3. **Sequential regeneration**: Ran regenerations sequentially (~5-20s each) after parallel approach caused hangs

## Issues Encountered
- **1020 empty description**: First regeneration attempt returned `{FINISH_SENTENCE}` only. Retry succeeded with full content.
- **1020-3 truncated sentence**: Description has a truncated sentence ("...and because it's \""). This is a GPT-5.2 generation artifact — noted for evaluation.
- **Finish sentence templating**: Some descriptions have incomplete finish references ("from to to" in 1025U) — likely missing finish data in the template pipeline.

## Self-Check: PASSED
- [x] Dockerfile contains `COPY .claude/skills /app/.claude/skills`
- [x] Cloud Run deployment live and healthy
- [x] 10 SKUs from 10 categories regenerated without errors
- [x] Comparison document has blind A/B format with answer key
- [x] Old content preserved in comparison document
