# Content Generation Paths — Code Trace and Feature Flag Audit

**Generated:** 2026-02-21
**Phase:** 18-diagnosis-establish-ground-truth (Plan 01)
**Purpose:** Answer DIAG-02 (which code path runs?) and DIAG-03 (are feature flags wired?) with grep-verified evidence.

---

## Summary Table

| Question | Answer | Evidence |
|----------|--------|----------|
| Which code path runs for UI regen? | `main.py::regenerate_content()` via Cloud Run | `route.ts:211` — `fetch(\`${PIPELINE_URL}/regenerate\`, {method: 'POST', ...})` |
| Which core functions are bypassed? | `generator.py::build_prompt()`, `keyword_placement.py`, `verifier.py`, `selection.py` | Not imported anywhere in `main.py`; only `optimize.py` imports `generator.py` |
| Are Paths A and B divergent? | Minimal — same core functions (`_build_generation_user_prompt`, `_generate_with_metrics`, `_enforce_finish_sentence_parity`) | Side-by-side comparison below |
| Are feature flags wired into production paths? | Yes — all 3 flags are called in production code paths (evidence.py + prompt_loader.py) | Call site table below |
| Flag runtime state in Cloud Run? | None explicitly set — all 3 default to `True` (enabled) | `gcloud run services describe` output: no PROMPT_CONTRACT_V2, INTENT_CURATOR_V1, SEGMENT_STRATEGY_V1 env vars present |
| Is keyword_bank.json in Cloud Run container? | NO — data/ directory is excluded from Docker build context | `.gcloudignore:40` — `data/` is excluded; Dockerfile only copies `src/` and `pyproject.toml` |

---

## Path A: Single-SKU UI Regeneration

**Trigger:** User clicks "Regenerate" in dashboard UI for a single SKU.

```
User Browser
  │
  ├─► dashboard/src/app/api/regenerate/route.ts   [POST handler]
  │     Line 100: export async function POST(request: NextRequest)
  │     Line 137: resolveCanonicalMasterSku(supabase, master_sku)
  │     Line 140: ensureSkuData(canonicalMasterSku, supabase)   [non-blocking background]
  │     Line 211: fetch(`${PIPELINE_URL}/regenerate`, {method: 'POST', ...})
  │
  │   [HTTP POST to Cloud Run /regenerate]
  │
  └─► src/feedops/api/main.py
        Line 941: @app.post("/regenerate")
        Line 942: async def regenerate_content(request: RegenerateRequest)
        │
        ├─► Line 949: ensure_generation_enabled(operation="regenerate_content")
        ├─► Line 951: resolve_canonical_master_sku(supabase, request.master_sku)
        ├─► Line 972: load_parent_sku_from_supabase(canonical_master_sku)
        │
        ├─► src/feedops/pipeline/evidence.py
        │     Line 169: build_evidence_table(parent_sku)
        │       ├─► Line 371: is_intent_curator_v1_enabled()   [FLAG CHECKED]
        │       └─► Line 348: is_segment_strategy_v1_enabled() [FLAG CHECKED]
        │     Line 531: format_evidence_markdown(evidence)
        │
        ├─► src/feedops/api/prompt_loader.py
        │     Line 140: get_system_prompt()
        │       └─► Line 149: is_prompt_contract_v2_enabled()  [FLAG CHECKED]
        │     Line 173: get_system_prompt_hash()
        │
        ├─► Line 988: _build_generation_user_prompt(parent_sku, evidence_markdown, ...)
        │     (defined in main.py lines 434-500)
        │     ├─► prompt_loader.get_category_guidance()
        │     └─► prompt_loader.format_gold_standard_examples()
        │
        ├─► Line 1002: _generate_with_metrics(provider, prompt, schema, system_prompt, ...)
        │     (defined in main.py lines 396-431)
        │     └─► provider.generate(prompt, schema, system_prompt)
        │
        ├─► Line 1016: _enforce_finish_sentence_parity(...)   [Google/Bing descriptions only]
        │     (defined in main.py lines 662-752)
        │     ├─► finish_sentence_regeneration_enabled()
        │     ├─► strip_hardcoded_finish_names() / strip_generic_finish_count_claims()
        │     ├─► normalize_base_description_with_finish_placeholder()
        │     └─► _generate_with_metrics(...)   [second LLM call for finish sentences]
        │
        └─► Lines 1027-1079: Persistence (direct DB writes — NOT via _persist_generated_content_and_history)
              ├─► supabase.table("generated_content").upsert(...)
              ├─► _lookup_generated_content_id(...)
              └─► supabase.table("regeneration_history").insert(...)
```

