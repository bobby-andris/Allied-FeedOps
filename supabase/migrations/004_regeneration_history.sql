-- 004_regeneration_history.sql
-- Migration for content versioning and regeneration tracking
-- Enables content regeneration from the dashboard with history tracking

-- ============================================================================
-- Add Versioning to Generated Content
-- ============================================================================
-- Track multiple versions of content for each SKU/platform/content_type

ALTER TABLE generated_content
ADD COLUMN IF NOT EXISTS version integer DEFAULT 1;

ALTER TABLE generated_content
ADD COLUMN IF NOT EXISTS is_current boolean DEFAULT true;

-- Index for efficient current content lookup
CREATE INDEX IF NOT EXISTS idx_content_current ON generated_content (
    master_sku,
    platform,
    content_type
)
WHERE
    is_current = true;

-- ============================================================================
-- Regeneration History Table
-- ============================================================================
-- Tracks all regeneration requests with feedback for audit and learning

CREATE TABLE IF NOT EXISTS regeneration_history (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    master_sku TEXT NOT NULL,
    content_type TEXT NOT NULL,  -- 'title', 'description'
    platform TEXT NOT NULL,      -- 'google', 'bing', 'shopify'

-- Regeneration mode and feedback
mode TEXT NOT NULL, -- 'simple', 'with_feedback'
feedback_text TEXT, -- User's custom feedback (null for simple mode)
feedback_preset TEXT, -- Preset used: 'shorter', 'longer', 'more_specific', etc.

-- Content snapshots for comparison
previous_content TEXT, new_content TEXT,

-- Metadata
model_version TEXT, -- e.g., 'gpt-5.2'
quality_score_before NUMERIC(5, 2),
quality_score_after NUMERIC(5, 2),

-- Audit fields
created_at TIMESTAMPTZ NOT NULL DEFAULT now(), created_by TEXT,

-- Reference to the generated content record
generated_content_id UUID REFERENCES generated_content(id) );

-- Indexes for common queries
CREATE INDEX IF NOT EXISTS idx_regen_history_sku ON regeneration_history (master_sku);

CREATE INDEX IF NOT EXISTS idx_regen_history_created ON regeneration_history (created_at DESC);

CREATE INDEX IF NOT EXISTS idx_regen_history_sku_type ON regeneration_history (
    master_sku,
    content_type,
    platform
);

-- ============================================================================
-- Row Level Security
-- ============================================================================

ALTER TABLE regeneration_history ENABLE ROW LEVEL SECURITY;

DROP POLICY IF EXISTS "Allow all access" ON regeneration_history;

CREATE POLICY "Allow all access" ON regeneration_history FOR ALL USING (true);

-- ============================================================================
-- Helper function to get current content version
-- ============================================================================

CREATE OR REPLACE FUNCTION get_current_content_version(
    p_master_sku TEXT,
    p_platform TEXT,
    p_content_type TEXT
) RETURNS INTEGER AS $$
DECLARE
    v_version INTEGER;
BEGIN
    SELECT COALESCE(MAX(version), 0) INTO v_version
    FROM generated_content
    WHERE master_sku = p_master_sku
      AND platform = p_platform
      AND content_type = p_content_type;
    RETURN v_version;
END;
$$ LANGUAGE plpgsql;

-- ============================================================================
-- Comments for documentation
-- ============================================================================

COMMENT ON
TABLE regeneration_history IS 'Tracks all content regeneration requests with feedback for audit and prompt improvement';

COMMENT ON COLUMN regeneration_history.mode IS 'simple = same prompts, with_feedback = includes user feedback';

COMMENT ON COLUMN regeneration_history.feedback_preset IS 'Preset values: shorter, longer, more_specific, different_angle, more_keywords, less_promotional, better_hook';