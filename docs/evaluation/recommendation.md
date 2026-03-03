# Production Recommendation: Claude Sonnet 4.6 + v3 Skill Prompt

**Date:** 2026-03-03
**Decision:** Switch production content generation from GPT-5.2 to Claude Sonnet 4.6 with v3 skill-adapted prompt

## Model Comparison (Real Evaluation Data)

| Metric | GPT-5.2 | Sonnet 4.6 (v2) | Sonnet 4.6 (v3 skill) | Opus 4.6 |
|--------|---------|------------------|----------------------|----------|
| Cost per SKU (3 platforms) | $0.116 | $0.017 | **$0.018** | $0.027 |
| Google desc avg length | 809 chars | 1,097 chars | **1,425 chars** | 1,123 chars |
| Google avg latency | 26.7s | 7.5s | **12.7s** | 7.7s |
| Blind quality score | 6.15/10 | — | **8.85/10** | 8.00/10 |
| {FINISH_NAME} compliance | 100% | 100% | **100%** | 100% |
| {FINISH_SENTENCE} compliance | 100% | 100% | **100%** | 100% |
| JSON parse failures | 0 | 0 | **0** | 0 |

## Why Sonnet 4.6 + v3

- **84% cheaper** than GPT-5.2 ($0.018 vs $0.116 per SKU)
- **2x faster** (12.7s vs 26.7s for Google platform)
- **Richer descriptions** — benefit-forward hooks, collection storytelling, 8-step structure
- **Best blind evaluation score** — 8.85/10 vs 6.15/10 for GPT-5.2
- **Zero-risk rollback** — env var change, no code deployment needed

## Go-Live Configuration

### Cloud Run env vars to set:

```bash
# Switch provider to Claude
FEEDOPS_PROVIDER=claude

# Activate v3 skill prompt for Google
FEEDOPS_GOOGLE_BRIEF_VERSION=v3
```

### Already configured (no action needed):

- `ANTHROPIC_API_KEY` — secret `feedops-anthropic-api-key` already bound
- `FEEDOPS_CLAUDE_MODEL` — defaults to `claude-sonnet-4-6`
- `OPENAI_API_KEY` — remains for fallback

## Rollback Procedure

Instant rollback — change env vars only, no code deployment:

```bash
# Rollback to GPT-5.2
gcloud run services update feedops-pipeline \
  --update-env-vars="FEEDOPS_PROVIDER=openai,FEEDOPS_GOOGLE_BRIEF_VERSION=v2" \
  --region=us-east1 \
  --project=bobbys-project-346400
```

## Post-Deploy Verification

1. Verify `/health` endpoint responds
2. Generate 1 SKU via dashboard regeneration
3. Verify description > 500 chars, {FINISH_NAME} in title, {FINISH_SENTENCE} in description
4. Bobby/Robert human review of output quality
5. If approved: production rollout confirmed

## Monthly Cost Projection

| Scenario | 500 SKUs/month | Annual |
|----------|---------------|--------|
| GPT-5.2 (current) | $58.00 | $696.00 |
| Sonnet 4.6 + v3 | $9.03 | $108.36 |
| **Annual savings** | | **$587.64** |

## Future Considerations

- **Image input**: Infrastructure exists (ImageInput, fetch_image, multimodal in ClaudeProvider). ~15 lines in executor.py to wire in. Defer until post-deploy verification.
- **Bing v3 prompt**: Create Bing-specific v3 skill prompt to fix the {FINISH_NAME} bug (Phase 7)
- **Rate limiting**: SDK auto-retries handle 429s. Add inter-SKU delay only if batch throughput is impacted.
