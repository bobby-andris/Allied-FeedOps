# P1 GMC Structured-Only Supplemental Feed Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use `superpowers:executing-plans` to implement this plan task-by-task.

**Goal:** Add an opt-in “structured-only” mode for Google Merchant Center supplemental feed publishing so AI-generated titles/descriptions are emitted as `structured_title` / `structured_description` (and not `title` / `description`) to support compliance and future-proofing.

**Architecture:** Keep existing RSS 2.0 supplemental feed output unchanged by default. When `FEEDOPS_GMC_STRUCTURED_ONLY=true`, emit `<g:structured_title>` and `<g:structured_description>` blocks (with `digital_source_type` + `content`) and omit `<g:title>`, `<g:description>`, and `<g:short_title>`.

**Tech Stack:** Python, ElementTree, pytest.

---

### Task 1: Add failing test for structured-only output

**Files:**
- Create: `tests/test_google_supplemental_structured.py`
- Modify: `src/feedops/integrations/google_supplemental.py`

**Step 1: Write the failing test**

Create `tests/test_google_supplemental_structured.py`:

```python
from feedops.integrations.google_supplemental import generate_supplemental_feed


def test_generate_supplemental_feed_structured_only_emits_structured_fields(monkeypatch):
    monkeypatch.setenv("FEEDOPS_GMC_STRUCTURED_ONLY", "true")

    patch = {
        "offerId": "shopify_US_1_1",
        "title": "Fallback Title",
        "description": "Fallback Description",
        "structured_title": {
            "digital_source_type": "trained_algorithmic_media",
            "content": "Structured Title",
        },
        "structured_description": {
            "digital_source_type": "trained_algorithmic_media",
            "content": "Structured Description",
        },
        "variants": [],
    }

    xml = generate_supplemental_feed([patch], environment="staging", include_variants=False)

    assert "<g:structured_title>" in xml
    assert "<g:structured_description>" in xml
    assert "Structured Title" in xml
    assert "Structured Description" in xml

    # Must not include plain title/description in structured-only mode
    assert "<g:title>" not in xml
    assert "<g:description>" not in xml
```

**Step 2: Run test to verify it fails**

Run:
`PYTHONPATH=./src .venv/bin/python -m pytest -q tests/test_google_supplemental_structured.py`

Expected: FAIL (structured tags not present).

---

### Task 2: Implement structured-only mode (minimal)

**Files:**
- Modify: `src/feedops/integrations/google_supplemental.py`

**Step 1: Add env flag**

Read `FEEDOPS_GMC_STRUCTURED_ONLY` as a boolean.

**Step 2: Emit structured elements**

When enabled:
- Create `<g:structured_title>` / `<g:structured_description>` children.
- Inside each, emit `<g:digital_source_type>` and `<g:content><![CDATA[...]]></g:content>`.
- Omit `<g:title>`, `<g:description>`, and `<g:short_title>`.
- Prefer `structured_*['content']` if present, else fallback to the plain field.
- Prefer `structured_*['digital_source_type']` if present, else default to `trained_algorithmic_media`.

**Step 3: Verify the test passes**

Run:
`PYTHONPATH=./src .venv/bin/python -m pytest -q tests/test_google_supplemental_structured.py`

Expected: PASS.

---

### Task 3: Run full test suite

Run:
`PYTHONPATH=./src .venv/bin/python -m pytest -q`

Expected: PASS.

---

### Task 4: Document the required GMC configuration (ops note)

**Files:**
- Update: `docs/plans/2026-01-29-p1-ultrathink-content-strategy.md`

Add a short “Operational note”:
- Google ignores `structured_*` if `title/description` are present in the combined item.
- If the primary feed provides `title/description`, a Merchant Center **Feed Rule** may be required to clear those fields for `custom_label_4=feedops-*` items so `structured_*` is used.

