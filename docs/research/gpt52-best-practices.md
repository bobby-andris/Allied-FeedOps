# GPT-5.2 Best Practices for FeedOps Content Generation

Research date: 2026-02-21
Sources: OpenAI Developer Docs (prompting guide, latest model guide, prompt engineering, prompt caching, structured outputs)

---

## 1. GPT-5.2 Specific Behaviors & Tips

### Default reasoning_effort is `none`
GPT-5.2's default reasoning effort is `none` (unlike GPT-5 which defaults to `medium`). This means **out of the box, GPT-5.2 behaves more like a fast completion model than a reasoning model**. For content generation where quality matters, we should explicitly set reasoning_effort.

**Migration mapping from docs:**
- GPT-4o -> GPT-5.2 with `reasoning_effort: none` (speed parity)
- GPT-5 -> keep same effort except `minimal -> none`
- o3 -> GPT-5.2 with `reasoning_effort: medium`, then tune up if needed

### "Conservative grounding bias"
GPT-5.2 has a "conservative grounding bias" -- it favors correctness over speculation. This is actually good for our use case (factual product content from evidence tables). The model is less likely to hallucinate claims, aligning with our P0_GLOBAL_FACTUAL_RULES.

### "Stronger instruction adherence" with "less drift from user intent"
GPT-5.2 follows instructions more precisely than predecessors. This means our detailed priority system (P0 > P1 > P2) should work better, but also means imprecise instructions will be followed more literally.

### Lower default verbosity
GPT-5.2 generates "generally lower verbosity" output. For product descriptions where we target specific character ranges (600-800 chars for Google, 700-1000 for Bing), we may need to be more explicit about length targets or the model will under-generate.

### "More deliberate scaffolding"
The model naturally produces more structured, scaffolded output. This is beneficial for our multi-field JSON output where each field has different requirements.

### temperature + top_p only work with reasoning_effort: none
**CRITICAL**: The docs state that `temperature`, `top_p`, and `logprobs` are "only supported when reasoning effort is set to `none`." If we set reasoning_effort to anything else (low/medium/high), passing `temperature=0.7` will cause an API error. We must use `reasoning.effort`, `text.verbosity`, and `max_output_tokens` instead.

**Impact on our code**: `openai_provider.py` currently always passes `temperature=0.7` AND may also pass `reasoning_effort`. These are mutually exclusive parameters on GPT-5.2.

---

## 2. Prompt Structure Optimization

### Instruction Priority / Authority Hierarchy
OpenAI's docs define a "chain of command": developer messages take precedence over user messages. Think of developer (system) messages as "function definitions" and user messages as "arguments to a function."

**Our current approach is correct**: We use a system message for static rules and a user message for per-SKU evidence. This aligns with the recommended pattern.

### Recommended message structure order
The docs recommend structuring developer messages in this order:
1. **Identity**: Purpose, communication style, goals
2. **Instructions**: Rules, dos and don'ts
3. **Examples**: Input-output pairs demonstrating desired behavior
4. **Context**: Supporting data, proprietary information

**Gap in our implementation**: Our SYSTEM_PROMPT follows this order (identity -> rules -> style guidance) but we put gold_standard_examples in the USER message (via prompt_loader). The docs suggest examples should be in the developer/system message for better adherence AND better caching.

### Use XML tags to delineate content boundaries
The GPT-5.2 guide emphasizes using structured sections like `<output_verbosity_spec>`, `<design_and_scope_constraints>`, and `<uncertainty_and_ambiguity>` to scaffold behavior. Our SYSTEM_PROMPT uses `=== P0_GLOBAL_FACTUAL_RULES ===` style headers. While functional, XML tags may improve parsing fidelity with GPT-5.2's instruction following.

### Explicit scope discipline
The guide recommends adding: "Implement EXACTLY and ONLY what the user requests. No extra features, no added components, no UX embellishments." For content generation, this translates to: generate EXACTLY the requested fields, no additional commentary, no extra fields in JSON.

### Verbosity control -- use concrete length clamping
Instead of vague targets like "target 600-800 characters", the GPT-5.2 guide recommends concrete constraints:
- Simple outputs: "<=2 sentences"
- Complex outputs: "1 short overview paragraph + <=5 tagged bullets"

For our use case: specify character counts as hard constraints, not "targets."

### Ambiguity handling
For ambiguous evidence, the guide recommends presenting "2-3 plausible interpretations with clearly labeled assumptions" rather than defaulting. Our current approach ("use conservative language") is simpler and probably better for production content, but we could add a `confidence` field to claims.

---

## 3. Prompt Caching Strategy

### How it works
Prompt caching automatically routes requests to servers that recently processed identical prompt prefixes. Benefits: up to 80% latency reduction and up to 90% input cost reduction.

