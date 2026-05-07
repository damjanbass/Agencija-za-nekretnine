-- ============================================================
-- Migracija: agent email, javni token, benchmark & public dashboard RPC
-- Pokrenuti u Supabase SQL Editor
-- ============================================================

-- 1. Email adresa agenta (za personalne izveštaje)
ALTER TABLE agents ADD COLUMN IF NOT EXISTS email TEXT;

-- 2. Javni token za agenciju (za read-only dashboard bez logina)
ALTER TABLE agencies ADD COLUMN IF NOT EXISTS public_token UUID NOT NULL DEFAULT gen_random_uuid();
CREATE UNIQUE INDEX IF NOT EXISTS agencies_public_token_idx ON agencies(public_token);

-- 3. Benchmark RPC: agregirani proseci za datu nedelju (dostupan anon korisnicima)
CREATE OR REPLACE FUNCTION get_benchmark(in_week_start DATE)
RETURNS JSONB
LANGUAGE SQL
SECURITY DEFINER
SET search_path = public
AS $$
  SELECT jsonb_build_object(
    'avg_conversion', ROUND(AVG(
      CASE WHEN inquiries > 0
           THEN (contracts_sale + contracts_rent)::NUMERIC / inquiries * 100
           ELSE 0
      END
    ), 1),
    'avg_revenue',   ROUND(AVG(revenue)),
    'avg_inquiries', ROUND(AVG(inquiries)),
    'agency_count',  COUNT(*)
  )
  FROM weekly_kpis
  WHERE week_start = in_week_start;
$$;

GRANT EXECUTE ON FUNCTION get_benchmark(DATE) TO anon;

-- 4. Javni dashboard RPC: vraća poslednju nedelju za dati public_token
CREATE OR REPLACE FUNCTION get_public_dashboard(p_token TEXT)
RETURNS JSONB
LANGUAGE plpgsql
SECURITY DEFINER
SET search_path = public
AS $$
DECLARE
  v_agency_id  UUID;
  v_week_start DATE;
  result       JSONB;
BEGIN
  BEGIN
    SELECT id INTO STRICT v_agency_id
    FROM agencies
    WHERE public_token = p_token::UUID AND active = true;
  EXCEPTION
    WHEN NO_DATA_FOUND OR INVALID_TEXT_REPRESENTATION THEN
      RETURN NULL;
  END;

  SELECT week_start INTO v_week_start
  FROM weekly_kpis
  WHERE agency_id = v_agency_id
  ORDER BY week_start DESC
  LIMIT 1;

  IF NOT FOUND THEN RETURN NULL; END IF;

  SELECT jsonb_build_object(
    'agency_name',     a.name,
    'week_start',      w.week_start::TEXT,
    'active_listings', w.active_listings,
    'inquiries',       w.inquiries,
    'contracts_sale',  w.contracts_sale,
    'contracts_rent',  w.contracts_rent,
    'revenue',         w.revenue,
    'revenue_goal',    a.revenue_goal
  ) INTO result
  FROM agencies a
  JOIN weekly_kpis w ON w.agency_id = a.id
  WHERE a.id = v_agency_id AND w.week_start = v_week_start;

  RETURN result;
END;
$$;

GRANT EXECUTE ON FUNCTION get_public_dashboard(TEXT) TO anon;
