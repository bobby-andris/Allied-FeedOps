---
name: checkpoint
description: Save session state proactively to avoid context overflow
---

# Session Checkpoint

Create a checkpoint of current work to prevent context overflow and enable seamless session resumption.

## When to Use

**Trigger checkpoint when:**
- Context feels long (50+ message exchanges)
- Multi-agent orchestration session
- Complex multi-phase work
- Before major phase transitions
- User says "checkpoint" or "save progress"
- You estimate >60% context usage

**Don't wait until context is full - checkpoint proactively!**

## Checkpoint Process

### 1. Create Checkpoint File

Write to: `.claude/checkpoints/YYYY-MM-DD-[topic].md`

**Template:**

```markdown
# Session Checkpoint: [Topic/Task Name]

**Date:** [timestamp]
**Status:** [in-progress / blocked / ready-for-next-phase / needs-review]
**Context Used:** [estimate: low/medium/high]

## Executive Summary
[2-3 sentences: What was the goal? What's been accomplished? What's remaining?]

## Completed ✅
- [Task 1 with key details]
- [Task 2 with key details]
- [Decision made: X approach chosen because Y]

## In Progress 🔄
- [Current step being worked on]
- [What's partially done]

## Blockers 🛑
- [Blocker 1: description and what's needed to unblock]
- [None if no blockers]

## Next Steps 📋
1. [Next action item with enough detail to start fresh]
2. [Second action]
3. [Third action]

## Key Context to Preserve

**Working Directory:** `[absolute path]`

**Modified Files:**
- `[file 1]` - [what changed]
- `[file 2]` - [what changed]

**Data Locations:**
- MCP query results: `[path if saved to disk]`
- Temporary files: `[paths]`
- Database state: [any relevant info]

**Environment/Configuration:**
- [Any non-obvious state that matters]
- [API keys loaded, services running, etc.]

**Decisions Made:**
- [Decision 1: Why we chose approach X over Y]
- [Decision 2: Trade-offs accepted]

**Learnings/Patterns:**
- [New pattern discovered]
- [Thing that should go in CLAUDE.md]

## Resume Instructions

**To resume this work:**

```bash
# Read checkpoint
Read .claude/checkpoints/[this-file].md

# Resume from Phase [N]
[Specific next command or action to take]
```

**Context needed:**
- [What files to read first]
- [What state to verify]

## Related Files
- [Link to related docs]
- [Link to related code]
- [Link to previous checkpoint if iterative work]
```

### 2. Update CLAUDE.md If Learnings

If you discovered new patterns, anti-patterns, or rules during this session:
- Add them to CLAUDE.md "Critical Behavioral Rules" or relevant section
- Document in checkpoint what was added

### 3. Report to User

```
✅ Checkpoint saved: .claude/checkpoints/[filename].md

Session Summary:
- Completed: [X tasks]
- Current: [working on Y]
- Remaining: [Z tasks]
- Context estimate: [60% / 70% / etc]

Options:
1. Continue in this session (if context allows)
2. Start fresh session: "Read .claude/checkpoints/[file] and continue from [phase]"
3. Review checkpoint and plan next steps

What would you like to do?
```

## Checkpoint Quality Checklist

Before finalizing checkpoint, verify:

- ✅ Someone else (or future-you) could resume work from this doc alone
- ✅ All decisions explained (not just "chose X" but "chose X because Y")
- ✅ File paths are absolute and correct
- ✅ Next steps are actionable (not vague like "continue working")
- ✅ Any data/state is either saved to disk or documented where to re-query it
- ✅ Learnings captured (for CLAUDE.md or future reference)

## Advanced: Multi-Checkpoint Projects

For very large projects spanning many sessions:

**Structure:**
```
.claude/checkpoints/
  project-name/
    001-initial-research.md
    002-architecture-decisions.md
    003-phase-1-implementation.md
    004-phase-1-testing.md
    CURRENT.md -> symlink to latest
```

**Maintain a checkpoint index:**
`.claude/checkpoints/project-name/INDEX.md` that lists all checkpoints chronologically.

## Integration with GSD

If using GSD workflow:
- Checkpoint aligns with phase boundaries
- Reference GSD phase number in checkpoint
- Link to relevant PLAN.md or ROADMAP.md files
- Include current phase status from GSD

Example:
```
## GSD Context
- Current Phase: 3.2 (Implement user authentication)
- Phase Status: 60% complete
- Plan: .planning/phases/phase-3/PLAN.md
- Roadmap: .planning/ROADMAP.md
```

## When NOT to Checkpoint

Skip checkpointing for:
- Very short sessions (<10 messages)
- Simple tasks with no state
- Already at end of work (just finish instead)
- User explicitly wants to power through in one session
