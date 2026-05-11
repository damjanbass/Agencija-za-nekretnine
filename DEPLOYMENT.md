# Deployment runbook

Vodič kroz produkcijski setup aplikacije. Pretpostavljam da je repo već kloniran i da imaš pristup Supabase, Gmail, GitHub i Vercel nalozima.

## 1. Env varijable

Aplikacija zavisi od 7 env varijabli. **Iste varijable** moraju biti na 3 mesta:

| Varijabla | Lokalni `.env` | GitHub Secrets | Vercel |
|---|---|---|---|
| `ANTHROPIC_API_KEY` | ✓ | ✓ | — |
| `SUPABASE_URL` | ✓ | ✓ | — |
| `SUPABASE_KEY` (service-role) | ✓ | ✓ | — |
| `SMTP_HOST` (`smtp.gmail.com`) | ✓ | ✓ | — |
| `SMTP_PORT` (`587`) | ✓ | ✓ | — |
| `SMTP_USER` | ✓ | ✓ | — |
| `SMTP_PASS` | ✓ | ✓ | — |

Opcione (imaju razumne defaulte iz `config.py`):
- `EMAIL_FROM` — From adresa. Default: `SMTP_USER` (Gmail to zahteva).
- `EMAIL_FROM_NAME` — ime pošiljaoca. Default: "Nekretnine Izveštaji".
- `SUPPORT_EMAIL` — kontakt u footeru izveštaja. Default: `EMAIL_FROM`.

Vercel ne zahteva env varijable jer servira samo statičke fajlove iz `web/`.

## 2. Gmail App Password

Reports moraju slati mejlove preko SMTP-a. Najlakše rešenje je dedikovani Gmail nalog sa App Password-om.

1. Kreiraj Gmail nalog (npr. `izvestaji.agencija@gmail.com`).
2. Uključi **2-Step Verification**: https://myaccount.google.com/security
3. Generiši App Password: https://myaccount.google.com/apppasswords
   - Aplikacija: "Mail", uređaj: "Other" → "Nekretnine reports".
   - Sačuvaj 16-karaktera password (prikazuje se samo jednom).
4. `SMTP_USER` = full Gmail adresa, `SMTP_PASS` = App Password (bez razmaka).

## 3. Rotacija Supabase ključa

Ako je `SUPABASE_KEY` već bio commit-ovan u `.env` (proveri `git log --all -- .env`):

1. Otvori Supabase Dashboard → Project Settings → API.
2. Klik "Reset" pored **service_role** key.
3. Stari ključ je odmah invalidiran. Novi ključ stavi u lokalni `.env` i GitHub Secret.

`.env` je u `.gitignore`, ali stari ključ je možda već u git history — rotacija je obavezna.

## 4. Lokalni `.env`

```bash
# c:\Users\PC\OneDrive\Desktop\Agencija za nekretnine\.env
ANTHROPIC_API_KEY=sk-ant-...
SUPABASE_URL=https://cesxmcbodcpfnpyusxhj.supabase.co
SUPABASE_KEY=<rotirani service-role key>
SMTP_HOST=smtp.gmail.com
SMTP_PORT=587
SMTP_USER=izvestaji.agencija@gmail.com
SMTP_PASS=<16-karaktera App Password>
```

## 5. GitHub Secrets

Otvori `https://github.com/<korisnik>/<repo>/settings/secrets/actions` i dodaj svih 7 secret-a iz tabele iznad.

Ili preko `gh` CLI:

```bash
gh secret set ANTHROPIC_API_KEY --body "sk-ant-..."
gh secret set SUPABASE_URL      --body "https://cesxmcbodcpfnpyusxhj.supabase.co"
gh secret set SUPABASE_KEY      --body "<rotirani key>"
gh secret set SMTP_HOST         --body "smtp.gmail.com"
gh secret set SMTP_PORT         --body "587"
gh secret set SMTP_USER         --body "izvestaji.agencija@gmail.com"
gh secret set SMTP_PASS         --body "<App Password>"
```

## 6. Provera setup-a

```bash
python -X utf8 admin/check_env.py
```

Skripta verifikuje:
- Sve potrebne env varijable su podešene.
- Supabase konekcija radi.
- SMTP login prolazi.
- Anthropic API odgovara.

## 7. Cron raspored

| Workflow | Frekvencija | Vreme (Beograd) | Šta radi |
|---|---|---|---|
| `weekly_report.yml` | ponedeljak | 08:00 | Šalje nedeljne izveštaje svim aktivnim agencijama |
| `monthly_report.yml` | prvog u mesecu | 08:00 | Šalje mesečne izveštaje (samo Pro/Premium) |
| `generate_feeds.yml` | dnevno | 07:00 | Generiše javne RSS/JSON feedove |

Ručno pokretanje: `gh workflow run weekly_report.yml`

## 8. Vercel — update alias-a posle deploy-a

Stabilni URL je `agencija-za-nekretnine-nine.vercel.app`. Posle svakog `git push` Vercel kreira novu deployment URL (npr. `agencija-za-nekretnine-xyz123-...`). Alias treba ručno povezati:

```bash
# Pronađi najnoviji deployment
npx vercel ls

# Postavi alias
npx vercel alias set agencija-za-nekretnine-xyz123-... agencija-za-nekretnine-nine.vercel.app
```

(Alternativa: u Vercel dashboardu uključi automatsko alias promovisanje za main branch.)

## 9. Migracije Supabase

Sve SQL migracije su u `supabase/`. Trenutno primenjene migracije (potrebne za produkciju):

- `schema.sql` — osnovne tabele
- `plans_migration.sql` — `plans` tabela + `agencies.plan_id`
- `web_auth_migration.sql` — `agencies.user_id` + RLS policies
- `features_migration.sql` — `agencies.public_token` + RPC funkcije
- `reports_type_migration.sql` — `reports.report_type` kolona

Ako pravim novu Supabase instancu, primeniti redom kroz SQL editor.

## 10. Production deploy checklist

Pre prvog real run-a:

- [ ] Gmail nalog + App Password kreirani
- [ ] Supabase ključ rotiran (ako je bio commit-ovan)
- [ ] Lokalni `.env` popunjen
- [ ] `python -X utf8 admin/check_env.py` → sve zeleno
- [ ] GitHub Secrets postavljeni
- [ ] Vercel alias pokazuje na najnoviji deploy
- [ ] Probni run sa svojim mejlom: `python -X utf8 main.py` — mejl stiže u inbox
- [ ] Ručno triggeruje GHA workflow: `gh workflow run weekly_report.yml` — green
