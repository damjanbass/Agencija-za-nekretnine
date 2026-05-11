# Onboarding nove agencije

Procedura za dodavanje nove agencije u sistem. Cilj: pod 10 minuta od potpisa do prvog login-a.

## Preduslov

- Lokalni `.env` popunjen (vidi [DEPLOYMENT.md](DEPLOYMENT.md)).
- Sa klijentom dogovoreni: naziv agencije, kontakt email, plan, nedeljni cilj prihoda, lista agenata.

## Korak 1 — Kreiraj agenciju

```bash
python -X utf8 admin/onboard.py create-agency \
    --name "Agencija Petrović d.o.o." \
    --email "office@agencija-petrovic.rs" \
    --plan basic \
    --revenue-goal 6000 \
    --user-password "PetrovicStart2026"
```

Šta `--revenue-goal` znači: **nedeljni** cilj prihoda u €. Mesečni se računa kao `4 × nedeljni`. Pitaj klijenta koliko želi da zarađuje **nedeljno**.

Plan opcije:
- `basic` — 69€/mes, AI analiza, mejl slanje, 5 agenata, 1 tržišni izvor
- `pro` — 139€/mes, sve iz basic-a + mesečni izveštaj, PDF, benchmark, 3 tržišna izvora, do 15 agenata
- `premium` — 199€/mes, neograničeno + custom branding

Skripta ispiše:
- `agency_id` (zapamti — treba za naredne komande)
- `public_token` (link za javni dashboard)
- Login URL + početni password (za slanje klijentu)

## Korak 2 — Dodaj agente

Po jednu komandu za svakog agenta. Email je opcioni ali **preporučen** (potreban za personalne izveštaje).

```bash
python -X utf8 admin/onboard.py add-agent \
    --agency-id "abc12345-..." \
    --name "Marko Petrović" \
    --email "marko@agencija-petrovic.rs"
```

Plan ograničava broj agenata. Ako prebaciš limit, `main.py` će automatski uzeti prvih N po planu.

## Korak 3 — Pošalji klijentu

Šablon mejla:

```
Pozdrav [Naziv kontakt osobe],

Vaš nalog je aktiviran. Detalji:

  Web panel:     https://agencija-za-nekretnine-nine.vercel.app/index.html
  Email:         office@agencija-petrovic.rs
  Početni pass:  PetrovicStart2026  (promenite ga nakon prvog login-a)
  Plan:          Basic (69€/mes)

  Javni dashboard (za interno deljenje):
  https://agencija-za-nekretnine-nine.vercel.app/public.html?token=...

Uputstvo za korišćenje je u prilogu (PDF).

Prvi nedeljni izveštaj stiže u ponedeljak ujutru.
Podatke za prvu nedelju unesite u panel do nedelje uveče.

Za sva pitanja: izvestaji.agencija@gmail.com
```

Priloži [uputstvo_za_klijenta.html](uputstvo_za_klijenta.html) (otvori u browser-u → Ctrl+P → Save as PDF).

## Korak 4 — Verifikuj

```bash
python -X utf8 admin/onboard.py list-agencies
```

Treba da vidiš novu agenciju u listi.

Posle prvog unosa podataka klijenta, ručno triggeruje workflow da pošalješ test izveštaj:

```bash
gh workflow run weekly_report.yml
```

## Naknadne izmene

### Klijent menja plan
```bash
python -X utf8 admin/onboard.py set-plan --agency-id "abc..." --plan pro
```

### Klijent menja nedeljni cilj
```bash
python -X utf8 admin/onboard.py set-goal --agency-id "abc..." --revenue-goal 8000
```

### Dodatni agenti (kasnije)
Iste `add-agent` komande kao u Koraku 2.

### Klijent je zaboravio password
Otvori Supabase Dashboard → Authentication → Users → klikni na korisnika → "Send password recovery". Alternativno, postavi nov password preko admin API-ja:

```python
# Supabase Python:
sb.auth.admin.update_user_by_id(user_id, {"password": "NoviPass2026"})
```

### Klijent prekinuo saradnju
Supabase Dashboard → tabela `agencies` → `active = false`. Time se isključuje iz svih cron run-ova ali se istorija čuva.

## Troubleshooting

**`[!] Auth user nije kreiran: User already registered`**
Email je već u Supabase Auth. Otvori Authentication → Users, obriši stari nalog ili koristi drugu email adresu.

**`[!] Agencija nije kreirana` (ali user_id već kreiran)**
Skripta to javi i navede `user_id` za ručno čišćenje. Otvori Authentication → Users → obriši taj user_id, pa pokreni create-agency ponovo.

**Klijent ne može da uloguje**
1. Proveri da li je `auth_user` kreiran (Supabase → Authentication).
2. Proveri da li `agencies.user_id` pokazuje na tog user-a (Supabase → Table editor → agencies).
3. Ako se ne podudaraju, ispravi `agencies.user_id` ručno.
