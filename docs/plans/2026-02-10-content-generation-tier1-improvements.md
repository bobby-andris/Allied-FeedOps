# Content Generation Tier‑1 Improvements Implementation Plan

> **For Codex/Claude:** REQUIRED SUB-SKILL: Use `superpowers:executing-plans` (or equivalent) to implement this plan task-by-task.

**Goal:** Improve Google/Bing/Shopify titles and descriptions by making keyword usage and competitive positioning more deterministic, evidence-grounded, and measurable before scaling to thousands of SKUs.

**Architecture:** Add a deterministic “keyword priority” signal derived from existing Search Query Insights evidence, enforce it via validation + auto-retry, and align scoring so “high score” means “search-aligned + human-readable + policy-safe.”

**Tech Stack:** Next.js (dashboard), TypeScript prompt/validation, Supabase evidence tables, Python FeedOps pipeline (legacy) where parity is required.

---

## Tier‑1 Changes (Scope)

1. **Deterministic keyword plan (per SKU)** from Search Query Insights, surfaced to the LLM as an explicit instruction block.
2. **Keyword-alignment validation + auto‑retry** so titles can’t “look good” while missing query intent.
3. **Bing anti‑stuffing hard rules** (negative patterns + validator) to prevent slash/parenthetical dumps.
4. **Competitive positioning guardrails** (allowed claims library + evidence checks) so differentiation is strong but never speculative.
5. **Scoring alignment**: add keyword alignment as a first-class dimension and reweight composite (so scores reflect what we’re optimizing).

---

## Task 1: Add deterministic keyword plan builder (TS)

**Files:**
- Create: `dashboard/src/lib/evidence/keyword-plan.ts`
- Modify: `dashboard/src/lib/evidence/queries.ts`

**Step 1: Implement query parsing helper**

Add a parser that converts `search_queries_top` evidence row value into structured items:
- `query_text`
- `volume` (prefer `avg_monthly_searches`; fallback to impressions)

Also add a normalizer/tokenizer used for overlap checks (stopword removal).

**Step 2: Implement anchor/support term selection**

Selection rules:
- **Anchor candidate pool:** top 10 `search_queries_top` phrases.
- **Fit constraint:** anchor must overlap with the product type tokens inferred from:
  - `category` (evidence row)
  - `current_title` (evidence row, if present)
  - `feature_title_keywords` (evidence row, if present)
- **Pick anchor:** highest `(volume_score × fit_score)` phrase.
- **Support terms:** up to 2 additional phrases that add *new* intent (mounting, room context, style) without duplicating the anchor.
- **Description terms:** up to 6 additional phrases; require at least 2 in the description.

**Step 3: Surface plan to the model**

Update `getProductEvidence` to append a new Evidence row:
- `field: "keyword_plan"`
- `source: "search_insights"`
- `value`: a formatted block:
  - `TITLE_ANCHOR: ...`
  - `TITLE_SUPPORT: ...`
  - `DESCRIPTION_TERMS: ...`
  - `ROOM_CONTEXT: bathroom|kitchen|...`

---

## Task 2: Enforce keyword plan via validation + auto‑retry

**Files:**
- Modify: `dashboard/src/lib/regeneration/prompts.ts`
- Modify: `dashboard/src/lib/regeneration/core.ts`

**Step 1: Extend validation signature**

Update `validateGeneratedContent()` to optionally accept:
- parsed keyword plan (anchor + required description terms)
- platform + content type

**Step 2: Add new violations**

Google/Bing titles:
- Must include `TITLE_ANCHOR` in first 70 chars (token-overlap, not exact substring).

Shopify titles:
- Must include the **anchor’s product-type core** but not finish/brand (use overlap threshold + stopword rules).

Descriptions:
- Must include at least `N` description terms (token overlap), with **strict anti-stuffing** rules.

**Step 3: Wire plan into auto-retry**

In `core.ts`, pass the keyword plan into validation so a miss triggers the existing auto‑retry loop with a concrete violation list.

---

## Task 3: Fix Bing anti‑stuffing with explicit negative patterns

**Files:**
- Modify: `dashboard/src/lib/regeneration/prompts.ts`
- Modify: `dashboard/src/lib/regeneration/prompts.ts` (validation rules)

**Step 1: Prompt updates**

Add explicit “never do this” patterns for Bing:
- No `a / b / c` dimension formats.
- No parenthetical synonym lists.
- No repeated near-identical sentences that only swap synonyms.

**Step 2: Validator patterns**

Add violations for:
- slash-separated alternatives: `/\s*\/\s*/` in the first 200 chars
- parenthetical dumps that include `or`/`/` lists
- repeated dimension variants (`6 inches`, `6-inch`, `6in`) in the same sentence

---

## Task 4: Competitive positioning guardrails (evidence-first)

**Files:**
- Modify: `dashboard/src/lib/evidence/builder.ts`
- Modify: `dashboard/src/lib/regeneration/prompts.ts`

**Step 1: Make competitive edge safer + conditional**

Replace the unconditional `competitive_edge` evidence value with a conditional one:
- If `material` includes brass → allow a qualified comparison (“solid brass construction for durability”).
- Otherwise → omit competitor comparisons entirely and focus on supported differentiators.

**Step 2: Prompt rule**

Add: “You may reference alternatives only in qualified terms (‘many lower-cost options…’) unless competitor data is provided.”

---

## Task 5: Scoring alignment (keyword alignment becomes first-class)

**Files:**
- Modify: `dashboard/src/lib/quality-scoring.ts`
- Modify: `dashboard/src/components/review/ContentQualityCard.tsx`
- (Parity) Modify: `src/feedops/quality/scoring.py` (if pipeline scores are used operationally)

**Step 1: Add keyword alignment scorer**

Add an optional parameter to `analyzeContent()` / `analyzeSixDimensions()`:
- `keywordPlan?: { titleAnchor?: string; descriptionTerms?: string[] }`

Score:
- Title anchor present in first 70 chars: 0–10
- Description includes ≥2 terms: 0–10 (cap at 10)

**Step 2: Reweight composite**

Update composite to weight:
- keywordAlignment 30%
- cvrProxy 25%
- ctrProxy 15%
- brandVoice 15%
- readability 15%

**Step 3: UI display**

Update the Quality UI to show keyword alignment explicitly so reviewers see why a score is high/low.

---

## Done Criteria (Methodology Validation, Not Performance)

- Titles reliably include an evidence-derived anchor phrase without stuffing.
- Bing descriptions stop producing slash/parenthetical keyword dumps.
- Competitive positioning statements are always supported/qualified (no speculative competitor claims).
- Scores change meaningfully when keyword alignment improves (no more “91.67 spam”).

