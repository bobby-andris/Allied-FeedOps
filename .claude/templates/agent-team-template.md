# Multi-Agent Orchestration Template

Use this template when dispatching agent teams for parallel research, data gathering, or analysis.

## Critical Rules

1. **MCP tools ONLY in main context** - Sub-agents can use MCP but need ToolSearch instruction OR gather data first and pass files
2. **Results to files, not messages** - Agents write outputs to disk to prevent context overflow
3. **Orchestrator synthesizes from files** - Don't accumulate agent transcripts, read their output files

## Template Structure

### Step 1: Define Roles & Responsibilities

```markdown
## Team Composition

**Orchestrator (You):**
- Coordinate workflow
- Gather shared MCP data (if any)
- Synthesize agent results
- Present final findings to user

**Agent 1: [Role Name]**
- Responsibility: [specific task]
- Input: [file path or data]
- Output: /tmp/agent-results/agent1-[descriptive-name].md

**Agent 2: [Role Name]**
- Responsibility: [specific task]
- Input: [file path or data]
- Output: /tmp/agent-results/agent2-[descriptive-name].md

[Additional agents as needed]
```

### Step 2: Data Gathering Phase (Main Context)

**If agents need MCP data:**

```markdown
## Phase 1: Data Gathering (Orchestrator)

I will gather all MCP-dependent data here in main context:

Query 1: [SQL or MCP operation]
Query 2: [SQL or MCP operation]

Save to:
- /tmp/agent-data/dataset1.json
- /tmp/agent-data/dataset2.json
```

Execute queries, save results:

```bash
# Create directories
mkdir -p /tmp/agent-data /tmp/agent-results

# Save query results
[Use MCP tools, write results to JSON files]
```

### Step 3: Spawn Agents with Clear Instructions

**Agent Prompt Template:**

```markdown
You are [Agent Role Name]. Your task is [specific responsibility].

## Input Data
- Data location: /tmp/agent-data/[filename]
- [Any additional context needed]

## Your Task
[Detailed, specific instructions - not vague]

Examples:
- ✅ "Analyze the CTR data and identify SKUs with >1000 impressions but <1% CTR"
- ❌ "Analyze performance" (too vague)

## Output Format
Write your findings to: /tmp/agent-results/[your-agent-name].md

Use this structure:
```markdown
# [Agent Role] Findings

## Summary
[2-3 sentence executive summary]

## Detailed Analysis
[Your analysis here with specifics]

## Key Findings
1. [Finding 1 with supporting data]
2. [Finding 2 with supporting data]
3. [etc]

## Recommendations
- [Actionable recommendation 1]
- [Actionable recommendation 2]

## Data Quality Notes
[Any issues with input data, missing data, etc]
```

## Communication
- Keep TaskUpdate messages brief (<3 sentences, status only)
- Put ALL analysis in your output file
- If you need MCP tools, use ToolSearch first: `ToolSearch query: "select:mcp__[tool-name]"`

## Constraints
- Work only with provided data (no fabrication)
- If data is insufficient, state clearly in output
- Complete within [time estimate]
```

**Spawn the agent:**

```
Task tool:
- subagent_type: general-purpose
- name: [agent-role-name]
- description: [Brief description]
- prompt: [Paste template above with specifics filled in]
```

### Step 4: Monitor Progress

While agents work:
- Don't read every TaskUpdate message deeply
- Watch for completion or blocked status
- Prepare synthesis structure

### Step 5: Synthesize Results

**After all agents complete:**

```markdown
## Phase 4: Synthesis (Orchestrator)

Read agent output files from disk:
- Read /tmp/agent-results/agent1-findings.md
- Read /tmp/agent-results/agent2-findings.md
- [etc]

Synthesize findings:
1. Common themes across agents
2. Conflicting findings (if any)
3. Combined recommendations
4. Gaps or areas needing follow-up

Write synthesis to: /tmp/synthesis/combined-findings.md
```

Present to user:

```markdown
## Team Results Summary

**Data Gathered:**
- [Summary of data phase]

**Agent Findings:**
- Agent 1 ([role]): [Key takeaway]
- Agent 2 ([role]): [Key takeaway]

**Combined Insights:**
[Synthesized findings]

**Recommendations:**
[Prioritized action items]

**Full Reports:**
- Agent 1 detailed: /tmp/agent-results/agent1-findings.md
- Agent 2 detailed: /tmp/agent-results/agent2-findings.md
- Combined synthesis: /tmp/synthesis/combined-findings.md
```

## Example: 3-Agent Performance Analysis

### Real Usage Example

```markdown
## Objective
Identify underperforming SKUs and recommend optimization priorities

## Team Structure

**Orchestrator:** Gather performance data, synthesize findings
**Agent 1 (Performance Analyst):** Identify low-CTR SKUs with high impressions
**Agent 2 (Content Auditor):** Analyze current content quality for identified SKUs
**Agent 3 (Competitor Researcher):** Check how competitors position similar products

## Execution

### Phase 1: Data Gathering (Main Context)
- Query Google Ads performance (last 30 days)
- Query current content from Supabase
- Save to /tmp/agent-data/

### Phase 2: Spawn Agents
[Launch 3 agents with specific prompts]

### Phase 3: Synthesis
[Combine findings into prioritized SKU list with rationale]
```

## Common Pitfalls to Avoid

❌ **Asking agents to query MCP without ToolSearch instruction**
- Fix: Include explicit ToolSearch step in prompt OR gather data first

❌ **Agents returning massive data in TaskUpdate messages**
- Fix: Instruct agents to write to files, keep messages brief

❌ **Orchestrator trying to read agent transcripts**
- Fix: Read output files only, not full conversation history

❌ **Vague agent instructions**
- Fix: Be specific about inputs, outputs, and success criteria

❌ **Not handling agent failures**
- Fix: Check output files exist, have content, meet quality bar

## Context Management

**For large team operations:**
- Spawn agents sequentially if context is tight (not parallel)
- Use checkpoint skill at 60-70% context
- Write intermediate synthesis files to disk
- Consider breaking into multiple sessions with handoff files

## Integration with GSD

If using GSD workflow:
- Each agent team can execute one GSD phase
- Orchestrator maintains phase state
- Checkpoint between phases
- Update ROADMAP.md with phase completion status

## Reusability

Save this filled-in template for recurring workflows:
- `.claude/templates/agent-team-performance-analysis.md`
- `.claude/templates/agent-team-content-audit.md`
- etc.

Then invoke with: "Use the agent team template for [task type]"
