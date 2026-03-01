#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT_DIR"

ENV_FILE="${ENV_FILE:-$ROOT_DIR/.env.vercel}"
PORT="${PORT:-18080}"
IMAGE_TAG="${IMAGE_TAG:-feedops-generation-smoke:local}"
DATE_STAMP="${DATE_STAMP:-$(date +%F)}"
RUN_STAMP="${RUN_STAMP:-$(date +%Y%m%d-%H%M%S)}"
OUTPUT_DIR="${OUTPUT_DIR:-$ROOT_DIR/docs/experiments/${DATE_STAMP}-generation-core-simplification/container-smoke/${RUN_STAMP}}"
CONTAINER_NAME="feedops-generation-smoke-${RUN_STAMP}"

mkdir -p "$OUTPUT_DIR"

if [[ ! -f "$ENV_FILE" ]]; then
  echo "Missing env file: $ENV_FILE" >&2
  exit 1
fi

cleanup() {
  local exit_code=$?
  if docker ps -a --format '{{.Names}}' | grep -qx "$CONTAINER_NAME"; then
    docker logs "$CONTAINER_NAME" >"$OUTPUT_DIR/container.log" 2>&1 || true
    docker rm -f "$CONTAINER_NAME" >/dev/null 2>&1 || true
  fi
  exit "$exit_code"
}
trap cleanup EXIT

echo "Building Docker image: $IMAGE_TAG"
docker build -t "$IMAGE_TAG" .

echo "Starting container: $CONTAINER_NAME"
docker run -d \
  --name "$CONTAINER_NAME" \
  --env-file "$ENV_FILE" \
  -e PORT=8080 \
  -p "${PORT}:8080" \
  "$IMAGE_TAG" >/dev/null

PIPELINE_URL="http://127.0.0.1:${PORT}"

echo "Waiting for /health on ${PIPELINE_URL}"
for _ in $(seq 1 60); do
  if curl -fsS "${PIPELINE_URL}/health" >"$OUTPUT_DIR/health.json"; then
    break
  fi
  sleep 2
done

if [[ ! -s "$OUTPUT_DIR/health.json" ]]; then
  echo "Container failed to become healthy" >&2
  exit 2
fi

python3 - "$PIPELINE_URL" "$OUTPUT_DIR" <<'PY'
from __future__ import annotations

import json
import sys
import time
import uuid
from pathlib import Path
from urllib import error, request

pipeline_url = sys.argv[1].rstrip("/")
output_dir = Path(sys.argv[2])


def call_json(method: str, path: str, payload: dict | None = None, *, timeout: int = 240) -> tuple[int, object, str]:
    req_id = str(uuid.uuid4())
    body = None if payload is None else json.dumps(payload).encode("utf-8")
    req = request.Request(
        f"{pipeline_url}{path}",
        data=body,
        method=method,
        headers={
            "Content-Type": "application/json",
            "X-Request-ID": req_id,
        },
    )
    try:
        with request.urlopen(req, timeout=timeout) as resp:
            raw = resp.read().decode("utf-8", errors="replace")
            try:
                parsed = json.loads(raw)
            except json.JSONDecodeError:
                parsed = raw
            return resp.status, parsed, req_id
    except error.HTTPError as exc:
        raw = exc.read().decode("utf-8", errors="replace")
        try:
            parsed = json.loads(raw)
        except json.JSONDecodeError:
            parsed = raw
        return exc.code, parsed, req_id


def record(name: str, status: int, payload: object, request_id: str, *, started: float, extra: dict | None = None) -> None:
    data = {
        "name": name,
        "http_status": status,
        "request_id": request_id,
        "elapsed_seconds": round(time.perf_counter() - started, 3),
        "payload": payload,
    }
    if extra:
        data.update(extra)
    (output_dir / f"{name}.json").write_text(json.dumps(data, indent=2, sort_keys=True))


