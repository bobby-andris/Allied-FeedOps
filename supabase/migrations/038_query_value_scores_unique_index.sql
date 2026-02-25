-- Migration: 038_query_value_scores_unique_index.sql
-- Phase 33: Add unique index on (search_term, custom_label_0) for upsert support
-- Required by tier-scoring API route to upsert scored terms without duplicates
-- Applied: 2026-02-25

-- Create unique index for upsert conflict resolution
-- This enables Supabase .upsert({ onConflict: 'search_term,custom_label_0' })
CREATE UNIQUE INDEX IF NOT EXISTS idx_query_value_scores_term_label_unique
  ON query_value_scores (search_term, custom_label_0);
