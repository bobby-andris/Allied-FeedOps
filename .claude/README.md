# Claude Code Workflow Automation System

This directory contains hooks, skills, and templates that automate best practices and catch common failure patterns in Claude Code workflows.

## Quick Start

1. **Hooks are active** - See `.claude/hooks/config.json` (already configured)
2. **Skills are available** - Use `/preflight`, `/checkpoint`, `/data-first`
3. **Templates ready** - Copy from `.claude/templates/` for new projects

## System Components

### 1. Hooks (Automatic Enforcement)

**Location:** `.claude/hooks/config.json`

**What they do:**
- Block deploys without passing builds
- Warn about MCP tool access issues in sub-agents
- Type-check after TypeScript edits
- Remind about documentation updates
- Detect potentially dangerous edits

**When they run:**
- `preToolUse` - Before tool execution (can block)
- `postToolUse` - After tool execution (informational)
- `sessionStart` - When session begins
- `sessionEnd` - When session ends

**How to customize:**
Edit `.claude/hooks/config.json` and add/modify hook rules.

### 2. Skills (Triggered Workflows)

**Location:** `.claude/skills/*/SKILL.md`

**Available Skills:**

#### `/preflight` - Pre-Flight Validation
Validates task requirements before execution:
- Data gathering needs
- MCP tool access patterns
- Deployment workflows
- Complexity/scope checks

**When to use:** Before complex tasks, deployments, or data analysis

#### `/checkpoint` - Session State Save
Saves current work state to avoid context overflow:
- Progress summary
- Completed/remaining work
- Resume instructions
- Key context preservation

**When to use:** At 60-70% context, before phase transitions, multi-agent sessions

#### `/data-first` - Data Gathering Enforcement
Enforces gathering real data before analysis:
- Prevents fabricated examples
- Validates data quality
- Documents data sources
- Ensures reproducibility

**When to use:** Before any analysis, planning, or recommendations

**How to use skills:**
Type `/skill-name` in your message to Claude, e.g., `/preflight` or `/checkpoint`

### 3. Templates (Reusable Patterns)

**Location:** `.claude/templates/`

**Available Templates:**

#### `hooks-template.json`
Generic hooks for any project:
- Language-agnostic build checks
- Test enforcement
- Lint validation

**Copy to new project:** `cp .claude/templates/hooks-template.json /path/to/project/.claude/hooks/config.json`

#### `hooks-gsd.json`
GSD workflow-specific hooks:
- Phase alignment checks
- Planning document validation
- Roadmap reminders

**Use with GSD:** Merge with project hooks

#### `agent-team-template.md`
Multi-agent orchestration pattern:
- Role definitions
- Data gathering strategy
- MCP tool handling
- Synthesis workflow

**Use when:** Spawning agent teams for parallel work

## Usage Patterns

### Pattern 1: Starting a Complex Task

```
1. User: "I need to analyze underperforming SKUs and create an optimization plan"
2. Claude: [Uses /preflight skill automatically]
   - Identifies data requirements
   - Proposes data-first approach
   - Checks for complexity/context issues
3. User: "Approved, proceed"
4. Claude: [Uses /data-first pattern]
   - Gathers real SKU performance data
   - Verifies data quality
   - Presents summary
5. User: "Data looks good"
6. Claude: Proceeds with analysis using verified data
```

### Pattern 2: Deploying Changes

```
1. Claude: Makes code changes
2. Hook (automatic): Runs TypeScript check after edits
   - ✅ No errors OR ⚠️ Errors detected
3. User: "Push to master"
4. Hook (automatic): Blocks push, runs build
   - ✅ Build passes → Push allowed
   - ❌ Build fails → Push blocked with error details
5. Claude: Fixes errors, retries
```

### Pattern 3: Multi-Agent Workflow

```
1. User: "Use agents to analyze Google Ads data across categories"
2. Claude: [Reads agent-team-template.md]
3. Hook (automatic): Warns about MCP tool usage
4. Claude: Proposes approach:
   - Gather MCP data in main context first
   - Spawn agents with file paths
   - Agents write results to disk
5. User: "Sounds good"
6. Claude: Executes orchestrated workflow
```

### Pattern 4: Avoiding Context Overflow

```
1. Claude: [Estimates context at ~60%]
2. Claude: [Proactively triggers /checkpoint]
   - Saves progress to .claude/checkpoints/[date]-[topic].md
   - Documents completed work
   - Writes resume instructions
3. User: "Continue in new session" OR "Keep going"
4. If new session: "Read .claude/checkpoints/[file] and continue"
```

## Configuration

### Project-Specific Rules

Add project-specific behavioral rules to **CLAUDE.md top section**:

```markdown
## ⚠️ CRITICAL BEHAVIORAL RULES

- [Project-specific rule 1]
- [Project-specific rule 2]
```

These are READ by Claude but not automatically enforced. Use hooks for enforcement.

### Hook Customization

Edit `.claude/hooks/config.json`:

```json
{
  "preToolUse": [
    {
      "tool": "Bash",
      "pattern": ".*custom-pattern.*",
      "command": "your-validation-script.sh",
      "description": "What this hook does"
    }
  ]
}
```

