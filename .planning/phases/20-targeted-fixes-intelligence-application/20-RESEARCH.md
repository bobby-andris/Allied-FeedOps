# Phase 20: Targeted Fixes & Intelligence Application - Research

**Researched:** 2026-02-21
**Domain:** Python pipeline prompt engineering, feature flag wiring, LLM provider configuration, image generation guidance
**Confidence:** HIGH (all findings verified against actual codebase)

---

<user_constraints>
## User Constraints (from CONTEXT.md)

### Locked Decisions

**Prompt parity (FIX-01)**
- Shared module approach: extract prompt construction into a common module that both single-SKU and batch paths import
- Base prompt is identical for both paths (segment strategy, keyword plan, gold examples, Shopping intelligence)
- Single-SKU path layers user feedback on top of the shared base prompt
- Feedback is additive — enriches the base prompt, doesn't fork it
- Pattern: `batch = core_prompt(sku) → model` / `single-SKU = core_prompt(sku) + feedback_layer → model`

**User feedback on single-SKU regeneration**
- Structured controls + free-text: tone/style selector, content emphasis (finish, dimensions, use case, compatibility, luxury positioning), length control (title and description independently), plus free-text for anything else
- Feedback weighting: user corrections are strongly weighted but model can still balance against SEO/Shopping best practices (weighted blend, not hard override)
- Persistent corrections: feedback saved per SKU record — every future regeneration for that SKU automatically includes prior corrections
- Addresses the recurring issue of prompts ignoring feedback: persistent corrections accumulate, so repeated issues get resolved permanently

**Feature flag activation (FIX-02)**
- Wire PROMPT_CONTRACT_V2 and INTENT_CURATOR_V1 to active generation code paths
- Toggling a flag must produce an observably different prompt structure
- Implementation details at Claude's discretion

**Google Shopping prompt integration (GOOG-04)**
- Separate "Google Shopping Optimization" section in the prompt — distinct from base rules, independently updatable
- Three-layer intelligence hierarchy:
  1. Universal rules — fundamental Shopping ranking factors that apply to all products
  2. Category-specific guidance — varies by custom_label_0 (60 product categories driving Shopping funnels)
  3. Product-type/product-specific intelligence — auto-inferred from search term data, competitor patterns, and product attributes
- Curated + auto-inferred: system auto-generates category intelligence, manual overrides/additions take priority
- Storage: Claude's discretion with lean toward Python YAML/config files (version-controlled, reviewable, deploys as a unit)
- Allied Brass USP: products are both beautifully designed AND highly functional
- custom_label_0 is the primary segmentation key

**Image generation guidance (GOOG-05)**
- Balance lifestyle aspiration with product clarity — product fidelity is the non-negotiable constraint
- Product must be indistinguishable from the actual physical product
- Three-dimensional image intelligence:
  1. Category — drives the scene environment
  2. Finish — drives lighting and material rendering
  3. Collection — drives staging style/environment
- Collection descriptions already exist in database (imported from `data/Collection_Descriptions_Complete_All_41_20260124.csv`)

**Model switch (MODEL-03)**
- Straight switch to GPT-5.2 — benchmarks are clear (90.0/100 vs GPT-4o at 76.4/100), no A/B needed
- Implementation: change model param, change `max_tokens` to `max_completion_tokens`, strengthen accuracy guardrail
- Cost is negligible (under $20 for full 2,784 SKU catalog at batch pricing)
- Fallback strategy: Claude's discretion (configurable vs hardcoded)

### Claude's Discretion
- Feature flag implementation approach (how PROMPT_CONTRACT_V2 and INTENT_CURATOR_V1 wire to code paths)
- Intelligence storage format (YAML vs JSON config, exact file structure) — lean toward Python config files
- Model configurability (env var vs hardcode for GPT-5.2)
- Exact structured feedback UI components (specific control designs)
- How auto-inferred category intelligence is generated and refreshed

### Deferred Ideas (OUT OF SCOPE)
- Gemini 2.5 Pro as offline batch generation alternative — future phase when batch volume warrants it
- Dashboard UI for editing category-specific intelligence rules — future phase (for now, config files are sufficient)
- Collection description enrichment/updates — verify database import is complete, but collection data management is separate scope
</user_constraints>

---

<phase_requirements>
## Phase Requirements

