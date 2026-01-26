# FeedOps Testing Guide

This guide explains how to test the FeedOps optimization system with real product SKUs, interpret the output, and make adjustments when needed.

## Prerequisites

Before testing, ensure:

1. **Environment is set up**

   ```bash
   # Install the package
   uv pip install -e ".[dev]"

   # Verify .env file exists with required keys
   ls -la .env
   ```

2. **Required environment variables** (in `.env` file):
   - `OPENAI_API_KEY` - OpenAI API key (primary LLM)
   - `GEMINI_API_KEY` - Google Gemini API key (fallback)

3. **Catalog file exists**
   - Default location: `data/catalog/Product Catalog.csv`
   - Or specify with `--catalog` flag

## Running a Quick Health Check

Before testing, verify everything is configured:

```bash
PYTHONPATH=./src .venv/bin/python -m feedops.cli.main healthcheck
```

Expected output:

```
FeedOps Health Check

✓ Catalog: data/catalog/Product Catalog.csv
✓ OpenAI API key configured
✓ Gemini API key configured
✓ Directory: dashboard_data/lifestyle-eval-candidate/reports/
✓ Directory: dashboard_data/lifestyle-eval-candidate/

All critical checks passed!
```

## Finding SKUs to Test

### List Available SKUs

```bash
PYTHONPATH=./src .venv/bin/python -m feedops.cli.main list-skus --limit 20
```

This shows MasterSKU values from your catalog. Each MasterSKU represents a parent product with one or more variant SKUs (different finishes, sizes, etc.).

### Understanding SKU Structure

- **MasterSKU**: Parent product identifier (e.g., `101`, `1031/18`, `P-700-16-GB`)
- **Variant SKUs**: Individual items with specific finishes (e.g., `101-PC` for Polished Chrome)
- The optimizer works at the **MasterSKU level** and generates content applicable to all variants

## Testing with a Real SKU

### Basic Dry-Run

```bash
PYTHONPATH=./src .venv/bin/python -m feedops.cli.main optimize \
  --parent-sku "101" \
  --dry-run
```

This generates:

1. **Report**: `dashboard_data/lifestyle-eval-candidate/reports/sku-101-YYYYMMDD-HHMMSS.md`
2. **Patch previews**:
   - `dashboard_data/lifestyle-eval-candidate/google-patch-101.json`
   - `dashboard_data/lifestyle-eval-candidate/bing-patch-101.json`
   - `dashboard_data/lifestyle-eval-candidate/shopify-patch-101.json`

### Testing with Sample Data

For safe testing without using real data:

```bash
PYTHONPATH=./src .venv/bin/python -m feedops.cli.main optimize \
  --parent-sku "SAMPLE-101" \
  --catalog samples/sample-catalog.csv \
  --dry-run
```

### Testing Multiple SKUs

For batch testing, use Python directly:

```python
from dotenv import load_dotenv
load_dotenv()

import asyncio
from feedops.pipeline.optimize import optimize_parent_sku

async def test_skus():
    skus = ['101', '1031/18', 'P-700-16-GB']

    for sku in skus:
        result = await optimize_parent_sku(
            master_sku=sku,
            catalog_path='data/catalog/Product Catalog.csv',
            dry_run=True,
            output_dir='dashboard_data/lifestyle-eval-candidate/reports',
        )
        print(f"{sku}: {result.candidate.final_score.composite}% - {result.candidate.final_score.approval_status}")

asyncio.run(test_skus())
```

## Interpreting the Output

### Report Structure

Each report (in `dashboard_data/lifestyle-eval-candidate/reports/sku-{SKU}-*.md`) contains:

1. **Current Content** - The existing title and description
2. **Optimized Content** - New title and description with character counts
3. **Quality Scores** - Six dimensions rated 0-10:
   - Specificity (concrete vs vague claims)
   - Benefit Coverage (benefits in first 150 chars)
   - Keyword Inclusion (proper placement)
   - Format Adherence (character limits met)
   - Brand Voice (premium, understated tone)
   - Factual Accuracy (verified against source data)