**Bypassed in Path A:**
- `src/feedops/pipeline/generator.py::build_prompt()` — not imported from `main.py`
- `src/feedops/pipeline/keyword_placement.py` — not imported from `main.py`
- `src/feedops/pipeline/verifier.py` — not imported from `main.py`
- `src/feedops/pipeline/selection.py` — not imported from `main.py`
- `src/feedops/pipeline/optimize.py` — the only importer of `generator.py`
- Multi-candidate generation (only 1 candidate generated per call)

**route.ts responsibilities (dashboard-side):**
- Input validation (fields, feedback mode requirements)
- Schema sanity check (`generated_content` table)
- `ensureSkuData()` background data collection (non-blocking)
- Content validation via `validateGeneratedContent()` — violations logged but not blocking
- Finish sentence normalization from pipeline response
- DB persistence: `generated_content` update/insert with versioning
- `variant_finish_sentences` upsert (Python pipeline also does this — dual write)

---

## Path B: Batch Generation

**Two batch endpoints exist:**

### Path B1: Standard Batch (`/batch-optimize`)
**Trigger:** Batch generation UI or API call for multiple SKUs.

```
HTTP POST /batch-optimize
  │
  └─► src/feedops/api/main.py
        Line 1159: async def batch_optimize(request: BatchOptimizeRequest)
        │
        ├─► Creates batch_generation_jobs record in Supabase (status: "queued")
        ├─► Creates batch_generation_job_skus records
        └─► run_async_in_thread(process_batch_job, ...)   [non-blocking thread]
              │
              └─► async def process_batch_job(job_id, skus, ...)  [lines 1418-1574]
                    │
                    ├── For each SKU:
                    │   ├─► load_parent_sku_from_supabase(canonical_sku)
                    │   ├─► build_evidence_table(parent_sku)            [same as Path A]
                    │   │     ├─► is_intent_curator_v1_enabled()        [FLAG CHECKED]
                    │   │     └─► is_segment_strategy_v1_enabled()      [FLAG CHECKED]
                    │   ├─► format_evidence_markdown(evidence)
                    │   ├─► get_system_prompt()                         [FLAG CHECKED]
                    │   │     └─► is_prompt_contract_v2_enabled()
                    │   ├─► _build_generation_user_prompt(...)           [SAME as Path A]
                    │   ├─► _generate_with_metrics(...)                  [SAME as Path A]
                    │   ├─► _enforce_finish_sentence_parity(...)        [SAME as Path A]
                    │   └─► _persist_generated_content_and_history(...) [different helper]
                    │
                    └── Update batch_generation_jobs status to completed/failed
```

### Path B2: Hybrid Batch (`/hybrid-generate`)
**Trigger:** Hybrid generation for multi-SKU product families.

```
HTTP POST /hybrid-generate
  │
  └─► src/feedops/api/main.py
        Line 1294: async def hybrid_generate(request: HybridGenerateRequest)
        │
        ├─► detect_multi_sku_families(supabase, canonical_skus)
        └─► run_async_in_thread(process_hybrid_batch_job, ...)
              │
              └─► async def process_hybrid_batch_job(...)  [lines 1577-1881]
                    │
                    ├── Single SKUs → generate_full_content(sku, platform, content_type)
                    │   [internal helper, lines 1695-1760]
                    │   ├─► load_parent_sku_from_supabase()
                    │   ├─► build_evidence_table()                     [same as Path A]
                    │   ├─► _build_generation_user_prompt()            [same as Path A]
                    │   ├─► _generate_with_metrics()                   [same as Path A]
                    │   ├─► _enforce_finish_sentence_parity()          [same as Path A]
                    │   └─► _persist_generated_content_and_history()
                    │
                    └── Variant SKUs → adapt_variant_content()
                        [src/feedops/api/hybrid_generation.py]
                        [Different code path — uses base SKU content as template]
```

---

## Path A vs Path B: Key Divergences