| ID | Description | Research Support |
|----|-------------|-----------------|
| FIX-01 | UI single-SKU regeneration path (/regenerate) uses the same rich prompt construction as batch path (segment strategy, keyword plan, gold examples from generator.py) | Codebase audit confirmed: main.py::_build_generation_user_prompt() is a simpler builder that lacks keyword_placement, segment_strategy, and uses per-platform gold examples instead of bundle examples. generator.py::build_split_prompt() is the rich path used by the legacy 6-agent pipeline. The fix is to make /regenerate call the same rich construction logic. |
| FIX-02 | Unwired feature flags (PROMPT_CONTRACT_V2, INTENT_CURATOR_V1) are connected to active generation code paths with observable activation | Phase 18 confirmed: PROMPT_CONTRACT_V2 is wired in prompt_loader.py (controls system prompt source). INTENT_CURATOR_V1 is wired in evidence.py. But neither produces a structurally different prompt when toggled — they select between fallback (DB) vs canonical (code) prompt, and enable/disable intent curation within evidence. The fix is to make each flag produce an observable structural difference in the output prompt. |
| GOOG-04 | Update content generation prompts to reflect Google Shopping ranking intelligence | 15 specific prompt change recommendations documented in docs/research/google-shopping-ranking-factors.md and docs/research/competitive-gap-analysis.md. Key changes: lead with finish + product type in first 70 chars, add "Decorative" for grab bars, include "Solid Brass" differentiator, front-load specs in first 160 chars of description. Storage: new Python YAML/config for Shopping intelligence layer. |
| GOOG-05 | Image generation guidance updated to reflect Google Shopping visual ranking factors | Lifestyle image generation currently in src/feedops/pipeline/lifestyle_images.py. Collection descriptions already loaded via collection_descriptions.py from the CSV. The fix is to wire finish metadata, collection design DNA, and category scene guidance into the image generation prompt. |
| MODEL-03 | Implement model switch in Python pipeline | ALREADY PARTIALLY DONE: OpenAIProvider defaults to gpt-5.2 in src/feedops/providers/openai_provider.py (line 36). factory.py defaults to gpt-5.2 when no FEEDOPS_OPENAI_MODEL env var is set (lines 47, 55, 69). The max_completion_tokens fix is already implemented (line 143 uses max_completion_tokens for gpt-5.x models). Only gap: accuracy guardrail strengthening in SYSTEM_PROMPT. |
</phase_requirements>

---

## Summary

Phase 20 applies the intelligence gathered in Phases 17-19 to the production content and image generation pipeline. The research reveals that several of the "fixes" are partially implemented or already done — the codebase has evolved significantly since Phases 17-18 documented the gaps.

**FIX-01 (prompt parity)** is the most substantive engineering change. The single-SKU regeneration path in `main.py` uses `_build_generation_user_prompt()` — a simpler builder that lacks keyword placement planning, segment strategy resolution, and uses per-platform gold examples rather than the cross-platform bundle. The batch path uses the same `_build_generation_user_prompt()` but `generator.py`'s richer `build_split_prompt()` is only called by the legacy 6-agent pipeline. The fix is to extract prompt construction into a shared module that both paths invoke. The persistent feedback addition (new `sku_corrections` table) is a net-new capability with no existing code.

**FIX-02 (feature flags)** is already partially done. All 3 flags (`PROMPT_CONTRACT_V2`, `INTENT_CURATOR_V1`, `SEGMENT_STRATEGY_V1`) default to True and are wired to code paths. The gap is observability: toggling a flag currently selects between code-owned vs DB-owned system prompt (PROMPT_CONTRACT_V2) or enables/disables intent curation evidence (INTENT_CURATOR_V1) but does not produce a clearly structured difference in the serialized prompt. The fix is to add Shopping intelligence sections (GOOG-04) and wire them to the flags to make activation observable.

**MODEL-03 (GPT-5.2 switch)** is effectively already done. `openai_provider.py` defaults to `gpt-5.2` with proper `max_completion_tokens` handling. The only remaining work is verifying no lingering `gpt-4o` references and strengthening the accuracy guardrail in the system prompt.

**GOOG-04/GOOG-05 (Shopping intelligence)** require creating a new intelligence configuration (recommended: Python YAML) and wiring it into `_build_generation_user_prompt()` for content and `generate_lifestyle_images_for_sku()` for images. The 41-collection design DNA is already loaded via `collection_descriptions.py`. The segment strategy module already handles `custom_label_0` mapping for the content path.

**Primary recommendation:** Implement in this order: (1) model confirmation/accuracy guardrail, (2) Shopping intelligence YAML + integration into prompts, (3) shared prompt module / prompt parity, (4) persistent corrections table + API changes, (5) image generation wiring, (6) feature flag observable activation.

---

## Standard Stack

### Core (No New Dependencies Required)

| Library | Version | Purpose | Why Standard |
|---------|---------|---------|--------------|
| Python YAML | stdlib `yaml` (PyYAML) | Shopping intelligence config storage | Already in Python environment; version-controlled, reviewable, deploys with code |
| FastAPI/Pydantic | Existing | Extended RegenerateRequest with feedback fields | Already the API framework |
| Supabase Python client | Existing | New `sku_corrections` table for persistent feedback | Already configured |
| OpenAI Python SDK | Existing | GPT-5.2 already wired | Model string is the only change needed |

### Supporting

| Library | Version | Purpose | When to Use |
|---------|---------|---------|-------------|
| `functools.lru_cache` | stdlib | Cache loaded YAML intelligence config | Use same pattern as `_load_collection_descriptions()` in collection_descriptions.py |
| `hashlib` | stdlib | Hash Shopping intelligence config for prompt hash lineage | Consistent with existing `get_system_prompt_hash()` pattern |

### Alternatives Considered

