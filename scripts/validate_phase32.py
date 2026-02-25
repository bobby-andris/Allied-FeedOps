#!/usr/bin/env python3
"""
Phase 32 Prerequisite Validation
Usage: python scripts/validate_phase32.py
Requires: SUPABASE_URL and SUPABASE_KEY (or SUPABASE_SERVICE_ROLE_KEY) env vars
Run: set -a && source .env.vercel && set +a && python scripts/validate_phase32.py
"""
import os
import sys
import json
import urllib.request
import urllib.error


def get_env():
    url = os.environ.get("NEXT_PUBLIC_SUPABASE_URL") or os.environ.get("SUPABASE_URL")
    key = (
        os.environ.get("SUPABASE_SERVICE_ROLE_KEY")
        or os.environ.get("SUPABASE_KEY")
        or os.environ.get("NEXT_PUBLIC_SUPABASE_ANON_KEY")
    )
    if not url or not key:
        print("ERROR: SUPABASE_URL and SUPABASE_KEY (or equivalents) must be set")
        print("Run: set -a && source .env.vercel && set +a && python scripts/validate_phase32.py")
        sys.exit(2)
    return url, key


def run_sql(url: str, key: str, query: str) -> list[dict]:
    """Execute SQL via Supabase PostgREST rpc endpoint."""
    endpoint = f"{url}/rest/v1/rpc/exec_sql"
    data = json.dumps({"query": query}).encode()
    req = urllib.request.Request(
        endpoint,
        data=data,
        headers={
            "apikey": key,
            "Authorization": f"Bearer {key}",
            "Content-Type": "application/json",
        },
    )
    try:
        with urllib.request.urlopen(req) as resp:
            return json.loads(resp.read())
    except urllib.error.HTTPError:
        # exec_sql RPC may not exist — fall back to pg-meta SQL endpoint
        pass

    # Fallback: use the Supabase management/pg endpoint pattern
    # Try the standard PostgREST query approach instead
    return run_sql_via_postgrest(url, key, query)


def run_sql_via_postgrest(url: str, key: str, query: str) -> list[dict]:
    """Fallback: query specific tables via PostgREST."""
    raise NotImplementedError("Direct SQL not available — use check-specific queries")


def check_funnel_data(url: str, key: str) -> tuple[bool, str]:
    """OPS-01: funnel_snapshots_daily has rows from last 7 days."""
    endpoint = (
        f"{url}/rest/v1/funnel_snapshots_daily"
        f"?select=snapshot_date"
        f"&snapshot_date=gte.{_date_n_days_ago(7)}"
        f"&limit=1"
    )
    req = urllib.request.Request(
        endpoint,
        headers={
            "apikey": key,
            "Authorization": f"Bearer {key}",
            "Prefer": "count=exact",
        },
    )
    with urllib.request.urlopen(req) as resp:
        content_range = resp.headers.get("Content-Range", "")
        # Format: "0-0/42" or "*/0"
        if "/" in content_range:
            count = int(content_range.split("/")[1])
        else:
            count = len(json.loads(resp.read()))

    if count > 0:
        return True, f"funnel_snapshots_daily has {count} rows in last 7 days"
    return False, "funnel_snapshots_daily has 0 rows in last 7 days\n       Action needed: Run backfill or verify Cloud Scheduler is active"


def check_scoring_columns(url: str, key: str) -> tuple[bool, str]:
    """OPS-03: query_value_scores has all 4 new columns."""
    required = {"tier_fit_scores", "recommended_tier", "net_monthly_impact", "scored_at"}
    found = _get_columns(url, key, "query_value_scores", required)
    missing = required - found
    if not missing:
        return True, "query_value_scores has all 4 required columns"
    return False, f"query_value_scores missing columns: {', '.join(sorted(missing))}\n       Action needed: Apply migration 037_extend_scoring_and_experiment_columns.sql"


def check_experiment_columns(url: str, key: str) -> tuple[bool, str]:
    """OPS-04: experiment_outcomes has all 3 new columns."""
    required = {"p_value", "confidence_interval", "minimum_sample_size"}
    found = _get_columns(url, key, "experiment_outcomes", required)
    missing = required - found
    if not missing:
        return True, "experiment_outcomes has all 3 required columns"
    return False, f"experiment_outcomes missing columns: {', '.join(sorted(missing))}\n       Action needed: Apply migration 037_extend_scoring_and_experiment_columns.sql"


def _get_columns(url: str, key: str, table: str, target_columns: set[str]) -> set[str]:
    """Check which target columns exist by attempting a select on the table."""
    found = set()
    for col in target_columns:
        endpoint = f"{url}/rest/v1/{table}?select={col}&limit=0"
        req = urllib.request.Request(
            endpoint,
            headers={
                "apikey": key,
                "Authorization": f"Bearer {key}",
            },
        )
        try:
            with urllib.request.urlopen(req) as resp:
                resp.read()
                found.add(col)
        except urllib.error.HTTPError:
            pass  # Column doesn't exist
    return found


def _date_n_days_ago(n: int) -> str:
    from datetime import date, timedelta
    return (date.today() - timedelta(days=n)).isoformat()


def main():
    url, key = get_env()

    print("Phase 32 Prerequisite Validation")
    print("=" * 42)

    checks = [
        ("OPS-01", check_funnel_data),
        ("OPS-03", check_scoring_columns),
        ("OPS-04", check_experiment_columns),
    ]

    results = []
    for label, check_fn in checks:
        try:
            passed, msg = check_fn(url, key)
        except Exception as e:
            passed, msg = False, f"Check error: {e}"
        results.append((label, passed, msg))

        status = "PASS" if passed else "FAIL"
        print(f"[{status}] {label}: {msg}")
        if label == "OPS-01" and passed:
            print("       Note: Verifies scheduler fired (or backfill covered window)")

    print("=" * 42)

    all_passed = all(r[1] for r in results)
    if all_passed:
        print("RESULT: ALL CHECKS PASSED — Phase 33 is cleared to proceed")
        sys.exit(0)
    else:
        failed = sum(1 for r in results if not r[1])
        print(f"RESULT: {failed} CHECK(S) FAILED — resolve before starting Phase 33")
        sys.exit(1)


if __name__ == "__main__":
    main()
