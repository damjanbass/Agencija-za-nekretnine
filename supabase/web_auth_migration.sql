-- ============================================================
-- Web panel: Auth korisnici + RLS
-- Pokreni u Supabase SQL Editoru
-- ============================================================

-- 1. Dodaj user_id kolonu u agencies
ALTER TABLE agencies
  ADD COLUMN IF NOT EXISTS user_id UUID REFERENCES auth.users(id) ON DELETE SET NULL;

-- 2. Uključi RLS na svim tabelama
ALTER TABLE agencies          ENABLE ROW LEVEL SECURITY;
ALTER TABLE weekly_kpis       ENABLE ROW LEVEL SECURITY;
ALTER TABLE inquiry_sources   ENABLE ROW LEVEL SECURITY;
ALTER TABLE agents            ENABLE ROW LEVEL SECURITY;
ALTER TABLE agent_performance ENABLE ROW LEVEL SECURITY;
ALTER TABLE reports           ENABLE ROW LEVEL SECURITY;

-- 3. RLS politike
-- agencies: vlasnik vidi samo svoju agenciju
CREATE POLICY "Agency owner access" ON agencies
  FOR ALL TO authenticated
  USING     (user_id = auth.uid())
  WITH CHECK (user_id = auth.uid());

-- weekly_kpis
CREATE POLICY "Agency owner weekly_kpis" ON weekly_kpis
  FOR ALL TO authenticated
  USING     (agency_id IN (SELECT id FROM agencies WHERE user_id = auth.uid()))
  WITH CHECK (agency_id IN (SELECT id FROM agencies WHERE user_id = auth.uid()));

-- inquiry_sources
CREATE POLICY "Agency owner inquiry_sources" ON inquiry_sources
  FOR ALL TO authenticated
  USING     (agency_id IN (SELECT id FROM agencies WHERE user_id = auth.uid()))
  WITH CHECK (agency_id IN (SELECT id FROM agencies WHERE user_id = auth.uid()));

-- agents (samo čitanje — agente dodaje admin)
CREATE POLICY "Agency owner agents read" ON agents
  FOR SELECT TO authenticated
  USING (agency_id IN (SELECT id FROM agencies WHERE user_id = auth.uid()));

-- agent_performance
CREATE POLICY "Agency owner agent_performance" ON agent_performance
  FOR ALL TO authenticated
  USING     (agency_id IN (SELECT id FROM agencies WHERE user_id = auth.uid()))
  WITH CHECK (agency_id IN (SELECT id FROM agencies WHERE user_id = auth.uid()));

-- reports (samo čitanje za vlasnika)
CREATE POLICY "Agency owner reports read" ON reports
  FOR SELECT TO authenticated
  USING (agency_id IN (SELECT id FROM agencies WHERE user_id = auth.uid()));

-- ============================================================
-- POSLE pokretanja ovog SQL-a:
--
-- 1. Idi na Authentication > Users > "Add user"
--    Email: vlasnik@primakretnine.rs (ili koji hoces)
--    Postavi lozinku
--
-- 2. Kopiraj UUID novog korisnika, pa pokreni:
--    UPDATE agencies
--    SET user_id = 'OVDE-ZALEPI-UUID'
--    WHERE id = 'aaaaaaaa-0000-0000-0000-000000000001';
-- ============================================================
