# Anti-Pattern Detector System

**Problem:** Hooks catch Claude's mistakes, but don't catch when USER prompts will trigger known failure modes.

**Solution:** Pattern-matching on user instructions to warn BEFORE execution.

## Known Anti-Patterns from Insights

Based on 86-session analysis, these user instruction patterns frequently lead to failures:

### 1. "Spawn agents to query [database/API]"

**Pattern:** User asks to spawn agents for MCP-dependent work

**Why it fails:** Sub-agents can access MCP tools but need explicit ToolSearch instruction, OR orchestrator should gather data first

**Detection regex:** `(spawn|create|launch|dispatch)\s+(agent|team|agents).*?(query|database|supabase|google ads|MCP|mcp__)`

**Warning:**
```
⚠️ Anti-Pattern Detected: Agent + MCP Work

Your request asks me to spawn agents that will need MCP tools (database/API access).

Known issue: This often fails because:
- Agents need explicit ToolSearch instructions for MCP tools
- OR data should be gathered in main context first

Recommended approaches:

**Option A (Recommended):**
- I gather MCP data in main context NOW
- Save to /tmp/agent-data/
- THEN spawn agents with file paths

**Option B:**
- I spawn agents with explicit ToolSearch instructions
- Each agent loads its own MCP tools
- Slightly more complex but works

Which approach would you prefer?
```

### 2. "Just give me a quick answer" (for analysis/planning tasks)

**Pattern:** User wants analysis without data gathering

**Why it fails:** Leads to fabricated examples and assumptions

**Detection regex:** `(just|quickly|quick|fast|simple)\s+(give|tell|show).*?(answer|analysis|plan|recommend)`

**Warning:**
```
⚠️ Anti-Pattern Detected: Analysis Without Data

Your request asks for [analysis/planning] but indicates you want it quickly.

Known issue: Quick answers often lead to:
- Fabricated examples (e.g., made-up SKU IDs)
- Assumptions instead of real data
- Low confidence in results

Recommended approach:

1. I gather real data first (30-60 seconds)
2. Present summary for verification
3. THEN provide data-grounded analysis

This takes ~2 minutes total but ensures accuracy.

Proceed with data-first approach, or accept assumption-based quick answer?
```

### 3. "[Action] and deploy" / "Fix and push"

**Pattern:** User combines work + deployment in one instruction

**Why it fails:** Often leads to pushing broken code without local verification

**Detection regex:** `(fix|add|update|change|refactor).*?(and|then)\s+(deploy|push|ship)`

**Warning:**
```
⚠️ Anti-Pattern Detected: Combined Work + Deploy

Your request combines implementation + deployment in one step.

Known issue: This often leads to:
- Pushing without running build locally
- TypeScript errors caught only on Vercel
- Failed deployments requiring multiple fix cycles

Recommended workflow:

1. Make code changes
2. Run build locally (npm run build)
3. Fix any errors
4. THEN push to master

I'll execute this workflow automatically.

Proceed with safe deploy workflow?
```

### 4. "Use [Node.js/npm] for this script"

**Pattern:** User specifies wrong language for this project

**Why it fails:** Project uses Python for scripts, not Node.js

**Detection regex:** `(use|write|create).*?(node|npm|javascript).*?(script|tool)`

**Warning:**
```
⚠️ Stack Mismatch Detected

Your request specifies Node.js/npm, but this project uses:
- Python for standalone scripts/pipelines
- TypeScript for dashboard/API routes

Known issue: Using wrong language leads to:
- Inconsistent tooling
- Unnecessary dependencies
- Maintenance friction

Recommended: Use Python for this script task

Proceed with Python, or you specifically need Node.js?
```

### 5. "Optimize [N] SKUs" (without specifying which)

**Pattern:** User asks for bulk operation without data selection

**Why it fails:** Leads to fabricated examples or unclear scope

**Detection regex:** `(optimize|regenerate|update|fix)\s+\d+\s+(sku|product|item)s?\b(?!.*\b(specific|following|these|ids?|list)\b)`

**Warning:**
```
⚠️ Anti-Pattern Detected: Bulk Operation Without Selection

Your request asks to work on N items, but doesn't specify WHICH items.

Known issue: This leads to:
- I fabricate example SKU IDs
- Unclear scope and deliverables
- Work that doesn't match your intent

Recommended approach:

**Option A:** You tell me criteria (e.g., "bottom 10 SKUs by CTR with >100 impressions")
**Option B:** I query database to identify candidates, you approve list

Which would you prefer?
```

### 6. "Continue where we left off"  (after context was lost)

