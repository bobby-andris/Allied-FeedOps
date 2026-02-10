#!/usr/bin/env python3
"""
Analyze repository file usage to identify unused files.

Usage:
    python scripts/analyze_file_usage.py [--aggressive]

Outputs:
    - Files not referenced anywhere in codebase
    - Files not modified in >6 months
    - Large files that might be candidates for cleanup
    - Potential duplicates

Options:
    --aggressive    Include more files in analysis (slower)
    --dry-run       Show what would be done without making changes
"""

import os
import subprocess
import json
from datetime import datetime, timedelta
from pathlib import Path
from collections import defaultdict
import argparse


def run_command(cmd, cwd="."):
    """Run shell command and return output"""
    result = subprocess.run(
        cmd,
        shell=True,
        capture_output=True,
        text=True,
        cwd=cwd
    )
    return result.stdout.strip()


def get_file_last_modified_days(filepath):
    """Get days since file was last modified"""
    try:
        mtime = os.path.getmtime(filepath)
        days = (datetime.now() - datetime.fromtimestamp(mtime)).days
        return days
    except:
        return 0


def get_file_size_mb(filepath):
    """Get file size in MB"""
    try:
        return os.path.getsize(filepath) / (1024 * 1024)
    except:
        return 0


def find_all_files(exclude_dirs=None):
    """Find all non-ignored files in repository"""
    if exclude_dirs is None:
        exclude_dirs = [
            "node_modules",
            ".venv",
            ".git",
            ".next",
            "build",
            "dist",
            "__pycache__",
            ".pytest_cache"
        ]

    # Use git ls-files for files tracked by git
    tracked = run_command("git ls-files").split("\n")

    # Also check for untracked files at root
    untracked = run_command("git ls-files --others --exclude-standard").split("\n")

    all_files = [f for f in tracked + untracked if f]

    # Filter out excluded directories
    filtered = []
    for f in all_files:
        if not any(excl in f for excl in exclude_dirs):
            if os.path.exists(f):
                filtered.append(f)

    return filtered


def is_file_referenced(filepath, all_files):
    """Check if file is referenced anywhere in codebase"""
    # Get just the filename
    filename = os.path.basename(filepath)

    # Skip certain files that are referenced by convention
    skip_patterns = [
        "README.md",
        "LICENSE",
        "CLAUDE.md",
        "package.json",
        "package-lock.json",
        "pyproject.toml",
        ".gitignore",
        "Dockerfile",
        "cloudbuild.yaml",
        "tsconfig.json"
    ]

    if any(pattern in filepath for pattern in skip_patterns):
        return True

    # Search for references to this file
    search_cmd = f'grep -r "{filename}" . --exclude-dir=node_modules --exclude-dir=.venv --exclude-dir=.git --exclude-dir=.next 2>/dev/null | wc -l'
    ref_count = int(run_command(search_cmd))

    # If file appears more than once (more than just in itself), it's referenced
    return ref_count > 1


def analyze_repository(aggressive=False):
    """Analyze repository for cleanup opportunities"""
    print("🔍 Analyzing repository...")

    all_files = find_all_files()
    print(f"Found {len(all_files)} tracked files\n")

    results = {
        "unreferenced": [],
        "old_files": [],
        "large_files": [],
        "root_clutter": [],
        "test_screenshots": [],
        "old_docs": []
    }

    # Analyze each file
    for filepath in all_files:
        days_old = get_file_last_modified_days(filepath)
        size_mb = get_file_size_mb(filepath)

        # Root-level clutter (non-essential files)
        if "/" not in filepath and not filepath.startswith("."):
            essential_root = [
                "README.md",
                "LICENSE",
                "CLAUDE.md",
                "AGENTS.md",
                "package.json",
                "package-lock.json",
                "pyproject.toml",
                "Dockerfile",
                "cloudbuild.yaml",
                ".env.example"
            ]
            if filepath not in essential_root:
                results["root_clutter"].append({
                    "file": filepath,
                    "days_old": days_old,
                    "size_mb": round(size_mb, 2)
                })

        # Test screenshots
        if any(pattern in filepath.lower() for pattern in ["test", "screenshot"]) and \
           filepath.endswith((".png", ".jpg", ".gif")):
            results["test_screenshots"].append({
                "file": filepath,
                "days_old": days_old,
                "size_mb": round(size_mb, 2)
            })

        # Old files (>6 months, not recently modified)
        if days_old > 180:
            results["old_files"].append({
                "file": filepath,
                "days_old": days_old,
                "size_mb": round(size_mb, 2)
            })

        # Large files (>1MB)
        if size_mb > 1.0:
            results["large_files"].append({
                "file": filepath,
                "size_mb": round(size_mb, 2)
            })

        # Old documentation (>1 year in docs/)
        if filepath.startswith("docs/") and filepath.endswith(".md") and days_old > 365:
            results["old_docs"].append({
                "file": filepath,
                "days_old": days_old
            })

        # Unreferenced files (aggressive mode only - slow)
        if aggressive:
            if not is_file_referenced(filepath, all_files):
                results["unreferenced"].append({
                    "file": filepath,
                    "days_old": days_old
                })

    return results


