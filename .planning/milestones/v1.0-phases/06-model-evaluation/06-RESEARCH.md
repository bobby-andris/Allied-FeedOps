# Phase 6: Model Evaluation - Research

**Researched:** 2026-03-03
**Domain:** LLM evaluation methodology, Python evaluation scripting, Google Sheets API, provider cost calculation
**Confidence:** HIGH

<user_constraints>
## User Constraints (from CONTEXT.md)

### Locked Decisions
- **SKU selection approach**: Auto-suggest 15-20 candidates with diversity rationale, Bobby/Robert pick final 10. Diversity dimensions: category spread, single vs multi-SKU products, description complexity, collection variety. 3-4 of the 10 SKUs should have existing `approved_content` for reference comparison.
- **Models under evaluation**: 3-way comparison: Claude Sonnet 4.6, Claude Opus, GPT-5.2. All use identical prompts (no provider-specific optimization — locked in Phase 5). Claude models selected via `FEEDOPS_CLAUDE_MODEL` env var, GPT-5.2 via existing `FEEDOPS_OPENAI_MODEL`.
- **Scoring methodology**: Pass/fail + freeform notes per output. Bobby and Robert score independently. Blind evaluation via Google Sheet with hidden provider labels (Output A/B/C), labels revealed after all scoring complete. All 3 platforms evaluated: Google, Bing, Shopify — 90 total outputs to score (10 SKUs x 3 models x 3 platforms).
- **Generation passes**: 3 generation passes per SKU x model for median latency and variance measurement. Token-based cost calculation using `last_usage` from provider metrics + published pricing. Output consistency measured across the 3 passes per SKU x model. First pass output used for blind scoring; all 3 passes stored for consistency analysis.
- **Output artifacts**: All results in `docs/evaluation/` (permanent git record). Reusable parameterized evaluation script (takes model list, SKU list, output directory — runnable for future model comparisons). Final recommendation: single default provider winner + scenario-based exceptions.
- **Starting point**: Phase 4's `verify_content_quality.py` is the starting point — extend it for multi-model evaluation with metrics capture.

### Claude's Discretion
- Evaluation script architecture (single script vs modular)
- Consistency measurement approach (exact string similarity vs semantic)
- Google Sheet structure and formatting
- How to handle generation failures during evaluation runs
- Statistical presentation of latency data (tables vs charts)

### Deferred Ideas (OUT OF SCOPE)
- Claude-optimized prompt variant
- Extended thinking budget tuning
- Automated LLM-as-judge scoring
- Claude fallback chains
</user_constraints>

<phase_requirements>
## Phase Requirements

| ID | Description | Research Support |
|----|-------------|-----------------|
| EVAL-01 | Select 10 diverse SKUs (mix of categories, single vs multi-SKU products) | DB query pattern for diversity selection from `product_catalog` + `generated_content` tables |
| EVAL-02 | Generate content with both providers using identical prompts | Provider switching via `FEEDOPS_PROVIDER` + `FEEDOPS_CLAUDE_MODEL` env vars; `/optimize-sku` endpoint handles 3 platforms in one call |
| EVAL-03 | Blind human scoring by Bobby/Robert on title quality, description quality, brand voice, accuracy | Google Sheets API (gspread); blind sheet structure with Output A/B/C labels, provider mapping stored separately |
| EVAL-04 | Compare cost per SKU, latency, and consistency across runs | `last_usage` on all providers; `estimate_openai_cost_usd_from_usage()` for cost; `difflib.SequenceMatcher` for consistency |
| EVAL-05 | Clear data on which provider produces better content for which scenarios | Cross-tabulation of pass rates by provider x platform x category |
| EVAL-06 | Cost/quality tradeoff documented | Final recommendation doc with data table |
</phase_requirements>

---

## Summary