**Pattern:** User expects continuity but no checkpoint exists

**Why it fails:** Context was lost, Claude doesn't remember previous session

**Detection regex:** `(continue|resume|pick up).*?(where|from|off|previous)`

**Warning:**
```
⚠️ Context Continuity Issue Detected

Your request assumes I remember previous work, but:
- This is a new session (or context was reset)
- I don't have access to prior conversation history

Known issue: Proceeding without context leads to:
- Misaligned work
- Duplicated effort
- Missing critical decisions/context

Recommended approach:

Do you have a checkpoint file from the previous session?
- Location: .claude/checkpoints/[date]-[topic].md
- If yes: "Read .claude/checkpoints/[file] and continue"
- If no: Please summarize what was done and what's needed next

Should I look for a checkpoint file, or would you like to summarize?
```

## Implementation as Pre-Prompt Hook

Since we can't directly hook user input, implement this as **behavioral pattern in CLAUDE.md**:

### Add to CLAUDE.md "Critical Behavioral Rules":

```markdown
### Anti-Pattern Detection (Proactive)

**Before executing user requests, check for these known failure patterns:**

1. **Agent + MCP:** "spawn agents to query database" → Warn about MCP access, offer data-first approach
2. **Quick Analysis:** "just give me quick answer" for analysis → Warn about fabrication risk, offer data-first
3. **Combined Deploy:** "fix and push" → Warn about broken deployments, enforce build-first workflow
4. **Wrong Language:** User specifies Node.js for script → Remind project uses Python
5. **Bulk Without Selection:** "optimize 10 SKUs" without specifying which → Ask for criteria or offer to query
6. **Assumed Continuity:** "continue where we left off" → Check for checkpoint file first

**Format for warnings:**

```
⚠️ Anti-Pattern Detected: [Name]

Your request: [restate user's request]

Known issue: [why this pattern fails]

Recommended: [better approach]

Proceed with recommendation, or you have specific reason for original approach?
```

**Don't be annoying:**
- Only warn if pattern matches closely
- User can override ("proceed anyway")
- Don't warn for same pattern multiple times in one session
```

## Advanced: Pattern Matching as Actual Hook

If we wanted to implement this as an actual hook (requires shell parsing of user input):

```json
{
  "preToolUse": [
    {
      "tool": "*",
      "description": "Anti-pattern detector on user prompts",
      "command": "bash -c 'if echo \"$USER_MESSAGE\" | grep -qiE \"(spawn|create).*agent.*(query|database)\"; then echo \"⚠️ Anti-pattern: Agent+MCP. Consider data-first approach.\"; fi; if echo \"$USER_MESSAGE\" | grep -qiE \"(just|quick).*answer.*(analysis|plan)\"; then echo \"⚠️ Anti-pattern: Quick analysis without data. Risk of fabrication.\"; fi'"
    }
  ]
}
```

**Limitation:** `$USER_MESSAGE` variable doesn't exist in current hook system.

## Benefits

1. **Catches issues before execution** - User gets warned, not surprised
2. **Educational** - Teaches user about failure patterns over time
3. **Saves time** - Prevents 2-3 correction cycles per anti-pattern
4. **Collaborative** - User can override if they have good reason

## Testing

**Test each pattern:**

```bash
# Pattern 1: Agent + MCP
User: "Spawn agent teams to query Supabase for performance data"
Expected: Warning about MCP access

# Pattern 2: Quick analysis
User: "Just give me a quick recommendation on which SKUs to optimize"
Expected: Warning about data-first

# Pattern 3: Combined deploy
User: "Fix the TypeScript errors and push to master"
Expected: Warning about build-first

# Pattern 4: Wrong language
User: "Write a Node.js script to sync data"
Expected: Reminder about Python

# Pattern 5: Bulk without selection
User: "Regenerate content for 20 SKUs"
Expected: Ask which 20 SKUs

# Pattern 6: Assumed continuity
User: "Continue where we left off yesterday"
Expected: Ask for checkpoint file
```

## Integration with /preflight

The `/preflight` skill can include anti-pattern checks:

```markdown
## Step 0: Anti-Pattern Check (Preflight)

Check user's request against known failure patterns:
- [Run pattern matching]
- Issue warnings if patterns detected
- Get user confirmation before proceeding
```

This makes `/preflight` even more powerful.

## Future: Machine Learning

Eventually, could train a classifier on:
- User prompt text
- Whether it led to success/failure
- What corrections were needed

Model predicts failure risk and suggests improvements proactively.

For now, regex + manual patterns work well enough.
