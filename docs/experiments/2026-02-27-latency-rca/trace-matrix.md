# Regenerate Trace Matrix (AS-IS)

Date: 2026-02-27
Branch: `codex/e245-latency-spend-rca-20260227`

## Scope
This matrix traces all required regenerate branches across dashboard, API, provider, and persistence paths.

## Branch Coverage

| Scenario | Entry Route | Python Branch | Provider Path | Persistence Path | Status |
|---|---|---|---|---|---|
| 1. Simple title | `/api/regenerate` (`mode=simple`) | `_execute_regeneration_request` with `selected_platforms=[platform]` | `OpenAIProvider.generate` single platform call | `_persist_regeneration_result` idempotent-aware write | Covered |
| 2. Simple description | `/api/regenerate` (`mode=simple`) | same as above | same as above | same as above | Covered |
| 3. With-feedback title | `/api/regenerate` (`mode=with_feedback`) | feedback layer assembled in `_execute_regeneration_request` | provider call includes feedback in prompt | `_persist_regeneration_result` with `mode=with_feedback` | Covered |
| 4. With-feedback description | `/api/regenerate` (`mode=with_feedback`) | same as above | same as above | same as above | Covered |
| 5. Description + finish branch | `/api/regenerate` (`content_type=description`, `platform in {google,bing}`) | `include_finish=True` appends `finish` platform | provider generates both target platform and `finish` | `variant_finish_sentences` upsert when state=`completed` | Covered |
| 6. Async queued/polled | `/api/regenerate` (`async_mode=true`) + `/api/regenerate/status/[jobId]` | `/regenerate` creates/returns job; `process_regenerate_job` runs in background; `/regenerate/status/{job_id}` polls | same provider path in worker | `generation_jobs` + normal regeneration persistence writes | Covered |
| 7. No-change/idempotent return | sync/async completion result | `_persist_regeneration_result` returns `state=no_change` when content unchanged | provider may run; write suppressed for generated_content/history | no new history row for no-change path | Covered |
| 8. Failure/error path | dashboard error wrapper | HTTP errors from regenerate/status + worker failure updates | retry/repair/circuit errors in provider | `generation_jobs.status=failed` + `error` message | Covered |

## File and Line Trace References

### Dashboard entry + async polling
- `/Users/bobby/.codex/worktrees/e245/Allied-FeedOps/dashboard/src/app/api/regenerate/route.ts:111`
- `/Users/bobby/.codex/worktrees/e245/Allied-FeedOps/dashboard/src/app/api/regenerate/route.ts:243`
- `/Users/bobby/.codex/worktrees/e245/Allied-FeedOps/dashboard/src/app/api/regenerate/status/[jobId]/route.ts:34`
- `/Users/bobby/.codex/worktrees/e245/Allied-FeedOps/dashboard/src/components/review/RegenerateButton.tsx:89`
- `/Users/bobby/.codex/worktrees/e245/Allied-FeedOps/dashboard/src/components/review/RegenerateButton.tsx:125`

### API sync/async orchestration
- `/Users/bobby/.codex/worktrees/e245/Allied-FeedOps/src/feedops/api/main.py:1335`
- `/Users/bobby/.codex/worktrees/e245/Allied-FeedOps/src/feedops/api/main.py:1588`
- `/Users/bobby/.codex/worktrees/e245/Allied-FeedOps/src/feedops/api/main.py:1649`
- `/Users/bobby/.codex/worktrees/e245/Allied-FeedOps/src/feedops/api/main.py:1724`

### Dedupe + lineage + attribution
- `/Users/bobby/.codex/worktrees/e245/Allied-FeedOps/src/feedops/api/main.py:905`
- `/Users/bobby/.codex/worktrees/e245/Allied-FeedOps/src/feedops/api/main.py:913`
- `/Users/bobby/.codex/worktrees/e245/Allied-FeedOps/src/feedops/api/main.py:934`
- `/Users/bobby/.codex/worktrees/e245/Allied-FeedOps/src/feedops/api/main.py:963`
- `/Users/bobby/.codex/worktrees/e245/Allied-FeedOps/src/feedops/api/main.py:688`

### Per-platform generation and finish branch
- `/Users/bobby/.codex/worktrees/e245/Allied-FeedOps/src/feedops/pipeline/generator.py:377`
- `/Users/bobby/.codex/worktrees/e245/Allied-FeedOps/src/feedops/pipeline/generator.py:465`
- `/Users/bobby/.codex/worktrees/e245/Allied-FeedOps/src/feedops/pipeline/generator.py:534`

### Provider retries and timeout budgets
- `/Users/bobby/.codex/worktrees/e245/Allied-FeedOps/src/feedops/providers/factory.py:41`
- `/Users/bobby/.codex/worktrees/e245/Allied-FeedOps/src/feedops/providers/openai_provider.py:166`
- `/Users/bobby/.codex/worktrees/e245/Allied-FeedOps/src/feedops/providers/openai_provider.py:300`
- `/Users/bobby/.codex/worktrees/e245/Allied-FeedOps/src/feedops/providers/openai_provider.py:401`
- `/Users/bobby/.codex/worktrees/e245/Allied-FeedOps/src/feedops/providers/openai_provider.py:487`

### Prompt authority and parity constraints
- `/Users/bobby/.codex/worktrees/e245/Allied-FeedOps/src/feedops/api/prompt_loader.py:143`
- `/Users/bobby/.codex/worktrees/e245/Allied-FeedOps/src/feedops/api/prompt_builder.py:538`
- `/Users/bobby/.codex/worktrees/e245/Allied-FeedOps/src/feedops/observability/__init__.py:35`

### Schema surfaces
- `/Users/bobby/.codex/worktrees/e245/Allied-FeedOps/supabase/migrations/003_content_storage_tables.sql:88`
- `/Users/bobby/.codex/worktrees/e245/Allied-FeedOps/supabase/migrations/004_regeneration_history.sql:30`
- `/Users/bobby/.codex/worktrees/e245/Allied-FeedOps/supabase/migrations/035_measurement_infrastructure_schema.sql:11`
- `/Users/bobby/.codex/worktrees/e245/Allied-FeedOps/supabase/migrations/20260226143000_add_regeneration_history_request_id.sql:2`

## Unknown/Deferred Paths
- No blocking unknown branches were found in the regenerate sync/async flow.
- Separate batch/hybrid/backfill endpoints are out of scope for this RCA except shared provider/runtime code.