4. **Claim Verification** - Each factual claim with its source
5. **Recommendation** - APPROVED, REVISE, or REJECTED

### Understanding Quality Scores

| Composite Score | Status   | Action                   |
| --------------- | -------- | ------------------------ |
| 80%+            | APPROVED | Ready for publication    |
| 70-79%          | REVISE   | Minor adjustments needed |
| <70%            | REJECTED | Major revision required  |

### JSON Patch Preview

The `dashboard_data/lifestyle-eval-candidate/google-patch-{SKU}.json` file contains:

```json
{
  "offerId": "shopify_US_...",
  "title": "Optimized title here",
  "short_title": "Optimized short title",
  "description": "Optimized description here",
  "channel": "online",
  "contentLanguage": "en",
  "targetCountry": "US",
  "_meta": {
    "master_sku": "101",
    "quality_score": 95.0,
    "approval_status": "approved"
  },
  "_previous": {
    "title": "Original title",
    "description": "Original description"
  }
}
```

## Making Tweaks to Output

### When to Adjust

Consider manual tweaks when:

- The score is 70-79% (REVISE status)
- Specific claims need refinement
- Brand voice doesn't match expectations
- A key product feature is missing

### How to Adjust

1. **Review the report** - Identify which dimensions scored low
2. **Check claim verification** - See which claims were rejected and why
3. **Edit the JSON patch** - Modify title/description directly
4. **Re-score manually** - Use the scoring rubric in `AGENTS.md`

### Common Issues and Fixes

| Issue                 | Cause                              | Fix                          |
| --------------------- | ---------------------------------- | ---------------------------- |
| Low factual accuracy  | LLM made unverifiable claims       | Edit to use only source data |
| Missing bullet points | LLM didn't format properly         | Add bullets to description   |
| Title too long        | Exceeded 150 chars                 | Trim functional modifiers    |
| Missing dimension     | Key spec not in first 70 chars     | Reorder title components     |
| Vague language        | Generic claims like "high quality" | Replace with specific specs  |

### Regenerating with Adjustments

To regenerate with the same SKU (may produce different results due to LLM randomness):

```bash
PYTHONPATH=./src .venv/bin/python -m feedops.cli.main optimize \
  --parent-sku "101" \
  --dry-run
```

## Testing Workflow

### Recommended Testing Process

1. **Start with sample data**

   ```bash
   feedops optimize --parent-sku SAMPLE-101 --catalog samples/sample-catalog.csv --dry-run
   ```

2. **Test one real SKU from each category**
   - Cabinet Hardware (e.g., `101`)
   - Towel Bars (e.g., `1031/18`)
   - Grab Bars (e.g., `P-700-16-GB`)
   - Mirrors, if applicable

3. **Review reports for quality patterns**
   - Are scores consistently above 80%?
   - Are claim verifications passing?
   - Is the output format consistent?

4. **Iterate on problematic categories**
   - If a category consistently scores low, check the source data quality
   - Missing fields in CSV = LLM can't make verified claims

### Checklist for Production Readiness

Before using in production:

- [ ] All test SKUs score 80%+
- [ ] Claim verification passes (factual accuracy 8+)
- [ ] Titles are 150 chars or less
- [ ] Descriptions are 500+ chars
- [ ] No promotional language in output
- [ ] JSON patch structure is valid
- [ ] Output matches brand voice expectations

## Troubleshooting

### "MasterSKU not found" Error

The SKU doesn't exist in your catalog. Check:

```bash
feedops list-skus | grep "YOUR-SKU"
```

### Low Factual Accuracy Score

The LLM made claims that couldn't be verified against source data. Check:

1. Are the required fields present in your CSV?
2. Does the CSV have correct column names?
3. Review the claim verification section of the report

### Empty or Short Descriptions

The source data may lack content. Check the CSV for:

- `Narraive Copy` field
- `Bullet 1` through `Bullet 6` fields
- Category and Collection fields

### API Rate Limits

If you hit rate limits:

- Add delays between SKUs when batch testing
- Use the Gemini fallback by removing `OPENAI_API_KEY`
- Reduce batch size