Phase 6 runs a 3-way blind evaluation (Claude Sonnet 4.6, Claude Opus, GPT-5.2) across 10 diverse SKUs and 3 platforms (Google, Bing, Shopify). The pipeline's provider abstraction layer (Phase 5) makes switching providers a single env-var change. The evaluation script extends `scripts/verify_content_quality.py` by adding multi-provider looping, metrics capture, 3-pass consistency measurement, and Google Sheets blind scoring sheet generation.

The critical design challenge is that `/optimize-sku` writes to the DB via `_persist_generated_content_and_history()` — the evaluation script must use `dry_run=True` to prevent 270 test-run rows from polluting the production `generated_content` table. All generation results should be captured in-memory/CSV by the script, not via DB writes.

The second critical challenge is that `OptimizeResponse` does not expose per-platform content, token counts, or latency in its HTTP response body — it only returns `success`, `master_sku`, `message`, and `report` (truncated previews). The evaluation script must either (a) call the provider directly (bypassing the HTTP endpoint) or (b) read from the DB after each non-dry-run call. The cleaner approach is to call providers directly using the same `generate_per_platform()` function the endpoint uses, running as a local Python script against the live Cloud Run API — or run as a local script that imports feedops directly with env vars set.

**Primary recommendation:** Write `scripts/run_model_evaluation.py` as a standalone Python script that imports feedops directly (not via HTTP), runs `generate_per_platform()` per SKU per model with 3 passes, captures all metrics in-memory, writes raw results to `docs/evaluation/raw_results.csv`, generates a scoring sheet via gspread, and writes the final comparison table to `docs/evaluation/comparison_table.md`.

## Standard Stack

### Core
| Library | Version | Purpose | Why Standard |
|---------|---------|---------|--------------|
| feedops (internal) | current | Provider selection, generation, metrics | Already wired; avoid HTTP overhead |
| gspread | 5.x | Google Sheets API Python client | Already in project deps (used by `fetch_sheets_data.js` pattern); simplest auth path |
| difflib (stdlib) | stdlib | Output consistency measurement | No dependency; `SequenceMatcher.ratio()` gives 0.0-1.0 similarity score |
| csv (stdlib) | stdlib | Raw results storage | Zero deps; human-readable; Excel-compatible |
| statistics (stdlib) | stdlib | p50/p95 latency calculation | `statistics.median()` and `statistics.quantiles()` |
| asyncio (stdlib) | stdlib | Running async generate calls | feedops providers are async |

### Supporting
| Library | Version | Purpose | When to Use |
|---------|---------|---------|-------------|
| google-auth | 2.x | Service account auth for gspread | When using service account credentials |
| tabulate | 0.9.x | Markdown/ASCII tables in output | Final recommendation doc formatting |

### Alternatives Considered
| Instead of | Could Use | Tradeoff |
|------------|-----------|----------|
| gspread | pygsheets | gspread simpler API, better maintained in 2026 |
| difflib | sentence-transformers | Semantic similarity is overkill for this eval; lexical diff is faster and interpretable |
| Direct feedops import | HTTP to /optimize-sku | HTTP path doesn't expose per-platform metrics in response body; direct import gives full access to `last_usage`, latencies, and content |

**Installation:**
```bash
uv pip install gspread google-auth tabulate
```

(These may already be present — check `pyproject.toml` before installing.)

## Architecture Patterns

### Recommended Project Structure
```
scripts/
└── run_model_evaluation.py    # Main eval script (parameterized)

docs/evaluation/
├── sku_selection.md           # 10 selected SKUs with rationale
├── raw_results.csv            # All 270 generations (10 SKUs x 3 models x 3 passes x 3 platforms)
├── scoring_sheet_url.txt      # Link to Google Sheet for blind scoring
├── consistency_analysis.md    # Output consistency across 3 passes per model
├── comparison_table.md        # Final cost/quality/latency comparison
└── recommendation.md          # Written recommendation
```

