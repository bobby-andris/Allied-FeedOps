#!/usr/bin/env python3
"""Post-deploy regenerate smoke test with request-id lineage output.

Runs a live POST /regenerate call against the pipeline URL and prints:
1) Request ID used for the call
2) HTTP status and response payload
3) Copy/paste SQL queries for DB merge/deploy sign-off
"""

from __future__ import annotations

import argparse
import json
import sys
import uuid
from urllib import error, request


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Run live regenerate smoke test and print DB verification queries."
    )
    parser.add_argument(
        "--pipeline-url",
        required=True,
        help="Base API URL, e.g. https://feedops-pipeline-xxxx.run.app",
    )
    parser.add_argument(
        "--master-sku",
        default="1031/30",
        help="Master SKU to regenerate (default: 1031/30)",
    )
    parser.add_argument(
        "--platform",
        choices=("google", "bing", "shopify"),
        default="google",
        help="Target platform (default: google)",
    )
    parser.add_argument(
        "--content-type",
        choices=("title", "description"),
        default="description",
        help="Content type (default: description)",
    )
    parser.add_argument(
        "--feedback",
        default="Smoke test regenerate for request-id lineage verification.",
        help="Feedback string to send in regenerate payload.",
    )
    parser.add_argument(
        "--timeout-seconds",
        type=int,
        default=180,
        help="HTTP timeout in seconds (default: 180).",
    )
    parser.add_argument(
        "--request-id",
        default=None,
        help="Optional fixed request ID to use instead of generating a random UUID.",
    )
    return parser


def _print_signoff_queries(request_id: str) -> None:
    print("\n=== DB SIGN-OFF QUERIES ===")
    print("-- 1) Was this request persisted to regeneration_history?")
    print(
        "select id, master_sku, platform, content_type, request_id, generated_content_id, created_at\n"
        "from public.regeneration_history\n"
        f"where request_id = '{request_id}'\n"
        "order by created_at desc;"
    )
    print("\n-- 2) Did the history row link to generated_content correctly?")
    print(
        "select rh.id as history_id, rh.request_id, rh.generated_content_id, gc.id as gc_id,\n"
        "       gc.master_sku, gc.platform, gc.content_type, gc.version, gc.updated_at\n"
        "from public.regeneration_history rh\n"
        "left join public.generated_content gc on gc.id = rh.generated_content_id\n"
        f"where rh.request_id = '{request_id}'\n"
        "order by rh.created_at desc;"
    )
    print("\n-- 3) Tuple uniqueness invariant check (must return zero rows)")
    print(
        "select master_sku, platform, content_type, count(*)::int as c\n"
        "from public.generated_content\n"
        "group by master_sku, platform, content_type\n"
        "having count(*) > 1\n"
        "order by c desc\n"
        "limit 20;"
    )


def main() -> int:
    parser = _build_parser()
    args = parser.parse_args()

    pipeline_url = args.pipeline_url.rstrip("/")
    request_id = args.request_id or str(uuid.uuid4())
    payload = {
        "master_sku": args.master_sku,
        "platform": args.platform,
        "content_type": args.content_type,
        "feedback": args.feedback,
    }

    body = json.dumps(payload).encode("utf-8")
    req = request.Request(
        f"{pipeline_url}/regenerate",
        data=body,
        method="POST",
        headers={
            "Content-Type": "application/json",
            "X-Request-ID": request_id,
        },
    )

    print("=== LIVE REGENERATE SMOKE ===")
    print(f"URL: {pipeline_url}/regenerate")
    print(f"request_id: {request_id}")
    print(f"payload: {json.dumps(payload)}")

    try:
        with request.urlopen(req, timeout=args.timeout_seconds) as resp:
            raw = resp.read().decode("utf-8", errors="replace")
            print(f"http_status: {resp.status}")
            print("response:")
            print(raw)
    except error.HTTPError as exc:
        raw = exc.read().decode("utf-8", errors="replace")
        print(f"http_status: {exc.code}")
        print("response:")
        print(raw)
        _print_signoff_queries(request_id)
        return 1
    except Exception as exc:  # noqa: BLE001
        print(f"request_failed: {exc}")
        _print_signoff_queries(request_id)
        return 2

    _print_signoff_queries(request_id)
    return 0


if __name__ == "__main__":
    sys.exit(main())
