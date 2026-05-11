-- ============================================================
-- Pro plan redizajn + uvođenje Premium plana (maj 2026)
-- Pokreni u Supabase SQL Editoru NAKON ostalih migracija.
--
-- Šta radi:
--   1. Pro plan: 1 agencija, 10 agenata, 6 meseci istorije.
--   2. Premium plan (100€): 1 agencija, neograničeno agenata,
--      12 meseci istorije, custom branding (logo na izveštajima).
--   3. Dodaje agencies.logo_url za upload logoa.
--
-- VAN SQL-A (uraditi ručno u Supabase Dashboard-u):
--   • Storage → New bucket: "agency-logos" (Public = ON)
--   • Bucket policy: insert/update/delete dozvoljen vlasniku
--     agencije (file path = "<agency_id>.png|jpg").
-- ============================================================

-- 1. Ažuriraj Pro plan na nove limite
UPDATE plans
SET max_agencies   = 1,
    max_agents     = 10,
    history_months = 6,
    price_eur      = 49
WHERE id = 'pro';

-- 2. Premium plan (100€)
INSERT INTO plans (
  id, name, price_eur,
  max_agencies, max_agents, history_months,
  ai_analysis, email_send,
  weekly_report, monthly_report, daily_report,
  pdf_export, custom_branding
) VALUES (
  'premium', 'Premium', 100,
  1, -1, 12,
  true, true,
  true, true, false,
  true, true
)
ON CONFLICT (id) DO UPDATE SET
  name            = EXCLUDED.name,
  price_eur       = EXCLUDED.price_eur,
  max_agencies    = EXCLUDED.max_agencies,
  max_agents      = EXCLUDED.max_agents,
  history_months  = EXCLUDED.history_months,
  ai_analysis     = EXCLUDED.ai_analysis,
  email_send      = EXCLUDED.email_send,
  weekly_report   = EXCLUDED.weekly_report,
  monthly_report  = EXCLUDED.monthly_report,
  daily_report    = EXCLUDED.daily_report,
  pdf_export      = EXCLUDED.pdf_export,
  custom_branding = EXCLUDED.custom_branding;

-- 3. Logo agencije (URL ka fajlu u storage bucket-u "agency-logos")
ALTER TABLE agencies
  ADD COLUMN IF NOT EXISTS logo_url TEXT;

-- ============================================================
-- POSLE pokretanja:
--   • Proveri:  SELECT id, price_eur, max_agents, history_months,
--               custom_branding FROM plans ORDER BY price_eur;
--   • Postojeće "pro" agencije sa >10 agenata: kontaktirati ručno.
--     SELECT a.id, a.name, COUNT(ag.id) AS cnt
--     FROM agencies a JOIN agents ag ON ag.agency_id = a.id
--     WHERE a.plan_id = 'pro' AND ag.active
--     GROUP BY a.id, a.name HAVING COUNT(ag.id) > 10;
-- ============================================================
