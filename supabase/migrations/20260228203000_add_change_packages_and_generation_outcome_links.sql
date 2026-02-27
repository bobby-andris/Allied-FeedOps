-- R4: Generation→outcome lineage bridge + immutable change package model.

CREATE TABLE IF NOT EXISTS change_packages (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  package_key TEXT NOT NULL UNIQUE,
  source_type TEXT NOT NULL DEFAULT 'publish_event',
  source_ref TEXT,
  action TEXT NOT NULL DEFAULT 'publish',
  environment TEXT NOT NULL,
  created_by TEXT,
  metadata JSONB,
  created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
  updated_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE INDEX IF NOT EXISTS idx_change_packages_source_type
  ON change_packages (source_type, created_at DESC);

CREATE INDEX IF NOT EXISTS idx_change_packages_environment
  ON change_packages (environment, created_at DESC);

ALTER TABLE publish_events
  ADD COLUMN IF NOT EXISTS change_package_id UUID REFERENCES change_packages(id) ON DELETE SET NULL;

CREATE INDEX IF NOT EXISTS idx_publish_events_change_package_id
  ON publish_events (change_package_id);

CREATE TABLE IF NOT EXISTS change_package_events (
  id BIGSERIAL PRIMARY KEY,
  change_package_id UUID NOT NULL REFERENCES change_packages(id) ON DELETE CASCADE,
  publish_event_id BIGINT NOT NULL REFERENCES publish_events(id) ON DELETE CASCADE,
  event_type TEXT NOT NULL DEFAULT 'publish',
  metadata JSONB,
  created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
  UNIQUE (change_package_id, publish_event_id)
);

CREATE INDEX IF NOT EXISTS idx_change_package_events_publish_event
  ON change_package_events (publish_event_id);

CREATE TABLE IF NOT EXISTS change_package_items (
  id BIGSERIAL PRIMARY KEY,
  change_package_id UUID NOT NULL REFERENCES change_packages(id) ON DELETE CASCADE,
  publish_event_id BIGINT REFERENCES publish_events(id) ON DELETE SET NULL,
  master_sku TEXT NOT NULL,
  platform TEXT NOT NULL,
  content_type TEXT NOT NULL DEFAULT 'title_and_description',
  published_title TEXT,
  published_description TEXT,
  content_version INTEGER,
  prompt_hash TEXT,
  final_payload_hash TEXT,
  evidence_hash TEXT,
  segment_key TEXT,
  metadata JSONB,
  created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
  UNIQUE (change_package_id, master_sku, platform, content_type)
);

CREATE INDEX IF NOT EXISTS idx_change_package_items_master_sku
  ON change_package_items (master_sku, platform, created_at DESC);

CREATE INDEX IF NOT EXISTS idx_change_package_items_publish_event
  ON change_package_items (publish_event_id);

CREATE TABLE IF NOT EXISTS generation_outcome_links (
  id BIGSERIAL PRIMARY KEY,
  change_package_id UUID NOT NULL REFERENCES change_packages(id) ON DELETE CASCADE,
  publish_event_id BIGINT NOT NULL REFERENCES publish_events(id) ON DELETE CASCADE,
  generated_content_id UUID REFERENCES generated_content(id) ON DELETE SET NULL,
  regeneration_history_id UUID REFERENCES regeneration_history(id) ON DELETE SET NULL,
  request_id TEXT,
  master_sku TEXT NOT NULL,
  platform TEXT NOT NULL,
  content_type TEXT NOT NULL,
  content_version INTEGER,
  prompt_hash TEXT,
  effect_status TEXT NOT NULL DEFAULT 'pending',
  metadata JSONB,
  created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
  UNIQUE (publish_event_id, content_type)
);

CREATE INDEX IF NOT EXISTS idx_generation_outcome_links_request_id
  ON generation_outcome_links (request_id)
  WHERE request_id IS NOT NULL;

CREATE INDEX IF NOT EXISTS idx_generation_outcome_links_generated_content_id
  ON generation_outcome_links (generated_content_id)
  WHERE generated_content_id IS NOT NULL;

CREATE INDEX IF NOT EXISTS idx_generation_outcome_links_master_sku
  ON generation_outcome_links (master_sku, platform, created_at DESC);

CREATE TABLE IF NOT EXISTS generation_effect_windows (
  id BIGSERIAL PRIMARY KEY,
  change_package_id UUID NOT NULL REFERENCES change_packages(id) ON DELETE CASCADE,
  publish_event_id BIGINT NOT NULL REFERENCES publish_events(id) ON DELETE CASCADE,
  master_sku TEXT NOT NULL,
  platform TEXT NOT NULL,
  environment TEXT NOT NULL,
  window_pre_days INTEGER NOT NULL DEFAULT 30,
  window_post_days INTEGER NOT NULL DEFAULT 30,
  effect_start_date DATE NOT NULL,
  effect_end_date DATE NOT NULL,
  treated_snapshot_count INTEGER NOT NULL DEFAULT 0,
  control_snapshot_count INTEGER NOT NULL DEFAULT 0,
  metrics JSONB,
  metadata JSONB,
  created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
  updated_at TIMESTAMPTZ NOT NULL DEFAULT now(),
  UNIQUE (publish_event_id, window_pre_days, window_post_days)
);

CREATE INDEX IF NOT EXISTS idx_generation_effect_windows_master_sku
  ON generation_effect_windows (master_sku, platform, created_at DESC);

CREATE INDEX IF NOT EXISTS idx_generation_effect_windows_effect_start_date
  ON generation_effect_windows (effect_start_date DESC);

DROP TRIGGER IF EXISTS update_change_packages_updated_at ON change_packages;
CREATE TRIGGER update_change_packages_updated_at
  BEFORE UPDATE ON change_packages
  FOR EACH ROW
  EXECUTE FUNCTION update_updated_at_column();

DROP TRIGGER IF EXISTS update_generation_effect_windows_updated_at ON generation_effect_windows;
CREATE TRIGGER update_generation_effect_windows_updated_at
  BEFORE UPDATE ON generation_effect_windows
  FOR EACH ROW
  EXECUTE FUNCTION update_updated_at_column();

ALTER TABLE change_packages ENABLE ROW LEVEL SECURITY;
ALTER TABLE change_package_events ENABLE ROW LEVEL SECURITY;
ALTER TABLE change_package_items ENABLE ROW LEVEL SECURITY;
ALTER TABLE generation_outcome_links ENABLE ROW LEVEL SECURITY;
ALTER TABLE generation_effect_windows ENABLE ROW LEVEL SECURITY;

DROP POLICY IF EXISTS "Allow all access" ON change_packages;
DROP POLICY IF EXISTS "Allow all access" ON change_package_events;
DROP POLICY IF EXISTS "Allow all access" ON change_package_items;
DROP POLICY IF EXISTS "Allow all access" ON generation_outcome_links;
DROP POLICY IF EXISTS "Allow all access" ON generation_effect_windows;

CREATE POLICY "Allow all access" ON change_packages FOR ALL USING (true);
CREATE POLICY "Allow all access" ON change_package_events FOR ALL USING (true);
CREATE POLICY "Allow all access" ON change_package_items FOR ALL USING (true);
CREATE POLICY "Allow all access" ON generation_outcome_links FOR ALL USING (true);
CREATE POLICY "Allow all access" ON generation_effect_windows FOR ALL USING (true);

COMMENT ON TABLE change_packages IS
  'Immutable publish change package envelope used for lineage, rollback, and outcome analysis.';

COMMENT ON TABLE generation_outcome_links IS
  'Bridges publish events to generated content and regeneration lineage for downstream impact analysis.';

COMMENT ON TABLE generation_effect_windows IS
  'Stores configured pre/post effect windows for publish events and derived outcome snapshots.';