### Minimum requirement: 1024 tokens
Prompts must contain **1024 tokens or longer** to enable caching. Our SYSTEM_PROMPT is well over this threshold (it's several hundred lines), so this is met.

### Critical rule: "Static content first, dynamic content last"
The docs are explicit: "Place static content like instructions and examples at the beginning of your prompt, and put variable content, such as user-specific information, at the end."

**What gets cached (in order of message array)**:
- System prompts and instructions
- Common examples
- Tool definitions
- Structured output schemas

**Our current architecture is correct**: System prompt (static) as first message, user prompt with evidence (dynamic) as second message. This maximizes cache prefix matching.

### Move gold standard examples INTO the system prompt
Currently, gold standard examples are loaded from the database and inserted into the user prompt via `format_gold_standard_examples()`. Since these examples change infrequently (maybe weekly), they should be part of the static system prompt to extend the cacheable prefix. Any per-SKU evidence should come AFTER examples.

### Category guidance should also be static-ish
If category guidance changes rarely, prepend it to the system prompt or add it as a second system message before the user message.

### Retention policy: use 24h extended caching
GPT-5.2 supports `prompt_cache_retention: "24h"` which uses GPU-local storage. Default in-memory caching only lasts 5-10 minutes of inactivity. For batch generation (where we process 50+ SKUs over minutes/hours), the 24h retention would ensure cache hits across the entire batch.

**Our code does NOT currently set this parameter.**

### Schema counts as cacheable prefix
The structured output schema (our CANDIDATE_SCHEMA) is part of the cacheable request. Since it's identical across all requests, it contributes to cache hits. This is already working in our favor.

### Request rate optimization
The docs recommend keeping request rates below ~15 per minute per prefix-key combination to avoid cache overflow. For batch processing, this means we should pace requests rather than fire them all simultaneously.

---

## 4. Structured Output Best Practices

### Use `strict: true` with json_schema (not json_object)
We currently use `response_format={"type": "json_object"}` which is the older JSON mode. The docs recommend upgrading to:

```python
response_format={
    "type": "json_schema",
    "json_schema": {
        "name": "product_content",
        "strict": True,
        "schema": CANDIDATE_SCHEMA
    }
}
```

**Benefits of strict mode:**
- "No need to validate or retry incorrectly formatted responses"
- Eliminates hallucinated extra fields
- Prevents omitted required keys
- Makes safety-based refusals programmatically detectable

**This would eliminate our JSON decode retry loop** (lines 214-237 in openai_provider.py) for schema violations, since the model is constrained to produce valid output.

### Schema requirements for strict mode
- Must include `additionalProperties: false` at every object level
- All fields must be `required` (use nullable types instead of optional fields)
- Supported types: string, number, integer, boolean, null, array, object, enum
- `maxLength` in schema descriptions helps guide the model but isn't enforced at the API level in strict mode

### Simpler prompting
The docs note that structured outputs "reduces need for strongly-worded formatting instructions." With strict mode, we can remove instructions like "Generate one JSON object containing..." and "respond with valid JSON only" from our prompts, freeing up token budget for quality-improving instructions.

### Schema as documentation
The `description` fields in our schema are used by the model as generation guidance. Our current descriptions are good (e.g., "Google Shopping title (max 150 characters)"). Consider enriching them with quality criteria.

---

## 5. Temperature & Parameter Settings

### Current setting: temperature=0.7 everywhere
Our `openai_provider.py` hardcodes `temperature=0.7` for all requests. The hybrid generation uses `0.6` for variant adaptation.

### GPT-5.2 parameter constraints
With GPT-5.2, the available controls depend on reasoning_effort:

**reasoning_effort: none (current default)**
- `temperature`: supported (0.0-2.0)
- `top_p`: supported
- `logprobs`: supported

**reasoning_effort: low/medium/high/xhigh**
- `temperature`: NOT SUPPORTED (will error)
- `top_p`: NOT SUPPORTED
- Use `text.verbosity` (high/medium/low) instead
- Use `max_output_tokens` for length control

### Recommended approach for quality optimization
For maximum content quality (our stated goal), the recommendation from the docs is:
1. Start with `reasoning_effort: medium` (gives the model internal CoT for better decisions)
2. Use `text.verbosity: medium` for descriptions, `text.verbosity: low` for titles
3. Do NOT pass temperature (incompatible with reasoning)
4. If quality is still insufficient, escalate to `reasoning_effort: high`

### Cost/latency tradeoff
Higher reasoning effort = more reasoning tokens = higher cost + latency. For batch generation of 50+ SKUs, consider:
- `reasoning_effort: medium` for base SKUs (full generation)
- `reasoning_effort: low` or `none` for variant adaptation (simpler task)

### Verbosity control (new parameter)
`text.verbosity` is a new GPT-5.2 parameter:
- `high`: longer, more structured output with explanations
- `medium`: balanced
- `low`: shorter, concise output

For our multi-field output, `medium` is likely optimal. If descriptions are too short, try `high`.

---

## 6. What We're Likely Doing Wrong Based on These Docs

### ISSUE 1: temperature + reasoning_effort conflict (BUG)
**File**: `/Users/bobby/Documents/GitHub/Allied-FeedOps/src/feedops/providers/openai_provider.py` lines 172, 183
**Problem**: We always pass `temperature=0.7` AND conditionally pass `reasoning_effort`. On GPT-5.2, these are mutually exclusive. If `FEEDOPS_REASONING_EFFORT` env var is set to anything other than `none`, API calls will error.
**Fix**: When reasoning_effort is set (and not `none`), omit temperature. When reasoning_effort is `none` or unset, keep temperature.

### ISSUE 2: Using json_object instead of json_schema with strict mode
**File**: `/Users/bobby/Documents/GitHub/Allied-FeedOps/src/feedops/providers/openai_provider.py` lines 171, 182
**Problem**: We use `response_format={"type": "json_object"}` which is the legacy approach. With GPT-5.2, we should use `json_schema` with `strict: true` and pass our CANDIDATE_SCHEMA.
**Impact**: We're relying on retry loops for JSON validation when strict mode would guarantee schema compliance. This wastes tokens and adds latency on validation failures.
**Fix**: Switch to `response_format={"type": "json_schema", "json_schema": {"name": "product_content", "strict": True, "schema": CANDIDATE_SCHEMA}}` and add `additionalProperties: false` to all objects in the schema.

### ISSUE 3: Not using extended prompt cache retention
**File**: `/Users/bobby/Documents/GitHub/Allied-FeedOps/src/feedops/providers/openai_provider.py`
**Problem**: We don't set `prompt_cache_retention: "24h"`. Default in-memory caching only lasts 5-10 minutes. During long batch runs, earlier cache entries may expire.
**Fix**: Add `prompt_cache_retention="24h"` to API calls (GPT-5.2 supports this).

### ISSUE 4: Gold standard examples in dynamic user prompt instead of static system prompt
**File**: `/Users/bobby/Documents/GitHub/Allied-FeedOps/src/feedops/api/prompt_loader.py`
**Problem**: Gold standard examples are loaded from DB and injected into the user prompt. Since these change infrequently, they break the cacheable prefix -- every request's user message starts differently depending on which examples are included.
**Fix**: Move gold standard examples into the system prompt (after the static rules, before the user message). Update them only when the DB content changes. This extends the cacheable prefix significantly.

### ISSUE 5: No reasoning_effort set by default for quality optimization
**File**: `/Users/bobby/Documents/GitHub/Allied-FeedOps/src/feedops/pipeline/optimize.py` line 148
**Problem**: `reasoning_effort` is only set if the `FEEDOPS_REASONING_EFFORT` env var exists. GPT-5.2 defaults to `none`, meaning the model does zero internal reasoning. For content quality optimization, this is leaving quality on the table.
**Fix**: Default to `reasoning_effort: medium` for content generation (or at minimum `low`). Make it configurable but don't default to `none` when quality is the goal.

### ISSUE 6: Not using the Responses API
**Problem**: We use the Chat Completions API. The docs recommend migrating to the Responses API for GPT-5.2 to unlock: "passing chain of thought (CoT) between turns, fewer generated reasoning tokens, higher cache hit rates, and lower latency."
**Impact**: Lower cache hit rates and inability to pass reasoning context between retries.
**Priority**: Medium -- this is an optimization, not a bug. The Chat Completions API still works.

### ISSUE 7: System prompt uses === headers instead of XML tags
**File**: `/Users/bobby/Documents/GitHub/Allied-FeedOps/src/feedops/pipeline/prompts.py`
**Problem**: Our SYSTEM_PROMPT uses `=== P0_GLOBAL_FACTUAL_RULES ===` style delimiters. The GPT-5.2 prompting guide specifically recommends XML tags for section delineation, as the model parses these more reliably.
**Fix**: Convert section headers to XML tags: `<p0_global_factual_rules>...</p0_global_factual_rules>`. This is a low-risk change that may improve instruction adherence.

### ISSUE 8: Vague length targets instead of hard constraints
**Problem**: Our schema descriptions say "target 600-800 characters" which GPT-5.2's lower verbosity may interpret as "optional guideline." With GPT-5.2's conservative/literal instruction following, vague targets may result in shorter-than-desired output.
**Fix**: Change to explicit constraints: "MUST be between 600 and 800 characters. Content shorter than 600 characters is a failure." Or use `text.verbosity: high` when generating descriptions.

---

## Priority Implementation Order

1. **FIX BUG**: temperature/reasoning_effort mutual exclusion (ISSUE 1) -- prevents API errors
2. **Quick win**: Switch to json_schema strict mode (ISSUE 2) -- eliminates retry waste
3. **Quick win**: Set default reasoning_effort to medium (ISSUE 5) -- immediate quality improvement
4. **Quick win**: Add prompt_cache_retention: "24h" (ISSUE 3) -- cost reduction for batches
5. **Medium effort**: Move gold examples to system prompt (ISSUE 4) -- better caching
6. **Medium effort**: Convert to XML tags in system prompt (ISSUE 7) -- instruction adherence
7. **Low priority**: Strengthen length constraints (ISSUE 8) -- output consistency
8. **Future**: Migrate to Responses API (ISSUE 6) -- further optimization
