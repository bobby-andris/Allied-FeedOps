# Phase 25-07: Round 3 Regeneration + Human Evaluation

## Status: SUPERSEDED

**Superseded by:** Phase 25.3 (Prompt Rewrite from Human Feedback)

## Context
Plan 25-07 called for regenerating all 10 test SKUs with 25-06 skill/prohibition fixes, building a blind Round 3 A/B comparison, and human evaluation against 8/10 thresholds.

## Why Superseded
Round 2 evaluation revealed the root cause was not fixable by skill injection alone — the system prompt was 57K+ tokens with 12 internal contradictions from dumped skill snippets. Phase 25.3 took a fundamentally different approach: rewriting prompts as GPT-5.2 creative briefs (~8-10K system prompt) instead of iterating on the broken skill-injection approach.

## Artifacts
- `25-07-round3-comparisons.md` — partial comparison document (never finalized)
- Round 2 evaluation results informed the 25.3 approach: `25-02-evaluation-results.md`
