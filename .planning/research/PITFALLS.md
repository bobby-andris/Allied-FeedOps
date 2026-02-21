# Pitfalls Research

**Domain:** Diagnosing and fixing Google Shopping feed impact issues in existing systems (Allied FeedOps v1.2)
**Researched:** 2026-02-20
**Confidence:** HIGH — grounded in verified codebase evidence, documented investigation history, and confirmed external patterns

---

## Critical Pitfalls

### Pitfall 1: Blaming Content Quality When the Real Bottleneck is Coverage

**What goes wrong:**
Team spends weeks tuning prompts, improving gold standard examples, and raising average quality scores from 75 to 82/100 — but Shopping impressions barely move. The optimization improved content that was never being surfaced in the first place. The real problem was that only ~200 of 2,784 SKUs had published content in GMC, so the higher-quality content affected a negligible fraction of catalog exposure.

**Why it happens:**
Coverage is invisible in the metrics dashboards most teams watch. Google Ads shows campaign-level impressions. If 2,500 SKUs still have original unoptimized titles, a 7-point quality improvement on 200 SKUs moves total catalog CTR by fractions of a percent. Teams optimize the wrong layer because quality is legible and measurable while coverage requires explicit counting.

**How to avoid:**
Before touching prompt quality or generation logic, establish a coverage baseline:
1. Count SKUs with `approved_content` in `generated_content` table
2. Count SKUs with at least one `publish_events` row (actually pushed to Google Sheets)
3. Verify Google Sheets row count matches expected published SKU × variant count
4. Check that GMC supplemental feed is actually fetching the updated sheet
5. If published SKU count < 10% of catalog, fix coverage before fixing quality

**Warning signs:**
- Generate and approve content but impressions don't move
- Quality scores go up but campaign CTR stays flat
- Less than 500 SKUs have `publish_events` entries despite months of operation

**Phase to address:**
Phase 1 (Diagnosis) — Measure coverage first, before any fix is applied

**Confidence:** HIGH — Verified via `generated_content`, `publish_events`, and `variant_index` table structure

---

### Pitfall 2: Assuming Feature Flags Are Active When They Default to True

**What goes wrong:**
`PROMPT_CONTRACT_V2`, `INTENT_CURATOR_V1`, and `SEGMENT_STRATEGY_V1` all default to `True` if the environment variable is absent (see `feature_flags.py` lines 16-24). A developer sees these defined as feature flags and assumes they need to be explicitly enabled in production. They check Cloud Run environment variables, find no `PROMPT_CONTRACT_V2=1` entry, and conclude the feature is off — and waste time trying to "activate" something that was already running.

**Why it happens:**
Feature flags that default to `True` are unusual. The common pattern is opt-in (default `False`). When a developer sees a flag with no env var set, they assume it's disabled. This codebase inverts the convention: absence of the variable means enabled.

**How to avoid:**
Read `feature_flags.py` before assuming any flag is inactive:
```python
def _is_enabled(name: str, default: bool) -> bool:
    raw = os.getenv(name)
    if raw is None:
        return default  # <-- returns True when env var is absent
```
To verify actual flag state in production, add a `/config/flags` health endpoint that logs active flag states on startup, or check Cloud Run logs for `"PROMPT_CONTRACT_V2 disabled"` — the absence of this log line means it IS enabled and using canonical Python prompts.

**Warning signs:**
- Searching Cloud Run env vars for the flag name and finding nothing, then concluding it's off
- Attempting to set `PROMPT_CONTRACT_V2=1` in Cloud Run thinking this enables it
- Treating the absence of an env var as proof the feature is not running

**Phase to address:**
Phase 1 (Diagnosis) — Verify flag states before diagnosing generation quality

**Confidence:** HIGH — Verified directly in `/Users/bobby/Documents/GitHub/Allied-FeedOps/src/feedops/pipeline/feature_flags.py`

---

### Pitfall 3: Treating Dead Code as the Active Execution Path

**What goes wrong:**
`dashboard/src/lib/regeneration/core.ts` contains a complete alternative content generation pipeline — its own OpenAI calls, prompt construction, and `regenerateContent()` function. It looks wired. It has substantial code. A developer investigating why content seems "off" reads this file and concludes this is the runtime path. They spend hours diagnosing prompt issues in TypeScript that are never executed. Meanwhile the actual runtime path is the Python Cloud Run pipeline.

