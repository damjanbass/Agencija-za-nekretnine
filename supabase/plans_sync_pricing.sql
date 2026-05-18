-- ============================================================
-- Sinhronizacija cena planova sa UI-em (maj 2026)
-- Pokreni u Supabase SQL Editoru.
--
-- UI prikazuje: Basic=29€, Pro=79€, Premium=149€
-- ============================================================

-- Osiguraj da Free plan postoji (koristi ga trigger i effective_plan_id)
INSERT INTO plans (
  id, name, price_eur,
  max_agencies, max_agents, max_listings, history_months,
  ai_analysis, email_send,
  weekly_report, monthly_report, daily_report,
  pdf_export, custom_branding
) VALUES (
  'free', 'Free', 0,
  1, 3, 5, 1,
  true, true,
  true, false, false,
  false, false
)
ON CONFLICT (id) DO UPDATE SET
  max_agents     = EXCLUDED.max_agents,
  max_listings   = EXCLUDED.max_listings,
  history_months = EXCLUDED.history_months;

-- Basic: 29€, do 3 agenta, 50 oglasa, 1 mesec istorije
UPDATE plans SET
  price_eur      = 29,
  max_agents     = 3,
  max_listings   = 50,
  history_months = 1,
  monthly_report = false,
  pdf_export     = false,
  custom_branding = false
WHERE id = 'basic';

-- Pro: 79€, do 10 agenata, 100 oglasa, 6 meseci istorije
UPDATE plans SET
  price_eur      = 79,
  max_agents     = 10,
  max_listings   = 100,
  history_months = 6,
  monthly_report = true,
  pdf_export     = true,
  custom_branding = false
WHERE id = 'pro';

-- Premium: 149€, neograničeno, 12 meseci istorije, custom branding
UPDATE plans SET
  price_eur      = 149,
  max_agents     = -1,
  max_listings   = -1,
  history_months = 12,
  monthly_report = true,
  pdf_export     = true,
  custom_branding = true
WHERE id = 'premium';

