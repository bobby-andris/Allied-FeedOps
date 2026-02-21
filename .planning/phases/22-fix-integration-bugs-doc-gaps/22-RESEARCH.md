# Phase 22: Fix Integration Bugs & Close Documentation Gaps - Research

**Researched:** 2026-02-21
**Domain:** Python bug fixes, Cloud Run environment config, TypeScript one-liner fixes, YAML frontmatter documentation
**Confidence:** HIGH

## Summary

Phase 22 is a targeted cleanup phase with five discrete, well-scoped items identified directly from the v1.2 milestone audit. Every issue has a known root cause, a known file location, and a one-to-three-line fix. There is no exploratory work — the audit document serves as the specification. The two sub-plans divide naturally: Plan 01 covers runtime/code fixes (integration bug, env var, tech debt fixes), Plan 02 covers documentation-only changes (SUMMARY frontmatter updates).

The largest risk in this phase is scope creep — these fixes are so small that a planner might be tempted to combine them or expand them. The correct approach is to treat each item as a discrete task within the appropriate plan, verify each fix in isolation, and commit atomically. No new tables, no new API routes, no new components.

Phase 21 confirmed that all database migrations (034 and 035) are already applied to the live Supabase instance. This means the bottleneck classifier and prompt lineage routes are now fully operational at the DB level — only the SUMMARY documentation and the code-level bugs remain.

**Primary recommendation:** Fix all five items in two plans (runtime fixes first, docs second). Keep tasks small and verifiable. No new infrastructure.

<phase_requirements>
## Phase Requirements

| ID | Description | Research Support |
|----|-------------|-----------------|
| FIX-01 | UI single-SKU regeneration path (/regenerate) uses same rich prompt construction as batch path — this was satisfied by Phase 20's build_core_prompt(), but the feedback layer (apply_feedback_layer) has a field name mismatch that corrupts persistent corrections | Fix `correction.get("text") or correction.get("correction")` → add `correction.get("correction_text")` as first key in prompt_builder.py:309 |
| MEAS-02 | GMC disapproval visibility — system can query Merchant API to identify disapproved/not-serving products | E2E flow requires GMC_MERCHANT_ID env var set in Cloud Run; MerchantApiClient() raises ValueError on __init__ if missing; fix via `gcloud run services update` or Cloud Console |
| MODEL-01 | Research GPT-5.2 capabilities vs current model — benchmark exists in docs/research/model-comparison.md, verified PASSED by Phase 17 VERIFICATION | Add `requirements-completed: [MODEL-01, MODEL-02]` to 17-02-SUMMARY.md frontmatter (documentation gap only, no code change) |
| MODEL-02 | Evaluate alternative models (Claude, Gemini, open-source) — same artifact as MODEL-01, verified PASSED | Same fix as MODEL-01 — single frontmatter line addition |
| MEAS-04 | Bottleneck classifier categorizes impact issues — code complete, DB tables now exist (Phase 21 confirmed), but missing from 19-02 and 19-03 SUMMARY frontmatter | Add `requirements-completed: [MEAS-04]` to 19-02-SUMMARY.md and 19-03-SUMMARY.md frontmatter |
</phase_requirements>

## Standard Stack

### Core
| Library/Tool | Version | Purpose | Why Standard |
|---|---|---|---|
| Python (prompt_builder.py) | 3.11 | Fix apply_feedback_layer() dict key | Existing production code |
| gcloud CLI / Cloud Console | Current | Set GMC_MERCHANT_ID env var on Cloud Run | Only way to configure Cloud Run env vars |
| TypeScript (route.ts) | 5.x | Fix `parsed.run_at` → `parsed.run_timestamp` | Existing dashboard API route |
| YAML frontmatter | — | Add `requirements-completed` fields to SUMMARY files | Existing pattern used by 17-01, 17-03, 19-01, 19-04 |

### No New Dependencies
This phase introduces zero new libraries. All changes are edits to existing files.

## Architecture Patterns

### Existing Pattern: SUMMARY Frontmatter Structure

The established pattern (seen in 17-01-SUMMARY.md, 17-03-SUMMARY.md, 19-01-SUMMARY.md, 19-04-SUMMARY.md) is:

