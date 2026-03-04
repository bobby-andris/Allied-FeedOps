---
phase: quick-2
plan: 01
type: execute
wave: 1
depends_on: []
files_modified:
  - dashboard/src/app/api/sku-selection/route.ts
  - dashboard/src/app/(dashboard)/review/[sku]/page.tsx
  - src/feedops/api/prompt_loader.py
  - src/feedops/api/finish_processing.py
  - src/feedops/pipeline/generator.py
  - dashboard/src/lib/publishing/expand-variants.ts
autonomous: true
requirements: [BUG-A, BUG-B2, BUG-B4]

must_haves:
  truths:
    - "SKUs with any generated_content rows (regardless of approval status) are excluded from Generate tab recommendations"
    - "Pipeline generates finish sentences only for finishes that exist in variant_index for that master_sku"
    - "Publish pipeline succeeds for SKUs with fewer than 28 variants (no count mismatch error)"
    - "Review page displays only finish sentences for finishes that exist in variant_index for that SKU"
  artifacts:
    - path: "dashboard/src/app/api/sku-selection/route.ts"
      provides: "SKU exclusion filtering"
      contains: "from('generated_content').select('master_sku')"
    - path: "src/feedops/api/prompt_loader.py"
      provides: "get_finish_list_for_sku function"
      exports: ["get_finish_list_for_sku"]
    - path: "src/feedops/api/finish_processing.py"
      provides: "SKU-specific finish sentence generation"
      contains: "get_finish_list_for_sku"
    - path: "dashboard/src/lib/publishing/expand-variants.ts"
      provides: "Publish validation using per-finish check instead of count comparison"
    - path: "dashboard/src/app/(dashboard)/review/[sku]/page.tsx"
      provides: "Filtered finish sentences prop — only SKU-relevant finishes"
      contains: "relevantFinishes"
  key_links:
    - from: "src/feedops/api/finish_processing.py"
      to: "src/feedops/api/prompt_loader.py"
      via: "get_finish_list_for_sku(master_sku)"
      pattern: "get_finish_list_for_sku"
    - from: "dashboard/src/lib/publishing/expand-variants.ts"
      to: "variant_index table"
      via: "per-finish coverage check"
      pattern: "variants.*finish.*finishSentences"
    - from: "dashboard/src/app/(dashboard)/review/[sku]/page.tsx"
      to: "variant_index query results"
      via: "filter finish sentences by variant finishes"
      pattern: "relevantFinishes.*finishSentences"
---

<objective>
Fix 3 UAT bugs: SKU exclusion scope too narrow on Generate tab, pipeline generating all 28 finish sentences regardless of actual variant count, review page showing all 28 finish sentences instead of only relevant ones, and publish pipeline failing on SKUs with fewer than 28 variants.

Purpose: Unblock publishing workflow, eliminate phantom finish display/generation waste, and show only relevant finishes on review page.
Output: Corrected SKU filtering, SKU-aware finish generation, filtered review page display, and resilient publish validation.
</objective>

<execution_context>
@/Users/bobby/.claude/get-shit-done/workflows/execute-plan.md
@/Users/bobby/.claude/get-shit-done/templates/summary.md
</execution_context>

<context>
@.planning/STATE.md
@dashboard/src/app/api/sku-selection/route.ts
@dashboard/src/app/(dashboard)/review/[sku]/page.tsx
@src/feedops/api/prompt_loader.py
@src/feedops/api/finish_processing.py
@src/feedops/pipeline/generator.py
@dashboard/src/lib/publishing/expand-variants.ts

<interfaces>
<!-- From src/feedops/api/prompt_loader.py -->
```python
FINISH_LIST_28: list[str]  # 28 hardcoded finish names (line 61-90)
def get_finish_list() -> list[str]:  # Returns FINISH_LIST_28 (line 397-403)
```

