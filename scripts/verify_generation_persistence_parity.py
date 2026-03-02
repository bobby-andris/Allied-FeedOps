#!/usr/bin/env python3
"""Verify request output parity against Supabase persistence artifacts.

This script validates that generation responses captured in smoke artifacts are
consistent with:
1) regeneration_history.new_content for the same request_id, and
2) generated_content persistence referenced by generated_content_id (candidate
   and/or approved content).

It is intentionally strict and exits non-zero on any mismatch.
"""

from __future__ import annotations

import argparse
import json
import os
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import requests


def _load_env_file(path: Path) -> None:
    if not path.exists():
        raise RuntimeError(f"Env file not found: {path}")
    for raw_line in path.read_text().splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#"):
            continue
        if line.startswith("export "):
            line = line[len("export ") :].strip()
        if "=" not in line:
            continue
        key, value = line.split("=", 1)
        key = key.strip()
        if not key:
            continue
        value = value.strip().strip('"').strip("'")
        os.environ.setdefault(key, value)


def _env(name: str) -> str | None:
    value = os.environ.get(name)
    if value and value.strip():
        return value.strip()
    return None


def _supabase_url() -> str:
    value = _env("SUPABASE_URL") or _env("NEXT_PUBLIC_SUPABASE_URL")
    if not value:
        raise RuntimeError(
            "Missing SUPABASE_URL/NEXT_PUBLIC_SUPABASE_URL in environment."
        )
    return value.rstrip("/")


def _supabase_key() -> str:
    value = (
        _env("SUPABASE_KEY")
        or _env("SUPABASE_SERVICE_ROLE_KEY")
        or _env("NEXT_PUBLIC_SUPABASE_ANON_KEY")
    )
    if not value:
        raise RuntimeError(
            "Missing SUPABASE_KEY/SUPABASE_SERVICE_ROLE_KEY/NEXT_PUBLIC_SUPABASE_ANON_KEY in environment."
        )
    return value


@dataclass(frozen=True)
class ArtifactRequest:
    request_id: str
    source_file: Path
    expected_content: str | None = None


class SupabaseRest:
    def __init__(self, base_url: str, api_key: str) -> None:
        self.base_url = f"{base_url}/rest/v1"
        self.headers = {
            "apikey": api_key,
            "Authorization": f"Bearer {api_key}",
            "Accept": "application/json",
        }

    def select(
        self,
        table: str,
        *,
        select_cols: str,
        filters: dict[str, str],
        order: str | None = None,
        limit: int | None = None,
    ) -> list[dict[str, Any]]:
        params: dict[str, str] = {"select": select_cols, **filters}
        if order:
            params["order"] = order
        if limit is not None:
            params["limit"] = str(limit)
        response = requests.get(
            f"{self.base_url}/{table}",
            headers=self.headers,
            params=params,
            timeout=45,
        )
        if not response.ok:
            raise RuntimeError(
                f"Supabase query failed for {table}: {response.status_code} {response.text[:400]}"
            )
        data = response.json()
        if not isinstance(data, list):
            raise RuntimeError(f"Unexpected response for {table}: {type(data)}")
        return data


def _load_artifact_requests(artifact_dir: Path) -> list[ArtifactRequest]:
    requests_out: list[ArtifactRequest] = []
    for file_path in sorted(artifact_dir.glob("*.json")):
        try:
            data = json.loads(file_path.read_text())
        except json.JSONDecodeError:
            continue
        if not isinstance(data, dict):
            continue
        request_id = data.get("request_id")
        if not isinstance(request_id, str) or not request_id.strip():
            continue
        payload = data.get("payload")
        expected_content: str | None = None
        if isinstance(payload, dict):
            content = payload.get("content")
            if isinstance(content, str) and content.strip():
                expected_content = content
        requests_out.append(
            ArtifactRequest(
                request_id=request_id.strip(),
                source_file=file_path,
                expected_content=expected_content,
            )
        )
    return requests_out


def _normalize_text(value: str | None) -> str:
    return (value or "").strip()


def _safe_int(value: Any) -> int | None:
    if value is None:
        return None
    try:
        return int(value)
    except (TypeError, ValueError):
        return None


def _maybe_parse_json_string(value: Any) -> Any:
    if not isinstance(value, str):
        return value
    raw = value.strip()
    if not raw or raw[0] not in "{[":
        return value
    try:
        return json.loads(raw)
    except json.JSONDecodeError:
        return value


def _collect_string_leaves(value: Any) -> list[str]:
    value = _maybe_parse_json_string(value)
    if isinstance(value, str):
        normalized = _normalize_text(value)
        return [normalized] if normalized else []
    if isinstance(value, list):
        collected: list[str] = []
        for item in value:
            collected.extend(_collect_string_leaves(item))
        return collected
    if isinstance(value, dict):
        collected = []
        for child in value.values():
            collected.extend(_collect_string_leaves(child))
        return collected
    return []


