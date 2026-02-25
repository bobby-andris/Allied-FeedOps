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
from openai import (
    APIConnectionError,
    APITimeoutError,
    AsyncOpenAI,
    InternalServerError,
    RateLimitError,
)

from feedops.api.prompt_builder import (
    build_bing_prompt,
    build_google_prompt,
    get_prompt_experiment_variant,
    build_shopify_prompt,
)
from feedops.api.prompt_loader import (
    format_gold_standard_examples_bundle,
    get_category_guidance,
)
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

META_SEARCH_COMMENTARY_PATTERNS = [
    re.compile(r"\bif\s+you(?:'re|\s+are)?\s+(?:searching|looking|shopping)\b", re.IGNORECASE),
    re.compile(r"\bif\s+you(?:'ve|\s+have)?\s+been\s+comparing\b", re.IGNORECASE),
    re.compile(r"\bsearch(?:ed|ing)?\s+for\b", re.IGNORECASE),
]

METADATA_DUMP_PATTERN = re.compile(
    r"\b(?:upc|gtin|category|mastersku|master sku|custom[_\s-]*label|item[_\s-]*group)\s*:",
    re.IGNORECASE,
)

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


def _platform_completion_tokens(platform: str, requested_tokens: int) -> int:
    """Ensure finish generation has enough completion budget in strict JSON mode."""
    if platform == "finish":
        return max(requested_tokens, 10000)
    return requested_tokens


def parse_json_payload(raw: str) -> Any:
    """Parse model output into JSON with light normalization/fallbacks."""
    def _unwrap_content_wrapper(value: Any) -> Any:
        current = value
        for _ in range(3):
            if isinstance(current, dict) and set(current.keys()) == {"content"}:
                inner = current.get("content")
                if isinstance(inner, (dict, list)):
                    current = inner
                    continue
                if isinstance(inner, str):
                    stripped = inner.strip()
                    if not stripped:
                        break
                    try:
                        current = json.loads(stripped)
                        continue
                    except json.JSONDecodeError:
                        break
            break
        return current

    text = (raw or "").strip()
    if not text:
        raise json.JSONDecodeError("empty response", raw, 0)

    try:
        return _unwrap_content_wrapper(json.loads(text))
    except json.JSONDecodeError:
        # Handle occasional markdown-wrapped JSON.
        fenced = re.search(r"```(?:json)?\\s*(.*?)```", text, flags=re.DOTALL)
        if fenced:
            return _unwrap_content_wrapper(json.loads(fenced.group(1).strip()))

        # Last-resort brace extraction.
        start = text.find("{")
        end = text.rfind("}")
        if start != -1 and end != -1 and end > start:
            return _unwrap_content_wrapper(json.loads(text[start : end + 1]))

        raise


def extract_response_diagnostics(response: Any) -> dict[str, Any]:
    """Extract finish_reason/refusal/raw-content metadata for debugging."""
    choice = response.choices[0]
    message = choice.message
    raw = message.content or ""
    return {
        "finish_reason": getattr(choice, "finish_reason", None),
        "refusal": getattr(message, "refusal", None),
        "raw_content_chars": len(raw),
    }


def _should_escalate_budget(diagnostics: dict[str, Any] | None) -> bool:
    """Escalate output budget only for strict-json empty-length failures."""
    if not diagnostics:
        return False
    return (
        diagnostics.get("finish_reason") == "length"
        and int(diagnostics.get("raw_content_chars") or 0) == 0
    )


def _is_transient_error(exc: Exception) -> bool:
    return isinstance(
        exc,
        (
            asyncio.TimeoutError,
            APITimeoutError,
            APIConnectionError,
            RateLimitError,
            InternalServerError,
        ),
    )


async def _create_completion_with_retry(
    client: AsyncOpenAI,
    *,
    model: str,
    messages: list[dict[str, Any]],
    response_format: dict[str, Any],
    reasoning_effort: str,
    max_completion_tokens: int,
    request_timeout_sec: int = 180,
    max_attempts: int = 3,
) -> Any:
    """Retry transient OpenAI errors with bounded exponential backoff."""
    last_error: Exception | None = None
    for attempt in range(max_attempts):
        try:
            return await asyncio.wait_for(
                client.chat.completions.create(
                    model=model,
                    messages=messages,
                    response_format=response_format,
                    reasoning_effort=reasoning_effort,
                    max_completion_tokens=max_completion_tokens,
                ),
                timeout=request_timeout_sec,
            )
        except Exception as exc:  # pragma: no cover - exercised via integration runs
            last_error = exc
            if not _is_transient_error(exc) or attempt == max_attempts - 1:
                break
            await asyncio.sleep(0.75 * (2**attempt))

    assert last_error is not None
    raise last_error


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


