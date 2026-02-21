-- Migration 036: Create sku_corrections table for persistent per-SKU corrections
-- Implements FIX-01: feedback layer — corrections that accumulate per SKU
-- so repeated issues get resolved permanently.
--
-- Per CONTEXT.md: "Sometimes there are things the prompt gets wrong regardless
-- of how many times it is regenerated with feedback." This table makes corrections sticky.

CREATE TABLE sku_corrections (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    master_sku TEXT NOT NULL,
    platform TEXT NOT NULL CHECK (platform IN ('google', 'bing', 'shopify', 'all')),
    content_type TEXT NOT NULL CHECK (content_type IN ('title', 'description', 'all')),
    correction_text TEXT NOT NULL,
    correction_type TEXT NOT NULL CHECK (
        correction_type IN ('tone', 'emphasis', 'length', 'free_text')
    ),
    is_active BOOLEAN NOT NULL DEFAULT TRUE,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

-- Lookup index: fetch active corrections for a specific SKU/platform/content_type
CREATE INDEX idx_sku_corrections_lookup
    ON sku_corrections (master_sku, platform, content_type, is_active);

-- Prevent exact duplicate corrections (when is_active = TRUE)
CREATE UNIQUE INDEX idx_sku_corrections_unique
    ON sku_corrections (master_sku, platform, content_type, correction_type, correction_text)
    WHERE is_active = TRUE;
