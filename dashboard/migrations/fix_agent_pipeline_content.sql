-- Fix malformed content from 6-agent pipeline for 10 SKUs
-- Migration: fix_agent_pipeline_content.sql
-- Date: 2026-02-07
-- Purpose: Transform incorrectly formatted content data from 6-agent pipeline
--          into proper schema format (separate title/description rows)

-- Background:
-- The 6-agent pipeline inserted content as single rows with JSON containing both
-- title and description. The dashboard expects separate rows for each content_type.
-- This migration fixes 10 SKUs: 1016, 1024, 1024E, 102, 1020, 1026, MC-60, WP-1/16, 1020-3, 1025U

DO $$
DECLARE
  sku TEXT;
  title_text TEXT;
  desc_text TEXT;
  baseline_title TEXT;
  baseline_desc TEXT;
  q_score NUMERIC;
  skus_fixed INTEGER := 0;
BEGIN
  -- Loop through each of the 10 SKUs
  FOR sku IN
    SELECT UNNEST(ARRAY['1016', '1024', '1024E', '102', '1020', '1026', 'MC-60', 'WP-1/16', '1020-3', '1025U'])
  LOOP
    -- Extract title and description from malformed JSON
    SELECT
      candidate_content::jsonb->>'title',
      candidate_content::jsonb->>'description',
      quality_score
    INTO title_text, desc_text, q_score
    FROM generated_content
    WHERE master_sku = sku AND platform = 'google'
    LIMIT 1;

    -- Skip if no data found (already fixed or never existed)
    IF title_text IS NULL THEN
      RAISE NOTICE 'Skipping SKU % (no data found)', sku;
      CONTINUE;
    END IF;

    -- Get baseline content from product_catalog
    SELECT title, narrative_copy
    INTO baseline_title, baseline_desc
    FROM product_catalog
    WHERE master_sku = sku
    LIMIT 1;

    -- Delete the malformed row
    DELETE FROM generated_content
    WHERE master_sku = sku AND platform = 'google';

    -- Insert properly formatted title row
    INSERT INTO generated_content (
      master_sku, platform, content_type, baseline_content,
      candidate_content, quality_score, generation_model,
      generation_timestamp, is_current, version
    ) VALUES (
      sku, 'google', 'title', baseline_title,
      title_text, q_score, '6-agent-pipeline-gpt-4',
      NOW(), true, 1
    );

    -- Insert properly formatted description row
    INSERT INTO generated_content (
      master_sku, platform, content_type, baseline_content,
      candidate_content, quality_score, generation_model,
      generation_timestamp, is_current, version
    ) VALUES (
      sku, 'google', 'description', baseline_desc,
      desc_text, q_score, '6-agent-pipeline-gpt-4',
      NOW(), true, 1
    );

    skus_fixed := skus_fixed + 1;
    RAISE NOTICE 'Fixed SKU: % (quality score: %)', sku, q_score;
  END LOOP;

  RAISE NOTICE 'Migration complete! Fixed % SKUs', skus_fixed;
END $$;

-- Verify the fix
SELECT
  master_sku,
  content_type,
  generation_model,
  quality_score,
  LENGTH(candidate_content) as content_length
FROM generated_content
WHERE master_sku IN ('1016', '1024', '1024E', '102', '1020', '1026', 'MC-60', 'WP-1/16', '1020-3', '1025U')
  AND platform = 'google'
ORDER BY master_sku, content_type;
