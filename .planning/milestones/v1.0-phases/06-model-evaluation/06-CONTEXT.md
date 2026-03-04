# Phase 6: Model Evaluation - Context

**Gathered:** 2026-03-03
**Status:** Ready for planning

<domain>
## Phase Boundary

Run a head-to-head evaluation of Claude (Sonnet 4.6 + Opus) vs GPT-5.2 on 10 diverse SKUs with blind human scoring. Produce concrete cost/quality/latency data and a written recommendation for which provider to use as default. No prompt changes, no new generation modes — evaluation uses existing infrastructure with identical prompts across all models.

</domain>

<decisions>
## Implementation Decisions

### SKU selection approach
- Auto-suggest 15-20 candidates with diversity rationale, Bobby/Robert pick final 10
- Diversity dimensions: category spread, single vs multi-SKU products, description complexity, collection variety
- 3-4 of the 10 SKUs should have existing `approved_content` for reference comparison (new output vs previously approved)
- Script queries DB for candidates and presents selection with rationale

### Models under evaluation
- 3-way comparison: Claude Sonnet 4.6, Claude Opus, GPT-5.2
- All use identical prompts (no provider-specific optimization — locked in Phase 5)
- Claude models selected via `FEEDOPS_CLAUDE_MODEL` env var, GPT-5.2 via existing `FEEDOPS_OPENAI_MODEL`

### Scoring methodology
- Pass/fail + freeform notes per output (mirrors existing approval workflow)
- Bobby and Robert score independently (measures inter-rater agreement)
- Blind evaluation: Google Sheet with hidden provider labels (Output A/B/C), labels revealed after all scoring complete
- All 3 platforms evaluated: Google, Bing, Shopify — 90 total outputs to score (10 SKUs x 3 models x 3 platforms)

### Generation and metrics capture
- 3 generation passes per SKU x model for median latency and variance measurement
- Token-based cost calculation using `last_usage` from provider metrics + published pricing
- Output consistency measured across the 3 passes per SKU x model (how similar are repeated generations?)
- First pass output used for blind scoring; all 3 passes stored for consistency analysis

### Output artifacts
- All results in `docs/evaluation/` (permanent git record)
- Reusable parameterized evaluation script (takes model list, SKU list, output directory — runnable for future model comparisons)
- Final recommendation: single default provider winner + scenario-based exceptions (e.g., "use X for category Y if cost is priority")

### Claude's Discretion
- Evaluation script architecture (single script vs modular)
- Consistency measurement approach (exact string similarity vs semantic)
- Google Sheet structure and formatting
- How to handle generation failures during evaluation runs
- Statistical presentation of latency data (tables vs charts)

</decisions>

<specifics>
## Specific Ideas

- Phase 4's `verify_content_quality.py` is the starting point — extend it for multi-model evaluation with metrics capture
- The evaluation script should be parameterized for reuse when new model versions drop (GPT-6, Claude 5, etc.)
- Include previously-approved content as a "human baseline" in the comparison — not as a third provider, but as context for scoring ("is the new output better/worse than what we already approved?")
- Inter-rater agreement between Bobby and Robert is itself a useful metric — high disagreement signals the models are producing "taste-dependent" content

</specifics>

<code_context>
## Existing Code Insights

### Reusable Assets
- `scripts/verify_content_quality.py`: Post-deploy verification script — calls `/optimize-sku`, checks description length per platform. Starting point for evaluation script
- `providers/factory.py`: `get_provider(preferred)` supports "claude"/"openai"/"gemini" — can switch models via env vars
- `providers/base.py`: `LLMProvider` ABC with `last_usage`, `last_parse_details`, `last_retry_counts` — all metrics available for capture
- `providers/claude_provider.py`: Full ClaudeProvider with structured output, metrics parity, image support

### Established Patterns
- Provider selection via `FEEDOPS_PROVIDER` env var + `FEEDOPS_CLAUDE_MODEL` / `FEEDOPS_OPENAI_MODEL` for model selection
- `/optimize-sku` endpoint accepts `master_sku` + `content_types` list — generates for all specified platforms in one call
- Token usage exposed via `last_usage` property on all providers (input_tokens, output_tokens)
- Content stored in Supabase `generated_content` table with `candidate_content` JSONB field

### Integration Points
- `/optimize-sku` endpoint: Main generation entry point — evaluation script calls this per SKU per provider
- `FEEDOPS_PROVIDER` env var: Switches between providers at runtime
- `generated_content.approved_content`: Reference baseline for SKUs that have been previously approved
- Google Sheets API: For creating the blind evaluation spreadsheet

</code_context>

<deferred>
## Deferred Ideas

- Claude-optimized prompt variant — evaluate after baseline comparison with identical prompts proves which provider handles the current prompt better
- Extended thinking budget tuning — if Claude Opus scores well, test different thinking budgets (low/medium/high) in a follow-up evaluation
- Automated LLM-as-judge scoring — out of scope per requirements (human scoring is ground truth), but could supplement future evaluations
- Claude fallback chains (OpenAI->Claude or Claude->OpenAI) — evaluate after provider strengths are proven

</deferred>

---

*Phase: 06-model-evaluation*
*Context gathered: 2026-03-03*
