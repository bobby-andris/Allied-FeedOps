# Main Regeneration: Clear Approved Content & Regenerate All SKUs

## Objective

Perform a complete content regeneration for all SKUs in the system with comprehensive monitoring:
1. Clear all approved content from the database (since previous content was reverted due to quality issues)
2. Regenerate content for all active SKUs using the latest prompts and vision capabilities
3. Generate lifestyle images for SKUs missing them
4. Monitor all subsystems during regeneration (pipeline, content, images, data)
5. Verify end-to-end by publishing one SKU completely to Google Sheets

## CRITICAL Prerequisites

**STOP! Before running this prompt, verify:**
- [ ] Prompt 23 (Publishing Enhancements) is complete - structured title/description + lifestyle image publishing
- [ ] Pre-flight setup is complete - all SKUs have performance baselines + search insights data
- [ ] Cloud Run pipeline is healthy: `curl https://feedops-pipeline-623866089882.us-east1.run.app/health`
- [ ] Dashboard builds successfully: `cd dashboard && npm run build`
- [ ] Vision is enabled in the pipeline (check `OPENAI_API_KEY` includes GPT-4 Vision access)

If any prerequisite is not met, STOP and complete it first.

## CRITICAL: Use Agent Teams with Parallel Monitoring

You MUST use agent teams for this work via the `TeamCreate` and `Task` tools.

**Team name:** `regeneration-team`

**Team structure (6 agents + lead):**
1. **Team Lead** - Orchestrates entire regeneration, coordinates agents, makes critical decisions, handles escalations
2. **Pipeline Monitor** - Watches Cloud Run health, API response times, rate limits, error rates
3. **Content Monitor** - Tracks batch job progress, quality scores, completion rates, content validation
4. **Image Monitor** - Monitors lifestyle image generation, vision API calls, storage uploads, approval status
5. **Data Monitor** - Ensures performance baselines and search insights stay current during regeneration
6. **Verification Agent** - Performs end-to-end publish test, validates database state, checks Google Sheets

**Why 6 agents:**
- ~2,700 SKUs regenerating = massive scale, high failure risk
- Multiple failure points need dedicated monitoring
- Early detection prevents hours of wasted compute
- Parallel monitoring catches issues before they cascade

## Phase 0: Pre-Regeneration Checks

**Owner: Team Lead**

### Tasks

1. **Verify prerequisites:**
   - Check prompt 23 completion: Read `CLAUDE.md` and verify "Shopify Publishing Strategy" section exists
   - Check pre-flight completion: Query `performance_baselines` and `search_queries_by_master_sku` for coverage
   - Check pipeline health: Test `/health` endpoint on Cloud Run
   - Check vision enabled: Look for vision-related code in `src/feedops/api/` (image description generation)

2. **Create safety snapshot:**
   - Before clearing approved content, create backup queries:
     ```sql
     -- Export approved content to temporary backup table
     CREATE TABLE approved_content_backup_YYYYMMDD AS
     SELECT * FROM generated_content WHERE approved_content IS NOT NULL;

     -- Export approval status to backup
     CREATE TABLE sku_approvals_backup_YYYYMMDD AS
     SELECT * FROM sku_approvals WHERE approval_status = 'approved';
     ```
   - Use Supabase MCP: `mcp__supabase__execute_sql`
   - Document backup table names in `docs/backups/regeneration-backup-YYYY-MM-DD.md`

3. **Count SKUs to regenerate:**
   - Query total active SKUs:
     ```sql
     SELECT COUNT(DISTINCT master_sku)
     FROM variant_index
     WHERE master_sku IS NOT NULL;
     ```
   - Estimate time: ~2,700 SKUs × 30 seconds per SKU = ~22.5 hours if sequential
   - Plan batch strategy: 10 batches of 270 SKUs each

4. **Brief all agents:**
   - Use `SendMessage` with `type: "broadcast"` to notify all agents
   - Share: SKU count, estimated time, batch strategy, success criteria
   - Assign monitoring responsibilities

## Phase 1: Clear Approved Content

**Owner: Team Lead (executes), Data Monitor (verifies)**

### Tasks

1. **Clear approved content columns:**
   ```sql
   -- Clear approved content but keep candidate content
   UPDATE generated_content
   SET approved_content = NULL,
       approved_at = NULL,
       approved_by = NULL,
       approved_version = NULL
   WHERE approved_content IS NOT NULL;
   ```

2. **Reset approval status:**
   ```sql
   -- Reset SKU approvals
   UPDATE sku_approvals
   SET approval_status = 'pending',
       approved_at = NULL,
       approved_by = NULL,
       notes = 'Reset for full regeneration - ' || COALESCE(notes, '')
   WHERE approval_status = 'approved';

   -- Reset variant approvals
   UPDATE variant_approvals
   SET approval_status = 'pending',
       approved_at = NULL,
       approved_by = NULL
   WHERE approval_status = 'approved';
   ```

