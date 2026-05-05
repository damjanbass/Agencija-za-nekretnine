-- ============================================================
-- Demo podaci za prvu agenciju
-- Pokreni NAKON schema.sql
-- ============================================================

-- Agencija
insert into agencies (id, name, email, revenue_goal)
values (
  'aaaaaaaa-0000-0000-0000-000000000001',
  'Agencija Prima',
  'vlasnik@primakretnine.rs',
  5000
)
on conflict (email) do nothing;

-- Agenti
insert into agents (id, agency_id, name) values
  ('bbbbbbbb-0000-0000-0000-000000000001', 'aaaaaaaa-0000-0000-0000-000000000001', 'Marko Petrović'),
  ('bbbbbbbb-0000-0000-0000-000000000002', 'aaaaaaaa-0000-0000-0000-000000000001', 'Ana Nikolić'),
  ('bbbbbbbb-0000-0000-0000-000000000003', 'aaaaaaaa-0000-0000-0000-000000000001', 'Jovan Đorđević'),
  ('bbbbbbbb-0000-0000-0000-000000000004', 'aaaaaaaa-0000-0000-0000-000000000001', 'Milica Stojanović')
on conflict do nothing;

-- Nedeljni KPI (prošla nedelja)
insert into weekly_kpis
  (agency_id, week_start, active_listings, new_listings, inquiries, contracts_sale, contracts_rent, revenue)
values
  ('aaaaaaaa-0000-0000-0000-000000000001',
   date_trunc('week', current_date - interval '7 days')::date,
   47, 5, 83, 3, 7, 4200),
  -- nedelja pre toga (za % poređenje)
  ('aaaaaaaa-0000-0000-0000-000000000001',
   date_trunc('week', current_date - interval '14 days')::date,
   42, 3, 71, 2, 5, 3600)
on conflict (agency_id, week_start) do nothing;

-- Upiti po izvoru (prošla nedelja)
insert into inquiry_sources (agency_id, week_start, source, count) values
  ('aaaaaaaa-0000-0000-0000-000000000001',
   date_trunc('week', current_date - interval '7 days')::date,
   'Halo oglasi', 38),
  ('aaaaaaaa-0000-0000-0000-000000000001',
   date_trunc('week', current_date - interval '7 days')::date,
   '4zida', 21),
  ('aaaaaaaa-0000-0000-0000-000000000001',
   date_trunc('week', current_date - interval '7 days')::date,
   'Sajt agencije', 14),
  ('aaaaaaaa-0000-0000-0000-000000000001',
   date_trunc('week', current_date - interval '7 days')::date,
   'Instagram/ostalo', 10)
on conflict (agency_id, week_start, source) do nothing;

-- Performanse agenata (prošla nedelja)
insert into agent_performance (agent_id, agency_id, week_start, inquiries, contracts) values
  ('bbbbbbbb-0000-0000-0000-000000000001', 'aaaaaaaa-0000-0000-0000-000000000001',
   date_trunc('week', current_date - interval '7 days')::date, 31, 4),
  ('bbbbbbbb-0000-0000-0000-000000000002', 'aaaaaaaa-0000-0000-0000-000000000001',
   date_trunc('week', current_date - interval '7 days')::date, 27, 3),
  ('bbbbbbbb-0000-0000-0000-000000000003', 'aaaaaaaa-0000-0000-0000-000000000001',
   date_trunc('week', current_date - interval '7 days')::date, 18, 2),
  ('bbbbbbbb-0000-0000-0000-000000000004', 'aaaaaaaa-0000-0000-0000-000000000001',
   date_trunc('week', current_date - interval '7 days')::date, 7, 0)
on conflict (agent_id, week_start) do nothing;
