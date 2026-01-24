from pathlib import Path

from feedops.quality.dashboard import parse_report_text, render_compare_html


def test_parse_report_text_extracts_evidence_and_prompt():
    report = """# Optimization Report: 101

**Generated:** 2026-01-23T00:00:00
**Status:** APPROVED

---

## Input Data Sent to LLM

**Provider/Model:** openai/gpt-5.2
**Image URL:** https://example.com/image.jpg
**Token Usage:** Prompt tokens: 10, Completion tokens: 5
**Estimated Cost:** $0.000100

## Available Product Data

| Attribute | Value | Source |
|-----------|-------|--------|
| material | Brass | material |

<details>
<summary>Full Prompt</summary>

```
FULL PROMPT TEXT
```
</details>
"""
    parsed = parse_report_text(report)
    assert "Available Product Data" in (parsed.evidence_markdown or "")
    assert "FULL PROMPT TEXT" in (parsed.prompt_text or "")
    assert parsed.provider_model == "openai/gpt-5.2"


def test_render_compare_html_escapes_sku():
    sku = "SKU<1>"
    html_output = render_compare_html(
        baseline_dir=Path("baseline"),
        candidate_dir=Path("candidate"),
        baseline_scores={sku: {"composite": 50.0, "google": {"composite": 50.0}}},
        candidate_scores={sku: {"composite": 60.0, "google": {"composite": 60.0}}},
        baseline_exports={sku: {"google": {"title": "t", "description": "d"}}},
        candidate_exports={sku: {"google": {"title": "t", "description": "d"}}},
        baseline_reports={sku: None},
        candidate_reports={sku: None},
    )
    assert "SKU<1>" not in html_output
    assert "SKU&lt;1&gt;" in html_output
    assert "href=\"#sku-sku-1\"" in html_output
    assert "id=\"sku-sku-1\"" in html_output
