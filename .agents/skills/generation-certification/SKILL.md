# Generation Certification

Use this skill whenever a task changes generation behavior, prompt assembly, task scope, runtime routing, lineage persistence, or dashboard readback.

## Required Steps

1. Read:
   - `AGENTS.md`
   - `docs/architecture/generation-runtime-truth.md`
   - `docs/architecture/generation-core-task-model.md`
   - `docs/architecture/generation-prompt-lineage-contract.md`
   - `docs/architecture/generation-pipeline-routing-reference.md`
2. Identify the affected route and expected task graph.
3. Run required host tests.
4. Run local container smoke.
5. Deploy the exact tested commit to Cloud Run.
6. Run the six-scenario live certification matrix.
7. Verify Supabase lineage rows.
8. Run prompt lineage audit.
9. Verify dashboard readback.
10. Update the dated experiment report with evidence and decision.

## Never Claim Done Without

- source review
- container proof
- Cloud Run proof
- Supabase proof
- dashboard proof

## Merge Blocker Rule

If any layer disagrees with the intended task model, the change is not merge-ready.
