-- GA4 attribution forensics diagnostics tables
-- Read-only telemetry snapshots for root-cause analysis and reconciliation.

create table if not exists ga4_source_medium_daily (
  id uuid primary key default gen_random_uuid(),
  property_id text not null,
  report_date date not null,
  source_medium text not null,
  quality_bucket text not null,
  sessions bigint not null default 0,
  transactions bigint not null default 0,
  purchase_revenue numeric(14,4) not null default 0,
  revenue_share numeric(10,6) not null default 0,
  session_share numeric(10,6) not null default 0,
  source_payload jsonb not null default '{}'::jsonb,
  created_at timestamptz not null default now()
);

do $$
begin
  if not exists (
    select 1
    from pg_constraint
    where conname = 'ga4_source_medium_daily_quality_bucket_check'
  ) then
    alter table ga4_source_medium_daily
      add constraint ga4_source_medium_daily_quality_bucket_check
      check (quality_bucket in ('not_set', 'data_not_available', 'valid'));
  end if;
end $$;

create unique index if not exists idx_ga4_source_medium_daily_unique
  on ga4_source_medium_daily (property_id, report_date, quality_bucket, source_medium);

create index if not exists idx_ga4_source_medium_daily_report_date
  on ga4_source_medium_daily (report_date desc);

create table if not exists ga4_landing_page_quality_daily (
  id uuid primary key default gen_random_uuid(),
  property_id text not null,
  report_date date not null,
  landing_page text not null,
  quality_bucket text not null,
  sessions bigint not null default 0,
  transactions bigint not null default 0,
  purchase_revenue numeric(14,4) not null default 0,
  revenue_share numeric(10,6) not null default 0,
  session_share numeric(10,6) not null default 0,
  source_payload jsonb not null default '{}'::jsonb,
  created_at timestamptz not null default now()
);

do $$
begin
  if not exists (
    select 1
    from pg_constraint
    where conname = 'ga4_landing_page_quality_daily_quality_bucket_check'
  ) then
    alter table ga4_landing_page_quality_daily
      add constraint ga4_landing_page_quality_daily_quality_bucket_check
      check (quality_bucket in ('blank', 'not_set', 'valid'));
  end if;
end $$;

create unique index if not exists idx_ga4_landing_page_quality_daily_unique
  on ga4_landing_page_quality_daily (property_id, report_date, quality_bucket, landing_page);

create index if not exists idx_ga4_landing_page_quality_daily_report_date
  on ga4_landing_page_quality_daily (report_date desc);

create table if not exists ga4_attribution_root_cause_daily (
  id uuid primary key default gen_random_uuid(),
  property_id text not null,
  report_date date not null,
  root_cause_type text not null,
  root_cause_key text not null,
  sessions bigint not null default 0,
  transactions bigint not null default 0,
  purchase_revenue numeric(14,4) not null default 0,
  revenue_share numeric(10,6) not null default 0,
  session_share numeric(10,6) not null default 0,
  source_payload jsonb not null default '{}'::jsonb,
  created_at timestamptz not null default now()
);

do $$
begin
  if not exists (
    select 1
    from pg_constraint
    where conname = 'ga4_attribution_root_cause_daily_type_check'
  ) then
    alter table ga4_attribution_root_cause_daily
      add constraint ga4_attribution_root_cause_daily_type_check
      check (root_cause_type in ('source_medium', 'campaign_pattern', 'landing_page'));
  end if;
end $$;

create unique index if not exists idx_ga4_attribution_root_cause_daily_unique
  on ga4_attribution_root_cause_daily (property_id, report_date, root_cause_type, root_cause_key);

create index if not exists idx_ga4_attribution_root_cause_daily_report_date
  on ga4_attribution_root_cause_daily (report_date desc);

create table if not exists ga4_shopify_reconciliation_daily (
  id uuid primary key default gen_random_uuid(),
  property_id text not null,
  report_date date not null,
  ga4_revenue numeric(14,4) not null default 0,
  shopify_revenue numeric(14,4) not null default 0,
  revenue_delta numeric(14,4) not null default 0,
  revenue_ratio numeric(12,6),
  order_count bigint not null default 0,
  source_payload jsonb not null default '{}'::jsonb,
  created_at timestamptz not null default now()
);

create unique index if not exists idx_ga4_shopify_reconciliation_daily_unique
  on ga4_shopify_reconciliation_daily (property_id, report_date);

create index if not exists idx_ga4_shopify_reconciliation_daily_report_date
  on ga4_shopify_reconciliation_daily (report_date desc);

alter table ga4_source_medium_daily enable row level security;
alter table ga4_landing_page_quality_daily enable row level security;
alter table ga4_attribution_root_cause_daily enable row level security;
alter table ga4_shopify_reconciliation_daily enable row level security;

drop policy if exists "Allow all access" on ga4_source_medium_daily;
drop policy if exists "Allow all access" on ga4_landing_page_quality_daily;
drop policy if exists "Allow all access" on ga4_attribution_root_cause_daily;
drop policy if exists "Allow all access" on ga4_shopify_reconciliation_daily;

create policy "Allow all access" on ga4_source_medium_daily for all using (true);
create policy "Allow all access" on ga4_landing_page_quality_daily for all using (true);
create policy "Allow all access" on ga4_attribution_root_cause_daily for all using (true);
create policy "Allow all access" on ga4_shopify_reconciliation_daily for all using (true);