| Instead of | Could Use | Tradeoff |
|------------|-----------|----------|
| YAML config file | Supabase DB table | YAML deploys atomically with code (no migration needed), is reviewable in git, works offline. DB table needs migration + admin UI. Choose YAML. |
| YAML config file | JSON config file | YAML is more human-readable and supports comments. Both work. YAML preferred for intelligence that humans will review and edit. |
| Persistent corrections in Supabase | In-memory accumulation | Supabase is the right choice — corrections must survive container restarts and be auditable. |

---

## Architecture Patterns

### Recommended Project Structure for Phase 20

```
src/feedops/
├── pipeline/
│   ├── prompts.py                    # EXISTING: SYSTEM_PROMPT — add Shopping intelligence section here
│   ├── shopping_intelligence.py      # NEW: load/cache YAML intel, format for injection
│   ├── segment_strategy.py           # EXISTING: custom_label_0 → SegmentStrategy mapping
│   ├── collection_descriptions.py    # EXISTING: 41-collection design DNA (already loads CSV)
│   └── lifestyle_images.py           # EXISTING: add collection/finish/category guidance injection
├── api/
│   ├── prompt_builder.py             # NEW: shared core_prompt() + feedback_layer() functions
│   ├── prompt_loader.py              # EXISTING: keep as system prompt cache/loader
│   └── main.py                       # EXISTING: wire to prompt_builder.py
└── config/
    └── shopping_intelligence.yaml    # NEW: Google Shopping intelligence config (GOOG-04)
```

### Pattern 1: Shared Prompt Module (FIX-01)

**What:** Extract `_build_generation_user_prompt()` from main.py into a dedicated `prompt_builder.py` that both `/regenerate` and `/batch-optimize` call. The richer construction logic from `generator.py::build_split_prompt()` feeds into this.

**When to use:** All generation paths — both endpoints call the same `build_core_prompt(parent_sku, platform, content_type)`.

**Current gap (verified from codebase):**

The current `_build_generation_user_prompt()` in `main.py` (lines 439-505) builds:
- category_guidance (from `get_category_guidance()` + fallback to `build_category_guidance()`)
- examples (from `format_gold_standard_examples()` — per-platform)
- context section (finish handling)
- feedback section (simple text append)

What is MISSING vs `generator.py::build_split_prompt()` (lines 140-172):
- `keyword_placement` — built via `build_keyword_placement_plan()` + `format_keyword_placement_section()`
- `segment_strategy_guidance` — built via `_resolve_segment_strategy()` + `format_segment_strategy_guidance()`
- Cross-platform gold examples bundle (`format_gold_standard_examples_bundle()` vs per-platform `format_gold_standard_examples()`)
- Shopping intelligence section (to be added in GOOG-04)

**Target architecture:**
```python
# src/feedops/api/prompt_builder.py

def build_core_prompt(
    parent_sku: ParentSKU,
    platform: str,
    content_type: str,
    evidence_markdown: str,
) -> str:
    """Build rich prompt — identical for batch and single-SKU paths."""
    # keyword_placement from build_keyword_placement_plan()
    # segment_strategy from _resolve_segment_strategy()
    # gold_examples from format_gold_standard_examples_bundle()
    # shopping_intelligence from get_shopping_intelligence()
    # category_guidance from get_category_guidance()
    ...

def build_feedback_layer(
    corrections: list[dict],   # persistent corrections from sku_corrections table
    session_feedback: str | None,  # current-session user input
) -> str:
    """Build feedback section to layer on top of core prompt."""
    ...
```

### Pattern 2: Persistent Corrections Table (FIX-01 feedback)

**What:** New Supabase table `sku_corrections` stores per-SKU, per-platform corrections that are automatically prepended to every regeneration.

**Schema:**
```sql
CREATE TABLE sku_corrections (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    master_sku TEXT NOT NULL,
    platform TEXT NOT NULL,  -- 'google' | 'bing' | 'shopify' | 'all'
    content_type TEXT NOT NULL,  -- 'title' | 'description' | 'all'
    correction_text TEXT NOT NULL,
    correction_type TEXT NOT NULL,  -- 'tone' | 'emphasis' | 'length' | 'free_text'
    is_active BOOLEAN DEFAULT TRUE,
    created_at TIMESTAMPTZ DEFAULT NOW(),
    created_by TEXT,  -- for audit trail
    UNIQUE (master_sku, platform, content_type, correction_type, correction_text)
);
```

**API change to RegenerateRequest:**
```python
class RegenerateRequest(BaseModel):
    master_sku: str
    content_type: Literal["title", "description"]
    platform: Literal["google", "bing", "shopify"]
    feedback: str | None = None
    finish_code: str | None = None
    # NEW: structured feedback fields
    tone_style: Literal["formal", "conversational", "technical", "aspirational"] | None = None
    emphasis: list[Literal["finish", "dimensions", "use_case", "compatibility", "luxury"]] | None = None
    length_preference: Literal["shorter", "standard", "longer"] | None = None
    save_as_correction: bool = False  # if True, save to sku_corrections
```

**Prompt injection pattern:**
```
Persistent Corrections for this SKU:
[list of active corrections from sku_corrections]

Session Feedback:
[current user input]
```

