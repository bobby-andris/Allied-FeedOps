---
name: wrapup
description: Automated end-of-session workflow (CLAUDE.md update, continuation prompt, push)
---

# Session Wrap-Up Automation

Automates your standard end-of-session workflow in one command.

## What This Does

Executes your complete wrap-up sequence:
1. ✅ Update CLAUDE.md with session learnings
2. ✅ Run build verification (TypeScript + lint)
3. ✅ Write continuation prompt if work is unfinished
4. ✅ Git commit with descriptive message
5. ✅ Push to master
6. ✅ Summarize what was accomplished

## When to Use

**Trigger `/wrapup` when:**
- Session is complete or nearly complete
- You're ready to commit and push changes
- You want to wrap up cleanly before ending

**Don't use if:**
- Work is in unstable state (failing tests/builds)
- You want to review changes manually first
- Making experimental changes you might revert

## Execution Flow

### Step 1: Gather Session Context

Review this session's work:
- What files were modified?
- What was accomplished?
- What remains unfinished?
- Any new patterns/learnings discovered?

### Step 2: Update CLAUDE.md

**Check if new learnings should be added to CLAUDE.md:**

**Add to CLAUDE.md if:**
- New pattern discovered (e.g., "import X before Y")
- New anti-pattern identified (e.g., "don't use X for Y")
- Critical bug fix with root cause worth documenting
- New workflow or best practice emerged
- Architecture decision made

**Skip if:**
- Just routine feature work with no new insights
- Only bug fixes for obvious typos/mistakes
- Changes are purely cosmetic
- Nothing notable to document

**Where to add in CLAUDE.md:**
- Behavioral rules → "Critical Behavioral Rules" section
- Component patterns → "Component Patterns" or "Key Locations"
- Database insights → "Key Database Tables" or "Conventions"
- Deployment learnings → "Deployment" or "Troubleshooting"
- General learnings → Create new section if needed

**Example additions:**

```markdown
## [Section Name]

**[Pattern Name]** ([Date discovered])
- **Issue**: [What went wrong or what was confusing]
- **Solution**: [How to do it correctly]
- **Example**: [Code or command example]
```

If updating CLAUDE.md, edit the file now.

### Step 3: Verify Build

**MANDATORY: Run build verification before committing**

```bash
cd dashboard && npm run build && npm run lint
```

**If build fails:**
- ❌ STOP wrapup
- Fix errors first
- Re-run `/wrapup` after fixes

**If build passes:**
- ✅ Continue to next step

### Step 4: Write Continuation Prompt (If Needed)

**Write continuation prompt if:**
- Work is partially complete
- There's a clear "next step"
- You'll return to this work in a future session
- Session hit context limits mid-work

**Skip if:**
- Work is fully complete
- No obvious follow-up needed
- This was a one-off task

**Continuation prompt template:**

Write to: `.claude/prompts/continue-[YYYY-MM-DD]-[topic].md`

```markdown
# Continuation: [Topic/Task Name]

**Date:** [current date]
**Previous Session:** [brief 1-sentence summary of what was done]

## Context

**Completed:**
- [Task 1]
- [Task 2]

**Current State:**
- [What's working]
- [What's not yet finished]

**Files Modified:**
- `[file1]` - [what changed]
- `[file2]` - [what changed]

## Next Steps

1. [First action to take]
2. [Second action]
3. [Third action]

## Important Context

- [Any non-obvious state]
- [Decisions made that inform next steps]
- [Things to watch out for]

## Resume Command

```bash
# To resume this work:
Read .claude/prompts/continue-[date]-[topic].md

# Then:
[Specific next action]
```
```

If writing continuation prompt, create the file now.

### Step 5: Commit Changes

**Generate commit message:**

**Format:**
```
<type>: <brief summary>

<detailed description if needed>

- [Key change 1]
- [Key change 2]

Co-Authored-By: Claude Sonnet 4.5 <noreply@anthropic.com>
```

