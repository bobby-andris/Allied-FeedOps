#!/usr/bin/env python3
"""Per-platform GPT-5.2 validation harness for Phase 25.2-01.

Generates platform-specific content using dedicated system prompts and schemas,
then validates key constraints and writes a results report.
"""

from __future__ import annotations

import argparse
import asyncio
import json
import os
import re
import sys
import time
from pathlib import Path
from typing import Any

import tiktoken
from openai import AsyncOpenAI

from feedops.api.prompt_builder import build_core_prompt
from feedops.api.supabase_loader import load_parent_sku_from_supabase
from feedops.pipeline.evidence import build_evidence_table, format_evidence_markdown
from feedops.pipeline.prompts import (
    BING_SCHEMA,
    FINISH_SENTENCES_SCHEMA,
    GOOGLE_SCHEMA,
    SHOPIFY_SCHEMA,
)
from feedops.pipeline.skill_loader import get_platform_system_prompt

PROJECT_ROOT = Path(__file__).parent.parent
DEFAULT_RESULTS_PATH = (
    PROJECT_ROOT
    / ".planning"
    / "phases"
    / "25.2-gpt52-prompt-engineering"
    / "25.2-01-test-results.md"
)

BANNED_WORDS = [
    "finest",
    "luxurious",
    "premium",
    "exclusive",
    "exceptional",
    "unparalleled",
    "superior",
    "exquisite",
    "ultimate",
]

COMPETITOR_BRANDS = [
    "jan barboglio",
    "kingston brass",
    "moen",
    "delta",
    "kohler",
    "american standard",
    "pfister",
    "brizo",
    "grohe",
    "hansgrohe",
    "restoration hardware",
    "pottery barn",
    "home depot",
    "lowes",
]

GENERIC_FINISH_PHRASES = [
    "makes a statement",
    "adds elegance",
    "elevates your space",
    "beautiful finish",
    "timeless appeal",
    "modern sophistication",
    "premium look",
]

STOP_WORDS = {
    "this",
    "that",
    "with",
    "from",
    "your",
    "into",
    "wall",
    "mount",
    "mounted",
    "solid",
    "brass",
    "allied",
    "collection",
    "bathroom",
}

ENCODING = tiktoken.get_encoding("o200k_base")


def load_env_file(path: str) -> None:
    """Load environment variables from a dotenv-style file."""
    env_path = Path(path)
    if not env_path.exists():
        return
    for line in env_path.read_text().splitlines():
        line = line.strip()
        if not line or line.startswith("#"):
            continue
        if "=" not in line:
            continue
        key, _, value = line.partition("=")
        os.environ.setdefault(key.strip(), value.strip().strip('"').strip("'"))


def count_tokens(text: str) -> int:
    return len(ENCODING.encode(text))


def _make_strict(schema: dict[str, Any]) -> dict[str, Any]:
    """Ensure strict schema requirements recursively."""
    result = dict(schema)
    if result.get("type") == "object":
        result["additionalProperties"] = False
        if "properties" in result:
            props = result["properties"]
            result["required"] = sorted(set(result.get("required", [])) | set(props.keys()))
            result["properties"] = {k: _make_strict(v) for k, v in props.items()}
    elif result.get("type") == "array" and "items" in result:
        result["items"] = _make_strict(result["items"])
    return result


def build_response_format(schema_name: str, schema: dict[str, Any]) -> dict[str, Any]:
    strict_schema = _make_strict(schema)
    return {
        "type": "json_schema",
        "json_schema": {
            "name": schema_name,
            "strict": True,
            "schema": strict_schema,
        },
    }


def extract_usage(response: Any) -> dict[str, int]:
    usage = {
        "prompt_tokens": getattr(response.usage, "prompt_tokens", 0) or 0,
        "completion_tokens": getattr(response.usage, "completion_tokens", 0) or 0,
        "cached_tokens": 0,
    }
    try:
        usage["cached_tokens"] = response.usage.prompt_tokens_details.cached_tokens or 0
    except Exception:
        usage["cached_tokens"] = 0
    return usage