### Pattern 3: Shopping Intelligence YAML (GOOG-04)

**What:** Python YAML file at `src/feedops/config/shopping_intelligence.yaml` with three-tier structure. Loaded once, cached via `lru_cache`, injected as a new section in the prompt.

**File structure:**
```yaml
# src/feedops/config/shopping_intelligence.yaml

version: "1.0"
last_updated: "2026-02-21"

universal_rules:
  title_structure:
    description: "Lead with finish + product type in first 70 characters"
    rule: "Title MUST open with [Finish Name] [Size] [Product Type]. Never lead with collection name or brand."
    example: "Polished Nickel 24-Inch Solid Brass Towel Bar - Waverly Place - Allied Brass"
  material_differentiator:
    rule: "Include 'Solid Brass' in every title. Differentiates from zinc alloy competitors."
  description_structure:
    rule: "First sentence of description: [Finish] [Product Type] for bathroom installation. [Material]. [Key dimension]. [Key functional claim]."
  finish_specificity:
    rule: "Integrate finish name naturally in first sentence. Never use 'Available in [Finish].' pattern."

category_rules:
  "grab bars":
    intent_keywords: ["decorative", "designer", "ADA compliant"]
    title_instruction: "Include 'Decorative' or 'Designer' for decorative grab bars. Include 'ADA Compliant' for ADA products."
    size_instruction: "Lead with size — 'XX-Inch' at position 2-3 in title (size-specific searches have 4.12% CTR)"
    evidence: "741 decorative grab bar impressions at 0% CTR traced to title language mismatch"
  "towel bars":
    intent_keywords: ["wall mounted towel bar", "towel rack", "towel holder"]
    synonym_instruction: "Include towel bar/rack/holder synonyms. 70,866 impressions/month = highest volume category."
    differentiation: "Lead with construction quality: solid brass vs zinc alloy"
  "garment rods":
    intent_keywords: ["garment rod", "wardrobe rod", "closet rod"]
    note: "54.9% IS lost to rank — highest priority for content improvement"
  "paper towel holders":
    intent_keywords: ["paper towel holder", "kitchen paper towel", "wall mount paper towel"]
    note: "54,761 impressions/month; 36.7% IS lost to rank"
  "retractable hooks":
    note: "57.4% IS lost to rank — high priority"

allied_brass_usp:
  dual_positioning: "Allied Brass products are both beautifully designed AND highly functional. Always reflect both."
  solid_brass_quality: "Solid brass construction is the primary material differentiator vs zinc alloy competitors."
  finish_variety: "28 finishes including specialty options (Unlacquered Brass, Venetian Bronze) that competitors don't offer."
```

**Loading pattern (mirrors collection_descriptions.py):**
```python
# src/feedops/pipeline/shopping_intelligence.py

@lru_cache(maxsize=1)
def _load_shopping_intelligence() -> dict:
    """Load Shopping intelligence config. Cached for container lifetime."""
    path = Path(__file__).parent.parent / "config" / "shopping_intelligence.yaml"
    with path.open() as f:
        return yaml.safe_load(f)

def get_universal_rules() -> str:
    """Format universal Shopping rules for prompt injection."""
    ...

def get_category_intelligence(custom_label_0: str | None) -> str:
    """Format category-specific Shopping rules for prompt injection."""
    ...
```

### Pattern 4: Image Generation Guidance Wiring (GOOG-05)

**What:** Wire collection design DNA + finish lighting guidance + category scene guidance into `generate_lifestyle_images_for_sku()` in `lifestyle_images.py`.

**Current state (verified):** The function exists in `lifestyle_images.py` and takes `master_sku`, `num_variations`, `dry_run`, `force_finish_code`. It already selects finish via Google Ads performance data. The image prompt construction is inside this function.

**Missing pieces:**
1. Collection design DNA injection — `collection_descriptions.py` already loads the 41-collection CSV with "Design" keywords column
2. Finish lighting guidance — not currently in prompt
3. Category scene guidance — not currently in prompt

**Target prompt structure for image generation:**
```
Generate a lifestyle image for: [Product Type] in [Finish Name] finish, [Collection Name]

PRODUCT FIDELITY (NON-NEGOTIABLE):
- The [Finish Name] finish must be rendered exactly. [Finish-specific lighting instruction]
- Product dimensions and design details must be indistinguishable from the actual product.
- Product must be the focal point of the scene.

SCENE ENVIRONMENT:
- Category: [product type] → [scene type]. Example: grab bar → accessible bathroom with modern fixtures
- Collection: [Collection Name] — [design keywords from CSV]. Environment should evoke [style group/subgroup].
- Finish lighting: [Oil Rubbed Bronze → warm directional lighting | Polished Chrome → bright diffuse | Matte Black → studio even lighting]

COMPOSITION:
- Product occupies 50-70% of frame
- Scene enhances product, never competes with it
- Professional interior photography style
```

### Pattern 5: Feature Flag Observable Activation (FIX-02)

