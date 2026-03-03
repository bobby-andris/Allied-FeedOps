# Model Evaluation SKU Selection

**Date:** 2026-03-03
**Selected by:** Claude (auto-selected per user request)
**Criteria:** No existing generated content, category diversity, multi-SKU mix

## Selection Criteria

1. **No generated content** — SKUs must have no `candidate_content` or `approved_content` in `generated_content` table, so winning outputs can go directly to the review queue
2. **Category diversity** — 10 different product categories for broad coverage
3. **Multi-SKU mix** — 3 multi-SKU products (share Shopify product_id with siblings) to test variant-aware generation
4. **Collection variety** — 6 different named collections + 2 with no collection
5. **Product type range** — Mix of decorative (candle holders, mirrors), functional (grab bars, toilet paper), and essential (towel bars, soap dishes)

## Final 10 SKUs

| # | SKU | Category | Collection | Multi-SKU | Rationale |
|---|-----|----------|------------|-----------|-----------|
| 1 | DM-1/3X | Make-Up Mirrors | (none) | Yes (4 siblings) | Multi-SKU, no collection, magnification variants |
| 2 | 433/18 | Glass Shelves | Venus | Yes (2 siblings) | Multi-SKU, named collection, size variants |
| 3 | CM-P-700-24-GB | Grab Bars | Camo | No | Specialty/safety category, unique collection |
| 4 | 2020T | Robe Hooks | Continental | No | Small accessory, accent variant (Twist) |
| 5 | 1032 | Soap Dishes | Skyline | No | Different collection, simple wall-mounted product |
| 6 | CC-64 | Candle Holders | Carolina Crystal | No | Niche decorative category |
| 7 | 1041/24 | Towel Bars | Skyline | Yes (4 siblings) | Multi-SKU, highest-volume category, size variants |
| 8 | AP-94 | Wall Mirrors | Astor Place | No | Premium category, tilt/bevel features |
| 9 | CVTS-25 | Freestanding Toilet Tissue Stands | Clearview | No | Freestanding product type |
| 10 | 404-12BB | Shower Door Hardware | (none) | No | Hardware category, no collection |

## Diversity Summary

- **Categories:** 10 unique (Make-Up Mirrors, Glass Shelves, Grab Bars, Robe Hooks, Soap Dishes, Candle Holders, Towel Bars, Wall Mirrors, Freestanding Toilet Tissue Stands, Shower Door Hardware)
- **Collections:** Astor Place, Camo, Carolina Crystal, Clearview, Continental, Skyline, Venus, (none) x2
- **Multi-SKU:** 3 of 10 (DM-1/3X, 433/18, 1041/24)
- **Approved content:** 0 of 10 (intentional — all are fresh SKUs)
- **Product types:** Wall-mounted (5), freestanding (2), vanity top (1), door hardware (1), specialty (1)

## Command to Run Evaluation

```bash
cd /Users/bobby/Documents/GitHub/Allied-FeedOps
set -a && source .env.vercel && set +a
PYTHONPATH=./src python scripts/run_model_evaluation.py \
  --skus "DM-1/3X" "433/18" "CM-P-700-24-GB" "2020T" "1032" "CC-64" "1041/24" "AP-94" "CVTS-25" "404-12BB" \
  --models gpt-5.2 claude-sonnet-4-6 claude-opus-4-6 \
  --passes 3 \
  --output-dir docs/evaluation
```
