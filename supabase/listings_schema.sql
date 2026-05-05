-- ============================================================
-- Oglasi za nekretnine
-- Pokreni u Supabase SQL Editoru
-- ============================================================

CREATE TABLE IF NOT EXISTS listings (
  id            UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  agency_id     UUID NOT NULL REFERENCES agencies(id) ON DELETE CASCADE,
  agent_id      UUID REFERENCES agents(id) ON DELETE SET NULL,
  ref_number    TEXT,                          -- interni broj oglasa
  type          TEXT NOT NULL,                 -- 'stan' | 'kuca' | 'poslovni' | 'plac'
  transaction   TEXT NOT NULL,                 -- 'prodaja' | 'zakup'
  title         TEXT NOT NULL,
  description   TEXT,
  price         NUMERIC NOT NULL,
  currency      TEXT NOT NULL DEFAULT 'EUR',
  area_m2       NUMERIC NOT NULL,
  city          TEXT NOT NULL,
  municipality  TEXT,
  street        TEXT,
  floor         INT,
  total_floors  INT,
  rooms         NUMERIC,                       -- 1, 1.5, 2, 2.5, 3 ...
  year_built    INT,
  heating       TEXT,                          -- 'centralno' | 'etazno' | 'podno' | 'struja'
  parking       BOOLEAN DEFAULT false,
  elevator      BOOLEAN DEFAULT false,
  furnished     TEXT DEFAULT 'nije',           -- 'nije' | 'polu' | 'namesteno'
  images        TEXT[] DEFAULT '{}',           -- niz URL-ova slika
  active        BOOLEAN DEFAULT true,
  created_at    TIMESTAMPTZ NOT NULL DEFAULT now(),
  updated_at    TIMESTAMPTZ NOT NULL DEFAULT now()
);

-- Auto-update updated_at
CREATE OR REPLACE FUNCTION update_updated_at()
RETURNS TRIGGER AS $$
BEGIN NEW.updated_at = now(); RETURN NEW; END;
$$ LANGUAGE plpgsql;

CREATE TRIGGER listings_updated_at
  BEFORE UPDATE ON listings
  FOR EACH ROW EXECUTE FUNCTION update_updated_at();

-- RLS (isti princip kao ostale tabele)
ALTER TABLE listings ENABLE ROW LEVEL SECURITY;

CREATE POLICY "Agency owner listings" ON listings
  FOR ALL TO authenticated
  USING     (agency_id IN (SELECT id FROM agencies WHERE user_id = auth.uid()))
  WITH CHECK (agency_id IN (SELECT id FROM agencies WHERE user_id = auth.uid()));

-- Seed: demo oglasi za Agencija Prima
INSERT INTO listings
  (agency_id, ref_number, type, transaction, title, description,
   price, area_m2, city, municipality, street, floor, total_floors,
   rooms, year_built, heating, parking, elevator, furnished, images)
VALUES
  ('aaaaaaaa-0000-0000-0000-000000000001',
   'PRI-001', 'stan', 'prodaja',
   'Svetao dvosoban stan na Vračaru',
   'Odličan dvosoban stan u mirnoj ulici, visoko prizemlje, nedavno renoviran. Blizina škola i javnog prevoza.',
   145000, 58, 'Beograd', 'Vračar', 'Cara Nikolaja II 14',
   3, 6, 2, 1985, 'centralno', false, true, 'namesteno',
   ARRAY['https://placehold.co/800x600?text=Stan+Vracar+1',
         'https://placehold.co/800x600?text=Stan+Vracar+2']),

  ('aaaaaaaa-0000-0000-0000-000000000001',
   'PRI-002', 'stan', 'zakup',
   'Trosoban stan Novi Beograd, blok 45',
   'Prostran trosoban stan sa garažnim mestom. Useljivost odmah. Blizina Arene i tržnih centara.',
   900, 78, 'Beograd', 'Novi Beograd', 'Jurija Gagarina 22',
   7, 12, 3, 1978, 'centralno', true, true, 'namesteno',
   ARRAY['https://placehold.co/800x600?text=Stan+NB+1']),

  ('aaaaaaaa-0000-0000-0000-000000000001',
   'PRI-003', 'kuca', 'prodaja',
   'Porodična kuća sa placem — Zemun',
   'Kuća P+1 na placu od 400m². Dva zasebna ulaza, garaža, lepo uređeno dvorište.',
   235000, 180, 'Beograd', 'Zemun', 'Gospodarska 7',
   NULL, 2, 5, 2005, 'etazno', true, false, 'namesteno',
   ARRAY['https://placehold.co/800x600?text=Kuca+Zemun+1',
         'https://placehold.co/800x600?text=Kuca+Zemun+2',
         'https://placehold.co/800x600?text=Kuca+Zemun+3']);
