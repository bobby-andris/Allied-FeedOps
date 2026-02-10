# Context Budget Monitor System

**Problem:** Context overflow kills sessions without warning. Users don't realize they're at risk until it's too late.

**Solution:** Proactive monitoring with automatic warnings at threshold points.

## How It Works

Claude monitors conversation length and issues warnings at:
- 🟢 **50% (100K tokens)** - "Context usage: Moderate. Long session ahead? Consider planning checkpoints."
- 🟡 **60% (120K tokens)** - "Context usage: High. Recommend checkpoint soon if work is complex."
- 🟠 **70% (140K tokens)** - "Context usage: Very High. **Create checkpoint now** to avoid losing work."
- 🔴 **80% (160K tokens)** - "Context usage: Critical. **Checkpoint immediately** or finish current task and end session."

## Implementation

Since Claude Code doesn't expose context usage directly to hooks, this is implemented as a **behavior pattern** rather than automated hook.

### Pattern: Proactive Self-Monitoring

**Claude should:**

1. **Track message count** as proxy for context usage:
   - ~10 messages ≈ 5-10K tokens
   - ~50 messages ≈ 50K tokens (25%)
   - ~100 messages ≈ 100K tokens (50%)
   - ~150+ messages ≈ 120K+ tokens (60%+)

2. **Issue warnings proactively:**

At ~50 message exchanges:
```
💡 Context Check: ~50% usage estimated.

If this will be a long session (multi-agent work, complex research, many files):
- Consider planning checkpoints at phase boundaries
- Use /checkpoint if approaching 60-70%

Continuing with current work.
```

At ~75 message exchanges:
```
⚠️ Context Check: ~60-65% usage estimated.

Recommend:
- Use /checkpoint now to save progress
- OR wrap up current task and plan continuation

Should I checkpoint now, or continue?
```

At ~100 message exchanges:
```
🔴 Context Critical: ~70-75% usage estimated.

**Action required:**
1. **Checkpoint now** - Use /checkpoint to save all progress
2. **OR finish current task** - Complete what you're working on
3. **Then end session** - Start fresh next time

I'll create checkpoint after your response.
```

### Pattern: Session Type Awareness

**Different session types consume context differently:**

**High-burn sessions (checkpoint early):**
- Multi-agent orchestration (agents generate lots of output)
- Deep codebase exploration (reading many files)
- Research + synthesis (gathering + analyzing data)
- Long debugging sessions (stack traces, error outputs)

**Low-burn sessions (checkpoint normally):**
- Simple bug fixes
- Documentation updates
- Configuration changes
- Code review

**Claude should estimate burn rate and adjust warnings:**

```markdown
Context estimate: ~50 messages exchanged

Session type detected: Multi-agent orchestration (high-burn)

Adjusted recommendation: Checkpoint at ~70 messages (vs normal 100)

Current: ~50 messages
Checkpoint threshold: ~70 messages (20 messages away)

I'll remind you when we approach checkpoint threshold.
```

## User-Facing Warnings

### Checkpoin Warning Format

```markdown
⚠️ Context: [N]% estimated

Current: ~[X] messages exchanged
Threshold: [50% / 60% / 70% / 80%]

Recommendation: [action]

Proceed or checkpoint?
```

### Automatic Checkpoint Trigger

At 80% estimated usage:

```markdown
🔴 Context Critical: Automatic checkpoint triggered

I'm creating a checkpoint now to preserve all work:

[Execute /checkpoint skill]

✅ Checkpoint saved: .claude/checkpoints/[file]

Recommend ending this session and resuming fresh:
"Read .claude/checkpoints/[file] and continue from [phase]"

Continue in this session (risky) or end here?
```

## CLAUDE.md Integration

Add to CLAUDE.md "Critical Behavioral Rules":

```markdown
### Context Monitoring (Self-Monitoring)

**Track message count as context proxy:**
- ~50 messages: 50% usage - Plan checkpoints if long session ahead
- ~75 messages: 60% usage - Recommend checkpoint
- ~100 messages: 70% usage - Checkpoint required
- ~120+ messages: 80%+ usage - Automatic checkpoint + end session

**High-burn sessions** (multi-agent, deep research):
- Adjust thresholds down by 20-30 messages
- Checkpoint earlier and more frequently

**Proactive warnings:**
- Issue context check at thresholds
- Offer checkpoint option
- At 80%: Auto-checkpoint and recommend ending session
```

## Example Flow

**Normal Session (Low-Burn):**

```
[Messages 1-49: Work proceeds normally]

[Message 50]:
Claude: "💡 Context check: ~50% estimated. Continuing with work..."

[Messages 51-74: Work continues]

[Message 75]:
Claude: "⚠️ Context: ~60-65% estimated. Recommend checkpoint soon. Continue or checkpoint now?"

User: "Continue"

[Messages 76-99: Work continues]

[Message 100]:
Claude: "🔴 Context: ~70% estimated. Creating checkpoint now..."
[Executes /checkpoint]
Claude: "Recommend ending session. Resume with: Read .claude/checkpoints/[file]"
```

**High-Burn Session (Multi-Agent):**

```
[Messages 1-30: Normal work]

[Message 31]: User: "Spawn agent team to analyze performance"

Claude: "Context note: Multi-agent work ahead (high-burn session).
Will monitor closely and suggest checkpoint at ~50 messages (vs normal 75)."

[Messages 32-49: Agent coordination]

[Message 50]:
Claude: "⚠️ Context: ~50-55% estimated (high-burn session).
Agents generated significant output.
Recommend checkpoint now before context becomes critical.
Checkpoint?"

User: "Yes"

Claude: [Executes /checkpoint]
```

## Benefits

1. **Prevents loss of work** - Checkpoint before overflow, not after
2. **User awareness** - Know when session is getting long
3. **Adaptive** - Adjusts based on session type (high/low burn)
4. **Automatic safety** - At 80%, checkpoint is forced
5. **Transparent** - User always knows context state

## Limitations

- **Estimated, not precise** - Based on message count, not actual token usage
- **Can't prevent all overflows** - Very large file reads can spike usage
- **Relies on Claude discipline** - Must actually issue warnings

## Testing

**Simulate high-context session:**

```
User: "Let's do a long research session with agents"
[Watch for 50% warning after ~50 messages]
[Watch for 60% warning after ~75 messages]
[Verify checkpoint suggestion]
```

## Future Enhancement

If Claude Code exposes actual context usage via API/variable:
- Replace message-count estimation with precise token measurement
- Dynamic thresholds based on remaining capacity
- Trend analysis (tokens per message, burn rate)
