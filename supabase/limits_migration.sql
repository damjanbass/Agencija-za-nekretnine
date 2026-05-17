-- ============================================================
-- Plan-based limits & subscription lifecycle
-- Pokreni u Supabase SQL Editoru NAKON ostalih migracija
--
-- Šta radi:
--   1. Dodaje max_listings u plans tabelu i seed-uje vrednosti
--   2. Dodaje subscription_status / trial_ends_at / current_period_end /
--      paypal_subscription_id u agencies
--   3. Pravi SQL helper effective_plan_id(uuid) — vraća 'free' kada
--      pretplata nije aktivna/u trialu (status expired/canceled/past_due)
--   4. Pravi BEFORE INSERT trigere koji blokiraju prekoračenje
--      limita agenata i oglasa, i BEFORE UPDATE trigger koji blokira
--      logo_url upis kada custom_branding=false
-- ============================================================

-- ── 1. max_listings ──────────────────────────────────────────
ALTER TABLE plans
  ADD COLUMN IF NOT EXISTS max_listings INT NOT NULL DEFAULT -1;

UPDATE plans SET max_listings = 5   WHERE id = 'free';
UPDATE plans SET max_listings = 25  WHERE id = 'basic';
UPDATE plans SET max_listings = 100 WHERE id = 'pro';
UPDATE plans SET max_listings = -1  WHERE id = 'premium';

-- ── 2. Subscription state na agencies ────────────────────────
ALTER TABLE agencies
  ADD COLUMN IF NOT EXISTS subscription_status     TEXT        NOT NULL DEFAULT 'trial',
  ADD COLUMN IF NOT EXISTS trial_ends_at           TIMESTAMPTZ,
  ADD COLUMN IF NOT EXISTS current_period_end      TIMESTAMPTZ,
  ADD COLUMN IF NOT EXISTS paypal_subscription_id  TEXT;

-- CHECK constraint: dozvoljene vrednosti za status
DO $$
BEGIN
  IF NOT EXISTS (
    SELECT 1 FROM pg_constraint WHERE conname = 'agencies_subscription_status_check'
  ) THEN
    ALTER TABLE agencies
      ADD CONSTRAINT agencies_subscription_status_check
      CHECK (subscription_status IN ('trial', 'active', 'past_due', 'canceled', 'expired'));
  END IF;
END $$;

-- Postojeće agencije bez trial_ends_at → 14 dana trial od sad
UPDATE agencies
  SET trial_ends_at = now() + INTERVAL '14 days'
  WHERE trial_ends_at IS NULL;

-- Demo agencija sa basic planom se tretira kao active (za testove)
UPDATE agencies
  SET subscription_status = 'active'
  WHERE id = 'aaaaaaaa-0000-0000-0000-000000000001';

-- ── 3. effective_plan_id(agency_id) ──────────────────────────
-- Vraća plan_id samo kada pretplata zaista važi.
-- Trial i active → pravi plan; sve ostalo → 'free'.
CREATE OR REPLACE FUNCTION public.effective_plan_id(p_agency_id UUID)
RETURNS TEXT
LANGUAGE sql
STABLE
SECURITY DEFINER
SET search_path = public
AS $$
  SELECT CASE
    WHEN subscription_status IN ('trial', 'active') THEN plan_id
    ELSE 'free'
  END
  FROM agencies
  WHERE id = p_agency_id;
$$;

-- ── 4. Trigger: limit agenata ────────────────────────────────
CREATE OR REPLACE FUNCTION public.enforce_agent_limit()
RETURNS TRIGGER
LANGUAGE plpgsql
SECURITY DEFINER
SET search_path = public
AS $$
DECLARE
  v_max     INT;
  v_count   INT;
BEGIN
  SELECT p.max_agents INTO v_max
  FROM plans p
  WHERE p.id = public.effective_plan_id(NEW.agency_id);

  IF v_max IS NULL OR v_max = -1 THEN
    RETURN NEW;
  END IF;

  SELECT COUNT(*) INTO v_count
  FROM agents
  WHERE agency_id = NEW.agency_id AND active = true;

  IF v_count + 1 > v_max THEN
    RAISE EXCEPTION 'LIMIT_EXCEEDED:agents:%', v_max
      USING ERRCODE = 'P0001';
  END IF;

  RETURN NEW;