```yaml
---
phase: [phase-name]
plan: [number]
subsystem: [subsystem]
tags: [...]
...
requirements-completed: [REQ-01, REQ-02]
...
---
```

The field name is `requirements-completed` (hyphenated, not underscored). The value is a YAML list of requirement IDs.

**Files missing this field:**
- `17-02-SUMMARY.md` — needs `requirements-completed: [MODEL-01, MODEL-02]`
- `19-02-SUMMARY.md` — needs `requirements-completed: [MEAS-04]`
- `19-03-SUMMARY.md` — needs `requirements-completed: [MEAS-04]`

### Existing Pattern: apply_feedback_layer() Key Lookup

Current code in `src/feedops/api/prompt_builder.py` line 309:
```python
text = correction.get("text") or correction.get("correction") or str(correction)
```

The `sku_corrections` table (migration 036, applied) has column `correction_text`. When `apply_feedback_layer()` receives correction dicts from Supabase, the dicts have key `correction_text`, not `text` or `correction`. The fallback `str(correction)` causes the raw Python dict repr to be injected into prompts.

**Fix (one line):**
```python
text = correction.get("correction_text") or correction.get("text") or correction.get("correction") or str(correction)
```

Rationale for ordering: `correction_text` is the correct DB column (highest priority), legacy keys kept as fallback for any callers that construct correction dicts programmatically.

### Existing Pattern: confirmed_sample.last_run

The spot-check-results.json file (verified to exist at `.planning/phases/18-diagnosis-establish-ground-truth/spot-check-results.json`) uses `run_timestamp` as the field name:

```json
{
  "run_timestamp": "2026-02-21T03:15:51.259438+00:00",
  "summary": { ... }
}
```

Current code in `dashboard/src/app/api/funnel/summary/route.ts` line 101:
```typescript
last_run: parsed.run_at ?? null,
```

**Fix (one character change):**
```typescript
last_run: parsed.run_timestamp ?? null,
```

This is a cosmetic fix — the dashboard shows `null` for `confirmed_sample.last_run` even when the spot-check has been run. No functional impact on data correctness.

### Existing Pattern: GMC_MERCHANT_ID in Cloud Run

`MerchantApiClient.__init__()` in `src/feedops/integrations/merchant_api.py`:
```python
self.mc_id = (
    merchant_center_id
    or os.environ.get("GMC_MERCHANT_ID")
    or os.environ.get("FEEDOPS_MERCHANT_CENTER_ID")
)
if not self.mc_id:
    raise ValueError(
        "Merchant Center ID not set. "
        "Set GMC_MERCHANT_ID environment variable."
    )
```

The constructor raises `ValueError` if `GMC_MERCHANT_ID` is not in the environment. Since `/gmc/sync` runs in a background thread via `run_async_in_thread()`, this exception is caught by the `except Exception as exc:` handler in `_run_gmc_sync()` and silently marks the job as failed. The fix is purely operational: set the env var in Cloud Run, no code changes required.

**How to set:**
```bash
gcloud run services update feedops-pipeline \
  --region us-east1 \
  --project bobbys-project-346400 \
  --update-env-vars GMC_MERCHANT_ID=<merchant_center_id>
```

Note: The Merchant Center ID is distinct from the Google Ads customer ID (6253381786). The audit notes this was documented in Phase 17-01's key decisions. The actual MC ID value needs to be retrieved from the Merchant Center account.

### Existing Pattern: keyword_bank.json in Cloud Run

The `data/` directory is excluded by `.gcloudignore` (line: `data/`). `keyword_bank.py` reads from `data/keyword-bank.json` by default but has a graceful fallback:

```python
def load_keyword_bank() -> dict[str, Any]:
    """Load keyword bank JSON if present; otherwise return empty dict."""
    path = _keyword_bank_path()
    if not path.exists():
        return {}
    return json.loads(path.read_text())
```

**Impact:** When `keyword_bank.json` is absent, `get_external_keywords()` returns `[]`. The evidence builder (`pipeline/evidence.py`) calls this and simply gets no external keywords in the evidence — generation still succeeds. This is LOW severity (not a crash, just silent data gap).

