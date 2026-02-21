-- ============================================================
-- DEFERRED MIGRATION — 035b_DEFERRED_unified_intent_execution_system.sql
-- ============================================================
-- WHY DEFERRED: Not in v1.2 milestone scope (phases 17-22).
--   The Unified Intent Execution System (bidding policy, search
--   governance, experiment tracking) is a major feature set
--   requiring dedicated implementation work beyond measurement
--   infrastructure.
--
-- CODEBASE STATUS: 10+ API routes reference these tables (estimates
--   based on research phase 21-RESEARCH.md):
--   - intent_taxonomy_versions: referenced by intent classification APIs
--   - term_intent_state: referenced by search query routing
--   - experiment_registry: referenced by A/B testing framework
--   - policy_decision_log: referenced by policy audit endpoints
--   Tables were applied out-of-band in a previous session.
--
-- WHEN TO APPLY: When the intent classification, search governance,
--   or experiment tracking features are prioritized in a future
--   milestone (e.g., v2.0 Intent Intelligence).
--
-- NOTE: File renamed from 035_unified_intent_execution_system.sql to
--   035b_DEFERRED_unified_intent_execution_system.sql to avoid conflict
--   with 035_measurement_infrastructure_schema.sql (which is applied).
--
-- STATUS: Tables created out-of-band; this file is reference only.
-- ============================================================

-- Unified Intent Intelligence & Execution System
-- Adds policy/versioning, search governance, experiment tracking, and value-confidence support tables.

create table if not exists intent_taxonomy_versions (
  id uuid primary key default gen_random_uuid(),
  version_key text not null unique,
  description text,
  class_definitions jsonb not null default '{}'::jsonb,
  mapping_rules jsonb not null default '{}'::jsonb,
  is_active boolean not null default false,
  activated_at timestamptz,
  activated_by text,
  created_at timestamptz not null default now()
);

create table if not exists term_intent_state (
  id uuid primary key default gen_random_uuid(),
  search_term text not null,
  normalized_search_term text not null,
  custom_label_0 text,
  intent_class text not null,
  intent_subclasses text[] not null default '{}',
  route_action text not null,
  shopping_tier text,
  search_tier text,
  confidence numeric(5,4) not null default 0,
  requires_review boolean not null default true,
  policy_version text not null,
  source_window_start date,
  source_window_end date,
  last_decided_at timestamptz not null default now(),
  metadata jsonb not null default '{}'::jsonb,
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now()
);

create unique index if not exists idx_term_intent_state_unique_term_label
  on term_intent_state (normalized_search_term, coalesce(custom_label_0, '__all__'));

create index if not exists idx_term_intent_state_intent_class
  on term_intent_state (intent_class, confidence desc, updated_at desc);

create table if not exists policy_decision_log (
  id uuid primary key default gen_random_uuid(),
  search_term text,
  custom_label_0 text,
  decision_type text not null,
  channel text not null,
  policy_version text not null,
  decision_payload jsonb not null default '{}'::jsonb,
  confidence numeric(5,4),
  requires_review boolean not null default true,
  created_by text,
  created_at timestamptz not null default now()
);

create index if not exists idx_policy_decision_log_type_created
  on policy_decision_log (decision_type, created_at desc);

create index if not exists idx_policy_decision_log_search_term
  on policy_decision_log (search_term, created_at desc);

create table if not exists policy_action_execution_log (
  id uuid primary key default gen_random_uuid(),
  action_type text not null,
  search_term text,
  custom_label_0 text,
  status text not null default 'planned',
  policy_version text not null,
  action_payload jsonb not null default '{}'::jsonb,
  reason_codes text[] not null default '{}',
  created_by text,
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now()
);

create index if not exists idx_policy_action_execution_status_created
  on policy_action_execution_log (status, created_at desc);

create index if not exists idx_policy_action_execution_action_type
  on policy_action_execution_log (action_type, created_at desc);

create table if not exists policy_snapshots (
  id uuid primary key default gen_random_uuid(),
  snapshot_key text not null unique,
  policy_version text not null,
  payload jsonb not null default '{}'::jsonb,
  created_by text,
  created_at timestamptz not null default now(),
  restored_at timestamptz,
  restored_by text
);

create index if not exists idx_policy_snapshots_created
  on policy_snapshots (created_at desc);

create table if not exists sku_margin_daily (
  id uuid primary key default gen_random_uuid(),
  snapshot_date date not null,
  sku text not null,
  unit_cogs numeric(14,4),
  gross_margin_rate numeric(10,6),
  currency_code text,
  source_payload jsonb not null default '{}'::jsonb,
  created_at timestamptz not null default now()
);

create unique index if not exists idx_sku_margin_daily_unique
  on sku_margin_daily (snapshot_date, sku);

create index if not exists idx_sku_margin_daily_sku
  on sku_margin_daily (sku, snapshot_date desc);

