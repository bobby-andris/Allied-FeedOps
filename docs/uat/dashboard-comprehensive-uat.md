# Dashboard Comprehensive UAT

**Created:** 2026-03-04
**Purpose:** End-to-end user acceptance testing via agent-browser
**Usage:** Run with `/gsd:quick` — each section is an independent test

---

## Pre-Requisites

- Dashboard running at `https://allied-feed-ops.vercel.app` (production) or `http://localhost:3001` (dev)
- Login: `bobby.andris@avondaledecor.com` / `bobby123`
- Cloud Run pipeline deployed and healthy
- Supabase accessible

---

## A. Generate Tab — SKU Selection (KNOWN BUGS)

**Context:** The Generate tab recommends SKUs for content generation. Currently it recommends SKUs that already have generated content. It should ONLY recommend SKUs with NO rows in `generated_content` table.

**Root cause:** `dashboard/src/app/api/sku-selection/route.ts` lines 29-36 only checks `approved_content IS NOT NULL` (130 SKUs). But 189 SKUs have `candidate_content` without approval — these still appear as recommendations. The filter should exclude ANY SKU with a row in `generated_content`.

### A1. Verify recommendations exclude already-generated SKUs
1. Navigate to `/generate`
2. Wait for SKU recommendations to load
3. Note the recommended SKU list
4. Cross-reference: query `SELECT DISTINCT master_sku FROM generated_content` via Supabase
5. **PASS:** Zero overlap between recommended SKUs and SKUs in `generated_content`
6. **FAIL:** Any recommended SKU has a row in `generated_content` (even candidate-only)

### A2. Verify excluded count is accurate
1. On the Generate page, check the "already optimized" excluded count
2. Query: `SELECT COUNT(DISTINCT master_sku) FROM generated_content` (should be ~191)
3. **PASS:** Excluded count matches or exceeds the query result
4. **FAIL:** Excluded count only shows ~130 (only counting approved, not all generated)

### A3. Verify variant_count displayed matches reality
1. Pick any recommended SKU from the list
2. Note the variant count shown in the UI
3. Query: `SELECT COUNT(*) FROM variant_index WHERE master_sku = '[SKU]'`
4. **PASS:** Numbers match
5. **FAIL:** UI shows 28 for a SKU that actually has 25 or 19

### A4. Post-generation exclusion
1. Select a never-generated SKU and trigger generation
2. Wait for generation to complete
3. Refresh the Generate page
4. **PASS:** The just-generated SKU no longer appears in recommendations
5. **FAIL:** SKU still shows up

---

## B. Publishing — Variant Count Mismatch (KNOWN BUGS)

**Context:** 42% of SKUs (1,159 of 2,784) have fewer than 28 variants. The pipeline generates finish sentences for all 28 standard finishes, but publishing fails when the finish sentence count doesn't match the actual variant count.

**Root cause:** `dashboard/src/lib/publishing/expand-variants.ts` line 230 throws `finish_sentences_incomplete` when `Object.keys(finishSentences).length !== uniqueFinishes`. A SKU with 25 variants but 28 finish sentences (or vice versa) triggers this error.

**Test SKU:** `7272D/30` (use this specific SKU for all B tests)

### B1. Check variant count for test SKU
1. Query: `SELECT COUNT(*), COUNT(DISTINCT finish) FROM variant_index WHERE master_sku = '7272D/30'`
2. Document the actual variant count (expected: not 28)

### B2. Check finish sentence coverage
1. Query: `SELECT master_sku, platform, jsonb_object_keys((finish_sentences#>>'{}')::jsonb) FROM variant_finish_sentences WHERE master_sku = '7272D/30' AND platform = 'google'`
2. Compare finish sentence count against actual variant count from B1
3. **PASS:** Counts match (finish sentences generated only for actual finishes)
4. **FAIL:** Finish sentences generated for 28 finishes but SKU has fewer variants

### B3. Attempt publish via Review page
1. Navigate to `/review/7272D-30` (note: slashes become hyphens in URL)
2. Verify content exists (title + description for Google)
3. If approved, attempt publish to Google
4. **PASS:** Publish succeeds OR gives clear actionable error about finish sentence mismatch with specific missing/extra finishes listed
5. **FAIL:** Generic error, silent failure, or crash

### B4. Validate content validation endpoint
1. Check the publish validation for this SKU via the review page UI
2. Look for any red/yellow validation warnings
3. **PASS:** Validation correctly identifies variant count issues before publish attempt
4. **FAIL:** Validation shows green/ready but publish then fails

---

## C. Review Page (Regression Testing)

### C1. Performance baselines show real data
1. Navigate to `/review/CL-55`
2. Check the performance section
3. **PASS:** Baseline impressions show ~731/day (known value from master baselines)
4. **FAIL:** Shows 0 or missing baselines

### C2. Platform tab persistence
1. On any review page, click the "Bing" platform tab
2. Note the URL changes to include `?platform=bing`
3. Refresh the page
4. **PASS:** Bing tab is still selected after refresh
5. **FAIL:** Defaults back to Google