**Why it happens:**
Dead code that isn't marked as deprecated looks exactly like live code. Signal audit confirmed `core.ts:regenerateContent()` has zero imports in the entire codebase. But without that knowledge, it's indistinguishable from an active path. The same pattern applies to `dashboard/src/lib/regeneration/prompts.ts` — `SYSTEM_PROMPT` and `PLATFORM_CONTEXT` are defined there but never used at runtime; only `validateGeneratedContent()` is called.

**How to avoid:**
Before diagnosing any quality issue, verify the actual execution path by tracing calls from the UI entry point forward:
1. `RegenerateButton.tsx` → `POST /api/regenerate` (dashboard route)
2. `route.ts` → `POST {PIPELINE_URL}/regenerate` (Python Cloud Run)
3. Python handles all generation; TypeScript is only a proxy
Run `grep -r "from '@/lib/regeneration/core'" dashboard/src` — it returns nothing. That's proof core.ts is dead.

**Warning signs:**
- Reading TypeScript prompt files to understand content generation behavior
- Diagnosing prompt quality by looking at `dashboard/src/lib/regeneration/prompts.ts`
- Spending time on `SYSTEM_PROMPT` in TypeScript when Python's `prompts.py` is canonical

**Phase to address:**
Phase 1 (Diagnosis) — Trace runtime path before reading any source file

**Confidence:** HIGH — Confirmed via signal audit at `/Users/bobby/Documents/GitHub/Allied-FeedOps/docs/audit/signal-audit-2026-02-11/prompt-wiring-map.md`

---

### Pitfall 4: Misattributing Low Impact to Auction Dynamics Before Verifying Feed Propagation

**What goes wrong:**
Team publishes content to Google Sheets, waits a week, sees no impression uplift, and concludes "Google's auction doesn't reward our optimized titles" or "this category is too competitive." In reality, the supplemental feed never refreshed GMC because the scheduled fetch was misconfigured, pointing to the wrong URL, or the sheet ID changed after a rename. The content change never reached Google's index.

**Why it happens:**
The propagation chain has four independently-failable steps: (1) Google Sheets write succeeds, (2) GMC scheduled fetch picks up the sheet, (3) GMC processes and approves the product, (4) Google Ads picks up the refreshed product data. Each step is asynchronous. Teams check step 1 (Google Sheets updated) and assume steps 2-4 followed. GMC's supplemental feed fetch is not real-time — it runs on a schedule, typically daily, and failures are silent unless you check GMC's feed diagnostics.

**How to avoid:**
Before concluding no impact, verify propagation at each layer:
1. Check Google Sheets row contains the new title for the target offer ID
2. In GMC > Products > Your products, search for the offer ID and check the title shown in GMC
3. Compare GMC product title to what's in Google Sheets — if they differ, feed hasn't propagated
4. Check GMC > Feeds > Supplemental feed > Fetch history for error status and last-success timestamp
5. Only after confirming GMC shows the new content, wait 48-72 hours before measuring impact

**Warning signs:**
- Google Sheets shows new title, Google Ads shows old title in product details
- GMC feed fetch history shows errors or "last fetched: 8 days ago"
- Impression data shows no change immediately after content update (should see change within ~72 hours once propagated)

**Phase to address:**
Phase 1 (Diagnosis) — Verify propagation chain before measuring impact

**Confidence:** HIGH — Documented in `/Users/bobby/Documents/GitHub/Allied-FeedOps/docs/architecture/data-pipeline.md` and `/docs/audit/gmc-feed-investigation-2026-02-08.md`

---

### Pitfall 5: Measuring Impact Too Early

**What goes wrong:**
Publish optimized titles for 50 SKUs. Check Google Ads performance data 2 days later. See no statistical improvement. Conclude the optimization didn't work. In reality, Google needs time to: re-crawl/re-index the updated feed, re-evaluate product relevance scores, re-enter auctions with updated signals, and accumulate enough impression/click data for statistical significance. Two days is nearly always insufficient.

**Why it happens:**
Developers used to A/B testing on websites expect near-real-time feedback. Google Shopping works differently — the feed is batch-processed, relevance signals update on Google's schedule (not yours), and Shopping performance data in Google Ads has a built-in ~2-3 day reporting delay.

