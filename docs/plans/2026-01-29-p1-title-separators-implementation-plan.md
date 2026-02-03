# P1 Title Separators + Prompt Alignment Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use `superpowers:executing-plans` to implement this plan task-by-task.

**Goal:** Align FeedOps title generation rules with current AGENTS.md guidance: reduce pipe-heavy titles, prefer clean punctuation, and allow evidence-gated functional modifiers without breaking the pipeline/dashboard.

**Architecture:** This is a prompt/validator behavior change, not a schema change. We update the generator prompt (`src/feedops/pipeline/prompts.py`) and soft validations (`src/feedops/pipeline/validators.py`) so outputs are guided toward commas/hyphens while remaining backwards-compatible with existing titles that contain pipes.

**Tech Stack:** Python, pytest.

---

### Task 1: Add tests for `validate_title_structure`

**Files:**
- Create: `tests/test_title_validators.py`
- Modify: `src/feedops/pipeline/validators.py`

**Step 1: Write the failing test**

Create `tests/test_title_validators.py`:

```python
from feedops.pipeline.validators import validate_title_structure


def test_validate_title_structure_accepts_hyphen_separator():
    warnings = validate_title_structure(
        "18-Inch Wall Mount Towel Bar - Solid Brass - Allied Brass",
        field="google_title",
    )
    assert not any("separator" in w.lower() for w in warnings)


def test_validate_title_structure_accepts_comma_separator():
    warnings = validate_title_structure(
        "18-Inch Wall Mount Towel Bar, Solid Brass, Allied Brass",
        field="google_title",
    )
    assert not any("separator" in w.lower() for w in warnings)


def test_validate_title_structure_warns_when_no_separator_present():
    warnings = validate_title_structure(
        "18-Inch Wall Mount Towel Bar Solid Brass Allied Brass",
        field="google_title",
    )
    assert any("separator" in w.lower() for w in warnings)
```

**Step 2: Run test to verify it fails**

Run:
`PYTHONPATH=./src .venv/bin/python -m pytest -q tests/test_title_validators.py`

Expected: FAIL because validator currently only recognizes ` | ` or ` - `.

**Step 3: Write minimal implementation**

Update `validate_title_structure` separator logic to accept:
- ` | `
- ` - `
- `,`

**Step 4: Run test to verify it passes**

Run:
`PYTHONPATH=./src .venv/bin/python -m pytest -q tests/test_title_validators.py`

Expected: PASS.

---

### Task 2: Update prompt title separator guidance (backwards-compatible)

**Files:**
- Modify: `src/feedops/pipeline/prompts.py`

**Step 1: Write the failing test (if needed)**

Skip if no prompt snapshot tests exist.

**Step 2: Implement minimal prompt change**

Change title instructions from “Use pipe separators” to:
- Prefer commas/hyphens between segments for readability
- Avoid symbol-heavy formatting
- Keep “Allied Brass” last but don’t require a pipe specifically

**Step 3: Run full test suite**

Run:
`PYTHONPATH=./src .venv/bin/python -m pytest -q`

Expected: PASS.

---

### Task 3: Clarify “no adjectives” rule to allow verified functional modifiers

**Files:**
- Modify: `src/feedops/pipeline/prompts.py`

**Step 1: Update prompt text**

Replace “NEVER start titles with adjectives” with:
- Never start with generic marketing adjectives (“Premium”, “High-Quality”, etc.)
- Starting with verified functional modifiers is OK (“ADA-Compliant”, “Retractable”, “Tilt-Adjustable”)

**Step 2: Run full test suite**

Run:
`PYTHONPATH=./src .venv/bin/python -m pytest -q`

Expected: PASS.

---

### Task 4: Optional: Align dashboard candidate examples later (non-blocking)

This is not required for correctness. Only do it if we want the dashboard samples to reflect the new style for reviewers.