**Hook variables available:**
- `$COMMAND` - The bash command being run
- `$TOOL` - Tool name being invoked
- `$FILE_PATH` - File being edited/read
- `$PROMPT` - Prompt being sent to agent
- `$OLD_STRING` / `$NEW_STRING` - Edit content

### Skill Customization

Create new skills in `.claude/skills/[name]/SKILL.md`:

```markdown
---
name: my-skill
description: Brief description
---

# Skill Content

Instructions for Claude to follow when skill is invoked.
```

## Best Practices

### 1. Layer Your Defenses

Don't rely on any single mechanism:
- ✅ CLAUDE.md rules (instructions)
- ✅ Hooks (automatic enforcement)
- ✅ Skills (triggered workflows)
- ✅ Templates (reusable patterns)

### 2. Update CLAUDE.md Learnings

After sessions, add new patterns discovered:
```
Session finding → CLAUDE.md rule → Hook if automatable
```

### 3. Checkpoint Proactively

Don't wait for context overflow:
- Long sessions: Checkpoint at 60-70%
- Multi-phase work: Checkpoint between phases
- Multi-agent: Checkpoint before spawning teams

### 4. Data First, Always

For any analysis or planning:
1. Identify data requirements
2. Query real data
3. Verify quality
4. THEN analyze

Never fabricate examples or use assumptions without explicit user approval.

### 5. Test Locally Before Deploy

Hooks enforce this, but remember:
```
Edit → Type-check → Lint → Build → THEN Push
```

## Troubleshooting

### Hooks Not Running

**Check:**
1. File exists: `.claude/hooks/config.json`
2. JSON is valid: `cat .claude/hooks/config.json | jq .`
3. Commands are executable: Test hook command manually
4. Pattern matches: Verify regex patterns

**Debug:**
```bash
# Test hook command manually
export COMMAND="git push origin master"
bash -c '[your hook command]'
```

### Skills Not Available

**Check:**
1. Directory exists: `.claude/skills/[skill-name]/`
2. SKILL.md file exists with front matter:
   ```markdown
   ---
   name: skill-name
   description: Brief description
   ---
   ```
3. Invoke with `/skill-name`

### Agent Teams Failing

**Common issues:**
1. MCP tools without ToolSearch → Add explicit ToolSearch instruction
2. Context overflow → Agents writing too much to messages → Use file outputs
3. Results lost → Orchestrator reading transcripts → Read output files instead

**Solution:** Use `.claude/templates/agent-team-template.md` pattern

## Integration with GSD

If using GSD workflow:

1. **Merge GSD hooks:**
   ```bash
   # Combine project + GSD hooks
   jq -s '.[0] * .[1]' .claude/hooks/config.json .claude/templates/hooks-gsd.json > .claude/hooks/config-merged.json
   mv .claude/hooks/config-merged.json .claude/hooks/config.json
   ```

2. **Use GSD-aware checkpoints:**
   - Reference phase numbers
   - Link to PLAN.md and ROADMAP.md
   - Update phase status after checkpoints

3. **Align phases with skills:**
   - Plan phase → Use `/preflight`
   - Execute phase → Use `/data-first` if analysis involved
   - Phase complete → Use `/checkpoint`

## Maintenance

### Updating Hooks

After discovering new failure patterns:

1. Identify pattern (e.g., "deployed without testing")
2. Add to CLAUDE.md as rule
3. Create hook to enforce if automatable
4. Test hook in isolation
5. Deploy to `.claude/hooks/config.json`

### Creating New Skills

When you repeat a workflow 3+ times:

1. Document the workflow
2. Create skill in `.claude/skills/[name]/SKILL.md`
3. Test by invoking: `/skill-name`
4. Refine based on usage
5. Share template in `.claude/templates/` if generalizable

### Reviewing Effectiveness

Periodically check:
- Are hooks catching issues? (Review hook output)
- Are skills being used? (Track invocations)
- Are new patterns emerging? (Update system)

## Templates for New Projects

### Minimal Setup (Any Project)

```bash
# Copy generic hooks
cp Allied-FeedOps/.claude/templates/hooks-template.json new-project/.claude/hooks/config.json

# Copy core skills
cp -r Allied-FeedOps/.claude/skills/preflight new-project/.claude/skills/
cp -r Allied-FeedOps/.claude/skills/checkpoint new-project/.claude/skills/
cp -r Allied-FeedOps/.claude/skills/data-first new-project/.claude/skills/

# Create CLAUDE.md with behavioral rules section
```

### Full Setup (Complex Project)

```bash
# All of minimal setup, plus:
cp Allied-FeedOps/.claude/templates/agent-team-template.md new-project/.claude/templates/
cp Allied-FeedOps/.claude/templates/hooks-gsd.json new-project/.claude/templates/

# If using GSD:
# Merge GSD hooks into config.json
```

## Getting Help

**Issues with this system:**
- Check Claude Code documentation: https://docs.claude.ai/code
- Review insights report for workflow patterns
- Ask Claude: "Why isn't my hook/skill working?"

**Suggesting improvements:**
- Document the issue
- Propose solution
- Test locally
- Update this README

## Version History

- **2026-02-10:** Initial system created based on usage insights analysis
  - Hooks: Deploy gates, MCP validation, type-checking
  - Skills: preflight, checkpoint, data-first
  - Templates: Generic hooks, GSD hooks, agent teams
