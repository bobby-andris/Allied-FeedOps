#!/usr/bin/env python3
"""A/B test prompt variations for content generation quality.

Tests 3 prompt variations (Current, Minimal, Optimized) against
representative and unseen SKUs to validate the new prompt architecture.

Usage:
    # Dry run (no API calls, just validates loading):
    PYTHONPATH=./src .venv/bin/python scripts/ab_prompt_test.py --dry-run

    # Full run with all 3 variations:
    set -a && source .env.vercel && set +a
    PYTHONPATH=./src .venv/bin/python scripts/ab_prompt_test.py

    # Single SKU quick test:
    PYTHONPATH=./src .venv/bin/python scripts/ab_prompt_test.py --sku 1025U

Output:
    - /tmp/ab_test_outputs/ — raw JSON outputs per SKU x variation
    - .planning/phases/25.1-prompt-architecture-research/ab-test-results.md
"""

from __future__ import annotations

import argparse
import asyncio
import collections
import json
import logging
import os
import re
import sys
import time
from pathlib import Path

# ---------------------------------------------------------------------------
# Environment loading
# ---------------------------------------------------------------------------

def load_env_file(path: str) -> None:
    """Load environment variables from a dotenv-style file."""
    env_path = Path(path)
    if not env_path.exists():
        return
    for line in env_path.read_text().splitlines():
        line = line.strip()
        if not line or line.startswith("#"):
            continue
        if "=" in line:
            key, _, value = line.partition("=")
            key = key.strip()
            value = value.strip().strip('"').strip("'")
            os.environ.setdefault(key, value)


project_root = Path(__file__).parent.parent
load_env_file(str(project_root / ".env.vercel"))

# ---------------------------------------------------------------------------
# Imports (after env loaded)
# ---------------------------------------------------------------------------

try:
    import tiktoken
except ImportError:
    print("ERROR: tiktoken not installed. Run: pip install tiktoken", file=sys.stderr)
    sys.exit(1)

from openai import AsyncOpenAI

from feedops.api.prompt_loader import get_system_prompt
from feedops.api.prompt_builder import build_core_prompt
from feedops.api.supabase_loader import load_parent_sku_from_supabase
from feedops.pipeline.evidence import build_evidence_table, format_evidence_markdown
from feedops.pipeline.prompts import (
    CANDIDATE_SCHEMA,
    SYSTEM_PROMPT as CANONICAL_SYSTEM_PROMPT,
)
from feedops.providers.openai_provider import _build_strict_schema

logging.basicConfig(level=logging.WARNING)
logger = logging.getLogger(__name__)


# Simplified schema for Variation C (3-criterion self-score)
CANDIDATE_SCHEMA_V2 = {
    "type": "object",
    "properties": {
        "google_title": {
            "type": "string",
            "description": "Google Shopping title (max 150 characters)",
            "maxLength": 150,
        },
        "google_short_title": {
            "type": "string",
            "description": "Google short title (max 70 characters)",
            "maxLength": 70,
        },
        "google_description": {
            "type": "string",
            "description": "Google Shopping description (target 700-900 characters)",
        },
        "bing_title": {
            "type": "string",
            "description": "Bing Shopping title (max 150 characters)",
            "maxLength": 150,
        },
        "bing_description": {
            "type": "string",
            "description": "Bing Shopping description (target 700-1000 characters)",
        },
        "shopify_title": {
            "type": "string",
            "description": "Shopify product title (max 255 characters)",
            "maxLength": 255,
        },
        "shopify_description": {
            "type": "string",
            "description": "Shopify product description (HTML allowed)",
        },
        "shopify_meta_description": {
            "type": "string",
            "description": "Shopify SEO meta description (target 140-155 characters)",
            "maxLength": 155,
        },
        "claims": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "claim": {"type": "string"},
                    "source_field": {"type": "string"},
                    "source_value": {"type": "string"},
                },
                "required": ["claim", "source_field", "source_value"],
            },
        },
        "self_score": {
            "type": "object",
            "properties": {
                "accuracy": {"type": "integer", "minimum": 0, "maximum": 10, "description": "All claims traceable to evidence? 10=every claim sourced, 0=fabricated content"},
                "specificity": {"type": "integer", "minimum": 0, "maximum": 10, "description": "Could this ONLY describe this exact product? 10=unmistakable, 0=could be any competitor's listing"},
                "engagement": {"type": "integer", "minimum": 0, "maximum": 10, "description": "Would a shopper click or keep scrolling? 10=compelling, 0=invisible"},
            },
            "required": ["accuracy", "specificity", "engagement"],
        },
    },
    "required": [
        "google_title", "google_short_title", "google_description",
        "bing_title", "bing_description",
        "shopify_title", "shopify_description", "shopify_meta_description",
        "claims", "self_score",
    ],
}