3. **Verification (Data Monitor):**
   - Query count of approved content (should be 0):
     ```sql
     SELECT COUNT(*) FROM generated_content WHERE approved_content IS NOT NULL;
     SELECT COUNT(*) FROM sku_approvals WHERE approval_status = 'approved';
     ```
   - Report to Team Lead: "Approved content cleared - X content records, Y SKU approvals, Z variant approvals"

## Phase 2: Regenerate All SKU Content

**Owner: Team Lead (orchestrates), Content Monitor (tracks progress)**

### Strategy

**Batch approach (recommended):**
- Split 2,700 SKUs into 10 batches of 270 each
- Use `/api/sku-selection/generate` endpoint to create batch jobs
- Monitor batch completion via `/api/batch-generation/status/{job_id}`
- Stagger batch starts by 15 minutes to avoid overwhelming Cloud Run

### Tasks

1. **Get all active SKUs:**
   ```sql
   SELECT DISTINCT master_sku
   FROM variant_index
   WHERE master_sku IS NOT NULL
   ORDER BY master_sku;
   ```

2. **Create 10 regeneration batches:**
   - For each batch (270 SKUs):
     ```bash
     curl -X POST https://allied-feed-ops.vercel.app/api/sku-selection/generate \
       -H "Content-Type: application/json" \
       -d '{
         "masterSkus": ["SKU1", "SKU2", ...],
         "batchName": "full-regen-batch-1",
         "model": "gpt-4o"
       }'
     ```
   - Record batch job IDs in a tracking file: `docs/regeneration/batch-jobs-YYYY-MM-DD.json`

3. **Content Monitor responsibilities:**
   - Poll each batch job status every 60 seconds:
     ```bash
     curl https://allied-feed-ops.vercel.app/api/batch-generation/status/{job_id}
     ```
   - Track metrics per batch:
     - Total SKUs
     - Completed SKUs
     - Failed SKUs
     - Average quality score
     - Average completion time per SKU
   - Alert Team Lead if:
     - Failure rate >10%
     - Average quality score <0.75
     - Any batch stalls (no progress for >10 minutes)
   - Report progress every 250 SKUs: "Batch X: Y/270 complete, Z failures, avg quality A.BC"

4. **Team Lead responsibilities:**
   - Make go/no-go decisions if failure rate exceeds threshold
   - Adjust batch strategy if needed (e.g., smaller batches, slower cadence)
   - Coordinate with Pipeline Monitor if rate limits hit
   - Log all decisions in `docs/regeneration/decisions-log-YYYY-MM-DD.md`

## Phase 3: Generate Missing Lifestyle Images

**Owner: Image Monitor (executes and tracks)**

### Tasks

1. **Identify SKUs missing lifestyle images:**
   ```sql
   -- SKUs with generated content but no approved lifestyle image
   SELECT DISTINCT gc.master_sku
   FROM generated_content gc
   LEFT JOIN generated_images gi ON gc.master_sku = gi.master_sku
     AND gi.approval_status = 'approved'
   WHERE gc.candidate_content IS NOT NULL
     AND gi.id IS NULL
   ORDER BY gc.master_sku;
   ```

2. **Trigger lifestyle image generation:**
   - For each SKU without images:
     ```bash
     curl -X POST https://feedops-pipeline-623866089882.us-east1.run.app/generate-lifestyle-image \
       -H "Content-Type: application/json" \
       -d '{
         "master_sku": "SKU123",
         "use_vision": true
       }'
     ```
   - Note: Endpoint might not exist yet - check Cloud Run API docs at `/docs` first
   - If endpoint doesn't exist, create a task for Automation Agent to add it

3. **Monitor image generation:**
   - Track metrics:
     - Total SKUs needing images
     - Images generated
     - Images failed
     - Vision API errors
     - Storage upload success rate
   - Alert Team Lead if:
     - Vision API error rate >5%
     - Storage upload failure rate >2%
     - Generation stalls for >5 minutes

4. **Verify image accessibility:**
   - Sample 10 random image URLs
   - Test public accessibility: `curl -I {image_url}`
   - Verify images are in Supabase Storage or Shopify CDN
   - Report to Team Lead: "X images generated, Y verified public, Z failed"

## Phase 4: Continuous Monitoring During Regeneration

**Owners: All monitoring agents (parallel execution)**

### Pipeline Monitor Tasks

1. **Watch Cloud Run health:**
   - Poll `/health` endpoint every 60 seconds
   - Track response time (alert if >3 seconds)
   - Check Supabase connection status in response