| Aspect | Path A (UI Regen) | Path B (Batch) |
|--------|-------------------|----------------|
| Entry point | `route.ts` → Cloud Run | Direct to Cloud Run |
| Thread model | Synchronous (awaits response) | `run_async_in_thread()` — non-blocking |
| Background task survival | N/A (direct call) | Non-daemon thread survives HTTP response |
| Persistence helper | Inline code in `regenerate_content()` | `_persist_generated_content_and_history()` helper |
| History mode field | `"with_feedback"` or `"simple"` | `"full_generation"` |
| Route.ts validation | Yes (field validation, schema check) | None — batch bypasses route.ts entirely |
| Data collection | `ensureSkuData()` triggers before generation | Not triggered |
| Content versioning | route.ts handles `version` increment | `_persist_generated_content_and_history()` uses upsert (no version tracking) |
| Core generation | `_build_generation_user_prompt` + `_generate_with_metrics` | **Identical** |
| Feature flag calls | Via `build_evidence_table()` + `get_system_prompt()` | **Identical** |
| Finish sentences | Via `_enforce_finish_sentence_parity()` | **Identical** |

**Verdict:** Core generation logic (evidence building, prompt construction, LLM call, finish sentence generation) is identical across all paths. Divergences are in threading, persistence helpers, and route-level validation only.

---

## Feature Flag Audit

### Flag Definitions

**File:** `src/feedops/pipeline/feature_flags.py` (25 lines total)

```python
def is_prompt_contract_v2_enabled() -> bool:
    return _is_enabled("PROMPT_CONTRACT_V2", True)   # default: True (enabled)

def is_intent_curator_v1_enabled() -> bool:
    return _is_enabled("INTENT_CURATOR_V1", True)    # default: True (enabled)

def is_segment_strategy_v1_enabled() -> bool:
    return _is_enabled("SEGMENT_STRATEGY_V1", True)  # default: True (enabled)
```

All flags use `_is_enabled(name, default=True)` which reads `os.getenv(name)` and returns the default if the env var is absent.

### Call Site Table

| Flag | File | Line | Function Context | In Production Path? |
|------|------|------|-----------------|---------------------|
| `is_prompt_contract_v2_enabled` | `src/feedops/api/prompt_loader.py` | 149 | `get_system_prompt()` — controls whether Python `CANONICAL_SYSTEM_PROMPT` or Supabase DB prompt is used | **YES** — called by `regenerate_content()`, `process_batch_job()`, `process_hybrid_batch_job()` |
| `is_intent_curator_v1_enabled` | `src/feedops/pipeline/evidence.py` | 371 | `build_evidence_table()` — controls which search query curation algorithm runs (`curate_search_queries_by_relevance` vs `filter_search_queries_by_relevance`) | **YES** — called by `build_evidence_table()` which is in ALL generation paths |
| `is_segment_strategy_v1_enabled` | `src/feedops/pipeline/evidence.py` | 348 | `build_evidence_table()` — controls whether `segment_strategy.fallback_queries` are injected when search query count is low | **YES** — called by `build_evidence_table()` which is in ALL generation paths |
| `is_segment_strategy_v1_enabled` | `src/feedops/pipeline/generator.py` | 100 | `_resolve_segment_strategy()` inside `generator.py` — used in legacy 6-agent pipeline | **ONLY IN LEGACY PATH** — `generator.py` is only imported by `optimize.py`, not by `main.py` |

### Flag Behavior (default: all True)

**PROMPT_CONTRACT_V2 = True (default):**
- `get_system_prompt()` returns `CANONICAL_SYSTEM_PROMPT` (Python code-owned)
- Supabase `prompt_templates.system_prompt` is NOT used as the runtime prompt
- Supabase data is still used for `gold_standard_examples` and `category_guidance`

**INTENT_CURATOR_V1 = True (default):**
- `build_evidence_table()` calls `curate_search_queries_by_relevance()` (smarter curation)
- Returns `(search_queries, diagnostics)` tuple with min/max limits (min_keep=3, max_keep=12)
- If False: falls back to `filter_search_queries_by_relevance()` (simpler filter, no diagnostics tuple)

**SEGMENT_STRATEGY_V1 = True (default):**
- `resolve_segment_strategy()` is called with `enabled=True`
- When search queries < 3, `segment_strategy.fallback_queries` are injected as padding
- In `generator.py` (legacy path): same behavior but in a different code context

---

## Cloud Run Runtime State

**Command used:**
```
gcloud run services describe feedops-pipeline --project=bobbys-project-346400 --region=us-east1 --format='json'
```

**Env vars present (non-secret values):**
```
GOOGLE_ADS_CUSTOMER_ID=6253381786
GOOGLE_ADS_API_ENABLED=1
OPENAI_API_KEY=<from secret>
SUPABASE_URL=<from secret>
SUPABASE_KEY=<from secret>
GOOGLE_ADS_DEVELOPER_TOKEN=<from secret>
GOOGLE_ADS_CLIENT_ID=<from secret>
GOOGLE_ADS_CLIENT_SECRET=<from secret>
GOOGLE_ADS_REFRESH_TOKEN=<from secret>
GOOGLE_ADS_LOGIN_CUSTOMER_ID=<from secret>
GEMINI_API_KEY=<from secret>
SLACK_WEBHOOK_URL=<from secret>
```

