-- Optimization control plane tables
-- Phase 1 foundation: query intelligence, value graph, guardrails, and recommendation tracking.

create table if not exists query_intent_features (
  id uuid primary key default gen_random_uuid(),
  search_term text not null,
  custom_label_0 text not null,
  parser_version text not null default 'v1',
  product_object text,
  modifier_tokens text[] not null default '{}',
  use_case_tokens text[] not null default '{}',
  is_branded boolean not null default false,
  is_competitor boolean not null default false,
  has_mismatch_risk boolean not null default false,
  confidence numeric(5,4) not null default 0,
  extracted jsonb not null default '{}'::jsonb,
  created_at timestamptz not null default now()
);

create index if not exists idx_query_intent_features_term_label_created
  on query_intent_features (search_term, custom_label_0, created_at desc);

create table if not exists query_value_scores (
  id uuid primary key default gen_random_uuid(),
  search_term text not null,
  custom_label_0 text not null,
  score_version text not null default 'v1',
  expected_clicks numeric(12,4) not null default 0,
  expected_cvr numeric(10,6) not null default 0,
  expected_conversion_value numeric(14,4) not null default 0,
  expected_profit_proxy numeric(14,4) not null default 0,
  uncertainty numeric(10,6) not null default 1,
  impact_score numeric(14,4) not null default 0,
  model_inputs jsonb not null default '{}'::jsonb,
  created_at timestamptz not null default now()
);

create index if not exists idx_query_value_scores_term_label_created
  on query_value_scores (search_term, custom_label_0, created_at desc);

create index if not exists idx_query_value_scores_impact_created
  on query_value_scores (impact_score desc, created_at desc);

create table if not exists routing_recommendations (
  id uuid primary key default gen_random_uuid(),
  search_term text not null,
  custom_label_0 text not null,
  recommended_action text not null,
  recommended_tier text,
  reason_codes text[] not null default '{}',
  confidence numeric(5,4) not null default 0,
  review_status text not null default 'pending',
  accepted boolean,
  accepted_at timestamptz,
  accepted_by text,
  metadata jsonb not null default '{}'::jsonb,
  created_at timestamptz not null default now()
);

do $$
begin
  if not exists (
    select 1
    from pg_constraint
    where conname = 'routing_recommendations_action_check'
  ) then
    alter table routing_recommendations
      add constraint routing_recommendations_action_check
      check (recommended_action in ('global_block', 'competitor', 'branded', 'funnel'));
  end if;
end $$;

do $$
begin
  if not exists (
    select 1
    from pg_constraint
    where conname = 'routing_recommendations_tier_check'
  ) then
    alter table routing_recommendations
      add constraint routing_recommendations_tier_check
      check (
        recommended_tier is null
        or recommended_tier in ('campaign_negative', 'high', 'medium', 'low')
      );
  end if;
end $$;

do $$
begin
  if not exists (
    select 1
    from pg_constraint
    where conname = 'routing_recommendations_review_status_check'
  ) then
    alter table routing_recommendations
      add constraint routing_recommendations_review_status_check
      check (review_status in ('pending', 'accepted', 'rejected', 'expired'));
  end if;
end $$;

create index if not exists idx_routing_recommendations_term_label_created
  on routing_recommendations (search_term, custom_label_0, created_at desc);

create index if not exists idx_routing_recommendations_status_created
  on routing_recommendations (review_status, created_at desc);

create table if not exists roas_target_recommendations (
  id uuid primary key default gen_random_uuid(),
  custom_label_0 text not null,
  tier text not null,
  current_target_roas numeric(10,4) not null,
  recommended_target_roas numeric(10,4) not null,
  expected_value_delta numeric(14,4),
  expected_roas_delta numeric(12,6),
  confidence numeric(5,4) not null default 0,
  recommendation_window_start date,
  recommendation_window_end date,
  approved boolean,
  approved_at timestamptz,
  approved_by text,
  applied boolean not null default false,
  applied_at timestamptz,
  metadata jsonb not null default '{}'::jsonb,
  created_at timestamptz not null default now()
);

do $$
begin
  if not exists (
    select 1
    from pg_constraint
    where conname = 'roas_target_recommendations_tier_check'
  ) then
    alter table roas_target_recommendations
      add constraint roas_target_recommendations_tier_check
      check (tier in ('high', 'medium', 'low'));
  end if;
end $$;

create index if not exists idx_roas_target_reco_label_tier_created
  on roas_target_recommendations (custom_label_0, tier, created_at desc);

create index if not exists idx_roas_target_reco_applied_created
  on roas_target_recommendations (applied, created_at desc);

create table if not exists opportunity_clusters (
  id uuid primary key default gen_random_uuid(),
  cluster_key text not null,
  representative_terms text[] not null default '{}',
  custom_label_0 text,
  intent_theme text,
  attractiveness_score numeric(14,4) not null default 0,
  overlap_score numeric(10,6) not null default 0,
  launch_status text not null default 'candidate',
  estimated_clicks numeric(14,4),
  estimated_conversion_value numeric(14,4),
  metadata jsonb not null default '{}'::jsonb,
  created_at timestamptz not null default now()
);

