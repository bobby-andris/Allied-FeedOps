---
description: Generate Allied FeedOps rules/commands/agents/docs from the attached research docs.
---

Use the repository docs as the source of truth for optimization rules.

Tasks:
1) Read the three research docs in /mnt/data that describe title/description optimization.
2) Create AGENTS.md with:
   - no-hallucination constraints
   - title rules: first ~70 chars prioritized; use up to 150 for matching coverage
   - description rules: first ~150 chars benefit-first; structured highlights; avoid fluff
   - a scoring rubric aligned to the research
3) Create .cursor/agents: data-analyst, feed-copywriter, verifier
4) Create .cursor/commands: /optimize-parent-sku, /evaluate-output, /add-mcp, /generate-docs
5) Create docs/00–04 runbook files describing the workflow and MCP plan.

Output must be commit-ready and grounded in the research.
