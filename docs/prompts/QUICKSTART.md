# FeedOps Prompt Quick Start Guide

## Execution Order

1. **Prompt 10** → Dashboard Implementation (07 & 08)
2. **Prompt 09** → GCP Cloud Run Setup
3. **Prompt 11** → Production Readiness Audit

After each prompt, run the **Verification & Completion Prompt** below.

---

## Quick Start: Prompt 10 (Dashboard Implementation)

**When to run:** First - implements remaining dashboard features

**Copy and paste into a new Claude Code chat:**

```
I need to implement the remaining dashboard features. Please enter plan mode and use the prompt at docs/prompts/10-complete-dashboard-implementation.md as your guide.

Key context:
- Repository: /Users/bobby/Documents/GitHub/Allied-FeedOps
- Dashboard: /dashboard (Next.js 14+)
- Live URL: https://allied-feed-ops.vercel.app
- Supabase project: qezuszwufortkiutlhym
- Google Ads customer ID: 6253381786

Goals:
1. Implement Prompt 07 (Dashboard Overview with real stats and charts)
2. Implement Prompt 08 (SKU Selection & Generation page)
3. Verify all prompts 01-08 are correctly implemented
4. Ensure build passes and no TypeScript errors

Use the brainstorming skill before implementation decisions. Use parallel subagents where appropriate. Create a task list to track progress. Use the verification-before-completion skill before claiming any task is done.

Do NOT commit changes until the full implementation is complete and verified.
```

---

## Quick Start: Prompt 09 (GCP Cloud Run Setup)

**When to run:** After Prompt 10 - sets up infrastructure for batch generation

**Copy and paste into a new Claude Code chat:**

```
I need to set up GCP Cloud Run for the FeedOps Python pipeline. Please enter plan mode and use the prompt at docs/prompts/09-gcp-cloud-run-setup.md as your guide.

Key context:
- Repository: /Users/bobby/Documents/GitHub/Allied-FeedOps
- Python pipeline: /src/feedops/
- Dashboard: /dashboard (needs to call Cloud Run)
- Supabase project: qezuszwufortkiutlhym

Goals:
1. Install and configure gcloud-mcp and cloud-run-mcp servers in Claude Code
2. Create Dockerfile for Python pipeline
3. Create FastAPI entry point (src/feedops/api/main.py)
4. Apply database migrations for generation_jobs tables
5. Document deployment commands (don't actually deploy without my approval)

Important:
- Do NOT store secrets in code - use environment variables or Secret Manager
- The FastAPI server should expose /health, /optimize-sku, /regenerate, /batch-optimize
- Test container locally with Docker before documenting Cloud Run deployment

Use the brainstorming skill for architecture decisions. Create a task list to track progress. Use the verification-before-completion skill before claiming any task is done.

Do NOT commit changes until the full implementation is complete and verified.
```

---

## Quick Start: Prompt 11 (Production Readiness Audit)

**When to run:** After Prompts 09 and 10 - final verification before production

**Copy and paste into a new Claude Code chat:**

```
I need to run a production readiness audit on the FeedOps dashboard. Please enter plan mode and use the prompt at docs/prompts/11-production-readiness-audit.md as your guide.

Key context:
- Repository: /Users/bobby/Documents/GitHub/Allied-FeedOps
- Dashboard: /dashboard (Next.js 14+)
- Live URL: https://allied-feed-ops.vercel.app
- Supabase project: qezuszwufortkiutlhym

Goals:
1. Security audit (auth, env vars, input validation, CORS)
2. Performance audit (bundle size, query optimization, caching)
3. Error handling audit (boundaries, logging, monitoring)
4. Accessibility audit (WCAG, responsive design)
5. Manual QA checklist verification
6. Documentation completeness check

Use the systematic-debugging skill if issues are found. Use parallel subagents for independent audit areas. Create a task list to track findings.

Generate a summary report of all findings with:
- Critical issues (must fix)
- Warnings (should fix)
- Recommendations (nice to have)

Do NOT commit changes until I've reviewed the findings.
```

