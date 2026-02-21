# Phase 25: Evaluate & Iterate - Context

**Gathered:** 2026-02-21
**Status:** Ready for planning

<domain>
## Phase Boundary

Validate the Phase 24 prompt architecture against reality. Regenerate 10 representative SKUs, compare old vs. new content through blind human evaluation, diagnose and fix systemic prompt issues where content falls short, and publish the highest-scoring SKU to verify the end-to-end pipeline. This phase proves the new prompt architecture works at quality before broader rollout.

</domain>

<decisions>
## Implementation Decisions

### SKU Selection
- Claude selects 10 representative SKUs optimizing for category diversity, revenue coverage, and evaluation signal
- Must span at least 4 different product categories (success criteria requirement)
- Include at least one multi-SKU product (e.g., DMF-2 family) to validate hybrid generation also benefits from new prompts
- Mix of gold-standard-adjacent and non-gold categories for signal on both exemplar impact and generalization — Claude's discretion on exact ratio

### Evaluation Method
- **Blind A/B test format**: Old and new descriptions shown without labels (Description A / Description B), evaluator picks the better one
- **Separate scoring for title and description**: Title quality and description quality evaluated independently, not as a bundle
- **Comparison document**: Markdown file in the repo — quick to generate, reviewable in any editor
- **Scoring approach**: Claude designs a lightweight scoring method that balances quantitative signal with evaluator time — at minimum: winner pick + differentiation check ("Could you tell this is Allied Brass?")

### Iteration Approach
- **Failures reveal systemic issues, not edge cases**: When a SKU fails, analyze WHY at a fundamental level — the disconnect between desired output and instructions given
- **Fix instructions holistically**: Never patch prompts for one SKU. Fix the instruction set so it works across all 2,800 SKUs with confidence. Remove harmful instructions; preserve beneficial ones.
- **Written root cause analysis before any prompt changes**: Document what went wrong and why before proposing changes — prevents whack-a-mole fixes
- **After any prompt change, regenerate and re-evaluate all 10**: Ensures fixes don't regress SKUs that were already passing
- **Iteration depth**: Claude determines reasonable rounds based on diminishing returns

### Test Batch Publishing
- **Dashboard approval workflow is the real gate**: Content must be approved through the dashboard, not auto-published
- **Publish at most 1 SKU**: The highest-scoring SKU gets published to verify the full end-to-end pipeline works (generation → approval → Google Sheets supplemental feed)
- **Performance data collection starts immediately**: Dashboard already captures performance snapshots post-publish
- **Hard measurement window**: Claude's discretion, but secondary to evaluation pass

### Completion Gate
- Evaluation passing the success criteria (8/10 blind test wins, avg 85%+ quality score) IS the definition of "v1.3a done"
- No requirement to wait for live CTR/CVR data before declaring v1.3a complete
- Broader rollout is the next milestone's concern

### Claude's Discretion
- Exact SKU selection methodology and final list
- Scoring rubric design (beyond minimum requirements above)
- Number of iteration rounds before diminishing returns
- Evaluation artifact location (phase directory vs docs/)
- Measurement window for the one published test SKU

</decisions>

<specifics>
## Specific Ideas

- "We should not be trying to fix our prompt for one failing SKU. Instead, we need to analyze why this prompt is failing at a fundamental level. It means we have a disconnect between what we want the LLM to generate and the instructions we are giving it."
- Root cause analysis is mandatory documentation — not optional conversation
- The blind test is the honest signal: if the evaluator can't tell which is new without labels, the improvement isn't real

</specifics>

<deferred>
## Deferred Ideas

None — discussion stayed within phase scope

</deferred>

---

*Phase: 25-evaluate-iterate*
*Context gathered: 2026-02-21*
