# Sample Data and Fixture SKU Sets

This directory contains both anonymized sample data and fixture SKU sets used for offline evaluation.

## Files

- `sample-catalog.csv` - 4-row anonymized product catalog demonstrating expected column structure (demo only)
- `eval-skus.json` - Phase 0 fixture set for repeatable offline quality validation
- `eval-skus-google-ads-90d.json` - high-intent fixture set sourced from recent Google Ads query coverage

## Important Notes

1. `sample-catalog.csv` is anonymized demo data only (not real products).
2. `eval-skus.json` and `eval-skus-google-ads-90d.json` contain real SKU identifiers used as offline baseline baskets.
3. Real product specs remain in `data/` (gitignored).
4. Python is the production logic source of truth; Supabase is the production data source of truth (`product_catalog`, search insight tables). These fixture files exist to keep regression runs deterministic/offline when Supabase access is unavailable.
5. Supabase MCP is an operator/analysis tool for engineers and agents; it is not a runtime dependency of the generation pipeline.

## Fixture Governance

1. Do not remove fixture SKUs without replacement coverage.
2. Add SKUs only when they improve category diversity or intent coverage.
3. Keep fixture list size stable and practical for repeatable regression runs (target range: 20-50 SKUs per set).
4. Treat `eval-skus.json` as the default Phase 0 baseline set and `eval-skus-google-ads-90d.json` as the high-intent companion set.

## Creating Your Own Samples

When creating anonymized samples from real data:
1. Replace actual SKUs with `SAMPLE-XXX` prefixes.
2. Replace brand names with `Sample Brand`.
3. Keep column structure and data types intact.
4. Limit to 5-10 representative rows.