do $$
begin
  if not exists (
    select 1
    from pg_constraint
    where conname = 'opportunity_clusters_launch_status_check'
  ) then
    alter table opportunity_clusters
      add constraint opportunity_clusters_launch_status_check
      check (launch_status in ('candidate', 'pilot', 'launched', 'rejected', 'archived'));
  end if;
end $$;

create unique index if not exists idx_opportunity_clusters_cluster_key_created
  on opportunity_clusters (cluster_key, created_at);

create index if not exists idx_opportunity_clusters_attractiveness_created
  on opportunity_clusters (attractiveness_score desc, created_at desc);

create table if not exists ga4_campaign_daily (
  id uuid primary key default gen_random_uuid(),
  property_id text not null,
  report_date date not null,
  channel_group text not null,
  campaign_name text not null,
  sessions bigint not null default 0,
  transactions bigint not null default 0,
  purchase_revenue numeric(14,4) not null default 0,
  source_payload jsonb not null default '{}'::jsonb,
  created_at timestamptz not null default now()
);

create unique index if not exists idx_ga4_campaign_daily_unique
  on ga4_campaign_daily (property_id, report_date, channel_group, campaign_name);

create index if not exists idx_ga4_campaign_daily_report_date
  on ga4_campaign_daily (report_date desc);

create table if not exists ga4_attribution_quality_daily (
  id uuid primary key default gen_random_uuid(),
  property_id text not null,
  report_date date not null,
  unattributed_revenue_share numeric(10,6) not null default 0,
  unassigned_channel_revenue_share numeric(10,6) not null default 0,
  not_set_campaign_revenue_share numeric(10,6) not null default 0,
  reconciliation_delta numeric(14,4),
  quality_score numeric(10,6) not null default 0,
  source_payload jsonb not null default '{}'::jsonb,
  created_at timestamptz not null default now()
);

create unique index if not exists idx_ga4_attribution_quality_daily_unique
  on ga4_attribution_quality_daily (property_id, report_date);

create index if not exists idx_ga4_attribution_quality_daily_date
  on ga4_attribution_quality_daily (report_date desc);

create table if not exists shopify_order_facts (
  id uuid primary key default gen_random_uuid(),
  shopify_order_gid text not null,
  order_number text,
  customer_gid text,
  order_created_at timestamptz not null,
  currency_code text,
  total_price numeric(14,4) not null default 0,
  subtotal_price numeric(14,4),
  total_discounts numeric(14,4),
  source_name text,
  tags text[] not null default '{}',
  source_payload jsonb not null default '{}'::jsonb,
  created_at timestamptz not null default now()
);

create unique index if not exists idx_shopify_order_facts_order_gid
  on shopify_order_facts (shopify_order_gid);

create index if not exists idx_shopify_order_facts_created_at
  on shopify_order_facts (order_created_at desc);

create index if not exists idx_shopify_order_facts_customer
  on shopify_order_facts (customer_gid);

create table if not exists shopify_order_line_facts (
  id uuid primary key default gen_random_uuid(),
  shopify_order_gid text not null,
  line_item_gid text,
  sku text,
  variant_gid text,
  product_gid text,
  quantity integer not null default 0,
  net_line_revenue numeric(14,4) not null default 0,
  currency_code text,
  custom_label_0 text,
  source_payload jsonb not null default '{}'::jsonb,
  created_at timestamptz not null default now()
);

create index if not exists idx_shopify_order_line_facts_order_gid
  on shopify_order_line_facts (shopify_order_gid);

create index if not exists idx_shopify_order_line_facts_sku
  on shopify_order_line_facts (sku);

create index if not exists idx_shopify_order_line_facts_custom_label
  on shopify_order_line_facts (custom_label_0);

create table if not exists shopify_customer_value_snapshots (
  id uuid primary key default gen_random_uuid(),
  customer_gid text not null,
  snapshot_date date not null default current_date,
  orders_30d integer not null default 0,
  orders_90d integer not null default 0,
  orders_365d integer not null default 0,
  revenue_30d numeric(14,4) not null default 0,
  revenue_90d numeric(14,4) not null default 0,
  revenue_365d numeric(14,4) not null default 0,
  avg_order_value_365d numeric(14,4),
  repeat_buyer boolean not null default false,
  source_payload jsonb not null default '{}'::jsonb,
  created_at timestamptz not null default now()
);

create unique index if not exists idx_shopify_customer_value_snapshots_unique
  on shopify_customer_value_snapshots (customer_gid, snapshot_date);

create index if not exists idx_shopify_customer_value_snapshots_date
  on shopify_customer_value_snapshots (snapshot_date desc);

