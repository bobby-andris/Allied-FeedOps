# Branch Retention Policy

## Allowed Branch Types

1. `master`
2. active `codex/*` feature branches
3. intentional long-lived maintenance branches with a documented owner and purpose

## Required Rules

1. no direct implementation on `master`
2. every feature branch starts from synced `master`
3. merged branches should be deleted promptly
4. stale investigative branches should not accumulate

## When To Delete A Local Branch

Delete when:

- it has been merged
- it has been superseded by a newer branch
- it has no active owner

## When To Delete A Remote Branch

Delete when:

- the PR has merged
- the branch is not intentionally retained as a milestone artifact
- the work is already captured by canonical docs or reports

## Worktree Rules

1. one worktree per active feature branch
2. remove worktrees after merge and cleanup
3. do not leave stale worktrees pointing to merged branches

## Retention Exception

If a branch must be retained intentionally, document:

- owner
- reason for retention
- expected deletion date