def print_results(results):
    """Print analysis results"""

    print("\n" + "="*60)
    print("📊 REPOSITORY ANALYSIS RESULTS")
    print("="*60 + "\n")

    # Root clutter
    if results["root_clutter"]:
        print(f"🗑️  ROOT-LEVEL CLUTTER ({len(results['root_clutter'])} files)")
        print("-" * 60)
        for item in results["root_clutter"][:10]:
            print(f"  • {item['file']}")
            print(f"    Age: {item['days_old']} days, Size: {item['size_mb']} MB")
        if len(results["root_clutter"]) > 10:
            print(f"  ... and {len(results['root_clutter']) - 10} more")
        print()

    # Test screenshots
    if results["test_screenshots"]:
        print(f"📸 TEST SCREENSHOTS ({len(results['test_screenshots'])} files)")
        print("-" * 60)
        for item in results["test_screenshots"]:
            print(f"  • {item['file']} ({item['size_mb']} MB)")
        print(f"\n💡 Consider: Move to docs/images/tests/ or delete if no longer needed\n")

    # Large files
    if results["large_files"]:
        print(f"💾 LARGE FILES >1MB ({len(results['large_files'])} files)")
        print("-" * 60)
        sorted_large = sorted(results["large_files"], key=lambda x: x["size_mb"], reverse=True)
        for item in sorted_large[:10]:
            print(f"  • {item['file']}: {item['size_mb']} MB")
        print()

    # Old files
    if results["old_files"]:
        print(f"📅 OLD FILES >6 MONTHS ({len(results['old_files'])} files)")
        print("-" * 60)
        sorted_old = sorted(results["old_files"], key=lambda x: x["days_old"], reverse=True)
        for item in sorted_old[:10]:
            print(f"  • {item['file']}: {item['days_old']} days old")
        if len(results["old_files"]) > 10:
            print(f"  ... and {len(results['old_files']) - 10} more")
        print()

    # Old documentation
    if results["old_docs"]:
        print(f"📄 OLD DOCUMENTATION >1 YEAR ({len(results['old_docs'])} files)")
        print("-" * 60)
        for item in results["old_docs"]:
            print(f"  • {item['file']}: {item['days_old']} days old")
        print(f"\n💡 Consider: Review for accuracy or archive\n")

    # Unreferenced files (if aggressive mode)
    if results["unreferenced"]:
        print(f"🔍 UNREFERENCED FILES ({len(results['unreferenced'])} files)")
        print("-" * 60)
        for item in results["unreferenced"][:20]:
            print(f"  • {item['file']}")
        if len(results["unreferenced"]) > 20:
            print(f"  ... and {len(results['unreferenced']) - 20} more")
        print(f"\n⚠️  Manual review recommended - some may be false positives\n")

    # Summary
    print("="*60)
    print("📋 SUMMARY")
    print("="*60)
    total_issues = sum(len(v) for v in results.values())
    print(f"Total files flagged: {total_issues}")
    print(f"  • Root clutter: {len(results['root_clutter'])}")
    print(f"  • Test screenshots: {len(results['test_screenshots'])}")
    print(f"  • Large files: {len(results['large_files'])}")
    print(f"  • Old files: {len(results['old_files'])}")
    print(f"  • Old docs: {len(results['old_docs'])}")
    if results["unreferenced"]:
        print(f"  • Unreferenced: {len(results['unreferenced'])}")

    print("\n💡 Next steps:")
    print("  1. Review flagged files manually")
    print("  2. Run /repo-audit skill for guided cleanup")
    print("  3. Create docs/ORGANIZATION.md with standards")
    print("  4. Set up monthly maintenance routine")


def generate_cleanup_script(results):
    """Generate a cleanup script based on results"""
    script_lines = [
        "#!/bin/bash",
        "# Repository Cleanup Script",
        "# Generated: " + datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        "",
        "set -e  # Exit on error",
        "",
        "echo 'Starting repository cleanup...'",
        "",
        "# Create archive directory",
        f"mkdir -p archive/{datetime.now().strftime('%Y-%m')}",
        ""
    ]

    # Add cleanup commands for root clutter
    if results["root_clutter"]:
        script_lines.append("# Clean up root-level clutter")
        for item in results["root_clutter"]:
            if item["file"].endswith((".png", ".jpg", ".gif")):
                script_lines.append(f"# mv {item['file']} docs/images/  # Review first")
            elif item["file"].endswith(".md"):
                script_lines.append(f"# mv {item['file']} docs/audit/  # Review first")
            else:
                script_lines.append(f"# Review and relocate: {item['file']}")
        script_lines.append("")

    # Add test screenshots cleanup
    if results["test_screenshots"]:
        script_lines.append("# Test screenshots")
        for item in results["test_screenshots"]:
            script_lines.append(f"# rm {item['file']}  # Delete if no longer needed")
        script_lines.append("")

    script_lines.append("echo 'Cleanup complete!'")

    with open("cleanup.sh", "w") as f:
        f.write("\n".join(script_lines))

    os.chmod("cleanup.sh", 0o755)
    print(f"\n✅ Generated cleanup.sh - Review and edit before running!")


def main():
    parser = argparse.ArgumentParser(description="Analyze repository file usage")
    parser.add_argument("--aggressive", action="store_true", help="Include reference checking (slower)")
    parser.add_argument("--generate-script", action="store_true", help="Generate cleanup script")
    args = parser.parse_args()

    results = analyze_repository(aggressive=args.aggressive)
    print_results(results)

    if args.generate_script:
        generate_cleanup_script(results)


if __name__ == "__main__":
    main()
