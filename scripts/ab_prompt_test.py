#!/usr/bin/env python3
"""A/B test prompt variations for content generation quality (v2.1).

Tests 3 prompt variations (Current, Minimal, Optimized) with VARIANT-LEVEL
generation — each SKU is tested with a specific finish, because Google/Bing
content is always variant-level.

Key changes from v1:
- Variant-level generation: each SKU gets a specific finish
- {FINISH_NAME} must be first element in Google/Bing titles
- Finish context from finish-expertise skill injected per variant
- Competitor brand detection: flags if competitor names leak into content
- Gold standard examples included in system prompt (Variation C)

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
            "description": "Google Shopping title (max 150 characters). MUST start with the finish name.",
            "maxLength": 150,
        },
        "google_short_title": {
            "type": "string",
            "description": "Google short title (max 70 characters). Finish + product type + dimension.",
            "maxLength": 70,
        },
        "google_description": {
            "type": "string",
            "description": "Google Shopping description (target 700-900 characters)",
        },
        "bing_title": {
            "type": "string",
            "description": "Bing Shopping title (max 150 characters). MUST start with the finish name.",
            "maxLength": 150,
        },
        "bing_description": {
            "type": "string",
            "description": "Bing Shopping description (target 700-900 characters)",
        },
        "shopify_title": {
            "type": "string",
            "description": "Shopify product title (max 255 characters, finish-agnostic)",
            "maxLength": 255,
        },
        "shopify_description": {
            "type": "string",
            "description": "Shopify product description (HTML format, finish-agnostic)",
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

# Representative SKUs from evaluation set with SPECIFIC FINISHES
# (variant-level testing — Google/Bing content is ALWAYS variant-level)
REPRESENTATIVE_SKUS = [
    {"sku": "1025U", "finish_name": "Polished Nickel", "finish_code": "PNI"},
    {"sku": "WP-2/16-GAL", "finish_name": "Oil Rubbed Bronze", "finish_code": "ORB"},
    {"sku": "DMF-2/2X", "finish_name": "Satin Brass", "finish_code": "SBR"},
]

# Unseen SKUs with specific finishes
UNSEEN_SKUS = [
    {"sku": "1026", "finish_name": "Antique Brass", "finish_code": "ABR"},
    {"sku": "1031/18", "finish_name": "Matte Black", "finish_code": "BKM"},
    {"sku": "1032", "finish_name": "Polished Chrome", "finish_code": "PC"},
]

# Finish context data (distilled from finish-expertise SKILL.md)
FINISH_CONTEXT_DATA = {
    "PNI": {
        "visual": "Warm silver with subtle golden undertones. Mirror-like but noticeably warmer than chrome.",
        "design_style": "Transitional, updated traditional, classic modern. The designer's alternative to chrome.",
        "pairs_with": "Polished nickel faucets, mixed metals, marble, warm-toned tiles, crystal.",
        "search_terms": "polished nickel bathroom hardware, polished nickel towel bar, warm silver bathroom accessories",
        "compelling_sentence": "Polished Nickel gives this piece a warm silver glow — richer than chrome, with subtle golden undertones that designers choose for transitional bathrooms.",
    },
    "ORB": {
        "visual": "Deep, dark brown-black with subtle copper/bronze highlights at edges. Rich, warm, with visible hand-rubbed character.",
        "design_style": "Traditional, rustic, industrial, craftsman, transitional.",
        "pairs_with": "Oil rubbed bronze faucets, dark wood, natural stone, warm tiles, copper accents.",
        "search_terms": "oil rubbed bronze towel bar, oil rubbed bronze bathroom hardware, dark bronze bathroom accessories",
        "compelling_sentence": "Oil Rubbed Bronze gives this piece rich, dark depth with subtle warm highlights that catch the light at edges — the go-to finish for bathrooms with traditional warmth.",
    },
    "SBR": {
        "visual": "Brushed golden surface with a soft, muted luster. Warmer than gold, less reflective than polished brass.",
        "design_style": "Transitional, modern farmhouse, contemporary warm. The 'it' finish in current design.",
        "pairs_with": "Brushed gold faucets, warm LED lighting, white oak vanities, quartz countertops.",
        "search_terms": "satin brass bathroom hardware, brushed brass towel bar, brushed gold bathroom accessories",
        "compelling_sentence": "Satin Brass softens the golden tone with a brushed texture that hides fingerprints and water spots — one of the most-specified finishes in current bathroom design.",
    },
    "ABR": {
        "visual": "Darkened golden-brown with a softened, aged patina. Warm but subdued — the look of brass that's been in a home for generations.",
        "design_style": "Traditional, vintage, colonial, English country.",
        "pairs_with": "Oil rubbed bronze, antique copper, warm wood tones, traditional fixtures.",
        "search_terms": "antique brass bathroom hardware, aged brass towel bar, vintage brass bath accessories",
        "compelling_sentence": "The Antique Brass finish gives this piece the warmth of hardware that's been in the family for generations — a softened golden patina that feels collected, not installed.",
    },
    "BKM": {
        "visual": "Deep, uniform black with zero reflections. Smooth, non-glossy surface. Bold and architectural.",
        "design_style": "Modern, industrial, contemporary, minimalist, farmhouse modern. Fastest-growing finish.",
        "pairs_with": "Matte black faucets, white tile, concrete, natural wood, mixed metals.",
        "search_terms": "matte black towel bar, black bathroom hardware, matte black bath accessories",
        "compelling_sentence": "Matte Black makes this piece a bold architectural element — the zero-reflection surface creates clean contrast against light tile and modern bathroom palettes.",
    },
    "PC": {
        "visual": "Bright, mirror-like silver with crisp reflections. Cool-toned, high-contrast. Most reflective finish.",
        "design_style": "Modern, contemporary, minimalist, traditional (versatile). The universal finish.",
        "pairs_with": "Chrome faucets, stainless steel, glass, white subway tile, modern fixtures.",
        "search_terms": "chrome towel bar, polished chrome bathroom accessories, chrome bath hardware",
        "compelling_sentence": "The Polished Chrome finish gives this piece a bright, mirror-like surface that matches the chrome faucets found in most American bathrooms.",
    },
}

# Competitor brand names to detect in generated content
COMPETITOR_BRANDS = [
    "jan barboglio", "kingston brass", "moen", "delta", "kohler",
    "american standard", "pfister", "brizo", "grohe", "hansgrohe",
    "restoration hardware", "pottery barn", "home depot", "lowes",
]

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


# ---------------------------------------------------------------------------
# Build finish context for variant-level generation
# ---------------------------------------------------------------------------

def build_finish_context(finish_name: str, finish_code: str) -> str:
    """Build finish context section for variant-level generation."""
    data = FINISH_CONTEXT_DATA.get(finish_code, {})
    if not data:
        # Fallback for unknown finishes
        return (
            f"<finish_context>\n"
            f"Generating content for finish: {finish_name}\n\n"
            f"{finish_name} MUST be the FIRST element in every Google and Bing title.\n"
            f"</finish_context>"
        )

    return (
        f"<finish_context>\n"
        f"Generating content for finish: {finish_name}\n\n"
        f"{finish_name} MUST be the FIRST element in every Google and Bing title.\n\n"
        f"Finish details:\n"
        f"- Finish code: {finish_code}\n"
        f"- Visual character: {data['visual']}\n"
        f"- Design style: {data['design_style']}\n"
        f"- Pairs with: {data['pairs_with']}\n"
        f"- Search behavior: {data['search_terms']}\n\n"
        f"Finish sentence for {{FINISH_SENTENCE}} placeholder:\n"
        f"{data['compelling_sentence']}\n\n"
        f"Integration rules for {{FINISH_SENTENCE}}:\n"
        f"- Place AFTER the opening hook sentence and BEFORE construction details\n"
        f"- Flow naturally as part of the product narrative\n"
        f"- GOOD: \"This 24-inch towel bar is constructed of solid brass. {data['compelling_sentence']} The collection's clean lines suit modern and transitional designs.\"\n"
        f"- BAD: \"Available in {finish_name}. {finish_name} features a bright surface.\"\n"
        f"</finish_context>"
    )


# ---------------------------------------------------------------------------
# Build prompts for each variation
# ---------------------------------------------------------------------------

def build_variation_a(parent_sku, evidence, evidence_md, finish_name, finish_code) -> tuple[str, str]:
    """Variation A: Current production prompt (full skills injection) with finish context."""
    system = get_system_prompt(mode="batch")
    user = build_core_prompt(
        parent_sku=parent_sku,
        evidence=evidence,
        evidence_markdown=evidence_md,
        platform="google",
        content_type="title and description",
        finish_code=finish_code,
    )
    # Add finish name instruction to user prompt for current system
    user += f"\n\nIMPORTANT: Generate content for finish: {finish_name}. Google/Bing titles MUST start with \"{finish_name}\"."
    return system, user


def build_variation_b(parent_sku, evidence, evidence_md, finish_name, finish_code) -> tuple[str, str]:
    """Variation B: Minimal — SYSTEM_PROMPT base only, no skills, with finish context."""
    system = CANONICAL_SYSTEM_PROMPT
    user = build_core_prompt(
        parent_sku=parent_sku,
        evidence=evidence,
        evidence_markdown=evidence_md,
        platform="google",
        content_type="title and description",
        finish_code=finish_code,
    )
    user += f"\n\nIMPORTANT: Generate content for finish: {finish_name}. Google/Bing titles MUST start with \"{finish_name}\"."
    return system, user


def build_variation_c(parent_sku, evidence, evidence_md, finish_name, finish_code) -> tuple[str, str]:
    """Variation C: Optimized — new CTCO prompt with variant-level finish context."""
    system = load_new_system_prompt()

    # Build VARIANT user prompt (primary template for Google/Bing)
    user_parts: list[str] = []

    user_parts.append(
        f"<task>\n"
        f"Generate one complete JSON object for variant: {parent_sku.master_sku} in {finish_name} finish.\n"
        f"Use only information in the inputs below. Every claim must trace to a field in the evidence table.\n\n"
        f"CRITICAL: Google and Bing titles MUST start with \"{finish_name}\" as the very first element.\n"
        f"</task>"
    )

    user_parts.append(f"<inputs>\n\n<evidence_table>\n{evidence_md}\n</evidence_table>")

    # Keyword placement with competitor brand warning
    try:
        from feedops.pipeline.keyword_placement import (
            build_keyword_placement_plan,
            format_keyword_placement_section,
        )
        kw_plan = build_keyword_placement_plan(parent_sku, evidence)
        kw_section = format_keyword_placement_section(kw_plan)
        if kw_section:
            kw_section += (
                "\n\nIMPORTANT: If any competitor brand names appear in keyword data "
                "(e.g., \"jan barboglio\", \"kingston brass\", \"moen\"), use them ONLY as "
                "query-matching intelligence — understand what shoppers are searching for — but "
                "NEVER include competitor brand names in the generated content."
            )
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

    # Finish context (REQUIRED for variant-level generation)
    user_parts.append(build_finish_context(finish_name, finish_code))

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
            max_completion_tokens=16000,
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


def check_competitor_brands(text: str) -> list[str]:
    """Check for competitor brand names in generated content."""
    found = []
    text_lower = text.lower()
    for brand in COMPETITOR_BRANDS:
        if brand.lower() in text_lower:
            found.append(brand)
    return found


def check_finish_in_title(title: str, finish_name: str) -> bool:
    """Check if the title starts with the finish name."""
    if not title or not finish_name:
        return False
    title_lower = title.lower().strip()
    finish_lower = finish_name.lower().strip()
    return title_lower.startswith(finish_lower)


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
    """Estimate factual claims per 100 words."""
    words = text.split()
    if not words:
        return 0.0
    claim_patterns = [
        r'\d+[\s-]?(?:inch|mm|cm|oz)',
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
    sku_configs: list[dict],
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

    for sku_config in sku_configs:
        sku = sku_config["sku"]
        finish_name = sku_config["finish_name"]
        finish_code = sku_config["finish_code"]

        print(f"\n{'='*60}")
        print(f"SKU: {sku} | Finish: {finish_name} ({finish_code})")
        print(f"{'='*60}")

        parent_sku, evidence, evidence_md = load_sku_data(sku)
        if not parent_sku:
            continue

        results[sku] = {
            "category": parent_sku.category or "Unknown",
            "finish_name": finish_name,
            "finish_code": finish_code,
        }

        for var_name in variations:
            builder = VARIATION_BUILDERS[var_name]
            system_prompt, user_prompt = builder(parent_sku, evidence, evidence_md, finish_name, finish_code)

            sys_tokens = count_tokens(system_prompt)
            user_tokens = count_tokens(user_prompt)
            sys_chars = len(system_prompt)

            print(f"\n  Variation {var_name}:")
            print(f"    System: {sys_chars:,} chars / {sys_tokens:,} tokens")
            print(f"    User:   {len(user_prompt):,} chars / {user_tokens:,} tokens")

            if dry_run:
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
                safe_sku = sku.replace("/", "-")
                out_path = OUTPUT_DIR / f"{safe_sku}_{var_name}_output.json"
                out_path.write_text(json.dumps(parsed, indent=2))

                google_title = parsed.get("google_title", "")
                google_desc = parsed.get("google_description", "")
                bing_title = parsed.get("bing_title", "")
                bing_desc = parsed.get("bing_description", "")
                shopify_title = parsed.get("shopify_title", "")

                # Quick summary
                print(f"    Google Title: {google_title[:80]}...")
                print(f"    Desc length:  {len(google_desc)} chars")

                # Analysis
                all_text = f"{google_title} {google_desc} {bing_title} {bing_desc}"
                repeated = count_repeated_words(all_text)
                filler = count_filler(all_text)
                concerns = check_roberts_concerns(all_text)
                competitors = check_competitor_brands(all_text)
                structure = analyze_structure(google_desc)
                density = claims_per_100_words(google_desc)

                # Finish name in title check
                google_title_has_finish = check_finish_in_title(google_title, finish_name)
                bing_title_has_finish = check_finish_in_title(bing_title, finish_name)

                if repeated:
                    print(f"    Keyword stuffing: {repeated[:3]}")
                if filler:
                    print(f"    Filler words: {filler}")
                if concerns:
                    print(f"    Robert's concerns: {concerns}")
                if competitors:
                    print(f"    COMPETITOR BRANDS LEAKED: {competitors}")
                print(f"    Finish in Google title: {'YES' if google_title_has_finish else 'NO'}")
                print(f"    Finish in Bing title: {'YES' if bing_title_has_finish else 'NO'}")

                # Self-score
                self_score = parsed.get("self_score", {})
                if isinstance(self_score, dict):
                    score_total = sum(v for v in self_score.values() if isinstance(v, (int, float)))
                    score_count = sum(1 for v in self_score.values() if isinstance(v, (int, float)))
                    avg_score = score_total / score_count if score_count else 0
                    print(f"    Self-score avg: {avg_score:.1f}")
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
                    "shopify_description": parsed.get("shopify_description", ""),
                    "self_score": self_score,
                    "self_score_total": score_total,
                    "self_score_avg": avg_score,
                    "repeated_words": repeated,
                    "filler_words": filler,
                    "roberts_concerns": concerns,
                    "competitor_brands": competitors,
                    "google_title_has_finish": google_title_has_finish,
                    "bing_title_has_finish": bing_title_has_finish,
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

def generate_results_doc(results: dict, sku_configs: list[dict], variations: list[str]) -> str:
    """Generate the ab-test-results.md document."""
    lines: list[str] = []
    lines.append("# A/B Prompt Testing Results (v2.1 — Variant-Level)")
    lines.append("")
    lines.append(f"**Date:** {time.strftime('%Y-%m-%d')}")
    lines.append("**Phase:** 25.1-prompt-architecture-research, Plan 03 (revised)")
    lines.append("**Model:** GPT-5.2 (reasoning_effort=medium, strict JSON schema)")
    lines.append(f"**SKUs tested:** {len(REPRESENTATIVE_SKUS)} representative + {len(UNSEEN_SKUS)} unseen")
    lines.append("**Key change from v1:** Variant-level generation with specific finishes per SKU")
    lines.append("")

    all_skus = [cfg["sku"] for cfg in sku_configs]
    sku_finish_map = {cfg["sku"]: cfg["finish_name"] for cfg in sku_configs}

    # Executive summary
    lines.append("## Executive Summary")
    lines.append("")
    lines.append("Three prompt variations tested with VARIANT-LEVEL generation (specific finish per SKU):")
    lines.append("- **A (Current):** Full SKILL.md injection (267K chars) + finish instruction appended")
    lines.append("- **B (Minimal):** SYSTEM_PROMPT base only (6.4K chars) + finish instruction appended")
    lines.append("- **C (Optimized):** New CTCO prompt (~18K chars) with gold examples, finish context, competitor prohibition")
    lines.append("")

    # Key findings
    lines.append("### Key Findings")
    lines.append("")

    # Calculate aggregate stats
    for var in variations:
        finish_google = 0
        finish_bing = 0
        competitor_leaks = 0
        total = 0
        for sku in all_skus:
            var_data = results.get(sku, {}).get(var, {})
            if "error" in var_data or var_data.get("dry_run"):
                continue
            total += 1
            if var_data.get("google_title_has_finish"):
                finish_google += 1
            if var_data.get("bing_title_has_finish"):
                finish_bing += 1
            if var_data.get("competitor_brands"):
                competitor_leaks += 1
        if total > 0:
            lines.append(f"**{var}:** Google title starts with finish: {finish_google}/{total} | "
                        f"Bing title starts with finish: {finish_bing}/{total} | "
                        f"Competitor brand leaks: {competitor_leaks}/{total}")
    lines.append("")

    # Summary table
    lines.append("## Summary Table")
    lines.append("")
    lines.append("| SKU | Finish | Category | Variation | Google Title (first 70 chars) | Desc Len | Finish First? | Competitors? | Filler | Robert |")
    lines.append("|-----|--------|----------|-----------|-------------------------------|----------|---------------|-------------|--------|--------|")

    for sku in all_skus:
        sku_data = results.get(sku, {})
        category = sku_data.get("category", "?")
        finish = sku_data.get("finish_name", "?")
        for var in variations:
            var_data = sku_data.get(var, {})
            if "error" in var_data or var_data.get("dry_run"):
                lines.append(f"| {sku} | {finish} | {category} | {var} | ERROR | - | - | - | - | - |")
                continue
            title = var_data.get("google_title", "")[:70]
            desc_len = len(var_data.get("google_description", ""))
            finish_ok = "YES" if var_data.get("google_title_has_finish") else "NO"
            competitors = ", ".join(var_data.get("competitor_brands", [])[:2]) or "Clean"
            filler = ", ".join(var_data.get("filler_words", [])[:2]) or "Clean"
            concerns = ", ".join(var_data.get("roberts_concerns", [])[:2]) or "Clean"
            lines.append(f"| {sku} | {finish} | {category} | {var} | {title} | {desc_len} | {finish_ok} | {competitors} | {filler} | {concerns} |")

    # Token usage comparison
    lines.append("")
    lines.append("## Token Usage Comparison")
    lines.append("")
    lines.append("| Variation | System Chars | System Tokens | Reduction vs Current |")
    lines.append("|-----------|-------------|---------------|---------------------|")

    for var in variations:
        sys_chars_list = []
        sys_tokens_list = []
        for sku in all_skus:
            var_data = results.get(sku, {}).get(var, {})
            if var_data.get("dry_run") or "error" in var_data:
                continue
            sys_chars_list.append(var_data.get("system_chars", 0))
            sys_tokens_list.append(var_data.get("system_tokens", 0))

        def avg(lst):
            return sum(lst) / len(lst) if lst else 0

        avg_chars = avg(sys_chars_list)
        avg_tokens = avg(sys_tokens_list)
        reduction = f"{(1 - avg_tokens / 57504) * 100:.1f}%" if avg_tokens > 0 else "--"
        lines.append(f"| {var} | {avg_chars:,.0f} | {avg_tokens:,.0f} | {reduction} |")

    # Side-by-side comparisons
    lines.append("")
    lines.append("## Side-by-Side Comparisons")

    for sku_config in sku_configs:
        sku = sku_config["sku"]
        finish_name = sku_config["finish_name"]
        sku_data = results.get(sku, {})
        category = sku_data.get("category", "?")
        is_representative = sku_config in REPRESENTATIVE_SKUS

        lines.append("")
        lines.append(f"### {sku} ({category}) — {finish_name} {'[Representative]' if is_representative else '[Unseen]'}")
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
            lines.append(f"**Bing Description** ({len(var_data.get('bing_description', ''))} chars):")
            lines.append(f"> {var_data.get('bing_description', 'N/A')}")
            lines.append("")
            lines.append(f"**Shopify Title:** {var_data.get('shopify_title', 'N/A')}")
            lines.append("")

            # Analysis
            lines.append("**Analysis:**")
            lines.append(f"- Finish in Google title: {'YES' if var_data.get('google_title_has_finish') else 'NO'}")
            lines.append(f"- Finish in Bing title: {'YES' if var_data.get('bing_title_has_finish') else 'NO'}")
            competitors = var_data.get("competitor_brands", [])
            lines.append(f"- Competitor brands in content: {'LEAKED: ' + str(competitors) if competitors else 'Clean'}")
            repeated = var_data.get("repeated_words", [])
            lines.append(f"- Keyword stuffing: {'FLAGGED ' + str(repeated[:3]) if repeated else 'Clean'}")
            filler = var_data.get("filler_words", [])
            lines.append(f"- Filler words: {'FLAGGED ' + str(filler) if filler else 'Clean'}")
            concerns = var_data.get("roberts_concerns", [])
            lines.append(f"- Robert's concerns: {'FLAGGED ' + str(concerns) if concerns else 'Clean'}")
            structure = var_data.get("structure", {})
            lines.append(f"- Structure: {structure.get('sentence_count', 0)} sentences, {structure.get('word_count', 0)} words")
            lines.append(f"- Opening words: {structure.get('opening_words', [])}")
            lines.append(f"- Claims density: {var_data.get('claims_density', 0)} per 100 words")

            self_score = var_data.get("self_score", {})
            if isinstance(self_score, dict) and self_score:
                score_items = ", ".join(f"{k}={v}" for k, v in self_score.items() if isinstance(v, (int, float)))
                lines.append(f"- Self-score: {score_items}")

            lines.append("")

    # Recommendation
    lines.append("## Recommendation")
    lines.append("")
    lines.append("### Validation Criteria")
    lines.append("")
    lines.append("| Criterion | A_Current | B_Minimal | C_Optimized |")
    lines.append("|-----------|-----------|-----------|-------------|")

    for var in variations:
        finish_rate = 0
        competitor_clean = 0
        total = 0
        for sku in all_skus:
            var_data = results.get(sku, {}).get(var, {})
            if "error" in var_data or var_data.get("dry_run"):
                continue
            total += 1
            if var_data.get("google_title_has_finish"):
                finish_rate += 1
            if not var_data.get("competitor_brands"):
                competitor_clean += 1

    # Build recommendation rows
    criteria_rows = []
    for criterion_name, key in [
        ("Finish first in Google title", "google_title_has_finish"),
        ("Finish first in Bing title", "bing_title_has_finish"),
        ("No competitor brands", "competitor_brands"),
        ("No Robert's concerns", "roberts_concerns"),
        ("No filler words", "filler_words"),
    ]:
        row = [criterion_name]
        for var in variations:
            yes_count = 0
            total = 0
            for sku in all_skus:
                var_data = results.get(sku, {}).get(var, {})
                if "error" in var_data or var_data.get("dry_run"):
                    continue
                total += 1
                if key in ("competitor_brands", "roberts_concerns", "filler_words"):
                    if not var_data.get(key):
                        yes_count += 1
                else:
                    if var_data.get(key):
                        yes_count += 1
            row.append(f"{yes_count}/{total}" if total > 0 else "N/A")
        criteria_rows.append(row)

    for row in criteria_rows:
        lines.append(f"| {row[0]} | {row[1]} | {row[2]} | {row[3]} |")

    lines.append("")
    lines.append("---")
    lines.append(f"*Generated: {time.strftime('%Y-%m-%d %H:%M UTC', time.gmtime())}*")
    lines.append(f"*Script: scripts/ab_prompt_test.py (v2.1 — variant-level)*")
    lines.append(f"*All outputs available in /tmp/ab_test_outputs/*")

    return "\n".join(lines)


# ---------------------------------------------------------------------------
# CLI entry point
# ---------------------------------------------------------------------------

def main():
    parser = argparse.ArgumentParser(description="A/B prompt testing for content generation (v2.1)")
    parser.add_argument("--dry-run", action="store_true", help="Validate loading without API calls")
    parser.add_argument("--sku", type=str, help="Test single SKU only (uses default finish)")
    parser.add_argument("--model", type=str, default="gpt-5.2", help="Model to use")
    parser.add_argument("--variations", type=str, default="A_Current,B_Minimal,C_Optimized",
                        help="Comma-separated variation names")
    parser.add_argument("--unseen-only", action="store_true", help="Test only unseen SKUs")
    parser.add_argument("--representative-only", action="store_true", help="Test only representative SKUs")
    args = parser.parse_args()

    variations = args.variations.split(",")

    if args.sku:
        # Default to Polished Nickel for single-SKU testing
        sku_configs = [{"sku": args.sku, "finish_name": "Polished Nickel", "finish_code": "PNI"}]
    elif args.unseen_only:
        sku_configs = UNSEEN_SKUS
    elif args.representative_only:
        sku_configs = REPRESENTATIVE_SKUS
    else:
        sku_configs = REPRESENTATIVE_SKUS + UNSEEN_SKUS

    print(f"A/B Prompt Test v2.1 (Variant-Level)")
    print(f"SKUs: {[c['sku'] + ' (' + c['finish_name'] + ')' for c in sku_configs]}")
    print(f"Variations: {variations}")
    print(f"Dry run: {args.dry_run}")
    print(f"Model: {args.model}")

    results = asyncio.run(run_test(sku_configs, variations, dry_run=args.dry_run, model=args.model))

    if not args.dry_run:
        doc = generate_results_doc(results, sku_configs, variations)
        RESULTS_PATH.parent.mkdir(parents=True, exist_ok=True)
        RESULTS_PATH.write_text(doc)
        print(f"\nResults written to: {RESULTS_PATH}")

    # Save raw results JSON
    raw_path = OUTPUT_DIR / "ab_test_results.json"
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
