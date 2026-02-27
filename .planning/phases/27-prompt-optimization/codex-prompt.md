# Codex 5.3 Task: Complete Phase 27 — Prompt Optimization

## Context

Allied-FeedOps is a product content generation pipeline that uses GPT-5.2 with strict JSON schema mode to generate Google Shopping, Bing Shopping, and Shopify product descriptions for Allied Brass bathroom hardware.

The v2 generation path:
1. `src/feedops/pipeline/generator.py` → `generate_per_platform()` makes 4 sequential GPT-5.2 calls (google, bing, shopify, finish_sentences)
2. Each call uses a per-platform system prompt built by `src/feedops/pipeline/skill_loader.py` → `get_platform_system_prompt(platform)` which concatenates `SYSTEM_PROMPT + platform_BRIEF` from `src/feedops/pipeline/prompts.py`
3. Provider at `src/feedops/providers/openai_provider.py` uses `_build_strict_schema()` for OpenAI strict JSON mode and `_parse_json_payload()` to parse responses
4. Results extracted in `generator.py` line 479+ with `.get()` calls

## The Problem

Three attempts to modify `src/feedops/pipeline/prompts.py` caused GPT-5.2 to return empty/placeholder-only content:
- Google/Bing descriptions: just `{FINISH_SENTENCE}` (the literal placeholder, not a full description)
- Shopify descriptions: empty string `""`
- All titles: empty

The file was reverted to its pre-change state and generation works again. The goal is to successfully make these changes.

## Root Cause Analysis (from code review)

Three potential root causes have been identified:

### 1. OpenAI Prompt Cache Invalidation + Token Budget Exhaustion
When `SYSTEM_PROMPT` text changes, OpenAI's prefix cache breaks. GPT-5.2 then spends more reasoning tokens re-processing the new prompt. With `max_completion_tokens=8000` (default) and `reasoning_effort="high"`, the model may exhaust its token budget on reasoning before emitting full JSON content. The retry logic in `openai_provider.py` lines 353-377 only doubles the budget once (8K→16K), which may still be insufficient.

Evidence: 1167 completion tokens generated but `shopify_description` was empty — those tokens were likely consumed by reasoning + claims array + structural JSON, with nothing left for the description string.

### 2. Partial JSON Fallback Silently Returns Empty Fields
In `openai_provider.py` lines 66-70, when JSON parsing fails on the full response, a fallback extracts text between the first `{` and last `}`. If GPT-5.2's response was truncated by the token limit, this parses a partial JSON object missing content fields. The `generator.py` extraction at line 484 (`google_payload.get("google_description", "")`) then returns `""` silently instead of raising an error.

### 3. Wasted 260K Skill Injection on Every v2 Request
At `src/feedops/api/main.py` line 1120, `get_system_prompt()` is called BEFORE the v2 branch check. This assembles the legacy prompt with all 8 skill files (~260K chars) that is NEVER used for v2 LLM calls. This is pure waste. Remove or guard with `if prompt_version != "v2":`.

## Changes to Make

### Phase 27 Goals (in priority order)

#### 1. Fix the machinery FIRST (make prompt changes safe)

