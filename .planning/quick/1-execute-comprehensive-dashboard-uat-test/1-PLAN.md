---
phase: quick
plan: 01
type: execute
wave: 1
depends_on: []
files_modified:
  - docs/uat/dashboard-comprehensive-uat.md
autonomous: false
requirements: []
must_haves:
  truths:
    - "All 17 UAT test cases executed with PASS/FAIL recorded"
    - "Performance page fix (PR #61) verified working in production"
    - "Known bugs A and B confirmed with evidence for future fix"
    - "UAT doc updated with results and committed"
  artifacts:
    - path: "docs/uat/dashboard-comprehensive-uat.md"
      provides: "UAT results with PASS/FAIL evidence"
  key_links: []
---

<objective>
Execute the comprehensive dashboard UAT test plan against production (https://allied-feed-ops.vercel.app) using agent-browser for UI verification and Supabase MCP for database cross-referencing.

Purpose: Verify the performance page fix from PR #61 works, confirm known bugs A/B with evidence, and regression-test core dashboard flows.
Output: Updated UAT doc with PASS/FAIL results and evidence for all test cases.
</objective>

<execution_context>
@/Users/bobby/.claude/get-shit-done/workflows/execute-plan.md
@/Users/bobby/.claude/get-shit-done/templates/summary.md
</execution_context>

<context>
@docs/uat/dashboard-comprehensive-uat.md
@CLAUDE.md
</context>

<tasks>

<task type="auto">
  <name>Task 1: Login + Priority Tests D1-D3, A1-A2, B1-B2</name>
  <files>docs/uat/dashboard-comprehensive-uat.md</files>
  <action>
Execute UAT tests in priority order using agent-browser and Supabase MCP.

**Login (F1):**
1. `agent-browser open https://allied-feed-ops.vercel.app/login`
2. `agent-browser snapshot -i` to get form refs
3. Fill email `bobby.andris@avondaledecor.com`, fill password `bobby123`, click Sign In
4. Verify redirect to dashboard overview. Record PASS/FAIL.

**D1-D3 (Performance Page — verify PR #61 fix):**
1. `agent-browser open https://allied-feed-ops.vercel.app/performance`
2. Snapshot and verify:
   - D1: Baselines show real numbers (WP-2TB/16-GAL ~990/day, CL-55 ~731/day). If page shows different SKUs, note actual values — non-zero is PASS.
   - D3: Summary cards at top show non-zero impressions, clicks, CTR.
3. For D2: Check snapshot dates are recent and days_since_publish is reasonable.
4. Cross-reference with Supabase: `SELECT master_sku, avg_daily_impressions, avg_daily_clicks FROM performance_baselines WHERE avg_daily_impressions > 0 ORDER BY avg_daily_impressions DESC LIMIT 5` (project_id: qezuszwufortkiutlhym)

**A1-A2 (Generate Tab — document known bug):**
1. `agent-browser open https://allied-feed-ops.vercel.app/generate`
2. Snapshot the recommended SKU list. Note several SKU names.
3. Query Supabase: `SELECT DISTINCT master_sku FROM generated_content` — check for overlap with recommended list.
4. A1: If overlap exists, record FAIL with specific overlapping SKUs.
5. Query: `SELECT COUNT(DISTINCT master_sku) FROM generated_content` — compare with excluded count shown in UI.
6. A2: If UI excluded count is ~130 but query returns ~191, record FAIL with both numbers.

**B1-B2 (Publishing variant mismatch — document known bug):**
1. Query Supabase: `SELECT COUNT(*), COUNT(DISTINCT finish) FROM variant_index WHERE master_sku = '7272D/30'`
2. B1: Record actual variant count.
3. Query: `SELECT master_sku, platform, jsonb_object_keys((finish_sentences#>>'{}')::jsonb) as finish FROM variant_finish_sentences WHERE master_sku = '7272D/30' AND platform = 'google'`
4. B2: Compare finish sentence count vs actual variant count. Record PASS if match, FAIL if mismatch.

Record all results as notes — do NOT update the doc yet (Task 2 does that).
  </action>
  <verify>
    <automated>echo "Task 1 is manual UAT — verify agent-browser session completed and results noted"</automated>
  </verify>
  <done>F1, D1-D3, A1-A2, B1-B2 all executed with PASS/FAIL recorded</done>
</task>

<task type="auto">
  <name>Task 2: Remaining Tests C1-C3, F2-F4, B3-B4 + Update UAT Doc</name>
  <files>docs/uat/dashboard-comprehensive-uat.md</files>
  <action>
Continue UAT execution with remaining tests.

**C1-C3 (Review Page regression):**
1. `agent-browser open https://allied-feed-ops.vercel.app/review/CL-55`
2. C1: Check performance section shows baseline data. Cross-reference: baselines should show impressions ~731/day.
3. C2: Click Bing tab, verify URL has `?platform=bing`. Refresh page. Verify Bing tab still selected. Record PASS/FAIL.
4. `agent-browser open https://allied-feed-ops.vercel.app/review/920D-6`
5. C3: Verify Google title contains `{FINISH_NAME}`, description contains `{FINISH_SENTENCE}`. Record PASS/FAIL.

**B3-B4 (Publishing from review page):**
1. `agent-browser open https://allied-feed-ops.vercel.app/review/7272D-30`
2. B3: Look for publish button or validation status. Note whether publish is available and what validation messages appear.
3. B4: Check for red/yellow validation warnings about variant count. Record what validation says.
4. Do NOT actually execute a publish — just document the validation state.

**F2-F4 (Navigation smoke test):**
1. Click through sidebar: Overview, Review, Generate, Performance, Batches, Search Insights, Settings
2. F2: Each page loads without error. Record PASS/FAIL per page.
3. F3: On Review page, search for "920D-6". Verify it appears and clicking navigates to detail.
4. F4: Note any visible errors in page rendering (we cannot check browser console via agent-browser, so check for error UI states).

**H1 (Pipeline health — quick check):**
Run via bash: `curl -s https://feedops-pipeline-3b43yg32oa-ue.a.run.app/health`
Record PASS if 200 with JSON.

**Update UAT doc:**
After all tests complete, update `docs/uat/dashboard-comprehensive-uat.md` by adding a Results section at the bottom with:
- Date of test run
- PASS/FAIL for each test case (F1, D1-D3, A1-A2, B1-B4, C1-C3, F2-F4, H1)
- Evidence notes (actual numbers seen, screenshots described, specific SKUs checked)
- Summary of bugs confirmed vs fixes verified

Format:
```markdown
## Results — 2026-03-04

| Test | Result | Evidence |
|------|--------|----------|
| F1   | PASS/FAIL | [notes] |
| D1   | PASS/FAIL | [notes] |
...
```
  </action>
  <verify>
    <automated>grep -c "PASS\|FAIL" docs/uat/dashboard-comprehensive-uat.md</automated>
  </verify>
  <done>All priority tests executed, UAT doc updated with results table showing PASS/FAIL for each test case</done>
</task>

<task type="checkpoint:human-verify" gate="blocking">
  <what-built>Comprehensive UAT test execution against production dashboard. All priority tests (D1-D3, A1-A2, B1-B4, C1-C3, F1-F4, H1) executed with results recorded in the UAT doc.</what-built>
  <how-to-verify>
    1. Review the updated UAT doc at docs/uat/dashboard-comprehensive-uat.md
    2. Check the Results table — does each PASS/FAIL match your expectations?
    3. Confirm Performance fix (D tests) is verified working
    4. Confirm known bugs A and B are documented with evidence
    5. Flag any tests you want re-run or results you disagree with
  </how-to-verify>
  <resume-signal>Type "approved" to commit results, or describe any issues to investigate</resume-signal>
</task>

</tasks>

<verification>
- UAT doc contains a Results section with PASS/FAIL for each test case
- Performance page fix from PR #61 verified (D1-D3 results)
- Known bugs A and B confirmed with specific evidence
- No tests left unexecuted from priority list
</verification>

<success_criteria>
- All 13+ priority test cases (F1, D1-D3, A1-A2, B1-B4, C1-C3, F2-F4, H1) have PASS/FAIL recorded
- UAT doc committed with results
- Clear evidence trail for any bugs found
</success_criteria>

<output>
After completion, commit updated docs/uat/dashboard-comprehensive-uat.md with test results.
</output>
