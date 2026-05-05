-- ============================================================
-- Nedeljni izveštaji za agencije za nekretnine
-- Pokreni ovo u Supabase SQL Editoru
-- ============================================================

-- Agencije (klijenti)
create table if not exists agencies (
  id           uuid primary key default gen_random_uuid(),
  name         text not null,
  email        text not null unique,
  revenue_goal numeric not null default 5000,
  active       boolean not null default true,
  created_at   timestamptz not null default now()
);

-- Nedeljni KPI snapshot (jedan red = jedna nedelja = jedna agencija)
create table if not exists weekly_kpis (
  id               uuid primary key default gen_random_uuid(),
  agency_id        uuid not null references agencies(id) on delete cascade,
  week_start       date not null,
  active_listings  int not null default 0,
  new_listings     int not null default 0,
  inquiries        int not null default 0,
  contracts_sale   int not null default 0,
  contracts_rent   int not null default 0,
  revenue          numeric not null default 0,
  created_at       timestamptz not null default now(),
  unique (agency_id, week_start)
);

-- Upiti po izvoru (za bar chart)
create table if not exists inquiry_sources (
  id         uuid primary key default gen_random_uuid(),
  agency_id  uuid not null references agencies(id) on delete cascade,
  week_start date not null,
  source     text not null,   -- 'Halo oglasi' | '4zida' | 'Sajt agencije' | 'Instagram/ostalo'
  count      int not null default 0,
  created_at timestamptz not null default now(),
  unique (agency_id, week_start, source)
);

-- Agenti
create table if not exists agents (
  id         uuid primary key default gen_random_uuid(),
  agency_id  uuid not null references agencies(id) on delete cascade,
  name       text not null,
  active     boolean not null default true,
  created_at timestamptz not null default now()
);

-- Nedeljne performanse agenata
create table if not exists agent_performance (
  id         uuid primary key default gen_random_uuid(),
  agent_id   uuid not null references agents(id) on delete cascade,
  agency_id  uuid not null references agencies(id) on delete cascade,
  week_start date not null,
  inquiries  int not null default 0,
  contracts  int not null default 0,
  created_at timestamptz not null default now(),
  unique (agent_id, week_start)
);

-- Sačuvani izveštaji (HTML, za arhivu)
create table if not exists reports (
  id         uuid primary key default gen_random_uuid(),
  agency_id  uuid not null references agencies(id) on delete cascade,
  week_start date not null,
  html       text,
  sent_at    timestamptz,
  created_at timestamptz not null default now(),
  unique (agency_id, week_start)
);

-- ============================================================
-- RLS: isključen za service_role (backend pristup)
-- Uključi ako dodaš korisničke naloge u budućnosti
-- ============================================================
alter table agencies         disable row level security;
alter table weekly_kpis      disable row level security;
alter table inquiry_sources  disable row level security;
alter table agents           disable row level security;
alter table agent_performance disable row level security;
alter table reports          disable row level security;
