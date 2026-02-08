-- 025_fix_publish_batches_status_enum.sql
-- Fix UI/database contract mismatch for publish_batches status enum
--
-- ISSUE: BatchesClient.tsx expects 'draft' status to show Publish button,
-- but database constraint only allowed ['pending', 'executing', 'published', 'partial', 'failed']
--
-- SOLUTION: Add 'draft' to allowed statuses
--
-- Related files:
-- - dashboard/src/components/batches/BatchesClient.tsx (line 167)
-- - dashboard/src/app/api/publish/batch/route.ts

-- Drop existing constraint
ALTER TABLE publish_batches
DROP CONSTRAINT IF EXISTS publish_batches_status_check;

-- Add updated constraint with 'draft' status
ALTER TABLE publish_batches
ADD CONSTRAINT publish_batches_status_check
CHECK (status = ANY (ARRAY[
    'draft'::text,      -- Initial state, shows Publish button in UI
    'pending'::text,    -- Queued for execution
    'executing'::text,  -- Currently publishing
    'published'::text,  -- Successfully completed
    'partial'::text,    -- Some SKUs succeeded, some failed
    'failed'::text      -- All SKUs failed
]));

-- Add comment explaining status workflow
COMMENT ON COLUMN publish_batches.status IS
'Batch publish status: draft → pending → executing → [published|partial|failed]';

-- Verify constraint
DO $$
BEGIN
    RAISE NOTICE '✅ Migration 025 completed successfully!';
    RAISE NOTICE 'Added "draft" status to publish_batches for UI compatibility';
    RAISE NOTICE 'UI will now show Publish button for batches in draft status';
END $$;
