-- Migration 040: Add label-level action scope to routing_recommendations
-- Phase 34.1-03: Supports blocking entire product categories (custom_label_0) at once
-- Applied: 2026-02-26

-- Add action_scope column (default 'term' for existing rows)
ALTER TABLE routing_recommendations
  ADD COLUMN IF NOT EXISTS action_scope text NOT NULL DEFAULT 'term';

-- Add check constraint for action_scope
DO $$
BEGIN
  IF NOT EXISTS (
    SELECT 1 FROM pg_constraint
    WHERE conname = 'routing_recommendations_action_scope_check'
  ) THEN
    ALTER TABLE routing_recommendations
      ADD CONSTRAINT routing_recommendations_action_scope_check
      CHECK (action_scope IN ('term', 'label'));
  END IF;
END $$;

-- Expand recommended_action check constraint to include 'label_block'
-- Must drop and recreate since we're adding a new allowed value
ALTER TABLE routing_recommendations
  DROP CONSTRAINT IF EXISTS routing_recommendations_action_check;

DO $$
BEGIN
  IF NOT EXISTS (
    SELECT 1 FROM pg_constraint
    WHERE conname = 'routing_recommendations_recommended_action_check'
  ) THEN
    ALTER TABLE routing_recommendations
      ADD CONSTRAINT routing_recommendations_recommended_action_check
      CHECK (recommended_action IN ('global_block', 'competitor', 'branded', 'funnel', 'label_block'));
  END IF;
END $$;
