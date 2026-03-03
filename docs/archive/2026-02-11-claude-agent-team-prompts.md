# Claude Code Agent Team Prompts: Feed Optimization That Drives Revenue

These prompts are for Claude Code Agent Teams. The intent is NOT to “rank for one query” or “write nicer descriptions.”

## Core Problem (What We’re Actually Solving)
We want to optimize the Shopping feed so that:
- Our products become eligible for, and are served on, the RIGHT searches (right user intent, right context, right category).
- When served, the ad copy + landing experience increases the likelihood the shopper chooses Allied Brass over competitors.

This starts with the feed because the feed is the seed input to Shopping/PMax relevance and selection.

## What “Better” Means (Practical, Measurable)
Because we can’t directly observe Google’s internal relevance model, we define measurable proxies and validate them:
- **Eligibility coverage**: titles contain high-intent query anchors and critical attributes where they matter (first 30/70/150 chars).
- **Intent alignment**: copy emphasizes attributes that match purchase intent (size, type, mount, category-specific differentiators) without stuffing.
- **Trust**: coherent, accurate, non-weird descriptions; no unverifiable claims; no policy-risk phrases.
- **Differentiation**: reduced overlap vs legacy and marketplace-vendor text (less auction collision, more distinct relevance signals).
- **Traceability**: we can prove which signals influenced each output (prompt hash, model metadata, source fields).

## Non-Negotiables (Guardrails)
- Python is runtime single source of truth for prompt construction (`src/feedops/pipeline/prompts.py`).
- No hallucinated product claims. If unknown, omit.
- Google/Bing **base descriptions** must be finish-agnostic (no hardcoded finish names).
- Never include finish-count marketing like “available in 28 finishes” in customer-facing titles/descriptions.
- `{FINISH_SENTENCE}` injection must be correct:
  - Present exactly once when finish sentence data is valid/complete for that SKU/platform output.
  - Absent when finish sentences are unavailable/invalid.
- Evidence must be concrete: SKU, route touched, stored `prompt_hash` + model metadata fields, and the DB fields that prove inputs.

## How To Run These In Claude Code (Agent Teams)
- Run each prompt in a separate Claude Code chat to avoid context compaction.
- Require teammates to provide file-level pointers + runnable commands, not just narratives.
- End every run: shut down teammates and clean up the team.

## Shared Verification Commands (Run At End Of Each Prompt)
- `.venv/bin/pytest -q`
- `RUN_SUPABASE_CANARY=1 bash scripts/verify_phase_0.sh`

---

## Prompt 1: Are We Solving The Right Problem? (Objective Function + Strategy Audit)
```text
You are the team lead in Claude Code. Create an agent team to audit whether /Users/bobby/Documents/GitHub/Allied-FeedOps is truly solving the core revenue problem: serving the right Shopping ads at the right time to the right intent, and improving purchase likelihood.

Scope:
- Do not optimize for a single query. Create a general framework that works across categories (grab bars, towel bars, etc.).
- Use examples only to validate the framework.

Team roles:
- Teammate A (Intent + Eligibility Model):
  - Define an intent taxonomy for Shopping queries across categories:
    - high-intent (size/type/finish/material + purchase action implied)
    - mid-intent (style-led / “decorative” / “designer”)
    - safety-led (ADA/grab bar use cases)
  - Define what the feed must do at each intent stage:
    - eligibility anchors (what terms must appear to be considered)
    - conversion/trust signals (what reduces uncertainty)
- Teammate B (Current System Audit):
  - Inspect current pipeline behavior and scoring to determine what it is actually optimizing for.
  - Identify whether we have explicit “objective function” equivalents (rules/tests/score gates) that map to:
    - eligibility coverage
    - intent alignment
    - differentiation
    - policy/trust
  - If we don’t: propose the minimum set of enforceable gates (tests) that encode the objective.
- Teammate C (Evidence Run):
  - Pick 3 real SKUs from different category classes:
    1) high-history SKU (lots of query signals)
    2) cold-start SKU (little/no query history)
    3) variant-heavy SKU (finish sentences relevant)
  - Generate content and score outputs against the intent model, with concrete evidence:
    - output text per platform
    - prompt_hash + model metadata
    - source fields that justify key claims and keyword/intent choices

Deliverables:
1) docs/plans/YYYY-MM-DD-objective-function-audit.md:
   - intent taxonomy
   - what “right time/right intent” means operationally
   - gaps between desired objective and current implementation
   - ranked fixes by expected impact on Shopping visibility and Shopify revenue
2) If missing: add minimal objective gates (tests) that make future drift impossible.

Verification:
- .venv/bin/pytest -q
- RUN_SUPABASE_CANARY=1 bash scripts/verify_phase_0.sh

End by shutting down teammates and cleaning up the team.
```

---

