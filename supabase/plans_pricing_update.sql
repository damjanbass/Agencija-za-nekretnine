-- ============================================================
-- Plans pricing update (maj 2026)
-- Uklanja Free plan, snižava cene Basic/Pro/Premium.
-- Pokreni u Supabase SQL Editoru.
-- ============================================================

-- 1. Migriraj sve agencije koje su trenutno na "free" → "basic"
--    (FK na plans.id ne dozvoljava brisanje "free" ako postoji ijedna agencija sa tim planom)
update agencies set plan_id = 'basic' where plan_id = 'free';

-- 2. Obriši Free plan iz plans tabele
delete from plans where id = 'free';

-- 3. Ažuriraj cene preostalih planova
update plans set price_eur = 69  where id = 'basic';
update plans set price_eur = 49 where id = 'pro';
update plans set price_eur = 199 where id = 'premium';

-- 4. Promeni default vrednost agencies.plan_id sa 'free' na 'basic'
alter table agencies
  alter column plan_id set default 'basic';