END;
$$;

DROP TRIGGER IF EXISTS trg_enforce_agent_limit ON agents;
CREATE TRIGGER trg_enforce_agent_limit
  BEFORE INSERT ON agents
  FOR EACH ROW
  EXECUTE FUNCTION public.enforce_agent_limit();

-- ── 5. Trigger: limit oglasa ─────────────────────────────────
CREATE OR REPLACE FUNCTION public.enforce_listing_limit()
RETURNS TRIGGER
LANGUAGE plpgsql
SECURITY DEFINER
SET search_path = public
AS $$
DECLARE
  v_max   INT;
  v_count INT;
BEGIN
  SELECT p.max_listings INTO v_max
  FROM plans p
  WHERE p.id = public.effective_plan_id(NEW.agency_id);

  IF v_max IS NULL OR v_max = -1 THEN
    RETURN NEW;
  END IF;

  SELECT COUNT(*) INTO v_count
  FROM listings
  WHERE agency_id = NEW.agency_id AND active = true;

  IF v_count + 1 > v_max THEN
    RAISE EXCEPTION 'LIMIT_EXCEEDED:listings:%', v_max
      USING ERRCODE = 'P0001';
  END IF;

  RETURN NEW;
END;
$$;

DROP TRIGGER IF EXISTS trg_enforce_listing_limit ON listings;
CREATE TRIGGER trg_enforce_listing_limit
  BEFORE INSERT ON listings
  FOR EACH ROW
  EXECUTE FUNCTION public.enforce_listing_limit();

-- ── 6. Trigger: custom_branding feature gate ─────────────────
-- Blokira upis logo_url ako plan ne dozvoljava custom branding.
CREATE OR REPLACE FUNCTION public.enforce_branding_feature()
RETURNS TRIGGER
LANGUAGE plpgsql
SECURITY DEFINER
SET search_path = public
AS $$
DECLARE
  v_allowed BOOLEAN;
BEGIN
  IF NEW.logo_url IS NULL OR NEW.logo_url = '' THEN
    RETURN NEW;
  END IF;

  IF NEW.logo_url IS NOT DISTINCT FROM OLD.logo_url THEN
    RETURN NEW;
  END IF;

  SELECT p.custom_branding INTO v_allowed
  FROM plans p
  WHERE p.id = public.effective_plan_id(NEW.id);

  IF NOT COALESCE(v_allowed, false) THEN
    RAISE EXCEPTION 'LIMIT_EXCEEDED:custom_branding:0'
      USING ERRCODE = 'P0001';
  END IF;

  RETURN NEW;
END;
$$;

DROP TRIGGER IF EXISTS trg_enforce_branding ON agencies;
CREATE TRIGGER trg_enforce_branding
  BEFORE UPDATE OF logo_url ON agencies
  FOR EACH ROW
  EXECUTE FUNCTION public.enforce_branding_feature();

-- ── 7. Reconciliation funkcija (trial → expired) ─────────────
-- Pokreće se iz dnevnog cron-a (vidi api/paypal_webhook.py / main.py).
CREATE OR REPLACE FUNCTION public.expire_stale_trials()
RETURNS INT
LANGUAGE plpgsql
SECURITY DEFINER
SET search_path = public
AS $$
DECLARE
  v_count INT;
  v_step  INT;
BEGIN
  UPDATE agencies
    SET subscription_status = 'expired'
    WHERE subscription_status = 'trial'
      AND trial_ends_at IS NOT NULL
      AND trial_ends_at < now();
  GET DIAGNOSTICS v_count = ROW_COUNT;

  UPDATE agencies
    SET subscription_status = 'expired'
    WHERE subscription_status = 'active'
      AND current_period_end IS NOT NULL
      AND current_period_end < now() - INTERVAL '3 days';
  GET DIAGNOSTICS v_step = ROW_COUNT;

  RETURN v_count + v_step;
END;
$$;
