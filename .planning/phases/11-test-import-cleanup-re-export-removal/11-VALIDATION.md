---
phase: 11
slug: test-import-cleanup-re-export-removal
status: draft
nyquist_compliant: false
wave_0_complete: false
created: 2026-03-04
---

# Phase 11 — Validation Strategy

> Per-phase validation contract for feedback sampling during execution.

---

## Test Infrastructure

| Property | Value |
|----------|-------|
| **Framework** | pytest 9.0.2 |
| **Config file** | `pyproject.toml` |
| **Quick run command** | `PYTHONPATH=./src .venv/bin/python -m pytest tests/api/ -q` |
| **Full suite command** | `PYTHONPATH=./src .venv/bin/python -m pytest tests/ -q --tb=short` |
| **Estimated runtime** | ~45 seconds |

---

## Sampling Rate

- **After every task commit:** Run `PYTHONPATH=./src .venv/bin/python -m pytest tests/api/ -q`
- **After every plan wave:** Run `PYTHONPATH=./src .venv/bin/python -m pytest tests/ -q --tb=short`
- **Before `/gsd:verify-work`:** Full suite must be green
- **Max feedback latency:** 45 seconds

---

## Per-Task Verification Map

| Task ID | Plan | Wave | Requirement | Test Type | Automated Command | File Exists | Status |
|---------|------|------|-------------|-----------|-------------------|-------------|--------|
| TBD | 01 | 1 | DEAD-02 | unit | `grep -rn "api_main\." tests/` should return empty | post-migration | pending |
| TBD | 01 | 1 | DEAD-03 | smoke | `PYTHONPATH=./src .venv/bin/python -m pytest tests/api/test_telemetry_smoke.py tests/api/test_persistence_smoke.py tests/api/test_schemas_smoke.py tests/api/test_job_runner_smoke.py tests/api/test_job_management_smoke.py -q` | yes | pending |
| TBD | 01 | 1 | DEAD-04 | unit | `PYTHONPATH=./src .venv/bin/python -m pytest tests/test_prompt_sanitization_contract.py -q` | yes | pending |

*Status: pending · green · red · flaky*

---

## Wave 0 Requirements

*Existing infrastructure covers all phase requirements.*

---

## Manual-Only Verifications

*All phase behaviors have automated verification.*

---

## Validation Sign-Off

- [ ] All tasks have `<automated>` verify or Wave 0 dependencies
- [ ] Sampling continuity: no 3 consecutive tasks without automated verify
- [ ] Wave 0 covers all MISSING references
- [ ] No watch-mode flags
- [ ] Feedback latency < 45s
- [ ] `nyquist_compliant: true` set in frontmatter

**Approval:** pending
