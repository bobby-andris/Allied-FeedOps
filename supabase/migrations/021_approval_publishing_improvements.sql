-- Migration: 021_approval_publishing_improvements.sql
-- Purpose: Add columns to support proper approval locking and publish tracking
--
-- Problem solved:
-- 1. Approval doesn't lock content - approved content can change before publish
-- 2. No content snapshot in publish_events for rollback capability
-- 3. No tracking of which version was approved/published

-- ============================================================================
-- 1. Add approved content columns to generated_content
-- ============================================================================

ALTER TABLE generated_content
  ADD COLUMN IF NOT EXISTS approved_content TEXT,
  ADD COLUMN IF NOT EXISTS approved_at TIMESTAMPTZ,
  ADD COLUMN IF NOT EXISTS approved_version INTEGER;

COMMENT ON COLUMN generated_content.approved_content IS 'Snapshot of candidate_content at approval time - immutable once set';
COMMENT ON COLUMN generated_content.approved_at IS 'When content was approved';
COMMENT ON COLUMN generated_content.approved_version IS 'Version number of approved content for rollback tracking';

-- ============================================================================
-- 2. Add published content snapshot to publish_events
-- ============================================================================

ALTER TABLE publish_events
  ADD COLUMN IF NOT EXISTS published_title TEXT,
  ADD COLUMN IF NOT EXISTS published_description TEXT,
  ADD COLUMN IF NOT EXISTS variant_count INTEGER,
  ADD COLUMN IF NOT EXISTS content_version INTEGER;

COMMENT ON COLUMN publish_events.published_title IS 'Actual title template published (for rollback)';
COMMENT ON COLUMN publish_events.published_description IS 'Actual description template published (for rollback)';
COMMENT ON COLUMN publish_events.variant_count IS 'Number of variants updated (for Google/Bing with expanded templates)';
COMMENT ON COLUMN publish_events.content_version IS 'Version of approved_content that was published';

-- ============================================================================
-- 3. Create index for efficient approval checks
-- ============================================================================

CREATE INDEX IF NOT EXISTS idx_generated_content_approved
  ON generated_content(master_sku, platform, content_type)
  WHERE approved_content IS NOT NULL;

-- ============================================================================
-- 4. Add helper view for publishing workflow (approved content ready to publish)
-- ============================================================================

CREATE OR REPLACE VIEW v_approved_content_ready AS
SELECT
  gc.master_sku,
  gc.platform,
  gc.content_type,
  gc.approved_content,
  gc.approved_at,
  gc.approved_version,
  sa.approval_status
FROM generated_content gc
JOIN sku_approvals sa ON gc.master_sku = sa.master_sku
WHERE gc.approved_content IS NOT NULL
  AND sa.approval_status = 'approved';

COMMENT ON VIEW v_approved_content_ready IS 'Content that has been approved and is ready for publishing';
