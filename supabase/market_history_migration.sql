-- ============================================================
-- Migracija: Istorija tržišnih snapshot-a + pojedinačni oglasi
-- ============================================================
-- Svrha (Faza 1 plana "Unapređenje analize tržišta"):
--   • Persistira market snapshot-e (do sada se podaci skrejpuju
--     i odbacuju nakon generisanja izveštaja).
--   • Čuva uzorak pojedinačnih oglasa po snapshot-u, što omogućava:
--       - pravo računanje 'new_this_week' (umesto 7% fikcije)
--       - dinamičke top_neighborhoods (umesto hardkodovanih)
--       - pricing benchmark (medijana, P25, P75) po segmentu
--       - Days-on-Market (Faza 2) preko praćenja external_id kroz snapshot-e
--   • Dodaje agencijske preferencije za praćenje prodaje/zakupa.
-- ============================================================

-- ---------- 1. Snapshot tabela ----------
-- Jedan red = jedan (sajt × grad × tip × tranzakcija × datum)
create table if not exists market_snapshots (
  id                   uuid primary key default gen_random_uuid(),
  site                 text not null,          -- 'Halo oglasi' | '4zida' | 'Nekretnine.rs' | 'CityExpert'
  city                 text not null,          -- 'beograd' (za sada); priprema za multi-city
  property_type        text not null default 'apartment',  -- 'apartment' | 'house' | 'commercial' (priprema)
  transaction_type     text not null,          -- 'sale' | 'rent'
  snapshot_date        date not null,

  -- Agregati izvučeni iz pojedinačnih oglasa (ne više hardkodovani)
  total_listings       int  not null default 0,
  avg_price_eur_m2     numeric,                 -- prosečna cena po m² (€)
  median_price_eur_m2  numeric,                 -- medijana — robustnija od proseka
  price_p25            numeric,                 -- 25. percentil €/m²
  price_p75            numeric,                 -- 75. percentil €/m²
  avg_total_price_eur  numeric,                 -- apsolutna cena (za prodaju), mesečna rata (za zakup)
  price_min_eur        numeric,
  price_max_eur        numeric,
  new_this_week        int  not null default 0, -- pravi broj iz listed_at, ne fikcija
  raw_sample_count     int  not null default 0, -- koliko pojedinačnih oglasa je obrađeno u uzorku
  top_neighborhoods    jsonb,                   -- [{"name": "Vračar", "count": 47}, ...] — dinamički
  is_mock              boolean not null default false,

  created_at           timestamptz not null default now(),

  unique (site, city, property_type, transaction_type, snapshot_date)
);

create index if not exists idx_market_snapshots_lookup
  on market_snapshots (city, property_type, transaction_type, snapshot_date desc);

create index if not exists idx_market_snapshots_site_date
  on market_snapshots (site, snapshot_date desc);

comment on table market_snapshots                       is 'Dnevni agregati tržišta po sajtu/gradu/tipu/tranzakciji. Insert-only — istorija za trendove.';
comment on column market_snapshots.transaction_type     is 'sale = prodaja, rent = zakup';
comment on column market_snapshots.median_price_eur_m2  is 'Medijana €/m² — koristi se za pricing benchmark (otpornija na outliers od proseka)';
comment on column market_snapshots.top_neighborhoods    is 'JSONB array {name, count} top 5 kvartova iz uzorka';


-- ---------- 2. Uzorak pojedinačnih oglasa ----------
-- Jedan red = jedan oglas viđen u jednom snapshot-u.
-- Isti oglas može imati više redova kroz vreme — to je osnova za DOM (Faza 2).
create table if not exists market_listings_sample (
  id              uuid primary key default gen_random_uuid(),
  snapshot_id     uuid not null references market_snapshots(id) on delete cascade,

  -- Identifikacija oglasa
  site            text not null,           -- denormalizovano za brzi grouping po (site, external_id)
  external_id     text not null,           -- ID iz URL-a ili stable slug
  url             text,

  -- Klasifikacija
  transaction_type text not null,           -- 'sale' | 'rent' (denormalizovano)
  property_type   text not null default 'apartment',
  neighborhood    text,
  city            text not null default 'beograd',

  -- Karakteristike
  area_m2         numeric,
  rooms           numeric,                  -- 1, 1.5, 2, 2.5, ...
  floor           text,                     -- 'PR', '3/5', 'VPR' — string je fleksibilniji
  year_built      int,

  -- Cena
  price_eur       numeric,                  -- ukupna (sale) ili mesečna (rent)
  price_eur_m2    numeric,                  -- price_eur / area_m2 (denormalizovano za brzo poređenje)

  -- Vreme
  listed_at       date,                     -- datum objave na sajtu (ne uvek dostupan; fallback null)
  snapshot_date   date not null,            -- denormalizovano sa snapshots.snapshot_date

  -- Vlasnik oglasa (za agregirani competitor intel u Fazi 3)
  publisher       text,                     -- naziv agencije ili 'private'
  publisher_type  text,                     -- 'agency' | 'private' | 'unknown'

  -- Sirov tekst (za semantičku analizu u budućnosti — drži se konkretan zbog veličine)
  title           text,

  created_at      timestamptz not null default now()
);

-- Ključni indeksi za rad sa podacima
create index if not exists idx_listings_sample_snapshot
  on market_listings_sample (snapshot_id);

-- DOM tracking (Faza 2): brzi lookup istog oglasa kroz datume
create index if not exists idx_listings_sample_dom
  on market_listings_sample (site, external_id, snapshot_date);

-- Pricing benchmark (Faza 1): segment lookup po (kvart, tip, tranzakcija, datum)
create index if not exists idx_listings_sample_segment
  on market_listings_sample (city, neighborhood, transaction_type, property_type, snapshot_date desc);

-- Hot zones (Faza 2): novi oglasi po kvartu po danu
create index if not exists idx_listings_sample_listed_at
  on market_listings_sample (listed_at)
  where listed_at is not null;

-- Competitor intel (Faza 3): grupisanje po publisher-u
create index if not exists idx_listings_sample_publisher
  on market_listings_sample (publisher, snapshot_date desc)
  where publisher is not null;

comment on table  market_listings_sample              is 'Uzorak pojedinačnih oglasa iz svakog scrape rana. Osnova za pricing benchmark, DOM, hot zones, competitor intel.';
comment on column market_listings_sample.external_id  is 'Stable ID iz URL-a (npr. Halo oglasi numerički ID, 4zida slug). Koristi se za DOM tracking — isti listing kroz dane.';
comment on column market_listings_sample.price_eur_m2 is 'Denormalizovano price_eur / area_m2 — za brzo poređenje sa medijanama bez recalculate-a.';
comment on column market_listings_sample.publisher    is 'Agencija ili vlasnik koji je objavio. Za agregirani competitor intel u Fazi 3 (broj oglasa po agenciji, bez per-agencija cena u alertima).';


-- ---------- 3. Agencijske preferencije: prati prodaju/zakup ----------
alter table agencies
  add column if not exists tracks_sale boolean not null default true,
  add column if not exists tracks_rent boolean not null default false;

comment on column agencies.tracks_sale is 'Agencija prati prodaju stanova (default true)';
comment on column agencies.tracks_rent is 'Agencija prati zakup stanova (default false; aktivira se u Podešavanjima)';


-- ---------- 4. RLS (konzistentno sa ostatkom shema) ----------
alter table market_snapshots         disable row level security;
alter table market_listings_sample   disable row level security;