create table if not exists order_line_returns_daily (
  id uuid primary key default gen_random_uuid(),
  snapshot_date date not null,
  shopify_order_gid text,
  sku text,
  returned_quantity integer not null default 0,
  return_amount numeric(14,4) not null default 0,
  restock_fee numeric(14,4),
  source_payload jsonb not null default '{}'::jsonb,
  created_at timestamptz not null default now()
);

create index if not exists idx_order_line_returns_daily_sku
  on order_line_returns_daily (sku, snapshot_date desc);

create index if not exists idx_order_line_returns_daily_order
  on order_line_returns_daily (shopify_order_gid, snapshot_date desc);

create table if not exists attribution_confidence_daily (
  id uuid primary key default gen_random_uuid(),
  snapshot_date date not null,
  channel text not null,
  campaign_key text,
  confidence_score numeric(10,6) not null default 0,
  quality_bucket text not null default 'unknown',
  signals jsonb not null default '{}'::jsonb,
  created_at timestamptz not null default now()
);

create unique index if not exists idx_attribution_confidence_daily_unique
  on attribution_confidence_daily (snapshot_date, channel, coalesce(campaign_key, '__all__'));

create index if not exists idx_attribution_confidence_daily_score
  on attribution_confidence_daily (confidence_score desc, snapshot_date desc);

create table if not exists experiment_registry (
  id uuid primary key default gen_random_uuid(),
  experiment_key text not null unique,
  name text not null,
  initiative text not null,
  hypothesis text not null,
  decision_rule text,
  success_threshold numeric(14,4),
  failure_threshold numeric(14,4),
  status text not null default 'active',
  start_date date not null,
  end_date date,
  metadata jsonb not null default '{}'::jsonb,
  created_by text,
  created_at timestamptz not null default now()
);

create table if not exists experiment_assignments (
  id uuid primary key default gen_random_uuid(),
  experiment_key text not null,
  entity_key text not null,
  cohort text not null,
  assigned_at timestamptz not null default now(),
  metadata jsonb not null default '{}'::jsonb,
  constraint experiment_assignments_experiment_key_fkey
    foreign key (experiment_key)
    references experiment_registry (experiment_key)
    on delete cascade
);

create unique index if not exists idx_experiment_assignments_unique
  on experiment_assignments (experiment_key, entity_key);

create table if not exists experiment_outcomes (
  id uuid primary key default gen_random_uuid(),
  experiment_key text not null,
  metric_name text not null,
  observed_lift numeric(14,6) not null default 0,
  sample_size bigint not null default 0,
  status text not null default 'observing',
  measured_at timestamptz not null default now(),
  metadata jsonb not null default '{}'::jsonb,
  constraint experiment_outcomes_experiment_key_fkey
    foreign key (experiment_key)
    references experiment_registry (experiment_key)
    on delete cascade
);

create index if not exists idx_experiment_outcomes_experiment_measured
  on experiment_outcomes (experiment_key, measured_at desc);

create table if not exists negative_registry (
  id uuid primary key default gen_random_uuid(),
  term text not null,
  scope text not null,
  source_policy text not null,
  confidence numeric(5,4) not null default 0,
  reason_codes text[] not null default '{}',
  rollback_token text,
  active boolean not null default true,
  metadata jsonb not null default '{}'::jsonb,
  created_by text,
  created_at timestamptz not null default now(),
  deactivated_at timestamptz,
  deactivated_by text
);

create index if not exists idx_negative_registry_scope_active
  on negative_registry (scope, active, created_at desc);

create index if not exists idx_negative_registry_term
  on negative_registry (term, created_at desc);

create table if not exists search_buildout_recommendations (
  id uuid primary key default gen_random_uuid(),
  search_term text not null,
  custom_label_0 text,
  recommended_search_tier text not null,
  status text not null default 'candidate',
  confidence numeric(5,4) not null default 0,
  metadata jsonb not null default '{}'::jsonb,
  approved_by text,
  approved_at timestamptz,
  created_at timestamptz not null default now()
);

create index if not exists idx_search_buildout_recommendations_status_created
  on search_buildout_recommendations (status, created_at desc);

create index if not exists idx_search_buildout_recommendations_term
  on search_buildout_recommendations (search_term, created_at desc);

create table if not exists operator_review_audit (
  id uuid primary key default gen_random_uuid(),
  queue_name text not null,
  entity_key text not null,
  action text not null,
  before_state jsonb,
  after_state jsonb,
  actor text,
  created_at timestamptz not null default now()
);

create index if not exists idx_operator_review_audit_queue_created
  on operator_review_audit (queue_name, created_at desc);

create index if not exists idx_operator_review_audit_entity
  on operator_review_audit (entity_key, created_at desc);

-- Constraints

do $$
begin
  if not exists (
    select 1 from pg_constraint where conname = 'term_intent_state_intent_class_check'
  ) then
    alter table term_intent_state
      add constraint term_intent_state_intent_class_check
      check (
        intent_class in (
          'BRAND_CORE',
          'PRODUCT_HIGH',
          'CATEGORY_MID',
          'DISCOVERY_LOW',
          'COMPETITOR',
          'INFO_ASSIST',
          'MISMATCH',
          'RISK_POLICY'
        )
      );
  end if;
