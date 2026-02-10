# Prompt Contract (Python Runtime Canonical)

## Purpose

Define exactly how prompt logic is owned, composed, versioned, and persisted at runtime so generation behavior is deterministic and auditable.

## Ownership Contract

- Canonical runtime system prompt lives in code: `src/feedops/pipeline/prompts.py` (`SYSTEM_PROMPT`).
- Runtime retrieval and version hash live in: `src/feedops/api/prompt_loader.py`.
- Runtime assembly of user prompt context lives in: `src/feedops/api/main.py` (`_build_generation_user_prompt`).

## Data-Only Contract (Supabase)

- `prompt_templates` is data-only for:
  - `gold_standard_examples`
  - `category_guidance`
  - `platform_rules`
- `prompt_templates.system_prompt` is explicitly non-authoritative and must never override Python `SYSTEM_PROMPT`.

## Composition Contract

Every runtime generation request composes prompt input as:

1. **System prompt**
   - From `get_system_prompt()` in `prompt_loader.py`.
2. **Evidence block**
   - Structured markdown from `build_evidence_table` + `format_evidence_markdown`.
3. **Entity/platform context**
   - Google/Bing: variant-facing, finish-aware context.
   - Shopify: master-facing, finish-agnostic context.
4. **Category guidance**
   - Supabase guidance if available, fallback to code guidance.
5. **Gold standard examples**
   - Pulled from Supabase examples payload.
6. **Reviewer feedback (optional)**
   - Included only for regeneration with feedback.

## Platform/Entity Contract

- `google`, `bing` generation is variant-oriented output context.
- `shopify` generation is master-oriented storefront context.
- Shopify title policy constraints remain strict:
  - no finish names
  - no `Allied Brass` in `shopify_title`

## Finish Vocabulary Contract

- Canonical finish list is provided by `get_finish_list()` in `prompt_loader.py`.
- Runtime logic must not hardcode alternate finish keys.
- Excluded novelty finishes remain excluded from standard finish sentence generation.

## Output Contract

- Runtime regenerate response is strict JSON with:
  - required `content`
  - optional `finish_sentences` for Google/Bing descriptions
- Stored generation metadata must include canonical prompt hash.
- Score/validation logic can evolve, but prompt authority cannot move out of Python runtime.

## Persistence Contract

Python writes prompt traceability into:

- `generated_content.generation_prompt_hash`
- `regeneration_history.prompt_hash`

These fields must be set from `get_system_prompt_hash()` and not from timestamp/random hashes.

## Prohibited Patterns

- Dashboard runtime paths creating alternative system prompts.
- Supabase `system_prompt` acting as runtime override.
- Parallel hardcoded finish vocabularies.
- Hidden platform rule branching outside Python prompt assembly.

## Change Protocol

When changing prompt behavior:

1. Update canonical prompt/rules in Python.
2. Add/update tests first for changed behavior.
3. Verify prompt hash persistence remains intact.
4. Update parity checklist (`docs/plans/2026-02-10-phase-1-ts-to-python-prompt-parity-checklist.md`) if rule mapping changes.
5. Re-run full Phase 0/Phase 1 verification gates.