### Pattern 1: Provider Switching via Env Vars
**What:** Set env vars before instantiating provider factory; run generate_per_platform
**When to use:** Each evaluation pass — loop over model configs

```python
# Source: src/feedops/providers/factory.py
import os
import asyncio
from feedops.providers.factory import get_provider
from feedops.providers.base import close_provider
from feedops.pipeline.generator import generate_per_platform

MODEL_CONFIGS = [
    {"FEEDOPS_PROVIDER": "openai",  "FEEDOPS_OPENAI_MODEL": "gpt-5.2"},
    {"FEEDOPS_PROVIDER": "claude",  "FEEDOPS_CLAUDE_MODEL": "claude-sonnet-4-6"},
    {"FEEDOPS_PROVIDER": "claude",  "FEEDOPS_CLAUDE_MODEL": "claude-opus-4-6"},
]

async def run_for_model(parent_sku, env_config):
    for key, value in env_config.items():
        os.environ[key] = value
    provider = get_provider()
    try:
        result = await generate_per_platform(
            parent_sku=parent_sku,
            provider=provider,
            prompt_version="v2",
        )
        return result
    finally:
        await close_provider(provider)
```

### Pattern 2: Metrics Extraction from generate_per_platform Result
**What:** Extract all evaluation metrics from the dict returned by generate_per_platform
**When to use:** After each generation pass to build the CSV row

```python
# Source: src/feedops/api/generation_telemetry.py + routes.py
def extract_eval_metrics(generated: dict, platform: str) -> dict:
    usage_by_platform = generated.get("usage_by_platform", {})
    latency_by_platform = generated.get("latency_by_platform", {})

    usage = usage_by_platform.get(platform, {})
    latency_ms = latency_by_platform.get(platform, 0)

    prompt_tokens = usage.get("prompt_tokens", 0)
    completion_tokens = usage.get("completion_tokens", 0)
    cached_tokens = usage.get("cached_tokens", 0)

    # Cost calculation (matches generation_telemetry.py)
    # NOTE: estimate_openai_cost_usd_from_usage() uses GPT-5.2 pricing.
    # For Claude, use separate pricing (see below).
    return {
        "prompt_tokens": prompt_tokens,
        "completion_tokens": completion_tokens,
        "cached_tokens": cached_tokens,
        "latency_ms": latency_ms,
        "title": generated.get(f"{platform}_title", ""),
        "description": generated.get(f"{platform}_description", ""),
    }
```

### Pattern 3: Cost Calculation by Provider
**What:** Token-based cost calculation using published pricing
**When to use:** After capturing token counts per run

```python
# Source: src/feedops/api/generation_telemetry.py (GPT-5.2 rates)
# Prices verified 2026-03-03 from platform.claude.com/docs/en/about-claude/pricing
# and platform.openai.com/docs/pricing

PRICING = {
    "gpt-5.2": {
        "input_per_mtok": 1.75,
        "cached_per_mtok": 0.175,  # 90% discount on cached
        "output_per_mtok": 14.0,
    },
    "claude-sonnet-4-6": {
        "input_per_mtok": 3.0,
        "cached_per_mtok": 0.30,   # 0.1x base price for cache reads
        "output_per_mtok": 15.0,
    },
    "claude-opus-4-6": {
        "input_per_mtok": 5.0,
        "cached_per_mtok": 0.50,   # 0.1x base price for cache reads
        "output_per_mtok": 25.0,
    },
}

def calculate_cost_usd(model: str, prompt_tokens: int, completion_tokens: int,
                        cached_tokens: int = 0) -> float:
    rates = PRICING[model]
    uncached = max(prompt_tokens - cached_tokens, 0)
    input_cost = (uncached / 1_000_000) * rates["input_per_mtok"]
    cached_cost = (cached_tokens / 1_000_000) * rates["cached_per_mtok"]
    output_cost = (completion_tokens / 1_000_000) * rates["output_per_mtok"]
    return round(input_cost + cached_cost + output_cost, 6)
```

