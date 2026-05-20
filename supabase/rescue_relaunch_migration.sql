-- Rescue Relaunch migracija — maj 2026
-- Ažurira nazive i cene planova + dodaje Lead Rescue feature flags
-- Pokreni u Supabase SQL Editor

-- 1. Novi nazivi i cene
UPDATE plans SET name = 'Rescue',     price_eur = 39  WHERE id = 'basic';
UPDATE plans SET name = 'Rescue+',    price_eur = 89  WHERE id = 'pro';
UPDATE plans SET name = 'Rescue Pro', price_eur = 179 WHERE id = 'premium';

-- 2. Lead Rescue feature flags (dodaj kolone ako ne postoje)
ALTER TABLE plans ADD COLUMN IF NOT EXISTS lead_rescue         BOOLEAN DEFAULT FALSE;
ALTER TABLE plans ADD COLUMN IF NOT EXISTS mystery_shopper     BOOLEAN DEFAULT FALSE;
ALTER TABLE plans ADD COLUMN IF NOT EXISTS stale_listing_nudge BOOLEAN DEFAULT FALSE;
ALTER TABLE plans ADD COLUMN IF NOT EXISTS daily_brief         BOOLEAN DEFAULT FALSE;

-- 3. Podesi feature flags po planu
UPDATE plans SET
  lead_rescue     = TRUE,
  mystery_shopper = TRUE,
  daily_brief     = TRUE
WHERE id = 'basic';

UPDATE plans SET
  lead_rescue         = TRUE,
  mystery_shopper     = TRUE,
  stale_listing_nudge = TRUE,
  daily_brief         = TRUE
WHERE id = 'pro';

UPDATE plans SET
  lead_rescue         = TRUE,
  mystery_shopper     = TRUE,
  stale_listing_nudge = TRUE,
  daily_brief         = TRUE
WHERE id = 'premium';
