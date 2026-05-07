-- Dodaje kolonu report_type u tabelu reports
-- 'weekly'  = nedeljni izveštaj
-- 'monthly' = mesečni izveštaj
--
-- Pokreni u Supabase SQL Editoru

ALTER TABLE reports
  ADD COLUMN IF NOT EXISTS report_type TEXT NOT NULL DEFAULT 'weekly'
  CHECK (report_type IN ('weekly', 'monthly'));
