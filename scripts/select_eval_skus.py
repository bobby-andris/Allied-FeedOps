#!/usr/bin/env python3
"""SKU selection script for Phase 6 model evaluation.

Queries product_catalog + generated_content to surface 15-20 diverse
evaluation candidates across categories, collections, and content states.

Usage:
    cd /path/to/Allied-FeedOps
    set -a && source .env.vercel && set +a
    python scripts/select_eval_skus.py

    # Filter to specific category
    python scripts/select_eval_skus.py --category "Grab Bars"

    # Show more candidates
    python scripts/select_eval_skus.py --limit 25

Output:
    Markdown table of candidate SKUs with diversity rationale printed to stdout.
    Copy 10 SKUs from the list and pass them to run_model_evaluation.py.

Required env vars: SUPABASE_URL, SUPABASE_KEY (or NEXT_PUBLIC_SUPABASE_ANON_KEY)
"""

from __future__ import annotations

import argparse
import json
import os
import sys
import urllib.error
import urllib.request


def _get_supabase_credentials() -> tuple[str, str]:
    """Resolve Supabase URL and key from env vars."""
    url = os.environ.get("SUPABASE_URL") or os.environ.get("NEXT_PUBLIC_SUPABASE_URL")
    key = (
        os.environ.get("SUPABASE_KEY")
        or os.environ.get("SUPABASE_SERVICE_ROLE_KEY")
        or os.environ.get("NEXT_PUBLIC_SUPABASE_ANON_KEY")
    )
    if not url:
        print(
            "ERROR: SUPABASE_URL not set. Run: set -a && source .env.vercel && set +a",
            file=sys.stderr,
        )
        sys.exit(2)
    if not key:
        print(
            "ERROR: SUPABASE_KEY not set. Run: set -a && source .env.vercel && set +a",
            file=sys.stderr,
        )
        sys.exit(2)
    return url.rstrip("/"), key


def _supabase_query(url: str, key: str, sql: str) -> list[dict]:
    """Execute a SQL query via Supabase REST /rpc/execute_sql or direct SQL endpoint."""
    # Use the /rest/v1/rpc/execute_sql if available, otherwise fall back to PostgREST
    endpoint = f"{url}/rest/v1/rpc/execute_sql"
    payload = json.dumps({"query": sql}).encode("utf-8")
    req = urllib.request.Request(
        endpoint,
        data=payload,
        method="POST",
        headers={
            "Content-Type": "application/json",
            "apikey": key,
            "Authorization": f"Bearer {key}",
        },
    )
    try:
        with urllib.request.urlopen(req, timeout=30) as resp:
            raw = resp.read().decode("utf-8", errors="replace")
            return json.loads(raw)
    except urllib.error.HTTPError as exc:
        raw = exc.read().decode("utf-8", errors="replace")
        print(f"ERROR: Supabase query failed (HTTP {exc.code}): {raw[:300]}", file=sys.stderr)
        sys.exit(1)
    except urllib.error.URLError as exc:
        print(f"ERROR: Could not reach Supabase: {exc.reason}", file=sys.stderr)
        sys.exit(2)


def _query_candidates(url: str, key: str, category_filter: str | None, limit: int) -> list[dict]:
    """Query product_catalog + generated_content for evaluation candidates.

    Uses three separate simple queries and merges results in Python to avoid
    CTEs (which are blocked by Supabase's execute_sql RPC policy).
    Multi-SKU detection uses variant_index.shopify_product_id as the grouping key.
    """
    category_clause = ""
    if category_filter:
        safe_cat = category_filter.replace("'", "''")
        category_clause = f"AND category ILIKE '%{safe_cat}%'"

    # Query 1: One representative variant per master_sku (prefer ORB finish, fallback any).
    # DISTINCT ON requires ORDER BY to start with the grouped column.
    sql_repr = f"""
SELECT DISTINCT ON (master_sku)
    master_sku,
    category,
    collection,
    LEFT(title, 60) AS title_preview
FROM product_catalog
WHERE finish_code IS NOT NULL
{category_clause}
ORDER BY master_sku,
         CASE WHEN finish_code = 'ORB' THEN 0 ELSE 1 END,
         position
"""
    representatives = _supabase_query(url, key, sql_repr)
    if not representatives:
        return []

    # Query 2: Multi-SKU detection via variant_index.shopify_product_id
    # A master_sku is "multi-SKU" if its shopify_product_id is shared by >1 master_sku.
    sql_multi = """
SELECT master_sku, shopify_product_id
FROM variant_index
GROUP BY master_sku, shopify_product_id
"""
    multi_rows = _supabase_query(url, key, sql_multi)
    # Build: shopify_product_id -> set of master_skus
    product_to_skus: dict[str, set] = {}
    for row in multi_rows:
        pid = str(row.get("shopify_product_id") or "")
        sku = row.get("master_sku", "")
        if pid and sku:
            product_to_skus.setdefault(pid, set()).add(sku)
    # Build: master_sku -> is_multi_sku
    sku_to_product: dict[str, str] = {
        row.get("master_sku", ""): str(row.get("shopify_product_id") or "")
        for row in multi_rows
    }

    # Query 3: SKUs with approved content (count platforms per master_sku)
    sql_approved = """
SELECT master_sku, COUNT(DISTINCT platform) AS approved_platform_count
FROM generated_content
WHERE approved_content IS NOT NULL
  AND approved_content != ''
GROUP BY master_sku
"""
    approved_rows = _supabase_query(url, key, sql_approved)
    approved_lookup: dict[str, int] = {
        row["master_sku"]: int(row.get("approved_platform_count") or 0)
        for row in approved_rows
        if row.get("master_sku")
    }

    # Merge and sort: prioritise approved, then by category/sku
    merged = []
    for row in representatives:
        sku = row.get("master_sku", "")
        pid = sku_to_product.get(sku, "")
        is_multi = len(product_to_skus.get(pid, set())) > 1 if pid else False
        approved_count = approved_lookup.get(sku, 0)
        merged.append({
            "master_sku": sku,
            "category": row.get("category", ""),
            "collection": row.get("collection", "") or "",
            "title_preview": row.get("title_preview", ""),
            "is_multi_sku": is_multi,
            "approved_platform_count": approved_count,
            "shopify_product_id": pid,
        })

    merged.sort(key=lambda r: (-r["approved_platform_count"], r["category"], r["master_sku"]))
    return merged[:limit]