**A. Increase default completion token budget for per-platform calls**
File: `src/feedops/pipeline/generator.py`, function `_platform_completion_cap()`
- Increase the default from 8000 to at least 16000 for content platforms (google, bing, shopify)
- Finish sentences can stay at 8000 (they're shorter)

**B. Add logging to detect truncated responses**
File: `src/feedops/pipeline/generator.py`, in the per-platform loop (line 444-469)
- After each `provider.generate()` call, log the keys present in the returned dict
- If any expected content key (google_description, bing_description, shopify_description) has a value shorter than 100 chars, log a WARNING with the full response keys and value lengths

**C. Make partial JSON parsing explicit, not silent**
File: `src/feedops/providers/openai_provider.py`, in `_parse_json_payload()` (line 66-70)
- When the first-`{`-to-last-`}` fallback is used, log a WARNING that indicates partial JSON was recovered
- Include the number of keys in the parsed result vs what was expected

**D. Remove the wasted `get_system_prompt()` call for v2**
File: `src/feedops/api/main.py`, around line 1120
- Guard the `system_prompt = get_system_prompt()` call: only execute it if `prompt_version != "v2"`
- For v2, initialize `system_prompt = ""` and let the v2 path populate it from `generated["system_prompts"]`

#### 2. THEN make the prompt content changes (one at a time, test between each)

**A. Remove self_score from output schemas**
File: `src/feedops/pipeline/prompts.py`
- Remove `self_score` and `_SELF_SCORE_SCHEMA` from `GOOGLE_SCHEMA`, `BING_SCHEMA`, `SHOPIFY_SCHEMA`
- Remove from each schema's `"required"` array
- Remove `<scoring_rubric>` section from `SYSTEM_PROMPT`
- Remove `self_score` from output_contract lines in GOOGLE_BRIEF, BING_BRIEF, SHOPIFY_BRIEF
- Keep `claims` — useful for traceability

**B. Clean up SYSTEM_PROMPT (minimal changes)**
File: `src/feedops/pipeline/prompts.py`
- Remove the line "The skills injected below contain rich guidance..." (v2 doesn't inject skills)
- Remove "For detailed brand voice guidance including anti-patterns and tone calibration, follow the allied-brass-brand-expert skill injected below."
- Add to `<creative_direction>`: "Find the ONE design detail that makes THIS product worth noticing and lead with it — what would a bathroom designer point out that a shopper wouldn't?"
- Compress `<accuracy_guardrail>`: remove the "Evidence rules:" sub-section (redundant with existing prohibitions), keep all "Content prohibitions" bullets

**C. Fix evidence exclusion for v2 path**
File: `src/feedops/pipeline/evidence.py`
- The 11 new fields in `_COPY_CONTEXT_EXCLUDED_FIELDS` only affect v1 (`for_customer_copy=True`). The v2 path in `generator.py` calls `build_evidence_table()` directly without the filter. Verify this is intentional — if the excluded fields (weight_capacity, product_height, etc.) should also be excluded from v2, add filtering in `generator.py` line 383.

## Testing Protocol

After EACH change above, deploy and test:
```bash
curl -s -X POST https://feedops-pipeline-623866089882.us-east1.run.app/regenerate \
  -H "Content-Type: application/json" \
  -d '{"master_sku": "1016", "platform": "google", "content_type": "description"}' | python3 -c "
import sys, json
data = json.load(sys.stdin)
c = data.get('content', '')
print('LEN:', len(c), '— PASS' if len(c) > 200 else '— FAIL')
print(c[:300])
"
```

**PASS criteria**: Content length > 200 chars, contains actual product description text (not just `{FINISH_SENTENCE}`).

Test at least 3 SKUs: `1016` (towel ring, Google), `CL-22` (retractable hook, Bing), `DMF-2/2X` (mirror, Shopify).

## Key Files

- `src/feedops/pipeline/prompts.py` — SYSTEM_PROMPT, platform briefs, JSON schemas
- `src/feedops/pipeline/generator.py` — `generate_per_platform()`, token budgets
- `src/feedops/providers/openai_provider.py` — strict schema builder, JSON parser, retry logic
- `src/feedops/api/main.py` — regenerate endpoint, wasted `get_system_prompt()` call
- `src/feedops/pipeline/skill_loader.py` — `get_platform_system_prompt()`
- `src/feedops/api/prompt_loader.py` — `get_system_prompt()` (v1 path)
- `src/feedops/pipeline/evidence.py` — evidence exclusion fields

## What's Already Done (keep these)

- `evidence.py`: 11 fields added to `_COPY_CONTEXT_EXCLUDED_FIELDS` (v1 copy context)
- `main.py`: DB truncation limit changed from `[:5000]` to `[:50000]` (2 locations in regeneration_history inserts)
- `prompt_builder.py`: `weight_capacity` removed from v1 `build_core_prompt` field list

## Constraints

- Python pipeline only (no TypeScript changes needed)
- Cloud Run auto-deploys on push to master
- GPT-5.2 model with strict JSON schema mode via OpenAI API
- Production is on `FEEDOPS_PROMPT_VERSION=v2` (per-platform generation)
- Do NOT modify GOOGLE_BRIEF, BING_BRIEF, SHOPIFY_BRIEF, FINISH_BRIEF content (those work well)
- Do NOT change the evidence table format or keyword placement format