2. **Monitor API rate limits:**
   - Watch for 429 (rate limit) responses
   - Track OpenAI API usage (model calls, token consumption)
   - Alert Team Lead if approaching quota limits

3. **Track error rates:**
   - Query Cloud Run logs for errors:
     ```bash
     gcloud run services logs read feedops-pipeline \
       --project=bobbys-project-346400 \
       --limit=100 \
       --format=json | grep ERROR
     ```
   - Classify errors: API failures, timeouts, validation failures
   - Alert if error rate >5%

### Data Monitor Tasks

1. **Verify performance data stays current:**
   - Every 500 SKUs regenerated, check:
     ```sql
     SELECT COUNT(*) FROM performance_baselines
     WHERE updated_at < NOW() - INTERVAL '30 days';
     ```
   - Alert if stale data found (data collection automation should prevent this)

2. **Verify search insights stay current:**
   - Check `search_queries` table for recent data
   - Alert if no new search terms in last hour (might indicate sync issue)

3. **Monitor evidence table quality:**
   - Spot-check 10 random SKUs
   - Verify evidence table includes performance metrics + search insights
   - Alert if evidence is incomplete

### Verification Agent Tasks

1. **Database state checks (every 30 minutes):**
   ```sql
   -- Check for orphaned records
   SELECT COUNT(*) FROM generated_content
   WHERE master_sku NOT IN (SELECT DISTINCT master_sku FROM variant_index);

   -- Check for duplicate entries
   SELECT master_sku, platform, COUNT(*)
   FROM generated_content
   GROUP BY master_sku, platform
   HAVING COUNT(*) > 1;

   -- Check quality score distribution
   SELECT
     COUNT(*) as total,
     AVG(quality_score) as avg_score,
     MIN(quality_score) as min_score,
     MAX(quality_score) as max_score
   FROM generated_content
   WHERE candidate_content IS NOT NULL;
   ```

2. **Spot-check content quality:**
   - Sample 5 random SKUs per batch
   - Read `generated_content.candidate_content` for Google platform
   - Verify:
     - Title includes `{FINISH_NAME}` placeholder
     - No hallucinated specs
     - Follows regeneration prompt structure
   - Alert if quality issues found

## Phase 5: End-to-End Publish Verification

**Owner: Verification Agent (executes), Team Lead (approves)**

### Goal
Publish ONE test SKU completely through the pipeline to verify everything works:
- Content generation → Approval → Publishing → Google Sheets verification

### Tasks

1. **Select test SKU:**
   - Choose a recently regenerated SKU with:
     - High quality score (>0.85)
     - Approved lifestyle image
     - Performance baseline + search insights data
   - Use staging environment tag: `feedops-staging`

2. **Approve content manually:**
   ```sql
   -- Approve generated content
   UPDATE generated_content
   SET approved_content = candidate_content,
       approved_at = NOW(),
       approved_by = 'regeneration-team-verification',
       approved_version = 1
   WHERE master_sku = 'TEST_SKU' AND platform = 'google';

   -- Approve SKU
   UPDATE sku_approvals
   SET approval_status = 'approved',
       approved_at = NOW(),
       approved_by = 'regeneration-team-verification'
   WHERE master_sku = 'TEST_SKU';
   ```

3. **Publish to Google Sheets:**
   ```bash
   curl -X POST https://allied-feed-ops.vercel.app/api/publish/sku \
     -H "Content-Type: application/json" \
     -d '{
       "masterSku": "TEST_SKU",
       "environment": "staging"
     }'
   ```

4. **Use Playwright MCP to verify Google Sheets:**
   - Navigate to dashboard:
     ```typescript
     await mcp__plugin_playwright_playwright__browser_navigate({
       url: "https://allied-feed-ops.vercel.app/login"
     });
     ```
   - Login and navigate to the SKU's review page
   - Take screenshot: `mcp__plugin_playwright_playwright__browser_take_screenshot`

5. **Verify in Google Sheets directly:**
   - Read Google Sheets API to verify published content:
   - Check columns: `structured_title`, `structured_description`, `lifestyle_image_link`
   - Verify compound format: `trained_algorithmic_media:"content text"`
   - Verify image URL is publicly accessible

6. **Report to Team Lead:**
   - Summary: "Test SKU published successfully"
   - Include screenshot showing published content
   - List verified fields: structured_title ✓, lifestyle_image ✓, etc.
   - Any issues found (should be zero)

## Phase 6: Completion Report & Cleanup

**Owner: Team Lead (coordinates all agents)**

### Tasks