### Pattern 4: Consistency Measurement
**What:** Measure how similar repeated generations are (0.0 = completely different, 1.0 = identical)
**When to use:** Across the 3 passes per SKU x model; report mean similarity

```python
import difflib

def measure_consistency(outputs: list[str]) -> float:
    """Mean pairwise similarity across all pairs in outputs list."""
    if len(outputs) < 2:
        return 1.0
    pairs = [(outputs[i], outputs[j])
             for i in range(len(outputs))
             for j in range(i + 1, len(outputs))]
    scores = [difflib.SequenceMatcher(None, a, b).ratio() for a, b in pairs]
    return sum(scores) / len(scores)
```

### Pattern 5: SKU Selection Query
**What:** Query DB to surface diverse candidates with approved content flags
**When to use:** Wave 1 — generate the candidate list for Bobby/Robert to select from

```sql
-- Source: docs/database/SCHEMA.md
-- Candidates with approved content (priority for evaluation)
SELECT
    pc.master_sku,
    pc.category,
    pc.collection,
    pc.title,
    COUNT(DISTINCT gc.platform) AS approved_platform_count,
    EXISTS (
        SELECT 1 FROM product_catalog pc2
        WHERE pc2.master_sku != pc.master_sku
          AND pc2.product_id = pc.product_id
    ) AS is_multi_sku_product
FROM product_catalog pc
LEFT JOIN generated_content gc
    ON gc.master_sku = pc.master_sku
    AND gc.approved_content IS NOT NULL
WHERE pc.finish_code = 'ORB'  -- One representative variant per master_sku
GROUP BY pc.master_sku, pc.category, pc.collection, pc.title, pc.product_id
ORDER BY approved_platform_count DESC, pc.category, pc.master_sku
LIMIT 30;
```

### Pattern 6: Google Sheets Blind Scoring Sheet
**What:** Create spreadsheet with Output A/B/C columns (labels hidden), one tab per SKU+platform
**When to use:** Wave 2 output — generated once, shared with Bobby and Robert

```python
import gspread
from google.oauth2.service_account import Credentials

def create_blind_scoring_sheet(results: list[dict]) -> str:
    """Create Google Sheet for blind scoring. Returns sheet URL."""
    scopes = ["https://spreadsheets.google.com/feeds",
              "https://www.googleapis.com/auth/drive"]
    creds = Credentials.from_service_account_file("service_account.json",
                                                   scopes=scopes)
    gc = gspread.authorize(creds)
    sh = gc.create("FeedOps Model Evaluation - Blind Scoring")

    # One worksheet per platform (google, bing, shopify)
    # Columns: SKU | Output A | Output B | Output C |
    #          Bobby Pass/Fail | Bobby Notes | Robert Pass/Fail | Robert Notes
    # Provider mapping stored in a HIDDEN "key" worksheet, not shared until scoring complete

    return sh.url
```

### Anti-Patterns to Avoid
- **Calling /optimize-sku via HTTP for evaluation**: The HTTP response does not expose per-platform content, tokens, or latency — only a report string with truncated previews. Always import feedops directly.
- **Writing evaluation results to generated_content table**: 270 test rows would pollute the production DB. Use in-memory capture only; all results go to CSV files.
- **Running all 3 passes synchronously in a single asyncio event loop without delays**: Rate limit risk. Add a small sleep between model calls (1-2 seconds minimum).
- **Overwriting env vars without restoring them**: Set env vars at the start of each model run; restore originals (or use a context manager) so the script can be rerun cleanly.
- **Revealing provider labels before all scoring is complete**: Store provider mapping in a separate CSV, not in the scoring sheet. Share the key only after both Bobby and Robert mark all rows complete.

## Don't Hand-Roll

