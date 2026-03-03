# Output Consistency Analysis

Mean pairwise similarity across generation passes (0.0 = entirely different, 1.0 = identical).
Computed using `difflib.SequenceMatcher.ratio()` on `title ||| description` concatenation.

## Title Consistency

| SKU | Model | Platform | Passes | Similarity |
|-----|-------|----------|--------|------------|
| 404-12BB | gpt-5.2 | bing | 1 | 1.000 |
| 404-12BB | gpt-5.2 | google | 1 | 1.000 |
| 404-12BB | gpt-5.2 | shopify | 1 | 1.000 |

## Summary by Model

| Model | Mean Similarity | Std Dev | Samples |
|-------|-----------------|---------|---------|
| gpt-5.2 | 1.000 | 0.000 | 3 |

## Interpretation

- **>0.90**: Very consistent — model produces nearly identical outputs across runs
- **0.75-0.90**: Consistent — minor wording variation, same structure
- **0.50-0.75**: Moderate variance — notable variation in phrasing
- **<0.50**: High variance — substantially different outputs across runs

Note: Run 1 may be slower (cold cache) than Runs 2-3 (warm cache). Latency data in raw_results.csv shows cache impact per pass.