<!-- From src/feedops/db/supabase_client.py (used by prompt_loader.py already) -->
```python
from feedops.db.supabase_client import get_client, is_supabase_available
```

<!-- From src/feedops/api/finish_processing.py -->
```python
def _build_finish_sentences_user_prompt(*, base_description: str, master_sku: str, platform: str) -> str
def _validate_finish_sentences_payload(raw, *, base_description: str, master_sku: str, platform: str) -> dict[str, str]
async def _enforce_finish_sentence_parity(*, provider, content, master_sku, platform, endpoint) -> tuple[str, dict[str, str] | None]
```

<!-- From src/feedops/pipeline/generator.py -->
```python
def _build_finish_metadata_rows(parent_sku: ParentSKU) -> list[dict[str, object]]
def _normalize_finish_sentence_payload(payload: dict[str, object], parent_sku: ParentSKU) -> dict[str, str]
```

<!-- From dashboard/src/lib/publishing/expand-variants.ts line 229-231 -->
```typescript
// CURRENT (broken): exact count comparison
const uniqueFinishes = new Set(variants.map((v) => v.finish)).size
if (Object.keys(finishSentences).length !== uniqueFinishes) {
    throw new Error('variant_finish_contradiction: publish_google_finish_sentences_incomplete')
}
```

<!-- From dashboard/src/app/(dashboard)/review/[sku]/page.tsx lines 188-193 -->
```typescript
// Variants already fetched from variant_index (line 189-193)
const { data: variants } = await supabase
  .from('variant_index')
  .select('*')
  .eq('master_sku', sku)
  .order('finish', { ascending: true })
```

<!-- From dashboard/src/app/(dashboard)/review/[sku]/page.tsx lines 303-315, 456-458 -->
```typescript
// Finish sentences fetched unfiltered (all 28 from DB)
const { data: googleFinishSentences } = await supabase
  .from('variant_finish_sentences')
  .select('finish_sentences')
  .eq('master_sku', sku)
  .eq('platform', 'google')
  .single()

// Passed directly to client without filtering
finishSentences: {
  google: googleFinishSentences?.finish_sentences as Record<string, string> | null || null,
  bing: bingFinishSentences?.finish_sentences as Record<string, string> | null || null,
},
```
</interfaces>
</context>

<tasks>

<task type="auto">
  <name>Task 1: Fix SKU exclusion + review page finish filtering + publish validation (TypeScript side)</name>
  <files>dashboard/src/app/api/sku-selection/route.ts, dashboard/src/app/(dashboard)/review/[sku]/page.tsx, dashboard/src/lib/publishing/expand-variants.ts</files>
  <action>
**Bug A — SKU exclusion (sku-selection/route.ts lines 28-36):**

Replace the current query that only excludes approved content:
```typescript
const { data: generatedSkus } = await supabase
  .from('generated_content')
  .select('master_sku, approved_content')
  .not('approved_content', 'is', null)
```

With a query that excludes ANY SKU with ANY row in generated_content:
```typescript
const { data: generatedSkus } = await supabase
  .from('generated_content')
  .select('master_sku')
```

The `alreadyGeneratedSkus` set construction (line 34-36) stays the same but no longer needs the `approved_content` field — just map `master_sku`.

**Bug B4 — Review page finish filtering (review/[sku]/page.tsx lines 456-458):**

The `variants` array from `variant_index` is already fetched at line 189-193 and contains `.finish` for each variant. After loading `googleFinishSentences` and `bingFinishSentences` (lines 303-315), filter each to only include keys that match finishes present in `variant_index` for this SKU.

Before the return statement (around line 448), add filtering logic:
```typescript
// Filter finish sentences to only finishes that exist in variant_index for this SKU
const relevantFinishes = new Set(
  (variants || []).map((v: VariantIndex) => v.finish).filter(Boolean)
)

const filterFinishSentences = (
  sentences: Record<string, string> | null
): Record<string, string> | null => {
  if (!sentences) return null
  const filtered: Record<string, string> = {}
  for (const [finish, sentence] of Object.entries(sentences)) {
    if (relevantFinishes.has(finish)) {
      filtered[finish] = sentence
    }
  }
  return Object.keys(filtered).length > 0 ? filtered : null
}
```