## Prompt 2: Keyword/Signal Reality Check (Data -> Prompt -> Output), Plus “Is Our Data Enough?”
```text
You are the team lead in Claude Code. Create an agent team to answer with evidence:
Do keyword/search/competitive signals actually flow into prompt inputs and measurably change generated titles/descriptions in /Users/bobby/Documents/GitHub/Allied-FeedOps, and is the captured data sufficient/correct to achieve the business goal?

Why this matters:
If the system is not truly data-driven, it will generate generic, overlapping text that fails to improve Shopping eligibility or purchase likelihood.

Safety (recommended):
Do this work on a new git branch/worktree so tests and wiring changes cannot break the current dashboard.
Example:
  git worktree add .worktrees/signal-audit -b signal-audit

Hard constraints:
- Python remains single source of truth.
- No hallucinated data. Use only available DB/runtime sources.
- Do not redesign architecture. Add the smallest seams/tests necessary to prove behavior.

Team roles:
- Teammate A (Database + Source Inventory, Sufficiency Verdict):
  - Use docs/database/SCHEMA.md and code to inventory what signal sources exist TODAY and how they’re populated.
  - For each source, answer:
    - coverage (% of SKUs/categories it covers)
    - freshness/TTL
    - join keys (master_sku/variant identifiers)
    - bias/limitations (for example: query history skewed by current feed)
  - Minimum sources to audit:
    - Google Ads search queries (search_queries, search_queries_by_master_sku)
    - Keyword Planner cache/enrichment (keyword_metrics, search_query_sync_jobs.enrich_with_keyword_planner)
    - performance/post-publish tracking (performance_snapshots, search_query_snapshots, publish_events if present)
    - competitor intelligence (competitor_listings, competitor_patterns, competitor_scrape_jobs)
    - Merchant Center metadata/health (where Merchant Center items/issues/status are stored/cached and how they are used)
  - Produce a “data enough / not enough” verdict for:
    - high-history SKUs (easy mode)
    - cold-start SKUs (little/no query history)
  - Explicitly list what’s missing for cold start (discovery signals, category query clusters, competitive context).

- Teammate B (Prompt Wiring + Causality Proof):
  - Trace the Python canonical prompt construction and all callers.
  - Produce a map:
      input tables/fields -> prompt sections -> output fields -> scoring/gates
  - Identify any drift where dashboard/local prompts bypass Python SOT.
  - Prove causality on one real SKU:
    - run generation with controlled signal inputs at the smallest seam (stub/mock)
    - demonstrate expected changes:
      - improved eligibility anchors in the first 70 chars (no stuffing)
      - better intent alignment
      - still policy compliant and factually grounded

- Teammate C (External Signals: Should We Add Them? How Would We Do It Safely?):
  - Evaluate whether adding these sources is necessary to solve the core problem, especially for cold-start SKUs:
    1) Google Ads API Keyword Planner (GenerateKeywordIdeas + historical metrics)
       - Confirm what is already implemented vs only documented.
       - Propose minimal integration:
         - how to seed ideas from product/category attributes
         - caching/TTL strategy (reuse keyword_metrics where possible)
         - quota/latency management (batch jobs, job tables)
       - Define exactly how Keyword Planner signals should influence generation:
         - selecting priority query anchors (not stuffing)
         - cold-start fallback when query history is missing
    2) Merchant API competitive/market metrics
       - DO NOT assume availability. Determine what competitive metrics are actually accessible for this merchant account.
       - If available: propose storage + usage strictly for prioritization/selection/monitoring (NOT as claims in copy).
       - If not available or too costly: propose how to extend competitor_scrape_jobs + competitor_patterns as the competitive signal layer.
  - Provide a ranked recommendation:
    - implement now vs later
    - expected impact on Shopping visibility + Shopify revenue
    - engineering cost and operational risk (auth, quotas, data quality)

Deliverables:
1) docs/plans/YYYY-MM-DD-signal-reality-and-sufficiency.md
   - DB/source inventory + sufficiency verdict
   - external signals assessment (Keyword Planner, Merchant competitive metrics): implement now/later and how
   - wiring map (inputs -> prompt -> outputs -> gates)
   - causality proof (tests/harness) that signals change outputs in the right direction
2) Minimal regression tests that prevent:
   - signals silently dropped
   - cold-start SKUs degrading into generic copy
   - policy regressions (finish-count marketing, base finish mention, missing/extra {FINISH_SENTENCE})

Verification:
- .venv/bin/pytest -q
- RUN_SUPABASE_CANARY=1 bash scripts/verify_phase_0.sh

End by shutting down teammates and cleaning up the team.
```

---