**How to avoid:**
- Minimum measurement window: 14 days post-propagation-confirmation (not post-publish)
- Preferred window: 28 days for statistical significance at typical Allied Brass impression volumes
- Do not look at absolute day-over-day changes — compare 14-day periods before vs. after
- Use `performance_baselines` and `performance_snapshots` tables to capture pre/post windows correctly
- Filter for `days_since_publish >= 7` before including any snapshot data in impact analysis

**Warning signs:**
- Measuring within 48 hours of publishing
- Comparing single-day before vs. single-day after
- Not accounting for day-of-week seasonality in small windows
- Comparing against baseline period that includes last week (too recent to be pre-optimization)

**Phase to address:**
Phase 2 (Measurement) — Build measurement protocol into fix rollout plan before fixing anything

**Confidence:** HIGH — Corroborated by industry evidence (2-4 week impact window for title changes) and `performance_snapshots` schema design

---

### Pitfall 6: Confusing Query Logic Failures with Data Pipeline Failures

**What goes wrong:**
Investigate why a SKU has no performance data. Assume it's a data sync issue — conclude Shopify/GMC/Google Ads pipeline is broken. Spend days auditing the pipeline, finding nothing wrong. The real issue: the query uses `master_sku`-level offer ID matching, but Google Ads returns data attributed to a different master_sku in the same product family (multi-SKU products share a `product_id`).

**Why it happens:**
This exact failure mode occurred in this codebase (documented in `docs/audit/SUMMARY-2026-02-08.md`): query match rate was 0.3% not because data was missing but because the query was too narrow. The investigator's instinct was to check data freshness and sync status — all healthy — rather than the query logic itself. "Data not found" looks identical to "data not queried correctly."

**How to avoid:**
Before concluding a data pipeline is broken:
1. Verify the data exists at all: check raw Acatalog.csv directly for the variant ID
2. Check if the product is multi-SKU: query variant_index for `product_id` matches across multiple `master_sku` values
3. Try a broader query: use `LIKE 'shopify_us_{product_id}_%'` instead of specific offer IDs
4. If the broader query returns data, the issue is query logic, not pipeline health
5. Only after confirming data truly doesn't exist at the source, investigate pipeline health

**Warning signs:**
- All pipeline components (GMC, Sheets, variant_index) show healthy status but performance data is empty
- Zero performance data for an SKU that has been live in Google Ads for months
- The problem occurs specifically for SKUs that share a product_id with other master SKUs

**Phase to address:**
Phase 1 (Diagnosis) — Apply multi-SKU product_id matching check before any pipeline audit

**Confidence:** HIGH — Root cause documented in `/Users/bobby/Documents/GitHub/Allied-FeedOps/docs/audit/SUMMARY-2026-02-08.md`

---

### Pitfall 7: Breaking Existing Working Workflows When Applying Fixes

**What goes wrong:**
Fix the keyword injection path to use more search query data. The prompt assembly changes make generated content longer. The finish sentence validation (`normalize_and_validate_finish_sentences`) starts rejecting sentences that exceed the validation length threshold. Finish sentence generation starts failing silently. Google/Bing description publishing now omits finish-specific copy. The fix improved headline content quality while breaking a different content layer.

**Why it happens:**
The content generation pipeline has interdependent validation layers. A change to prompt content changes LLM output structure, which can break downstream validators that expect specific formats, lengths, or patterns. The system has at least three distinct validation gates (`normalize_and_validate_finish_sentences`, `validate_candidate_content` in hybrid path, `validateGeneratedContent` in route.ts), each with its own thresholds. Changes that bypass one gate often hit another unexpectedly.

**How to avoid:**
Before applying any fix to generation logic:
1. Run existing test suite: `PYTHONPATH=./src .venv/bin/python -m pytest tests/ -v`
2. Generate test content for 3-5 SKUs and trace through all validation layers manually
3. Check finish sentence output specifically — it's the most likely to break silently
4. For each planned code change, grep for all callers and validators that depend on the changed component
5. After any fix: verify publish → Google Sheets → GMC propagation still works end-to-end for at least one SKU

**Warning signs:**
- Fix passes unit tests but finish sentences are empty in generated content
- `normalize_and_validate_finish_sentences` log shows increased rejections after a change
- Content quality improves for main title/description but variant descriptions regress
- Hybrid path validation starts throwing errors that didn't exist before

**Phase to address:**
Phase 3 (Fix Application) — Run regression checklist before every fix deployment

**Confidence:** HIGH — Validated via `docs/architecture/2026-02-11-content-generation-pipeline-current-state.md` which documents path-specific validation asymmetry

