#!/usr/bin/env python3
"""Post-deploy content quality verification script.

Calls /optimize-sku for test SKUs and verifies description length per platform.
Reusable for Phase 5 (Claude provider), Phase 7 (Bing fix), and future prompt changes.

Usage:
    python scripts/verify_content_quality.py --pipeline-url $FEEDOPS_PIPELINE_URL
    python scripts/verify_content_quality.py --pipeline-url $FEEDOPS_PIPELINE_URL --master-sku 920D-6
    python scripts/verify_content_quality.py \\
        --pipeline-url $FEEDOPS_PIPELINE_URL \\
        --master-sku 920D-6 \\
        --master-sku AP-41/18 \\
        --platforms google,bing \\
        --min-desc-len 500

Exit codes:
    0 — All checks PASS
    1 — At least one check FAIL
    2 — Connection/setup error (bad URL, no network, missing pipeline URL)
"""

from __future__ import annotations

import argparse
import json
import os
import sys
from urllib import error, request


DEFAULT_SKUS = ["920D-6", "AP-41/18"]
DEFAULT_PLATFORMS = ["google", "bing", "shopify"]
DEFAULT_MIN_DESC_LEN = 500
DEFAULT_TIMEOUT = 300  # content generation takes ~3 min


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description=(
            "Post-deploy content quality verification. "
            "POSTs to /optimize-sku and checks description length per platform."
        ),
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=__doc__,
    )
    parser.add_argument(
        "--pipeline-url",
        default=None,
        help=(
            "Base API URL, e.g. https://feedops-pipeline-xxxx.run.app. "
            "Falls back to FEEDOPS_PIPELINE_URL env var if not provided."
        ),
    )
    parser.add_argument(
        "--master-sku",
        action="append",
        dest="master_skus",
        metavar="SKU",
        help=(
            f"Master SKU to verify (repeatable). "
            f"Defaults to {DEFAULT_SKUS!r} if not provided."
        ),
    )
    parser.add_argument(
        "--platforms",
        default=",".join(DEFAULT_PLATFORMS),
        help=(
            "Comma-separated list of platforms to check. "
            f"Defaults to '{','.join(DEFAULT_PLATFORMS)}'."
        ),
    )
    parser.add_argument(
        "--min-desc-len",
        type=int,
        default=DEFAULT_MIN_DESC_LEN,
        help=f"Minimum description character length to pass. Defaults to {DEFAULT_MIN_DESC_LEN}.",
    )
    parser.add_argument(
        "--timeout",
        type=int,
        default=DEFAULT_TIMEOUT,
        help=f"HTTP timeout in seconds. Defaults to {DEFAULT_TIMEOUT}.",
    )
    return parser


def verify_sku(
    pipeline_url: str,
    master_sku: str,
    platforms: list[str],
    min_desc_len: int,
    timeout: int,
) -> dict[str, dict]:
    """Call /optimize-sku for a single SKU and return per-platform results.

    Returns a dict keyed by platform name. Each value is a dict with:
        status: "PASS" | "FAIL" | "ERROR" | "TIMEOUT"
        desc_len: int (0 if not available)
        title_preview: str (first 60 chars of title, or empty string)
        error: str (only present for ERROR/TIMEOUT)
    """
    url = f"{pipeline_url}/optimize-sku"
    payload = {
        "master_sku": master_sku,
        "content_types": platforms,
    }
    body = json.dumps(payload).encode("utf-8")
    req = request.Request(
        url,
        data=body,
        method="POST",
        headers={"Content-Type": "application/json"},
    )

    results: dict[str, dict] = {}

    try:
        with request.urlopen(req, timeout=timeout) as resp:
            raw = resp.read().decode("utf-8", errors="replace")
    except error.HTTPError as exc:
        raw = exc.read().decode("utf-8", errors="replace")
        err_msg = f"HTTP {exc.code}: {raw[:200]}"
        for platform in platforms:
            results[platform] = {
                "status": "ERROR",
                "desc_len": 0,
                "title_preview": "",
                "error": err_msg,
            }
        return results
    except TimeoutError:
        err_msg = f"Request timed out after {timeout}s"
        for platform in platforms:
            results[platform] = {
                "status": "TIMEOUT",
                "desc_len": 0,
                "title_preview": "",
                "error": err_msg,
            }
        return results
    except OSError as exc:
        # Connection-level errors (DNS failure, refused, etc.) — re-raise to caller
        raise

    try:
        data = json.loads(raw)
    except json.JSONDecodeError as exc:
        err_msg = f"JSON parse error: {exc} — raw: {raw[:200]}"
        for platform in platforms:
            results[platform] = {
                "status": "ERROR",
                "desc_len": 0,
                "title_preview": "",
                "error": err_msg,
            }
        return results

    platform_results = data.get("results", {})
    for platform in platforms:
        if platform not in platform_results:
            results[platform] = {
                "status": "ERROR",
                "desc_len": 0,
                "title_preview": "",
                "error": f"Platform '{platform}' missing from response",
            }
            continue

        platform_data = platform_results[platform]
        description = platform_data.get("description", "") or ""
        title = platform_data.get("title", "") or ""
        desc_len = len(description)
        title_preview = title[:60]

        if desc_len >= min_desc_len:
            status = "PASS"
        else:
            status = "FAIL"

        results[platform] = {
            "status": status,
            "desc_len": desc_len,
            "title_preview": title_preview,
        }

    return results