create table if not exists audience_watchlist_snapshots (
  id uuid primary key default gen_random_uuid(),
  source_platform text not null default 'ga4',
  segment_name text not null,
  segment_key text not null,
  score numeric(14,4) not null default 0,
  risk_level text not null default 'low',
  recommendation_status text not null default 'observe',
  sessions bigint,
  transactions bigint,
  purchase_revenue numeric(14,4),
  conversion_rate numeric(10,6),
  metadata jsonb not null default '{}'::jsonb,
  snapshot_date date not null default current_date,
  created_at timestamptz not null default now()
);

do $$
begin
  if not exists (
    select 1
    from pg_constraint
    where conname = 'audience_watchlist_snapshots_risk_check'
  ) then
    alter table audience_watchlist_snapshots
      add constraint audience_watchlist_snapshots_risk_check
      check (risk_level in ('low', 'medium', 'high', 'critical'));
  end if;
end $$;

do $$
begin
  if not exists (
    select 1
    from pg_constraint
    where conname = 'audience_watchlist_snapshots_reco_status_check'
  ) then
    alter table audience_watchlist_snapshots
      add constraint audience_watchlist_snapshots_reco_status_check
      check (recommendation_status in ('observe', 'exclude', 'target', 'review'));
  end if;
end $$;

create index if not exists idx_audience_watchlist_snapshots_date
  on audience_watchlist_snapshots (snapshot_date desc, score desc);

create table if not exists guardrail_incidents (
  id uuid primary key default gen_random_uuid(),
  rule_id text not null,
  severity text not null default 'medium',
  status text not null default 'open',
  impacted_entities jsonb not null default '[]'::jsonb,
  message text not null,
  suggested_action text,
  acknowledged_at timestamptz,
  acknowledged_by text,
  resolved_at timestamptz,
  metadata jsonb not null default '{}'::jsonb,
  created_at timestamptz not null default now()
);

do $$
begin
  if not exists (
    select 1
    from pg_constraint
    where conname = 'guardrail_incidents_severity_check'
  ) then
    alter table guardrail_incidents
      add constraint guardrail_incidents_severity_check
      check (severity in ('low', 'medium', 'high', 'critical'));
  end if;
end $$;

do $$
begin
  if not exists (
    select 1
    from pg_constraint
    where conname = 'guardrail_incidents_status_check'
  ) then
    alter table guardrail_incidents
      add constraint guardrail_incidents_status_check
      check (status in ('open', 'acknowledged', 'resolved', 'ignored'));
  end if;
end $$;

create index if not exists idx_guardrail_incidents_status_created
  on guardrail_incidents (status, created_at desc);

create index if not exists idx_guardrail_incidents_severity_created
  on guardrail_incidents (severity, created_at desc);

-- Enable RLS + permissive policy for dashboard operations consistency.
alter table query_intent_features enable row level security;
alter table query_value_scores enable row level security;
alter table routing_recommendations enable row level security;
alter table roas_target_recommendations enable row level security;
alter table opportunity_clusters enable row level security;
alter table ga4_campaign_daily enable row level security;
alter table ga4_attribution_quality_daily enable row level security;
alter table shopify_order_facts enable row level security;
alter table shopify_order_line_facts enable row level security;
alter table shopify_customer_value_snapshots enable row level security;
alter table audience_watchlist_snapshots enable row level security;
alter table guardrail_incidents enable row level security;

drop policy if exists "Allow all access" on query_intent_features;
drop policy if exists "Allow all access" on query_value_scores;
drop policy if exists "Allow all access" on routing_recommendations;
drop policy if exists "Allow all access" on roas_target_recommendations;
drop policy if exists "Allow all access" on opportunity_clusters;
drop policy if exists "Allow all access" on ga4_campaign_daily;
drop policy if exists "Allow all access" on ga4_attribution_quality_daily;
drop policy if exists "Allow all access" on shopify_order_facts;
drop policy if exists "Allow all access" on shopify_order_line_facts;
drop policy if exists "Allow all access" on shopify_customer_value_snapshots;
drop policy if exists "Allow all access" on audience_watchlist_snapshots;
drop policy if exists "Allow all access" on guardrail_incidents;

create policy "Allow all access" on query_intent_features for all using (true);
create policy "Allow all access" on query_value_scores for all using (true);
create policy "Allow all access" on routing_recommendations for all using (true);
create policy "Allow all access" on roas_target_recommendations for all using (true);
create policy "Allow all access" on opportunity_clusters for all using (true);
create policy "Allow all access" on ga4_campaign_daily for all using (true);
create policy "Allow all access" on ga4_attribution_quality_daily for all using (true);
create policy "Allow all access" on shopify_order_facts for all using (true);
create policy "Allow all access" on shopify_order_line_facts for all using (true);
create policy "Allow all access" on shopify_customer_value_snapshots for all using (true);
create policy "Allow all access" on audience_watchlist_snapshots for all using (true);
create policy "Allow all access" on guardrail_incidents for all using (true);
