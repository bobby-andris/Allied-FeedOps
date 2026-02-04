-- Migration: 008_product_catalog.sql
-- Description: Create product_catalog table to store rich product data from Acatalog.csv
-- Purpose: Enable dashboard regeneration API to pass comprehensive product context to LLM

-- Product Catalog Table
-- Source: data/Acatalog.csv (75,773 rows)
-- Each row is a variant (option_sku), not master SKU
-- Provides bullets, narrative_copy, images, specs needed for quality descriptions

CREATE TABLE IF NOT EXISTS product_catalog (
    id BIGSERIAL PRIMARY KEY,

    -- Identifiers (CSV columns 1-7)
    master_sku TEXT NOT NULL,
    option_sku TEXT NOT NULL UNIQUE,  -- Variant-level unique key (e.g., "101-ABR")
    core_sku TEXT,                    -- CoreSKU column
    upc TEXT,
    gtin TEXT,
    gmc_id TEXT,                      -- GMCID: shopify_US_{product}_{variant}
    amazon_asin TEXT,

    -- Finish information (columns 8-10)
    finish_name TEXT NOT NULL,
    finish_code TEXT NOT NULL,        -- 3-letter code (e.g., "ABR", "PC")
    position INTEGER,                 -- Display order within master_sku

    -- Classification (columns 11-12)
    category TEXT NOT NULL,
    collection TEXT,                  -- "Allied Brass Collection" column

    -- Current content (columns 13, 17-23)
    title TEXT NOT NULL,
    narrative_copy TEXT,              -- Full description (CSV: "Narraive Copy" - typo in source)
    bullet_1 TEXT,
    bullet_2 TEXT,
    bullet_3 TEXT,
    bullet_4 TEXT,
    bullet_5 TEXT,
    bullet_6 TEXT,

    -- Product dimensions (first occurrence: columns 24-28)
    -- Note: CSV has duplicate Length/Height/Width columns - first set is product, second is box
    product_length NUMERIC(10, 2),
    product_height NUMERIC(10, 2),
    product_width NUMERIC(10, 2),
    projection NUMERIC(10, 2),
    product_weight NUMERIC(10, 2),

    -- Box/Shipping dimensions (second occurrence: columns 29-32)
    box_length NUMERIC(10, 2),
    box_height NUMERIC(10, 2),
    box_width NUMERIC(10, 2),
    box_weight NUMERIC(10, 2),

    -- Documentation URLs (columns 33-34)
    installation_url TEXT,
    specification_url TEXT,

    -- Images (columns 35-40)
    main_image_filename TEXT,
    main_image_url TEXT,
    alt_image_1 TEXT,
    alt_image_2 TEXT,
    alt_image_3 TEXT,
    alt_image_4 TEXT,

    -- Specifications (columns 41-48)
    center_to_center NUMERIC(10, 2),
    diameter NUMERIC(10, 2),
    screw_size TEXT,
    mirror_height NUMERIC(10, 2),
    mirror_width NUMERIC(10, 2),
    thickness NUMERIC(10, 2),
    weight_capacity NUMERIC(10, 2),
    material TEXT,

    -- Style attributes (columns 49-55)
    style TEXT,
    shape TEXT,
    orientation TEXT,
    tilting TEXT,
    mounting_type TEXT,
    assembly_required BOOLEAN DEFAULT FALSE,
    item_number TEXT,

    -- Additional info (column 56)
    included_items TEXT,

    -- Timestamps
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

-- Indexes for common query patterns
CREATE INDEX IF NOT EXISTS idx_product_catalog_master_sku ON product_catalog(master_sku);
CREATE INDEX IF NOT EXISTS idx_product_catalog_gmc_id ON product_catalog(gmc_id);
CREATE INDEX IF NOT EXISTS idx_product_catalog_category ON product_catalog(category);
CREATE INDEX IF NOT EXISTS idx_product_catalog_collection ON product_catalog(collection);
CREATE INDEX IF NOT EXISTS idx_product_catalog_finish ON product_catalog(master_sku, finish_code);

-- Full-text search on narrative content (optional, for future use)
CREATE INDEX IF NOT EXISTS idx_product_catalog_narrative_fts
    ON product_catalog USING gin(to_tsvector('english', COALESCE(narrative_copy, '')));

-- RLS (Row Level Security)
ALTER TABLE product_catalog ENABLE ROW LEVEL SECURITY;
CREATE POLICY "Allow all access to product_catalog" ON product_catalog FOR ALL USING (true);

-- Updated timestamp trigger
CREATE OR REPLACE FUNCTION update_product_catalog_updated_at()
RETURNS TRIGGER AS $$
BEGIN
    NEW.updated_at = now();
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

DROP TRIGGER IF EXISTS tr_product_catalog_updated_at ON product_catalog;
CREATE TRIGGER tr_product_catalog_updated_at
    BEFORE UPDATE ON product_catalog
    FOR EACH ROW
    EXECUTE FUNCTION update_product_catalog_updated_at();

-- Comment on table
COMMENT ON TABLE product_catalog IS 'Rich product catalog data from Acatalog.csv for LLM description generation';
COMMENT ON COLUMN product_catalog.narrative_copy IS 'Full product description from CSV (source column: "Narraive Copy")';
COMMENT ON COLUMN product_catalog.gmc_id IS 'Google Merchant Center offer ID: shopify_US_{product_id}_{variant_id}';
