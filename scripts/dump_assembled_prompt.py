#!/usr/bin/env python3
"""Dump and analyze the full assembled prompt GPT-5.2 receives.

This script loads the complete system prompt (SYSTEM_PROMPT + all 8 skills) and
a sample user prompt for a real SKU, then measures token counts using tiktoken
with the o200k_base encoding (GPT-5.2's tokenizer).

Usage:
    # From project root with .env.vercel credentials:
    set -a && source .env.vercel && set +a
    PYTHONPATH=./src .venv/bin/python scripts/dump_assembled_prompt.py

    # Or specify a different SKU:
    PYTHONPATH=./src .venv/bin/python scripts/dump_assembled_prompt.py --sku 1042

Output:
    - /tmp/prompt_dump_system.txt   Full system message
    - /tmp/prompt_dump_user.txt     Full user message for the SKU
    - Console summary with token counts and per-skill breakdown
"""

from __future__ import annotations

import argparse
import os
import re
import sys
from pathlib import Path

# ---------------------------------------------------------------------------
# Environment loading (from .env.vercel)
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


# Load .env.vercel from project root (parent of scripts/)
project_root = Path(__file__).parent.parent
load_env_file(str(project_root / ".env.vercel"))

# ---------------------------------------------------------------------------
# Imports (after env is loaded so Supabase can connect)
# ---------------------------------------------------------------------------

try:
    import tiktoken
except ImportError:
    print("ERROR: tiktoken not installed. Run: pip install tiktoken", file=sys.stderr)
    sys.exit(1)

from feedops.api.prompt_loader import get_system_prompt
from feedops.api.prompt_builder import build_core_prompt
from feedops.api.supabase_loader import load_parent_sku_from_supabase
from feedops.pipeline.evidence import build_evidence_table, format_evidence_markdown
from feedops.pipeline.skill_loader import load_skill_content, ALL_SKILLS
from feedops.pipeline.prompts import SYSTEM_PROMPT as CANONICAL_SYSTEM_PROMPT

# ---------------------------------------------------------------------------
# Token counting
# ---------------------------------------------------------------------------

# GPT-5.2 uses o200k_base encoding
enc = tiktoken.get_encoding("o200k_base")


def count_tokens(text: str) -> int:
    """Count tokens using o200k_base encoding."""
    return len(enc.encode(text))


# ---------------------------------------------------------------------------
# Claude-specific content detection
# ---------------------------------------------------------------------------

# Patterns that are Claude Code metadata, not useful for GPT-5.2
CLAUDE_SPECIFIC_PATTERNS = [
    (r"^---\n.*?^---\n", "YAML frontmatter"),
    (r"(?m)^This skill is the \*\*source of truth\*\*.*?(?=\n## |\Z)", "Skill identity preamble"),
    (r"(?m)^## Companion Skills\n.*?(?=\n---\n|\n## [^C]|\Z)", "Companion Skills section"),
    (r"(?m)^## When to Invoke.*?(?=\n## |\Z)", "When to Invoke section"),
    (r"(?m)^## Rule Files.*?(?=\n## |\Z)", "Rule Files section"),
    (r"(?m)^## Agent Guidance.*?(?=\n## |\Z)", "Agent Guidance section"),
    (r"(?m)^## Quick Reference.*?(?=\n## |\Z)", "Quick Reference section"),
    (r"(?ms)^Use this skill whenever.*?\.\n", "Invocation guidance"),
]


def find_claude_specific_content(text: str) -> list[tuple[str, int, int]]:
    """Find Claude-specific sections in a SKILL.md file.

    Returns list of (pattern_name, char_count, token_count).
    """
    results = []
    for pattern, name in CLAUDE_SPECIFIC_PATTERNS:
        matches = re.findall(pattern, text, re.MULTILINE | re.DOTALL)
        for match in matches:
            results.append((name, len(match), count_tokens(match)))
    return results


# ---------------------------------------------------------------------------
# Over-instruction hotspot analysis
# ---------------------------------------------------------------------------

