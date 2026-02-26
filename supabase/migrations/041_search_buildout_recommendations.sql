-- Standalone table for Search Governance candidates
-- Extracted from deferred 035b migration (only this table needed now)

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
  created_at timestamptz not null default now(),
  constraint search_buildout_reco_tier_check
    check (recommended_search_tier in ('broad', 'phrase', 'exact')),
  constraint search_buildout_reco_status_check
    check (status in ('candidate', 'approved', 'applied', 'rejected', 'paused')),
  constraint search_buildout_reco_term_unique unique (search_term)
);

create index if not exists idx_search_buildout_recommendations_status_created
  on search_buildout_recommendations (status, created_at desc);

create index if not exists idx_search_buildout_recommendations_term
  on search_buildout_recommendations (search_term, created_at desc);

-- RLS with permissive policy for dashboard access
alter table search_buildout_recommendations enable row level security;
drop policy if exists "Allow all access" on search_buildout_recommendations;
create policy "Allow all access" on search_buildout_recommendations for all using (true);
