-- Tabela za čuvanje per-agent HTML izveštaja (Pro/Premium feature)
-- Vlasnik agencije pristupa izveštajima kroz app.html → Agenti tab
-- HTML se generiše Python skriptom (main.py --agent-reports) i čuva ovde

CREATE TABLE IF NOT EXISTS agent_reports (
    id           UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    agency_id    UUID NOT NULL REFERENCES agencies(id) ON DELETE CASCADE,
    agent_id     UUID NOT NULL REFERENCES agents(id)  ON DELETE CASCADE,
    week_start   DATE NOT NULL,
    html         TEXT NOT NULL,
    generated_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

-- Upsert po (agency_id, agent_id, week_start)
CREATE UNIQUE INDEX IF NOT EXISTS agent_reports_uq
    ON agent_reports (agency_id, agent_id, week_start);

-- Brzi lookup po agenciji (za Agenti tab)
CREATE INDEX IF NOT EXISTS agent_reports_agency_week
    ON agent_reports (agency_id, week_start DESC);

-- RLS: vlasnik agencije može da čita samo svoje agent izveštaje
ALTER TABLE agent_reports ENABLE ROW LEVEL SECURITY;

CREATE POLICY "agency owner reads agent reports"
    ON agent_reports FOR SELECT
    USING (
        agency_id IN (
            SELECT id FROM agencies WHERE user_id = auth.uid()
        )
    );

-- Python backend (service role) može da upisuje
-- (service role key zaobilazi RLS — nema potrebe za posebnom policy-jem)
