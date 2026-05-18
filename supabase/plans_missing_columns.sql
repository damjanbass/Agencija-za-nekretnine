-- Dodaje kolone koje PlanGate query zahtijeva a nisu bile u plans tabeli.
-- Pokreni u Supabase SQL Editoru.

ALTER TABLE plans ADD COLUMN IF NOT EXISTS benchmark      boolean NOT NULL DEFAULT false;
ALTER TABLE plans ADD COLUMN IF NOT EXISTS agent_reports  boolean NOT NULL DEFAULT false;
ALTER TABLE plans ADD COLUMN IF NOT EXISTS max_listings   int     NOT NULL DEFAULT -1;

-- Vrijednosti po planu
UPDATE plans SET benchmark = false, agent_reports = false WHERE id = 'free';
UPDATE plans SET benchmark = false, agent_reports = false WHERE id = 'basic';
UPDATE plans SET benchmark = true,  agent_reports = true  WHERE id = 'pro';
UPDATE plans SET benchmark = true,  agent_reports = true  WHERE id = 'premium';

-- Verifikacija
SELECT id, name, custom_branding, benchmark, agent_reports, max_agents, max_listings
FROM plans ORDER BY price_eur;
