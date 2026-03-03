"""Guard test: main.py must stay under 500 lines (DECOMP-09).

This test prevents future code from bloating main.py back into a monolith.
If this test fails, the new code should go into the appropriate service module
(routes.py, job_runner.py, generation.py, etc.) instead.
"""
from pathlib import Path

MAIN_PY = Path(__file__).resolve().parents[2] / "src" / "feedops" / "api" / "main.py"
MAX_LINES = 500


def test_main_py_under_500_lines():
    line_count = len(MAIN_PY.read_text().splitlines())
    assert line_count < MAX_LINES, (
        f"main.py is {line_count} lines (max {MAX_LINES}). "
        f"Move new code to the appropriate service module."
    )