---

### Pitfall 8: Inferring Runtime Prompt Behavior from Code Without Checking the Actual Prompt Hash

**What goes wrong:**
Developer reads `src/feedops/pipeline/prompts.py` and assumes the content they see is what the LLM receives. But prompts.py is a static file. The actual runtime prompt may differ if: (a) PROMPT_CONTRACT_V2 is somehow disabled and Supabase fallback is used, (b) gold standard examples are populated in Supabase and get injected, (c) category guidance from Supabase adds additional context, or (d) the code has been changed but Cloud Run hasn't been redeployed yet (stale container).

**Why it happens:**
Prompt assembly is multi-layered: canonical system prompt from Python code + Supabase data (gold examples, category guidance) + runtime evidence table. Reading any single layer gives an incomplete picture. Most debugging starts from the code layer and never checks what actually ran.

**How to avoid:**
To see what actually executed for a specific generation run:
1. Query `regeneration_history.system_prompt` — this is the truncated prompt that was actually sent
2. Query `regeneration_history.prompt_hash` — compare against `get_system_prompt_hash()` output to confirm canonical prompt was used
3. Query `regeneration_history.user_prompt` — see actual evidence table that was assembled
4. If diagnosing a specific generation, always start with database records, not source code
5. To verify current Cloud Run is running latest code: `gcloud builds list --project=bobbys-project-346400 --limit=3`

**Warning signs:**
- Prompts.py code was updated but Cloud Run still serving old content (check build status)
- Prompt hash in `generated_content.generation_prompt_hash` doesn't match expected hash from local code
- Category guidance in Supabase `prompt_templates` table is outdated and injecting stale context

**Phase to address:**
Phase 1 (Diagnosis) — Query actual execution records before reading source code

**Confidence:** HIGH — `regeneration_history` schema documented in codebase; prompt hash contract verified in `prompt_loader.py`

---

### Pitfall 9: Over-Engineering Diagnostics Instead of Checking Basics First

**What goes wrong:**
Team builds a multi-agent diagnostic pipeline, queries Google Ads API across all campaigns, generates a comprehensive coverage report, and runs correlation analysis between content scores and impression deltas — before checking whether the Google Sheets supplemental feed has a valid scheduled fetch configured in GMC. The answer was "fetch was set to monthly, not daily." Two hours of instrumentation, one lookup in GMC settings.

**Why it happens:**
Engineers gravitate toward tools they know. Building diagnostic infrastructure feels productive. The simple operational checks (feed schedule, approval status in GMC, sheet fetch history) require going into third-party UIs that engineers rarely visit, so they skip them and build instead.

**How to avoid:**
Apply a strict "basics first" checklist before any engineering work:
1. Is the supplemental feed fetch configured and succeeding? (GMC UI)
2. Does GMC show the new title for a specific offer ID you published? (GMC product search)
3. Is the product approved for Shopping ads? (check `destinationStatuses` in GMC)
4. Is the Google Sheet accessible with the correct column mapping? (spot-check 2 rows)
5. Does the Google Ads campaign serving these products still have budget and positive bids?

Only after these five checks pass should diagnostic tooling be built.

**Warning signs:**
- No one has looked at GMC UI in the past 2 weeks
- The feed configuration has never been verified after initial setup
- Diagnostics are built before root cause is even hypothesized

**Phase to address:**
Phase 1 (Diagnosis) — Enforce operational basics checklist as first step

**Confidence:** HIGH — Validated by the documented investigation pattern in this codebase where data pipeline appeared broken but was actually a query logic issue

---

### Pitfall 10: Applying Multiple Fixes Simultaneously, Making Root Cause Unattributable

**What goes wrong:**
Deploy four changes at once: fix offer ID case transformation, improve prompt keyword injection, add search query data to cold-start SKUs, and update the supplemental feed fetch schedule from weekly to daily. Performance improves. Team cannot determine which change drove the improvement, cannot attribute value to each fix, and cannot safely revert a specific change if a regression appears.

**Why it happens:**
Fixing multiple things at once feels efficient. Teams accumulate a list of suspected issues and batch them into a single deployment. The cost — loss of causal attribution — is invisible until you need to isolate a problem.

