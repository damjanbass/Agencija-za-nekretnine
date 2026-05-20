-- Stale Listing Nudge migration
-- Pokreni u Supabase SQL Editor

-- 1. Prodavac kontakt i datum prvog objavljivanja
ALTER TABLE listings ADD COLUMN IF NOT EXISTS seller_name          TEXT;
ALTER TABLE listings ADD COLUMN IF NOT EXISTS seller_phone         TEXT;
ALTER TABLE listings ADD COLUMN IF NOT EXISTS seller_email         TEXT;
ALTER TABLE listings ADD COLUMN IF NOT EXISTS portal_url           TEXT;
ALTER TABLE listings ADD COLUMN IF NOT EXISTS first_published_at   TIMESTAMPTZ DEFAULT now();
ALTER TABLE listings ADD COLUMN IF NOT EXISTS view_count           INTEGER DEFAULT 0;
ALTER TABLE listings ADD COLUMN IF NOT EXISTS inquiry_count        INTEGER DEFAULT 0;

-- 2. Indeksi za detekciju starih oglasa
CREATE INDEX IF NOT EXISTS idx_listings_active_published
  ON listings(agency_id, active, first_published_at)
  WHERE active = TRUE;