def _build_v2_strict_schema() -> dict:
    """Build strict schema for the V2 simplified prompt."""
    def _make_strict(schema: dict) -> dict:
        result = dict(schema)
        if result.get("type") == "object":
            result["additionalProperties"] = False
            if "properties" in result:
                props = result["properties"]
                existing_required = set(result.get("required", []))
                all_props = set(props.keys())
                result["required"] = sorted(all_props | existing_required)
                result["properties"] = {k: _make_strict(v) for k, v in props.items()}
        elif result.get("type") == "array" and "items" in result:
            result["items"] = _make_strict(result["items"])
        return result

    strict_schema = _make_strict(CANDIDATE_SCHEMA_V2)
    return {
        "type": "json_schema",
        "json_schema": {
            "name": "candidate_content",
            "strict": True,
            "schema": strict_schema,
        },
    }

enc = tiktoken.get_encoding("o200k_base")

# ---------------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------------

# Representative SKUs from evaluation set (different failure modes):
# - 1025U: Paper Towel Holder — had keyword stuffing in titles
# - WP-2/16-GAL: Glass Shelf — had filler-heavy descriptions, weight capacity issues
# - DMF-2/2X: Make-Up Mirror — monotonous structure, weak differentiation
REPRESENTATIVE_SKUS = ["1025U", "WP-2/16-GAL", "DMF-2/2X"]

# Unseen SKUs NOT in the 10 evaluation set
# (10 eval: 1025U, 1016, 102, 1020-3, 1024, 1020, DMF-2/2X, WP-2/16-GAL, 1098, CL-22)
# Chosen for category variety:
# - 1026: Tumbler Toothbrush Holders (small accessories category)
# - 1031/18: Towel Bars (high-volume category, different product)
# - 1032: Soap Dishes (different accessory type)
UNSEEN_SKUS = ["1026", "1031/18", "1032"]

OUTPUT_DIR = Path("/tmp/ab_test_outputs")
RESULTS_PATH = project_root / ".planning" / "phases" / "25.1-prompt-architecture-research" / "ab-test-results.md"

# Banned/filler words for analysis
FILLER_WORDS = [
    "premium", "luxurious", "finest", "exceptional", "unparalleled",
    "superior", "exquisite", "ultimate", "exclusive", "upgrade your bathroom",
    "transform your", "elevate your", "stunning", "gorgeous", "beautiful",
]

ROBERTS_CONCERNS = [
    "die-cast zinc", "zinc alloy", "plated alternatives", "chrome-plated steel",
    "hollow zinc", "heritage bathroom fixtures", "weight capacity",
    "also searched as", "also known as", "28 finishes", "28+ finishes",
    "spring-loaded", "spring mechanism",
]


# ---------------------------------------------------------------------------
# Token counting
# ---------------------------------------------------------------------------

def count_tokens(text: str) -> int:
    return len(enc.encode(text))


# ---------------------------------------------------------------------------
# Load the new system prompt from file
# ---------------------------------------------------------------------------

def load_new_system_prompt() -> str:
    """Load the new optimized system prompt from Plan 02 output."""
    prompt_path = (
        project_root / ".planning" / "phases"
        / "25.1-prompt-architecture-research" / "new-system-prompt.txt"
    )
    text = prompt_path.read_text()
    # Strip the header metadata (everything before the first <context> tag)
    idx = text.find("<context>")
    if idx >= 0:
        return text[idx:]
    return text


def load_new_user_template() -> str:
    """Load the new user prompt template from Plan 02 output."""
    template_path = (
        project_root / ".planning" / "phases"
        / "25.1-prompt-architecture-research" / "new-user-prompt-template.txt"
    )
    text = template_path.read_text()
    # Extract the master SKU template (first template, before the VARIANT section)
    variant_marker = "VARIANT USER PROMPT TEMPLATE"
    idx = text.find(variant_marker)
    if idx >= 0:
        text = text[:idx]
    # Strip the file header
    task_idx = text.find("<task>")
    if task_idx >= 0:
        return text[task_idx:]
    return text


# ---------------------------------------------------------------------------
# Build prompts for each variation
# ---------------------------------------------------------------------------

