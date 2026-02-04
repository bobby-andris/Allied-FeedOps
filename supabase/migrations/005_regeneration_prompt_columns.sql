-- 005_regeneration_prompt_columns.sql
-- Store the exact prompts used for regeneration (debugging + transparency)

ALTER TABLE regeneration_history
ADD COLUMN IF NOT EXISTS system_prompt TEXT,
ADD COLUMN IF NOT EXISTS user_prompt TEXT,
ADD COLUMN IF NOT EXISTS prompt_hash TEXT;

CREATE INDEX IF NOT EXISTS idx_regen_history_prompt_hash ON regeneration_history (prompt_hash);