def _build_rationale(row: dict) -> str:
    """Build a short diversity rationale string for a candidate."""
    parts = []
    if row.get("is_multi_sku"):
        parts.append("multi-SKU")
    else:
        parts.append("single-SKU")
    approved = int(row.get("approved_platform_count") or 0)
    if approved >= 3:
        parts.append("approved (all platforms)")
    elif approved > 0:
        parts.append(f"approved ({approved} platform{'s' if approved > 1 else ''})")
    else:
        parts.append("no approved content")
    return "; ".join(parts)


def _print_markdown_table(candidates: list[dict]) -> None:
    """Print candidates as a markdown table."""
    header = (
        "| # | master_sku | category | collection | multi_sku | approved | rationale |"
    )
    sep = (
        "|---|------------|----------|------------|-----------|----------|-----------|"
    )
    print(header)
    print(sep)
    for i, row in enumerate(candidates, start=1):
        sku = row.get("master_sku", "")
        category = row.get("category", "")[:30]
        collection = row.get("collection", "")[:25]
        is_multi = "yes" if row.get("is_multi_sku") else "no"
        approved = str(int(row.get("approved_platform_count") or 0))
        rationale = _build_rationale(row)
        print(f"| {i} | {sku} | {category} | {collection} | {is_multi} | {approved} | {rationale} |")


def _print_sku_list(candidates: list[dict]) -> None:
    """Print space-separated SKU list for easy copy-paste into run_model_evaluation.py."""
    skus = [row.get("master_sku", "") for row in candidates]
    print("\nSpace-separated SKU list (all candidates):")
    print(" ".join(skus))


def _print_category_summary(candidates: list[dict]) -> None:
    """Print a breakdown of categories in the candidate list."""
    from collections import Counter
    cats = Counter(row.get("category", "Unknown") for row in candidates)
    print("\nCategory breakdown:")
    for cat, count in sorted(cats.items()):
        print(f"  {count:2d}  {cat}")


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description=(
            "Query Supabase for 15-20 diverse SKU candidates for Phase 6 evaluation. "
            "Presents a markdown table for Bobby/Robert to select 10 final SKUs."
        ),
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=__doc__,
    )
    parser.add_argument(
        "--category",
        default=None,
        help="Filter candidates to a specific category (partial match, case-insensitive).",
    )
    parser.add_argument(
        "--limit",
        type=int,
        default=20,
        help="Maximum number of candidates to return (default: 20).",
    )
    parser.add_argument(
        "--no-sku-list",
        action="store_true",
        help="Suppress the space-separated SKU list at the bottom.",
    )
    return parser


def main() -> int:
    parser = _build_parser()
    args = parser.parse_args()

    supabase_url, supabase_key = _get_supabase_credentials()

    print(f"Querying Supabase for up to {args.limit} diverse evaluation candidates...")
    print()

    candidates = _query_candidates(
        url=supabase_url,
        key=supabase_key,
        category_filter=args.category,
        limit=args.limit,
    )

    if not candidates:
        print("No candidates found. Check database connectivity and category filter.", file=sys.stderr)
        return 1

    print(f"Found {len(candidates)} candidates\n")

    # Print diversity guidance
    print("## Diversity Selection Guide")
    print()
    print("Target 10 SKUs with:")
    print("  - At least 4 different categories")
    print("  - 2-3 multi-SKU products (share product_id with siblings)")
    print("  - 3-4 SKUs with approved content (for reference comparison)")
    print("  - Mix of collection types")
    print()

    # Print the main table
    print("## Candidates")
    print()
    _print_markdown_table(candidates)

    # Print category summary
    _print_category_summary(candidates)

    # Print space-separated list for easy copy-paste
    if not args.no_sku_list:
        _print_sku_list(candidates)
        print()
        print("Next step: Select 10 SKUs from the table above, then run:")
        print("  python scripts/run_model_evaluation.py --skus SKU1 SKU2 SKU3 ...")

    return 0


if __name__ == "__main__":
    sys.exit(main())
