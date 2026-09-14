-- ============================================================
-- AI-improves-itself — schéma Supabase (Postgres)
-- Phase 2 : migrer les données locales (core/data/*.json) ici.
-- Exécuter dans SQL Editor de Supabase, puis renseigner
-- SUPABASE_URL / SUPABASE_ANON_KEY / SUPABASE_SERVICE_KEY dans .env
-- ============================================================

-- --- Prompt système (versionné, modifiable par l'IA) ---
create table if not exists prompts (
  id          text primary key,          -- 'main', 'code', 'recherche'...
  scope       text not null default 'global',
  version     int  not null default 1,
  content     text not null,
  updated_at  timestamptz not null default now(),
  updated_by  text not null default 'seed'
);

create table if not exists prompt_versions (
  id         bigint generated always as identity primary key,
  prompt_id  text not null references prompts(id),
  version    int  not null,
  content    text not null,
  reason     text,
  trigger    text,
  author     text not null default 'ai',   -- 'ai' | 'human'
  created_at timestamptz not null default now()
);

-- --- Skills (l'IA peut en proposer, le dev implémente) ---
create table if not exists skills (
  id          text primary key,
  name        text not null,
  description text,
  params      jsonb,
  created_at  timestamptz not null default now(),
  updated_at  timestamptz not null default now()
);

-- --- Page /request : file de requêtes (IA -> dev ET humain -> dev) ---
create table if not exists dev_requests (
  id          uuid primary key default gen_random_uuid(),
  title       text not null,
  description text,
  type        text not null default 'other',  -- feature | ui | bug | prompt_update | other
  from_role   text not null default 'human',  -- 'ai' | 'human'
  status      text not null default 'open',   -- open | done | rejected
  created_at  timestamptz not null default now()
);

-- --- Recherche : tâches (exécutées par Colab / le service Chromium) ---
create table if not exists research_tasks (
  id         uuid primary key default gen_random_uuid(),
  kind       text not null,                 -- 'search' | 'fetch'
  target     text not null,                 -- requête ou URL
  reason     text,
  by         text not null default 'ai',    -- 'ai' | 'human'
  status     text not null default 'pending', -- pending | processing | done | failed
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now()
);

-- --- Recherche : résultats (renvoyés par Colab / le scraper) ---
create table if not exists research_results (
  id         uuid primary key default gen_random_uuid(),
  task_id    uuid references research_tasks(id),
  kind       text not null,                 -- 'search' | 'fetch' | 'note'
  data       jsonb not null,
  status     text not null default 'done',
  created_at timestamptz not null default now()
);

-- --- Base de connaissances ("base de données") ---
create table if not exists knowledge (
  id         uuid primary key default gen_random_uuid(),
  title      text not null,
  category   text,
  date       date,
  summary    text,
  source     text,
  created_at timestamptz not null default now()
);

-- Index utiles
create index if not exists idx_prompt_versions_prompt on prompt_versions(prompt_id, version desc);
create index if not exists idx_dev_requests_status on dev_requests(status, created_at desc);
create index if not exists idx_research_tasks_status on research_tasks(status, created_at desc);
create index if not exists idx_knowledge_date on knowledge(date desc);

-- RLS : lecture ouverte (recherche), écriture via clé service (serveur).
alter table prompts          enable row level security;
alter table prompt_versions  enable row level security;
alter table skills           enable row level security;
alter table dev_requests     enable row level security;
alter table research_tasks   enable row level security;
alter table research_results enable row level security;
alter table knowledge        enable row level security;

create policy "read all" on prompts          for select using (true);
create policy "read all" on prompt_versions  for select using (true);
create policy "read all" on skills           for select using (true);
create policy "read all" on dev_requests     for select using (true);
create policy "read all" on research_tasks   for select using (true);
create policy "read all" on research_results for select using (true);
create policy "read all" on knowledge        for select using (true);
-- Les INSERT/UPDATE se font via SUPABASE_SERVICE_KEY (bypass RLS côté serveur).
