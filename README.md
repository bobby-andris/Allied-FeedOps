# Allied FeedOps

AI-powered product feed optimization system for Allied Brass, designed to maximize revenue and ad efficiency through research-backed title and description optimization.

## Quick Start

```bash
# Optimize a single product
/optimize-parent-sku AB-TOWEL-24

# Evaluate content quality
/evaluate-output
Title: Your title here
Description: Your description here

# Generate feed audit report
/generate-docs feed-audit
```

## Overview

FeedOps optimizes product content for:
- **Google Shopping / Performance Max** - Better query matching, lower CPC
- **Microsoft/Bing Shopping** - Copilot visibility, literal keyword matching
- **Shopify** - On-site conversion and organic SEO

### Key Research Findings

| Finding | Impact |
|---------|--------|
| First 70 chars determine visibility | Front-load brand + product + dimension |
| Brand-modified queries convert 3.6x higher | Include brand in titles |
| Functional modifiers drive 2-10x CVR | Add "ADA", "wall-mount", etc. |
| 500+ char descriptions: +1.4pp CVR | Expand with structured content |
| First 150 chars are previewed | Benefit-first opening hooks |

## Project Structure

```
Allied-FeedOps/
├── AGENTS.md                    # Core optimization rules and scoring rubric
├── .cursor/
│   ├── agents/
│   │   ├── data-analyst.md      # Feed analysis and performance tracking
│   │   ├── feed-copywriter.md   # Content generation (no hallucination)
│   │   └── verifier.md          # Quality validation and compliance
│   └── commands/
│       ├── optimize-parent-sku.md   # End-to-end product optimization
│       ├── evaluate-output.md       # Quality scoring against rubric
│       ├── add-mcp.md               # MCP server configuration
│       └── generate-docs.md         # Reports and exports
├── docs/
│   ├── 00-overview.md           # System introduction
│   ├── 01-workflow.md           # Step-by-step processes
│   ├── 02-mcp-plan.md           # Integration architecture
│   ├── 03-quality-rubric.md     # Scoring methodology
│   ├── 04-platform-guidelines.md # Google/Bing/Shopify specifics
│   └── [research documents]     # Source research
└── README.md
```

## Core Principles

### 1. No Hallucination
Every claim must trace to actual product data. Never invent specifications.

### 2. Quality Scoring
All content scored on 6 dimensions:
- Specificity (specific vs vague claims)
- Benefit Coverage (first 150 chars)
- Keyword Inclusion (proper placement)
- Format Adherence (character limits, structure)
- Brand Voice (premium, understated)
- Factual Accuracy (verified against source)

**Threshold**: ≥80% approved, 70-79% revise, <70% reject

### 3. Title Structure Formula
```
[Brand] + [Product Type] + [Key Dimension] + [Material] + [Finish] + [Functional Modifier]
```

Example: `Allied Brass 24-Inch Towel Bar | Solid Brass | Polished Chrome | Wall Mount`

### 4. Description Structure
```
1. Opening Hook (benefit + key spec) - first 150 chars
2. Bullet Highlights (3-5 benefit + feature combos)
3. Specifications (dimensions, materials, included items)
4. Trust Elements (warranty, installation, certifications)
```

## Commands

| Command | Description |
|---------|-------------|
| `/optimize-parent-sku` | Full optimization workflow for a product and variants |
| `/evaluate-output` | Score content against quality rubric |
| `/add-mcp` | Configure MCP server connections |
| `/generate-docs` | Create reports, audits, and exports |

## Agents

| Agent | Role |
|-------|------|
| **Data Analyst** | Audit feeds, analyze performance, identify opportunities |
| **Feed Copywriter** | Generate optimized titles/descriptions from product data |
| **Verifier** | Validate content accuracy, score quality, check compliance |

## Documentation

- [Overview](docs/00-overview.md) - System introduction and architecture
- [Workflow Guide](docs/01-workflow.md) - Step-by-step optimization processes
- [MCP Plan](docs/02-mcp-plan.md) - Integration architecture and roadmap
- [Quality Rubric](docs/03-quality-rubric.md) - Detailed scoring methodology
- [Platform Guidelines](docs/04-platform-guidelines.md) - Google/Bing/Shopify specifics

## Research Foundation

This system is built on synthesis of:
- Google Merchant Center documentation and feed specifications
- Behavioral economics and eye-tracking studies (Baymard, Nielsen Norman)
- A/B testing case studies from e-commerce
- Platform-specific algorithmic analysis

See `/docs` for full research documents.

## License

Proprietary - Allied Brass
