# Phase 10: Image Workflow Improvements - Context

**Gathered:** 2026-02-18
**Status:** Ready for planning

<domain>
## Phase Boundary

Give users control over which finish/variant is used for lifestyle image generation, with smart auto-selection fallback using real Google Ads impression data, and a per-SKU coverage view showing which variants have lifestyle images and which do not. Feedback-driven regeneration (correcting wrong AI output) is out of scope for this phase.

</domain>

<decisions>
## Implementation Decisions

### Variant selector design
- Variant selector appears as a **modal/dialog** — triggered when user opens the selection UI before generation
- Variants presented as a **dropdown/select** inside the modal
- Each dropdown option shows: **finish name + impression count + image status** (e.g. "Antique Brass — 1,240 impressions ✓ has image")
- Modal flow: select variant → close modal → Generate (modal captures selection only; generation triggered separately)

### Auto-select transparency
- When no manual selection is made, the system auto-selects the highest-impressions variant and **displays it prominently** near the Generate button before the user clicks
- Label format: **"Highest impressions: [Finish Name]"** — communicates both that it was auto-selected and why
- After user manually picks a variant, label updates to **"Manual: [Finish Name]"** to distinguish manual from auto
- Fallback when no impression data exists: **Claude's discretion** (pick simplest deterministic fallback)

### Selection persistence
- Post-generation reset behavior: **Claude's discretion** (pick what feels most natural for the workflow)
- Storage level: **Claude's discretion** (pick appropriate level — in-memory is simplest, session if needed)
- Re-opening the modal after a prior selection: **Claude's discretion** (pick most intuitive behavior)

### Coverage view layout
- Coverage view lives in a **separate tab or section** (not inside the expanded row or the modal)
- Scope: **per-SKU only** — shows all variants for the currently expanded/selected SKU
- Each variant row displays: **finish name + lifestyle image thumbnail (if exists) + date generated**
- Thumbnails are shown for variants that have images; missing variants show no image state
- CTA for missing variants: **Claude's discretion** (whether to include per-row Generate button or keep view-only)

### Claude's Discretion
- Fallback variant when no impression data available
- Post-generation selection reset behavior
- Storage level for selection persistence (in-memory vs. session vs. localStorage)
- Modal pre-selection behavior on re-open
- Whether coverage view rows have a direct Generate button for missing variants

</decisions>

<specifics>
## Specific Ideas

- The variant selector dropdown should show both impression count AND image status together per option — gives the user everything they need to make an informed choice in one place
- The "Highest impressions: [Finish Name]" label near Generate is key — it should be visible without opening the modal so users know what will be generated before they commit
- "Manual: [Finish Name]" label clearly distinguishes user-chosen from auto-chosen selections

</specifics>

<deferred>
## Deferred Ideas

- **Image regeneration with user feedback** — User wants to provide product-type context or rejection reason before re-generating when AI produces wrong use-case imagery (e.g. cabinet knob rendered as robe hook). Example: SKU 102 shows a cabinet knob incorrectly staged as a robe hook. This requires a feedback/correction UI + backend changes to pass user context into the image generation prompt. Future phase.

</deferred>

---

*Phase: 10-image-workflow-improvements*
*Context gathered: 2026-02-18*
