-- Mystery Shopper migration
-- Pokreni u Supabase SQL Editor

-- 1. Oznaka mystery shopper lead-ova u leads tabeli
ALTER TABLE leads ADD COLUMN IF NOT EXISTS is_mystery_shopper BOOLEAN DEFAULT FALSE;

-- 2. Konfiguracija mystery shoppinga po agenciji
ALTER TABLE agencies ADD COLUMN IF NOT EXISTS mystery_shopper_email       TEXT;
ALTER TABLE agencies ADD COLUMN IF NOT EXISTS mystery_shopper_listing_url TEXT;

-- 3. Indeks za brze upite
CREATE INDEX IF NOT EXISTS idx_leads_mystery_shopper
  ON leads(agency_id, source)
  WHERE source = 'mystery_shopper';
