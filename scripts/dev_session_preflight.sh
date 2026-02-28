#!/usr/bin/env bash
set -euo pipefail

fail() {
  echo "preflight: FAIL - $1" >&2
  exit 1
}

info() {
  echo "preflight: $1"
}

REPO_ROOT="$(git rev-parse --show-toplevel 2>/dev/null || true)"
[[ -n "$REPO_ROOT" ]] || fail "not inside a git repository"
EXPECTED_REPO="${FEEDOPS_EXPECTED_REPO:-}"
if [[ -n "$EXPECTED_REPO" ]]; then
  [[ "$REPO_ROOT" == "$EXPECTED_REPO" ]] || fail "repo root mismatch (expected $EXPECTED_REPO, got $REPO_ROOT)"
else
  info "repo root detected: $REPO_ROOT"
fi

CURRENT_BRANCH="$(git branch --show-current)"
[[ -n "$CURRENT_BRANCH" ]] || fail "detached HEAD is not allowed for active development"

if ! git diff --quiet || ! git diff --cached --quiet; then
  fail "working tree is not clean"
fi

[[ "$CURRENT_BRANCH" != "master" ]] || fail "do not implement on master"
[[ "$CURRENT_BRANCH" == codex/* ]] || fail "branch must use codex/* prefix"

info "fetching origin to verify master parity"
git fetch origin --prune >/dev/null 2>&1

MASTER_LOCAL="$(git rev-parse master)"
MASTER_REMOTE="$(git rev-parse origin/master)"
[[ "$MASTER_LOCAL" == "$MASTER_REMOTE" ]] || fail "local master is not in sync with origin/master"

info "PASS"
echo "  repo_root: $REPO_ROOT"
echo "  branch: $CURRENT_BRANCH"
echo "  master_sha: $MASTER_LOCAL"
