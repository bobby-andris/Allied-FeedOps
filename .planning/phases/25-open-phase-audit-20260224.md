# Open Phase Audit: Phase 25+ (as of 2026-02-24)

## Summary

| Phase | Plan | Status | Action Taken |
|-------|------|--------|--------------|
| 25 | 25-03 (Publish best SKU) | BLOCKED | Requires human gate pass + dashboard publish. Cannot close this session. |
| 25 | 25-07 (Round 3 regen) | SUPERSEDED | SUMMARY written. Superseded by 25.3. |
| 25.1 | 25.1-03 (A/B test) | COMPLETE | SUMMARY written. Negative result spawned 25.2. |
| 25.2 | 25.2-03 (6-SKU validation) | PARTIAL/SUPERSEDED | SUMMARY written. Superseded by 25.3. |
| 25.3 | 25.3-01 (cherry-pick) | COMPLETE | SUMMARY written. Commit `5933c906`. |
| 25.3 | 25.3-02 (prompt rewrite) | COMPLETE | SUMMARY written. Commit `ad68f85c`. |
| 25.3 | 25.3-03 (validation) | IN PROGRESS | Automated gates: PASS. Human gate: PENDING. |
| 25.3 | 25.3-04 (deploy) | BLOCKED | Blocked on 25.3-03 human gate. |

## Root Cause: Prompt Contract Drift

**Problem:** The committed `scripts/ab_prompt_test.py` imported `build_core_prompt` (v1 legacy), which injects `"Product Evidence Table:\n..."` into user prompts. The v2 per-platform builders (`build_google_prompt`, `build_bing_prompt`, `build_shopify_prompt`) use XML-tagged `<evidence_table>` instead.

**Fix:** Rewrote `ab_prompt_test.py` imports to use v2 builders. Added guardrail tests that fail if `build_core_prompt` appears in v2 code paths.

**Commits:**
- `97277291` — feat(25.3-03): wire v2 per-platform harness, fix prompt contract drift
- `a3134e31` — test(25.3-03): add guardrail tests for v2 prompt contract and harness

**Verification:**
- 49 prompt-related tests pass
- Fresh unseen run (5 SKUs, seed=52): 0 legacy patterns, 10/10 task tags, 65/65 checks pass
- Fresh canonical run: in progress

## Remaining Blockers

1. **Human gate (Bobby + Robert review)** — blank scorecard at `.planning/phases/25.3-prompt-rewrite/25.3a-human-scorecard.md`
2. **Phase 25-03 (Publish best SKU)** — requires human-approved content + dashboard publish workflow
3. **Phase 25.3-04 (Deploy v2 default)** — set `FEEDOPS_PROMPT_VERSION=v2` on Cloud Run after human gate passes

## Branch Safety

All work is on branch `v1.3a/prompt-rewrite-validation`. Production `master` is untouched. The v2 path is behind the `FEEDOPS_PROMPT_VERSION` feature flag (defaults to `v1`).
