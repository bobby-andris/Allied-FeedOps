# Sample Data

This directory contains **anonymized sample data** for testing and documentation purposes.

## Files

- `sample-catalog.csv` - 4-row anonymized product catalog demonstrating expected column structure

## Important Notes

1. **These are NOT real products** - SKUs, brands, and details are placeholders
2. **Use for testing pipeline logic only** - not for actual optimization
3. **Real data stays in `data/`** - which is gitignored

## Creating Your Own Samples

When creating samples from real data:
1. Replace actual SKUs with `SAMPLE-XXX` prefixes
2. Replace brand name with `Sample Brand`
3. Keep column structure and data types intact
4. Limit to 5-10 representative rows