| Problem | Don't Build | Use Instead | Why |
|---------|-------------|-------------|-----|
| Google Sheets creation | Custom HTTP client | gspread | Handles OAuth, sheet creation, cell formatting |
| Token cost calculation | New cost estimator | Extend `estimate_openai_cost_usd_from_usage()` pattern | Already validated against live usage data |
| Latency stats | Manual percentile code | `statistics.quantiles(data, n=20)[18]` for p95 | stdlib, no deps |
| Provider metrics access | Parsing log output | `provider.last_usage`, `provider.last_parse_details` | Already exposed on all providers |
| Output similarity | Levenshtein distance library | `difflib.SequenceMatcher` | stdlib; sufficient precision for this use case |

**Key insight:** The feedops provider abstraction (Phase 5) was specifically built so evaluation doesn't need to rebuild anything — the hard part (structured output, token tracking, retry counts) is already done.

## Common Pitfalls

### Pitfall 1: OptimizeResponse Does Not Return Content
**What goes wrong:** Script calls `/optimize-sku` and tries to read title/description from response JSON — fields don't exist.
**Why it happens:** `OptimizeResponse` only has `success`, `master_sku`, `message`, `report`. The report is a truncated string of previews.
**How to avoid:** Import `generate_per_platform` and `load_parent_sku_from_supabase` directly. Run the evaluation script as a local Python script with feedops on `PYTHONPATH`, not as an HTTP client.
**Warning signs:** Script produces empty content columns in the CSV.

### Pitfall 2: estimate_openai_cost_usd_from_usage() Uses GPT-5.2 Rates Only
**What goes wrong:** Script uses the existing helper to calculate cost for Claude providers — returns wrong numbers.
**Why it happens:** `generation_telemetry.py:16-28` hardcodes GPT-5.2 rates ($1.75/$14.00 per MTok).
**How to avoid:** Write a separate `calculate_cost_usd(model, usage)` function in the evaluation script using the per-model rates table.
**Warning signs:** Claude Sonnet appears cheaper than GPT-5.2 by a factor of ~1.7x (actual prices show Claude Sonnet is more expensive per output token: $15 vs $14).

### Pitfall 3: Env Var Leakage Between Model Runs
**What goes wrong:** Second model run picks up env vars from first run (e.g., `FEEDOPS_CLAUDE_MODEL` set to Sonnet bleeds into Opus run).
**Why it happens:** `os.environ` is global state; `get_provider()` reads it at call time.
**How to avoid:** Save and restore env vars around each model run. Pattern: `old = {k: os.environ.get(k) for k in keys}`, set new values, run, then restore with `os.environ.update(old)` / `os.environ.pop()` for keys that were not originally set.
**Warning signs:** All 3 model runs produce identical token counts.

### Pitfall 4: generate_per_platform Supabase Writes
**What goes wrong:** Running 3 passes x 10 SKUs x 3 models = 90 calls to `generate_per_platform`, each writing to `generated_content` — 90 rows pollute the production table and may trigger downstream side effects.
**Why it happens:** `generate_per_platform` calls `_persist_generated_content_and_history` internally... actually CHECK: `generate_per_platform` is in `feedops.pipeline.generator`, not routes.py. The persistence happens in `routes.py::optimize_single_sku()`. If calling `generate_per_platform()` directly, no persistence occurs.
**How to avoid:** Call `generate_per_platform()` directly (bypasses routes and persistence). Only if calling via HTTP endpoint does DB write occur — but we already decided to avoid HTTP.
**Warning signs:** `generated_content` table grows by 90+ rows after eval run.

### Pitfall 5: 90 Blind Outputs Is a Lot to Score
**What goes wrong:** Bobby and Robert commit to scoring 90 outputs but fatigue sets in; incomplete scoring yields non-comparable results.
**Why it happens:** 3 platforms x 10 SKUs x 3 models = 90, but each "output" is a (title, description) pair, so really 180 text fields to evaluate.
**How to avoid:** Structure the sheet so each row = one SKU, with A/B/C title and description side-by-side. Scoring is one Pass/Fail decision per (output, rater) = 90 decisions per rater, not 180. Provide clear scoring rubric in sheet header (4 criteria: title quality, description quality, brand voice, accuracy).
**Warning signs:** Incomplete score cells; inter-rater agreement can't be computed.

