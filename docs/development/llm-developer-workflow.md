# LLM Developer Workflow

## Purpose
Codex, Claude, and human developers must follow the same workflow for generation-affecting work so the repo does not drift into multiple incompatible truths.

## Required Startup Reading Order

1. `AGENTS.md`
2. `docs/architecture/generation-runtime-truth.md`
3. `docs/architecture/generation-core-task-model.md`
4. `docs/architecture/generation-prompt-lineage-contract.md`
5. `docs/architecture/generation-pipeline-routing-reference.md`
6. latest relevant dated experiment report

## Branch And Worktree Rules

1. never implement on `master`
2. always start from synced `master`
3. use a dedicated `codex/*` branch
4. prefer a dedicated worktree for non-trivial work
5. delete merged and stale branches after integration

## Change Execution Loop

1. understand the route and task graph
2. write or confirm the plan
3. implement on the feature branch
4. run host verification
5. run local container smoke
6. deploy and certify Cloud Run
7. verify Supabase lineage
8. verify dashboard readback
9. update the report
10. merge only after all evidence agrees

## If You Find A Divergence

Do not patch speculatively.

Instead:

1. document the exact mismatch
2. identify the smallest failing boundary
3. add a failing regression test when feasible
4. fix the proven root cause
5. rerun the affected proof layers

## Required Proof Before Saying “Done”

- source review complete
- required host tests pass
- container smoke reviewed
- Cloud Run revision certified
- Supabase rows verified
- dashboard readback verified

## Documentation Rule

Every generation-affecting branch must leave behind a dated report that another developer can use to reconstruct:

- what changed
- why it changed
- what was tested
- what revision was certified
- what remains risky, if anything
