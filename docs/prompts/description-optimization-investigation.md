# Description Optimization Investigation

This investigation is split into **3 separate chats** to avoid context overflow.

---

## Prompt 1: Data Gathering

Run this first. Copy into a new chat:

```
## Task: Gather Search & Sales Data for Description Optimization

Allied Brass sells premium bathroom hardware ($60-$150). We need to understand what people actually search for and which finishes sell best.

### Task 1: Search Term Analysis
Use Google Ads MCP (customer ID: 6253381786).

Query shopping_performance_view to find:
1. Top search queries for shower storage products - do people search "shower basket" or "shower caddy" or "shower organizer"?
2. Which queries get clicks vs impressions only?
3. Do people search for specific finishes? ("matte black towel bar", "brass shower caddy")

### Task 2: Finish Popularity
Use Shopify Dev MCP to find:
1. Which of the 28 finishes sell best overall?
2. Which finishes have the highest conversion rates?
3. Any patterns? (Are metallics more popular than colors like Pink/Lavender?)

### Output Format
Provide findings in this format so I can use them in the next chat:

**Search Terms Findings:**
- Top queries: [list]
- Finish-specific searches: [list]
- Queries with impressions but no clicks: [list]

**Finish Popularity Findings:**
- Top 5 finishes by sales: [list]
- Top 5 finishes by conversion rate: [list]
- Patterns observed: [notes]
```

**Save the output from Prompt 1 before starting Prompt 2.**

---

## Prompt 2: Analysis

After Prompt 1 completes, run this in a new chat:

```
## Task: Analyze Current Description System

### Context from Previous Research
[PASTE YOUR FINDINGS FROM PROMPT 1 HERE]

### Your Analysis Tasks

#### Task 1: Understand the Architecture
Read @docs/prompts/description-optimization-context.md

Key things to understand:
- Master SKU vs Variant SKU (Shopify vs Google/Bing)
- Why descriptions need to be finish-neutral for Shopify
- Why finish injection exists for Google/Bing variants

#### Task 2: Analyze Current Prompt
Read @src/feedops/pipeline/prompts.py (focus on lines 134-200)

Identify:
- What rules are causing robotic output?
- What's missing that would help justify premium pricing?

#### Task 3: Analyze Finish Injection
Read @src/feedops/pipeline/finish_injection.py

Identify:
- Why does it create awkward output like "Available in Antique Brass. Antique Brass features..."?
- What needs to change?

#### Task 4: Review Current Output
Read @dashboard_data/lifestyle-eval-candidate/google-patch-BSK-275LA.json

Look at the actual description being generated. What's wrong with it?

### Output Format

**Architecture Understanding:**
- Master SKU used for: [X]
- Variant SKU used for: [X]
- Finish injection purpose: [X]

**Current Prompt Problems:**
- [list specific issues]

**Finish Injection Problems:**
- [list specific issues]

**Current Output Problems:**
- [list specific issues]
```

**Save the output from Prompt 2 before starting Prompt 3.**

---

## Prompt 3: Solution

After Prompt 2 completes, run this in a new chat:

```
## Task: Create Description Framework & Recommendations

### Context from Previous Research

**Data Findings:**
[PASTE PROMPT 1 FINDINGS]

**Analysis Findings:**
[PASTE PROMPT 2 FINDINGS]

### Background
- Allied Brass: Premium bathroom hardware ($60-$150 vs $15-$30 Amazon)
- 28 finishes available (competitive advantage)
- Master SKU = Shopify (finish-neutral, user toggles finishes)
- Variant SKU = Google/Bing (finish-specific, separate listings)

### Your Tasks

#### Task 1: Create Framework
Create 3-5 simple principles (NOT 15 rules) for descriptions that:
- Open with benefit, not specs
- Answer "why pay 4x more than Amazon?"
- Work for BOTH master (finish-neutral) and variant (finish-specific)

#### Task 2: Fix Finish Injection
Recommend:
- How master descriptions should be structured
- How variant descriptions should incorporate finish naturally
- Better finish-specific benefit content (not just "features a patina")

#### Task 3: Write Proof of Concept
For BSK-275LA (shower basket), write:
1. **Master description** (Shopify) - finish-neutral
2. **Variant description** (Google/Bing) - Antique Brass finish

Test: Would YOU click the variant over a $20 Amazon option?

#### Task 4: Provide Prompt Changes
Write the exact text to replace in @src/feedops/pipeline/prompts.py (lines 136-152).

Make it copy-paste ready.

### Deliverables
1. Framework (3-5 principles)
2. Finish injection recommendations
3. Two proof-of-concept descriptions
4. Copy-paste prompt changes for prompts.py
```

---

## Quick Reference

| Prompt | Purpose | Output |
|--------|---------|--------|
| 1 | Data gathering | Search terms + finish popularity |
| 2 | Analysis | Problems with current system |
| 3 | Solution | Framework + descriptions + prompt changes |

Each prompt should complete without hitting context limits.
