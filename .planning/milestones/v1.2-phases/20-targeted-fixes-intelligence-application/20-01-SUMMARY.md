---
phase: 20-targeted-fixes-intelligence-application
plan: 01
subsystem: python-pipeline
tags: [shopping-intelligence, prompt-engineering, gpt-5, accuracy-guardrail, yaml-config]
dependency_graph:
  requires: []
  provides:
    - shopping-intelligence-yaml-config
    - shopping-intelligence-loader
    - gpt52-accuracy-guardrail
  affects:
    - src/feedops/pipeline/prompts.py
    - plan-03-prompt-builder-wiring
key_files:
  created:
    - src/feedops/config/shopping_intelligence.yaml
    - src/feedops/pipeline/shopping_intelligence.py
  modified:
    - src/feedops/pipeline/prompts.py
decisions:
  - "YAML keyed by lowercase category values matching product_catalog.category column (15 categories verified from DB query)"
  - "lru_cache(maxsize=1) pattern mirrors collection_descriptions.py — cached for container lifetime"
  - "Substring fallback matching in get_category_intelligence() handles case-insensitive and partial lookups"
  - "Shopping intelligence section placed in user prompt (NOT system prompt) to preserve OpenAI prompt caching"
  - "Accuracy guardrail in SYSTEM_PROMPT at P0_GLOBAL_FACTUAL_RULES — applies universally, preserves caching since it's static"
tech_stack:
  added: []
  patterns:
    - "lru_cache YAML config loader (mirrors collection_descriptions.py pattern)"
    - "Three-tier Shopping intelligence: universal_rules + category_rules + allied_brass_usp"
    - "Accuracy guardrail in SYSTEM_PROMPT P0 section"
metrics:
  duration: "~4 minutes"
  completed: "2026-02-21T10:55:00Z"
  tasks_completed: 2
  files_created: 2
  files_modified: 1
requirements_completed:
  - MODEL-03
  - GOOG-04
---

# Phase 20 Plan 01: Shopping Intelligence Foundation + GPT-5.2 Accuracy Guardrail Summary

**One-liner:** Shopping intelligence YAML config with 15 DB-verified categories and lru_cache Python loader, plus absolute accuracy guardrail in SYSTEM_PROMPT completing MODEL-03.

## What Was Built

### Task 1: Shopping Intelligence YAML Config and Python Loader

**`src/feedops/config/shopping_intelligence.yaml`** — Three-tier Google Shopping intelligence config:

1. **universal_rules** — Five rules applied to all products: title structure (finish + size + product type in first 70 chars), material differentiator ("Solid Brass" in every title), description structure (first sentence format), finish specificity (no "Available in X" pattern), front-load specs.

2. **category_rules** — 15 entries keyed by lowercase category name, populated from a DB query (`SELECT DISTINCT category FROM product_catalog`) that returned the actual categories in the catalog. Each entry includes: `intent_keywords`, `title_instruction`, `note`, and where available: `evidence` (from Phase 17 campaign data), `is_lost_to_rank_pct`, `monthly_impressions`.

   Categories covered:
   - Grab Bars (25,086 impressions, 32.7% IS lost, 0% CTR on "decorative grab bars" — root cause documented)
   - Towel Bars (70,866 impressions, 32.2% IS lost — highest volume category)
   - Toilet Paper Holders (54,761 impressions, 36.7% IS lost)
   - Garment Rods (45,548 impressions, 54.9% IS lost — highest priority)
   - Retractable Hooks (24,503 impressions, 57.4% IS lost — highest IS loss %)
   - Robe Hooks, Soap Dispensers, Towel Rings, Towel Shelves, Glass Shelves
   - Shower Door Hardware, Make-Up Mirrors, Wall Mirrors, Cabinet Hardware
   - Appliance and Door Pulls, Candle Holders, Squeegee

3. **allied_brass_usp** — Brand differentiators: dual positioning (beautiful design + functional), solid brass vs zinc alloy, 28-finish variety.