**How to avoid:**
Apply fixes in staged, independently measurable deployments:
1. Fix one variable at a time with at least 72 hours of measurement between changes
2. Document pre-fix baseline metrics before each deployment (not just the first one)
3. Use the existing `performance_snapshots` infrastructure to capture state at each fix boundary
4. If multiple fixes must ship together (e.g., offer ID case + sheet update), group only changes that affect the same layer

**Warning signs:**
- "We shipped 4 fixes this week" in a context where impact measurement is the goal
- No pre-fix snapshot was taken before applying fixes
- Cannot answer "which fix caused the improvement?"

**Phase to address:**
Phase 3 (Fix Application) — Enforce one fix per measurement window

**Confidence:** HIGH — Industry best practice; corroborated by Google's own guidance on avoiding simultaneous feed changes

---

### Pitfall 11: Keyword Planning Data Not Reaching Generation for Low-Volume SKUs

**What goes wrong:**
For SKUs with fewer than 10 impressions in Google Ads, `search_queries_by_master_sku` returns empty (the view filters for `total_impressions >= 10`). The evidence table builds without any `search_queries_top`, `search_query_themes`, or `keyword_gaps_current_title` rows. Generation proceeds on product catalog data alone. The generated title for a low-impression SKU misses the high-volume search terms customers actually use for that category. The fix — improving prompt quality — doesn't help because the evidence is incomplete.

**Why it happens:**
The evidence assembly code silently continues when search data is absent. There's no warning, no fallback activation log, and no indication in the generated content that it was built without search signal data. The problem is invisible to anyone reviewing the output.

**How to avoid:**
For impact debugging, always check evidence completeness before evaluating content quality:
1. Query `search_queries_by_master_sku` for the target SKU — if empty, content was generated without search signals
2. Check search terms coverage: `SELECT COUNT(DISTINCT master_sku) FROM search_queries` (824/2784 as of v1.2 start)
3. For SKUs with no search data, `keyword_bank.json` provides category-level fallback — verify this file exists in Cloud Run deployment (it may be gitignored and absent)
4. Distinguish between "bad content" (prompt/model quality issue) and "thin evidence" (data coverage issue) before choosing a fix

**Warning signs:**
- Generated titles miss obvious category keywords despite good prompt quality
- Evidence table in `regeneration_history.user_prompt` lacks `search_queries_top` rows
- SKU has low impressions and was generated early in the backfill before search data was collected
- `data/keyword-bank.json` is gitignored and not deployed to Cloud Run

**Phase to address:**
Phase 1 (Diagnosis) — Check evidence completeness per SKU before quality evaluation

**Confidence:** HIGH — Documented in `/docs/audit/signal-audit-2026-02-11/external-signals-assessment.md` and evidence.py code review

---

### Pitfall 12: Performance Baselines Contaminated by Pre-Optimization Content

**What goes wrong:**
A SKU was published with optimized content in November. Performance baselines were captured in January (using the 30-day pre-publish window). The baseline capture query uses `published_at` from `publish_events` to define the pre-period — but if a SKU was published multiple times (e.g., regenerated and re-published), the baseline may use the most recent publish date rather than the first one, comparing against a post-optimization baseline. The "improvement" calculation shows neutral because both baseline and snapshot reflect optimized content.

**Why it happens:**
`performance_baselines` captures a 30-day pre-period anchored to `published_at`. If a SKU was published, then regenerated and re-published, the baseline anchor shifts to the re-publish date. The 30-day pre-period now falls inside the original optimization period. This makes before/after comparison meaningless.

**How to avoid:**
1. Check `publish_events` count for each SKU being measured — if > 1, the baseline may be anchored to a re-publish
2. For multi-publish SKUs, use the earliest `published_at` date as baseline anchor, not the latest
3. Visually validate baseline CTR against Google Ads historical data in the UI for a few SKUs before trusting any aggregate impact numbers
4. The `performance_snapshots` table captures `days_since_publish` — ensure this is calculated from the *first* publish, not the most recent

**Warning signs:**
- Baseline and snapshot CTR are nearly identical despite a content change
- `publish_events` shows 2+ entries for the same SKU within 90 days
- Baseline period's CTR looks "too high" for unoptimized content (because it was already optimized)

**Phase to address:**
Phase 2 (Measurement) — Audit baseline integrity before computing impact scores

**Confidence:** HIGH — Grounded in `performance_baselines` and `publish_events` schema understanding

---

## Technical Debt Patterns