def parse_json_payload(raw: str) -> Any:
    """Parse model output into JSON with light normalization/fallbacks."""
    text = (raw or "").strip()
    if not text:
        raise json.JSONDecodeError("empty response", raw, 0)

    try:
        return json.loads(text)
    except json.JSONDecodeError:
        # Handle occasional markdown-wrapped JSON.
        fenced = re.search(r"```(?:json)?\\s*(.*?)```", text, flags=re.DOTALL)
        if fenced:
            return json.loads(fenced.group(1).strip())

        # Last-resort brace extraction.
        start = text.find("{")
        end = text.rfind("}")
        if start != -1 and end != -1 and end > start:
            return json.loads(text[start : end + 1])

        raise


def extract_strings(payload: Any) -> list[str]:
    strings: list[str] = []
    if isinstance(payload, str):
        strings.append(payload)
    elif isinstance(payload, dict):
        for value in payload.values():
            strings.extend(extract_strings(value))
    elif isinstance(payload, list):
        for value in payload:
            strings.extend(extract_strings(value))
    return strings


def detect_banned_words(text: str) -> list[str]:
    text_lower = text.lower()
    return [word for word in BANNED_WORDS if word in text_lower]


def detect_competitor_brands(text: str) -> list[str]:
    text_lower = text.lower()
    return [brand for brand in COMPETITOR_BRANDS if brand in text_lower]


def infer_product_keywords(parent_sku: Any) -> set[str]:
    tokens = re.findall(r"[a-z0-9]+", f"{parent_sku.current_title} {parent_sku.category}".lower())
    return {t for t in tokens if len(t) > 3 and t not in STOP_WORDS}


def list_finish_pairs(parent_sku: Any) -> list[tuple[str, str]]:
    seen: set[tuple[str, str]] = set()
    for variant in parent_sku.variants:
        pair = (variant.finish_code, variant.finish)
        if pair not in seen:
            seen.add(pair)
    return sorted(seen, key=lambda pair: pair[0])


def build_user_prompt(
    platform: str,
    parent_sku: Any,
    evidence: list[Any],
    evidence_markdown: str,
    finish_pairs: list[tuple[str, str]],
) -> str:
    if platform in {"google", "bing", "shopify"}:
        content_type = "platform content package"
        prompt = build_core_prompt(
            parent_sku=parent_sku,
            evidence=evidence,
            evidence_markdown=evidence_markdown,
            platform=platform,
            content_type=content_type,
            finish_code=None,
            mode="batch",
        )
        if platform in {"google", "bing"}:
            prompt += (
                "\n\n<placeholder_requirements>\n"
                "Use literal placeholder strings exactly as written:\n"
                "- {FINISH_NAME} must be the first token in titles.\n"
                "- {FINISH_SENTENCE} must appear in descriptions.\n"
                "Do not expand these placeholders.\n"
                "</placeholder_requirements>"
            )
        else:
            prompt += (
                "\n\n<placeholder_requirements>\n"
                "Shopify output is finish-agnostic. Never include {FINISH_NAME} or "
                "{FINISH_SENTENCE}.\n"
                "</placeholder_requirements>"
            )
        return prompt

    finish_lines = "\n".join(
        f"- {finish_code}: {finish_name}" for finish_code, finish_name in finish_pairs
    )
    bullets = [
        b
        for b in [
            parent_sku.bullet_1,
            parent_sku.bullet_2,
            parent_sku.bullet_3,
            parent_sku.bullet_4,
        ]
        if b
    ]
    bullet_block = "\n".join(f"- {b}" for b in bullets) if bullets else "- (no bullets provided)"

    return (
        "<task>Generate finish sentence data for this product.</task>\n"
        "<requirements>\n"
        "Return exactly one sentence per finish listed below.\n"
        "Every sentence must be 40-80 characters and feel specific to THIS product.\n"
        "Avoid generic style-only statements. Mention a product-relevant keyword naturally.\n"
        "</requirements>\n"
        "<product_context>\n"
        f"Master SKU: {parent_sku.master_sku}\n"
        f"Category: {parent_sku.category}\n"
        f"Current title: {parent_sku.current_title}\n"
        "Product bullets:\n"
        f"{bullet_block}\n"
        "</product_context>\n"
        "<evidence_table>\n"
        f"{evidence_markdown}\n"
        "</evidence_table>\n"
        "<finish_list>\n"
        f"{finish_lines}\n"
        "</finish_list>"
    )


