---
phase: 12
slug: shared-utils-extraction
status: draft
nyquist_compliant: false
wave_0_complete: false
created: 2026-03-04
---

# Phase 12 — Validation Strategy

> Per-phase validation contract for feedback sampling during execution.

---

## Test Infrastructure

| Property | Value |
|----------|-------|
| **Framework** | pytest 9.0.2 |
| **Config file** | `pyproject.toml` (`[tool.pytest.ini_options]`) |
| **Quick run command** | `PYTHONPATH=./src .venv/bin/python -m pytest tests/api/test_job_management_smoke.py tests/api/test_persistence_smoke.py tests/api/test_main_master_sku_alias_runtime.py::test_require_request_id_rejects_placeholder -v` |
| **Full suite command** | `PYTHONPATH=./src .venv/bin/python -m pytest tests/ -v` |
| **Estimated runtime** | ~15 seconds |

---

## Sampling Rate

- **After every task commit:** Run `PYTHONPATH=./src .venv/bin/python -c "import feedops.api.main; print('OK')" && PYTHONPATH=./src .venv/bin/python -m pytest tests/api/test_job_management_smoke.py tests/api/test_persistence_smoke.py -x`
- **After every plan wave:** Run `PYTHONPATH=./src .venv/bin/python -m pytest tests/ -v`
- **Before `/gsd:verify-work`:** Full suite must be green
- **Max feedback latency:** 15 seconds

---

## Per-Task Verification Map

| Task ID | Plan | Wave | Requirement | Test Type | Automated Command | File Exists | Status |
|---------|------|------|-------------|-----------|-------------------|-------------|--------|
| 12-01-01 | 01 | 1 | DEAD-06 | unit | `PYTHONPATH=./src .venv/bin/python -c "from feedops.api.utils import _require_request_id; print('OK')"` | ❌ W0 | ⬜ pending |
| 12-01-02 | 01 | 1 | DEAD-06 | unit | `PYTHONPATH=./src .venv/bin/python -c "from feedops.api.utils import GenerationBudgetExceededError; print('OK')"` | ❌ W0 | ⬜ pending |
| 12-01-03 | 01 | 1 | DEAD-06 | smoke | `PYTHONPATH=./src .venv/bin/python -c "import feedops.api.main; print('OK')"` | ✅ | ⬜ pending |
| 12-01-04 | 01 | 1 | DEAD-06 | smoke | `PYTHONPATH=./src .venv/bin/python -c "import ast, pathlib; src=pathlib.Path('src/feedops/api/persistence.py').read_text(); tree=ast.parse(src); defs=[n.name for n in ast.walk(tree) if isinstance(n, ast.FunctionDef)]; assert '_require_request_id' not in defs"` | ✅ | ⬜ pending |
| 12-01-05 | 01 | 1 | DEAD-06 | smoke | `PYTHONPATH=./src .venv/bin/python -c "import ast, pathlib; src=pathlib.Path('src/feedops/api/job_management.py').read_text(); tree=ast.parse(src); defs=[n.name for n in ast.walk(tree) if isinstance(n, ast.FunctionDef)]; assert '_require_request_id' not in defs"` | ✅ | ⬜ pending |
| 12-01-06 | 01 | 1 | DEAD-06 | regression | `PYTHONPATH=./src .venv/bin/python -m pytest tests/ -x` | ✅ | ⬜ pending |

*Status: ⬜ pending · ✅ green · ❌ red · ⚠️ flaky*

---

## Wave 0 Requirements

- [ ] `src/feedops/api/utils.py` — the new module (created in Wave 1 Task 1)

*Existing smoke tests and runtime alias tests cover all extraction behaviors. Import assertions serve as inline verification steps.*

---

## Manual-Only Verifications

*All phase behaviors have automated verification.*

---

## Validation Sign-Off

- [ ] All tasks have `<automated>` verify or Wave 0 dependencies
- [ ] Sampling continuity: no 3 consecutive tasks without automated verify
- [ ] Wave 0 covers all MISSING references
- [ ] No watch-mode flags
- [ ] Feedback latency < 15s
- [ ] `nyquist_compliant: true` set in frontmatter

**Approval:** pending
