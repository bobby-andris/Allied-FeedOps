---
name: data-first
description: Gather and verify real data before any analysis or planning
---

# Data-First Methodology

Enforce a strict data-gathering phase before analysis, planning, or recommendations to prevent fabricated examples and assumptions.

## Core Principle

**Never analyze, plan, or recommend without real data.**

If you can't query the data, explicitly state assumptions and get user approval before proceeding.

## When to Use This Skill

**Trigger data-first for tasks involving:**
- "Analyze [something]"
- "Create a plan for [something]"
- "Recommend [something]"
- "Optimize [something]"
- "Which SKUs/products/items should we [action]"
- "What's the performance of [something]"
- "Audit [something]"
- "Review [something]"

**Key indicator:** Any task where you might be tempted to use example data or make assumptions.

## The Data-First Process

### Phase 1: Identify Data Requirements

Before doing ANY analysis, list:

```markdown
## Data Requirements

To complete this task, I need:

1. **[Data Source 1]**: [What specifically]
   - Table/API: [name]
   - Columns/Fields: [list]
   - Filters: [date range, conditions, etc.]
   - Expected volume: [~N rows/records]

2. **[Data Source 2]**: [What specifically]
   - Table/API: [name]
   - Columns/Fields: [list]
   - Filters: [conditions]
   - Expected volume: [~N rows/records]

3. **[etc]**

**Questions:**
- Is this data available?
- Any access restrictions I should know about?
- Should I proceed with gathering?
```

**Wait for user confirmation before querying.**

### Phase 2: Gather Data

Execute queries and save results:

```bash
# For Supabase
Use mcp__supabase__execute_sql with well-formed query

# Save results to file
Write results to /tmp/data-gathering/[descriptive-name].json

# Or for large datasets
Save summary + file path for later reference
```

**Rules:**
- ✅ Use ToolSearch to load MCP tools if needed
- ✅ Check docs/database/SCHEMA.md BEFORE writing queries
- ✅ Save raw results to disk for reference
- ✅ Handle empty results gracefully (don't fabricate)

### Phase 3: Verify Data Quality

Before proceeding to analysis, check:

```markdown
## Data Quality Check

**[Dataset 1]:**
- ✅ Query executed successfully
- ✅ Returned [N] records ([expected/unexpected])
- ✅ Date range: [start] to [end]
- ✅ Key fields present: [list]
- ⚠️ [Any anomalies or missing data]

**[Dataset 2]:**
- [Same checks]

**Issues Found:**
- [None / List any data quality issues]

**Sample Data (first 3 rows):**
```json
[show actual data sample]
```
```

### Phase 4: Present Data Summary

Show user a summary for verification:

```markdown
## Data Gathered ✅

**Summary:**
- [Dataset 1]: [N records] from [source]
- [Dataset 2]: [N records] from [source]
- Date range: [start] to [end]
- Saved to: `/tmp/data-gathering/`

**Sample findings (top 3):**
1. [Real SKU/item]: [real metrics]
2. [Real SKU/item]: [real metrics]
3. [Real SKU/item]: [real metrics]

**Data looks correct?**

Ready to proceed with analysis using this real data.
```

**Wait for user confirmation: "Yes" / "Data looks good" / etc.**

### Phase 5: Analyze Using ONLY Real Data

Now proceed with analysis, but:

- ✅ Reference actual SKUs/items from the data
- ✅ Use actual metrics (not made up numbers)
- ✅ If data is missing for something, explicitly state "No data available for X"
- ❌ NEVER invent examples that weren't in the query results
- ❌ NEVER use placeholder names like "Example-SKU-123"

## Handling Edge Cases

### Case 1: Data Doesn't Exist

```markdown
⚠️ Data Not Available

I cannot find data for: [what was requested]

Checked:
- [Source 1]: No results
- [Source 2]: No matching records

Options:
1. Adjust query parameters (different date range, filters)?
2. Proceed with assumptions (I'll clearly label them)?
3. Wait until data is available?

Which approach would you prefer?
```

### Case 2: Partial Data

```markdown
⚠️ Partial Data Available

Found data for: [what exists]
Missing data for: [what doesn't exist]

Example: Found performance data for 45 of 60 SKUs.

Options:
1. Proceed with available data only
2. Investigate why 15 SKUs are missing data
3. Fabricate nothing - work with what we have

Recommend: Option 1. Analyze the 45 SKUs and note data gaps.
```

### Case 3: User Insists on Speed

If user says "just give me a quick answer, don't worry about data":

```markdown
⚠️ Proceeding Without Data (User Approved)

User requested fast answer without data gathering.

ASSUMPTION-BASED RESPONSE (not verified):
[Your response]

⚠️ These are assumptions, not verified with real data. Treat as hypothetical.

Should I verify these recommendations with real data?
```

## Integration with Multi-Agent Workflows

When using data-first with agent teams:

### Pattern A: Orchestrator Gathers, Agents Analyze

```markdown
## Phase 1: Data Gathering (Orchestrator - Main Context)
I (orchestrator) gather all data using MCP tools:
- Query 1: [execute]
- Query 2: [execute]
- Save to: /tmp/data-gathering/

## Phase 2: Analysis (Spawn Agents)
Spawn agents with file paths:
- Agent 1: Analyze /tmp/data-gathering/dataset1.json
- Agent 2: Analyze /tmp/data-gathering/dataset2.json

Agents work with real data, cannot fabricate.
```

## Anti-Patterns to Avoid

❌ **Making up example SKUs:**
```
Bad: "For example, if we optimize CL-55 which currently has a 2% CTR..."
```

✅ **Using real data:**
```
Good: "Looking at DMF-2-2X (offer_id: shopify_us_4539975336068_31635975659652),
which currently has 1,247 impressions and a 1.8% CTR..."
```

❌ **Assuming approval rates:**
```
Bad: "If we assume an 80% approval rate..."
```

✅ **Querying approval rates:**
```
Good: "Queried approval rates: 67% approved (40 of 60 SKUs)"
```

❌ **Using hardcoded assumptions about system behavior:**
```
Bad: "The system typically generates content in 3 minutes..."
```

✅ **Measuring actual behavior:**
```
Good: "Checked last 10 generation jobs: avg time 2.8 minutes (range: 2.1-4.5 min)"
```

## Checklist Before Proceeding to Analysis

- [ ] All required data sources identified
- [ ] User approved data gathering plan
- [ ] All queries executed successfully
- [ ] Results saved to disk (if large)
- [ ] Data quality verified (no empty results, expected volume)
- [ ] User confirmed data looks correct
- [ ] No fabricated examples in my analysis plan

**Only proceed when ALL boxes checked.**

## Benefits of Data-First

1. **Trust:** User trusts your recommendations are grounded in reality
2. **Accuracy:** Decisions based on facts, not assumptions
3. **Reproducibility:** Someone else can verify your work
4. **Debugging:** If analysis is wrong, can trace back to data
5. **Credibility:** Demonstrates rigorous methodology

## Related Skills

- Use `/preflight` before starting to catch data requirements early
- Use `/checkpoint` to save gathered data for future sessions