**Feature flag env vars: NONE SET**

| Flag Env Var | Present in Cloud Run? | Runtime Behavior |
|---|---|---|
| `PROMPT_CONTRACT_V2` | No | Falls back to `default=True` → Python `CANONICAL_SYSTEM_PROMPT` is active |
| `INTENT_CURATOR_V1` | No | Falls back to `default=True` → `curate_search_queries_by_relevance()` is active |
| `SEGMENT_STRATEGY_V1` | No | Falls back to `default=True` → segment fallback injection is active |

**Conclusion:** All three feature flags are active (enabled) in production Cloud Run. No env vars are needed to enable them; they are on by default and cannot be toggled without a new Cloud Run deployment.

---

## keyword_bank.json in Cloud Run

**Question:** Is `data/keyword-bank.json` available inside the Cloud Run container?

**Answer: NO.**

Evidence:
1. `.gcloudignore` line 40: `data/` — entire data directory excluded from Cloud Build context
2. `Dockerfile` copies only `src/` and `pyproject.toml` — no `COPY data/ ./data/`
3. `src/feedops/integrations/keyword_bank.py` line 26-27: `if not path.exists(): return {}`

**Runtime behavior:** `get_external_keywords()` always returns `[]` in Cloud Run. The `keyword_bank` evidence row is never added to the evidence table in production. External keyword research data from Apify/SEO is not reaching the prompt.

**Workaround:** Set `FEEDOPS_KEYWORD_BANK_PATH` env var pointing to a mounted volume or GCS path, or migrate keyword bank data into Supabase.

---

## Legacy Path (Not Used by UI or Batch)

**`src/feedops/pipeline/optimize.py`** is the only importer of `generator.py`:
```
grep result: /src/feedops/pipeline/optimize.py:17:
  from feedops.pipeline.generator import build_prompt, generate_candidates
```

`optimize.py` is used by the original 6-agent experimental pipeline (manual execution only, not wired to any HTTP endpoint in `main.py`). It is not part of any production HTTP path.

**Functions exclusive to the legacy path (not reachable from main.py):**
- `generator.py::build_prompt()` — builds legacy single-string prompt
- `generator.py::build_split_prompt()` — cache-optimized split prompt
- `generator.py::generate_candidate()` — single candidate generation
- `generator.py::generate_candidates()` — multi-candidate generation
- `keyword_placement.py::build_keyword_placement_plan()` — keyword insertion planning
- `verifier.py` — claim verification against evidence
- `selection.py` — candidate scoring and selection

---

## File Reference Index

| File | Role | Key Functions |
|------|------|---------------|
| `dashboard/src/app/api/regenerate/route.ts` | Path A entry point (TypeScript) | `POST()` — validates, proxies to Cloud Run, persists |
| `src/feedops/api/main.py` | Cloud Run FastAPI app | `regenerate_content()`, `batch_optimize()`, `hybrid_generate()`, `process_batch_job()`, `process_hybrid_batch_job()`, `_build_generation_user_prompt()`, `_generate_with_metrics()`, `_enforce_finish_sentence_parity()`, `_persist_generated_content_and_history()` |
| `src/feedops/pipeline/feature_flags.py` | Flag definitions | `is_prompt_contract_v2_enabled()`, `is_intent_curator_v1_enabled()`, `is_segment_strategy_v1_enabled()` |
| `src/feedops/api/prompt_loader.py` | System prompt + Supabase template loader | `get_system_prompt()`, `get_system_prompt_hash()`, `get_category_guidance()`, `format_gold_standard_examples()` |
| `src/feedops/pipeline/evidence.py` | Evidence table builder | `build_evidence_table()`, `format_evidence_markdown()` |
| `src/feedops/pipeline/generator.py` | Legacy 6-agent pipeline only | `build_prompt()`, `generate_candidates()` |
| `src/feedops/pipeline/optimize.py` | Legacy 6-agent pipeline only | Imports from `generator.py` |
| `src/feedops/integrations/keyword_bank.py` | External keyword loader | `get_external_keywords()` — returns `[]` in Cloud Run |
| `src/feedops/api/hybrid_generation.py` | Variant adaptation | `adapt_variant_content()` — Path B2 variant SKUs only |
