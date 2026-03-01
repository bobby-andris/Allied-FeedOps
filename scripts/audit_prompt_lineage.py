#!/usr/bin/env python3
"""Audit source-expected prompts against persisted regeneration lineage.

This script reconstructs the prompts that should have been sent to the model
for the certified production runs, then compares them to the `system_prompt`,
`user_prompt`, and prompt hashes stored in Supabase `regeneration_history`.

It intentionally covers every prompt row that is actually persisted today:
single-route rows, batch base-generation rows, and hybrid base/adaptation rows.
Finish generation is traced in the route matrix but is not audited as a stored
prompt row because the current runtime does not persist it separately.
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


ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
CANONICAL_ROOT = Path("/Users/bobby/Documents/GitHub/Allied-FeedOps")
DEFAULT_ENV_FILE = ROOT / ".env.vercel"
if not DEFAULT_ENV_FILE.exists():
    DEFAULT_ENV_FILE = CANONICAL_ROOT / ".env.vercel"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from feedops.api.hybrid_generation import (  # noqa: E402
    build_variant_adaptation_prompt as build_runtime_variant_adaptation_prompt,
)
from feedops.api.multi_sku_detection import extract_spec_difference  # noqa: E402
from feedops.api.prompt_loader import get_platform_system_prompt_hash  # noqa: E402
from feedops.api.supabase_loader import load_parent_sku_from_supabase  # noqa: E402
from feedops.generation.contracts import GenerationTaskKind, TaskSpec  # noqa: E402
from feedops.generation.tasks import (  # noqa: E402
    build_task_prompt,
    build_task_system_prompt,
    task_prompt_hash,
)
from feedops.pipeline.evidence import (  # noqa: E402
    build_evidence_table,
    filter_evidence_for_copy_context,
    format_evidence_markdown,
)


REQUEST_CASES = {
    "fe2510cb-b759-4a06-a5df-c58309f1e8a4": {
        "label": "single_google_title",
        "route": "/regenerate",
        "job_id_expected": False,
        "request_feedback": "Post-fix live single title-only verification.",
        "stored_prompt_rows_expected": 1,
    },
    "15d179be-8dec-4cbe-8b24-01fafd8c1a15": {
        "label": "single_google_description",
        "route": "/regenerate",
        "job_id_expected": False,
        "request_feedback": "Post-fix live single description-only verification.",
        "stored_prompt_rows_expected": 1,
    },
    "b9cb52c9-6654-4a50-9fac-e39a437118ff": {
        "label": "batch_google_title",
        "route": "/batch-optimize",
        "job_id_expected": True,
        "job_id": "f3a17184-fde9-41c8-9414-bc6bf873f1a3",
        "stored_prompt_rows_expected": 1,
    },
    "16040988-905e-42fa-93e1-225447fb5b79": {
        "label": "batch_google_description",
        "route": "/batch-optimize",
        "job_id_expected": True,
        "job_id": "ef371ff2-b2c8-4d03-ac99-74ecb5fc36b1",
        "stored_prompt_rows_expected": 1,
    },
    "aada2ba2-b0fb-4194-a200-d126d48f4082": {
        "label": "hybrid_google_title",
        "route": "/hybrid-generate",
        "job_id_expected": True,
        "job_id": "c8119d75-e24c-4f24-9e47-7ae15cc072ee",
        "base_sku": "1033/18",
        "variant_sku": "1033/24",
        "stored_prompt_rows_expected": 2,
    },
    "99c5f032-86fb-4cf1-b115-7f3e714fd216": {
        "label": "hybrid_google_description",
        "route": "/hybrid-generate",
        "job_id_expected": True,
        "job_id": "cbc104f5-f7fd-4e87-8905-27ec6e6e9bea",
        "base_sku": "1033/18",
        "variant_sku": "1033/24",
        "stored_prompt_rows_expected": 2,
    },
}


@dataclass
class LineageRow:
    id: str
    request_id: str
    master_sku: str
    platform: str
    content_type: str
    mode: str | None
    model_version: str | None
    previous_content: str | None
    new_content: str | None
    system_prompt: str | None
    user_prompt: str | None
    prompt_hash: str | None
    assembled_prompt_hash: str | None
    canonical_platform_hash: str | None
    provider_attempt_count: int | None
    parse_retry_count: int | None
    created_at: str | None
    generated_content_id: str | None


def load_env_file(path: Path) -> None:
    for raw_line in path.read_text().splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        os.environ.setdefault(key, value)


def assembled_prompt_hash(system_prompt: str, user_prompt: str) -> str:
    canonical = json.dumps(
        {
            "system_prompt": system_prompt or "",
            "user_prompt": user_prompt or "",
        },
        sort_keys=True,
        separators=(",", ":"),
    )
    return __import__("hashlib").sha256(canonical.encode("utf-8")).hexdigest()


class SupabaseRest:
    def __init__(self, url: str, service_role_key: str) -> None:
        self.base_url = url.rstrip("/") + "/rest/v1"
        self.headers = {
            "apikey": service_role_key,
            "Authorization": f"Bearer {service_role_key}",
            "Accept": "application/json",
        }

    def fetch(self, table: str, params: dict[str, str]) -> list[dict[str, Any]]:
        response = requests.get(
            f"{self.base_url}/{table}",
            headers=self.headers,
            params=params,
            timeout=60,
        )
        response.raise_for_status()
        payload = response.json()
        if isinstance(payload, list):
            return payload
        raise RuntimeError(f"Unexpected payload from {table}: {type(payload)!r}")


def fetch_corrections(
    rest: SupabaseRest,
    *,
    master_sku: str,
    platform: str,
    content_type: str,
) -> list[dict[str, Any]]:
    return rest.fetch(
        "sku_corrections",
        {
            "select": "*",
            "master_sku": f"eq.{master_sku}",
            "platform": f"in.({platform},all)",
            "content_type": f"in.({content_type},all)",
            "is_active": "eq.true",
        },
    )


def build_feedback_by_platform(
    rest: SupabaseRest,
    *,
    request_id: str,
    master_sku: str,
    platform: str,
    content_type: str,
) -> dict[str, str] | None:
    if request_id not in {
        "fe2510cb-b759-4a06-a5df-c58309f1e8a4",
        "15d179be-8dec-4cbe-8b24-01fafd8c1a15",
    }:
        return None

    corrections = fetch_corrections(
        rest,
        master_sku=master_sku,
        platform=platform,
        content_type=content_type,
    )
    feedback_lines: list[str] = []
    if corrections:
        correction_lines: list[str] = []
        for correction in corrections:
            text = (
                correction.get("correction_text")
                or correction.get("text")
                or correction.get("correction")
            )
            if isinstance(text, str) and text.strip():
                correction_lines.append(f"- {text.strip()}")
        if correction_lines:
            feedback_lines.append("Persistent Corrections:\n" + "\n".join(correction_lines))
    request_feedback = REQUEST_CASES.get(request_id, {}).get("request_feedback")
    if isinstance(request_feedback, str) and request_feedback.strip():
        feedback_lines.append("Reviewer Feedback:\n" + request_feedback.strip())
    if not feedback_lines:
        return None
    return {platform: "\n\n".join(feedback_lines)}


def fetch_lineage_rows(rest: SupabaseRest, request_id: str) -> list[LineageRow]:
    rows = rest.fetch(
        "regeneration_history",
        {
            "select": ",".join(
                [
                    "id",
                    "request_id",
                    "master_sku",
                    "platform",
                    "content_type",
                    "mode",
                    "model_version",
                    "previous_content",
                    "new_content",
                    "system_prompt",
                    "user_prompt",
                    "prompt_hash",
                    "assembled_prompt_hash",
                    "canonical_platform_hash",
                    "provider_attempt_count",
                    "parse_retry_count",
                    "created_at",
                    "generated_content_id",
                ]
            ),
            "request_id": f"eq.{request_id}",
            "order": "created_at.asc",
        },
    )
    return [LineageRow(**row) for row in rows]


def build_base_generation_expectation(
    rest: SupabaseRest,
    *,
    row: LineageRow,
) -> dict[str, str]:
    parent_sku = load_parent_sku_from_supabase(row.master_sku)
    if parent_sku is None:
        raise RuntimeError(f"Unable to load parent SKU for {row.master_sku}")

    evidence = build_evidence_table(parent_sku)
    evidence_for_copy = filter_evidence_for_copy_context(evidence)
    evidence_markdown = format_evidence_markdown(
        evidence_for_copy if isinstance(evidence_for_copy, list) else [],
        for_customer_copy=True,
    )
    kind = (
        GenerationTaskKind.TITLE
        if row.content_type == "title"
        else GenerationTaskKind.DESCRIPTION_BASE
    )
    spec = TaskSpec(
        task_id=f"audit-{row.id}",
        kind=kind,
        master_sku=row.master_sku,
        platform=row.platform,
        content_type=row.content_type,
        prompt_version="v2",
        request_id=row.request_id,
    )
    feedback_by_platform = build_feedback_by_platform(
        rest,
        request_id=row.request_id,
        master_sku=row.master_sku,
        platform=row.platform,
        content_type=row.content_type,
    )
    user_prompt = build_task_prompt(
        spec,
        parent_sku=parent_sku,
        evidence=evidence,
        evidence_markdown=evidence_markdown,
        feedback_by_platform=feedback_by_platform,
    )
    system_prompt = build_task_system_prompt(spec)
    return {
        "system_prompt": system_prompt,
        "user_prompt": user_prompt,
        "prompt_hash": task_prompt_hash(system_prompt, user_prompt),
        "assembled_prompt_hash": assembled_prompt_hash(system_prompt, user_prompt),
        "canonical_platform_hash": get_platform_system_prompt_hash(row.platform),
    }


def build_variant_generation_expectation(
    *,
    row: LineageRow,
    request_rows: list[LineageRow],
) -> dict[str, str]:
    case = REQUEST_CASES[row.request_id]
    base_sku = str(case["base_sku"])
    variant_sku = row.master_sku
    base_row = next(
        candidate
        for candidate in request_rows
        if candidate.master_sku == base_sku
        and candidate.platform == row.platform
        and candidate.content_type == row.content_type
        and candidate.mode != "variant-adaptation-v2"
    )
    base_spec, variant_spec = extract_spec_difference(base_sku, variant_sku)
    user_prompt, _requires_json = build_runtime_variant_adaptation_prompt(
        content_type=row.content_type,
        platform=row.platform,
        base_sku=base_sku,
        variant_sku=variant_sku,
        base_content=base_row.new_content or "",
        base_spec=base_spec,
        variant_spec=variant_spec,
        include_finish_sentences=False,
    )
    spec = TaskSpec(
        task_id=f"audit-{row.id}",
        kind=GenerationTaskKind.VARIANT_ADAPTATION,
        master_sku=base_sku,
        variant_sku=variant_sku,
        platform=row.platform,
        content_type=row.content_type,
        prompt_version="v2",
        request_id=row.request_id,
    )
    system_prompt = build_task_system_prompt(spec)
    return {
        "system_prompt": system_prompt,
        "user_prompt": user_prompt,
        "prompt_hash": task_prompt_hash(system_prompt, user_prompt),
        "assembled_prompt_hash": assembled_prompt_hash(system_prompt, user_prompt),
        "canonical_platform_hash": get_platform_system_prompt_hash(row.platform),
    }


def build_route_prompt_matrix() -> list[dict[str, Any]]:
    return [
        {
            "route": "/regenerate",
            "scenario": "single Google title",
            "job_id_expected": False,
            "task_graph": ["TITLE"],
            "system_prompt_source": "build_task_system_prompt(TaskSpec[TITLE]) -> get_platform_system_prompt('google')",
            "user_prompt_source": "build_task_prompt(TaskSpec[TITLE]) -> build_core_prompt(...) + optional persistent corrections + task output contract",
            "stored_prompt_rows": ["google/title base generation"],
        },
        {
            "route": "/regenerate",
            "scenario": "single Google description",
            "job_id_expected": False,
            "task_graph": ["DESCRIPTION_BASE", "FINISH_SENTENCES"],
            "system_prompt_source": "base row uses get_platform_system_prompt('google'); finish subcall uses get_platform_system_prompt('finish')",
            "user_prompt_source": "base row uses build_core_prompt(...) + optional persistent corrections + task output contract; finish subcall uses build_finish_prompt(...)",
            "stored_prompt_rows": [
                "google/description base generation",
                "finish subcall is executed but not persisted as its own regeneration_history row",
            ],
        },
        {
            "route": "/batch-optimize",
            "scenario": "batch Google title",
            "job_id_expected": True,
            "task_graph": ["TITLE"],
            "system_prompt_source": "build_task_system_prompt(TaskSpec[TITLE]) -> get_platform_system_prompt('google')",
            "user_prompt_source": "build_task_prompt(TaskSpec[TITLE]) -> build_core_prompt(...) + task output contract",
            "stored_prompt_rows": ["google/title base generation"],
        },
        {
            "route": "/batch-optimize",
            "scenario": "batch Google description",
            "job_id_expected": True,
            "task_graph": ["DESCRIPTION_BASE", "FINISH_SENTENCES"],
            "system_prompt_source": "base row uses get_platform_system_prompt('google'); finish subcall uses get_platform_system_prompt('finish')",
            "user_prompt_source": "base row uses build_core_prompt(...) + task output contract; finish subcall uses build_finish_prompt(...)",
            "stored_prompt_rows": [
                "google/description base generation",
                "finish subcall is executed but not persisted as its own regeneration_history row",
            ],
        },
        {
            "route": "/hybrid-generate",
            "scenario": "hybrid Google title",
            "job_id_expected": True,
            "task_graph": ["shared TITLE", "VARIANT_ADAPTATION"],
            "system_prompt_source": "both rows use get_platform_system_prompt('google') via build_task_system_prompt(...)",
            "user_prompt_source": "base row uses build_core_prompt(...) + task output contract; variant row uses build_variant_adaptation_prompt(..., include_finish_sentences=False)",
            "stored_prompt_rows": ["google/title base generation", "google/title variant adaptation"],
        },
        {
            "route": "/hybrid-generate",
            "scenario": "hybrid Google description",
            "job_id_expected": True,
            "task_graph": ["shared DESCRIPTION_BASE", "shared FINISH_SENTENCES", "VARIANT_ADAPTATION"],
            "system_prompt_source": "base row uses get_platform_system_prompt('google'); finish subcall uses get_platform_system_prompt('finish'); variant row uses get_platform_system_prompt('google')",
            "user_prompt_source": "base row uses build_core_prompt(...) + task output contract; finish subcall uses build_finish_prompt(...); variant row uses build_variant_adaptation_prompt(..., include_finish_sentences=False)",
            "stored_prompt_rows": [
                "google/description base generation",
                "google/description variant adaptation",
                "finish subcall is executed but not persisted as its own regeneration_history row",
            ],
        },
    ]


def compare_row(
    row: LineageRow,
    expected: dict[str, str],
) -> dict[str, Any]:
    actual_system = row.system_prompt or ""
    actual_user = row.user_prompt or ""
    return {
        "id": row.id,
        "request_id": row.request_id,
        "master_sku": row.master_sku,
        "platform": row.platform,
        "content_type": row.content_type,
        "mode": row.mode,
        "model_version": row.model_version,
        "provider_attempt_count": row.provider_attempt_count,
        "parse_retry_count": row.parse_retry_count,
        "system_prompt_matches": actual_system == expected["system_prompt"],
        "user_prompt_matches": actual_user == expected["user_prompt"],
        "prompt_hash_matches": (row.prompt_hash or "") == expected["prompt_hash"],
        "assembled_prompt_hash_matches": (row.assembled_prompt_hash or "")
        == expected["assembled_prompt_hash"],
        "canonical_platform_hash_matches": (row.canonical_platform_hash or "")
        == expected["canonical_platform_hash"],
        "all_matches": (
            actual_system == expected["system_prompt"]
            and actual_user == expected["user_prompt"]
            and (row.prompt_hash or "") == expected["prompt_hash"]
            and (row.assembled_prompt_hash or "") == expected["assembled_prompt_hash"]
            and (row.canonical_platform_hash or "") == expected["canonical_platform_hash"]
        ),
        "actual": {
            "system_prompt": actual_system,
            "user_prompt": actual_user,
            "prompt_hash": row.prompt_hash or "",
            "assembled_prompt_hash": row.assembled_prompt_hash or "",
            "canonical_platform_hash": row.canonical_platform_hash or "",
        },
        "expected": expected,
    }


def write_outputs(
    *,
    output_dir: Path,
    route_matrix: list[dict[str, Any]],
    cases: list[dict[str, Any]],
) -> None:
    output_dir.mkdir(parents=True, exist_ok=True)
    json_path = output_dir / "prompt-lineage-audit.json"
    md_path = output_dir / "prompt-lineage-audit.md"

    payload = {
        "route_prompt_matrix": route_matrix,
        "cases": cases,
    }
    json_path.write_text(json.dumps(payload, indent=2))

    lines: list[str] = [
        "# Prompt Lineage Audit",
        "",
        "## Job ID Behavior",
        "",
        "Single-route `/regenerate` executions are synchronous and return `RegenerateResponse`, so a missing `job_id` is expected for successful inline single Google title/description runs.",
        "",
        "Batch and hybrid routes create background job rows and therefore return `job_id` values.",
        "",
        "## Route Prompt Matrix",
        "",
    ]

    for entry in route_matrix:
        lines.append(f"### {entry['scenario']}")
        lines.append(f"- Route: `{entry['route']}`")
        lines.append(f"- Job ID expected: `{entry['job_id_expected']}`")
        lines.append(f"- Task graph: `{', '.join(entry['task_graph'])}`")
        lines.append(f"- System prompt source: {entry['system_prompt_source']}")
        lines.append(f"- User prompt source: {entry['user_prompt_source']}")
        lines.append("- Stored prompt rows:")
        for row_desc in entry["stored_prompt_rows"]:
            lines.append(f"  - {row_desc}")
        lines.append("")

    lines.extend(
        [
            "## Row-by-Row Prompt Parity",
            "",
            "| Case | Request ID | Stored rows | All rows matched | Notes |",
            "| --- | --- | ---: | --- | --- |",
        ]
    )
    for case in cases:
        notes = case["notes"]
        lines.append(
            f"| {case['label']} | `{case['request_id']}` | {case['row_count']} | "
            f"{'yes' if case['all_rows_match'] else 'no'} | {notes} |"
        )

    for case in cases:
        lines.extend(
            [
                "",
                f"### {case['label']}",
                "",
                f"- Route: `{case['route']}`",
                f"- Request ID: `{case['request_id']}`",
                f"- Job ID expected: `{case['job_id_expected']}`",
                f"- Job ID: `{case.get('job_id') or 'none'}`",
                f"- Stored prompt rows found: `{case['row_count']}`",
                f"- All stored prompt rows matched source expectation: `{case['all_rows_match']}`",
                "",
                "| SKU | Platform | Content | Mode | System | User | Prompt hash | Assembled hash | Canonical hash |",
                "| --- | --- | --- | --- | --- | --- | --- | --- | --- |",
            ]
        )
        for row in case["rows"]:
            lines.append(
                f"| `{row['master_sku']}` | `{row['platform']}` | `{row['content_type']}` | `{row['mode']}` | "
                f"{'yes' if row['system_prompt_matches'] else 'no'} | "
                f"{'yes' if row['user_prompt_matches'] else 'no'} | "
                f"{'yes' if row['prompt_hash_matches'] else 'no'} | "
                f"{'yes' if row['assembled_prompt_hash_matches'] else 'no'} | "
                f"{'yes' if row['canonical_platform_hash_matches'] else 'no'} |"
            )

    md_path.write_text("\n".join(lines) + "\n")


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--env-file",
        default=str(DEFAULT_ENV_FILE),
        help="Path to env file with Supabase credentials",
    )
    parser.add_argument(
        "--output-dir",
        default=str(
            ROOT
            / "docs/experiments/2026-02-28-production-divergence-closure/prompt-audit"
        ),
        help="Directory for JSON/Markdown artifacts",
    )
    args = parser.parse_args()

    load_env_file(Path(args.env_file))
    supabase_url = os.environ["NEXT_PUBLIC_SUPABASE_URL"]
    service_role_key = os.environ["SUPABASE_SERVICE_ROLE_KEY"]
    rest = SupabaseRest(supabase_url, service_role_key)

    route_matrix = build_route_prompt_matrix()
    cases: list[dict[str, Any]] = []

    for request_id, case_meta in REQUEST_CASES.items():
        request_rows = fetch_lineage_rows(rest, request_id)
        comparisons: list[dict[str, Any]] = []
        for row in request_rows:
            if row.mode == "variant-adaptation-v2":
                expected = build_variant_generation_expectation(
                    row=row,
                    request_rows=request_rows,
                )
            else:
                expected = build_base_generation_expectation(rest, row=row)
            comparisons.append(compare_row(row, expected))

        all_rows_match = all(item["all_matches"] for item in comparisons)
        expected_rows = int(case_meta["stored_prompt_rows_expected"])
        count_matches = len(comparisons) == expected_rows
        notes_parts = []
        if not case_meta["job_id_expected"]:
            notes_parts.append("synchronous route; no job_id expected")
        if any("FINISH_SENTENCES" in ", ".join(entry["task_graph"]) for entry in route_matrix if entry["scenario"].startswith(case_meta["label"].replace("_", " ").split("google")[0].strip()) ):
            pass
        if not count_matches:
            notes_parts.append(
                f"expected {expected_rows} stored prompt rows, found {len(comparisons)}"
            )
        if request_id in {
            "15d179be-8dec-4cbe-8b24-01fafd8c1a15",
            "16040988-905e-42fa-93e1-225447fb5b79",
            "99c5f032-86fb-4cf1-b115-7f3e714fd216",
        }:
            notes_parts.append("finish generation executes but is not stored as a separate prompt row")
        if all_rows_match and count_matches and not notes_parts:
            notes_parts.append("stored prompt rows match source exactly")

        cases.append(
            {
                "label": case_meta["label"],
                "route": case_meta["route"],
                "request_id": request_id,
                "job_id_expected": case_meta["job_id_expected"],
                "job_id": case_meta.get("job_id"),
                "row_count": len(comparisons),
                "expected_row_count": expected_rows,
                "row_count_matches_expectation": count_matches,
                "all_rows_match": all_rows_match and count_matches,
                "notes": "; ".join(notes_parts),
                "rows": comparisons,
            }
        )

    write_outputs(
        output_dir=Path(args.output_dir),
        route_matrix=route_matrix,
        cases=cases,
    )

    failed_cases = [case["label"] for case in cases if not case["all_rows_match"]]
    if failed_cases:
        print("Prompt audit failed:", ", ".join(failed_cases))
        return 1

    print("Prompt audit passed for all certified stored prompt rows.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
