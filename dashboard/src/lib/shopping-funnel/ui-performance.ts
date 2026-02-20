/**
 * UI-level caps to keep shopping funnel interactions responsive.
 *
 * The API can serve larger pages, but rendering thousands of rows with rich
 * controls in one paint causes poor INP on filter/sort interactions.
 */
export const NEEDS_DECISION_UI_LIMIT = 500
export const EXISTING_FUNNEL_UI_LIMIT = 1000
