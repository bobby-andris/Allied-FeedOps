# Codex / Claude Session Template

Use this template when starting a new generation-affecting session.

## Startup

1. `cd /Users/bobby/Documents/GitHub/Allied-FeedOps`
2. `git fetch origin --prune`
3. `git switch master`
4. `git pull --ff-only origin master`
5. create a fresh `codex/<topic>-<yyyymmdd>` worktree or branch
6. run `scripts/dev_session_preflight.sh`

## Read First

1. `AGENTS.md`
2. `docs/architecture/generation-runtime-truth.md`
3. `docs/architecture/generation-core-task-model.md`
4. `docs/architecture/generation-prompt-lineage-contract.md`
5. `docs/architecture/generation-pipeline-routing-reference.md`
6. latest relevant experiment report

## Before Editing

Answer these questions:

1. what route is changing?
2. what task graph is expected?
3. what prompts are expected?
4. what lineage rows should exist?
5. what should the dashboard show afterward?

## Before PR

- host tests pass
- container smoke passes
- Cloud Run revision certified
- Supabase lineage verified
- dashboard readback verified
- report updated

## Ready For PR Means

Another developer could read the branch report and reproduce the exact proof without asking for tribal knowledge.