def build_variation_a(parent_sku, evidence, evidence_md) -> tuple[str, str]:
    """Variation A: Current production prompt (full skills injection)."""
    system = get_system_prompt(mode="batch")
    user = build_core_prompt(
        parent_sku=parent_sku,
        evidence=evidence,
        evidence_markdown=evidence_md,
        platform="google",
        content_type="title and description",
    )
    return system, user


def build_variation_b(parent_sku, evidence, evidence_md) -> tuple[str, str]:
    """Variation B: Minimal — SYSTEM_PROMPT base only, no skills."""
    system = CANONICAL_SYSTEM_PROMPT
    user = build_core_prompt(
        parent_sku=parent_sku,
        evidence=evidence,
        evidence_markdown=evidence_md,
        platform="google",
        content_type="title and description",
    )
    return system, user


def build_variation_c(parent_sku, evidence, evidence_md) -> tuple[str, str]:
    """Variation C: Optimized — new CTCO prompt from Plan 02."""
    system = load_new_system_prompt()

    # Build user prompt from the new template structure with actual data
    # We use the evidence and product data but in the new template format
    user_parts: list[str] = []

    user_parts.append(f"<task>\nGenerate one complete JSON object for MasterSKU: {parent_sku.master_sku}.\n"
                      "Use only information in the inputs below. Every claim must trace to a field in the evidence table.\n</task>")

    user_parts.append(f"<inputs>\n\n<evidence_table>\n{evidence_md}\n</evidence_table>")

    # Keyword placement
    try:
        from feedops.pipeline.keyword_placement import (
            build_keyword_placement_plan,
            format_keyword_placement_section,
        )
        kw_plan = build_keyword_placement_plan(parent_sku, evidence)
        kw_section = format_keyword_placement_section(kw_plan)
        if kw_section:
            user_parts.append(f"<keyword_placement>\n{kw_section}\n</keyword_placement>")
    except Exception:
        pass

    # Category guidance
    from feedops.api.prompt_loader import get_category_guidance
    cat_guidance = get_category_guidance(parent_sku.category)
    if cat_guidance:
        user_parts.append(f"<category_guidance>\n{cat_guidance}\n</category_guidance>")

    # Product design story
    story_parts: list[str] = []
    if parent_sku.category:
        story_parts.append(f"Product category: {parent_sku.category}")
    for item in parent_sku.merchant_center_items or []:
        col = item.get("collection") or ""
        if col:
            story_parts.append(f"Collection: {col}")
            break
    if parent_sku.current_description and parent_sku.current_description != parent_sku.current_title:
        story_parts.append(f"Manufacturer description: {parent_sku.current_description}")
    bullets = []
    for attr in ["bullet_1", "bullet_2", "bullet_3", "bullet_4"]:
        val = getattr(parent_sku, attr, None)
        if val and val.strip():
            bullets.append(val.strip())
    if bullets:
        story_parts.append("Product selling points:\n" + "\n".join(f"- {b}" for b in bullets))
    if story_parts:
        user_parts.append(f"<product_design_story>\n" + "\n".join(story_parts) + "\n</product_design_story>")

    # Competitive positioning — positive only
    comp_parts: list[str] = []
    for ev in evidence:
        if isinstance(ev, dict):
            material = ev.get("material") or ev.get("Material") or ""
            if "brass" in str(material).lower():
                comp_parts.append("Evidence confirms: solid brass construction")
                break
    if comp_parts:
        user_parts.append(f"<competitive_positioning>\n" + "\n".join(comp_parts) + "\n</competitive_positioning>")

    # Gold examples (from Supabase)
    from feedops.api.prompt_loader import format_gold_standard_examples_bundle
    try:
        gold = format_gold_standard_examples_bundle(max_examples=2)
        if gold:
            user_parts.append(f"<gold_examples>\n{gold}\n</gold_examples>")
    except Exception:
        pass

    user_parts.append("</inputs>")

    # Output contract with V2 schema (simplified self-score)
    schema_str = json.dumps(CANDIDATE_SCHEMA_V2, indent=2)
    user_parts.append(f"<output_contract>\nReturn ONLY valid JSON matching this schema:\n{schema_str}\n</output_contract>")

    user = "\n\n".join(user_parts)
    return system, user


VARIATION_BUILDERS = {
    "A_Current": build_variation_a,
    "B_Minimal": build_variation_b,
    "C_Optimized": build_variation_c,
}


# ---------------------------------------------------------------------------
# OpenAI call
# ---------------------------------------------------------------------------