**Types:**
- `feat:` - New feature
- `fix:` - Bug fix
- `refactor:` - Code restructuring
- `docs:` - Documentation updates
- `chore:` - Maintenance tasks
- `test:` - Test additions/fixes

**Example commit messages:**

```
feat: Add lifestyle image approval UI to variant review

- New approval controls for product lifestyle images
- Integration with variant_lifestyle_images table
- Bulk approve/reject actions

Co-Authored-By: Claude Sonnet 4.5 <noreply@anthropic.com>
```

```
fix: Resolve baseline capture query for multi-SKU products

Root cause: Product families (DMF-2/2X, 2/3X) share product_id, causing
aggregation issues in performance queries.

- Update query to handle multiple master_skus per product_id
- Add product_id-based matching logic
- Update CLAUDE.md with multi-SKU pattern

Co-Authored-By: Claude Sonnet 4.5 <noreply@anthropic.com>
```

**Execute commit:**

```bash
git add -A
git commit -m "[message]"
```

### Step 6: Push to Master

**Final check:**
- ✅ Build passed
- ✅ CLAUDE.md updated (if needed)
- ✅ Continuation prompt written (if needed)
- ✅ Changes committed

**Push:**

```bash
git push origin master
```

**Monitor:**
- Vercel will auto-deploy (if dashboard changes)
- Cloud Run will auto-deploy (if Python pipeline changes)

### Step 7: Session Summary

**Present to user:**

```markdown
## Session Wrap-Up Complete ✅

**Accomplished:**
- [Key accomplishment 1]
- [Key accomplishment 2]
- [Key accomplishment 3]

**Files Modified:** [N files]
- [Most significant file changes]

**CLAUDE.md Updated:** [Yes/No]
- [What was added if yes]

**Continuation Prompt:** [Yes/No]
- Location: `.claude/prompts/[filename]` [if yes]

**Commit:** [commit hash]
**Message:** [commit message first line]

**Deployed:** [Pending/In Progress]
- Vercel: [if applicable]
- Cloud Run: [if applicable]

**Next Session:**
- [What to do next, or "Work complete"]
```

## Edge Cases

### Build Fails

```
❌ Build verification failed.

Errors found:
[Show build errors]

Cannot complete wrapup until build passes.

Fix errors and retry /wrapup, or commit manually if intentional.
```

### Nothing to Commit

```
⚠️ No changes to commit.

All files are already staged/committed.

Session summary:
[What was discussed/reviewed]

No wrapup needed.
```

### Experimental/WIP Changes

If user says changes are experimental:

```
⚠️ Experimental changes detected.

Recommend:
1. Create a feature branch instead of pushing to master
2. Use git stash if you want to save but not commit
3. Skip wrapup and handle manually

Proceed with wrapup to master anyway? (Not recommended)
```

## Integration with Other Skills

**Combine with checkpoint:**
- If session was long/complex, suggest running `/checkpoint` first
- Then run `/wrapup` to finalize

**After `/wrapup`:**
- If continuation prompt exists, mention it for next session
- If CLAUDE.md was updated, highlight what was learned

## Options for User

**After presenting summary, ask:**

```
Wrapup complete. Options:

1. ✅ Done - End session
2. 🔍 Review - Show me the diff/commit details
3. 📋 Continue - Keep working in this session
4. ⚠️ Rollback - Undo commit (if needed)

What would you like to do?
```

## Verification Checklist

Before declaring wrapup complete, verify:

- [ ] Build passed (npm run build && npm run lint)
- [ ] CLAUDE.md reviewed for learnings
- [ ] Continuation prompt written (if work unfinished)
- [ ] Commit message is descriptive and accurate
- [ ] Changes pushed to master
- [ ] User presented with summary

## Time Estimate

Typical `/wrapup` execution: 2-3 minutes

- CLAUDE.md review: 30s
- Build verification: 30-60s
- Continuation prompt (if needed): 60s
- Commit + push: 30s
- Summary generation: 30s
