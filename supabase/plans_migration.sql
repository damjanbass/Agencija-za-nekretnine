-- ============================================================
-- Planovi (SaaS tier-ovi)
-- Pokreni u Supabase SQL Editoru
-- ============================================================

create table if not exists plans (
  id               text primary key,   -- 'free' | 'basic' | 'pro' | 'premium'
  name             text not null,
  price_eur        int  not null,
  max_agencies     int  not null,      -- -1 = neograničeno
  max_agents       int  not null,      -- -1 = neograničeno
  history_months   int  not null,      -- -1 = neograničeno
  ai_analysis      boolean not null default false,
  email_send       boolean not null default false,
  weekly_report    boolean not null default true,
  monthly_report   boolean not null default false,
  daily_report     boolean not null default false,
  pdf_export       boolean not null default false,
  custom_branding  boolean not null default false
);

alter table plans disable row level security;

-- Seed planovi
insert into plans values
  ('free',    'Free',    0,   1,  3,  1,  false, false, true,  false, false, false, false),
  ('basic',   'Basic',   150, 1,  5,  3,  true,  true,  true,  false, false, false, false),
  ('pro',     'Pro',     300, 3,  15, 12, true,  true,  true,  true,  false, true,  false),
  ('premium', 'Premium', 500, -1, -1, -1, true,  true,  true,  true,  true,  true,  true)
on conflict (id) do update set
  name            = excluded.name,
  price_eur       = excluded.price_eur,
  max_agencies    = excluded.max_agencies,
  max_agents      = excluded.max_agents,
  history_months  = excluded.history_months,
  ai_analysis     = excluded.ai_analysis,
  email_send      = excluded.email_send,
  weekly_report   = excluded.weekly_report,
  monthly_report  = excluded.monthly_report,
  daily_report    = excluded.daily_report,
  pdf_export      = excluded.pdf_export,
  custom_branding = excluded.custom_branding;

-- Dodaj plan_id na agencies
alter table agencies
  add column if not exists plan_id text not null default 'free'
  references plans(id);

-- Demo agencija → basic plan
update agencies
set plan_id = 'basic'
where id = 'aaaaaaaa-0000-0000-0000-000000000001';
