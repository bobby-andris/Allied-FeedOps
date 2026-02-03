# P1 ULTRATHINK: Titles/Descriptions Strategy + AGENTS.md Verification (2026-01-29)

## What “truth” we verified (high-confidence)

### Google Merchant Center (policy + performance)
- **`title` max length is 150 characters.** Use key info first; avoid promotional text and gimmicky symbols. (GMC product data spec + title best practices)
- **AI-generated titles/descriptions should use `structured_title` / `structured_description`** with `digital_source_type`.
  - If both `title` and `structured_title` are provided, **Google will use `title` and ignore `structured_title`**.
  - Operational implication: if FeedOps content is AI-generated and we want policy compliance, our Google override mechanism must be able to publish *structured* attributes without simultaneously providing `title`/`description`.

### Shopify (SEO + on-site UX)
- Shopify recommends keeping **SEO title under ~60 characters** and **meta description under ~160** characters. Product titles can be longer, but long titles can reduce readability and “scanability”.

### Competitive reality
- Kohler/Moen patterns emphasize **size + finish + product type** early, with clean punctuation. They rarely use pipe-heavy titles, and they front-load the shopper’s query language (“24\" towel bar”, “brushed gold”, “grab bar”).

### What your own Google Ads data suggests (query language)
From Google Ads search term data (customer `6253381786`, `2025-10-01` → `2026-01-28`), many high-impression, finish-specified queries are **finish-first**, e.g.:
- `polished nickel paper towel holder`
- `unlacquered brass towel bar`
- `unlacquered brass toilet paper holder`

Implication: for some categories, “finish-first” titles may be more query-congruent than “product-type-first”, as long as product type remains visible early.

## Where our current system is misaligned

### 1) “Pipe-first” titles conflict with Google’s own guidance
Our generator and prompts currently push ` | ` as the primary separator. Google guidance discourages symbol-heavy titles and gimmicky punctuation. Pipes also read “clinical/inventory-like” for a premium brand.

### 2) Prompt rules block our stated “benefit-first” strategy
`src/feedops/pipeline/prompts.py` currently says:
- “NEVER start titles with adjectives or generic benefit words.”
This makes it difficult to lead with verified modifiers that matter for conversion in this category (e.g., “ADA-Compliant”, “Retractable”, “Tilt”).

### 3) `structured_title` compliance is not guaranteed end-to-end
We generate `structured_title` in patch JSON, but the publish-side integrations must support shipping structured attributes without also shipping `title`/`description` in the same submission.

## The highest ROI P1 improvements (ranked)

### P1-A (Highest impact / lowest risk): Make titles “human-first” without losing match coverage
Goal: lift Shopping CTR without harming CVR by reducing “inventory list” vibe and increasing query resonance.

Implementation:
- Replace ` | ` separators in Google/Bing titles with commas / hyphens (clean punctuation).
- Keep “query core” in first ~70 chars:
  - `[Product Type] + [Key Dimension] + [Finish/Variant]` (and only then collection/brand)
- Keep brand last for most Allied Brass items unless we can prove brand-search demand for that SKU/category.

Expected impact (order-of-magnitude):
- CTR lift on Shopping/PMax: **+3% to +12%** on impacted SKUs (conservative range).

### P1-B (High impact / medium risk): Allow evidence-gated modifiers at the front
Goal: increase CTR and pre-qualify buyers (reducing “wrong click” waste).

Implementation:
- Update prompt constraints to allow *verified* front-loaded modifiers:
  - “ADA-Compliant” for grab bars
  - “Retractable” for retractable hooks/rods
  - “Tilt” / “Tilt-Adjustable” for tilt mirrors
- Keep “no hollow marketing words” rule intact.

Expected impact:
- Better query match + better audience fit → higher CTR + higher CVR (fewer low-intent clicks).

### P1-C (Compliance + future-proof): Add a safe path for `structured_title` publishing
Goal: policy-compliant AI content delivery to GMC.

Implementation:
- Add an env-flagged mode to Google publishing that emits only:
  - `g:structured_title` / `g:structured_description`
  - no `g:title` / `g:description`
- Document the operational step required in Merchant Center (feed rules / mapping) so the structured attributes take effect.

Expected impact:
- Reduces account risk; aligns with Google’s direction for GenAI disclosures.

### P1-D (Revenue unlock beyond copy): Trust signals that matter more than copy
Copy cannot out-run weak trust inputs on Shopping.

Operational priorities (non-code):
- Improve/validate shipping speed, return policy visibility, and ratings coverage.
- Ensure GTIN/MPN/brand fields are complete and consistent where applicable.
- Confirm price competitiveness for “same product, multiple sellers” cases (title tweaks won’t win a price war).

## Revenue impact framing (how to think about it)

Base numbers (last 365 days):
- Sessions: 1,961,693
- AOV: ~$249

Incremental revenue per +0.05pp CVR lift:
- Full-site upper bound: `1,961,693 × 0.0005 × $249 ≈ $244k`
- If only 30% of sessions are influenced by Shopping/PMax content changes:
  - `1,961,693 × 0.30 × 0.0005 × $249 ≈ $73k`

Key truth: **FeedOps can’t plausibly influence 100% of sessions**, so any revenue model must include a “share of traffic affected” assumption.

## Recommended single A/B test (if we only run one)

Test: **Pipe-heavy titles vs clean-punctuation titles** (keep the same keywords and ordering as much as possible).
- Primary metric: Shopping CTR (SKU-level).
- Guardrail metrics: CVR, CPA, return/refund rate.
- Design: run on the 40 pilot SKUs; stagger rollout by SKU group to reduce seasonality noise.

## AGENTS.md changes applied

Updated `AGENTS.md` to:
- Add explicit policy guardrails (structured attributes for AI, avoid symbol-heavy titles).
- Remove unverified numeric claims (e.g., “+1.4pp”, “3.6x”, “2–10x”) and keep them as qualitative heuristics.
- Resolve internal inconsistency: prioritize product type + dimension + variant differentiator in the first 70 chars for niche brands.