**Current state (verified from Phase 18 audit):**
- `PROMPT_CONTRACT_V2` is in `prompt_loader.py:149` — when disabled, falls back to DB system prompt. When enabled, uses Python code-owned SYSTEM_PROMPT. Already active.
- `INTENT_CURATOR_V1` is in `evidence.py:371` and `evidence.py:348` — controls whether search query intent curation is applied to evidence building. Already active.
- `SEGMENT_STRATEGY_V1` is in `generator.py:100` (legacy-only) and presumably `evidence.py:348` — controls segment strategy application.

**The observable activation gap:** None of these flags currently change the *structure* of the serialized prompt in a way that's visible in `regeneration_history.user_prompt`. Adding the Shopping intelligence section (GOOG-04) wired to a flag would provide observable activation.

**Recommended FIX-02 approach:** Wire the Shopping intelligence section to `PROMPT_CONTRACT_V2`. When enabled (default), the prompt includes the full Shopping intelligence section. When disabled, it falls back to the simpler legacy prompt without Shopping intelligence. This makes the flag's effect measurable and auditable via `regeneration_history.user_prompt`.

### Anti-Patterns to Avoid

- **Forking the prompt**: Do not create separate `_build_single_sku_prompt()` and `_build_batch_prompt()` functions. Single shared module with a feedback layer on top.
- **Modifying SYSTEM_PROMPT for Shopping intelligence**: Shopping intelligence belongs in the user prompt (dynamic, per-SKU section), not the system prompt. This preserves prompt caching.
- **Hardcoding collection data in prompts.py**: Collection data comes from `collection_descriptions.py` which loads the CSV. Use the existing loader.
- **Adding DB lookups for intelligence config**: YAML file is the right choice. No runtime DB queries for config data.
- **Importing from main.py in generator.py**: main.py is the API entry point. The shared module should live in `api/prompt_builder.py` or `pipeline/prompt_builder.py`, imported by both main.py and generator.py.

---

## Don't Hand-Roll

| Problem | Don't Build | Use Instead | Why |
|---------|-------------|-------------|-----|
| Loading YAML config | Custom parser | `import yaml` (PyYAML, already in Python env) | Standard library-level simplicity |
| Caching YAML config | TTL cache | `@lru_cache(maxsize=1)` | Same pattern as collection_descriptions.py:36 |
| Finish lighting guidance | Custom rules engine | Static lookup dict in shopping_intelligence.py | 28 finishes, static data — simple dict is correct |
| Segment strategy per custom_label_0 | New mapping | `segment_strategy.py::resolve_segment_strategy()` | Already maps all 60+ custom_label_0 categories |
| Collection data lookup | Re-implement CSV parsing | `collection_descriptions.py::get_collection_description()` | Already implemented, cached, sanitized |
| Model configurability | Hardcode gpt-5.2 everywhere | `FEEDOPS_OPENAI_MODEL` env var (already in factory.py:38) | factory.py already reads this env var |

**Key insight:** Most infrastructure already exists. The work is wiring existing pieces together and adding the Shopping intelligence layer as a new composable section.

---

## Common Pitfalls

### Pitfall 1: Assuming generator.py is On the Hot Path

**What goes wrong:** Phase 18 confirmed that `generator.py::build_split_prompt()` is NOT called for UI regeneration or standard batch jobs. It's only called by the legacy 6-agent pipeline (`optimize.py`). Planning tasks that target generator.py for FIX-01 will miss the actual production paths.

**Why it happens:** generator.py has the richest prompt construction but is a legacy path. main.py has the production paths with a simpler builder.

**How to avoid:** Target `main.py::_build_generation_user_prompt()` and create `prompt_builder.py` as a new module that replaces it. generator.py should eventually import from prompt_builder.py but that's secondary.

**Warning signs:** If a task says "modify generator.py to fix FIX-01" without also touching main.py, it's targeting the wrong file.

### Pitfall 2: Breaking Prompt Caching by Adding Dynamic Content to System Prompt

**What goes wrong:** OpenAI prompt caching requires the system prompt to be byte-for-byte identical across requests. Any per-SKU content added to SYSTEM_PROMPT would defeat caching for all requests.

**Why it happens:** The Shopping intelligence section feels like "rules" that belong in the system prompt.

**How to avoid:** Shopping intelligence goes in the user prompt (dynamic section). The system prompt stays static and cacheable. This is documented in `prompts.py:101-107`:
```
# This prompt is sent as a system/developer message. It must be byte-for-byte
# identical across requests so the OpenAI prompt cache can reuse it.
```

**Warning signs:** Any proposed change that injects per-SKU or per-category content into SYSTEM_PROMPT.

### Pitfall 3: YAML File Not Available in Cloud Run Container

**What goes wrong:** The Dockerfile only copies `src/` and `pyproject.toml`. A new YAML file at `src/feedops/config/shopping_intelligence.yaml` would be inside `src/` and would be included. But any YAML outside `src/` would not.

**Why it happens:** `data/` is excluded by `.gcloudignore`. Phase 18 confirmed `keyword_bank.json` was absent from the container for this reason.