def extract_customer_content_strings(platform: str, payload: dict[str, Any]) -> list[str]:
    """Return only customer-facing content fields (exclude claims/self_score)."""
    if platform == "google":
        return [
            str(payload.get("google_title", "") or ""),
            str(payload.get("google_short_title", "") or ""),
            str(payload.get("google_description", "") or ""),
        ]
    if platform == "bing":
        return [
            str(payload.get("bing_title", "") or ""),
            str(payload.get("bing_description", "") or ""),
        ]
    if platform == "shopify":
        return [
            str(payload.get("shopify_title", "") or ""),
            str(payload.get("shopify_meta_description", "") or ""),
            str(payload.get("shopify_description", "") or ""),
        ]
    if platform == "finish":
        sentences = payload.get("sentences", [])
        if isinstance(sentences, list):
            return [str(item.get("sentence", "") or "") for item in sentences if isinstance(item, dict)]
    return []


def detect_banned_words(text: str) -> list[str]:
    text_lower = text.lower()
    return [word for word in BANNED_WORDS if word in text_lower]


def detect_competitor_brands(text: str) -> list[str]:
    text_lower = text.lower()
    return [brand for brand in COMPETITOR_BRANDS if brand in text_lower]


def detect_meta_search_commentary(text: str) -> list[str]:
    return [pattern.pattern for pattern in META_SEARCH_COMMENTARY_PATTERNS if pattern.search(text or "")]


def detect_metadata_dump(text: str) -> list[str]:
    return [METADATA_DUMP_PATTERN.pattern] if METADATA_DUMP_PATTERN.search(text or "") else []


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
        category_guidance = get_category_guidance(getattr(parent_sku, "category", ""))

        if platform == "google":
            try:
                gold_examples = format_gold_standard_examples_bundle(max_examples=2)
            except Exception:
                gold_examples = ""
            return build_google_prompt(
                sku_data=parent_sku,
                evidence=evidence,
                keywords=None,
                category_guidance=category_guidance,
                gold_examples=gold_examples,
            )

        if platform == "bing":
            return build_bing_prompt(
                sku_data=parent_sku,
                evidence=evidence,
                keywords=None,
                category_guidance=category_guidance,
            )

        return build_shopify_prompt(
            sku_data=parent_sku,
            evidence=evidence,
            category_guidance=category_guidance,
        )

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
    response_format = build_response_format(schema_name, schema)
    platform_completion_tokens = _platform_completion_tokens(
        platform, max_completion_tokens
    )
    base_messages = [
        {"role": "system", "content": system_prompt},
        {"role": "user", "content": user_prompt},
    ]
    response = await _create_completion_with_retry(
        client,
        model=model,
        messages=base_messages,
        response_format=response_format,
        reasoning_effort=reasoning_effort,
        max_completion_tokens=platform_completion_tokens,
    )

    message = response.choices[0].message
    raw = message.content
    diagnostics = {
        "initial": extract_response_diagnostics(response),
        "repair": None,
    }
    if raw is None:
        raise RuntimeError(
            f"Platform {platform} returned no content "
            f"(finish_reason={diagnostics['initial'].get('finish_reason')}, "
            f"refusal={diagnostics['initial'].get('refusal')}, "
            f"raw_chars={diagnostics['initial'].get('raw_content_chars')})"
        )

    try:
        payload = parse_json_payload(raw)
    except json.JSONDecodeError:
        # One retry with explicit repair instruction before failing.
        repair_completion_tokens = platform_completion_tokens
        repair_reasoning_effort = reasoning_effort
        if _should_escalate_budget(diagnostics["initial"]):
            repair_completion_tokens = max(platform_completion_tokens * 2, 10000)

        repair_messages: list[dict[str, str]] = [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_prompt},
        ]
        if raw.strip():
            repair_messages.append({"role": "assistant", "content": raw})
        repair_messages.append(
            {
                "role": "user",
                "content": (
                    "Return valid JSON only that matches the response schema. "
                    "No prose, no markdown fences."
                ),
            }
        )
        repair = await _create_completion_with_retry(
            client,
            model=model,
            messages=repair_messages,
            response_format=response_format,
            reasoning_effort=repair_reasoning_effort,
            max_completion_tokens=repair_completion_tokens,
        )
        diagnostics["repair"] = extract_response_diagnostics(repair)
        diagnostics["repair_completion_tokens"] = repair_completion_tokens
        diagnostics["repair_reasoning_effort"] = repair_reasoning_effort
        repaired_raw = repair.choices[0].message.content or ""
        try:
            payload = parse_json_payload(repaired_raw)
        except json.JSONDecodeError as exc:
            raise RuntimeError(
                f"Platform {platform} invalid JSON after repair "
                f"(initial_finish_reason={diagnostics['initial'].get('finish_reason')}, "
                f"initial_raw_chars={diagnostics['initial'].get('raw_content_chars')}, "
                f"repair_finish_reason={diagnostics['repair'].get('finish_reason')}, "
                f"repair_raw_chars={diagnostics['repair'].get('raw_content_chars')})"
            ) from exc
        usage = extract_usage(response)
        repair_usage = extract_usage(repair)
        usage["prompt_tokens"] += repair_usage.get("prompt_tokens", 0)
        usage["completion_tokens"] += repair_usage.get("completion_tokens", 0)
        usage["cached_tokens"] += repair_usage.get("cached_tokens", 0)
    else:
        usage = extract_usage(response)

    if diagnostics["initial"].get("refusal"):
        raise RuntimeError(
            f"Platform {platform} refusal: {diagnostics['initial']['refusal']}"
        )

    return {
        "platform": platform,
        "experiment_variant": get_prompt_experiment_variant(),
        "system_prompt": system_prompt,
        "user_prompt": user_prompt,
        "system_prompt_chars": len(system_prompt),
        "system_prompt_tokens": count_tokens(system_prompt),
        "user_prompt_chars": len(user_prompt),
        "user_prompt_tokens": count_tokens(user_prompt),
        "usage": usage,
        "latency_sec": round(time.time() - started_at, 2),
        "payload": payload,
        "diagnostics": diagnostics,
    }