async def generate_content(
    client: AsyncOpenAI,
    system_prompt: str,
    user_prompt: str,
    model: str = "gpt-5.2",
    use_v2_schema: bool = False,
) -> tuple[dict | None, dict]:
    """Call OpenAI and return (parsed_json, usage_info)."""
    schema_format = _build_v2_strict_schema() if use_v2_schema else _build_strict_schema()
    try:
        response = await client.chat.completions.create(
            model=model,
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt},
            ],
            response_format=schema_format,
            reasoning_effort="medium",
            max_completion_tokens=4000,
        )
        content = response.choices[0].message.content
        usage = {
            "prompt_tokens": getattr(response.usage, "prompt_tokens", 0) or 0,
            "completion_tokens": getattr(response.usage, "completion_tokens", 0) or 0,
        }
        try:
            cached = response.usage.prompt_tokens_details.cached_tokens
        except Exception:
            cached = 0
        usage["cached_tokens"] = cached or 0

        if content is None:
            finish_reason = response.choices[0].finish_reason
            logger.error(f"Response content is None (finish_reason={finish_reason})")
            return None, {**usage, "error": f"Content is None, finish_reason={finish_reason}"}

        return json.loads(content), usage
    except json.JSONDecodeError as e:
        logger.error(f"JSON parse failed: {e}, content={repr(content)[:200]}")
        return None, {"prompt_tokens": 0, "completion_tokens": 0, "cached_tokens": 0, "error": f"JSON: {e}"}
    except Exception as e:
        logger.error(f"Generation failed: {e}")
        return None, {"prompt_tokens": 0, "completion_tokens": 0, "cached_tokens": 0, "error": str(e)}


# ---------------------------------------------------------------------------
# Analysis functions
# ---------------------------------------------------------------------------

def count_repeated_words(text: str, threshold: int = 4) -> list[tuple[str, int]]:
    """Count non-trivial words that appear 4+ times."""
    words = re.findall(r'\b[a-z]{4,}\b', text.lower())
    # Exclude common stop words
    stop_words = {
        "that", "this", "with", "from", "your", "have", "will", "been",
        "each", "into", "when", "than", "also", "them", "they", "more",
        "only", "over", "such", "some", "very", "make", "most", "just",
        "about", "made", "like", "does", "every", "well", "which", "what",
        "their", "there", "these", "those",
    }
    counts = collections.Counter(w for w in words if w not in stop_words)
    return [(w, c) for w, c in counts.most_common() if c >= threshold]


def count_filler(text: str) -> list[str]:
    """Count filler/banned words and phrases."""
    found = []
    text_lower = text.lower()
    for filler in FILLER_WORDS:
        if filler.lower() in text_lower:
            found.append(filler)
    return found


def check_roberts_concerns(text: str) -> list[str]:
    """Check for Robert's prohibited content."""
    found = []
    text_lower = text.lower()
    for concern in ROBERTS_CONCERNS:
        if concern.lower() in text_lower:
            found.append(concern)
    return found


def analyze_structure(text: str) -> dict:
    """Analyze description structure."""
    sentences = re.split(r'[.!?]+', text)
    sentences = [s.strip() for s in sentences if s.strip()]
    opening_words = []
    for s in sentences[:5]:
        words = s.split()
        if words:
            opening_words.append(words[0])
    return {
        "sentence_count": len(sentences),
        "word_count": len(text.split()),
        "char_count": len(text),
        "opening_words": opening_words,
    }


def claims_per_100_words(text: str) -> float:
    """Estimate factual claims per 100 words (proxy for info density)."""
    words = text.split()
    if not words:
        return 0.0
    # Count sentences that contain specific product details
    claim_patterns = [
        r'\d+[\s-]?(?:inch|mm|cm|oz)',  # dimensions
        r'solid brass',
        r'concealed',
        r'wall[- ]mount',
        r'collection',
        r'limited lifetime warranty',
        r'made in (?:usa|the usa)',
    ]
    claims = 0
    text_lower = text.lower()
    for pattern in claim_patterns:
        claims += len(re.findall(pattern, text_lower))
    return round(claims / len(words) * 100, 1)


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def load_sku_data(sku: str):
    """Load parent SKU and build evidence."""
    parent_sku = load_parent_sku_from_supabase(sku)
    if not parent_sku:
        print(f"  WARNING: SKU {sku} not found in database, skipping")
        return None, None, None
    evidence = build_evidence_table(parent_sku)
    evidence_md = format_evidence_markdown(evidence)
    return parent_sku, evidence, evidence_md


