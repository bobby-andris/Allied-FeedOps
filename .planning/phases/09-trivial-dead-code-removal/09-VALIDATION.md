---
phase: 9
slug: trivial-dead-code-removal
status: draft
nyquist_compliant: false
wave_0_complete: false
created: 2026-03-03
---

# Phase 9 — Validation Strategy

> Per-phase validation contract for feedback sampling during execution.

---

## Test Infrastructure

| Property | Value |
|----------|-------|
| **Framework** | pytest (installed in `.venv`) |
| **Config file** | `pyproject.toml` — `[tool.pytest.ini_options]`, testpaths=["tests"], asyncio_mode="auto" |
| **Quick run command** | `.venv/bin/pytest tests/test_pipeline.py tests/test_hybrid_generation_parity.py -q --tb=short` |
| **Full suite command** | `.venv/bin/pytest tests/ -q --tb=short` |
| **Estimated runtime** | ~37 seconds |

---

## Sampling Rate

- **After every task commit:** Run `.venv/bin/pytest tests/ -q --tb=short`
- **After every plan wave:** Run `.venv/bin/pytest tests/ -q --tb=short`
- **Before `/gsd:verify-work`:** Full suite must be green
- **Max feedback latency:** 37 seconds

---

## Per-Task Verification Map

| Task ID | Plan | Wave | Requirement | Test Type | Automated Command | File Exists | Status |
|---------|------|------|-------------|-----------|-------------------|-------------|--------|
| 09-01-01 | 01 | 1 | DEAD-01 | import smoke | `.venv/bin/pytest tests/test_pipeline.py -q --tb=short` | ✅ | ⬜ pending |
| 09-01-02 | 01 | 1 | DEAD-01 | import smoke | `.venv/bin/pytest tests/test_pipeline.py -q --tb=short` | ✅ | ⬜ pending |
| 09-01-03 | 01 | 1 | DEAD-01 | lint | `.venv/bin/ruff check src/feedops/api/finish_processing.py src/feedops/api/generation.py` | ✅ | ⬜ pending |
| 09-02-01 | 02 | 1 | DEAD-05 | grep + pytest | `grep -rn "FEEDOPS_VARIANT_AT_LLM_TIME" src/ && .venv/bin/pytest tests/ -q --tb=short` | ✅ | ⬜ pending |
| 09-02-02 | 02 | 1 | DEAD-05 | lint | `.venv/bin/ruff check src/feedops/pipeline/generator.py src/feedops/pipeline/reporter.py src/feedops/pipeline/finish_injection.py` | ✅ | ⬜ pending |

*Status: ⬜ pending · ✅ green · ❌ red · ⚠️ flaky*

---

## Wave 0 Requirements

Existing infrastructure covers all phase requirements. No new test files needed.

---

## Manual-Only Verifications

| Behavior | Requirement | Why Manual | Test Instructions |
|----------|-------------|------------|-------------------|
| FEEDOPS_VARIANT_AT_LLM_TIME fully removed | DEAD-05 | Structural grep check | `grep -rn "FEEDOPS_VARIANT_AT_LLM_TIME" src/` → must return 0 results |

---

## Validation Sign-Off

- [ ] All tasks have `<automated>` verify or Wave 0 dependencies
- [ ] Sampling continuity: no 3 consecutive tasks without automated verify
- [ ] Wave 0 covers all MISSING references
- [ ] No watch-mode flags
- [ ] Feedback latency < 37s
- [ ] `nyquist_compliant: true` set in frontmatter

**Approval:** pending