Then update the finishSentences prop at lines 456-458:
```typescript
finishSentences: {
  google: filterFinishSentences(googleFinishSentences?.finish_sentences as Record<string, string> | null || null),
  bing: filterFinishSentences(bingFinishSentences?.finish_sentences as Record<string, string> | null || null),
},
```

This ensures the review page only displays finish sentences for finishes that actually exist in variant_index for the SKU (per CONTEXT.md locked decision).

**Bug B4 — Publish validation (expand-variants.ts lines 228-232):**

Replace the blunt count comparison:
```typescript
const uniqueFinishes = new Set(variants.map((v) => v.finish)).size
if (Object.keys(finishSentences).length !== uniqueFinishes) {
    throw new Error('variant_finish_contradiction: publish_google_finish_sentences_incomplete')
}
```

With a per-finish coverage check (consistent with the readiness check at lines 421-435 that already does this correctly):
```typescript
const requiredFinishes = [...new Set(variants.map((v) => v.finish).filter(Boolean))]
const missingFinishes = requiredFinishes.filter(f => !finishSentences[f])
if (missingFinishes.length > 0) {
    throw new Error(`variant_finish_contradiction: publish_google_finish_sentences_incomplete — missing: ${missingFinishes.slice(0, 3).join(', ')}`)
}
```

This allows the DB to have 28 finish sentences while the SKU only has 25 variants — publish succeeds as long as every required finish has a sentence.
  </action>
  <verify>
    <automated>cd /Users/bobby/Documents/GitHub/Allied-FeedOps/dashboard && npx tsc --noEmit 2>&1 | head -20</automated>
  </verify>
  <done>
  - SKU selection API excludes any SKU with any row in generated_content (not just approved rows)
  - Review page filters finish sentences to only show finishes present in variant_index for the SKU
  - Publish expand-variants checks per-finish coverage instead of exact count match
  - TypeScript compiles clean
  </done>
</task>

<task type="auto">
  <name>Task 2: Add SKU-specific finish list + wire into pipeline (Python side)</name>
  <files>src/feedops/api/prompt_loader.py, src/feedops/api/finish_processing.py, src/feedops/pipeline/generator.py</files>
  <action>
**Step 1 — Add `get_finish_list_for_sku()` to prompt_loader.py (after `get_finish_list()` at line 403):**

```python
def get_finish_list_for_sku(master_sku: str) -> list[str]:
    """Get the actual finish list for a specific SKU from variant_index.

    Queries Supabase variant_index to find which finishes this SKU actually has.
    Falls back to FINISH_LIST_28 if Supabase is unavailable or no variants found.

    Returns:
        List of finish names for this SKU's actual variants.
    """
    if not is_supabase_available():
        logger.warning("Supabase unavailable for get_finish_list_for_sku(%s), falling back to FINISH_LIST_28", master_sku)
        return FINISH_LIST_28
    try:
        supabase = get_client()
        result = supabase.table("variant_index").select("finish").eq("master_sku", master_sku).execute()
        finishes = sorted(set(
            row["finish"] for row in (result.data or [])
            if row.get("finish")
        ))
        if not finishes:
            logger.warning("No variant_index finishes found for %s, falling back to FINISH_LIST_28", master_sku)
            return FINISH_LIST_28
        return finishes
    except Exception as exc:
        logger.warning("Failed to query variant_index for %s: %s — falling back to FINISH_LIST_28", master_sku, exc)
        return FINISH_LIST_28
```

Note: `is_supabase_available` and `get_client` are already imported at line 19.

**Step 2 — Wire into finish_processing.py:**

