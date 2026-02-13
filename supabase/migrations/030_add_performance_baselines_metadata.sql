-- Add metadata JSONB column to performance_baselines for multi-SKU family flags
-- and other validation metadata

ALTER TABLE performance_baselines
ADD COLUMN IF NOT EXISTS metadata JSONB DEFAULT '{}'::jsonb;

COMMENT ON COLUMN performance_baselines.metadata IS 'Multi-SKU family flags and other validation metadata. Example: {"is_multi_sku_family": true, "family_members": ["DMF-2/2X", "DMF-2/3X"], "family_size": 2, "data_aggregation": "product_id_level"}';
