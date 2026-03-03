# GA4 Attribution Forensics Runbook (Read-Only)

## Scope Guardrail
- This workflow is diagnostics-only.
- Do not change GTM, storefront tracking code, checkout scripts, or Analyzify configuration from this runbook.
- All outputs are evidence artifacts for escalation and follow-through.

## Daily Operating Flow
1. Open `/attribution-forensics` in the dashboard.
2. Review health cards:
   - Attribution quality score
   - Unassigned revenue share
   - `(not set)` campaign revenue share
   - Landing blank/`(not set)` revenue share
   - GA4 ↔ Shopify reconciliation ratio
3. Review active incidents.
4. If stale or missing, click `Capture now` to persist a fresh snapshot.
5. Export handoff packet for escalation when incidents are high/critical.

## Incident Thresholds
- `critical`: `unassigned_revenue_share >= 0.25`
- `high`: `not_set_campaign_revenue_share >= 0.15`
- `high`: `(blank + not_set landing page) revenue share >= 0.10`
- `medium`: GA4/Shopify revenue ratio outside `[0.80, 1.20]` for 3 consecutive snapshots

## Escalation Template: Evidence for Analyzify
Subject: `GA4 Attribution Leakage Evidence - Action Needed`

Body:
- Property: `properties/342525135`
- Window: `{start_date} to {end_date}`
- Incident(s):
  - `{rule_id}` - `{severity}` - `{message}`
- Evidence summary:
  - Unassigned share: `{value}`
  - `(not set)` campaign share: `{value}`
  - Landing blank/`(not set)` share: `{value}`
  - GA4 ↔ Shopify ratio: `{value}`
- Attached:
  - JSON handoff packet
  - CSV handoff packet
- Requested action:
  - Root-cause analysis and implementation plan with ETA
  - Validation steps and expected post-fix metric movement

## Escalation Template: Campaign Naming Governance Team
Subject: `Campaign Naming Integrity Drift Detected`

Body:
- Property: `properties/342525135`
- Window: `{start_date} to {end_date}`
- Nonstandard campaign naming impact:
  - Revenue: `{value}`
  - Sessions: `{value}`
  - Top offending names:
    - `{campaign_a}`
    - `{campaign_b}`
    - `{campaign_c}`
- Requested action:
  - Align names to approved conventions
  - Confirm expected naming regex
  - Provide completion ETA

## Verification Checklist
- [ ] Dashboard loads with no 500 errors.
- [ ] All three APIs return payloads with `available` and `warnings`.
- [ ] Snapshot capture writes daily rows into:
  - `ga4_source_medium_daily`
  - `ga4_landing_page_quality_daily`
  - `ga4_attribution_root_cause_daily`
  - `ga4_shopify_reconciliation_daily`
  - `ga4_attribution_quality_daily`
- [ ] Incidents are generated only when thresholds are breached.
- [ ] No edits touched tracking implementation paths.

## Ownership
- Analytics owner: triages incidents daily.
- Paid media owner: reviews campaign naming and traffic quality implications.
- Tracking implementation owner (Analyzify): executes tracking-side fixes after evidence handoff.