def verify_parity(
    artifact_dir: Path,
    *,
    allow_version_drift: bool = False,
) -> tuple[int, list[str]]:
    artifact_requests = _load_artifact_requests(artifact_dir)
    if not artifact_requests:
        return 1, [f"No request artifacts found in {artifact_dir}"]

    supabase = SupabaseRest(_supabase_url(), _supabase_key())
    failures: list[str] = []

    for artifact in artifact_requests:
        history_rows = supabase.select(
            "regeneration_history",
            select_cols=(
                "id,request_id,platform,content_type,new_content,"
                "generated_content_id,prompt_hash,result_version,created_at"
            ),
            filters={"request_id": f"eq.{artifact.request_id}"},
            order="created_at.asc",
            limit=50,
        )
        if not history_rows:
            # Poll request IDs are expected to miss; only fail if this was a content-bearing artifact.
            if artifact.expected_content:
                failures.append(
                    f"{artifact.source_file.name}: no regeneration_history rows for request_id={artifact.request_id}"
                )
            continue

        content_rows = [
            row
            for row in history_rows
            if row.get("platform") in {"google", "bing", "shopify"}
            and row.get("content_type") in {"title", "description"}
            and isinstance(row.get("new_content"), str)
            and _normalize_text(row.get("new_content"))
        ]
        if not content_rows:
            if artifact.expected_content:
                failures.append(
                    f"{artifact.source_file.name}: no customer-copy lineage rows for request_id={artifact.request_id}"
                )
            continue

        if artifact.expected_content:
            expected = _normalize_text(artifact.expected_content)
            matched = any(
                _normalize_text(row.get("new_content")) == expected for row in content_rows
            )
            if not matched:
                failures.append(
                    f"{artifact.source_file.name}: response payload content does not match any regeneration_history.new_content row for request_id={artifact.request_id}"
                )

        for row in content_rows:
            row_id = row.get("id")
            gcid = row.get("generated_content_id")
            platform = row.get("platform")
            content_type = row.get("content_type")
            if not isinstance(gcid, str) or not gcid.strip():
                failures.append(
                    f"{artifact.source_file.name}: regeneration_history.id={row_id} missing generated_content_id"
                )
                continue
            gc_rows = supabase.select(
                "generated_content",
                select_cols=(
                    "id,approved_content,candidate_content,"
                    "master_sku,platform,content_type,version,updated_at"
                ),
                filters={"id": f"eq.{gcid}"},
                limit=1,
            )
            if not gc_rows:
                failures.append(
                    f"{artifact.source_file.name}: regeneration_history.id={row_id} references missing generated_content.id={gcid}"
                )
                continue
            gc_row = gc_rows[0]
            latest_rows = supabase.select(
                "regeneration_history",
                select_cols="id,created_at",
                filters={
                    "generated_content_id": f"eq.{gcid}",
                    "platform": f"eq.{platform}",
                    "content_type": f"eq.{content_type}",
                },
                order="created_at.desc",
                limit=1,
            )
            latest_row_id = latest_rows[0].get("id") if latest_rows else None
            if latest_row_id != row_id:
                # Request-level lineage is present, but content has been superseded by a
                # newer write to the same generated_content row.
                continue

            history_text = _normalize_text(row.get("new_content"))
            approved_text = _normalize_text(gc_row.get("approved_content"))
            history_version = _safe_int(row.get("result_version"))
            current_version = _safe_int(gc_row.get("version"))
            candidate_values = _collect_string_leaves(gc_row.get("candidate_content"))
            candidate_match = history_text in candidate_values
            approved_match = history_text == approved_text

            if not (approved_match or candidate_match):
                if (
                    allow_version_drift
                    and history_version is not None
                    and current_version is not None
                    and current_version != history_version
                ):
                    continue
                failures.append(
                    " / ".join(
                        [
                            f"{artifact.source_file.name}",
                            f"request_id={artifact.request_id}",
                            f"regeneration_history.id={row_id}",
                            f"generated_content.id={gcid}",
                            (
                                "mismatch: new_content not found in approved_content "
                                "or candidate_content"
                            ),
                            f"history_version={history_version}",
                            f"current_version={current_version}",
                        ]
                    )
                )

    if failures:
        return 1, failures
    return 0, [
        f"Parity check passed for {len(artifact_requests)} request artifact(s) in {artifact_dir}"
    ]


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--allow-version-drift",
        action="store_true",
        help=(
            "Allow generated_content.version to differ from regeneration_history.result_version. "
            "Useful when validating stale artifacts that have been superseded."
        ),
    )
    parser.add_argument(
        "--env-file",
        type=Path,
        default=None,
        help="Optional .env file to load before Supabase checks.",
    )
    parser.add_argument(
        "artifact_dir",
        type=Path,
        help="Directory containing smoke JSON artifacts.",
    )
    args = parser.parse_args()
    if args.env_file is not None:
        _load_env_file(args.env_file.resolve())
    artifact_dir = args.artifact_dir.resolve()
    if not artifact_dir.is_dir():
        print(f"Artifact directory not found: {artifact_dir}", file=sys.stderr)
        return 2

    status, messages = verify_parity(
        artifact_dir,
        allow_version_drift=bool(args.allow_version_drift),
    )
    for message in messages:
        stream = sys.stderr if status else sys.stdout
        print(message, file=stream)
    return status


if __name__ == "__main__":
    raise SystemExit(main())
