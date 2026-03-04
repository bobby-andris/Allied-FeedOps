# Phase 4: GPT-5.2 Bug Fixes - Context

**Gathered:** 2026-03-03
**Status:** Ready for planning

<domain>
## Phase Boundary

Fix all 5 known GPT-5.2 bugs with regression tests and automated curl verification. Most bugs are already fixed in code from prior work — Phase 4 locks them down with tests, adds `prompt_cache_key` for better cache efficiency, and creates a reusable verification script. Each fix is a separate PR with curl verification against live endpoint.

</domain>

<decisions>
## Implementation Decisions

### Bug status and approach
- GPT-01 (temperature/reasoning conflict): Already fixed at `openai_provider.py:370-374` — write regression test only
- GPT-02 (reasoning_effort default): Keep `"high"` as default (not `"medium"` per original spec). The 98% approval rate was achieved with `"high"`. Update the requirement spec to match
- GPT-03 (json_schema strict mode): Already fixed via `_build_strict_schema()` — write regression test only
- GPT-04 (prompt_cache_retention): Already fixed with `extra_body={"prompt_cache_retention": "24h"}` on both API call paths — write regression test only
- GPT-05 (XML tags in system prompt): Already fixed — SYSTEM_PROMPT uses XML tags (`<creative_direction>`, `<brand_voice>`, etc.), no `===` headers remain. Write regression test only

### Additional improvement: prompt_cache_key
- Add `prompt_cache_key` parameter to API calls (OpenAI docs: "Use prompt_cache_key instead [of user field] to maintain caching optimizations")
- Groups batch requests under same cache key since they share the system prompt prefix
- One-line addition per API call path — low risk, direct extension of GPT-04 caching fix

### Test approach
- Dedicated `tests/test_gpt52_regression.py` file — all 5 bug checks in one place
- GPT-01 test: Assert temperature is never passed alongside reasoning_effort
- GPT-02 test: Assert default reasoning_effort is `"high"` when env var is unset
- GPT-03 test: Assert response_format uses `json_schema` type with `strict: True`, not `json_object`
- GPT-04 test: Assert `prompt_cache_retention: "24h"` is in extra_body for both regular and image API calls
- GPT-05 test: Assert SYSTEM_PROMPT contains XML tags and no `===` section headers

### Automated verification script
- Python script that curls `/optimize-sku` and checks output
- Three verification SKUs:
  - `920D-6` — the canonical test SKU (single SKU, known good baseline)
  - A random SKU — selected at runtime from the database to catch edge cases
  - `AP-41/18` — hybrid/multi-SKU product to verify family generation path
- Checks: description length > 500 chars for each platform (Google, Bing, Shopify)
- Reusable for future prompt changes (Phase 7 Bing fix, Phase 5 Claude provider)

### PR strategy (GPT-06)
- One PR for the regression test file (covers GPT-01 through GPT-05)
- One PR for `prompt_cache_key` addition (the only actual code change)
- One PR for the verification script
- Curl verification after each PR merge against live endpoint

### Claude's Discretion
- Exact test assertions and mock setup within the regression file
- Verification script output format and error reporting
- Whether `prompt_cache_key` value is a static string or derived from batch_id/job context
- Random SKU selection strategy in verification script (query criteria)

</decisions>

<specifics>
## Specific Ideas

- Verification script should be reusable — it'll be needed again for Phase 5 (Claude provider) and Phase 7 (Bing fix)
- The script should print clear pass/fail per SKU per platform, not just a single boolean
- Consider making the script runnable both against localhost and production URL via env var

</specifics>

<code_context>
## Existing Code Insights

### Reusable Assets
- `openai_provider.py`: All GPT-5.2 interaction logic — the target for regression tests. Already has `_build_strict_schema()`, mutual exclusivity logic, `prompt_cache_retention`
- `prompts.py`: SYSTEM_PROMPT with XML tags — target for GPT-05 regression test
- `src/feedops/providers/base.py`: `LLMProvider` ABC — tests can mock at this interface
- `tests/api/test_openai_provider_smoke.py`: Existing smoke tests — new regression file follows same patterns

### Established Patterns
- Provider tests mock `AsyncOpenAI` client and verify call arguments
- `_build_strict_schema()` is a pure function — easily unit testable
- `extra_body` is passed as kwargs to `client.chat.completions.create()` — inspectable in mock

### Integration Points
- `openai_provider.py:366-374`: Where temperature/reasoning_effort mutual exclusivity is enforced
- `openai_provider.py:333-337`: Where reasoning_effort default is set (currently `"high"`)
- `openai_provider.py:341`: Where `_build_strict_schema(schema)` is called
- `openai_provider.py:407,419`: Where `extra_body={"prompt_cache_retention": "24h"}` is passed (both regular and image paths)
- `prompts.py:271-332`: SYSTEM_PROMPT with XML structure

</code_context>

<deferred>
## Deferred Ideas

- `output_verbosity` parameter (new OpenAI API feature) — controls response verbosity. Could help with description length targets but needs careful testing given GPT-5.2 sensitivity. Better evaluated in Phase 6 (Model Evaluation) with controlled comparisons.
- `prompt_cache_key` granularity optimization — using batch_id or job context as cache key for even better bucketing. Evaluate after seeing cache hit rate data from the basic implementation.

</deferred>

---

*Phase: 04-gpt52-bug-fixes*
*Context gathered: 2026-03-03*