### C3. Content display
1. Navigate to `/review/920D-6`
2. Verify Google title and description are displayed
3. Verify content contains `{FINISH_NAME}` placeholder in title
4. Verify content contains `{FINISH_SENTENCE}` placeholder in description
5. **PASS:** All content renders correctly with placeholders visible
6. **FAIL:** Missing content, broken rendering, or placeholders expanded

---

## D. Performance Page (Our Fix — Hybrid Fallback)

### D1. Baselines show real numbers
1. Navigate to `/performance`
2. Look at the baseline impressions column for published SKUs
3. **PASS:** SKUs like WP-2TB/16-GAL show ~990/day, CL-55 shows ~731/day
4. **FAIL:** All zeros or dramatically wrong numbers

### D2. Snapshot data is current
1. Check that snapshot data shows dates from Mar 4 or later
2. Verify "days since publish" is reasonable (not negative, not 999)
3. **PASS:** Recent snapshot dates, reasonable day counts
4. **FAIL:** Old or missing snapshot data

### D3. Summary stats are non-zero
1. Check the summary cards at top of performance page
2. **PASS:** Total impressions, total clicks are non-zero; avg CTR change is a real percentage
3. **FAIL:** All summary stats are 0

---

## E. Batch Publishing

### E1. Create and execute a batch
1. Navigate to `/batches`
2. Check if any batches exist
3. If a batch can be created, create one with 1-2 approved SKUs (28-variant SKUs only to avoid Bug B)
4. Execute the batch
5. **PASS:** Batch status transitions: pending → executing → published
6. **FAIL:** Batch gets stuck on "executing" (known issue — status update may timeout)

### E2. Verify Google Sheets rows
1. After a successful batch publish, check the Google Sheet
2. Verify rows were updated (not duplicated) for the published SKUs
3. Check offer ID format is uppercase `shopify_US_` (not lowercase)
4. **PASS:** Correct rows updated, correct format
5. **FAIL:** Duplicate rows, wrong case, or missing updates

---

## F. General Dashboard Health

### F1. Login flow
1. Navigate to login page
2. Enter credentials and sign in
3. **PASS:** Redirected to dashboard overview
4. **FAIL:** Login error, stuck on login page, or redirect loop

### F2. Navigation smoke test
1. Click through each sidebar nav item:
   - Overview, Review, Generate, Performance, Batches, Search Insights, Settings
2. **PASS:** Each page loads without errors, shows relevant content or empty state
3. **FAIL:** Any page crashes, shows 500 error, or fails to load

### F3. SKU search
1. On the Review page, use the search/filter to find "920D-6"
2. **PASS:** SKU appears in results, clicking navigates to review detail
3. **FAIL:** Search returns no results or wrong results

### F4. Console errors
1. Open browser console before navigating
2. Visit Overview, Review (list + detail), Generate, Performance
3. **PASS:** No JavaScript errors in console (warnings OK)
4. **FAIL:** Unhandled exceptions or API errors in console

---

## G. Search Insights Page

### G1. Data loads
1. Navigate to `/search-insights`
2. Verify search term data populates
3. **PASS:** Table shows search terms with impressions/clicks/CTR
4. **FAIL:** Empty table or loading spinner forever

### G2. SKU filter
1. Enter a specific SKU in the filter (e.g., "CL-55")
2. **PASS:** Results filter to show only search terms for that SKU
3. **FAIL:** Filter doesn't work or shows all results

---

## H. Pipeline Health

### H1. Cloud Run health check
1. `curl -s https://feedops-pipeline-3b43yg32oa-ue.a.run.app/health`
2. **PASS:** Returns 200 with JSON including Supabase status
3. **FAIL:** Timeout, 500, or missing Supabase connection

### H2. Regeneration endpoint
1. On a review page, trigger a regeneration for a single field (e.g., Google title)
2. **PASS:** New content generates within ~60 seconds, appears as candidate
3. **FAIL:** Timeout, error, or no content returned

---

## Priority Order for Testing

1. **D1-D3** — Verify our performance fix works (just deployed)
2. **A1-A2** — Confirm Generate tab bug (document current behavior for fix)
3. **B1-B4** — Confirm publishing variant count bug with 7272D/30
4. **C1-C3** — Review page regression check
5. **F1-F4** — General health
6. **E1-E2** — Batch publishing (if time permits)
7. **G1-G2, H1-H2** — Lower priority

---

## Bug Fix Tracking

| Bug | Status | Root Cause File | Fix Description |
|-----|--------|----------------|-----------------|
| A: Generate recommends already-generated | OPEN | `dashboard/src/app/api/sku-selection/route.ts:29-36` | Change filter from `approved_content IS NOT NULL` to `ANY row exists in generated_content` |
| B: Variant count publish failure | OPEN | `dashboard/src/lib/publishing/expand-variants.ts:230` + pipeline `prompts.py` | Pipeline must generate finish sentences for actual variant count, not hardcoded 28 |
| D: Performance all-or-nothing fallback | FIXED (PR #61) | `dashboard/src/app/api/performance/route.ts` | Per-SKU hybrid: variant if non-zero, else master |
