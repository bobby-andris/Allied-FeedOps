# FeedOps Post-custom_label_0 Optimization Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Increase qualified Shopping/SEO traffic and onsite conversion by improving title/description generation quality, observability, and intent alignment now that Merchant Center custom labels are mostly synchronized.

**Architecture:** Treat `custom_label_0` as the segmentation spine for generation strategy and experimentation, persist final post-expansion payloads as source-of-truth, and enforce clean search-intent evidence before LLM generation. Run controlled segment-level rollouts with explicit performance gates.

**Tech Stack:** Python FeedOps pipeline, Supabase (Postgres), Next.js dashboard API routes, Google Merchant API, Google Ads reporting, Notion execution tracking.

## Current State (Verified)
- Merchant Center API access now works for account `136699027` with service-account file credentials.
- `variant_index` label coverage is high: `master_skus_with_label0 = 2717/2784`, `rows_with_label0 = 70925`.
- Remaining missing cohort after re-sync:
  - `rows_missing_label0_with_offer = 1098`
  - `master_skus_missing_label0_with_offer = 175`
  - Reconciliation split: `949` variants exist in GMC but label0 empty; `149` variants missing in GMC products set.
- Reliability patch shipped for Merchant fetch retries/timeouts.

## Task 1: Stabilize Merchant Label Sync as an Operational Primitive

**Files:**
- Modify: `src/feedops/integrations/merchant_center.py`
- Modify: `src/feedops/jobs/workers.py`
- Add: `src/feedops/jobs/metrics.py` (optional helper)
- Test: `tests/test_merchant_center.py`

**Step 1: Add explicit sync telemetry output**
- Emit counters for: offers fetched, variants attempted, variants updated, variants missing in GMC, variants with blank label0.

**Step 2: Add bounded retry at worker layer for full-catalog fetch**
- Keep endpoint-level retries and add worker-level retry for full pagination run failures.

**Step 3: Add a deterministic “no-match export” utility command**
- Persist current reconciliation CSV generation as a reusable command.

**Step 4: Add tests for retry/telemetry/no-match paths**
- Extend existing Merchant tests with expected status/counter behavior.

**Step 5: Verify and commit**
- Run targeted tests and a dry-run sync.

## Task 2: Lock Prompt Contract by Channel and Reduce Instruction Entropy

**Files:**
- Modify: `src/feedops/pipeline/prompts.py`
- Modify: `src/feedops/pipeline/generator.py`
- Modify: `src/feedops/pipeline/evidence.py`
- Test: `tests/test_evidence_custom_label.py`
- Add: `tests/test_prompt_contract.py`

**Step 1: Split channel intent blocks into strict non-conflicting objectives**
- Google/Bing: feed relevance + query fit + policy-safe phrasing.
- Shopify: semantic breadth + conversion clarity + trust/supporting detail.

**Step 2: Add prompt budget and ordering guardrails**
- Keep high-priority constraints in front; move low-priority examples/rules behind.

**Step 3: Enforce `custom_label_0` role in prompt semantics**
- Label influences lexical framing only; never emitted as factual claim.

**Step 4: Add tests for conflicting-instruction regression**
- Detect if mutually contradictory directives are reintroduced.

**Step 5: Verify and commit**
- Run generation smoke tests with golden SKUs by segment.

## Task 3: Build Search-Intent Evidence Layer (Relevance First)

**Files:**
- Modify: `src/feedops/integrations/search_query_insights.py`
- Modify: `src/feedops/pipeline/evidence.py`
- Add: `src/feedops/pipeline/intent_curator.py`
- Test: `tests/test_search_query_hygiene.py`

**Step 1: Add dedupe + intent filtering with strict allow/deny signals**
- Remove competitor/noisy/mismatched-intent terms before LLM evidence.

**Step 2: Weight terms by recency + conversion support + segment fit**
- Build a compact curated term list per master SKU and per `custom_label_0`.

**Step 3: Add fallback for sparse term histories**
- Use segment-level representative terms where SKU evidence is thin.

**Step 4: Add validation tests**
- Ensure irrelevant terms are excluded and high-intent terms preserved.

**Step 5: Verify and commit**
- Compare curated vs raw term sets on sample SKUs.

## Task 4: Complete L1 Final-Payload Observability and Diffability

**Files:**
- Modify: `dashboard/src/app/api/publish/sku/route.ts`
- Modify: `dashboard/src/app/api/publish/batch/route.ts`
- Modify: `dashboard/src/lib/publishing/final-payload.ts`
- Modify: `dashboard/src/lib/publishing/types.ts`
- Migration done: `supabase/migrations/033_add_publish_event_final_payload_snapshot.sql`

**Step 1: Guarantee snapshot write for all publish paths/channels**
- Require `final_payload_snapshot` for successful/ready publish records.

**Step 2: Add payload hash + template hash metadata**
- Enable deterministic diff and attribution across revisions.

**Step 3: Add dashboard read model for snapshot inspection**
- Expose final text that was actually prepared/published by channel.

**Step 4: Verify and commit**
- Validate random SKU snapshots for Google/Bing/Shopify paths.

## Task 5: Resolve Remaining Missing Label Cohort with Explicit Buckets

**Files:**
- Use report outputs in `reports/merchant_center/*.csv`
- Modify (if needed): `src/feedops/jobs/workers.py`
- Add: `docs/audit/custom-label-reconciliation.md`

**Step 1: Split backlog into two work queues**
- Queue A: `exists_in_gmc = False` (stale/invalid offer IDs).
- Queue B: `exists_in_gmc = True` with blank label0 (upstream Merchant label assignment gap).

**Step 2: Create correction playbooks by queue**
- Queue A: refresh `gmc_offer_id` mapping from source feed/indexing.
- Queue B: update Merchant feed rule/source attribute population.

**Step 3: Re-run sync and re-export reconciliation report**
- Track closure % by day/week until backlog reaches target threshold.

## Task 6: Controlled Performance Rollout and Revenue Attribution

**Files:**
- Modify: `src/feedops/jobs/workers.py`
- Add: `src/feedops/analysis/segment_lift.py`
- Add: `docs/audit/segment-rollout-scorecard.md`

**Step 1: Define segment rollout order**
- Start with top 10 `custom_label_0` by impression and revenue contribution.

**Step 2: Apply holdout/phase strategy**
- 2-week windows by segment with fixed pre/post baselines.

**Step 3: Track lift metrics**
- Impressions, CTR, CVR, Revenue, and quality proxy (return/refund where available).

**Step 4: Promotion gate**
- Only scale segments that clear target lift thresholds and maintain policy quality.

## Success Criteria
- `master_skus_with_label0` coverage ≥ 99% of active catalog.
- 100% of publish events store `final_payload_snapshot` for successful/ready paths.
- Prompt conflict regressions prevented by tests.
- Query evidence duplication and irrelevant term contamination reduced materially.
- Segment rollouts show positive lift in qualified traffic and revenue metrics before full release.

## Rollback Strategy
- Keep previous prompt template versions available and hash-addressable.
- Feature-flag curated intent inputs.
- Feature-flag new channel prompt contract.
- For degraded segments, revert to prior generation profile and retain snapshot evidence for RCA.
