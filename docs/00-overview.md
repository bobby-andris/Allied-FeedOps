# Allied FeedOps: Overview

## Canonical Generation Documentation

If you are working on generation behavior, prompts, runtime parity, persistence, or dashboard readback, start here before reading the rest of this overview:

1. `AGENTS.md`
2. `docs/architecture/generation-runtime-truth.md`
3. `docs/architecture/generation-core-task-model.md`
4. `docs/architecture/generation-prompt-lineage-contract.md`
5. `docs/architecture/generation-pipeline-routing-reference.md`
6. `docs/experiments/2026-02-28-production-divergence-closure/report.md`
7. `docs/development/generation-change-checklist.md`

Those files are the operational truth for generation work. Older investigation docs may still exist for forensics, but they are not the default source of truth unless one of the documents above links to them explicitly.

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
- canonical reading order for generation work
- certification requirements across source, container, Cloud Run, Supabase, and dashboard
- prompt lineage invariants
- dashboard runtime routing invariants

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
- `architecture/generation-runtime-truth.md`: layer-by-layer runtime truth
- `architecture/generation-core-task-model.md`: task graph contract
- `architecture/generation-prompt-lineage-contract.md`: prompt persistence contract
- `architecture/generation-pipeline-routing-reference.md`: deep route and persistence reference
- `development/generation-change-checklist.md`: required generation PR checklist
- `operations/deploy-and-certify-generation.md`: deploy and live-proof playbook

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

1. **Read the Workflow Guide** (`docs/01-workflow.md`) for repo-level execution flow
2. **Read Runtime Truth** (`docs/architecture/generation-runtime-truth.md`) before any generation change
3. **Read the Task Model** (`docs/architecture/generation-core-task-model.md`) before changing routing or prompts
4. **Use the Generation Checklist** (`docs/development/generation-change-checklist.md`) before opening a PR
