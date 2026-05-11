-- ============================================================
-- Agenti: dozvola vlasniku agencije da dodaje i uklanja agente
-- Pokreni u Supabase SQL Editoru
-- ============================================================

-- Stara politika je dozvoljavala samo SELECT. Brisemo je i dodajemo
-- punu kontrolu (SELECT/INSERT/UPDATE/DELETE) za sopstvene agente.
DROP POLICY IF EXISTS "Agency owner agents read" ON agents;

CREATE POLICY "Agency owner agents access" ON agents
  FOR ALL TO authenticated
  USING     (agency_id IN (SELECT id FROM agencies WHERE user_id = auth.uid()))
  WITH CHECK (agency_id IN (SELECT id FROM agencies WHERE user_id = auth.uid()));
