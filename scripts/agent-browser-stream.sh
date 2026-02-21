#!/usr/bin/env bash
set -euo pipefail

# Launch agent-browser with WebSocket viewport streaming enabled.
# Usage:
#   scripts/agent-browser-stream.sh [url]
# Env:
#   AGENT_BROWSER_STREAM_PORT (default: 9223)
#   AGENT_BROWSER_SESSION (default: dashboard-stream)
#   AGENT_BROWSER_HEADED ("1" = headed, default)

URL="${1:-http://localhost:3000}"
PORT="${AGENT_BROWSER_STREAM_PORT:-9223}"
SESSION="${AGENT_BROWSER_SESSION:-dashboard-stream}"
HEADED="${AGENT_BROWSER_HEADED:-1}"

ARGS=()
if [[ "${HEADED}" == "1" ]]; then
  ARGS+=(--headed)
fi

echo "Starting agent-browser stream:"
echo "  URL:      ${URL}"
echo "  session:  ${SESSION}"
echo "  ws:       ws://localhost:${PORT}"

AGENT_BROWSER_STREAM_PORT="${PORT}" \
  agent-browser \
  --session "${SESSION}" \
  "${ARGS[@]}" \
  open "${URL}"