### Pitfall 6: Consistency Run Ordering Affects Cache Hit Rates
**What goes wrong:** Run 1 has cold cache, runs 2-3 benefit from prompt caching — latency for runs 2-3 is artificially lower, making p50 look better than cold-start reality.
**Why it happens:** Claude uses `cache_control: ephemeral` (5-min TTL). GPT-5.2 uses `prompt_cache_retention: 24h`.
**How to avoid:** Document cache behavior in results. Report p50 as median across all 3 runs (includes warm cache benefit). Report run-1 latency separately as "cold start". This is actually useful data — shows real-world benefit of prompt caching.
**Warning signs:** Run 1 is 3-4x slower than runs 2-3 for Claude (cache miss vs hit).

## Code Examples

### CSV Row Structure for Raw Results
```python
# Source: derived from routes.py usage + generate_per_platform interface
CSV_FIELDS = [
    "sku",
    "model",           # "gpt-5.2", "claude-sonnet-4-6", "claude-opus-4-6"
    "pass_num",        # 1, 2, 3
    "platform",        # "google", "bing", "shopify"
    "title",
    "description",
    "prompt_tokens",
    "completion_tokens",
    "cached_tokens",
    "latency_ms",
    "cost_usd",
    "parse_mode",      # "strict_json", "markdown_fence", "substring_fallback"
    "json_retries",
    "api_retries",
    "has_approved_content",  # True/False (for reference comparison)
    "error",           # Empty string if success
]
```

### Script Entrypoint Signature
```python
# scripts/run_model_evaluation.py
def main():
    parser = argparse.ArgumentParser(description="FeedOps multi-model evaluation")
    parser.add_argument("--skus", nargs="+", required=True,
                        help="Master SKUs to evaluate (space-separated)")
    parser.add_argument("--models", nargs="+",
                        default=["gpt-5.2", "claude-sonnet-4-6", "claude-opus-4-6"],
                        help="Models to compare")
    parser.add_argument("--passes", type=int, default=3,
                        help="Generation passes per SKU x model (default: 3)")
    parser.add_argument("--output-dir", default="docs/evaluation",
                        help="Directory for all output files")
    parser.add_argument("--create-sheet", action="store_true",
                        help="Create Google Sheets blind scoring sheet")
    parser.add_argument("--service-account", default=None,
                        help="Path to Google service account JSON for Sheets")
```

### Latency Statistics
```python
import statistics

def latency_stats(latencies_ms: list[int]) -> dict:
    """Compute p50 and p95 latency from a list of measurements."""
    if not latencies_ms:
        return {"p50_ms": None, "p95_ms": None, "count": 0}
    sorted_lat = sorted(latencies_ms)
    p50 = statistics.median(sorted_lat)
    # p95 via quantiles (requires Python 3.8+)
    if len(sorted_lat) >= 2:
        p95 = statistics.quantiles(sorted_lat, n=20)[18]  # 19/20 = 95th percentile
    else:
        p95 = sorted_lat[-1]
    return {"p50_ms": int(p50), "p95_ms": int(p95), "count": len(latencies_ms)}
```

## State of the Art

| Old Approach | Current Approach | When Changed | Impact |
|--------------|------------------|--------------|--------|
| Manual curl testing | `verify_content_quality.py` stdlib script | Phase 4 (Plan 04-03) | Consistent baseline; eval script extends this |
| OpenAI only | Provider abstraction with Claude + OpenAI | Phase 5 | Makes Phase 6 evaluation trivial to implement |
| `json_object` response format | `json_schema` strict mode (GPT-5.2) + `output_config.format` (Claude) | Phase 4+5 | Fewer parse errors; more reliable structured output |
| Temperature sampling | `reasoning_effort` without temperature | Phase 4 (GPT-01 fix) | More deterministic output; affects consistency metric interpretation |

