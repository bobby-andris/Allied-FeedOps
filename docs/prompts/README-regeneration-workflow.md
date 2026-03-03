# Complete Regeneration Workflow - README

This document explains the two-prompt workflow for performing a complete content regeneration with comprehensive monitoring.

## Overview

The regeneration process is split into two phases, each using its own agent team:

1. **Pre-flight Setup** (`PREFLIGHT-performance-search-insights-setup.md`) - Infrastructure preparation
2. **Main Regeneration** (`REGENERATE-ALL-clear-approved-content.md`) - Content regeneration with monitoring

## Why Two Prompts?

**Separation of concerns:**
- Pre-flight focuses on data collection infrastructure (one-time setup that benefits all future operations)
- Main regeneration focuses on content generation (can be run multiple times without redoing setup)

**Different agent teams:**
- Setup team: Audit, Data Collection, Automation, Monitoring agents
- Regeneration team: Pipeline, Content, Image, Data, Verification monitors

**Checkpoint between phases:**
- Verify pre-flight succeeded before starting expensive regeneration
- Avoids wasting compute if data collection is broken

## Prerequisites (Before Running ANY Prompt)

**1. Prompt 23 must be complete:**
- [ ] Structured title/description columns added to Google Sheets
- [ ] Lifestyle image publishing implemented
- [ ] Shopify publishing strategy documented in CLAUDE.md

**2. System health verified:**
- [ ] Cloud Run pipeline healthy: `curl "$FEEDOPS_PIPELINE_URL/health"`
- [ ] Dashboard builds: `cd dashboard && npm run build`
- [ ] Vercel deployment successful

**3. Vision enabled:**
- [ ] GPT-4 Vision access in OpenAI API key
- [ ] Vision code implemented in Cloud Run pipeline

## Phase 1: Pre-flight Setup

**Estimated time:** 2-4 hours

**What it does:**
1. Audits current state (SKUs with/without performance data and search insights)
2. Backfills missing data for all SKUs (~2,700 SKUs)
3. Sets up automation to collect data for all future SKUs before generation
4. Creates post-publish monitoring infrastructure (tables, API endpoints, dashboard page)

**How to run:**
1. Open a NEW Claude Code chat session
2. Paste the entire contents of `PREFLIGHT-performance-search-insights-setup.md`
3. Let the agent team run (will use TeamCreate to spawn 5 agents)
4. Monitor the task list and agent messages
5. When complete, verify success criteria in the completion report

**Success criteria:**
- [ ] 100% of active SKUs have performance baselines (<30 days old)
- [ ] 100% of active SKUs have search insights data (<30 days old)
- [ ] `ensureAllData()` helper integrated into 3 API routes
- [ ] `search_query_snapshots` table created
- [ ] Monitoring API endpoints created
- [ ] Monitoring dashboard page created
- [ ] All changes committed and pushed to master

**Output artifacts:**
- `docs/audit/preflight-audit-YYYY-MM-DD.md` - Initial gap analysis
- `docs/audit/preflight-completion-YYYY-MM-DD.md` - Completion report
- `dashboard/src/lib/data-collection/ensure-data.ts` - Data collection helpers
- `dashboard/src/app/(dashboard)/monitoring/page.tsx` - Monitoring dashboard

## Phase 2: Main Regeneration

**Estimated time:** 24-48 hours (depends on API rate limits and batch size)

**What it does:**
1. Creates safety snapshots (backups approved content before clearing)
2. Clears all approved content and approval status
3. Regenerates content for ~2,700 SKUs in 10 batches
4. Generates lifestyle images for SKUs missing them
5. Monitors all subsystems continuously (6 parallel monitoring agents)
6. Verifies end-to-end by publishing one test SKU to Google Sheets

**How to run:**
1. **STOP! Verify pre-flight is complete first** (check completion report)
2. Open a NEW Claude Code chat session (separate from pre-flight)
3. Paste the entire contents of `REGENERATE-ALL-clear-approved-content.md`
4. Let the agent team run (will use TeamCreate to spawn 6 agents + lead)
5. Monitor the task list and agent messages (agents will report progress every 250 SKUs)
6. When complete, review the completion report

**Success criteria:**
- [ ] All approved content cleared (0 records)
- [ ] ~2,700 SKUs regenerated with >95% success rate
- [ ] Average quality score >0.80
- [ ] 100% of SKUs have lifestyle images
- [ ] Test SKU published successfully to Google Sheets
- [ ] Structured title/description format verified
- [ ] No critical errors (<5% error rate)
- [ ] Dashboard accessible and functional

**Output artifacts:**
- `docs/backups/regeneration-backup-YYYY-MM-DD.md` - Backup table documentation
- `docs/regeneration/batch-jobs-YYYY-MM-DD.json` - Batch job IDs
- `docs/regeneration/decisions-log-YYYY-MM-DD.md` - Team Lead decisions log
- `docs/regeneration/completion-report-YYYY-MM-DD.md` - Final metrics report
- Screenshots of dashboard pages (via Playwright MCP)

## Agent Team Structure

### Pre-flight Setup Team (5 agents)
```
setup-team/
├── Team Lead (orchestrates)
├── Audit Agent (gap analysis)
├── Data Collection Agent (backfill data)
├── Automation Agent (integrate helpers)
└── Monitoring Agent (build infrastructure)
```