| Shortcut | Immediate Benefit | Long-term Cost | When Acceptable |
|----------|-------------------|----------------|-----------------|
| Measure impact before verifying propagation | Faster feedback loop | False negatives — conclude fix didn't work when feed hasn't propagated | Never |
| Apply multiple fixes at once | Faster shipping | Cannot attribute improvement or isolate regression | Only if fixes are in completely independent layers |
| Skip evidence completeness check | Simpler debugging | Optimize content built on thin data | Only if catalog-wide search data is confirmed populated |
| Read source code to understand runtime behavior | Faster than querying DB | May read dead code or stale code | Only after confirming the code path is live |
| Trust batch job "success" without checking row counts | Less monitoring overhead | Silent coverage gaps | Never — always validate with coverage counts |
| Infer GMC sync status from Sheets update timestamp | Avoids GMC UI login | Feed may not have been fetched | Never for impact diagnosis |

---

## Integration Gotchas

| Integration | Common Mistake | Correct Approach |
|-------------|----------------|------------------|
| GMC Supplemental Feed | Assume Sheets update = GMC update | Verify in GMC UI that title matches Sheets value for a specific offer ID |
| GMC Supplemental Feed | Assume daily refresh by default | Check fetch schedule in GMC — may be weekly or monthly |
| Google Ads reporting | Measure impact immediately after publish | Wait 14-28 days post-propagation-confirmation; ads reporting has 2-3 day delay |
| Google Ads + multi-SKU | Match performance data by master_sku offer IDs | Match by `product_id` extracted from offer ID to capture all family variants |
| Cloud Run feature flags | Absent env var = flag disabled | For this codebase, absent env var uses the `default` parameter (often `True`) |
| Python Cloud Run | Read TypeScript files to understand generation | Python `prompts.py` and `main.py` are canonical; TypeScript `core.ts` is dead code |
| `regeneration_history` | Read source code for prompt content | Query `regeneration_history.user_prompt` to see what actually ran |
| Offer ID case | Store/query with lowercase | GMC requires uppercase `shopify_US_`; Sheets write must transform |
| `search_queries_by_master_sku` | Assume all SKUs have search data | 824/2784 SKUs covered as of v1.2; check per-SKU before evaluating content quality |

---

## Performance Traps

| Trap | Symptoms | Prevention | When It Breaks |
|------|----------|------------|----------------|
| Measuring on too-small a window | Single-day CTR variance swamps signal | Minimum 14-day window, prefer 28 days | < 14 days always |
| Measuring without seasonality control | Week-over-week swings look like optimization impact | Compare same weekdays; compare 4-week vs 4-week periods | Any holiday/seasonal product category |
| Including unpropagated SKUs in impact measurement | Dilutes true signal — half your "optimized" SKUs still show old content | Filter `days_since_publish >= 7` before including snapshot data | Immediately |
| Using campaign-level metrics to measure SKU-level impact | Campaign metric movement may be driven by unrelated SKUs | Measure at SKU level using `shopping_performance_view` with product filter | Any analysis |

---

## "Looks Done But Isn't" Checklist

- [ ] **Content published to Sheets:** Often this is where verification stops — also verify GMC shows new title for a specific offer ID
- [ ] **Feature flags "on":** Often inferred from flag name presence — verify by checking default behavior and absence of "disabled" log line
- [ ] **Generation pipeline wired:** TypeScript `core.ts` looks live — verify by tracing from UI entry point through actual HTTP calls
- [ ] **Impact measured:** Publishing happened — verify propagation chain (Sheets → GMC fetch → GMC approval → Ads serving) before measuring
- [ ] **Search data wired into generation:** Evidence table is assembled — verify search rows are actually present in `regeneration_history.user_prompt` for target SKUs
- [ ] **Baseline captures pre-optimization period:** Baseline exists — verify baseline `created_at` is before `publish_events.published_at` and no re-publish has shifted the anchor
- [ ] **Fix isolated:** Improvement observed — verify only one variable changed per measurement window

---

## Recovery Strategies

