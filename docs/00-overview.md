# Allied FeedOps: Overview

## What is FeedOps?

FeedOps is an AI-powered product feed optimization system designed for Allied Brass. It optimizes product titles and descriptions to maximize:

1. **Algorithmic Performance** - Better matching on Google Shopping, Bing, and organic search
2. **Buyer Conversion** - Content that reduces uncertainty and triggers purchase decisions
3. **Ad Efficiency** - Lower CPC through improved Quality Scores and relevance

## The Problem We're Solving

### Current State Issues

1. **Underutilized Title Space**: Average titles use only 45 of 150 available characters, missing query matching opportunities

2. **Generic Descriptions**: Vague language like "high-quality" fails to:
   - Match specific search queries
   - Answer buyer questions
   - Differentiate from competitors

3. **Window Shopping Products**: 35 products show 32.1% of views but only 0.23% conversion - visitors look but don't buy due to insufficient information

4. **Missed Premium Positioning**: Solid brass construction (a key differentiator) often buried or unstated

## Research Foundation

This system is built on three research documents synthesizing:

- Google Merchant Center documentation and feed specifications
- Behavioral economics and eye-tracking studies
- A/B testing case studies from e-commerce
- Platform-specific algorithmic differences

### Key Research Findings

| Finding | Impact | Application |
|---------|--------|-------------|
| First 70 chars determine visibility | Clicks | Front-load brand + product + dimension |
| Brand-modified queries convert 3.6x higher | Revenue | Include brand in titles |
| Functional modifiers drive 2-10x CVR | Conversion | Add "ADA", "wall-mount", etc. |
| 500+ char descriptions: +1.4pp CVR | Conversion | Expand descriptions with structure |
| First 150 chars of description are previewed | Engagement | Benefit-first opening hooks |
| Specific claims > vague claims | Trust | "500 lb capacity" beats "very strong" |

## System Architecture

```
┌─────────────────────────────────────────────────────────────┐
│                      Allied FeedOps                          │
├─────────────────────────────────────────────────────────────┤
│                                                             │
│  ┌─────────────┐    ┌─────────────┐    ┌─────────────┐     │
│  │   Data      │───▶│    Feed     │───▶│  Verifier   │     │
│  │  Analyst    │    │ Copywriter  │    │   Agent     │     │
│  └─────────────┘    └─────────────┘    └─────────────┘     │
│        │                  │                   │             │
│        │                  │                   │             │
│        ▼                  ▼                   ▼             │
│  ┌─────────────────────────────────────────────────────┐   │
│  │                 Quality Rubric                       │   │
│  │  Specificity | Benefits | Keywords | Format | Voice │   │
│  └─────────────────────────────────────────────────────┘   │
│                           │                                 │
│                           ▼                                 │
│  ┌─────────────────────────────────────────────────────┐   │
│  │              Platform Outputs                        │   │
│  │    Google Shopping | Bing | Shopify | Performance Max│   │
│  └─────────────────────────────────────────────────────┘   │
│                                                             │
└─────────────────────────────────────────────────────────────┘
```

## Core Components

### 1. AGENTS.md
Central guidelines document containing:
- No-hallucination constraints
- Title optimization rules (70/150 character strategy)
- Description optimization rules (150/500+ character strategy)
- Quality scoring rubric (6 dimensions, 80% threshold)
- Platform-specific considerations

### 2. Agent Definitions (.cursor/agents/)
- **Data Analyst**: Audits feeds, analyzes performance, identifies opportunities
- **Feed Copywriter**: Generates optimized titles and descriptions
- **Verifier**: Validates content against rubric and source data

### 3. Commands (.cursor/commands/)
- `/optimize-parent-sku`: End-to-end optimization workflow
- `/evaluate-output`: Score content against quality rubric
- `/add-mcp`: Configure external data connections
- `/generate-docs`: Create reports and exports

### 4. Documentation (docs/)
- 00: This overview
- 01: Workflow guide (step-by-step processes)
- 02: MCP integration plan
- 03: Quality rubric deep dive
- 04: Platform-specific guidelines

## Quick Start

### Optimize a Single Product
```
/optimize-parent-sku AB-TOWEL-24
```

### Evaluate Existing Content
```
/evaluate-output
Title: Allied Brass Towel Bar 24
Description: This is a great towel bar...
```

### Generate Feed Audit
```
/generate-docs feed-audit
```

## Success Metrics

### Quality Thresholds
- **80%+**: Approved for publication
- **70-79%**: Minor revisions needed
- **<70%**: Major revision required

### Expected Impact (Based on Research)
- **CTR improvement**: 18-88% from optimized titles
- **CVR improvement**: +1.4pp from longer descriptions
- **CPC reduction**: Through improved Quality Scores
- **ROAS improvement**: From better query matching and conversion

## Core Principles

### 1. No Hallucination
Every claim must trace to actual product data. Never invent specifications.

### 2. Algorithm + Psychology
Content must satisfy both machine matching requirements AND human decision-making heuristics.

### 3. Specific > Generic
"Solid brass, 500 lb capacity" always beats "premium quality, very strong."

### 4. Benefits Before Features
Lead with what the product does for the buyer, then prove it with specifications.

### 5. Measurable Quality
Every output scored against objective rubric before publication.

## Next Steps

1. **Read the Workflow Guide** (docs/01-workflow.md) for step-by-step processes
2. **Understand the Rubric** (docs/03-quality-rubric.md) for scoring details
3. **Plan MCP Integration** (docs/02-mcp-plan.md) for data source connections
4. **Review Platform Guidelines** (docs/04-platform-guidelines.md) for channel-specific rules
