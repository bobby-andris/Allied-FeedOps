from pathlib import Path

from feedops.quality.data_loader import parse_report_text


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
