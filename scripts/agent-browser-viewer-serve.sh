#!/usr/bin/env bash
set -euo pipefail

PORT="${1:-8787}"
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

echo "Serving stream viewer at:"
echo "  http://localhost:${PORT}/agent-browser-stream-viewer.html"
echo
echo "If your stream port differs from 9223, update WS URL in the page."

cd "${ROOT}"
python3 -m http.server "${PORT}"