## Prompt 3: Intent-First Feed Copy Rules (Generalize Across Categories, Avoid Overfitting)
```text
You are the team lead in Claude Code. Create an agent team to implement an intent-first, category-general framework for titles/descriptions in /Users/bobby/Documents/GitHub/Allied-FeedOps.

Goal:
Make the system reliably produce copy that increases Shopping eligibility for profitable intent clusters and improves purchase likelihood, across categories (not just one query).

Constraints:
- Python SOT stays authoritative; no dashboard-local prompt drift.
- No hallucinations; preserve policy and {FINISH_SENTENCE} rules.
- Do not add “competitive claims” into copy; competitive signals only influence prioritization and keyword anchor selection.

Team roles:
- Teammate A (Category Templates That Aren’t Generic):
  - Define category families (grab bars vs towel bars vs mirrors vs accessories).
  - For each family, define:
    - the top decision-driving attributes (type, size, mount, compliance, etc.)
    - the “must-win” eligibility anchors
    - safe synonym distribution patterns (no parenthetical stuffing)
  - Define cold-start fallback logic when query data is missing.
- Teammate B (Placement + Anti-Stuffing):
  - Encode deterministic placement rules (first 30/70/150) and forbid “stuffing-like” patterns.
  - Ensure titles stay readable and stable for Shopify while maximizing Shopping eligibility.
- Teammate C (Proof + Regression):
  - Validate across at least 5 SKUs spanning 3 category families (include at least one cold-start and one variant-heavy SKU).
  - Produce scorecards: eligibility anchors, intent alignment, trust, uniqueness, policy compliance, traceability.
  - Add tests to keep the rules stable.

Deliverables:
1) docs/plans/YYYY-MM-DD-intent-first-framework.md
2) Minimal code + tests implementing the framework within Python SOT
3) Evidence bundle (SKU, outputs, prompt_hash/model metadata, input fields used)

Verification:
- .venv/bin/pytest -q
- RUN_SUPABASE_CANARY=1 bash scripts/verify_phase_0.sh

Shut down teammates and clean up the team.
```

---

## Prompt 4: Differentiation Engine (Reduce Vendor Overlap Without Losing Relevance)
```text
You are the team lead in Claude Code. Create an agent team to reduce overlap with legacy and marketplace-vendor copy while improving relevance/intent alignment in /Users/bobby/Documents/GitHub/Allied-FeedOps.

Why:
If our text is the same as vendor text, we lose differentiation and may increase auction collisions.

Constraints:
- Python SOT, no hallucinations, preserve policy, base descriptions finish-agnostic, {FINISH_SENTENCE} correct.

Team roles:
- Teammate A (Overlap Measurement):
  - Implement explainable overlap scoring for title and description vs:
    - legacy store copy
    - marketplace/vendor copy (if stored)
    - competitor_listings (when available)
  - Provide reason codes and thresholds per field/category.
- Teammate B (Safe Uniqueness Levers):
  - Define allowed transformations:
    - reorder attributes toward intent
    - clarify size/fit info
    - distribute synonyms across sentences naturally
  - Define forbidden transformations:
    - fluff/superlatives
    - unverified claims
    - finish-count marketing
    - stuffing patterns
- Teammate C (Gates + Proof):
  - Add tests/gates that enforce overlap ceilings + policy correctness.
  - Prove before/after across multiple category families.

Deliverables:
1) docs/plans/YYYY-MM-DD-differentiation-engine.md
2) Overlap evaluator + tests/gates
3) Evidence that relevance/intent alignment improves while overlap decreases

Verification:
- .venv/bin/pytest -q
- RUN_SUPABASE_CANARY=1 bash scripts/verify_phase_0.sh

Shut down teammates and clean up the team.
```

---

## Prompt 5: Measurement Loop (Prove Impact, Not Vibes)
```text
You are the team lead in Claude Code. Create an agent team to build a measurement loop that proves feed text improvements are likely to increase revenue in /Users/bobby/Documents/GitHub/Allied-FeedOps.

Principle:
If we can’t measure, we can’t iterate safely. This system must produce evidence that changes improve eligibility + CTR/CVR proxies.

Team roles:
- Teammate A (Metrics + Proxies):
  - Define measurable proxies tied to the core objective:
    - eligibility anchors coverage
    - intent match score
    - uniqueness/overlap score
    - policy risk score
    - factual grounding score
  - Define which require external data vs internal only.
- Teammate B (Harness + Reports):
  - Implement a harness that compares:
    - legacy vs generated
    - before vs after publish (if snapshots exist)
  - Emit reason codes and a single go/no-go.
- Teammate C (Field Ops Proof):
  - Pick a small SKU set, run the harness, and produce a report that’s actionable for business decisions.

Deliverables:
1) docs/plans/YYYY-MM-DD-measurement-loop.md
2) Harness implementation + tests
3) A single report artifact that a business owner can read in <5 minutes

Verification:
- .venv/bin/pytest -q
- RUN_SUPABASE_CANARY=1 bash scripts/verify_phase_0.sh

Shut down teammates and clean up the team.
```

---

## Prompt 6 (Optional): Phase 2 Design (Shopping Ads Funnel + Negatives), Design-Only
```text
You are the team lead in Claude Code. Create an agent team to design (not implement) Phase 2: a Google Ads Shopping intent funnel + negative keyword pipeline, built on top of the feed optimization engine in /Users/bobby/Documents/GitHub/Allied-FeedOps.

Deliverables:
1) docs/plans/YYYY-MM-DD-phase2-shopping-funnel-design.md:
   - intent stage definitions
   - query classification approach
   - negative keyword governance to avoid footguns
   - how feed changes and campaign structure reinforce each other
2) A prioritized backlog with acceptance tests and measurement plan

Do not change Phase 1 architecture; this is design-only.
Shut down teammates and clean up the team.
```