In `_build_finish_sentences_user_prompt()` (line 30): Replace `get_finish_list()` with `get_finish_list_for_sku(master_sku)`. The `master_sku` parameter is already available in the function signature.

In `_validate_finish_sentences_payload()` (line 72): Replace `get_finish_list()` with `get_finish_list_for_sku(master_sku)`. The `master_sku` parameter is already available.

In `_enforce_finish_sentence_parity()` (line 118): Replace `get_finish_list()` with `get_finish_list_for_sku(master_sku)`. The `master_sku` parameter is already available. Also update:
- Line 119: `build_fallback_finish_sentences(finish_names)` — use the SKU-specific list
- Line 150-156: The `finish_schema` properties and required list — use SKU-specific list
- Line 195: The completeness check — use SKU-specific list

Update the import at line 8: Add `get_finish_list_for_sku` alongside `get_finish_list`.

**Step 3 — Wire into generator.py:**

In `_build_finish_metadata_rows()` (line 290): Replace `get_finish_list()` with the SKU's actual variants from `parent_sku.variants`. The function already has `parent_sku` available. Change to iterate over unique finishes from `parent_sku.variants` instead of `get_finish_list()`:
```python
sku_finishes = sorted(set(
    (variant.finish or "").strip()
    for variant in parent_sku.variants
    if getattr(variant, "finish", None)
))
if not sku_finishes:
    sku_finishes = get_finish_list()
```

In `_normalize_finish_sentence_payload()` (line 309): Replace `get_finish_list()` with `get_finish_list_for_sku(parent_sku.master_sku)` — need to check if `parent_sku` has a `master_sku` attribute. If it does, use SKU-specific. If not, extract from variants or fall back to `get_finish_list()`.

Update the import at line 11 of generator.py: Add `get_finish_list_for_sku` from `feedops.api.prompt_loader`.

**IMPORTANT**: Keep `get_finish_list()` function unchanged — it's still valid for contexts where no specific SKU is known. Only add the new function alongside it.
  </action>
  <verify>
    <automated>cd /Users/bobby/Documents/GitHub/Allied-FeedOps && PYTHONPATH=./src python -c "from feedops.api.prompt_loader import get_finish_list_for_sku; print('Import OK'); from feedops.api.finish_processing import _build_finish_sentences_user_prompt; print('finish_processing OK'); from feedops.pipeline.generator import _build_finish_metadata_rows; print('generator OK')"</automated>
  </verify>
  <done>
  - `get_finish_list_for_sku(master_sku)` exists in prompt_loader.py and queries variant_index
  - finish_processing.py uses SKU-specific finish list for prompt building, validation, and parity enforcement
  - generator.py uses variant-derived finish list for metadata rows and normalization
  - All modules import cleanly with no circular dependency issues
  - Fallback to FINISH_LIST_28 if variant_index unavailable (graceful degradation)
  </done>
</task>

</tasks>

<verification>
1. TypeScript build passes: `cd dashboard && npm run build`
2. Python imports clean: `PYTHONPATH=./src python -c "from feedops.api.prompt_loader import get_finish_list_for_sku; from feedops.api.finish_processing import _build_finish_sentences_user_prompt"`
3. Lint passes: `cd dashboard && npm run lint`
</verification>

<success_criteria>
- Bug A: SKU selection API query no longer filters by `approved_content IS NOT NULL` — any SKU with generated content is excluded
- Bug B2: Pipeline finish sentence generation uses SKU-specific finish list from variant_index, not hardcoded 28
- Bug B4 (review): Review page filters finish sentences to only display finishes that exist in variant_index for that SKU
- Bug B4 (publish): Publish expand-variants validates per-finish coverage (every variant finish has a sentence) instead of exact count match
- All TypeScript compiles, Python imports clean, no regressions
</success_criteria>

<output>
After completion, create `.planning/quick/2-fix-3-uat-bugs-sku-exclusion-phantom-fin/2-SUMMARY.md`
</output>
