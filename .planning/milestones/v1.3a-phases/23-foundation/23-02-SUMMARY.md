---
phase: 23-foundation
plan: 02
subsystem: content-generation
tags: [gold-standards, quality-rubric, prompt-engineering, pipeline]
depends_on: []
provides: [10-criterion-rubric, gold-standard-examples, batch-evaluation]
affects: [pipeline-scoring, content-review, prompt-templates]
tech_stack:
  added: []
  patterns: [supabase-upsert, dry-run-flag, argparse-cli]
key_files:
  modified:
    - src/feedops/pipeline/prompts.py
  created:
    - scripts/load_gold_standards.py
decisions:
  - "10-criterion rubric replaces 6-criterion self_score: hook_quality, product_specificity, competitive_diff, keyword_integration, customer_scenario, emotional_resonance, factual_accuracy, platform_compliance, finish_integration, variety_score"
  - "Gold examples sourced from two skills verbatim: 10 from google-shopping-content SKILL.md, 5 improved versions from quality-evaluation SKILL.md"
  - "feedops_v3 upserted as the active prompt_templates row — deactivates all prior active templates on load"
  - "Batch evaluation reports both old_score (numeric) and new_score (computed from quality_breakdown self_score keys) — new scores only appear for content generated with the updated pipeline"
metrics:
  duration: 276s
  tasks_completed: 2
  files_modified: 1
  files_created: 1
  completed_date: "2026-02-21"
requirements_satisfied:
  - GOLD-01
  - GOLD-02
  - GOLD-03
  - GOLD-04
---

# Phase 23 Plan 02: Gold Standards and 10-Criterion Quality Rubric Summary

One-liner: Replaced 6-criterion self-score with 10-criterion click-worthiness rubric and loaded 15 verbatim gold standards across 15 product categories into prompt_templates.

## What Was Built

### Task 1: 10-Criterion Self-Score Rubric (GOLD-01, GOLD-03)

**File:** `src/feedops/pipeline/prompts.py`

Replaced the 6-criterion `self_score` in `CANDIDATE_SCHEMA` with a 10-criterion rubric that measures click-worthiness, not rule compliance:

| Old Criteria (removed) | New Criteria (added) | Weight |
|---|---|---|
| specificity | hook_quality | 15% |
| benefit_coverage | product_specificity | 15% |
| keyword_inclusion | competitive_diff | 12% |
| format_adherence | keyword_integration | 10% |
| brand_voice | customer_scenario | 10% |
| factual_accuracy (kept) | emotional_resonance | 10% |
| | factual_accuracy | 10% |
| | platform_compliance | 8% |
| | finish_integration | 5% |
| | variety_score | 5% |

The old rubric gave 81% to bad content because it rewarded template adherence. The new rubric measures whether a shopper would click. A generic description that follows all rules now scores 50-60 instead of 80+.

Updated the `SYSTEM_PROMPT` scoring intent section to include:
- Explicit criteria names and weights
- "A description that follows all rules but is generic should score 50-60, not 80+"
- "Score each criterion 0-10 independently. Do NOT inflate to hit a target."

### Task 2: Gold Standard Loader (GOLD-02, GOLD-04)

**File:** `scripts/load_gold_standards.py`

Created a Python script that:

1. **Embeds 15 gold standard examples** sourced verbatim from skill files:
   - 10 examples from `google-shopping-content` SKILL.md (scores 87-92/100, avg 89.3)
   - 5 improved examples from `quality-evaluation` SKILL.md bad-to-good section (scores 75-79/100)

2. **Covers 15 product categories** (exceeds 10+ requirement):
   Cabinet Hardware, Cabinet Knobs, Glass Shelves, Grab Bars, Guest Towel Holders, Makeup Mirrors, Mirrors, Multi Hooks, Multi Hooks 3-Position, Paper Towel Holders, Robe Hooks, Shower Accessories, Toilet Paper Holders, Toilet Paper Holders Wall Mount, Towel Rings

3. **Loaded into Supabase** as `feedops_v3` template (active), JSONB format readable by `prompt_loader.py`

4. **--dry-run flag** prints all 15 examples with titles and scores without any DB write

5. **--evaluate flag** queries `generated_content` for recent candidate_content, computes new weighted scores from `quality_breakdown.self_score`, and prints a comparison table showing old score vs new score vs grade

**Run commands:**
```bash
# Dry run
python scripts/load_gold_standards.py --dry-run

# Load into Supabase
python scripts/load_gold_standards.py

# Evaluate recent content
python scripts/load_gold_standards.py --evaluate

# Evaluate specific SKU
python scripts/load_gold_standards.py --evaluate --sku WP-2/16-GAL
```

## Verification Results

All 7 verification criteria passed:

1. CANDIDATE_SCHEMA self_score has exactly 10 criteria (old `specificity` etc. removed)
2. SYSTEM_PROMPT scoring intent references new criteria and weights
3. prompt_templates has 15 gold standard examples (active template = feedops_v3 v3)
4. Gold standards cover 15 distinct product categories
5. evaluate_recent_content() function exists with 10-criterion rubric weights
6. prompt_loader.py format_gold_standard_examples() and format_gold_standard_examples_bundle() both work with new format
7. All Python imports succeed without errors

## Deviations from Plan

None — plan executed exactly as written.

## Key Data Points

- **Old rubric**: CL-28-18 description scored 81% (good) despite being a fragment-opening keyword dump
- **New rubric**: Same description scores 31% (Reject) — 50-point gap is the difference between measuring compliance and measuring quality
- **Gold standards average**: 85.3/100 across 15 examples (vs 89.3 for top 10)
- **Pipeline impact**: Next generation run will output 10 self-score keys instead of 6; downstream quality_breakdown storage will capture the new rubric automatically

## Self-Check: PASSED

All files present and all commits verified:
- `src/feedops/pipeline/prompts.py` — FOUND
- `scripts/load_gold_standards.py` — FOUND
- `.planning/phases/23-foundation/23-02-SUMMARY.md` — FOUND
- Commit `751b549f` (Task 1 - rubric update) — FOUND
- Commit `58049c5c` (Task 2 - gold standard loader) — FOUND
