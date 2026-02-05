-- 009_variant_finish_sentences.sql
-- Store product+finish tailored sentences for variant content generation.
-- Each row contains 28 finish-specific sentences for one SKU+platform combination.

CREATE TABLE IF NOT EXISTS variant_finish_sentences (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    master_sku TEXT NOT NULL,
    platform TEXT NOT NULL CHECK (platform IN ('google', 'bing')),
    finish_sentences JSONB NOT NULL, -- { "Antique Brass": "...", "Fire Engine Red": "...", ... }
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    UNIQUE(master_sku, platform)
);

-- Index for fast lookups by SKU
CREATE INDEX IF NOT EXISTS idx_variant_finish_sentences_sku ON variant_finish_sentences(master_sku);

-- Enable Row Level Security
ALTER TABLE variant_finish_sentences ENABLE ROW LEVEL SECURITY;

-- Allow all access (dashboard auth is handled at app level)
CREATE POLICY "Allow all access" ON variant_finish_sentences FOR ALL USING (true);