**Fix options (pick one):**

1. **Add a data/ exception in .gcloudignore** — include `keyword-bank.json` specifically:
   ```
   data/
   !data/keyword-bank.json
   ```
   Note: `.gcloudignore` does NOT support `!` negation patterns like `.gitignore` — this approach will NOT work.

2. **Embed keyword_bank.json in src/** — move it from `data/` to `src/feedops/data/keyword-bank.json` and update the default path constant. This file would then be included in the Docker build context.

3. **Set FEEDOPS_KEYWORD_BANK_PATH env var** — point to a path inside the container that is populated at build time.

**Recommended fix:** Move to `src/feedops/data/keyword-bank.json` (Option 2). The file is checked into git at `data/keyword-bank.json` (it's not secrets, it's research data). Moving it into the `src/` tree makes it a proper code artifact that belongs in the container. Update `DEFAULT_KEYWORD_BANK_PATH` in `keyword_bank.py`.

**Important verification:** Confirm `.gcloudignore` does not support `!` negation before choosing approach. The current `.gcloudignore` has no negation patterns anywhere, suggesting this is a known limitation.

## Don't Hand-Roll

| Problem | Don't Build | Use Instead |
|---|---|---|
| GMC_MERCHANT_ID in Cloud Run | Custom secrets manager integration | `gcloud run services update --update-env-vars` (or Cloud Console) |
| SUMMARY frontmatter validation | New CI check | Manual edit — one-time fix, not recurring |
| keyword_bank path resolution | Dynamic path discovery | Move file to `src/` where Docker COPY already includes it |

## Common Pitfalls

### Pitfall 1: Wrong field name in SUMMARY frontmatter
**What goes wrong:** Using `requirements_completed` (underscored) instead of `requirements-completed` (hyphenated)
**Why it happens:** Inconsistency between YAML key naming conventions
**How to avoid:** Copy the pattern from an existing correct file (`17-01-SUMMARY.md` line 40: `requirements-completed: [GOOG-01, GOOG-03]`)
**Verification:** Grep for the field after editing: `grep "requirements-completed" <file>`

### Pitfall 2: Overwriting existing frontmatter keys in SUMMARY files
**What goes wrong:** Adding `requirements-completed` as a duplicate key, or in the wrong position within the YAML block
**Why it happens:** YAML blocks require careful placement — adding after the closing `---` puts it in body text, not frontmatter
**How to avoid:** Insert the field before the closing `---` of the frontmatter block. Use `Read` to verify exact line numbers before editing.

### Pitfall 3: GMC_MERCHANT_ID value unknown
**What goes wrong:** Attempting to set the env var without knowing the actual Merchant Center ID
**Why it happens:** MC ID is different from Google Ads customer ID and wasn't documented in GCP secrets
**How to avoid:** Retrieve MC ID from the Merchant Center UI before executing the gcloud command. Check if it's stored elsewhere in the codebase (google-sheets.ts, other config files).
**Where to check:** `grep -r "merchant" /Users/bobby/Documents/GitHub/Allied-FeedOps/dashboard/src/ --include="*.ts" -l` and `grep -r "mc_id\|merchant_id" /Users/bobby/Documents/GitHub/Allied-FeedOps/src/ --include="*.py" -l`

### Pitfall 4: .gcloudignore negation not supported
**What goes wrong:** Adding `!data/keyword-bank.json` to .gcloudignore expecting it to re-include the file
**Why it happens:** `.gitignore`-style negation is a common assumption
**How to avoid:** Move keyword-bank.json into `src/feedops/data/` instead of trying to negate the exclusion. The Docker COPY statement copies the entire `src/` tree.

### Pitfall 5: Not running build verification after TypeScript fix
**What goes wrong:** The `run_at` → `run_timestamp` fix is trivial but the build must still pass
**Why it happens:** Even one-line TypeScript changes need type-checking — `parsed` has type `any` here so no TS error, but lint must be clean
**How to avoid:** Run `cd dashboard && npm run build && npm run lint` after the fix per CLAUDE.md pre-deploy gates

## Code Examples

### Exact Fix: apply_feedback_layer()

**File:** `/Users/bobby/Documents/GitHub/Allied-FeedOps/src/feedops/api/prompt_builder.py`
**Line:** 309
**Current:**
```python
text = correction.get("text") or correction.get("correction") or str(correction)
```
**Fixed:**
```python
text = correction.get("correction_text") or correction.get("text") or correction.get("correction") or str(correction)
```

Also update the docstring (line 296) which says "Each dict should have a 'text' key" — change to "Each dict should have a 'correction_text' key (from sku_corrections table)."

### Exact Fix: confirmed_sample.last_run

**File:** `/Users/bobby/Documents/GitHub/Allied-FeedOps/dashboard/src/app/api/funnel/summary/route.ts`
**Line:** 101
**Current:**
```typescript
last_run: parsed.run_at ?? null,
```
**Fixed:**
```typescript
last_run: parsed.run_timestamp ?? null,
```

### Exact Fix: SUMMARY frontmatter additions

**File:** `.planning/phases/17-google-shopping-intelligence-model-research/17-02-SUMMARY.md`
**Add before closing `---` of frontmatter:**
```yaml
requirements-completed: [MODEL-01, MODEL-02]
```

**File:** `.planning/phases/19-measurement-infrastructure/19-02-SUMMARY.md`
**Add before closing `---` of frontmatter:**
```yaml
requirements-completed: [MEAS-04]
```

**File:** `.planning/phases/19-measurement-infrastructure/19-03-SUMMARY.md`
**Add before closing `---` of frontmatter:**
```yaml
requirements-completed: [MEAS-04]
```

### keyword_bank.json Path Fix

**File:** `/Users/bobby/Documents/GitHub/Allied-FeedOps/src/feedops/integrations/keyword_bank.py`
**Current:**
```python
DEFAULT_KEYWORD_BANK_PATH = Path("data/keyword-bank.json")
```
**Fixed:**
```python
DEFAULT_KEYWORD_BANK_PATH = Path(__file__).parent / "data" / "keyword-bank.json"
```

**Also required:** Create `src/feedops/integrations/data/` directory, copy `data/keyword-bank.json` to it, and commit the file (it is NOT in `.gitignore` currently — `data/` is in `.gcloudignore` but not necessarily `.gitignore`; verify before committing).

**Verify gitignore:** `grep "^data" /Users/bobby/Documents/GitHub/Allied-FeedOps/.gitignore`

## Plan Breakdown

### 22-01-PLAN.md (Runtime Fixes)
Covers: FIX-01 (apply_feedback_layer field name), MEAS-02 (GMC_MERCHANT_ID env var), and tech debt fixes (run_at→run_timestamp, keyword_bank.json path)

Tasks:
1. Fix `apply_feedback_layer()` — edit prompt_builder.py line 309 + docstring, run Python tests
2. Set `GMC_MERCHANT_ID` in Cloud Run — retrieve MC ID, run gcloud update command, verify /gmc/sync no longer raises ValueError
3. Fix `confirmed_sample.last_run` — edit route.ts line 101, run `npm run build && npm run lint`
4. Fix `keyword_bank.json` path — create `src/feedops/integrations/data/`, move file, update DEFAULT_KEYWORD_BANK_PATH, commit

### 22-02-PLAN.md (Documentation Gaps)
Covers: MODEL-01, MODEL-02, MEAS-04 (all documentation-only)

Tasks:
1. Add `requirements-completed: [MODEL-01, MODEL-02]` to 17-02-SUMMARY.md frontmatter
2. Add `requirements-completed: [MEAS-04]` to 19-02-SUMMARY.md frontmatter
3. Add `requirements-completed: [MEAS-04]` to 19-03-SUMMARY.md frontmatter

## State of the Art

| Old State | Current State (after Phase 22) | Impact |
|---|---|---|
| apply_feedback_layer() extracts correction.get("text") | Extracts correction.get("correction_text") first | Persistent corrections produce correct prompt text |
| GMC_MERCHANT_ID not set in Cloud Run | GMC_MERCHANT_ID set in Cloud Run service | /gmc/sync E2E flow operational |
| confirmed_sample.last_run always null | Shows actual run_timestamp from JSON | Dashboard funnel shows real last-run date |
| keyword_bank.json absent from container | Included in src/ tree, copied to container | Evidence builder has external keywords in Cloud Run |
| 17-02-SUMMARY missing requirements-completed | Has requirements-completed: [MODEL-01, MODEL-02] | REQUIREMENTS.md traceability table complete |
| 19-02 and 19-03 SUMMARY missing requirements-completed | Both have requirements-completed: [MEAS-04] | MEAS-04 shows as satisfied in audit |

## Open Questions

1. **What is the actual GMC Merchant Center ID?**
   - What we know: It is distinct from Google Ads customer ID (6253381786), noted in Phase 17-01 decisions
   - What's unclear: The exact numeric ID is not documented in any tracked config file
   - Recommendation: Check the Merchant Center account UI at merchants.google.com, or search dashboard source code for any hardcoded MC IDs

2. **Is data/keyword-bank.json committed to git?**
   - What we know: The file exists at `/Users/bobby/Documents/GitHub/Allied-FeedOps/data/keyword-bank.json` locally; `data/` is excluded from Cloud Run builds via `.gcloudignore`
   - What's unclear: Whether `data/` is also in `.gitignore` (which would mean it's NOT committed and can't be moved to `src/` without first obtaining the file from a separate source)
   - Recommendation: `git ls-files data/keyword-bank.json` to confirm it's tracked in git before the fix task begins

3. **Does 19-02-SUMMARY or 19-03-SUMMARY frontmatter use YAML list format or block sequence?**
   - What we know: 17-01-SUMMARY and 19-04-SUMMARY use inline list: `[GOOG-01, GOOG-03]`
   - What's unclear: Whether 19-02 and 19-03 already have other list fields that set a local convention
   - Recommendation: Use inline list format `[MEAS-04]` to match the established pattern in all other SUMMARY files

## Sources

### Primary (HIGH confidence)
- Direct file reads: `src/feedops/api/prompt_builder.py` (verified at lines 290-326)
- Direct file reads: `dashboard/src/app/api/funnel/summary/route.ts` (verified at lines 85-107)
- Direct file reads: `.planning/phases/18-diagnosis-establish-ground-truth/spot-check-results.json` (confirmed `run_timestamp` field)
- Direct file reads: `src/feedops/integrations/merchant_api.py` (confirmed ValueError on missing GMC_MERCHANT_ID)
- Direct file reads: `src/feedops/integrations/keyword_bank.py` (confirmed DEFAULT_KEYWORD_BANK_PATH = `data/keyword-bank.json`)
- Direct file reads: `.gcloudignore` (confirmed `data/` excluded, no negation patterns)
- Direct file reads: `Dockerfile` (confirmed only `src/` and `pyproject.toml` COPY'd, no `data/`)
- Direct file reads: `17-02-SUMMARY.md`, `19-02-SUMMARY.md`, `19-03-SUMMARY.md` (confirmed missing `requirements-completed` field)
- Direct file reads: `17-01-SUMMARY.md`, `19-04-SUMMARY.md` (confirmed correct `requirements-completed` pattern)
- Direct file reads: `v1.2-MILESTONE-AUDIT.md` (full audit with root causes and line references)
- Direct file reads: `21-01-SUMMARY.md` (confirmed migrations 034+035 applied to live Supabase)

### Secondary (MEDIUM confidence)
- REQUIREMENTS.md traceability table — shows MODEL-01, MODEL-02, MEAS-02, MEAS-04, FIX-01 all "Pending" assigned to Phase 22

## Metadata

**Confidence breakdown:**
- Bug fix locations: HIGH — file paths and line numbers verified by direct read
- GMC_MERCHANT_ID fix: HIGH for approach; MEDIUM for actual MC ID value (not yet retrieved)
- SUMMARY frontmatter format: HIGH — pattern verified from multiple existing correct files
- keyword_bank.json fix approach: HIGH for Move-to-src strategy; MEDIUM on git tracking status (needs `git ls-files` check)
- .gcloudignore negation limitation: MEDIUM — noted from pattern observation, not official GCP docs

**Research date:** 2026-02-21
**Valid until:** 2026-03-21 (stable domain — no external dependencies that could change)
