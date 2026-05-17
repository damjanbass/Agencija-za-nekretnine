-- ============================================================
-- Self-service signup support
-- Pokreni u Supabase SQL Editoru NAKON ostalih migracija
--
-- Šta radi:
--   1. Vraća Free plan u plans tabelu (ako je obrisan)
--   2. Pravi trigger koji na novi auth.users red automatski
--      kreira agencies red sa plan_id='free' i podacima iz
--      raw_user_meta_data (agency_name).
--   3. Resetuje default plan na 'free' (umesto 'basic').
-- ============================================================

-- ── 1. Free plan (idempotent insert) ────────────────────────
INSERT INTO plans (
  id, name, price_eur,
  max_agencies, max_agents, history_months,
  ai_analysis, email_send,
  weekly_report, monthly_report, daily_report,
  pdf_export, custom_branding
) VALUES (
  'free', 'Free', 0,
  1, 3, 1,
  true, true,
  true, false, false,
  false, false
)
ON CONFLICT (id) DO UPDATE SET
  name           = EXCLUDED.name,
  price_eur      = EXCLUDED.price_eur,
  max_agencies   = EXCLUDED.max_agencies,
  max_agents     = EXCLUDED.max_agents,
  history_months = EXCLUDED.history_months;

-- ── 2. Default plan za nove agencije: 'free' ────────────────
ALTER TABLE agencies
  ALTER COLUMN plan_id SET DEFAULT 'free';

-- ── 3. Trigger funkcija ─────────────────────────────────────
--    Kreira agencies red iz auth.users.raw_user_meta_data.
--    SECURITY DEFINER → bypassuje RLS (kreirano u kontekstu admin-a).
CREATE OR REPLACE FUNCTION public.handle_new_signup()
RETURNS TRIGGER
LANGUAGE plpgsql
SECURITY DEFINER
SET search_path = public
AS $$
DECLARE
  v_agency_name TEXT;
BEGIN
  v_agency_name := COALESCE(
    NEW.raw_user_meta_data ->> 'agency_name',
    split_part(NEW.email, '@', 1)
  );

  -- Idempotent: ako agencies email već postoji, samo poveži user_id.
  -- Novi nalozi startuju u 14-dnevnom trial-u (subscription_status='trial').
  INSERT INTO public.agencies (
    name, email, user_id, plan_id, revenue_goal, active,
    subscription_status, trial_ends_at
  )
  VALUES (
    v_agency_name, NEW.email, NEW.id, 'free', 5000, true,
    'trial', now() + INTERVAL '14 days'
  )
  ON CONFLICT (email) DO UPDATE
    SET user_id = EXCLUDED.user_id
    WHERE agencies.user_id IS NULL;

  RETURN NEW;
END;
$$;

-- ── 4. Trigger na auth.users ────────────────────────────────
DROP TRIGGER IF EXISTS on_auth_user_created ON auth.users;

CREATE TRIGGER on_auth_user_created
  AFTER INSERT ON auth.users
  FOR EACH ROW
  EXECUTE FUNCTION public.handle_new_signup();

-- ============================================================
-- POSLE pokretanja:
--   1. Supabase Dashboard → Authentication → Providers → Email
--      → "Confirm email" — ostaviti UKLJUČENO za produkciju (sigurnije).
--      Ako želite trenutni login bez potvrde, isključite ga ovde.
--   2. Authentication → URL Configuration → "Site URL"
--      postavite na https://izvestaj.com (ili vaš Vercel URL).
-- ============================================================
