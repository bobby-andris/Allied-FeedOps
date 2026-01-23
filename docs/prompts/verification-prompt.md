# Task: Verify FeedOps MVP Implementation

## Required Skill

**FIRST**: Read the verification-before-completion skill at:
`/Users/bobby/.cursor/projects/Users-bobby-Documents-GitHub-Allied-FeedOps/skills/superpowers/skills/verification-before-completion/SKILL.md`

Announce: "I'm using the verification-before-completion skill to verify the FeedOps implementation."

## Context

The FeedOps MVP has been implemented following the plan at:
`.cursor/plans/feedops_mvp_implementation_f7d9387f.plan.md`

Your job is to verify the implementation works correctly by running tests, healthchecks, and dry-runs, then reviewing the code quality and output quality.

## Verification Steps

### Step 1: Environment Check

Verify the project is set up correctly. Install the package in dev mode and check that all required env vars exist (names only, never print values).

Expected env vars: OPENAI_API_KEY, GEMINI_API_KEY, SHOPIFY_STORE_URL, SHOPIFY_ACCESS_TOKEN, GMC_MERCHANT_ID, GMC_API_KEY

### Step 2: Run Test Suite

Run pytest with verbose output and short tracebacks. Document total tests run, pass/fail count, and any failures with error messages.

### Step 3: Run Healthcheck

Run the feedops healthcheck command. Document which checks passed, which failed, and the healthcheck report location.

### Step 4: Dry-Run with Sample Data

Run feedops optimize with parent-sku SAMPLE-101 in dry-run mode. Check that outputs exist at reports/sku-SAMPLE-101.md and:
- exports/google-patch-SAMPLE-101.json
- exports/bing-patch-SAMPLE-101.json
- exports/shopify-patch-SAMPLE-101.json
Review the report content for quality.

### Step 5: Dry-Run with Real Data (3 SKUs)

Test with real SKUs from the catalog:
- SKU 101 (Cabinet Hardware)
- SKU 1031/18 (Towel Bar)
- One Grab Bar SKU (find with list-skus command)

For each, review: Does the report generate without errors? Is the JSON patch preview valid? Are all claims traced to source fields? Is the quality score at least 80%?

### Step 6: Output Quality Review

For one of the real SKU reports, manually verify:

Title Quality: Must be 150 chars or less, brand in first 70 chars, product type in first 70 chars, key dimension included, no promotional text or ALL CAPS.

Description Quality: Must be 500 chars or more, benefit-first opening in first 150 chars, bullet points present, all claims specific and verifiable.

Claim Verification: Every claim has a source_field, source_value matches actual CSV data, no hallucinated facts.

JSON Patch Preview: Valid JSON structure, contains title and description, contains item identifiers.

### Step 7: Code Review

Review key files for quality:
- src/feedops/models/ - Are Pydantic models well-structured?
- src/feedops/providers/llm/ - Is retry/repair logic implemented?
- src/feedops/pipeline/verifier.py - Does claim verification work?
- src/feedops/cli/ - Are CLI commands properly implemented?

Check for: No hardcoded secrets, proper error handling, logging without exposing sensitive data, type hints present.

## Deliverable

Create a verification report at reports/verification-report.md containing:

1. Test Results Summary: Total tests, passed, failed with details
2. Healthcheck Results: Each check marked PASS or FAIL
3. Dry-Run Results: Sample SKU and 3 real SKUs with quality scores
4. Output Quality Assessment: Title quality, description quality, claim verification, overall PASS or FAIL
5. Code Quality Assessment: Models, providers, pipeline, CLI each marked PASS or FAIL
6. Issues Found: Lists of critical, important, and minor issues
7. Verdict: Either READY FOR USE or NEEDS FIXES

## If Issues Are Found

For each issue found: Describe the problem, show the error or incorrect output, identify the likely cause, and propose a fix. Do not implement fixes unless explicitly asked.

## Success Criteria

Verification is complete when:
- All tests pass or failures are documented
- Healthcheck passes or failures are documented
- At least 3 dry-runs complete successfully
- Output quality meets the rubric with 80% or higher score
- Verification report is saved to reports/verification-report.md
- Clear verdict is provided