def poll_batch_job(name: str, job_id: str) -> dict[str, object]:
    poll_payload: object = {"error": "batch did not complete"}
    poll_request_id = None
    poll_status = None
    for _ in range(90):
        time.sleep(2)
        poll_status, poll_payload, poll_request_id = call_json(
            "GET",
            f"/batch-status/{job_id}",
            None,
            timeout=120,
        )
        if poll_status != 200:
            break
        if isinstance(poll_payload, dict) and poll_payload.get("status") in {"completed", "failed"}:
            break
    (output_dir / f"{name}-poll.json").write_text(
        json.dumps(
            {
                "name": f"{name}-poll",
                "job_id": job_id,
                "poll_request_id": poll_request_id,
                "http_status": poll_status,
                "payload": poll_payload,
            },
            indent=2,
            sort_keys=True,
        )
    )
    return {
        "job_id": job_id,
        "poll_request_id": poll_request_id,
        "poll_http_status": poll_status,
        "poll_payload": poll_payload,
    }


summary: list[dict] = []


def run_single_case(name: str, payload: dict) -> None:
    started = time.perf_counter()
    status, response_payload, request_id = call_json("POST", "/regenerate", payload)
    record(name, status, response_payload, request_id, started=started)
    summary.append(
        {
            "name": name,
            "request_id": request_id,
            "http_status": status,
            "elapsed_seconds": round(time.perf_counter() - started, 3),
        }
    )


def run_batch_case(name: str, payload: dict) -> None:
    started = time.perf_counter()
    status, response_payload, request_id = call_json("POST", "/batch-optimize", payload)
    extra: dict[str, object] = {}
    if status == 200 and isinstance(response_payload, dict) and response_payload.get("job_id"):
        extra.update(poll_batch_job(name, str(response_payload["job_id"])))
    record(name, status, response_payload, request_id, started=started, extra=extra)
    summary.append(
        {
            "name": name,
            "request_id": request_id,
            "job_id": extra.get("job_id"),
            "http_status": status,
            "elapsed_seconds": round(time.perf_counter() - started, 3),
        }
    )


def run_hybrid_case(name: str, payload: dict) -> None:
    started = time.perf_counter()
    status, response_payload, request_id = call_json("POST", "/hybrid-generate", payload)
    extra: dict[str, object] = {}
    if status == 200 and isinstance(response_payload, dict) and response_payload.get("job_id"):
        extra.update(poll_batch_job(name, str(response_payload["job_id"])))
    record(name, status, response_payload, request_id, started=started, extra=extra)
    summary.append(
        {
            "name": name,
            "request_id": request_id,
            "job_id": extra.get("job_id"),
            "http_status": status,
            "elapsed_seconds": round(time.perf_counter() - started, 3),
        }
    )


run_single_case(
    "single-google-title",
    {
        "master_sku": "CL-55",
        "platform": "google",
        "content_type": "title",
        "feedback": "Container smoke title-only runtime scope verification.",
        "async_mode": False,
    },
)
run_single_case(
    "single-google-description",
    {
        "master_sku": "CL-55",
        "platform": "google",
        "content_type": "description",
        "feedback": "Container smoke description-only runtime scope verification.",
        "async_mode": False,
    },
)
run_batch_case(
    "batch-google-title",
    {
        "skus": ["CL-55"],
        "num_candidates": 1,
        "dry_run": False,
        "options": {
            "titles": True,
            "descriptions": False,
            "platforms": ["google"],
        },
    },
)
run_batch_case(
    "batch-google-description",
    {
        "skus": ["CL-55"],
        "num_candidates": 1,
        "dry_run": False,
        "options": {
            "titles": False,
            "descriptions": True,
            "platforms": ["google"],
        },
    },
)
run_hybrid_case(
    "hybrid-google-description",
    {
        "skus": ["1033/18", "1033/24"],
        "options": {"titles": False, "descriptions": True, "platforms": ["google"]},
    },
)
run_hybrid_case(
    "hybrid-google-title",
    {
        "skus": ["1033/18", "1033/24"],
        "options": {"titles": True, "descriptions": False, "platforms": ["google"]},
    },
)

(output_dir / "summary.json").write_text(json.dumps(summary, indent=2, sort_keys=True))
PY

docker logs "$CONTAINER_NAME" >"$OUTPUT_DIR/container.log" 2>&1 || true

echo "Container smoke artifacts written to $OUTPUT_DIR"
