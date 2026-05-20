-- Lead Rescue Engine migration
-- Pokreni u Supabase SQL Editor

-- 1. IMAP konfiguracija i SLA podešavanja po agenciji
ALTER TABLE agencies ADD COLUMN IF NOT EXISTS imap_host        TEXT;
ALTER TABLE agencies ADD COLUMN IF NOT EXISTS imap_port        INTEGER DEFAULT 993;
ALTER TABLE agencies ADD COLUMN IF NOT EXISTS imap_user        TEXT;
ALTER TABLE agencies ADD COLUMN IF NOT EXISTS imap_pass        TEXT;
ALTER TABLE agencies ADD COLUMN IF NOT EXISTS imap_folder      TEXT DEFAULT 'INBOX';
ALTER TABLE agencies ADD COLUMN IF NOT EXISTS sla_minutes      INTEGER DEFAULT 15;
ALTER TABLE agencies ADD COLUMN IF NOT EXISTS escalation_email TEXT;

-- 2. Broj telefona agenta (za WhatsApp linkove)
ALTER TABLE agents ADD COLUMN IF NOT EXISTS phone             TEXT;
ALTER TABLE agents ADD COLUMN IF NOT EXISTS lead_assignments  INTEGER DEFAULT 0;

-- 3. Tabela individualnih lead-ova
CREATE TABLE IF NOT EXISTS leads (
  id                    UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  agency_id             UUID NOT NULL REFERENCES agencies(id) ON DELETE CASCADE,
  assigned_agent_id     UUID REFERENCES agents(id),
  source                TEXT NOT NULL,
  external_message_id   TEXT,
  buyer_name            TEXT,
  buyer_phone           TEXT,
  buyer_email           TEXT,
  message               TEXT,
  listing_title         TEXT,
  listing_url           TEXT,
  status                TEXT NOT NULL DEFAULT 'new',
  received_at           TIMESTAMPTZ NOT NULL DEFAULT now(),
  assigned_at           TIMESTAMPTZ,
  responded_at          TIMESTAMPTZ,
  escalated_at          TIMESTAMPTZ,
  sla_deadline          TIMESTAMPTZ,
  response_time_minutes INTEGER,
  wa_link_generated     BOOLEAN DEFAULT FALSE,
  created_at            TIMESTAMPTZ NOT NULL DEFAULT now(),
  UNIQUE(agency_id, external_message_id)
);

-- 4. Audit log za svaki lead
CREATE TABLE IF NOT EXISTS lead_events (
  id          UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  lead_id     UUID NOT NULL REFERENCES leads(id) ON DELETE CASCADE,
  event_type  TEXT NOT NULL,
  actor       TEXT,
  note        TEXT,
  created_at  TIMESTAMPTZ NOT NULL DEFAULT now()
);

-- 5. RLS
ALTER TABLE leads       ENABLE ROW LEVEL SECURITY;
ALTER TABLE lead_events ENABLE ROW LEVEL SECURITY;

-- Vlasnik vidi samo lead-ove svoje agencije
DO $$
BEGIN
  IF NOT EXISTS (
    SELECT 1 FROM pg_policies WHERE tablename = 'leads' AND policyname = 'Owner reads own leads'
  ) THEN
    CREATE POLICY "Owner reads own leads"
      ON leads FOR SELECT
      USING (agency_id IN (
        SELECT id FROM agencies WHERE user_id = auth.uid()
      ));
  END IF;

  IF NOT EXISTS (
    SELECT 1 FROM pg_policies WHERE tablename = 'lead_events' AND policyname = 'Owner reads own lead events'
  ) THEN
    CREATE POLICY "Owner reads own lead events"
      ON lead_events FOR SELECT
      USING (lead_id IN (
        SELECT l.id FROM leads l
        JOIN agencies a ON a.id = l.agency_id
        WHERE a.user_id = auth.uid()
      ));
  END IF;
END
$$;

-- 6. Indeksi za brzu SLA proveru
CREATE INDEX IF NOT EXISTS idx_leads_status        ON leads(status);
CREATE INDEX IF NOT EXISTS idx_leads_agency_status ON leads(agency_id, status);
CREATE INDEX IF NOT EXISTS idx_leads_sla_deadline  ON leads(sla_deadline) WHERE status IN ('assigned');
CREATE INDEX IF NOT EXISTS idx_lead_events_lead_id ON lead_events(lead_id);

-- 7. Stored function za round-robin brojač
CREATE OR REPLACE FUNCTION increment_lead_assignments(agent_id UUID)
RETURNS void
LANGUAGE sql
AS $$
  UPDATE agents SET lead_assignments = lead_assignments + 1 WHERE id = agent_id;
$$;
