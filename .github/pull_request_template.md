## Summary

- [ ] Briefly describe the change and affected areas.

## Verification

- [ ] `./scripts/verify_cloud_run_parity.sh`
- [ ] Targeted suite(s) for touched files
- [ ] Any required dashboard lint/build checks

## Cloud Run Parity Report (Required)

- [ ] Confirmed parity suite passed against current branch
- [ ] Confirmed required Cloud Run env/secret contract unchanged or intentionally updated
- [ ] Included request-id propagation validation (`dashboard -> pipeline -> response`)

## Database / Migration Notes

- [ ] No migration
- [ ] Migration included (document rollback strategy and impact)

## Conflict Resolution Notes (if rebased/cherry-picked)

- [ ] Documented how conflicts were resolved against `origin/master`