**How to avoid:** Place YAML inside `src/feedops/config/` (inside the `src/` directory tree that is copied). Verify the path in the Dockerfile.

**Warning signs:** YAML placed in `data/`, `config/` at root, or any path not under `src/`.

### Pitfall 4: `sku_corrections` Table Missing Platform/Content_Type Matching Logic

**What goes wrong:** The persistent corrections lookup queries only `master_sku` without matching `platform` and `content_type`. A "make title shorter" correction would incorrectly apply to description regeneration too.

**Why it happens:** Simple query `WHERE master_sku = ?` misses the scoping columns.

**How to avoid:** Query pattern: `WHERE master_sku = ? AND platform IN (?, 'all') AND content_type IN (?, 'all') AND is_active = TRUE`. The `'all'` sentinel means "apply to all platforms/types for this SKU."

### Pitfall 5: Keyword Placement Plan Breaks for Single-SKU Path

**What goes wrong:** `build_keyword_placement_plan()` in `keyword_placement.py` requires the full evidence table to be built. If the single-SKU path calls it without loading the correct evidence structure, it may fail or return empty.

**Why it happens:** The keyword placement plan reads from `parent_sku.merchant_center_items` and evidence rows — same data that the batch path already builds.

**How to avoid:** The shared prompt builder must receive both `parent_sku` and `evidence_markdown`. The evidence is already being built in the `/regenerate` endpoint (lines 992-993 of main.py). Pass `parent_sku` (not just evidence_markdown) to the shared builder so keyword placement has access to raw product data.

---

## Code Examples

### Current main.py _build_generation_user_prompt() (What We're Replacing)

```python
# Source: src/feedops/api/main.py, lines 439-505
def _build_generation_user_prompt(
    parent_sku: ParentSKU,
    evidence_markdown: str,
    platform: str,
    content_type: str,
    feedback: str | None = None,
    finish_code: str | None = None,
) -> str:
    category_guidance = get_category_guidance(parent_sku.category)
    if not category_guidance:
        category_guidance = build_category_guidance(parent_sku.category)

    examples = format_gold_standard_examples(
        platform=platform, content_type=content_type, max_examples=3,
    )
    # ... feedback section, context section ...
    return f"""Product Evidence Table: {evidence_markdown}\n..."""
```

**Missing from this vs generator.py::build_split_prompt():**
- `keyword_plan = build_keyword_placement_plan(parent_sku, evidence)` — not called
- `keyword_placement = format_keyword_placement_section(keyword_plan)` — not called
- `segment_strategy = _resolve_segment_strategy(parent_sku)` — not called
- `format_segment_strategy_guidance(segment_strategy)` — not called
- `format_gold_standard_examples_bundle()` (cross-platform) vs `format_gold_standard_examples()` (per-platform)
- Shopping intelligence section — new addition

### Target prompt_builder.py (Pseudocode)

```python
# Source: NEW src/feedops/api/prompt_builder.py

from feedops.pipeline.keyword_placement import (
    build_keyword_placement_plan, format_keyword_placement_section
)
from feedops.pipeline.segment_strategy import (
    format_segment_strategy_guidance, resolve_segment_strategy
)
from feedops.pipeline.shopping_intelligence import (
    get_universal_rules, get_category_intelligence
)
from feedops.api.prompt_loader import (
    get_category_guidance, format_gold_standard_examples_bundle
)

def build_core_prompt(
    parent_sku: ParentSKU,
    evidence: list,
    evidence_markdown: str,
    platform: str,
    content_type: str,
) -> str:
    """Build rich prompt — identical for batch and single-SKU paths."""
    keyword_plan = build_keyword_placement_plan(parent_sku, evidence)
    keyword_placement = format_keyword_placement_section(keyword_plan)

    custom_label_0_values = _extract_custom_label_0_values(parent_sku)
    segment_strategy = resolve_segment_strategy(custom_label_0_values)
    segment_guidance = format_segment_strategy_guidance(segment_strategy)

    gold_examples = format_gold_standard_examples_bundle(max_examples=2)
    category_guidance = get_category_guidance(parent_sku.category) or build_category_guidance(parent_sku.category)
    shopping_intelligence = get_category_intelligence(
        custom_label_0_values[0] if custom_label_0_values else None
    )

    return _assemble_prompt(
        evidence_markdown=evidence_markdown,
        keyword_placement=keyword_placement,
        segment_guidance=segment_guidance,
        category_guidance=category_guidance,
        shopping_intelligence=shopping_intelligence,
        gold_examples=gold_examples,
        platform=platform,
        content_type=content_type,
    )

def apply_feedback_layer(
    core_prompt: str,
    corrections: list[dict],
    session_feedback: str | None,
) -> str:
    """Layer feedback on top of core prompt. Does NOT fork the base prompt."""
    if not corrections and not session_feedback:
        return core_prompt

    feedback_parts = []
    if corrections:
        feedback_parts.append("Persistent corrections for this SKU (STRONGLY WEIGHTED):")
        for c in corrections:
            feedback_parts.append(f"- {c['correction_text']}")
    if session_feedback:
        feedback_parts.append(f"Session feedback: {session_feedback}")

    return core_prompt + "\n\n" + "\n".join(feedback_parts)
```