end $$;

do $$
begin
  if not exists (
    select 1 from pg_constraint where conname = 'term_intent_state_route_action_check'
  ) then
    alter table term_intent_state
      add constraint term_intent_state_route_action_check
      check (
        route_action in (
          'funnel',
          'global_block',
          'competitor',
          'branded',
          'search_discovery',
          'search_exact_candidate',
          'observe_only'
        )
      );
  end if;
end $$;

do $$
begin
  if not exists (
    select 1 from pg_constraint where conname = 'policy_action_execution_status_check'
  ) then
    alter table policy_action_execution_log
      add constraint policy_action_execution_status_check
      check (status in ('planned', 'applied', 'rolled_back', 'failed', 'cancelled'));
  end if;
end $$;

do $$
begin
  if not exists (
    select 1 from pg_constraint where conname = 'attribution_confidence_daily_bucket_check'
  ) then
    alter table attribution_confidence_daily
      add constraint attribution_confidence_daily_bucket_check
      check (quality_bucket in ('high', 'medium', 'low', 'unknown'));
  end if;
end $$;

do $$
begin
  if not exists (
    select 1 from pg_constraint where conname = 'experiment_registry_status_check'
  ) then
    alter table experiment_registry
      add constraint experiment_registry_status_check
      check (status in ('draft', 'active', 'paused', 'completed', 'cancelled'));
  end if;
end $$;

do $$
begin
  if not exists (
    select 1 from pg_constraint where conname = 'experiment_outcomes_status_check'
  ) then
    alter table experiment_outcomes
      add constraint experiment_outcomes_status_check
      check (status in ('observing', 'success', 'failure', 'inconclusive'));
  end if;
end $$;

do $$
begin
  if not exists (
    select 1 from pg_constraint where conname = 'search_buildout_reco_tier_check'
  ) then
    alter table search_buildout_recommendations
      add constraint search_buildout_reco_tier_check
      check (recommended_search_tier in ('broad', 'phrase', 'exact'));
  end if;
end $$;

do $$
begin
  if not exists (
    select 1 from pg_constraint where conname = 'search_buildout_reco_status_check'
  ) then
    alter table search_buildout_recommendations
      add constraint search_buildout_reco_status_check
      check (status in ('candidate', 'approved', 'applied', 'rejected', 'paused'));
  end if;
end $$;

-- RLS and permissive policies for dashboard/admin workflows.
alter table intent_taxonomy_versions enable row level security;
alter table term_intent_state enable row level security;
alter table policy_decision_log enable row level security;
alter table policy_action_execution_log enable row level security;
alter table policy_snapshots enable row level security;
alter table sku_margin_daily enable row level security;
alter table order_line_returns_daily enable row level security;
alter table attribution_confidence_daily enable row level security;
alter table experiment_registry enable row level security;
alter table experiment_assignments enable row level security;
alter table experiment_outcomes enable row level security;
alter table negative_registry enable row level security;
alter table search_buildout_recommendations enable row level security;
alter table operator_review_audit enable row level security;

drop policy if exists "Allow all access" on intent_taxonomy_versions;
drop policy if exists "Allow all access" on term_intent_state;
drop policy if exists "Allow all access" on policy_decision_log;
drop policy if exists "Allow all access" on policy_action_execution_log;
drop policy if exists "Allow all access" on policy_snapshots;
drop policy if exists "Allow all access" on sku_margin_daily;
drop policy if exists "Allow all access" on order_line_returns_daily;
drop policy if exists "Allow all access" on attribution_confidence_daily;
drop policy if exists "Allow all access" on experiment_registry;
drop policy if exists "Allow all access" on experiment_assignments;
drop policy if exists "Allow all access" on experiment_outcomes;
drop policy if exists "Allow all access" on negative_registry;
drop policy if exists "Allow all access" on search_buildout_recommendations;
drop policy if exists "Allow all access" on operator_review_audit;

create policy "Allow all access" on intent_taxonomy_versions for all using (true);
create policy "Allow all access" on term_intent_state for all using (true);
create policy "Allow all access" on policy_decision_log for all using (true);
create policy "Allow all access" on policy_action_execution_log for all using (true);
create policy "Allow all access" on policy_snapshots for all using (true);
create policy "Allow all access" on sku_margin_daily for all using (true);
create policy "Allow all access" on order_line_returns_daily for all using (true);
create policy "Allow all access" on attribution_confidence_daily for all using (true);
create policy "Allow all access" on experiment_registry for all using (true);
create policy "Allow all access" on experiment_assignments for all using (true);
create policy "Allow all access" on experiment_outcomes for all using (true);
create policy "Allow all access" on negative_registry for all using (true);
create policy "Allow all access" on search_buildout_recommendations for all using (true);
create policy "Allow all access" on operator_review_audit for all using (true);
