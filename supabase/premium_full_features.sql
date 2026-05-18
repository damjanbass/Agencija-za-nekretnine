-- ============================================================
-- Premium plan — pun set funkcionalnosti
-- Pokreni u Supabase SQL Editoru.
--
-- Šta radi:
--   1. Osigurava da plans tabela ima sve potrebne feature kolone
--      (benchmark, agent_reports, max_listings).
--   2. Postavlja Premium plan na sve što je obećano na /pricing:
--        • neograničen broj agenata (max_agents = -1)
--        • neograničen broj oglasa (max_listings = -1)
--        • 12 meseci istorije izveštaja
--        • AI analiza, email, nedeljni + mesečni izveštaji
--        • pojedinačni izveštaji po agentu (agent_reports)
--        • PDF export
--        • benchmark / poređenje sa tržištem
--        • custom branding (logo na izveštajima)
--   3. Sinhronizuje cene i niže planove (Basic / Pro).
-- ============================================================

-- ── 1. Feature kolone (idempotent) ───────────────────────────
ALTER TABLE plans ADD COLUMN IF NOT EXISTS benchmark     BOOLEAN NOT NULL DEFAULT false;
ALTER TABLE plans ADD COLUMN IF NOT EXISTS agent_reports BOOLEAN NOT NULL DEFAULT false;
ALTER TABLE plans ADD COLUMN IF NOT EXISTS max_listings  INT     NOT NULL DEFAULT -1;

-- ── 2. Premium: sve uključeno ────────────────────────────────
INSERT INTO plans (
  id, name, price_eur,
  max_agencies, max_agents, max_listings, history_months,
  ai_analysis, email_send,
  weekly_report, monthly_report, daily_report,
  pdf_export, custom_branding,
  benchmark, agent_reports
) VALUES (
  'premium', 'Premium', 149,
  1, -1, -1, 12,
  true, true,
  true, true, false,
  true, true,
  true, true
)
ON CONFLICT (id) DO UPDATE SET
  name            = EXCLUDED.name,
  price_eur       = EXCLUDED.price_eur,
  max_agencies    = EXCLUDED.max_agencies,
  max_agents      = EXCLUDED.max_agents,
  max_listings    = EXCLUDED.max_listings,
  history_months  = EXCLUDED.history_months,
  ai_analysis     = EXCLUDED.ai_analysis,
  email_send      = EXCLUDED.email_send,
  weekly_report   = EXCLUDED.weekly_report,
  monthly_report  = EXCLUDED.monthly_report,
  daily_report    = EXCLUDED.daily_report,
  pdf_export      = EXCLUDED.pdf_export,
  custom_branding = EXCLUDED.custom_branding,
  benchmark       = EXCLUDED.benchmark,
  agent_reports   = EXCLUDED.agent_reports;

-- ── 3. Pro: prema /pricing tabeli ────────────────────────────
UPDATE plans SET
  price_eur       = 79,
  max_agents      = 10,
  max_listings    = 100,
  history_months  = 6,
  monthly_report  = true,
  pdf_export      = true,
  benchmark       = true,
  agent_reports   = true,
  custom_branding = false
WHERE id = 'pro';

-- ── 4. Basic: prema /pricing tabeli ──────────────────────────
UPDATE plans SET
  price_eur       = 29,
  max_agents      = 3,
  max_listings    = 50,
  history_months  = 1,
  monthly_report  = false,
  pdf_export      = false,
  benchmark       = false,
  agent_reports   = true,
  custom_branding = false
WHERE id = 'basic';

-- ── 5. Verifikacija ──────────────────────────────────────────
SELECT
  id, name, price_eur,
  max_agents, max_listings, history_months,
  ai_analysis, monthly_report,
  pdf_export, benchmark, agent_reports, custom_branding
FROM plans
ORDER BY price_eur;
