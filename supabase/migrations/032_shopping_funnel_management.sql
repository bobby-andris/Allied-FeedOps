-- Shopping funnel management staging + error tracking tables
-- Phase 2 dashboard module: Shopping Funnel Search Terms Management

create table if not exists search_term_decisions (
  id uuid primary key default gen_random_uuid(),
  search_term text not null,
  action_type text not null,
  custom_label_0 text,
  tier text,
  source_campaign text,
  source_tier text,
  impressions integer,
  clicks integer,
  cost_micros bigint,
  conversions numeric(10,2),
  conversions_value numeric(10,2),
  posted_to_google_ads boolean not null default false,
  posted_at timestamptz,
  created_at timestamptz not null default now(),
  created_by text
);

create index if not exists idx_search_term_decisions_posted
  on search_term_decisions (posted_to_google_ads);

create index if not exists idx_search_term_decisions_created_at
  on search_term_decisions (created_at desc);

create index if not exists idx_search_term_decisions_search_term
  on search_term_decisions (search_term);

do $$
begin
  if not exists (
    select 1
    from pg_constraint
    where conname = 'search_term_decisions_action_type_check'
  ) then
    alter table search_term_decisions
      add constraint search_term_decisions_action_type_check
      check (action_type in ('global_block', 'competitor', 'branded', 'funnel'));
  end if;
end $$;

do $$
begin
  if not exists (
    select 1
    from pg_constraint
    where conname = 'search_term_decisions_tier_check'
  ) then
    alter table search_term_decisions
      add constraint search_term_decisions_tier_check
      check (
        tier is null
        or tier in ('campaign_negative', 'high', 'medium', 'low')
      );
  end if;
end $$;

create table if not exists google_ads_api_errors (
  id uuid primary key default gen_random_uuid(),
  search_term text not null,
  action_attempted text not null,
  error_message text,
  error_code text,
  campaign_name text,
  ad_group_name text,
  retry_count integer not null default 0,
  resolved boolean not null default false,
  created_at timestamptz not null default now()
);

create index if not exists idx_google_ads_api_errors_resolved
  on google_ads_api_errors (resolved, created_at desc);

create index if not exists idx_google_ads_api_errors_search_term
  on google_ads_api_errors (search_term);