async def generate_per_platform(
    client: AsyncOpenAI,
    parent_sku: Any,
    evidence: list[Any],
    evidence_markdown: str,
    platform: str,
    model: str,
    reasoning_effort: str,
    max_completion_tokens: int,
) -> dict[str, Any]:
    """Generate one platform payload using platform-specific prompt + schema."""
    schemas = {
        "google": ("google_content", GOOGLE_SCHEMA),
        "bing": ("bing_content", BING_SCHEMA),
        "shopify": ("shopify_content", SHOPIFY_SCHEMA),
        "finish": ("finish_sentences", FINISH_SENTENCES_SCHEMA),
    }
    if platform not in schemas:
        raise ValueError(f"Unsupported platform: {platform}")

    schema_name, schema = schemas[platform]
    finish_pairs = list_finish_pairs(parent_sku)
    system_prompt = get_platform_system_prompt(platform)
    user_prompt = build_user_prompt(
        platform=platform,
        parent_sku=parent_sku,
        evidence=evidence,
        evidence_markdown=evidence_markdown,
        finish_pairs=finish_pairs,
    )

    started_at = time.time()
    response = await client.chat.completions.create(
        model=model,
        messages=[
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_prompt},
        ],
        response_format=build_response_format(schema_name, schema),
        reasoning_effort=reasoning_effort,
        max_completion_tokens=max_completion_tokens,
    )

    message = response.choices[0].message
    raw = message.content
    if raw is None:
        raise RuntimeError(
            f"Platform {platform} returned no content "
            f"(finish_reason={response.choices[0].finish_reason})"
        )

    try:
        payload = parse_json_payload(raw)
    except json.JSONDecodeError:
        # One retry with explicit repair instruction before failing.
        repair = await client.chat.completions.create(
            model=model,
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt},
                {
                    "role": "assistant",
                    "content": raw,
                },
                {
                    "role": "user",
                    "content": (
                        "Return valid JSON only that matches the response schema. "
                        "No prose, no markdown fences."
                    ),
                },
            ],
            response_format=build_response_format(schema_name, schema),
            reasoning_effort=reasoning_effort,
            max_completion_tokens=max_completion_tokens,
        )
        repaired_raw = repair.choices[0].message.content or ""
        payload = parse_json_payload(repaired_raw)
        usage = extract_usage(response)
        repair_usage = extract_usage(repair)
        usage["prompt_tokens"] += repair_usage.get("prompt_tokens", 0)
        usage["completion_tokens"] += repair_usage.get("completion_tokens", 0)
        usage["cached_tokens"] += repair_usage.get("cached_tokens", 0)
    else:
        usage = extract_usage(response)

    if message.refusal:
        raise RuntimeError(f"Platform {platform} refusal: {message.refusal}")

    return {
        "platform": platform,
        "system_prompt": system_prompt,
        "user_prompt": user_prompt,
        "system_prompt_chars": len(system_prompt),
        "system_prompt_tokens": count_tokens(system_prompt),
        "user_prompt_chars": len(user_prompt),
        "user_prompt_tokens": count_tokens(user_prompt),
        "usage": usage,
        "latency_sec": round(time.time() - started_at, 2),
        "payload": payload,
    }


