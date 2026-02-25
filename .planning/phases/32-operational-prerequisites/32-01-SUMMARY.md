---
plan: 32-01
title: Schema Migrations — Extend Scoring and Experiment Tables
status: complete
started: 2026-02-25
completed: 2026-02-25
---

## What Was Built

Applied migration `037_extend_scoring_and_experiment_columns.sql` to production Supabase. Created base tables (`query_value_scores`, `experiment_registry`, `experiment_outcomes`) via CREATE IF NOT EXISTS from deferred migrations 033b/035b, then added 7 new columns across 2 tables.

## Key Files

### Created
- `supabase/migrations/037_extend_scoring_and_experiment_columns.sql`

## Decisions Made
- Included full CREATE TABLE IF NOT EXISTS for safety (tables from deferred migrations may or may not exist)
- Added RLS policies with "Allow all access" for service role compatibility
- CHECK constraints use DO $$ blocks with pg_constraint existence checks for idempotency

## Deviations
- None

## Self-Check: PASSED
- [x] 4 columns on query_value_scores: tier_fit_scores, recommended_tier, net_monthly_impact, scored_at
- [x] 3 columns on experiment_outcomes: p_value, confidence_interval, minimum_sample_size
- [x] All nullable, no defaults
- [x] CHECK constraints on recommended_tier (HIGH/MEDIUM/LOW) and p_value (0-1)
- [x] Index idx_query_value_scores_scored_at created
