---
phase: 10
slug: image-wiring
status: draft
nyquist_compliant: false
wave_0_complete: false
created: 2026-03-04
---

# Phase 10 — Validation Strategy

> Per-phase validation contract for feedback sampling during execution.

---

## Test Infrastructure

| Property | Value |
|----------|-------|
| **Framework** | pytest + pytest-asyncio (already configured) |
| **Config file** | `pyproject.toml` (project root) |
| **Quick run command** | `PYTHONPATH=./src .venv/bin/python -m pytest tests/test_image_wiring.py -x -v` |
| **Full suite command** | `PYTHONPATH=./src .venv/bin/python -m pytest tests/ -v` |
| **Estimated runtime** | ~30 seconds (full suite) |

---

## Sampling Rate

- **After every task commit:** Run `PYTHONPATH=./src .venv/bin/python -m pytest tests/test_image_wiring.py -x -v`
- **After every plan wave:** Run `PYTHONPATH=./src .venv/bin/python -m pytest tests/ -v`
- **Before `/gsd:verify-work`:** Full suite must be green
- **Max feedback latency:** 30 seconds

---

## Per-Task Verification Map

| Task ID | Plan | Wave | Requirement | Test Type | Automated Command | File Exists | Status |
|---------|------|------|-------------|-----------|-------------------|-------------|--------|
| 10-01-01 | 01 | 1 | IMG-01 | unit | `pytest tests/test_image_wiring.py -x -v` | ❌ W0 | ⬜ pending |
| 10-01-02 | 01 | 1 | IMG-01 | unit | `pytest tests/test_image_wiring.py::test_image_is_fetched_and_forwarded_to_provider -x` | ❌ W0 | ⬜ pending |
| 10-01-03 | 01 | 1 | IMG-01 | unit | `pytest tests/test_image_wiring.py::test_no_image_url_completes_normally -x` | ❌ W0 | ⬜ pending |
| 10-01-04 | 01 | 1 | IMG-01 | unit | `pytest tests/test_image_wiring.py::test_finish_task_does_not_receive_image -x` | ❌ W0 | ⬜ pending |
| 10-01-05 | 01 | 1 | IMG-01 | regression | `pytest tests/ -x` | ✅ | ⬜ pending |

*Status: ⬜ pending · ✅ green · ❌ red · ⚠️ flaky*

---

## Wave 0 Requirements

- [ ] `tests/test_image_wiring.py` — stubs for IMG-01 (4 test functions)

*Existing infrastructure covers all other phase requirements (pytest, conftest, fixtures).*

---

## Manual-Only Verifications

| Behavior | Requirement | Why Manual | Test Instructions |
|----------|-------------|------------|-------------------|
| Cloud Run log line confirms image wired | IMG-01 (SC1) | Requires deployed Cloud Run + real SKU with `main_image_url` | `curl /optimize-sku` with a real SKU, check Cloud Run logs for `image_wired:` |

---

## Validation Sign-Off

- [ ] All tasks have `<automated>` verify or Wave 0 dependencies
- [ ] Sampling continuity: no 3 consecutive tasks without automated verify
- [ ] Wave 0 covers all MISSING references
- [ ] No watch-mode flags
- [ ] Feedback latency < 30s
- [ ] `nyquist_compliant: true` set in frontmatter

**Approval:** pending
