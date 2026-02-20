# Allied Brass Google Ads Account Structure Audit

Generated: 2026-02-20 (UTC)  
Data sources:
- Google Ads API (direct, customer `6253381786`)
- Supabase (`qezuszwufortkiutlhym`) for supporting data checks

Snapshot artifact: `dashboard_data/google_ads_account_structure_snapshot.json`

## 1) Account Overview

- Customer ID: `6253381786`
- Descriptive name: `{active} Andris, Robert - Allied Brass`
- Currency: `USD`
- Time zone: `America/New_York`
- Manager account: `false`
- Test account: `false`

## 2) Shopping Campaign Architecture

### High-level counts

- Shopping campaigns (all statuses): `486`
- Shopping campaigns (enabled): `179`
- Shopping ad groups (enabled): `179`
- Enabled ad groups per enabled campaign:
  - Min: `1`
  - Max: `1`
  - Avg: `1.0`
- Campaign name == ad group name mismatches: `0`

### Naming pattern coverage

Expected funnel naming pattern:

`AVD - Shopping - US - {custom_label_0} - {HIGH|MEDIUM|LOW}`

Enabled campaigns:
- Matching pattern: `178`
- Not matching pattern: `1`
  - `AVD - Shopping - BRANDED - US`

### Enabled funnel labels and tier integrity

- Distinct `custom_label_0` values inferred from enabled campaign names: `60`
- Labels missing one or more tiers:
  - `catchall`: missing `MEDIUM`, `LOW`

### Bidding strategy structure (enabled shopping)

All enabled shopping campaigns use `TARGET_ROAS` with 3 shared strategy resources:

- High tier campaigns use strategy `AVD - Shopping - US - HIGH - tROAS` at `3.6` (360%)
- Medium tier campaigns use `3.1` (310%)
- Low tier campaigns use `2.6` (260%)

This aligns with the intended 3-tier ROAS design.

## 3) Shared Negative Keyword Infrastructure

- Negative shared sets (all): `10`
- Key shared sets detected:
  - `AVD - Global Block` (id `11908862588`)
  - `AVD - Competitor Terms` (id `11906247801`)
  - `AVD - BRANDED_SEARCH_TERMS - US` (id `11898627450`)

Key list keyword counts:
- `AVD - Global Block`: `1886`
- `AVD - Competitor Terms`: `2184`
- `AVD - BRANDED_SEARCH_TERMS - US`: `166`

Total keywords across these 3 core shared lists: `4236`.

## 4) Funnel Negative Keyword Footprint

- Campaign-level negatives (enabled shopping): `71343`
  - Match types: `EXACT` only
- Ad group-level negatives (enabled shopping): `20338`
  - Match types:
    - `EXACT`: `19935`
    - `PHRASE`: `403`

Notes:
- The workflow standard appears to be exact negatives.
- There are `403` phrase-match ad-group negatives currently in account state.

## 5) Search Term Volume in Active Shopping Funnel

30-day enabled shopping search term pull:
- Rows: `51366`
- Distinct normalized search terms: `31721`

Top-volume examples include:
- `recessed toilet paper holder`
- `valet rod`
- `shower squeegee`
- `brass paper towel holder`
- `unlacquered brass toilet paper holder`

This confirms substantial query volume for continuous funnel maintenance.

## 6) custom_label_0 Integrity Findings

### A) Campaign-name-derived label set (control plane)

Distinct enabled campaign labels: `60` (all lowercase in naming).

Compared to the provided canonical list (normalized lowercase), differences are:

- Missing from enabled campaigns:
  - `patriotic`
  - `reserve roll tp holder`
  - `sports`
- Present in campaigns but not in canonical list:
  - `catchall`

### B) Shopping performance `segments.product_custom_attribute0` (data plane)

Distinct values observed in last 30 days: `99`.

Examples observed in performance but not in campaign label set:
- `appliance and door pulls`
- `cabinet knob`
- `cabinet pull`
- `toilet paper holders`
- `towel bars`
- `vertical towel bars`
- `bathroom set accessories`
- `shower curtain rod`

Interpretation:
- Feed-level `customLabel0` values are broader/more varied than active campaign label taxonomy.
- Classification logic should anchor to campaign naming and map/normalize feed labels where needed.

### C) Supabase label storage state

Supabase check on `variant_index`:
- Total rows: `72023`
- Rows with `custom_labels` populated: `0`
- Rows with `customLabel0` key: `0`

Implication:
- Do not rely on `variant_index.custom_labels` yet for shopping funnel classification until backfilled.

## 7) Structural Conclusion

The account is already operating as a shopping funnel system with:
- 3 tiered tROAS strategies (`HIGH`, `MEDIUM`, `LOW`)
- 1:1 campaign↔ad group structure
- Large negative-keyword infrastructure (shared + campaign + ad group)

Key implementation constraints for dashboard phase 2:
- Use campaign naming as the primary source of funnel label/tier identity.
- Treat `catchall` as a special-case label.
- Support and expose phrase-match ad-group negatives present in current state.
- Build normalization/mapping for feed `customLabel0` values vs campaign-label taxonomy.
- Avoid DB dependence on `variant_index.custom_labels` until the backfill job is completed.

## 8) Files Produced

- `AB_GADS_ACCT_STRUCTURE.md` (this document)
- `dashboard_data/google_ads_account_structure_snapshot.json` (raw audit snapshot)