def _status_label(status: str) -> str:
    """Return fixed-width status label for aligned output."""
    labels = {
        "PASS": "PASS",
        "FAIL": "FAIL",
        "ERROR": "ERROR",
        "TIMEOUT": "TIMEOUT",
    }
    return labels.get(status, status)


def main() -> int:
    parser = _build_parser()
    args = parser.parse_args()

    # Resolve pipeline URL
    pipeline_url = args.pipeline_url or os.environ.get("FEEDOPS_PIPELINE_URL")
    if not pipeline_url:
        print(
            "ERROR: --pipeline-url not provided and FEEDOPS_PIPELINE_URL env var not set.",
            file=sys.stderr,
        )
        print("Usage: python scripts/verify_content_quality.py --pipeline-url <URL>", file=sys.stderr)
        return 2
    pipeline_url = pipeline_url.rstrip("/")

    # Resolve SKUs
    master_skus = args.master_skus or DEFAULT_SKUS

    # Resolve platforms
    platforms = [p.strip() for p in args.platforms.split(",") if p.strip()]
    if not platforms:
        print("ERROR: --platforms produced empty list.", file=sys.stderr)
        return 2

    min_desc_len = args.min_desc_len
    timeout = args.timeout

    print(f"Pipeline URL: {pipeline_url}")
    print(f"SKUs: {master_skus}")
    print(f"Platforms: {platforms}")
    print(f"Min description length: {min_desc_len} chars")
    print(f"Timeout: {timeout}s")
    print()

    total_checks = 0
    passed_checks = 0
    failed_checks = 0
    any_fail = False

    for master_sku in master_skus:
        print(f"=== Verification: {master_sku} ===")
        try:
            sku_results = verify_sku(
                pipeline_url=pipeline_url,
                master_sku=master_sku,
                platforms=platforms,
                min_desc_len=min_desc_len,
                timeout=timeout,
            )
        except OSError as exc:
            print(f"  CONNECTION ERROR: {exc}", file=sys.stderr)
            print(f"  Could not reach {pipeline_url} — check URL and network.", file=sys.stderr)
            return 2

        max_platform_len = max(len(p) for p in platforms)

        for platform in platforms:
            if platform not in sku_results:
                # Should not happen, but be defensive
                print(f"  {platform:<{max_platform_len}}: MISSING")
                any_fail = True
                total_checks += 1
                continue

            result = sku_results[platform]
            status = result["status"]
            desc_len = result["desc_len"]
            title_preview = result.get("title_preview", "")
            error_msg = result.get("error", "")

            total_checks += 1
            if status == "PASS":
                passed_checks += 1
                print(
                    f"  {platform:<{max_platform_len}}: PASS    "
                    f"(desc: {desc_len} chars) | Title: \"{title_preview}\""
                )
            elif status == "FAIL":
                failed_checks += 1
                any_fail = True
                print(
                    f"  {platform:<{max_platform_len}}: FAIL    "
                    f"(desc: {desc_len} chars, need >={min_desc_len}) | Title: \"{title_preview}\""
                )
            elif status in ("ERROR", "TIMEOUT"):
                any_fail = True
                print(
                    f"  {platform:<{max_platform_len}}: {status:<7} "
                    f"| {error_msg}"
                )
            else:
                any_fail = True
                print(f"  {platform:<{max_platform_len}}: UNKNOWN | status={status!r}")

        print()

    print("=== SUMMARY ===")
    other_checks = total_checks - passed_checks - failed_checks
    summary_parts = [f"Total: {total_checks} checks", f"PASS: {passed_checks}", f"FAIL: {failed_checks}"]
    if other_checks > 0:
        summary_parts.append(f"ERROR/TIMEOUT: {other_checks}")
    print(" | ".join(summary_parts))
    overall = "PASS" if not any_fail else "FAIL"
    print(f"Overall: {overall}")

    return 0 if not any_fail else 1


if __name__ == "__main__":
    sys.exit(main())
