# Custom Label Reconciliation Runbook

## Purpose
Use this runbook to reconcile `custom_label_0` coverage for offer-linked variants and split remediation into two operational queues:

- Queue A: `exists_in_gmc=false` (stale/missing `gmc_offer_id` mapping)
- Queue B: `exists_in_gmc=true` with blank label (expected catchall inventory by default)

## Command

```bash
uv run python -m feedops.cli.main reconcile-custom-labels --output-dir reports/merchant_center
```

If you want strict upstream-gap mode instead of catchall mode:

```bash
uv run python -m feedops.cli.main reconcile-custom-labels --treat-gmc-blank-as-upstream-gap
```

Optional (skip Merchant existence check):

```bash
uv run python -m feedops.cli.main reconcile-custom-labels --skip-gmc-lookup
```

## Outputs

The command writes two timestamped CSV files:

- `reports/merchant_center/custom-label-no-match-variants-<timestamp>.csv`
- `reports/merchant_center/custom-label-no-match-master-skus-<timestamp>.csv`

### Variants CSV fields

- `master_sku`
- `gmc_offer_id`
- `normalized_offer_id`
- `exists_in_gmc`
- `queue`

### Masters CSV fields

- `master_sku`
- `missing_variant_count`
- `exists_true_count`
- `exists_false_count`
- `exists_unknown_count`
- `all_missing_in_gmc`
- `partially_missing_in_gmc`

## Coverage KPI

Coverage is measured over **offer-linked variants only**:

- Denominator: `variant_index` rows with non-null `gmc_offer_id`
- Numerator: rows where `custom_label_0` is non-empty

Two KPIs are emitted:

1. `strict_label_coverage_pct`  
Counts only explicit `custom_label_0` values.
2. `actionable_coverage_pct`  
Treats Queue B as expected catchall and focuses on actionable mapping defects (Queue A).

## Triage Workflow

1. Run reconciliation command.
2. Resolve Queue A first:
- correct stale/missing `gmc_offer_id` mapping in `variant_index`
- re-run command and verify Queue A count drops
3. Review Queue B:
- In catchall mode (default), Queue B is expected and should not block rollout.
- In strict mode, treat Queue B as upstream data gap and remediate feed rules.
4. Repeat until Queue A is acceptably low and actionable coverage target is met.

## Regression Check

Run reconciliation daily during backfill/cleanup.

Regression threshold: no day-over-day actionable coverage drop greater than `0.2%`.
