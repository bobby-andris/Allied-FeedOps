# Phase 33: Tier Scoring Engine - Context

**Gathered:** 2026-02-25
**Status:** Ready for planning

<domain>
## Phase Boundary

Replace hardcoded ROAS tier thresholds (3.6/3.1/2.6) with dynamically computed, distribution-based scoring that adapts to actual performance data. Users see tier performance distributions, per-term placement scores with confidence, and auto-adjusting boundaries — all organized by custom_label_0 product group. This phase computes and displays scores; taking action on misplacements (executing tier movements) is Phase 34.

</domain>

<decisions>
## Implementation Decisions

### Page Entry Point & Hero
- Lead with actionable callouts, not raw statistics: "23 terms may be in the wrong tier — $2.4K/mo potential impact"
- Hero section communicates what needs attention and quantifies the revenue opportunity (increased sales + reduced wasted ad spend)
- The overarching goal is optimizing ad spend to drive more sales — every insight should connect back to revenue impact

### Information Hierarchy (Drill-Down)
- Level 1: All custom_label_0 groups overview — show all four metrics (ROAS, CVR, CPC, CTR) per group in compact format, with all three tiers visible per group
- Level 2: Drill into one custom_label_0 group — see tier-level distributions and misplaced terms within that group
- Level 3: Drill into one tier within a group — see individual term scores and placements
- Level 4: Individual term detail — full scoring breakdown with verdict + scorecard
- At each drill-down level, guide the business user on where to look next and why (Claude decides the guidance pattern — inline callouts vs sidebar vs hybrid)
- Groups sorted by attention needed: prioritize groups where action could increase sales or reduce wasted ad spend

### Statistics & Language
- Statistics are always visible (not hidden behind toggles) — transparency builds decision-making confidence
- Every statistical measure must be explained in plain English tied to the data being shown (e.g., "Median ROAS: 3.1x — half of your HIGH tier terms earn more than 3.1x return on ad spend")
- No jargon without explanation — the audience includes data scientists AND business stakeholders who need to make decisions

### Scoring Transparency (Per-Term)
- Combined approach: lead with a plain English verdict ("This term is a strong fit for HIGH tier because..."), then show a visual scorecard with individual factors (ROAS position, CVR position, consistency, data volume)
- Each factor in the scorecard is clickable/expandable to reveal the underlying math
- Show peer context: "This term's 5.2x ROAS ranks in the top 15% of Towel Bar terms" — contextualizes performance against the group

### Confidence Scores
- Always-visible confidence badge on every term (High/Medium/Low confidence), color-coded
- Confidence combines: data volume, metric consistency, statistical significance, NLP intent alignment
- Badge is always present — not just when confidence is low

### Misplaced Term Flagging
- Inline arrow indicators on every term list view showing current → recommended tier with potential impact
- PLUS a dedicated "Misplaced Terms" section that aggregates all mismatch terms as an action queue sorted by dollar impact
- Both views coexist — inline arrows for discovery while browsing, dedicated section for focused work

### Degraded States & Sparse Data
- Always show which fallback level is being used for scoring (per-group data, category-wide averages, or global defaults) — full transparency on data source
- Groups with zero scored terms: show with "No data yet" state (don't hide) — prevents confusion about missing groups
- Claude's Discretion: exact visual treatment of sparse tiers (grayed-out vs collapsed), and threshold for "new term needs more data" vs "score with low confidence"

### Boundary Auto-Adjustment
- Cap maximum boundary shift per recalculation to prevent wild swings from data anomalies — show warning if uncapped shift would have been larger
- Manual override allowed on ANY boundary or scoring decision — transparent tracking shows "Manual override active — data suggests 3.8x but pinned at 4.0x"
- Philosophy: the system recommends, the user decides. It's their company, we guide and assist
- Claude's Discretion: recalculation frequency (daily/weekly/on-demand), boundary change communication pattern (change log vs before/after diff)

### Claude's Discretion
- Visualization approach for distributions (not box plots or stat cards — something accessible that becomes more granular on demand)
- Guided drill-down pattern (inline callouts, sidebar, or hybrid)
- Sparse tier visual treatment and new-term scoring threshold
- Recalculation frequency and boundary change display pattern
- Exact layout and component structure

</decisions>

<specifics>
## Specific Ideas

- "The graphs should be easily understood, and they can become more granular, but also they need to be paired with explanations about what they mean"
- "Truly show us insights that help drive the people who need to make business decisions, make those decisions with as much data as possible"
- "Being confident in making business decisions requires showing why this confidence can be instilled. And to do that, we need to have statistics. But if they are presented, they need to be explained and tied into the data"
- "At the end of the day, it's their company, they know the most, and we're just trying to guide them and assist them the best we can"
- The audience is both data scientists AND business stakeholders (like Bobby's dad) — neither should feel lost or overwhelmed
- Revenue optimization is the north star: increase sales + reduce wasted ad spend on Google Ads → conversions on Shopify

</specifics>

<deferred>
## Deferred Ideas

None — discussion stayed within phase scope

</deferred>

---

*Phase: 33-tier-scoring-engine*
*Context gathered: 2026-02-25*