def evaluate_platform_output(platform: str, payload: dict[str, Any], parent_sku: Any) -> dict[str, Any]:
    checks: dict[str, dict[str, Any]] = {}

    all_text = "\n".join(extract_strings(payload))
    banned = detect_banned_words(all_text)
    competitors = detect_competitor_brands(all_text)

    checks["no_banned_words"] = {"passed": not banned, "details": banned}
    checks["no_competitor_brands"] = {"passed": not competitors, "details": competitors}

    if platform == "google":
        title = payload.get("google_title", "")
        description = payload.get("google_description", "")
        checks["title_starts_with_FINISH_NAME"] = {
            "passed": title.startswith("{FINISH_NAME}"),
            "details": title,
        }
        checks["description_has_FINISH_SENTENCE_placeholder"] = {
            "passed": "{FINISH_SENTENCE}" in description,
            "details": description,
        }
        checks["description_length_700_900"] = {
            "passed": 700 <= len(description) <= 900,
            "details": len(description),
        }

    elif platform == "bing":
        title = payload.get("bing_title", "")
        description = payload.get("bing_description", "")
        checks["title_starts_with_FINISH_NAME"] = {
            "passed": title.startswith("{FINISH_NAME}"),
            "details": title,
        }
        checks["description_has_FINISH_SENTENCE_placeholder"] = {
            "passed": "{FINISH_SENTENCE}" in description,
            "details": description,
        }
        checks["description_length_700_1000"] = {
            "passed": 700 <= len(description) <= 1000,
            "details": len(description),
        }

    elif platform == "shopify":
        title = payload.get("shopify_title", "")
        description = payload.get("shopify_description", "")
        meta = payload.get("shopify_meta_description", "")
        checks["no_finish_placeholders"] = {
            "passed": "{FINISH_NAME}" not in title
            and "{FINISH_NAME}" not in description
            and "{FINISH_SENTENCE}" not in title
            and "{FINISH_SENTENCE}" not in description,
            "details": {
                "title_contains_FINISH_NAME": "{FINISH_NAME}" in title,
                "description_contains_FINISH_NAME": "{FINISH_NAME}" in description,
                "description_contains_FINISH_SENTENCE": "{FINISH_SENTENCE}" in description,
            },
        }
        checks["meta_description_lt_160"] = {
            "passed": len(meta) < 160,
            "details": len(meta),
        }

    elif platform == "finish":
        sentences = payload.get("sentences", [])
        checks["has_28_sentences"] = {
            "passed": len(sentences) == 28,
            "details": len(sentences),
        }

        keyword_hints = infer_product_keywords(parent_sku)
        generic_hits: list[str] = []
        bad_length: list[tuple[str, int]] = []
        missing_keywords: list[str] = []
        duplicate_codes: list[str] = []

        seen_codes: set[str] = set()
        for item in sentences:
            finish_code = item.get("finish_code", "")
            sentence = item.get("sentence", "")
            sentence_len = len(sentence)
            sentence_lower = sentence.lower()

            if finish_code in seen_codes:
                duplicate_codes.append(finish_code)
            seen_codes.add(finish_code)

            if sentence_len < 40 or sentence_len > 80:
                bad_length.append((finish_code, sentence_len))

            if any(phrase in sentence_lower for phrase in GENERIC_FINISH_PHRASES):
                generic_hits.append(finish_code)

            if keyword_hints and not any(k in sentence_lower for k in keyword_hints):
                missing_keywords.append(finish_code)

        checks["sentence_length_40_80"] = {
            "passed": not bad_length,
            "details": bad_length,
        }
        checks["no_duplicate_finish_codes"] = {
            "passed": not duplicate_codes,
            "details": sorted(set(duplicate_codes)),
        }
        checks["not_generic_finish_copy"] = {
            "passed": not generic_hits,
            "details": sorted(set(generic_hits)),
        }
        checks["product_specific_language"] = {
            "passed": len(missing_keywords) <= 3,
            "details": {
                "keyword_hints": sorted(keyword_hints),
                "missing_keyword_codes": sorted(set(missing_keywords)),
            },
        }

    return checks