HOTSPOT_KEYWORDS = {
    "competitor_materials": [
        "die-cast zinc", "zinc alloy", "plated alternatives",
        "chrome-plated steel", "hollow zinc", "competitor",
        "Kingston Brass", "cheaper materials",
    ],
    "finish_handling": [
        "28 finishes", "28+", "finish variety", "{FINISH_NAME}",
        "finish_specificity", "finish integration", "finish-specific",
    ],
    "description_length": [
        "600-800", "700-900", "700-1000", "target.*character",
        "character budget",
    ],
    "title_rules": [
        "title formula", "first 30 char", "first 70 char",
        "max 150", "60-150", "product type in first",
    ],
}


def find_hotspots(text: str, topic: str, keywords: list[str]) -> list[tuple[int, str]]:
    """Find all occurrences of hotspot keywords in text.

    Returns list of (line_number, matching_line).
    """
    results = []
    for i, line in enumerate(text.splitlines(), 1):
        for kw in keywords:
            if re.search(re.escape(kw) if not any(c in kw for c in ".*+?[]()") else kw, line, re.IGNORECASE):
                results.append((i, line.strip()))
                break  # One match per line is enough
    return results


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main():
    parser = argparse.ArgumentParser(description="Dump and analyze assembled GPT-5.2 prompt")
    parser.add_argument("--sku", default="920D-6", help="Master SKU to use for user prompt (default: 920D-6)")
    args = parser.parse_args()

    master_sku = args.sku
    print(f"=== Prompt Dump & Analysis for SKU: {master_sku} ===\n")

    # --- 1. Load system prompt (with all 8 skills) ---
    print("Loading system prompt (batch mode, all 8 skills)...")
    system_prompt = get_system_prompt(mode="batch")
    system_chars = len(system_prompt)
    system_tokens = count_tokens(system_prompt)

    # --- 2. Load ParentSKU and build user prompt ---
    print(f"Loading ParentSKU: {master_sku}...")
    parent_sku = load_parent_sku_from_supabase(master_sku)
    if not parent_sku:
        print(f"ERROR: Could not load SKU {master_sku} from Supabase", file=sys.stderr)
        sys.exit(1)

    print("Building evidence table...")
    evidence = build_evidence_table(parent_sku)
    evidence_markdown = format_evidence_markdown(evidence)

    print("Building user prompt...")
    user_prompt = build_core_prompt(
        parent_sku=parent_sku,
        evidence=evidence,
        evidence_markdown=evidence_markdown,
        platform="google",
        content_type="description",
        mode="batch",
    )
    user_chars = len(user_prompt)
    user_tokens = count_tokens(user_prompt)

    # --- 3. Write dumps to /tmp ---
    Path("/tmp/prompt_dump_system.txt").write_text(system_prompt, encoding="utf-8")
    Path("/tmp/prompt_dump_user.txt").write_text(user_prompt, encoding="utf-8")
    print("\nDump files written:")
    print(f"  System: /tmp/prompt_dump_system.txt ({system_chars:,} chars)")
    print(f"  User:   /tmp/prompt_dump_user.txt ({user_chars:,} chars)")

    # --- 4. Per-skill breakdown ---
    print("\n" + "=" * 70)
    print("SYSTEM PROMPT BREAKDOWN")
    print("=" * 70)

    # Base SYSTEM_PROMPT (without skills)
    base_chars = len(CANONICAL_SYSTEM_PROMPT)
    base_tokens = count_tokens(CANONICAL_SYSTEM_PROMPT)
    print(f"\n{'Component':<45} {'Chars':>8} {'Tokens':>8} {'% System':>8}")
    print("-" * 70)
    print(f"{'SYSTEM_PROMPT base':<45} {base_chars:>8,} {base_tokens:>8,} {base_chars/system_chars*100:>7.1f}%")

    # Per-skill breakdown
    total_skill_chars = 0
    total_skill_tokens = 0
    skill_details = []
    for skill_name in ALL_SKILLS:
        content = load_skill_content(skill_name)
        if content:
            # The skill is wrapped in XML tags: <skill name="...">content</skill>
            wrapped = f'<skill name="{skill_name}">\n{content}\n</skill>'
            sc = len(wrapped)
            st = count_tokens(wrapped)
            total_skill_chars += sc
            total_skill_tokens += st
            skill_details.append((skill_name, sc, st))
            print(f"  {skill_name:<43} {sc:>8,} {st:>8,} {sc/system_chars*100:>7.1f}%")

    print("-" * 70)
    print(f"{'Total skills':<45} {total_skill_chars:>8,} {total_skill_tokens:>8,} {total_skill_chars/system_chars*100:>7.1f}%")
    print(f"{'TOTAL SYSTEM MESSAGE':<45} {system_chars:>8,} {system_tokens:>8,} {'100.0%':>8}")

    # --- 5. User prompt breakdown ---
    print(f"\n{'USER MESSAGE':<45} {user_chars:>8,} {user_tokens:>8,}")

    # --- 6. Grand total ---
    total_chars = system_chars + user_chars
    total_tokens = system_tokens + user_tokens
    print(f"\n{'GRAND TOTAL':<45} {total_chars:>8,} {total_tokens:>8,}")
    print(f"\n  System/User ratio: {system_tokens/total_tokens*100:.1f}% / {user_tokens/total_tokens*100:.1f}%")

    # --- 7. Claude-specific content inventory ---
    print("\n" + "=" * 70)
    print("CLAUDE-SPECIFIC CONTENT IN SKILL.MD FILES")
    print("(Content irrelevant to GPT-5.2 — pure noise)")
    print("=" * 70)

    total_claude_chars = 0
    total_claude_tokens = 0
    for skill_name in ALL_SKILLS:
        content = load_skill_content(skill_name)
        if not content:
            continue
        claude_sections = find_claude_specific_content(content)
        if claude_sections:
            skill_claude_chars = sum(c for _, c, _ in claude_sections)
            skill_claude_tokens = sum(t for _, _, t in claude_sections)
            total_claude_chars += skill_claude_chars
            total_claude_tokens += skill_claude_tokens
            print(f"\n  {skill_name}:")
            for name, chars, tokens in claude_sections:
                print(f"    {name:<35} {chars:>6,} chars  {tokens:>5,} tokens")
            print(f"    {'Subtotal':<35} {skill_claude_chars:>6,} chars  {skill_claude_tokens:>5,} tokens")

    print(f"\n  {'TOTAL CLAUDE-SPECIFIC NOISE':<35} {total_claude_chars:>6,} chars  {total_claude_tokens:>5,} tokens")
    print(f"  Percentage of system prompt: {total_claude_chars/system_chars*100:.1f}%")

    # --- 8. Over-instruction hotspots ---
    print("\n" + "=" * 70)
    print("OVER-INSTRUCTION HOTSPOTS")
    print("(Topics appearing in 3+ locations with conflicting/redundant guidance)")
    print("=" * 70)

    for topic, keywords in HOTSPOT_KEYWORDS.items():
        matches = find_hotspots(system_prompt, topic, keywords)
        user_matches = find_hotspots(user_prompt, topic, keywords)
        total = len(matches) + len(user_matches)
        print(f"\n  {topic} ({total} occurrences)")
        if matches:
            print(f"    System prompt ({len(matches)} hits):")
            for line_no, line_text in matches[:8]:
                truncated = line_text[:100] + "..." if len(line_text) > 100 else line_text
                print(f"      L{line_no}: {truncated}")
        if user_matches:
            print(f"    User prompt ({len(user_matches)} hits):")
            for line_no, line_text in user_matches[:5]:
                truncated = line_text[:100] + "..." if len(line_text) > 100 else line_text
                print(f"      L{line_no}: {truncated}")

    print("\n" + "=" * 70)
    print("ANALYSIS COMPLETE")
    print("=" * 70)
    print(f"\nKey findings:")
    print(f"  System prompt: {system_tokens:,} tokens ({system_chars:,} chars)")
    print(f"  User prompt:   {user_tokens:,} tokens ({user_chars:,} chars)")
    print(f"  Total:         {total_tokens:,} tokens ({total_chars:,} chars)")
    print(f"  Skills are {total_skill_chars/system_chars*100:.1f}% of system prompt ({total_skill_tokens:,} tokens)")
    print(f"  Claude-specific noise: {total_claude_chars:,} chars ({total_claude_tokens:,} tokens)")
    print(f"  Signal-to-noise estimate: {(system_chars - total_claude_chars)/system_chars*100:.0f}% signal, {total_claude_chars/system_chars*100:.0f}% noise")


if __name__ == "__main__":
    main()
