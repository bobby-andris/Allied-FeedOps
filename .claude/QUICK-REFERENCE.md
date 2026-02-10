# Claude Code Quick Reference

## 🚀 When to Use What

| Situation | Use This | Why |
|-----------|----------|-----|
| Starting complex task | `/preflight` | Validates approach before execution |
| Need to analyze data | `/data-first` | Ensures real data, prevents fabrication |
| Session getting long | `/checkpoint` | Saves state before context overflow |
| Spawning agent team | `.claude/templates/agent-team-template.md` | Proper MCP handling, file-based results |
| About to deploy | Hooks auto-run | Enforces build verification |
| Creating new project | `.claude/templates/hooks-template.json` | Generic best practices |

## 🎯 Skills Available

### `/preflight` - Task Validation
✅ Checks data requirements
✅ Validates MCP access patterns
✅ Estimates complexity/scope
✅ Verifies deployment workflows

**Use before:** Complex features, analysis, deployments

### `/checkpoint` - Save Progress
✅ Documents completed work
✅ Preserves context for resumption
✅ Prevents context overflow
✅ Enables session handoffs

**Use at:** 60-70% context, phase boundaries, before agent teams

### `/data-first` - Real Data Enforcement
✅ Prevents fabricated examples
✅ Validates data quality
✅ Documents assumptions
✅ Ensures reproducibility

**Use before:** Any analysis, planning, or recommendations

## 🔒 Automatic Protections (Hooks)

These run automatically, no action needed:

✅ **Deploy blocked** without passing build
✅ **Type errors caught** immediately after TypeScript edits
✅ **MCP warnings** when spawning agents incorrectly
✅ **Import removal alerts** during edits
✅ **End-of-session reminders** to update docs

## 📋 Common Workflows

### Deploy Changes
```
1. Make edits → Hook checks types automatically
2. "Push to master" → Hook runs build
3. ✅ Passes → Push allowed
4. ❌ Fails → Fix errors, retry
```

### Analyze Data
```
1. "Analyze X" → Use /data-first
2. Gather real data first
3. Verify quality
4. THEN analyze
```

### Multi-Agent Work
```
1. Check agent-team-template.md
2. Gather MCP data in main context
3. Spawn agents with file paths
4. Synthesize from files, not messages
```

### Long Session
```
1. ~60% context → Use /checkpoint
2. Saves progress to .claude/checkpoints/
3. Continue OR start fresh session
4. Resume: "Read .claude/checkpoints/[file] and continue"
```

## ⚠️ Critical Rules

1. **Pre-Deploy:** Build → Lint → Test → Push (hooks enforce this)
2. **Data First:** Query real data before analysis (never fabricate)
3. **MCP in Agents:** Include ToolSearch OR gather data first
4. **Checkpoint Early:** At 60-70% context, not when full
5. **Schema First:** Read docs/database/SCHEMA.md before SQL

## 🛠️ Customization

**Add project-specific rules:**
Edit `CLAUDE.md` → "Critical Behavioral Rules" section

**Add custom hooks:**
Edit `.claude/hooks/config.json` → Add new preToolUse/postToolUse rules

**Create new skills:**
```bash
mkdir .claude/skills/my-skill
# Create SKILL.md with front matter
```

**Agent team patterns:**
Copy `.claude/templates/agent-team-template.md` → Fill in your workflow

## 🔍 Troubleshooting

**Hook not running?**
- Check `.claude/hooks/config.json` exists and is valid JSON
- Test command manually: `export COMMAND="..."; bash -c '[hook command]'`

**Skill not available?**
- Verify `.claude/skills/[name]/SKILL.md` exists
- Check front matter has `name:` field
- Invoke with `/skill-name`

**Agent team failing?**
- MCP issue? → Use ToolSearch in prompt OR gather data first
- Context overflow? → Agents writing to files, not messages?
- Results lost? → Reading files, not transcripts?

## 📚 Full Documentation

- **System overview:** `.claude/README.md`
- **Hooks config:** `.claude/hooks/config.json`
- **Skills details:** `.claude/skills/*/SKILL.md`
- **Templates:** `.claude/templates/`
- **Project rules:** `CLAUDE.md` (top section)

## 💡 Pro Tips

1. Run `/preflight` before complex work saves 3-5 correction rounds
2. Checkpoint proactively prevents losing work to context limits
3. Data-first methodology eliminates fabrication issues entirely
4. Agent teams work best with file-based communication
5. Hooks are your safety net - let them catch mistakes

## 🎓 Learning Path

**Week 1:** Learn core skills (`/preflight`, `/checkpoint`, `/data-first`)
**Week 2:** Understand hooks (watch them work, read config)
**Week 3:** Use agent teams with template
**Week 4:** Customize hooks/skills for your patterns

---

**Quick Access:** Bookmark this file for instant reference!