async def run_test(
    skus: list[str],
    variations: list[str],
    dry_run: bool = False,
    model: str = "gpt-5.2",
) -> dict:
    """Run the A/B test across all SKUs and variations."""
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    results = {}

    client = None
    if not dry_run:
        api_key = os.environ.get("OPENAI_API_KEY")
        if not api_key:
            print("ERROR: OPENAI_API_KEY not set. Use --dry-run or source .env.vercel", file=sys.stderr)
            sys.exit(1)
        client = AsyncOpenAI(api_key=api_key)

    for sku in skus:
        print(f"\n{'='*60}")
        print(f"SKU: {sku}")
        print(f"{'='*60}")

        parent_sku, evidence, evidence_md = load_sku_data(sku)
        if not parent_sku:
            continue

        results[sku] = {"category": parent_sku.category or "Unknown"}

        for var_name in variations:
            builder = VARIATION_BUILDERS[var_name]
            system_prompt, user_prompt = builder(parent_sku, evidence, evidence_md)

            sys_tokens = count_tokens(system_prompt)
            user_tokens = count_tokens(user_prompt)
            sys_chars = len(system_prompt)

            print(f"\n  Variation {var_name}:")
            print(f"    System: {sys_chars:,} chars / {sys_tokens:,} tokens")
            print(f"    User:   {len(user_prompt):,} chars / {user_tokens:,} tokens")

            if dry_run:
                # Save prompts for inspection (sanitize SKU for filesystem)
                safe_sku = sku.replace("/", "-")
                (OUTPUT_DIR / f"{safe_sku}_{var_name}_system.txt").write_text(system_prompt)
                (OUTPUT_DIR / f"{safe_sku}_{var_name}_user.txt").write_text(user_prompt)
                results[sku][var_name] = {
                    "system_chars": sys_chars,
                    "system_tokens": sys_tokens,
                    "user_tokens": user_tokens,
                    "dry_run": True,
                }
                continue

            # Call OpenAI
            print(f"    Calling {model}...")
            t0 = time.time()
            use_v2 = var_name == "C_Optimized"
            parsed, usage = await generate_content(client, system_prompt, user_prompt, model, use_v2_schema=use_v2)
            elapsed = time.time() - t0
            print(f"    Done in {elapsed:.1f}s | Tokens: prompt={usage.get('prompt_tokens',0):,} completion={usage.get('completion_tokens',0):,} cached={usage.get('cached_tokens',0):,}")

            if parsed:
                # Save raw output (sanitize SKU for filesystem)
                safe_sku = sku.replace("/", "-")
                out_path = OUTPUT_DIR / f"{safe_sku}_{var_name}_output.json"
                out_path.write_text(json.dumps(parsed, indent=2))

                google_title = parsed.get("google_title", "")
                google_desc = parsed.get("google_description", "")
                bing_title = parsed.get("bing_title", "")
                bing_desc = parsed.get("bing_description", "")
                shopify_title = parsed.get("shopify_title", "")
                shopify_desc = parsed.get("shopify_description", "")

                # Quick summary
                print(f"    Google Title: {google_title[:80]}...")
                print(f"    Desc length:  {len(google_desc)} chars")

                # Analysis
                all_text = f"{google_title} {google_desc} {bing_title} {bing_desc}"
                repeated = count_repeated_words(all_text)
                filler = count_filler(all_text)
                concerns = check_roberts_concerns(all_text)
                structure = analyze_structure(google_desc)
                density = claims_per_100_words(google_desc)

                if repeated:
                    print(f"    Keyword stuffing: {repeated[:3]}")
                if filler:
                    print(f"    Filler words: {filler}")
                if concerns:
                    print(f"    Robert's concerns: {concerns}")

                # Self-score
                self_score = parsed.get("self_score", {})
                if isinstance(self_score, dict):
                    score_total = sum(v for v in self_score.values() if isinstance(v, (int, float)))
                    score_count = sum(1 for v in self_score.values() if isinstance(v, (int, float)))
                    avg_score = score_total / score_count if score_count else 0
                    print(f"    Self-score avg: {avg_score:.1f} (total: {score_total}/{score_count * 10})")
                else:
                    score_total = 0
                    avg_score = 0

                results[sku][var_name] = {
                    "system_chars": sys_chars,
                    "system_tokens": sys_tokens,
                    "user_tokens": user_tokens,
                    "usage": usage,
                    "elapsed": elapsed,
                    "google_title": google_title,
                    "google_description": google_desc,
                    "bing_title": bing_title,
                    "bing_description": bing_desc,
                    "shopify_title": shopify_title,
                    "shopify_description": shopify_desc,
                    "self_score": self_score,
                    "self_score_total": score_total,
                    "self_score_avg": avg_score,
                    "repeated_words": repeated,
                    "filler_words": filler,
                    "roberts_concerns": concerns,
                    "structure": structure,
                    "claims_density": density,
                    "parsed": parsed,
                }
            else:
                results[sku][var_name] = {
                    "system_chars": sys_chars,
                    "system_tokens": sys_tokens,
                    "error": usage.get("error", "Unknown error"),
                }

    return results