### Shopping Intelligence Section in Prompt (Example Output)

```
=== GOOGLE SHOPPING OPTIMIZATION ===

Universal Rules:
- Title MUST open with [Finish Name] [Size] [Product Type] in first 70 characters.
  Example: "Polished Nickel 24-Inch Solid Brass Towel Bar - Waverly Place - Allied Brass"
- Include "Solid Brass" in every title — primary differentiator from zinc alloy competitors.
- Description must open with: "[Finish] [Product Type] for bathroom installation. [Material]. [Key dimension]."

Category Rules (Grab Bars):
- Include "Decorative" or "Designer" in title for decorative grab bars.
  Evidence: 741 decorative grab bar impressions at 0% CTR — title language mismatch confirmed.
- Include "ADA Compliant" for ADA-certified grab bars.
- Lead with size: "XX-Inch" at position 2-3. Size-specific terms have 4.12% CTR (highest in data).

Allied Brass USP:
- Products are both beautifully designed AND highly functional — reflect both in every piece.
- Solid brass quality and 28-finish variety are genuine differentiators from Kingston Brass/Moen/Delta.
```

### Image Generation Prompt Enhancement (GOOG-05)

```python
# Source: src/feedops/pipeline/lifestyle_images.py — wiring pattern

from feedops.pipeline.collection_descriptions import (
    get_collection_description, sanitize_collection_description
)

FINISH_LIGHTING = {
    "Oil Rubbed Bronze": "warm directional lighting with amber tones, shadows emphasize texture",
    "Polished Chrome": "bright diffuse lighting, crisp reflections, silver tones",
    "Matte Black": "even studio lighting, minimal reflections, high contrast",
    "Polished Brass": "warm golden ambient light, soft reflections",
    "Satin Nickel": "soft diffuse lighting, subtle sheen without harsh reflections",
    # ... all 28 finishes
}

CATEGORY_SCENE = {
    "grab bars": "modern accessible bathroom, tile walls, shower or tub surround",
    "towel bars": "clean bathroom wall with neutral tiles, near sink or shower",
    "paper towel holders": "kitchen counter or bathroom vanity setting",
    "garment rods": "closet or dressing room with soft lighting",
    # ... mapped to custom_label_0 segments
}

def _build_image_prompt(master_sku, product_type, finish_name, collection_name):
    collection_desc = sanitize_collection_description(
        get_collection_description(collection_name)
    )
    finish_lighting = FINISH_LIGHTING.get(finish_name, "professional even lighting")
    scene = CATEGORY_SCENE.get(product_type.lower(), "bathroom setting")

    return f"""
Generate a professional lifestyle photograph of {product_type} in {finish_name} finish.

PRODUCT FIDELITY (NON-NEGOTIABLE):
- The {finish_name} finish must be rendered with absolute precision. {finish_lighting}.
- Product details must be indistinguishable from the actual physical product.
- Product occupies 50-70% of frame as the clear focal point.

SCENE: {scene}
COLLECTION STYLE: {collection_desc if collection_desc else 'contemporary bathroom setting'}

DO NOT compromise product accuracy for scene aesthetics.
"""
```

### Supabase Migration for sku_corrections

```sql
-- supabase/migrations/036_sku_corrections.sql
CREATE TABLE sku_corrections (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    master_sku TEXT NOT NULL,
    platform TEXT NOT NULL CHECK (platform IN ('google', 'bing', 'shopify', 'all')),
    content_type TEXT NOT NULL CHECK (content_type IN ('title', 'description', 'all')),
    correction_text TEXT NOT NULL,
    correction_type TEXT NOT NULL CHECK (
        correction_type IN ('tone', 'emphasis', 'length', 'free_text')
    ),
    is_active BOOLEAN NOT NULL DEFAULT TRUE,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX idx_sku_corrections_lookup
    ON sku_corrections (master_sku, platform, content_type, is_active);
```

---

## State of the Art

| Old Approach | Current Approach | When Changed | Impact on Phase 20 |
|--------------|------------------|--------------|-------------------|
| GPT-4o as default model | GPT-5.2 as default (`gpt-5.2` in openai_provider.py:36) | Already implemented before this research | MODEL-03 is 90% done — only accuracy guardrail remains |
| `max_tokens` parameter | `max_completion_tokens` for gpt-5.x | Already implemented (openai_provider.py:143) | MODEL-03 API compat already handled |
| generator.py on production path | main.py::_build_generation_user_prompt() on production path | Phase 18 confirmed | FIX-01 targets main.py, not generator.py |
| Feature flags unobservable | All 3 flags active, wired to code paths | Phase 18/19 confirmed | FIX-02 needs observable structural difference |
| No persistent feedback | No table exists yet | N/A | New capability — needs migration + API changes |