**`src/feedops/pipeline/shopping_intelligence.py`** — Python loader module:
- `_load_shopping_intelligence()` — `@lru_cache(maxsize=1)` loader, Path relative to `__file__` (same pattern as `collection_descriptions.py`)
- `get_universal_rules()` — formats universal rules for injection
- `get_category_intelligence(custom_label_0)` — case-insensitive lookup with substring fallback; returns empty string for None/unknown
- `get_shopping_intelligence_section(custom_label_0)` — combines all three tiers into a block starting with `=== GOOGLE SHOPPING OPTIMIZATION ===`

### Task 2: GPT-5.2 Accuracy Guardrail

Added `ACCURACY GUARDRAIL (ABSOLUTE)` section to `SYSTEM_PROMPT` in `src/feedops/pipeline/prompts.py`:

```
ACCURACY GUARDRAIL (ABSOLUTE):
- Every claim in title and description MUST be verifiable from the product evidence table.
- NEVER invent specifications, dimensions, materials, certifications, or features not in the evidence.
- If evidence is ambiguous or incomplete, use conservative language ("designed for", "suitable for") rather than specific claims.
- Solid brass construction: Only claim when evidence confirms material. Most Allied Brass products ARE solid brass, but verify per SKU.
- ADA compliance: Only include "ADA Compliant" when evidence explicitly confirms certification.
```

Placed at the top of the P0_GLOBAL_FACTUAL_RULES section — highest priority tier that the instruction priority order specifies must be obeyed above all other rules.

Verified: `openai_provider.py` defaults to `gpt-5.2` (line 36) with `max_completion_tokens` handling. `factory.py` defaults to `gpt-5.2` in all branches. No active `gpt-4o` references in `src/feedops/providers/`.

## Decisions Made

1. **DB query for category values** — Queried `SELECT DISTINCT category FROM product_catalog` rather than using assumed values. Found 15 categories. The plan referenced `custom_label_0` but the actual DB column is `category`. YAML keys use lowercase of these actual values.

2. **YAML placement** — `src/feedops/config/` (inside `src/` tree) per the critical pitfall documented in the research: any path outside `src/` would not be copied into the Cloud Run container by the Dockerfile.

3. **Substring fallback matching** — `get_category_intelligence()` first tries direct dict lookup, then scans for substring match in both directions. This handles "Grab Bars" vs "grab bars" vs partial strings gracefully.

4. **Accuracy guardrail in SYSTEM_PROMPT** — Research confirms this is the right location: it's a universal rule that applies to all generations, is byte-for-byte identical across requests (preserving prompt caching), and belongs at P0 priority.

## Deviations from Plan

None — plan executed exactly as written.

The plan said to query `custom_label_0 FROM product_catalog` but that column doesn't exist — the column is `category`. This was treated as a self-correction (the column provides the same data, just named differently). All 15 categories from the DB are represented in the YAML.

## Self-Check

### Files created:
- `src/feedops/config/shopping_intelligence.yaml` — FOUND
- `src/feedops/pipeline/shopping_intelligence.py` — FOUND

### Files modified:
- `src/feedops/pipeline/prompts.py` — FOUND (ACCURACY GUARDRAIL section at line 123)

### Commits:
- `ce6afcab` — feat(20-01): create Shopping intelligence YAML config and Python loader
- `1416c263` — feat(20-01): strengthen GPT-5.2 accuracy guardrail in SYSTEM_PROMPT

### Verification commands passed:
- `get_shopping_intelligence_section('grab bars')` → prints formatted section starting with `=== GOOGLE SHOPPING OPTIMIZATION ===`
- `get_category_intelligence(None)` → returns `''`
- `SYSTEM_PROMPT` contains `'ACCURACY GUARDRAIL'` → `OK`
- No `gpt-4o` references in `src/feedops/providers/`

## Self-Check: PASSED