---

## Verification & Completion Prompt

**When to run:** After EACH prompt implementation is complete

**Copy and paste into the SAME chat where you just implemented a prompt:**

```
The implementation appears complete. Before we commit and push, I need you to:

## 1. VERIFICATION CHECKLIST

Run these checks and report results:

### Build Verification
- Run `cd dashboard && npm run build` - report exit code
- Run `cd dashboard && npx tsc --noEmit` - report any errors
- Run `cd dashboard && npm run lint` - report any warnings/errors

### Python Tests (if Python code was modified)
- Run `source .venv/bin/activate && PYTHONPATH=./src python -m pytest tests/ -v --tb=short` - report pass/fail count

### Implementation Completeness
- List each feature/task from the prompt
- For each, confirm: ✅ Implemented, ⚠️ Partial, ❌ Not done
- If any are not ✅, explain what's missing

## 2. VISUAL INSPECTION WITH PLAYWRIGHT

Use the Playwright MCP server to visually verify the implementation:

1. Navigate to https://allied-feed-ops.vercel.app/login
2. Take a screenshot of the login page
3. Navigate to each page that was modified/created in this implementation
4. Take screenshots of each page
5. Report any visual issues, broken layouts, or missing elements

If Playwright can't launch (browser already running), use WebFetch to verify pages load without errors.

## 3. GIT STATUS & DIFF REVIEW

Run `git status` and `git diff --stat` to show:
- All files that were modified
- All files that were created
- Confirm no sensitive files (.env, credentials) are staged

## 4. DOCUMENTATION UPDATES

Based on what was implemented, determine if updates are needed to:

### CLAUDE.md (project memory for AI agents)
Add/update if:
- New pages or routes were added
- New API endpoints were created
- New environment variables are required
- New database tables were created
- Important architectural decisions were made

### README.md (human documentation)
Add/update if:
- Setup instructions changed
- New commands are available
- New features need user documentation

### AGENTS.md (content generation guidelines)
Add/update if:
- New content policies were implemented
- Platform-specific rules changed
- Scoring or validation rules changed

Propose the specific additions/changes needed for each file.

## 5. COMMIT & PUSH

Once I approve the verification results and documentation updates:

1. Stage all relevant files (excluding any sensitive data)
2. Create a descriptive commit message summarizing what was implemented
3. Push to origin master
4. Report the commit hash and confirm push succeeded

## 6. FINAL SUMMARY

Provide a summary including:
- What was implemented
- What documentation was updated
- Any known limitations or follow-up tasks
- Next recommended action

---

Please proceed with steps 1-4 now. Wait for my approval before step 5.
```

---

## Post-Completion: Update Memory Files

After pushing changes, if significant updates were made, you may want to run this to ensure documentation is comprehensive:

```
Review the current state of CLAUDE.md, README.md, and AGENTS.md. Based on the recent changes pushed to the repository, ensure these files accurately reflect:

1. CLAUDE.md:
   - All implemented dashboard pages and their routes
   - All API endpoints and their purposes
   - Current database schema (tables we rely on)
   - Environment variables required
   - Key file locations

2. README.md:
   - Accurate setup instructions
   - All available CLI commands
   - Feature descriptions that match current implementation

3. AGENTS.md:
   - Any new content policies
   - Updated platform guidelines
   - Current scoring rubrics

Make minimal, focused updates. Don't rewrite sections that are already accurate. Show me the proposed changes before committing.
```

---

## Troubleshooting

### Playwright won't launch
Chrome is probably already running. Either:
- Close Chrome and retry
- Use WebFetch instead to verify pages load

### Build fails
Check the error message for:
- Missing dependencies → `npm install`
- TypeScript errors → Fix type issues
- Environment variables → Ensure they're set in Vercel

### Tests fail
- Read the failure message carefully
- Check if the test is testing removed functionality
- Use systematic-debugging skill to investigate

### Push rejected
- Pull latest: `git pull origin master --rebase`
- Resolve conflicts if any
- Push again
