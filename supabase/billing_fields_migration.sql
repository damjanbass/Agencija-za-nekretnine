-- ============================================================
-- Migracija: dodavanje polja za R-1 račun (PIB, matični broj, adresa)
-- ============================================================
-- Svrha: omogućiti agenciji da kasnije unese podatke koji
-- su potrebni za R-1 fiskalni račun (Srbija).
-- Sva polja su opciona — agencija može da preskoči i račun će
-- stići bez R-1 elemenata.
-- ============================================================

ALTER TABLE agencies
  ADD COLUMN IF NOT EXISTS pib              text,
  ADD COLUMN IF NOT EXISTS maticni_broj     text,
  ADD COLUMN IF NOT EXISTS legal_address    text,
  ADD COLUMN IF NOT EXISTS legal_city       text,
  ADD COLUMN IF NOT EXISTS billing_email    text;

-- Indeks za PIB pretragu (može biti koristan u admin alatima)
CREATE INDEX IF NOT EXISTS idx_agencies_pib ON agencies (pib);

COMMENT ON COLUMN agencies.pib            IS 'PIB agencije za R-1 račun (opciono)';
COMMENT ON COLUMN agencies.maticni_broj   IS 'Matični broj firme (opciono)';
COMMENT ON COLUMN agencies.legal_address  IS 'Pravna adresa za fakturu (opciono)';
COMMENT ON COLUMN agencies.legal_city     IS 'Grad za fakturu (opciono)';
COMMENT ON COLUMN agencies.billing_email  IS 'Email za fakture (ako se razlikuje od glavnog)';
