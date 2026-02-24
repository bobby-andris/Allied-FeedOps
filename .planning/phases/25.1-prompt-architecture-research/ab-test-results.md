# A/B Prompt Testing Results (v2.1 — Variant-Level)

**Date:** 2026-02-23
**Phase:** 25.1-prompt-architecture-research, Plan 03 (revised)
**Model:** GPT-5.2 (reasoning_effort=medium, strict JSON schema)
**Status:** BLOCKED — OpenAI API quota exceeded (429). Script validated via dry-run. Rerun when quota replenished.

## What Changed from v1

1. **Variant-level generation**: Each SKU tested with a specific finish (not master-SKU level)
2. **{FINISH_NAME} must be first title element**: Validated in analysis
3. **Finish context injected**: Per-finish visual, design style, compelling sentence from finish-expertise
4. **Competitor brand detection**: New analysis checks for leaked competitor names
5. **Gold standard examples in system prompt**: 5 exemplars from google-shopping-content skill
6. **Competitor brand prohibition explicit**: P0 rule in system prompt

## Test Configuration

| SKU | Category | Finish | Type |
|-----|----------|--------|------|
| 1025U | Paper Towel Holders | Polished Nickel | Representative |
| WP-2/16-GAL | Glass Shelves | Oil Rubbed Bronze | Representative |
| DMF-2/2X | Make-Up Mirrors | Satin Brass | Representative |
| 1026 | Tumbler Toothbrush Holders | Antique Brass | Unseen |
| 1031/18 | Towel Bars | Matte Black | Unseen |
| 1032 | Soap Dishes | Polished Chrome | Unseen |

## Prompt Size Comparison (from dry-run)

| Variation | System Chars | System Tokens | Reduction vs Current |
|-----------|-------------|---------------|---------------------|
| A_Current | 266,242 | 57,504 | -- (baseline) |
| B_Minimal | 6,406 | 1,328 | 97.7% |
| C_Optimized | 18,313 | 3,890 | 93.2% |

**Note on C_Optimized size:** v2.1 is larger than v2 (18K vs 8.2K) because it DISTILLS essential domain knowledge instead of stripping it. This includes:
- 5 gold standard examples (~5K chars)
- Title formula with {FINISH_NAME} enforcement
- {FINISH_SENTENCE} integration rules with good/bad examples
- Brand voice truths (solid brass, 41 collections, concealed mounting)
- Interior designer perspective
- Explicit competitor brand prohibition
- Category-specific content structure

The 93% reduction from current still eliminates all 12 contradictions and all Claude Code metadata noise.

## How to Rerun

```bash
# Ensure OpenAI quota is available, then:
set -a && source .env.vercel && set +a
PYTHONPATH=./src .venv/bin/python scripts/ab_prompt_test.py

# Quick single-SKU test:
PYTHONPATH=./src .venv/bin/python scripts/ab_prompt_test.py --sku 1025U

# Representative SKUs only (3 SKUs x 3 variations = 9 calls):
PYTHONPATH=./src .venv/bin/python scripts/ab_prompt_test.py --representative-only
```

The script will:
1. Generate content for each SKU in its assigned finish
2. Validate titles start with finish name
3. Check for competitor brand leaks
4. Check for Robert's concerns
5. Write detailed side-by-side results to this file

---
*Generated: 2026-02-23*
*Script: scripts/ab_prompt_test.py (v2.1 -- variant-level)*
*Dry-run validated: all prompts build correctly, all SKU data loads*