## Open Questions

1. **generate_per_platform persistence behavior**
   - What we know: Routes.py calls `_persist_generated_content_and_history()` after `generate_per_platform()`. The pipeline function itself is in `feedops/pipeline/generator.py`.
   - What's unclear: Does `generate_per_platform()` write to DB directly, or only when called from the route handler? Need to verify before running 90 passes.
   - Recommendation: Check `feedops/pipeline/generator.py` at plan time. If it writes to DB, add a `dry_run` flag or mock the persistence call.

2. **Google Sheets service account credentials**
   - What we know: GCP service accounts already exist (`profit-pilot-runtime`). No gspread usage in current codebase.
   - What's unclear: Which credentials file path to use; whether Sheets API is already enabled in GCP project.
   - Recommendation: Wave 1 task should verify GCP Sheets API is enabled and document the credential path. Fallback: create sheet manually and share link with Bobby/Robert; script writes HTML/CSV instead.

3. **Claude Opus model ID**
   - What we know: Factory defaults to `claude-sonnet-4-6`. Context.md specifies "Claude Opus" but the exact model ID for the claude-opus-4-6 series needs verification.
   - What's unclear: Is the current Anthropic SDK version in the project compatible with `claude-opus-4-6`?
   - Recommendation: Verify model ID by running a quick `health_check()` call in Wave 1 before committing to it in the evaluation.

4. **Approved content retrieval for reference comparison**
   - What we know: `generated_content.approved_content` is a TEXT column; query pattern is documented in SCHEMA.md (line 108-110).
   - What's unclear: Format of `approved_content` — is it the raw string or JSON? Is it platform-specific (one row per platform+content_type)?
   - Recommendation: Query `SELECT master_sku, platform, content_type, approved_content FROM generated_content WHERE master_sku = ? AND approved_content IS NOT NULL` in the SKU selection script to confirm format.

## Sources

### Primary (HIGH confidence)
- `src/feedops/providers/factory.py` — provider switching mechanism, env var names, model defaults
- `src/feedops/providers/claude_provider.py` — last_usage fields, cache_control behavior, metrics interface
- `src/feedops/api/generation_telemetry.py` — cost estimation pattern (GPT-5.2 rates), extract_platform_telemetry()
- `src/feedops/api/routes.py` — what generate_per_platform returns, content field key naming
- `scripts/verify_content_quality.py` — starting point script structure
- `src/feedops/api/schemas.py` — OptimizeResponse fields (confirms response does NOT expose content)

### Secondary (MEDIUM confidence)
- [Anthropic Claude Pricing](https://platform.claude.com/docs/en/about-claude/pricing) — Claude Sonnet 4.6 ($3/$15 per MTok), Claude Opus 4.6 ($5/$25 per MTok); verified 2026-03-03
- [OpenAI GPT-5.2 Pricing](https://platform.openai.com/docs/pricing) — $1.75 input / $14.00 output per MTok; $0.175 cached input; verified 2026-03-03

### Tertiary (LOW confidence)
- gspread 5.x API patterns — standard Python library, API is stable but Sheet creation auth flow should be verified against GCP project setup

## Metadata

**Confidence breakdown:**
- Standard stack: HIGH — all libraries are stdlib + well-established; pricing verified from official docs
- Architecture: HIGH — based on direct code inspection of factory.py, routes.py, generation_telemetry.py
- Pitfalls: HIGH — OptimizeResponse gap and env var leakage are verified from code inspection; cache pitfall derived from ClaudeProvider implementation

**Research date:** 2026-03-03
**Valid until:** 2026-04-03 (pricing may change; verify before finalizing cost calculations)
