# FeedOps Content Quality Improvement Plan

## Context
This plan consolidates findings from the quality audit, user feedback, and Codex recommendations into a prioritized set of fixes for the title/description generation pipeline.

## Key Clarifications
- **Collection names**: Not all products belong to collections - must be conditional
- **Google Ads data**: Already using real performance data (conversions, clicks, impressions) to rank keywords - no changes needed
- **Focus**: Title quality, claim verification accuracy, and marketing language control

## Scope
**Implementing Phase 1 only (Quick Wins)** - 4 low-effort, high-impact fixes

---

## Phase 1 Implementation (Quick Wins)

### Fix 1: Add Enrichment Fields to Verifier Lookup
**Impact:** High | **Effort:** Low
- **Problem:** Claims like "Available in 28 designer finishes" always rejected because `verifier.py` only checks ParentSKU/Variant fields, not enrichment-injected fields
- **Fix:** Add `finish_variety`, `statement_finishes` to verifier's field lookup
- **Files:** `src/feedops/pipeline/verifier.py:49-57`
- **Validation:** Claims referencing enrichment fields pass verification

### Fix 2: Resolve Prompt Conflict: Product-Type-First Titles
**Impact:** High | **Effort:** Low
- **Problem:** Prompt says both "benefit-first" and "don't start with generic benefits" - conflicting
- **Fix:** Clarify prompt to ALWAYS start with `[Product Type]` or `[Feature Modifier + Product Type]`, move benefits to secondary clause
- **Files:** `src/feedops/pipeline/prompts.py:117-146`
- **Validation:** Zero titles starting with generic benefits in output samples

### Fix 3: Add Banned Marketing Words List
**Impact:** Medium | **Effort:** Low
- **Problem:** "finest", "luxurious", "premium" pass through without evidence
- **Fix:** Add banned words list to prompt + soft-gate scoring penalty
- **Files:**
  - `src/feedops/pipeline/prompts.py` (add banned list)
  - `src/feedops/quality/scoring.py` (add penalty for banned words)
- **Banned words:** finest, luxurious, premium, exclusive, exceptional, unparalleled, superior
- **Validation:** Fewer soft-gate warnings; scoring flags banned words

### Fix 4: Apply Title Case Normalization
**Impact:** Medium | **Effort:** Low
- **Problem:** Inconsistent casing across titles
- **Fix:** Post-process titles to Title Case with standard separators ("|")
- **Files:** `src/feedops/pipeline/selection.py` (add in `sanitize_candidate_content()`)
- **Validation:** All titles follow consistent casing pattern

---

## Implementation Order

```
Fix 1: Enrichment verifier lookup → Fix 2: Prompt clarification → Fix 3: Banned words → Fix 4: Title casing
```

---

## Files to Modify

| File | Changes |
|------|---------|
| `src/feedops/pipeline/verifier.py` | Add enrichment field lookup (Fix 1) |
| `src/feedops/pipeline/prompts.py` | Clarify title structure, add banned words (Fix 2, 3) |
| `src/feedops/quality/scoring.py` | Add banned word penalty (Fix 3) |
| `src/feedops/pipeline/selection.py` | Title case normalization (Fix 4) |

---

## Verification Approach

After each fix:
1. Run `python -m feedops.cli optimize --sku DT-GRS-16` on sample SKUs
2. Review generated reports in `reports/` directory

**Fix 1 Verification:**
- Check claim verification section - enrichment claims (finish_variety) should now pass

**Fix 2 Verification:**
- Review titles - should start with product type, not generic benefits like "Easy-Clean"

**Fix 3 Verification:**
- Search output for banned words (finest, luxurious, premium) - should be zero
- Check scoring output for soft-gate warnings

**Fix 4 Verification:**
- All titles should have consistent Title Case formatting

**End-to-end validation:**
1. Generate reports for 10-SKU sample set
2. Compare composite scores to baseline (88.26%)
3. Manual review of title structure and marketing language

---

## Future Work (Phase 2+)

Deferred for later implementation:
- Canonical product type enforcement (towel bar vs towel holder)
- Durability claim extraction (corrosion-free, rust-free)
- Short-title redundancy deduplication
- Kitchen vs bathroom context awareness
- Title lint check in selection pipeline
- Category synonyms in first 150 chars
- Collection metadata expansion
