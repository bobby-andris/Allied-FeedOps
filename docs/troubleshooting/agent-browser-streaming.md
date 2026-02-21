# Agent Browser Streaming Setup

This setup gives you a live viewport over WebSocket so you can watch an agent-browser run and optionally inject mouse/keyboard input.

## Prerequisites

- `agent-browser` installed
- Browser binaries installed: `agent-browser install`

## 1) Start a streamed browser session

Run this in terminal A:

```bash
scripts/agent-browser-stream.sh http://localhost:3000
```

Defaults:
- Stream socket: `ws://localhost:9223`
- Session: `dashboard-stream`
- Headed mode: enabled

You can override:

```bash
AGENT_BROWSER_STREAM_PORT=9333 AGENT_BROWSER_SESSION=phase8 scripts/agent-browser-stream.sh http://localhost:3000
```

## 2) Start the local viewer

Run this in terminal B:

```bash
scripts/agent-browser-viewer-serve.sh 8787
```

Open:

```text
http://localhost:8787/agent-browser-stream-viewer.html
```

In the page:
- Keep WebSocket URL as `ws://localhost:9223` unless you changed the stream port
- Click `Connect`
- Leave `Enable input injection` on if you want to interact

## 3) Continue automation in terminal C (optional)

Use the same session name while driving commands:

```bash
agent-browser --session dashboard-stream snapshot -i
agent-browser --session dashboard-stream click @e1
agent-browser --session dashboard-stream fill @e2 "920D-6"
```

The viewer will update live as commands run.

## Input protocol notes

Streaming follows the repo docs:
- Frames received as JSON `{"type":"frame","data":"<base64 jpeg>","metadata":...}`
- Input events sent as:
  - `input_mouse` (`mousePressed`, `mouseReleased`, `mouseMoved`, `mouseWheel`)
  - `input_keyboard` (`keyDown`, `keyUp`, `char`)

Source reference:
- `https://github.com/vercel-labs/agent-browser` (README + `docs/src/app/streaming/page.mdx`)

## When to use in current dashboard workflow

- Run now for a quick Phase 7/ops smoke check (session, controls, visibility).
- Run again after Phase 8 implementation for full end-to-end acceptance (Prompt E flow).

Recommended sequence:
1. Start stream + viewer.
2. Execute Prompt E browser flow with one SKU.
3. Review generated output quality and Python single-source-of-truth evidence.
