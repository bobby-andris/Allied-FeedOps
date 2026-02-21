# Phase 19: Measurement Infrastructure - Context

**Gathered:** 2026-02-20
**Status:** Ready for planning

<domain>
## Phase Boundary

Add minimum instrumentation to know when fixes are working: feature flag state at generation time, GMC disapproval visibility, prompt version lineage, and bottleneck classification. This phase builds the measurement layer — it does not fix generation paths or apply optimizations (that's Phase 20).

</domain>

<decisions>
## Implementation Decisions

### GMC Disapproval Surfacing
- **Dedicated monitoring page** under /monitoring for full disapproval list + **inline badges** on existing pages (SKU review, overview, performance)
- Inline badges show **icon + count** (e.g., warning icon with number of issues per SKU)
- **Scheduled sync** — daily/periodic job stores GMC status in Supabase, enabling fast page loads and trend tracking over time
- Issue detail level: Claude's discretion based on what Merchant API provides

### Bottleneck Classifier Output
- **Both** color-coded tags inline on SKU tables + dedicated diagnostic view grouping SKUs by bottleneck type
- Five categories: code-path gap, auction/bid, query relevance, coverage gap, propagation failure
- **Manual override** supported — user can change classification with a note when they know something the system doesn't
- **Auto-run after publish** + manual re-run button for reclassifying existing SKUs
- Evidence display: Claude's discretion based on existing dashboard UI patterns

### Flag & Prompt Lineage Visibility
- UI visibility level: Claude's discretion (likely collapsible technical details to avoid clutter)
- **Opt-in side-by-side comparison** — ability to compare two generations by prompt version, but NOT default view; user must explicitly request it
- **Both hash + named versions** — auto-generated hash for accuracy, optional human-readable alias (e.g., v2.1) for important versions
- Filtering by flag state supports **both A/B analysis** (segment performance by flag ON/OFF) and **debugging** (find generations with specific flag combos)

### Data Capture Granularity
- Full prompt text vs hash-only: Claude's discretion (assess storage vs debugging value)
- Raw model response storage: Claude's discretion (assess debugging value vs storage)
- Retention policy: Claude's discretion (expected volume ~2,784 SKUs with occasional regeneration — likely keep everything)
- **Track generation costs** — record tokens used, model name, and latency per generation for cost analysis and model comparison

### Claude's Discretion
- GMC issue detail level (based on Merchant API data available)
- Bottleneck evidence display format (expandable row vs detail panel — match existing patterns)
- Flag/prompt lineage UI placement (likely collapsible section)
- Full prompt text vs hash-only storage
- Raw model response storage
- Data retention policy

</decisions>

<specifics>
## Specific Ideas

- Side-by-side prompt comparison should be opt-in, not default — "don't clutter the page unless the user truly wants to be looking at side by side"
- Bottleneck tags should be color-coded by category for quick scanning
- GMC sync should be scheduled (not on-demand) to support trend tracking

</specifics>

<deferred>
## Deferred Ideas

None — discussion stayed within phase scope

</deferred>

---

*Phase: 19-measurement-infrastructure*
*Context gathered: 2026-02-20*
