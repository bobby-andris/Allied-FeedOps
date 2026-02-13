-- Migration: Add custom_labels JSONB column to variant_index
-- Purpose: Store custom labels 0-4 from Google Merchant Center for use in data collection worker
-- Worker: collect_custom_labels_batch (src/feedops/jobs/workers.py)
-- Phase: 06 - Data Collection Pipeline
-- Plan: 06-01

ALTER TABLE variant_index ADD COLUMN IF NOT EXISTS custom_labels jsonb;

COMMENT ON COLUMN variant_index.custom_labels IS 'Custom labels 0-4 from GMC, stored as {"customLabel0": "value", "customLabel1": "value", ...}. Updated by collect_custom_labels_batch worker.';
