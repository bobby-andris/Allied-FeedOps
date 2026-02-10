---
name: verify-deploy
description: Verify deployment completed successfully after push
---

# Deployment Verification

Closes the loop on deployments by verifying they completed successfully.

## When to Use

**Trigger `/verify-deploy` after:**
- Pushing changes to master
- Waiting ~2-3 minutes for auto-deploy
- Want to confirm deployment succeeded

**Don't use if:**
- Haven't pushed yet (use build verification instead)
- Just pushed seconds ago (deployments take 2-3 minutes)
- Making local changes only

## What This Checks

### For Dashboard Changes (Vercel)

1. **Build Status**
   - Check latest Vercel deployment
   - Verify build completed without errors
   - Get deployment URL

2. **Deployment Health**
   - Hit health endpoint (if exists)
   - Verify returns 200 OK
   - Check response time

3. **Key Pages Accessible**
   - Test critical routes load
   - No 500 errors
   - No obvious visual breaks

### For Pipeline Changes (Cloud Run)

1. **Build Status**
   - Check latest Cloud Build
   - Verify Docker build succeeded
   - Confirm deployment to Cloud Run

2. **Service Health**
   - Hit `/health` endpoint
   - Verify Supabase connection
   - Check response structure

3. **Recent Logs**
   - Check for startup errors
   - Verify no crashes
   - Confirm service is stable

## Execution Flow

### Step 1: Identify What Was Deployed

Check git diff:

```bash
git log -1 --name-only
```

**Determine:**
- Dashboard changes? (files in `dashboard/`)
- Pipeline changes? (files in `src/feedops/`)
- Both?

### Step 2: Vercel Verification (If Dashboard Changes)

**Option A: Using Vercel MCP (if available)**

```typescript
// Use mcp__vercel__ tools to check deployment status
// Get latest deployment
// Check build status
// Get deployment URL
```

**Option B: Using Vercel CLI**

```bash
# Check latest deployment
vercel list --project-id=prj_00zlLdZVgbP8XjDWIEXSRdFyqDqA --limit=1

# Get deployment status
vercel inspect [deployment-url]
```

**Option C: Check Vercel dashboard logs**

```bash
# View logs via Vercel API or dashboard link
echo "View logs: https://vercel.com/[team]/[project]/deployments"
```

**What to verify:**
- ✅ Status: READY (not ERROR or BUILDING)
- ✅ Build time: Reasonable (~1-2 minutes for this project)
- ✅ Commit hash: Matches latest push
- ⚠️ Warnings: Check for deprecation notices

**Test health:**

```bash
# Hit production URL
curl -I https://allied-feed-ops.vercel.app/api/health

# Expected: 200 OK
```

### Step 3: Cloud Run Verification (If Pipeline Changes)

**Check Cloud Build:**

```bash
gcloud builds list \
  --project=bobbys-project-346400 \
  --limit=1 \
  --format="table(id,status,createTime,duration)"
```

**What to verify:**
- ✅ Status: SUCCESS
- ✅ Create time: Recent (within last 5 minutes)
- ✅ Duration: Reasonable (~3-5 minutes for this project)

**Check Cloud Run deployment:**

```bash
gcloud run services describe feedops-pipeline \
  --project=bobbys-project-346400 \
  --region=us-east1 \
  --format="value(status.latestReadyRevisionName,status.conditions)"
```

**What to verify:**
- ✅ Latest revision matches recent deployment
- ✅ Conditions: All READY
- ⚠️ Check for any warnings

**Test health endpoint:**

```bash
curl -s https://feedops-pipeline-623866089882.us-east1.run.app/health | jq .

# Expected response:
# {
#   "status": "healthy",
#   "supabase_connected": true,
#   "timestamp": "[recent-time]"
# }
```

**Check recent logs:**

```bash
gcloud run services logs read feedops-pipeline \
  --project=bobbys-project-346400 \
  --limit=20 \
  --format="table(timestamp,severity,textPayload)"

# Look for:
# - ✅ "Application startup complete"
# - ✅ No ERROR severity logs
# - ⚠️ Any unexpected warnings
```

### Step 4: Report Results

**Format:**

```markdown
## Deployment Verification Results

**Commit:** [hash] - [message first line]
**Pushed:** [timestamp]
**Verified:** [current timestamp]

### Dashboard (Vercel)
- Status: [✅ DEPLOYED / ⚠️ BUILDING / ❌ FAILED]
- Build: [SUCCESS / ERRORS]
- URL: [deployment URL]
- Health: [✅ 200 OK / ❌ Error]
[Details if issues]

### Pipeline (Cloud Run)
- Status: [✅ DEPLOYED / ⚠️ BUILDING / ❌ FAILED]
- Build: [SUCCESS / ERRORS]
- Service: [READY / NOT READY]
- Health: [✅ Healthy / ❌ Unhealthy]
[Details if issues]

### Overall: [✅ ALL SYSTEMS GO / ⚠️ WARNINGS / ❌ FAILURES]
```

**If all successful:**

```markdown
✅ Deployment Verified Successfully

All systems operational:
- Dashboard: https://allied-feed-ops.vercel.app
- Pipeline: https://feedops-pipeline-623866089882.us-east1.run.app

Changes from commit [hash] are live.
```

**If issues found:**

```markdown
❌ Deployment Issues Detected

Dashboard: [issue description]
- [Details]
- [Logs/errors]

Pipeline: [issue description if applicable]
- [Details]
- [Logs/errors]

Recommended action: [rollback / investigate / wait]
```

## Edge Cases

### Still Building

```markdown
⏳ Deployment In Progress

Dashboard: BUILDING (started [time] ago)
Pipeline: BUILDING (started [time] ago)

Typical deploy time: 2-3 minutes

Recommendation: Wait 2 more minutes, then run /verify-deploy again
```

### Partial Success

```markdown
⚠️ Partial Deployment

Dashboard: ✅ Deployed successfully
Pipeline: ❌ Build failed with errors:
[error details]

Since dashboard changes succeeded, those are live.
Pipeline issues need investigation.
```

### Rollback Needed

If critical issues detected:

```markdown
🔴 Critical Issues - Rollback Recommended

Issue: [description of what's broken]
Impact: [production / high / medium]

Rollback options:

1. **Instant (Vercel):** Revert to previous deployment in Vercel dashboard
2. **Git revert:** `git revert [commit-hash] && git push`
3. **Wait for fix:** If low impact, fix forward

Recommend: [Option number] because [reason]

Should I execute rollback, or investigate further?
```

## Integration with /wrapup

**Enhanced wrapup flow:**

```
1. /wrapup executes (CLAUDE.md, build, commit, push)
2. Push completes
3. Auto-suggest: "Wait 2-3 minutes for deploy, then run /verify-deploy"
4. User runs /verify-deploy after waiting
5. Confirmation deployment succeeded
```

## Automation Opportunity

**Future enhancement:** Hook that runs automatically 3 minutes after push:

```json
{
  "postToolUse": [
    {
      "tool": "Bash",
      "pattern": ".*git push.*",
      "command": "bash -c 'echo \"⏰ Deploy verification: Run /verify-deploy in 2-3 minutes\"'"
    }
  ]
}
```

## Time Estimate

Typical `/verify-deploy` execution: 30-60 seconds

- Cloud Build check: 5s
- Cloud Run check: 5s
- Health endpoints: 5s
- Vercel check: 5-10s
- Log review: 10-20s
- Report generation: 5s