1. **Gather metrics from all agents:**
   - Content Monitor: Total regenerated, failures, avg quality score
   - Image Monitor: Total images generated, vision errors, accessibility rate
   - Pipeline Monitor: API health, rate limit incidents, error rate
   - Data Monitor: Data freshness, evidence quality
   - Verification Agent: Database state, content quality spot-checks, publish test result

2. **Generate completion report:**
   - Write to: `docs/regeneration/completion-report-YYYY-MM-DD.md`
   - Include:
     - Total SKUs regenerated (target: ~2,700)
     - Success rate (target: >95%)
     - Average quality score (target: >0.80)
     - Lifestyle images generated (target: 100% coverage)
     - Issues encountered and resolutions
     - Time elapsed (start to finish)
     - Next steps (ready for manual review and approval in dashboard)

3. **Verify dashboard accessibility:**
   - Use Playwright MCP to test key pages:
     - `/` - Dashboard overview
     - `/performance` - Performance page
     - `/search-insights` - Search insights page
     - `/review/{master_sku}` - Sample SKU review page
   - Take screenshots of each
   - Verify no errors in browser console

4. **Clean up backup tables (optional):**
   - If regeneration succeeded and spot-checks pass, can drop backup tables:
     ```sql
     DROP TABLE IF EXISTS approved_content_backup_YYYYMMDD;
     DROP TABLE IF EXISTS sku_approvals_backup_YYYYMMDD;
     ```
   - Keep backups for 7 days before dropping

5. **Shutdown team:**
   - Team Lead sends shutdown request to all agents via `SendMessage`
   - Agents respond with final status before shutting down
   - Team Lead verifies all agents shutdown cleanly

## Success Criteria

- [ ] All approved content cleared (0 records with `approved_content`)
- [ ] ~2,700 SKUs regenerated with success rate >95%
- [ ] Average quality score >0.80 across all regenerated content
- [ ] 100% of SKUs have lifestyle images (either existing or newly generated)
- [ ] Performance baselines and search insights data remain current
- [ ] Test SKU published successfully to Google Sheets with structured title/description + lifestyle image
- [ ] Google Sheets compound format verified: `trained_algorithmic_media:"content"`
- [ ] No critical errors during regeneration (error rate <5%)
- [ ] Dashboard accessible and functional
- [ ] Completion report generated with full metrics

## Rollback Plan (If Needed)

If regeneration fails critically (>20% failure rate, major quality issues):

1. **Stop all batch jobs immediately:**
   - Team Lead broadcasts shutdown to all agents
   - Cancel any in-progress API calls

2. **Restore from backup:**
   ```sql
   -- Restore approved content
   UPDATE generated_content gc
   SET approved_content = b.approved_content,
       approved_at = b.approved_at,
       approved_by = b.approved_by,
       approved_version = b.approved_version
   FROM approved_content_backup_YYYYMMDD b
   WHERE gc.master_sku = b.master_sku AND gc.platform = b.platform;

   -- Restore approval status
   UPDATE sku_approvals sa
   SET approval_status = b.approval_status,
       approved_at = b.approved_at,
       approved_by = b.approved_by
   FROM sku_approvals_backup_YYYYMMDD b
   WHERE sa.master_sku = b.master_sku;
   ```

3. **Investigate root cause:**
   - Review Pipeline Monitor logs
   - Check Cloud Run error logs
   - Analyze failed SKU patterns
   - Fix underlying issue before retry

## Important Notes

- **Vision must be enabled** - Verify GPT-4 Vision is available in the OpenAI API key
- **Rate limits are real** - OpenAI has per-minute token limits, batch carefully
- **Quality over speed** - Better to go slower and catch issues early than regenerate badly
- **Monitor continuously** - Don't set and forget, agents must actively watch for problems
- **Communicate proactively** - Agents should report status frequently, not just on errors
- **Team Lead makes decisions** - If something goes wrong, Team Lead decides whether to continue, pause, or rollback

## Team Communication Protocol

- **Use SendMessage tool** for all inter-agent communication
- **Broadcast for milestones** - Team Lead broadcasts phase transitions
- **Direct messages for issues** - Agents message Team Lead directly for blockers
- **Status updates every 250 SKUs** - Content Monitor sends progress updates
- **Immediate alerts** - Any agent seeing critical issue (error rate spike, quality drop) alerts Team Lead immediately

## Post-Regeneration Next Steps

After successful regeneration:
1. **Manual review in dashboard** - Review team inspects sample of regenerated content
2. **Approve high-quality content** - Use dashboard approval workflow
3. **Publish approved batches** - Use batch publish to push to Google Sheets
4. **Monitor performance changes** - Use `/monitoring` dashboard to track post-publish metrics
5. **Iterate on quality** - If quality issues found, adjust prompts and regenerate specific SKUs
