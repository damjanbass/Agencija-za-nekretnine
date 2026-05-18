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

## 10. PayPal webhook (Vercel)

Webhook (`api/paypal_webhook.py`) je FastAPI serverless funkcija. Vercel je automatski detektuje preko `api/` foldera. Routes (preko `vercel.json` rewrites):

| URL | Šta radi | Ko zove |
|---|---|---|
| `POST /webhook/paypal` | Prima PayPal evente, ažurira pretplate, šalje email | PayPal |
| `POST /admin/expire` | Reconciliation — markira stale trials kao expired | Cron / ručno |
| `POST /admin/activate` | Ručna aktivacija pretplate na agency | Frontend nakon checkout-a |

### 10a. Env varijable na Vercelu

Idi na **Vercel Dashboard → Project Settings → Environment Variables** i dodaj:

| Varijabla | Vrednost | Gde naći |
|---|---|---|
| `SUPABASE_URL` | `https://cesxmcbodcpfnpyusxhj.supabase.co` | Supabase → Settings → API |
| `SUPABASE_KEY` | service-role key | Supabase → Settings → API |
| `SMTP_HOST` | `smtp.resend.com` (ili Gmail) | tvoj SMTP provider |
| `SMTP_PORT` | `587` | — |
| `SMTP_USER` | `resend` (ili Gmail adresa) | — |
| `SMTP_PASS` | Resend API key / Gmail App Password | — |
| `EMAIL_FROM` | npr. `racuni@izvestaj.rs` | — |
| `EMAIL_FROM_NAME` | npr. `Izveštaj` | — |
| `SUPPORT_EMAIL` | npr. `hello@izvestaj.rs` | — |
| `PAYPAL_CLIENT_ID` | REST API client id | PayPal Dashboard → Apps & Credentials |
| `PAYPAL_SECRET` | REST API secret | isto |
| `PAYPAL_API_BASE` | `https://api-m.paypal.com` (live) ili `https://api-m.sandbox.paypal.com` | — |
| `PAYPAL_WEBHOOK_ID` | ID webhook-a iz PayPal Dashboarda | (popunjava se posle koraka 10c) |
| `ADMIN_TOKEN` | bilo koji random string | — |

Posle dodavanja varijabli pokreni novi deploy: `git commit --allow-empty -m "trigger redeploy" && git push`.

### 10b. PayPal Business account setup

1. Otvori **PayPal Business** nalog (https://www.paypal.com/business).
2. Idi na **Developer Dashboard → Apps & Credentials** → "Create App" (live mode).
3. Kopiraj **Client ID** i **Secret** → dodaj kao Vercel env varijable (`PAYPAL_CLIENT_ID`, `PAYPAL_SECRET`).
4. **Kreiraj subscription plans** (Subscriptions → Products → Create Product, jedan po planu):
   - **Basic**: Trial 30 dana @ 0€ → mesečno @ 29€ EUR
   - **Pro**: Trial 30 dana @ 0€ → mesečno @ 79€ EUR
   - **Premium**: Trial 30 dana @ 0€ → mesečno @ 149€ EUR
5. Kopiraj **plan ID** za svaki (počinje sa `P-`) → uneti u `web/checkout.html` u `PAYPAL_PLAN_IDS` konstantu (basic, pro, premium).
6. U istoj fajli zameni `PAYPAL_CLIENT_ID = "sb"` sa tvojim live client ID-jem.

### 10c. PayPal webhook konfiguracija

1. PayPal Dashboard → **Apps & Credentials** → tvoja aplikacija → **Webhooks** → "Add Webhook".
2. **Webhook URL**: `https://agencija-za-nekretnine-nine.vercel.app/webhook/paypal`
3. **Event types** (selektuj samo ove):
   - `BILLING.SUBSCRIPTION.ACTIVATED`
   - `BILLING.SUBSCRIPTION.RE-ACTIVATED`
   - `BILLING.SUBSCRIPTION.CANCELLED`
   - `BILLING.SUBSCRIPTION.EXPIRED`
   - `BILLING.SUBSCRIPTION.SUSPENDED`
   - `BILLING.SUBSCRIPTION.PAYMENT.FAILED`
   - `PAYMENT.SALE.COMPLETED`
   - `PAYMENT.SALE.DENIED`
4. Posle kreiranja, kopiraj **Webhook ID** → dodaj kao `PAYPAL_WEBHOOK_ID` u Vercel env.
5. Triggeruj redeploy.

### 10d. Test posle deploy-a

```bash
# 1. Health check (treba 404 — endpoint nije implementiran, ali server živi)
curl https://agencija-za-nekretnine-nine.vercel.app/webhook/paypal

# 2. Test webhook bez verifikacije (samo dok PAYPAL_WEBHOOK_ID nije setovan):
curl -X POST https://agencija-za-nekretnine-nine.vercel.app/webhook/paypal \
  -H "Content-Type: application/json" \
  -d '{"event_type":"BILLING.SUBSCRIPTION.ACTIVATED","resource":{"id":"I-TEST123"}}'

# 3. Real-life test: registruj testni nalog, prođi PayPal checkout (sandbox plan IDs),
#    proveri logove u Vercel Dashboard → tvoja funkcija → Logs.
#    Email "Pretplata aktivirana" treba da stigne na test email.
```

### 10e. Sanity checklist

- [ ] Vercel env varijable popunjene (sve iz tabele 10a)
- [ ] PayPal app kreirana, plan ID-ovi dobijeni
- [ ] `web/checkout.html` ima pravi `PAYPAL_CLIENT_ID` i plan ID-ove
- [ ] PayPal webhook URL podešen + Webhook ID upisan u Vercel env
- [ ] Sandbox test prošao (email stigao)
- [ ] Live test (mali iznos, sa svojom karticom)

## 11. Production deploy checklist

Pre prvog real run-a:

- [ ] Gmail nalog + App Password kreirani
- [ ] Supabase ključ rotiran (ako je bio commit-ovan)
- [ ] Lokalni `.env` popunjen
- [ ] `python -X utf8 admin/check_env.py` → sve zeleno
- [ ] GitHub Secrets postavljeni
- [ ] Vercel alias pokazuje na najnoviji deploy
- [ ] Vercel env varijable za PayPal popunjene (vidi 10a)
- [ ] PayPal Business app + plan ID-ovi + webhook konfigurisani (10b–10c)
- [ ] Probni run sa svojim mejlom: `python -X utf8 main.py` — mejl stiže u inbox
- [ ] Ručno triggeruje GHA workflow: `gh workflow run weekly_report.yml` — green
- [ ] Sandbox PayPal checkout prošao end-to-end (email aktivacije stigao)