**Already done (do not re-implement):**
- GPT-5.2 model string and max_completion_tokens (openai_provider.py)
- FEEDOPS_OPENAI_MODEL env var configurability (factory.py)
- Feature flag wiring to code paths (all 3 flags have active call sites)
- Collection description CSV loading (collection_descriptions.py)
- Segment strategy custom_label_0 mapping (segment_strategy.py)
- Evidence building + formatting for /regenerate path (main.py:992-993)

---

## Open Questions

1. **What is the exact behavior gap for INTENT_CURATOR_V1?**
   - What we know: it's in evidence.py:371 and 348, wired to production path
   - What's unclear: what changes in the evidence table when disabled vs enabled? Need to read evidence.py around those lines to understand the observable difference.
   - Recommendation: Read evidence.py around lines 348 and 371 before planning FIX-02 tasks. The flag may already produce observable differences in evidence content that flow through to the prompt.

2. **What is the format of `parent_sku.merchant_center_items` in the `/regenerate` path?**
   - What we know: `load_parent_sku_from_supabase()` loads this. The segment strategy extraction in generator.py reads `item.get("customLabel0")`.
   - What's unclear: Does the regenerate path load the same structure? Does `parent_sku` have `merchant_center_items` populated for all SKUs?
   - Recommendation: Verify `load_parent_sku_from_supabase()` populates `merchant_center_items` before assuming keyword placement and segment strategy will work in the single-SKU path.

3. **How many active custom_label_0 categories are in the database?**
   - What we know: Phase 17 found 179 campaigns with `AVD - Shopping - US - {custom_label_0} - {tier}` naming. The CONTEXT says "60 product categories driving Shopping funnels."
   - What's unclear: The exact list of custom_label_0 values — the YAML config needs entries for each.
   - Recommendation: Run `SELECT DISTINCT custom_label_0 FROM product_catalog LIMIT 100` before writing the YAML file to ensure all categories are covered.

4. **Should the accuracy guardrail strengthening for MODEL-03 go in SYSTEM_PROMPT or user prompt?**
   - What we know: SYSTEM_PROMPT is cacheable (must be static). The accuracy guardrail is a rule, not per-SKU data.
   - Recommendation: Accuracy guardrail goes in SYSTEM_PROMPT (it's a universal rule). Add it to the P0_GLOBAL_FACTUAL_RULES section as an additional constraint. This doesn't break caching since the prompt is still identical across requests.

---

## Sources

### Primary (HIGH confidence — verified against actual codebase)

- `src/feedops/api/main.py` — _build_generation_user_prompt() at lines 439-505, /regenerate endpoint at lines 954-1114
- `src/feedops/pipeline/generator.py` — build_split_prompt() at lines 140-172, confirming what main.py lacks
- `src/feedops/pipeline/prompts.py` — SYSTEM_PROMPT, USER_PROMPT_TEMPLATE structure
- `src/feedops/providers/openai_provider.py` — GPT-5.2 default (line 36), max_completion_tokens handling (line 143)
- `src/feedops/providers/factory.py` — FEEDOPS_OPENAI_MODEL env var configurability (lines 38-70)
- `src/feedops/pipeline/feature_flags.py` — All 3 flags, default True
- `src/feedops/api/prompt_loader.py` — PROMPT_CONTRACT_V2 wiring (line 149), get_system_prompt()
- `src/feedops/pipeline/collection_descriptions.py` — CSV loader, get_collection_description()
- `src/feedops/pipeline/segment_strategy.py` — custom_label_0 → SegmentStrategy mapping
- `src/feedops/pipeline/lifestyle_images.py` — generate_lifestyle_images_for_sku() (missing collection/finish wiring)
- `data/Collection_Descriptions_Complete_All_41_20260124.csv` — 41 collections with Design, Group, Subgroup columns

### Secondary (HIGH confidence — verified research documents)

- `docs/research/google-shopping-ranking-factors.md` — 15 prompt change recommendations, campaign data, title structure analysis
- `docs/research/competitive-gap-analysis.md` — Competitive gap analysis, PMax Zombie SKUs finding
- `.planning/phases/17-*/17-02-SUMMARY.md` — GPT-5.2 benchmark: 90.0/100, model switch confirmed correct
- `.planning/phases/18-*/18-01-SUMMARY.md` — Phase 18 code trace: generator.py bypass confirmed, feature flag audit
- `dashboard/src/app/api/regenerate/route.ts` — TypeScript proxy to Cloud Run, feedback text construction

### Database Schema

- No `sku_corrections` table exists (verified by searching all migrations)
- `regeneration_history` table: stores system_prompt, user_prompt, feature_flags_active, prompt_hash
- `sku_approvals`, `variant_approvals`, `generated_content` — existing approval/content tables

---

## Metadata

**Confidence breakdown:**
- Standard stack: HIGH — all findings from direct codebase inspection
- Architecture: HIGH — verified against actual main.py, generator.py, prompt_loader.py
- Pitfalls: HIGH — based on Phase 18 confirmed findings (generator.py bypass, keyword_bank.json absence)
- Shopping intelligence content: HIGH — sourced from Phase 17 research documents with live Google Ads data

**Research date:** 2026-02-21
**Valid until:** 30 days — Python pipeline changes infrequently, model defaults already confirmed
