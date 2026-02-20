-- Migration: 033_add_publish_event_final_payload_snapshot.sql
-- Purpose: Persist post-expansion payload snapshots for channel auditability.

ALTER TABLE publish_events
  ADD COLUMN IF NOT EXISTS final_payload_snapshot JSONB;

COMMENT ON COLUMN publish_events.final_payload_snapshot IS
  'Final channel-ready payload snapshot (post-expansion content) for audit/debug';

