-- Migration 039: routing_recommendations table with upsert support
-- Creates table IF NOT EXISTS (safe if 033b was partially applied)
-- Adds unique constraint on (search_term, custom_label_0) for upsert

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

-- Check constraints (idempotent)
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

-- Unique constraint for upsert support (NEW - not in 033b)
do $$
begin
  if not exists (
    select 1 from pg_constraint
    where conname = 'routing_recommendations_term_label_unique'
  ) then
    alter table routing_recommendations
      add constraint routing_recommendations_term_label_unique
      unique (search_term, custom_label_0);
  end if;
end $$;

-- Indexes from 033b
create index if not exists idx_routing_recommendations_term_label_created
  on routing_recommendations (search_term, custom_label_0, created_at desc);

create index if not exists idx_routing_recommendations_status_created
  on routing_recommendations (review_status, created_at desc);

-- RLS + permissive policy
alter table routing_recommendations enable row level security;

drop policy if exists "Allow all access" on routing_recommendations;
create policy "Allow all access" on routing_recommendations for all using (true);