# ---------------------------------------------------------------------------
# Results document generation
# ---------------------------------------------------------------------------

def generate_results_doc(results: dict, all_skus: list[str], variations: list[str]) -> str:
    """Generate the ab-test-results.md document."""
    lines: list[str] = []
    lines.append("# A/B Prompt Testing Results")
    lines.append("")
    lines.append(f"**Date:** {time.strftime('%Y-%m-%d')}")
    lines.append("**Phase:** 25.1-prompt-architecture-research, Plan 03")
    lines.append("**Model:** GPT-5.2 (reasoning_effort=medium)")
    lines.append("")

    # Summary table
    lines.append("## Summary Table")
    lines.append("")
    lines.append("| SKU | Category | Variation | Google Title (first 70 chars) | Desc Length | Self Score Avg | Keyword Stuffing | Filler | Robert's Concerns |")
    lines.append("|-----|----------|-----------|-------------------------------|-------------|----------------|------------------|--------|-------------------|")

    for sku in all_skus:
        sku_data = results.get(sku, {})
        category = sku_data.get("category", "?")
        for var in variations:
            var_data = sku_data.get(var, {})
            if "error" in var_data or var_data.get("dry_run"):
                lines.append(f"| {sku} | {category} | {var} | ERROR | - | - | - | - | - |")
                continue
            title = var_data.get("google_title", "")[:70]
            desc_len = len(var_data.get("google_description", ""))
            avg_score = var_data.get("self_score_avg", 0)
            repeated = var_data.get("repeated_words", [])
            stuffing = ", ".join(f"{w}({c})" for w, c in repeated[:2]) if repeated else "None"
            filler = ", ".join(var_data.get("filler_words", [])[:2]) or "None"
            concerns = ", ".join(var_data.get("roberts_concerns", [])[:2]) or "None"
            lines.append(f"| {sku} | {category} | {var} | {title} | {desc_len} | {avg_score:.1f} | {stuffing} | {filler} | {concerns} |")

    # Token usage comparison
    lines.append("")
    lines.append("## Token Usage Comparison")
    lines.append("")
    lines.append("| Variation | System Chars | System Tokens | Avg Prompt Tokens | Avg Completion Tokens | Avg Cached Tokens |")
    lines.append("|-----------|-------------|---------------|-------------------|----------------------|-------------------|")

    for var in variations:
        sys_chars_list = []
        sys_tokens_list = []
        prompt_tokens_list = []
        comp_tokens_list = []
        cached_tokens_list = []
        for sku in all_skus:
            var_data = results.get(sku, {}).get(var, {})
            if var_data.get("dry_run") or "error" in var_data:
                continue
            sys_chars_list.append(var_data.get("system_chars", 0))
            sys_tokens_list.append(var_data.get("system_tokens", 0))
            usage = var_data.get("usage", {})
            prompt_tokens_list.append(usage.get("prompt_tokens", 0))
            comp_tokens_list.append(usage.get("completion_tokens", 0))
            cached_tokens_list.append(usage.get("cached_tokens", 0))

        def avg(lst):
            return sum(lst) / len(lst) if lst else 0

        lines.append(
            f"| {var} | {avg(sys_chars_list):,.0f} | {avg(sys_tokens_list):,.0f} | "
            f"{avg(prompt_tokens_list):,.0f} | {avg(comp_tokens_list):,.0f} | {avg(cached_tokens_list):,.0f} |"
        )

    # Side-by-side comparisons for each SKU
    lines.append("")
    lines.append("## Side-by-Side Comparisons")

    for sku in all_skus:
        sku_data = results.get(sku, {})
        category = sku_data.get("category", "?")
        is_representative = sku in REPRESENTATIVE_SKUS

        lines.append("")
        lines.append(f"### {sku} ({category}) {'[Representative]' if is_representative else '[Unseen]'}")
        lines.append("")

        for var in variations:
            var_data = sku_data.get(var, {})
            if "error" in var_data or var_data.get("dry_run"):
                lines.append(f"**{var}:** Error or dry run")
                continue

            lines.append(f"#### {var}")
            lines.append("")
            lines.append(f"**Google Title:** {var_data.get('google_title', 'N/A')}")
            lines.append(f"**Google Short Title:** {var_data.get('parsed', {}).get('google_short_title', 'N/A')}")
            lines.append("")
            lines.append(f"**Google Description** ({len(var_data.get('google_description', ''))} chars):")
            lines.append(f"> {var_data.get('google_description', 'N/A')}")
            lines.append("")
            lines.append(f"**Bing Title:** {var_data.get('bing_title', 'N/A')}")
            lines.append("")
            lines.append(f"**Bing Description** ({len(var_data.get('bing_description', ''))} chars):")
            lines.append(f"> {var_data.get('bing_description', 'N/A')}")
            lines.append("")
            lines.append(f"**Shopify Title:** {var_data.get('shopify_title', 'N/A')}")
            lines.append("")

            # Analysis
            repeated = var_data.get("repeated_words", [])
            filler = var_data.get("filler_words", [])
            concerns = var_data.get("roberts_concerns", [])
            structure = var_data.get("structure", {})
            density = var_data.get("claims_density", 0)

            lines.append("**Analysis:**")
            lines.append(f"- Keyword stuffing: {'FLAGGED ' + str(repeated[:3]) if repeated else 'Clean'}")
            lines.append(f"- Filler words: {'FLAGGED ' + str(filler) if filler else 'Clean'}")
            lines.append(f"- Robert's concerns: {'FLAGGED ' + str(concerns) if concerns else 'Clean'}")
            lines.append(f"- Structure: {structure.get('sentence_count', 0)} sentences, {structure.get('word_count', 0)} words")
            lines.append(f"- Opening words: {structure.get('opening_words', [])}")
            lines.append(f"- Claims density: {density} per 100 words")

            self_score = var_data.get("self_score", {})
            if isinstance(self_score, dict) and self_score:
                score_items = ", ".join(f"{k}={v}" for k, v in self_score.items() if isinstance(v, (int, float)))
                lines.append(f"- Self-score: {score_items}")

            lines.append("")

    # Comparative analysis
    lines.append("## Comparative Analysis")
    lines.append("")

    # Aggregate metrics
    for metric_name, metric_key, higher_better in [
        ("Keyword Stuffing (fewer = better)", "repeated_words", False),
        ("Filler Words (fewer = better)", "filler_words", False),
        ("Robert's Concerns (fewer = better)", "roberts_concerns", False),
        ("Description Length (chars)", "google_description", None),
        ("Claims Density (per 100 words)", "claims_density", True),
    ]:
        lines.append(f"### {metric_name}")
        lines.append("")
        lines.append("| Variation | Metric Value |")
        lines.append("|-----------|-------------|")
        for var in variations:
            values = []
            for sku in all_skus:
                var_data = results.get(sku, {}).get(var, {})
                if "error" in var_data or var_data.get("dry_run"):
                    continue
                if metric_key in ("repeated_words", "filler_words", "roberts_concerns"):
                    values.append(len(var_data.get(metric_key, [])))
                elif metric_key == "google_description":
                    values.append(len(var_data.get(metric_key, "")))
                elif metric_key == "claims_density":
                    values.append(var_data.get(metric_key, 0))
            avg_val = sum(values) / len(values) if values else 0
            lines.append(f"| {var} | {avg_val:.1f} |")
        lines.append("")

    # Structure variety analysis
    lines.append("### Structure Variety")
    lines.append("")
    lines.append("Opening words across all SKUs per variation:")
    lines.append("")
    for var in variations:
        all_openings = []
        for sku in all_skus:
            var_data = results.get(sku, {}).get(var, {})
            structure = var_data.get("structure", {})
            first_word = (structure.get("opening_words", [None]) or [None])[0]
            if first_word:
                all_openings.append(first_word)
        unique_ratio = len(set(all_openings)) / len(all_openings) if all_openings else 0
        lines.append(f"- **{var}:** {all_openings} (unique ratio: {unique_ratio:.0%})")
    lines.append("")

    # Overall recommendation
    lines.append("## Recommendation")
    lines.append("")

    # Compute aggregate winner
    var_scores: dict[str, dict] = {v: {"stuffing": 0, "filler": 0, "concerns": 0, "density": 0.0, "count": 0} for v in variations}
    for var in variations:
        for sku in all_skus:
            var_data = results.get(sku, {}).get(var, {})
            if "error" in var_data or var_data.get("dry_run"):
                continue
            var_scores[var]["stuffing"] += len(var_data.get("repeated_words", []))
            var_scores[var]["filler"] += len(var_data.get("filler_words", []))
            var_scores[var]["concerns"] += len(var_data.get("roberts_concerns", []))
            var_scores[var]["density"] += var_data.get("claims_density", 0)
            var_scores[var]["count"] += 1

    for var in variations:
        cnt = var_scores[var]["count"] or 1
        lines.append(f"**{var}:**")
        lines.append(f"- Total keyword stuffing instances: {var_scores[var]['stuffing']}")
        lines.append(f"- Total filler word instances: {var_scores[var]['filler']}")
        lines.append(f"- Total Robert's concern violations: {var_scores[var]['concerns']}")
        lines.append(f"- Avg claims density: {var_scores[var]['density'] / cnt:.1f} per 100 words")
        lines.append("")

    # Determine winner
    c_data = var_scores.get("C_Optimized", {})
    a_data = var_scores.get("A_Current", {})
    if c_data.get("count", 0) > 0 and a_data.get("count", 0) > 0:
        c_better_stuffing = c_data["stuffing"] < a_data["stuffing"]
        c_better_filler = c_data["filler"] < a_data["filler"]
        c_better_concerns = c_data["concerns"] < a_data["concerns"]
        wins = sum([c_better_stuffing, c_better_filler, c_better_concerns])
        if wins >= 2:
            lines.append("**Verdict: Variation C (Optimized) wins on the majority of quality metrics.**")
            lines.append("The new CTCO prompt architecture produces content with less keyword stuffing, fewer filler words, and fewer violations of Robert's evaluation concerns.")
        elif wins == 1:
            lines.append("**Verdict: Mixed results — Variation C shows improvement on some metrics but not all.**")
            lines.append("Further iteration or tuning may be needed.")
        else:
            lines.append("**Verdict: Variation A (Current) performed comparably or better on automated metrics.**")
            lines.append("Human review is critical to assess qualitative differences the metrics may not capture.")
    else:
        lines.append("**Verdict: Insufficient data for automated recommendation. See human review checkpoint.**")

    lines.append("")
    lines.append("---")
    lines.append(f"*Generated: {time.strftime('%Y-%m-%d %H:%M UTC', time.gmtime())}*")
    lines.append(f"*Script: scripts/ab_prompt_test.py*")

    return "\n".join(lines)