### Main Regeneration Team (6 agents + lead)
```
regeneration-team/
├── Team Lead (orchestrates, makes decisions)
├── Pipeline Monitor (Cloud Run health, rate limits)
├── Content Monitor (batch jobs, quality scores)
├── Image Monitor (lifestyle images, vision API)
├── Data Monitor (performance, search insights)
└── Verification Agent (end-to-end publish test)
```

## Monitoring During Regeneration

**Content Monitor reports every 250 SKUs:**
- "Batch 1: 250/270 complete, 3 failures, avg quality 0.82"

**Pipeline Monitor alerts on:**
- API response time >3 seconds
- Error rate >5%
- Rate limit (429) responses

**Image Monitor alerts on:**
- Vision API error rate >5%
- Storage upload failure rate >2%
- Generation stalls >5 minutes

**Data Monitor verifies:**
- Performance data stays current (<30 days old)
- Search insights updated regularly
- Evidence table quality maintained

**Verification Agent checks (every 30 minutes):**
- No orphaned records
- No duplicate entries
- Quality score distribution healthy

## Rollback Plan

If main regeneration fails critically (>20% failure rate):

1. **Stop immediately** - Team Lead broadcasts shutdown
2. **Restore from backup** - Use backup tables created in Phase 0
3. **Investigate** - Review logs, analyze patterns
4. **Fix** - Address root cause
5. **Retry** - Run main regeneration prompt again

Backup tables:
- `approved_content_backup_YYYYMMDD`
- `sku_approvals_backup_YYYYMMDD`

## Post-Regeneration Workflow

After successful regeneration:

1. **Manual review** - Team reviews sample of regenerated content in dashboard
2. **Approve quality content** - Use dashboard approval workflow
3. **Publish batches** - Use batch publish to push to Google Sheets
4. **Monitor performance** - Use `/monitoring` dashboard to track changes
5. **Iterate** - Adjust prompts if quality issues found

## Key MCP Tools Used

**Supabase MCP:**
- `mcp__supabase__execute_sql` - All database queries
- `mcp__supabase__apply_migration` - Create monitoring tables

**Google Ads MCP:**
- `mcp__google-ads-mcp__search` - Fetch performance baselines

**Playwright MCP:**
- `mcp__plugin_playwright_playwright__browser_navigate` - Test dashboard
- `mcp__plugin_playwright_playwright__browser_take_screenshot` - Capture screenshots
- `mcp__plugin_playwright_playwright__browser_console_messages` - Check for errors

**Cloud Run (via Pipeline Client):**
- `POST /search-insights/sync` - Sync search terms from Google Ads
- `POST /search-insights/enrich` - Enrich with Keyword Planner data
- `POST /regenerate` - Generate content for SKUs

## Cost Estimates

**Pre-flight setup:**
- Agent runtime: 2-4 hours × 5 agents = ~$50-100
- API calls: Google Ads (performance data), Keyword Planner (search volume)
- Database operations: Minimal cost (Supabase queries)

**Main regeneration:**
- Agent runtime: 24-48 hours × 6 agents = ~$600-1,200
- OpenAI API: 2,700 SKUs × ~5,000 tokens/SKU × $0.015/1K tokens = ~$200
- Vision API: 2,700 images × ~1,000 tokens/image × $0.03/1K tokens = ~$80
- Total estimated: ~$900-1,500

## Safety Constraints

**Pre-flight:**
- Don't modify existing data, only add new data
- Use 30-day TTL for cached data (performance baselines, keyword metrics)
- Rate limit Google Ads API calls (fewer requests/min than other services)

**Main regeneration:**
- Always create backup tables before clearing approved content
- Batch carefully to avoid overwhelming Cloud Run (10 batches, stagger by 15 min)
- Monitor continuously - don't set and forget
- Stop immediately if error rate exceeds 20% (rollback plan)

## Troubleshooting

**Pre-flight fails with "Google Ads API quota exceeded":**
- Reduce batch size for performance data fetching
- Add delays between API calls (suggest 1-2 seconds per call)
- Retry failed SKUs after quota resets (hourly limit)

**Main regeneration stalls during batch processing:**
- Check Cloud Run logs for errors: `gcloud run services logs read feedops-pipeline`
- Verify OpenAI API key has sufficient quota
- Check rate limits on OpenAI API dashboard
- Reduce batch size or increase stagger time between batches

**Quality scores unexpectedly low (<0.70 average):**
- Review regeneration prompts in `dashboard/src/lib/regeneration/prompts.ts`
- Check evidence table quality (performance data, search insights present?)
- Verify gold standard examples loaded correctly from `prompt_templates` table
- Consider adjusting quality threshold or regenerating with improved prompts

**Lifestyle images failing to generate:**
- Verify vision is enabled (GPT-4 Vision API key)
- Check Cloud Run endpoint exists: `GET /docs` on pipeline
- Review error logs for vision API failures
- May need to implement image generation endpoint if missing

## Questions or Issues?

- Review completion reports in `docs/audit/` and `docs/regeneration/`
- Check Cloud Run logs: `gcloud run services logs read feedops-pipeline --limit=100`
- Review agent messages in task list (agents report issues to Team Lead)
- Check CLAUDE.md for system constraints and deployment notes