def format_check_line(name: str, check: dict[str, Any]) -> str:
    status = "PASS" if check.get("passed") else "FAIL"
    return f"- **{status}** `{name}` — {check.get('details')}"


def render_results_markdown(
    sku: str,
    model: str,
    reasoning_effort: str,
    results: dict[str, Any],
) -> str:
    timestamp = time.strftime("%Y-%m-%d %H:%M:%S UTC", time.gmtime())

    lines = [
        "# Phase 25.2-01 Per-Platform GPT-5.2 Test Results",
        "",
        f"- **Generated:** {timestamp}",
        f"- **SKU:** {sku}",
        f"- **Model:** {model}",
        f"- **Reasoning effort:** {reasoning_effort}",
        "",
        "## System Prompt Sizes",
        "",
        "| Platform | System chars | System tokens | User chars | User tokens | Prompt tokens | Completion tokens | Cached tokens | Latency (s) |",
        "|---|---:|---:|---:|---:|---:|---:|---:|---:|",
    ]

    for platform in sorted(results):
        item = results[platform]
        usage = item["usage"]
        lines.append(
            "| {platform} | {sys_chars} | {sys_tokens} | {user_chars} | {user_tokens} | {prompt_tokens} | {completion_tokens} | {cached_tokens} | {latency} |".format(
                platform=platform,
                sys_chars=item["system_prompt_chars"],
                sys_tokens=item["system_prompt_tokens"],
                user_chars=item["user_prompt_chars"],
                user_tokens=item["user_prompt_tokens"],
                prompt_tokens=usage.get("prompt_tokens", 0),
                completion_tokens=usage.get("completion_tokens", 0),
                cached_tokens=usage.get("cached_tokens", 0),
                latency=item["latency_sec"],
            )
        )

    lines.extend(["", "## Constraint Analysis", ""])

    for platform in sorted(results):
        item = results[platform]
        checks = item["checks"]
        lines.append(f"### {platform.title()}")
        lines.append("")
        for check_name, check in checks.items():
            lines.append(format_check_line(check_name, check))
        lines.append("")

    placeholder_findings: list[str] = []
    if "google" in results:
        google_pass = results["google"]["checks"].get(
            "description_has_FINISH_SENTENCE_placeholder", {}
        ).get("passed")
        placeholder_findings.append(
            f"Google description placeholder preservation: {'PASS' if google_pass else 'FAIL'}"
        )
    if "bing" in results:
        bing_pass = results["bing"]["checks"].get(
            "description_has_FINISH_SENTENCE_placeholder", {}
        ).get("passed")
        placeholder_findings.append(
            f"Bing description placeholder preservation: {'PASS' if bing_pass else 'FAIL'}"
        )
    if "shopify" in results:
        shopify_pass = results["shopify"]["checks"].get("no_finish_placeholders", {}).get(
            "passed"
        )
        placeholder_findings.append(
            f"Shopify finish-agnostic behavior: {'PASS' if shopify_pass else 'FAIL'}"
        )

    lines.extend(["## Placeholder Behavior Findings", ""])
    lines.extend([f"- {finding}" for finding in placeholder_findings])
    lines.append("")

    lines.extend(["## Full Outputs", ""])
    for platform in sorted(results):
        lines.append(f"### {platform.title()} Output")
        lines.append("````json")
        lines.append(json.dumps(results[platform]["payload"], indent=2))
        lines.append("````")
        lines.append("")

    return "\n".join(lines)


