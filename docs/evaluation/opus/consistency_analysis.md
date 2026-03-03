# Output Consistency Analysis

Mean pairwise similarity across generation passes (0.0 = entirely different, 1.0 = identical).
Computed using `difflib.SequenceMatcher.ratio()` on `title ||| description` concatenation.

## Title Consistency

| SKU | Model | Platform | Passes | Similarity |
|-----|-------|----------|--------|------------|
| 1032 | claude-opus-4-6 | bing | 1 | 1.000 |
| 1032 | claude-opus-4-6 | google | 1 | 1.000 |
| 1032 | claude-opus-4-6 | shopify | 1 | 1.000 |
| 1041/24 | claude-opus-4-6 | bing | 1 | 1.000 |
| 1041/24 | claude-opus-4-6 | google | 1 | 1.000 |
| 1041/24 | claude-opus-4-6 | shopify | 1 | 1.000 |
| 2020T | claude-opus-4-6 | bing | 1 | 1.000 |
| 2020T | claude-opus-4-6 | google | 1 | 1.000 |
| 2020T | claude-opus-4-6 | shopify | 1 | 1.000 |
| 404-12BB | claude-opus-4-6 | bing | 1 | 1.000 |
| 404-12BB | claude-opus-4-6 | google | 1 | 1.000 |
| 404-12BB | claude-opus-4-6 | shopify | 1 | 1.000 |
| 433/18 | claude-opus-4-6 | bing | 1 | 1.000 |
| 433/18 | claude-opus-4-6 | google | 1 | 1.000 |
| 433/18 | claude-opus-4-6 | shopify | 1 | 1.000 |
| AP-94 | claude-opus-4-6 | bing | 1 | 1.000 |
| AP-94 | claude-opus-4-6 | google | 1 | 1.000 |
| AP-94 | claude-opus-4-6 | shopify | 1 | 1.000 |
| CC-64 | claude-opus-4-6 | bing | 1 | 1.000 |
| CC-64 | claude-opus-4-6 | google | 1 | 1.000 |
| CC-64 | claude-opus-4-6 | shopify | 1 | 1.000 |
| CM-P-700-24-GB | claude-opus-4-6 | bing | 1 | 1.000 |
| CM-P-700-24-GB | claude-opus-4-6 | google | 1 | 1.000 |
| CM-P-700-24-GB | claude-opus-4-6 | shopify | 1 | 1.000 |
| CVTS-25 | claude-opus-4-6 | bing | 1 | 1.000 |
| CVTS-25 | claude-opus-4-6 | google | 1 | 1.000 |
| CVTS-25 | claude-opus-4-6 | shopify | 1 | 1.000 |
| DM-1/3X | claude-opus-4-6 | bing | 1 | 1.000 |
| DM-1/3X | claude-opus-4-6 | google | 1 | 1.000 |
| DM-1/3X | claude-opus-4-6 | shopify | 1 | 1.000 |

## Summary by Model

| Model | Mean Similarity | Std Dev | Samples |
|-------|-----------------|---------|---------|
| claude-opus-4-6 | 1.000 | 0.000 | 30 |

## Interpretation

- **>0.90**: Very consistent — model produces nearly identical outputs across runs
- **0.75-0.90**: Consistent — minor wording variation, same structure
- **0.50-0.75**: Moderate variance — notable variation in phrasing
- **<0.50**: High variance — substantially different outputs across runs

Note: Run 1 may be slower (cold cache) than Runs 2-3 (warm cache). Latency data in raw_results.csv shows cache impact per pass.