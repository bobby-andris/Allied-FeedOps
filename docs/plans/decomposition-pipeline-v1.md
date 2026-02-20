# Decomposition Pipeline v1 (Deterministic)

## Purpose
This document describes the v1 decomposition pipeline shipped for Shopping Funnel intelligence. The goal is to produce deterministic, versioned query artifacts for each `search_term × custom_label_0` pair and persist them for reuse across optimization endpoints.

## Scope
- Deterministic parser only (no LLM calls in v1).
- Google Ads-first intelligence.
- Backward-compatible response contract for existing Shopping Funnel consumers.
- Append-only persistence to optimization control-plane tables:
  - `query_intent_features`
  - `query_value_scores`
  - `routing_recommendations`

## Versions
- Parser version: `decomp_v1`
- Score version: `score_v1`
- Recommendation version: `route_v1`
- Stale threshold: `24h`

## Pipeline Flow
1. Build pair list from `needs-decision` terms (`search_term × custom_label_0`).
2. Read latest persisted artifacts by pair.
3. Recompute pairs that are missing, stale, or version-mismatched.
4. Persist recomputed artifacts (best-effort, append-only).
5. Roll up pair-level outputs into existing term-level fields:
  - `intent_features`
  - `recommendation`
  - `value_score`
6. Return additive `pipeline` metadata to expose cache/recompute/warnings.

## Deterministic Intent Features
For each pair, the engine extracts:
- `product_object`
- `modifier_tokens`
- `use_case_tokens`
- `is_branded`
- `is_competitor`
- `has_mismatch_risk`

Precedence:
- `branded > competitor > mismatch > funnel`

Ambiguity handling:
- If multiple product-object phrases match, select highest-priority phrase.
- Store all candidates and ambiguity diagnostics in `query_intent_features.extracted`.

## Confidence Logic
Intent confidence:
- Base `0.35`
- `+0.20` product-object found
- `+0.10` modifier/use-case signal
- `+0.20` explicit branded/competitor phrase
- `-0.15` ambiguous product-object
- Clamp to `[0.05, 0.99]`

Recommendation confidence:
- Branded: `0.96`
- Competitor: `0.90`
- Mismatch: `0.78`
- Funnel formula: `0.55 + min(clicks,200)/2000 + min(conversions,20)/100 + min(labelCount,5)*0.03`
- Clamp to `[0.05, 0.99]`

Uncertainty:
- `1 - min(clicks/50, 1)` (rounded to 4 decimals)

## Persistence Mapping
`query_intent_features`
- Stores parser outputs + confidence.
- `extracted` stores deterministic diagnostics and token matches.

`query_value_scores`
- Stores value estimates and uncertainty.
- `model_inputs` stores numeric inputs used for score calculation.

`routing_recommendations`
- Stores recommended action/tier + confidence + reason codes.
- `metadata` stores parser/score/recommendation versions plus source metric snapshot.

## Endpoints Added
- `GET /api/optimization/decomposition/health`
  - Coverage, stale %, confidence buckets, low-confidence terms, warning list.
- `POST /api/optimization/decomposition/backfill`
  - Supports `dry_run` (default true), bounded batch processing, and optional persistence.
  - Uses `x-internal-token` auth outside development (`INTERNAL_API_TOKEN`).

## Backfill Instructions
1. Dry run a bounded window:
```bash
curl -X POST \
  "http://localhost:3000/api/optimization/decomposition/backfill?start_date=2026-01-21&end_date=2026-02-20&max_pairs=5000&dry_run=true"
```
2. Persist once dry-run looks healthy:
```bash
curl -X POST \
  "http://localhost:3000/api/optimization/decomposition/backfill?start_date=2026-01-21&end_date=2026-02-20&max_pairs=5000&dry_run=false" \
  -H "x-internal-token: $INTERNAL_API_TOKEN"
```
3. Validate health:
```bash
curl "http://localhost:3000/api/optimization/decomposition/health?start_date=2026-01-21&end_date=2026-02-20"
```

## Troubleshooting
### Low coverage
- Check `pipeline.warnings` in `needs-decision` response.
- Run backfill in dry-run first, then persist.
- Confirm service-role Supabase credentials are configured correctly.

### High stale %
- Verify requests are using expected version constants (`decomp_v1`, `score_v1`, `route_v1`).
- Trigger backfill for stale window.

### Insert/write failures
- Requests should still return computed in-memory artifacts (best-effort fallback).
- Inspect warning messages from:
  - `/api/search-terms/needs-decision`
  - `/api/optimization/decomposition/backfill`
  - `/api/optimization/decomposition/health`

### Unexpected recommendation outputs
- Inspect per-pair diagnostics from persisted `query_intent_features.extracted`.
- Confirm token dictionaries in `decomposition/config.ts` include expected phrases.

## Rollout Guidance
1. Set `SHOPPING_DECOMPOSITION_PIPELINE_ENABLED=true` in target environment.
2. Run backfill dry-run for 30-day window.
3. Run real backfill for same window.
4. Monitor health endpoint for 72h.
5. If warning/error rate rises above operational threshold, disable feature flag and continue with in-memory fallback path.
