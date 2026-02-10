---
name: preflight
description: Validate task approach and requirements before execution
---

# Pre-Flight Validation

Before executing the user's request, run these validation checks to catch common failure patterns.

## 1. Data Requirements Check

**If task involves:** "analysis", "plan", "optimize", "recommend", "improve", "audit", "review"

**Action:**
- 🛑 STOP - Do NOT proceed with assumptions or fabricated examples
- ✅ Identify what data needs to be gathered (database tables, API endpoints, files)
- ✅ List the specific queries/reads needed
- ✅ Ask: "Should I gather this data first, then proceed with analysis?"

**Example:**
```
⚠️ This task requires data gathering first.

Data needed:
- Performance metrics from Google Ads (last 30 days)
- Current SKU content from Supabase (generated_content table)
- Approval rates by category

Approach:
1. Query database for real data
2. Present summary for verification
3. THEN proceed with analysis using verified data

Proceed with data gathering?
```

## 2. Multi-Agent + MCP Tool Check

**If task involves:** Spawning agents (Task tool) + database/MCP operations

**Action:**
- ⚠️ Warn: "Sub-agents need explicit ToolSearch instructions for MCP tools"
- 💡 Present options:
  - **Option A:** Gather all MCP data in main context, save to `/tmp/`, pass file paths to agents
  - **Option B:** Include ToolSearch instruction in agent prompts

**Example:**
```
⚠️ This task spawns agents that need MCP data.

Option A (Recommended):
- I run MCP queries here in main context
- Save results to /tmp/agent-data/
- Spawn agents with file paths

Option B:
- Spawn agents with explicit ToolSearch instructions
- Each agent loads its own MCP tools

Which approach do you prefer?
```

## 3. Deployment/Push Check

**If task includes:** "deploy", "push", "commit", "merge", "ship"

**Action:**
- ✅ Add to plan: Build verification before push
- ✅ Verify workflow includes: `build → lint → test → push`
- ⚠️ Remind: "Never push without local verification"

**Example:**
```
✅ Deployment workflow verified:
1. Make code changes
2. Run local build (npm run build / pytest)
3. Fix any errors
4. Run linter
5. THEN git push

This is included in the plan.
```

## 4. Scope & Context Check

**If task seems complex:** >10 steps, multiple phases, deep research

**Action:**
- ⚠️ Warn: "This is complex - may hit context limits"
- 💡 Suggest: "Break into phases with checkpoints?" or "Write checkpoint at 60-70% progress?"

**Example:**
```
⚠️ Complex task detected (estimated 15+ steps)

Risk: Context overflow mid-execution

Recommendation:
- Break into 2-3 phases
- Write checkpoint files after each phase
- OR plan to checkpoint at ~60% progress

Proceed with phased approach or continue in one session?
```

## 5. Database/Schema Check

**If task involves:** Writing SQL queries, database operations

**Action:**
- ✅ Remind: "Check docs/database/SCHEMA.md (or equivalent) for column names"
- ✅ Add to workflow: "Read schema docs BEFORE writing queries"

**Example:**
```
✅ Database query workflow:
1. Read docs/database/SCHEMA.md for table structure
2. Verify column names and types
3. Write query using documented schema
4. Test query

This prevents column name errors.
```

## 6. Stack/Language Check

**If task involves:** Scripts, new files, tools

**Action:**
- ✅ Check project conventions (CLAUDE.md, package.json, pyproject.toml)
- ⚠️ Verify language choice matches project: Python vs Node.js, TypeScript vs JavaScript
- 💡 Remind about existing utilities before writing new code

**Example:**
```
✅ Stack verification:
- Project uses Python for scripts (pyproject.toml found)
- TypeScript for frontend (dashboard/tsconfig.json)
- Existing utilities in: src/lib/, dashboard/src/lib/

Will use Python for this script task.
```

## Output Format

Present findings as a structured report:

```
## Pre-Flight Check Results

✅ **Ready to proceed:** [aspects that look good]

⚠️ **Recommendations:**
- [suggestion 1]
- [suggestion 2]

🛑 **Blockers/Risks:**
- [blocker 1 if any]

**Proposed Approach:**
[Brief outline of how you'll execute based on validations]

Proceed as planned, adjust based on recommendations, or discuss approach?
```

## When to Skip Pre-Flight

Skip this validation for:
- Simple, well-defined tasks (<5 steps)
- User explicitly says "skip preflight" or similar
- Follow-up tasks in same session where context is already established
- Emergency fixes where speed is critical

## Integration with Workflows

**Recommended usage:**
- Complex features: Always run preflight
- Data analysis: Always run preflight
- Multi-agent work: Always run preflight
- Deployments: Usually run preflight
- Bug fixes: Optional (use judgment)
- Trivial edits: Skip
