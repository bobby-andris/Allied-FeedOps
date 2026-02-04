## FeedOps “Perfect Output” — New Agent Handoff Prompt

### Mission (3–5 lines)
You are continuing work on `Allied-FeedOps`, a Python (uv) project that generates platform-specific product titles/descriptions (Google, Bing, Shopify) for Allied Brass products. The system must be **fully grounded in product data** (no invented specs, no source-citation leakage). Your goal is to iteratively improve **CTR/CVR/brand voice** using the **offline heuristic evaluator** and optional **Apify SERP/Shopping keyword research**.

### What’s already in place (high-level)
- **Platform outputs**: Google/Bing/Shopify fields are generated and exported as `exports/<platform>-patch-<SKU>.json`.
- **Multimodal grounding**: the LLM may receive the product image (when available).
- **Citation leakage prevention**: customer-facing fields must never contain `catalog_csv.*` strings.
- **Offline evaluation**: `evaluate-exports` scores exports for CTR/CVR/voice proxies to compare prompt variants quickly.
- **Keyword bank**: optional local `data/keyword-bank.json` (gitignored) can inject `external_keywords` into evidence for keyword/intent guidance (phrases only, not facts).

### Key files to know
- **Prompt logic**: `src/feedops/pipeline/prompts.py`
- **Evidence builder**: `src/feedops/pipeline/evidence.py`
- **Optimizer orchestration**: `src/feedops/pipeline/optimize.py`
- **Claim verification**: `src/feedops/pipeline/verifier.py`
- **Offline scoring**: `src/feedops/quality/scoring.py`
- **Exports evaluator**: `src/feedops/quality/evaluator.py`
- **CLI**: `src/feedops/cli/main.py`
- **Content rules source-of-truth**: `AGENTS.md`

### Run commands (always use this pattern)
- **Tests**:
  - `PYTHONPATH=./src .venv/bin/python -m pytest tests/ -v`
- **Optimize one SKU (dry run)**:
  - `PYTHONPATH=./src .venv/bin/python -m feedops.cli.main optimize --parent-sku "<SKU>" --catalog "data/catalog/Product Catalog.csv" --dry-run --output-dir "reports/<run>" --exports-dir "exports/<run>"`
- **Evaluate an exports directory**:
  - `PYTHONPATH=./src .venv/bin/python -m feedops.cli.main evaluate-exports --exports-dir "exports/<run>" --output "reports/quality-eval-<run>.md"`

### Apify (optional) — recommended Actors + safe workflow
Goal: extract **generic keyword/intent phrases** (NOT competitor brands/spec claims) to inform titles/descriptions.

- **SERP**: `apify/google-search-scraper`
- **Shopping listings**: `damilo/google-shopping-apify`

Suggested workflow:
1. Run Actors for a category query (e.g., “18 inch wall mount towel bar solid brass”, “1 1/2 inch solid brass cabinet knob”).
2. Extract **generic phrases** (e.g., “towel rail”, “towel holder”, “wall mounted”, “concealed mounting”).
3. Save to local keyword bank file (gitignored): `data/keyword-bank.json`:
   - Format:
     - `{ "<Category>": { "external_keywords": ["phrase 1", "phrase 2", ...] } }`
4. Confirm the prompt treats `external_keywords` as **keyword phrases only** (never as product facts; never copy competitor brands).

### Constraints (non-negotiable)
- No invented specs, finishes, capacities, dimensions, materials.
- No source attribution in customer-facing fields (titles/descriptions).
- Avoid SKU codes in customer-facing text.
- Allied Brass is niche: **benefits/keywords first, brand last** in titles.

### What to do next (first session checklist)
- Pick 3–5 SKUs across categories (towel bar, knob, grab bar, mirror).
- Run `optimize` into a dedicated `exports/<run>` directory.
- Run `evaluate-exports` and record the markdown scores.
- Iterate prompt rules in `prompts.py` and re-run on the same SKUs.
- Keep changes small, measurable, and validated by the evaluator + spot-checking outputs.

