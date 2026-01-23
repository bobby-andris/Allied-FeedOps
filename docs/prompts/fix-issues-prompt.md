# Task: Fix Verification Issues and Re-Verify

Based on the verification report at `reports/verification-report.md`, fix the 3 identified issues, then re-run verification to confirm.

## Issue 1: Evidence Naming Inconsistency (Medium Severity)

**Problem:** Evidence table uses `catalog_csv.Material` as source field name, but the verifier looks for `material` as the attribute name on ParentSKU. This causes false claim rejections.

**Location:** `src/feedops/pipeline/evidence.py` (around line 61-62)

**Fix:** Update the evidence table builder to use the actual ParentSKU attribute names without the `catalog_csv.` prefix. The source field should match what the verifier expects.

**After fixing:** The claim verification should work correctly and not show "Field 'catalog_csv.Material' not found in source data" errors.

## Issue 2: CLI Does Not Auto-Load .env (Low Severity)

**Problem:** Running `feedops healthcheck` directly fails to find API keys because the CLI doesn't load environment variables from `.env`.

**Location:** `src/feedops/cli/main.py`

**Fix:** Add dotenv loading at the top of main.py:

```python
from dotenv import load_dotenv
load_dotenv()
```

This should be called before any other imports that depend on environment variables.

**After fixing:** Users can run `feedops healthcheck` without manually exporting environment variables.

## Issue 3: Deprecated google.generativeai Package (Low Severity)

**Problem:** The `google.generativeai` package shows deprecation warnings and will eventually stop working.

**Fix:** This is lower priority. For now, just note it. If time permits, migrate from `google.generativeai` to `google.genai` in the Gemini provider.

## Verification Steps After Fixes

After applying fixes for Issue 1 and Issue 2:

1. Run the test suite to ensure nothing broke:
   ```bash
   pytest tests/ -v --tb=short
   ```

2. Run healthcheck without manually exporting env vars:
   ```bash
   feedops healthcheck
   ```

3. Re-run dry-run on sample data to verify claim verification works:
   ```bash
   feedops optimize --parent-sku SAMPLE-101 --dry-run
   ```
   
   Check that the quality score is now higher (should be 80%+ if claims verify correctly).

4. Re-run on one real SKU to confirm:
   ```bash
   feedops optimize --parent-sku 101 --dry-run
   ```

## Expected Outcomes

After fixes:
- All tests still pass (48/48)
- Healthcheck works without manual env export
- SAMPLE-101 quality score improves from 75% to 85%+
- All claims verify correctly (no false rejections)

## Deliverable

Update the verification report at `reports/verification-report.md` with:
1. Issues fixed (which ones, how)
2. New test results
3. New dry-run results showing improved scores
4. Updated verdict

Commit the fixes with message: `fix: resolve evidence naming and CLI dotenv issues`