async def run_platform_tests(
    sku: str,
    selected_platforms: list[str],
    model: str,
    reasoning_effort: str,
    max_completion_tokens: int,
) -> tuple[Any, dict[str, Any]]:
    parent_sku = load_parent_sku_from_supabase(sku)
    if not parent_sku:
        raise RuntimeError(f"SKU not found: {sku}")

    evidence = build_evidence_table(parent_sku)
    evidence_markdown = format_evidence_markdown(evidence)

    api_key = os.environ.get("OPENAI_API_KEY")
    if not api_key:
        raise RuntimeError("OPENAI_API_KEY is not set. Source .env.vercel before running.")

    client = AsyncOpenAI(api_key=api_key)
    results: dict[str, Any] = {}

    for platform in selected_platforms:
        print(f"\nGenerating {platform}...")
        generated = await generate_per_platform(
            client=client,
            parent_sku=parent_sku,
            evidence=evidence,
            evidence_markdown=evidence_markdown,
            platform=platform,
            model=model,
            reasoning_effort=reasoning_effort,
            max_completion_tokens=max_completion_tokens,
        )
        generated["checks"] = evaluate_platform_output(
            platform=platform,
            payload=generated["payload"],
            parent_sku=parent_sku,
        )
        results[platform] = generated

        passed = sum(1 for c in generated["checks"].values() if c.get("passed"))
        total = len(generated["checks"])
        print(
            f"  {platform}: {passed}/{total} checks passed | "
            f"prompt_tokens={generated['usage']['prompt_tokens']} "
            f"completion_tokens={generated['usage']['completion_tokens']}"
        )

    return parent_sku, results


def parse_platforms(value: str) -> list[str]:
    if value == "all":
        return ["google", "bing", "shopify", "finish"]
    return [value]


def main() -> None:
    load_env_file(str(PROJECT_ROOT / ".env.vercel"))

    parser = argparse.ArgumentParser(description="Per-platform GPT-5.2 prompt validation")
    parser.add_argument("--sku", default="1025U", help="Master SKU to test")
    parser.add_argument(
        "--platform",
        choices=["google", "bing", "shopify", "finish", "all"],
        default="all",
        help="Platform to test (default: all)",
    )
    parser.add_argument("--model", default="gpt-5.2", help="OpenAI model")
    parser.add_argument(
        "--reasoning-effort",
        choices=["low", "medium", "high"],
        default="medium",
        help="reasoning_effort passed to GPT-5.2",
    )
    parser.add_argument(
        "--max-completion-tokens",
        type=int,
        default=4000,
        help="max_completion_tokens for each platform call",
    )
    parser.add_argument(
        "--results-path",
        default=str(DEFAULT_RESULTS_PATH),
        help="Markdown output path",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Only print planned platforms and exit",
    )
    args = parser.parse_args()

    platforms = parse_platforms(args.platform)
    print(
        "Running per-platform test:\n"
        f"  SKU={args.sku}\n"
        f"  platforms={platforms}\n"
        f"  model={args.model}\n"
        f"  reasoning_effort={args.reasoning_effort}\n"
        f"  max_completion_tokens={args.max_completion_tokens}"
    )

    if args.dry_run:
        return

    try:
        _, results = asyncio.run(
            run_platform_tests(
                sku=args.sku,
                selected_platforms=platforms,
                model=args.model,
                reasoning_effort=args.reasoning_effort,
                max_completion_tokens=args.max_completion_tokens,
            )
        )
    except Exception as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        raise

    report = render_results_markdown(
        sku=args.sku,
        model=args.model,
        reasoning_effort=args.reasoning_effort,
        results=results,
    )

    results_path = Path(args.results_path)
    results_path.parent.mkdir(parents=True, exist_ok=True)
    results_path.write_text(report)

    raw_dir = Path("/tmp/ab_test_outputs")
    raw_dir.mkdir(parents=True, exist_ok=True)
    safe_sku = args.sku.replace("/", "-")
    for platform, data in results.items():
        (raw_dir / f"{safe_sku}_{platform}_output.json").write_text(
            json.dumps(data["payload"], indent=2)
        )

    print(f"\nReport written: {results_path}")
    print(f"Raw payloads: {raw_dir}")


if __name__ == "__main__":
    main()
