# Phase 9: SKU Review Revamp - Context

**Gathered:** 2026-02-18
**Status:** Ready for planning

<domain>
## Phase Boundary

Transform the SKU review page from a vertically-scrolling per-SKU card layout into a compact filterable list with:
- A stats summary bar showing approval counts per platform at the top
- Compact rows showing per-platform status badges at a glance (no scrolling required per SKU)
- Filter controls for status and platform
- Inline expand/collapse for SKU detail without leaving the list

Platform coverage is Google, Bing, AND Shopify (three platforms, not two).

Creating new content, triggering regeneration, and image generation are out of scope — this phase is the review/approval list UX only.

</domain>

<decisions>
## Implementation Decisions

### Compact list row design
- Each row shows: master SKU name + truncated product title + small image thumbnail + status badges for Google, Bing, and Shopify
- Three platforms: Google, Bing, Shopify — all three must have status badges per row
- Exact badge style (colored pills, icon-only, abbreviated text) is Claude's discretion — optimize for scannability
- Active working set is 50–200 SKUs; Claude picks rendering approach based on current real count and designs for easy virtualization upgrade toward 3,000 SKUs
- Row click behavior (whole row vs explicit expand icon) is Claude's discretion — most natural UX

### Inline expand behavior
- Inline expand is a **preview** — it surfaces key content and actions, but includes a "View full review" link to the full SKU detail page for deep editing
- Only **one row open at a time** — opening a new row collapses the previously expanded one
- What appears in the preview and auto-scroll behavior are Claude's discretion — optimize for the review-and-approve workflow
- The inline expand must allow quick approval decisions per platform without full-page navigation

### Stats bar composition
- **Per-platform breakdown**: separate approved/pending/etc. counts for Google, Bing, and Shopify
- Stats bar is **clickable** — clicking a stat (e.g., "7 needs review on Google") applies a filter to the list
- Sticky vs static behavior is Claude's discretion
- **Status model**: Claude should design a 4-state model that captures the workflow reality:
  - Needs review — candidate content exists, no approval action taken
  - Partial — some content types approved (e.g., title/description done, image pending) but not all
  - Approved — all content types approved for that platform, ready to batch
  - Published — already pushed to that platform in a published batch
- If the existing `sku_approvals` schema cannot support partial tracking, propose a minimal schema addition

### Filter UX
- Filter placement, AND vs OR logic, URL persistence, and text search are Claude's discretion
- Follow existing patterns where they exist (e.g., `?platform=bing` URL param pattern in SkuReviewClient)
- Filters must update the list immediately (no submit button)
- Stats bar clickable filters must integrate cleanly with the manual filter controls (no conflicting state)

### Claude's Discretion
- Status badge visual design (style, colors, icons)
- Exact row click affordance (whole row or chevron)
- Whether stats bar is sticky
- Filter bar placement
- Filter combination logic (AND for status+platform or platform-as-view-toggle)
- URL persistence of filter state
- Whether to add text search (decide based on current SKU count and scannability)
- Auto-scroll when expanding a row
- Amount of detail shown in inline expand
- Rendering strategy for the list (simple vs virtualized)

</decisions>

<specifics>
## Specific Ideas

- The inline expand is explicitly a **preview with a "View full review" escape hatch** — not a replacement for the full review page
- The 4-state status model (Needs review / Partial / Approved / Published) needs to be grounded in the actual `sku_approvals` schema — researcher should read the schema before planning the stats bar
- Clickable stats as filter shortcuts: clicking a stat in the summary bar should behave identically to manually setting the corresponding filters (no duplicate state)
- Three platforms, not two: Shopify is included alongside Google and Bing in all status badges, stats counts, and filter options
- All three SkuReviewClient variants (main, magazine, original) must be updated — this is a mandatory constraint from the codebase (not optional)

</specifics>

<deferred>
## Deferred Ideas

None — discussion stayed within phase scope.

</deferred>

---

*Phase: 09-sku-review-revamp*
*Context gathered: 2026-02-18*
