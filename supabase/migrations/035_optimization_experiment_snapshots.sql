-- Optimization experiment instrumentation snapshots
-- Stores guardrail rollout decisions and supporting metrics over time.

create table if not exists optimization_experiment_snapshots (
  id uuid primary key default gen_random_uuid(),
  experiment_key text not null,
  window_start date not null,
  window_end date not null,
  decision_status text not null,
  confidence numeric(10,6) not null default 0,
  blocking_rules jsonb not null default '[]'::jsonb,
  metrics jsonb not null default '{}'::jsonb,
  created_at timestamptz not null default now()
);

do $$
begin
  if not exists (
    select 1
    from pg_constraint
    where conname = 'optimization_experiment_snapshots_decision_status_check'
  ) then
    alter table optimization_experiment_snapshots
      add constraint optimization_experiment_snapshots_decision_status_check
      check (decision_status in ('go', 'hold', 'blocked'));
  end if;
end $$;

create index if not exists idx_optimization_experiment_snapshots_key_created
  on optimization_experiment_snapshots (experiment_key, created_at desc);

create index if not exists idx_optimization_experiment_snapshots_window
  on optimization_experiment_snapshots (window_end desc, window_start desc);

alter table optimization_experiment_snapshots enable row level security;

drop policy if exists "Allow all access" on optimization_experiment_snapshots;
create policy "Allow all access" on optimization_experiment_snapshots for all using (true);