| Pitfall | Recovery Cost | Recovery Steps |
|---------|---------------|----------------|
| Wrong layer optimized (quality vs coverage) | MEDIUM | Count actual published SKUs; pivot work to increase publishing coverage |
| Feature flag assumed off when default-on | LOW | Re-read feature_flags.py; confirm flag state from Cloud Run logs |
| Time lost on dead code | LOW | Grep for `core.ts` imports to confirm dead; pivot to Python source |
| Feed never propagated to GMC | LOW | Check GMC supplemental feed fetch history; manually trigger fetch; verify title in GMC |
| Measured too early | MEDIUM | Discard early measurement; re-baseline; wait full 14-28 day window |
| Multi-SKU query logic failure | MEDIUM | Switch to product_id-based matching; re-run data collection |
| Regression from simultaneous fixes | HIGH | Revert all changes; re-apply one at a time with measurement windows |
| Evidence thin for low-volume SKUs | MEDIUM | Run search term backfill first; confirm keyword bank present in Cloud Run; re-generate after data populated |
| Contaminated baselines | MEDIUM | Identify re-published SKUs; use earliest publish date for anchor; re-compute impact scores |

---

## Pitfall-to-Phase Mapping

| Pitfall | Prevention Phase | Verification |
|---------|------------------|--------------|
| Coverage vs quality confusion | Phase 1: Diagnosis | Published SKU count > 10% of catalog before quality work begins |
| Feature flag observability | Phase 1: Diagnosis | Log active flag state on startup; document default behavior |
| Dead code path confusion | Phase 1: Diagnosis | Execution path traced from UI through HTTP to Python before any source reading |
| Feed propagation not verified | Phase 1: Diagnosis | GMC product search confirms new title before measurement window opens |
| Measuring too early | Phase 2: Measurement | Measurement protocol enforces 14-day minimum window |
| Query logic vs pipeline failure | Phase 1: Diagnosis | Multi-SKU product_id matching check before any pipeline audit |
| Regression from fix | Phase 3: Fix Application | Regression checklist run before each deployment; tests pass |
| Runtime prompt vs source code | Phase 1: Diagnosis | `regeneration_history` queried before source code examined |
| Over-engineered diagnostics | Phase 1: Diagnosis | Operational basics checklist completed before any tooling built |
| Multi-fix attribution loss | Phase 3: Fix Application | One fix per measurement window enforced |
| Thin evidence for cold-start SKUs | Phase 1: Diagnosis | Evidence completeness check per SKU before content quality evaluation |
| Contaminated baselines | Phase 2: Measurement | Baseline integrity audit for re-published SKUs |

---

## Sources

**Project investigation history:**
- `/Users/bobby/Documents/GitHub/Allied-FeedOps/docs/audit/SUMMARY-2026-02-08.md` — Documented query logic vs pipeline failure example
- `/Users/bobby/Documents/GitHub/Allied-FeedOps/docs/audit/gmc-feed-investigation-2026-02-08.md` — GMC feed propagation verification pattern
- `/Users/bobby/Documents/GitHub/Allied-FeedOps/docs/audit/signal-audit-2026-02-11/prompt-wiring-map.md` — Dead code identification (core.ts), runtime path verification
- `/Users/bobby/Documents/GitHub/Allied-FeedOps/docs/audit/signal-audit-2026-02-11/external-signals-assessment.md` — Evidence completeness for low-volume SKUs, search data coverage gaps

**Codebase verification:**
- `/Users/bobby/Documents/GitHub/Allied-FeedOps/src/feedops/pipeline/feature_flags.py` — Default-True flag pattern
- `/Users/bobby/Documents/GitHub/Allied-FeedOps/src/feedops/api/prompt_loader.py` — Multi-layer prompt assembly
- `/Users/bobby/Documents/GitHub/Allied-FeedOps/src/feedops/api/runtime_controls.py` — Kill switches
- `/Users/bobby/Documents/GitHub/Allied-FeedOps/docs/architecture/2026-02-11-content-generation-pipeline-current-state.md` — Validation layer asymmetry
- `/Users/bobby/Documents/GitHub/Allied-FeedOps/docs/architecture/data-pipeline.md` — Propagation chain documentation

**External references:**
- [Google Shopping feed optimization impact timelines](https://www.storegrowers.com/product-title-optimization/) — 2-4 week measurement window
- [GMC supplemental feed sync behavior](https://www.jumpfly.com/blog/setting-up-supplemental-feeds-in-google-merchant-center-next-part-2-of-3/) — Daily fetch schedule, manual trigger
- [Avoiding simultaneous changes in feed testing](https://blog.adnabu.com/google-shopping-feed/google-shopping-feed-optimization/) — One variable at a time principle

---
*Pitfalls research for: Allied FeedOps v1.2 — Impact Debug & Fix milestone*
*Researched: 2026-02-20*