# ---------------------------------------------------------------------------
# CLI entry point
# ---------------------------------------------------------------------------

def main():
    parser = argparse.ArgumentParser(description="A/B prompt testing for content generation")
    parser.add_argument("--dry-run", action="store_true", help="Validate loading without API calls")
    parser.add_argument("--sku", type=str, help="Test single SKU only")
    parser.add_argument("--model", type=str, default="gpt-5.2", help="Model to use")
    parser.add_argument("--variations", type=str, default="A_Current,B_Minimal,C_Optimized",
                        help="Comma-separated variation names")
    parser.add_argument("--unseen-only", action="store_true", help="Test only unseen SKUs")
    parser.add_argument("--representative-only", action="store_true", help="Test only representative SKUs")
    args = parser.parse_args()

    variations = args.variations.split(",")

    if args.sku:
        skus = [args.sku]
    elif args.unseen_only:
        skus = UNSEEN_SKUS
    elif args.representative_only:
        skus = REPRESENTATIVE_SKUS
    else:
        skus = REPRESENTATIVE_SKUS + UNSEEN_SKUS

    print(f"A/B Prompt Test")
    print(f"SKUs: {skus}")
    print(f"Variations: {variations}")
    print(f"Dry run: {args.dry_run}")
    print(f"Model: {args.model}")

    results = asyncio.run(run_test(skus, variations, dry_run=args.dry_run, model=args.model))

    if not args.dry_run:
        # Generate results document
        doc = generate_results_doc(results, skus, variations)
        RESULTS_PATH.parent.mkdir(parents=True, exist_ok=True)
        RESULTS_PATH.write_text(doc)
        print(f"\nResults written to: {RESULTS_PATH}")

    # Save raw results JSON
    raw_path = OUTPUT_DIR / "ab_test_results.json"
    # Serialize — remove non-serializable 'parsed' key
    serializable = {}
    for sku, sku_data in results.items():
        serializable[sku] = {}
        for k, v in sku_data.items():
            if isinstance(v, dict) and "parsed" in v:
                v2 = {k2: v2 for k2, v2 in v.items() if k2 != "parsed"}
                serializable[sku][k] = v2
            else:
                serializable[sku][k] = v
    raw_path.write_text(json.dumps(serializable, indent=2, default=str))
    print(f"Raw results: {raw_path}")


if __name__ == "__main__":
    main()