def evaluate_platform_output(platform: str, payload: dict[str, Any], parent_sku: Any) -> dict[str, Any]:
    checks: dict[str, dict[str, Any]] = {}
    category_lower = str(getattr(parent_sku, "category", "") or "").lower()

    all_text = "\n".join(extract_customer_content_strings(platform, payload))
    banned = detect_banned_words(all_text)
    competitors = detect_competitor_brands(all_text)
    meta_search = detect_meta_search_commentary(all_text)
    metadata_dump = detect_metadata_dump(all_text)

    checks["no_banned_words"] = {"passed": not banned, "details": banned}
    checks["no_competitor_brands"] = {"passed": not competitors, "details": competitors}
    if platform in {"google", "bing"}:
        checks["no_meta_search_commentary"] = {
            "passed": not meta_search,
            "details": meta_search,
        }
        checks["no_metadata_dump"] = {
            "passed": not metadata_dump,
            "details": metadata_dump,
        }

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
        if "towel bar" in category_lower or "towel bars" in category_lower:
            title_lower = str(title).lower()
            short_title_lower = str(payload.get("google_short_title", "")).lower()
            checks["title_matches_category_product_noun"] = {
                "passed": "towel bar" in title_lower and "towel rack" not in title_lower,
                "details": title,
            }
            checks["short_title_matches_category_product_noun"] = {
                "passed": "towel bar" in short_title_lower and "towel rack" not in short_title_lower,
                "details": payload.get("google_short_title", ""),
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
        if "towel bar" in category_lower or "towel bars" in category_lower:
            title_lower = str(title).lower()
            checks["title_matches_category_product_noun"] = {
                "passed": "towel bar" in title_lower and "towel rack" not in title_lower,
                "details": title,
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
            "passed": len(meta) <= 160,
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
        f"- **Prompt experiment variant:** {next(iter(results.values())).get('experiment_variant', 'control') if results else 'control'}",
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
        failed_checks = [name for name, check in checks.items() if not check.get("passed")]
        if failed_checks:
            lines.append(
                "- Diagnostics: "
                f"{json.dumps(item.get('diagnostics', {}), ensure_ascii=False)}"
            )
            if item.get("error"):
                lines.append(f"- Generation error: {item.get('error')}")
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
    platform_timeout_sec: int = 210,
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

    async def _run_platform(platform: str) -> tuple[str, dict[str, Any]]:
        print(f"\nGenerating {platform}...")
        try:
            generated = await asyncio.wait_for(
                generate_per_platform(
                    client=client,
                    parent_sku=parent_sku,
                    evidence=evidence,
                    evidence_markdown=evidence_markdown,
                    platform=platform,
                    model=model,
                    reasoning_effort=reasoning_effort,
                    max_completion_tokens=max_completion_tokens,
                ),
                timeout=platform_timeout_sec,
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
            failed_checks = [
                name
                for name, check in generated["checks"].items()
                if not check.get("passed")
            ]
            if failed_checks:
                print(f"  diagnostics={generated.get('diagnostics', {})}")
            return platform, generated
        except Exception as exc:
            error_message = f"{type(exc).__name__}: {exc}"
            print(f"  {platform}: ERROR — {error_message}")
            return platform, {
                "platform": platform,
                "error": error_message,
                "system_prompt_chars": 0,
                "system_prompt_tokens": 0,
                "user_prompt_chars": 0,
                "user_prompt_tokens": 0,
                "usage": {"prompt_tokens": 0, "completion_tokens": 0, "cached_tokens": 0},
                "latency_sec": 0.0,
                "payload": {},
                "diagnostics": {
                    "initial": {
                        "finish_reason": None,
                        "refusal": None,
                        "raw_content_chars": 0,
                    },
                    "repair": None,
                },
                "checks": {
                    "generation_succeeded": {"passed": False, "details": error_message},
                },
            }

    platform_results = await asyncio.gather(
        *[_run_platform(platform) for platform in selected_platforms]
    )
    for platform, generated in platform_results:
        results[platform] = generated

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
        default="high",
        help="reasoning_effort passed to GPT-5.2",
    )
    parser.add_argument(
        "--max-completion-tokens",
        type=int,
        default=8000,
        help="max_completion_tokens for each platform call",
    )
    parser.add_argument(
        "--platform-timeout-sec",
        type=int,
        default=210,
        help="Hard timeout per platform generation call in seconds.",
    )
    parser.add_argument(
        "--experiment-variant",
        default="",
        help="Optional FEEDOPS_PROMPT_EXPERIMENT_VARIANT override for this run",
    )
    parser.add_argument(
        "--results-path",
        default=str(DEFAULT_RESULTS_PATH),
        help="Markdown output path",
    )
    parser.add_argument(
        "--raw-dir",
        default="/tmp/ab_test_outputs",
        help="Directory for raw JSON payload outputs",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Only print planned platforms and exit",
    )
    args = parser.parse_args()

    platforms = parse_platforms(args.platform)
    if args.experiment_variant.strip():
        os.environ["FEEDOPS_PROMPT_EXPERIMENT_VARIANT"] = (
            args.experiment_variant.strip().lower()
        )
    run_timestamp = time.strftime("%Y%m%d-%H%M%S", time.gmtime())
    print(
        "Running per-platform test:\n"
        f"  SKU={args.sku}\n"
        f"  platforms={platforms}\n"
        f"  model={args.model}\n"
        f"  reasoning_effort={args.reasoning_effort}\n"
        f"  max_completion_tokens={args.max_completion_tokens}\n"
        f"  platform_timeout_sec={args.platform_timeout_sec}\n"
        f"  experiment_variant={get_prompt_experiment_variant()}"
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
                platform_timeout_sec=args.platform_timeout_sec,
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

    default_results = str(DEFAULT_RESULTS_PATH)
    requested_results = Path(args.results_path)
    if args.results_path == default_results or requested_results.exists():
        results_path = requested_results.with_name(
            f"{requested_results.stem}-{args.sku.replace('/', '-')}-{run_timestamp}{requested_results.suffix or '.md'}"
        )
    else:
        results_path = requested_results
    results_path.parent.mkdir(parents=True, exist_ok=True)
    results_path.write_text(report)

    raw_dir = Path(args.raw_dir)
    if raw_dir.exists():
        raw_dir = raw_dir / f"run-{args.sku.replace('/', '-')}-{run_timestamp}"
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
