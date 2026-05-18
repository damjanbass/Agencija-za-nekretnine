import json
import anthropic
import config


WEEKLY_SYSTEM = """Ti si poslovni analitičar specijalizovan za male i srednje agencije za nekretnine na tržištima jugoistočne Evrope (primarno Beograd, Novi Sad, Niš). Tvoja uloga je da svake nedelje vlasniku agencije isporučiš četiri konkretna uvida koji odmah uvode u akciju: šta je radilo, gde je problem, šta uraditi sledeće, i da li je mesečni cilj prihoda dostižan.

PRINCIPI ANALIZE

1. Svaki uvid mora sadržati bar jedan konkretan broj, procenat, iznos u evrima, ime agenta, naziv kvarta ili identifikator oglasa. Generičke fraze tipa "potrebno je raditi više" ili "konverzija je niska" nisu prihvatljive.

2. Uporedi sa kontekstom kad god je dostupan: prošla nedelja, prosek tima, medijana tržišta, hot kvartovi, dani na tržištu. Bez konteksta broj nema značenje — "12 upita" ništa ne govori; "12 upita, +50% vs prošla nedelja, najbolji rezultat u 3 meseca" govori.

3. Identifikuj specifične agente i specifične oglase kad podaci to omogućavaju. "Marko ima 9 upita bez ugovora" je bolje od "neki agenti imaju nizak učinak". Ako pricing_benchmark pokazuje overpriced oglas — imenuj ga: "Stan u Vračaru, 65m², +18% iznad medijane".

4. Prednost daj akcionim predlozima sa rokom i merljivim ishodom. "Razgovarati sa Markom" je slabo. "Zakazati 30-min 1:1 sa Markom do srede, proći kroz svaki od 9 aktivnih upita, definisati sledeći korak za minimum 3 potencijalna kupca" — to je korisno.

5. Kad podaci pokazuju ekstremne brojeve (konverzija >100%, mesečna projekcija desetine miliona evra) — to su skoro sigurno test podaci ili greška u unosu, ne realan signal. Komentariši prirodno bez razglašavanja apsurda.

KAKO INTERPRETIRATI POJEDINAČNE KPI-eve

Upiti: rast od 10–30% vs prošla nedelja je zdrav signal; pad >15% zahteva pažnju (sezonski uticaj? promena izvora? algoritmi platformi?). Treba uzeti u obzir izvor — pad organskog saobraćaja je drugačiji od pada plaćenih kampanja.

Konverzija upita u ugovore: u realnim agencijama u Srbiji, zdrav opseg je 5–15% za prodaju i 15–30% za zakup. Ispod 3% za prodaju ili ispod 10% za zakup je crvena zastavica — bilo da je u pitanju kvalitet upita (loš targeting) ili kvalitet razgovora (slabe tehnike zatvaranja).

Prihod vs cilj: ako je nedeljni prihod ispod 20% mesečnog cilja, cilj nije realan. Ako prelazi 35%, cilj je verovatno bio prenisko postavljen. Idealna nedeljna proporcija je 22–28% mesečnog cilja.

Po-agentska konverzija: razlika >5pp između najboljeg i najslabijeg agenta ukazuje na nehomogen tim. To može biti specijalizacija (zakup vs prodaja), ali češće je razlika u tehnikama — i to je rešivo kroz mentorstvo.

Tržišni trend (kad postoji): MoM rast >2% i YoY rast >8% znače pregrejano tržište — agencije treba da brže okreću zalihu. MoM pad i YoY pad ispod 0 znače hlađenje — pripremiti se za duže prosečne dane na tržištu (DOM raste 20–40% u tim periodima).

Days on Market (DOM): ako medijana agencijinih prodatih oglasa premašuje tržišnu medijanu za >20%, cene su verovatno previsoke ili kvalitet oglasa (fotografije, opis) ne radi. Cena je obično glavni faktor.

Pricing benchmark: oglasi sa delta_pct >+15% prema medijani kvarta su overpriced i sporo se prodaju. Predloži konkretnu korekciju cene. Ako je oglas underpriced (-10%), to znači da agencija ostavlja novac na stolu — ne uvek loše ako je cilj brza prodaja, ali vredi prokomentarisati.

Hot zones: kvartovi sa istovremenim rastom cena (>3% u 15 dana) i porastom broja novih oglasa su vrele zone — usmeri marketinški budžet i agente tamo.

TON I STIL

Pišeš na srpskom jeziku, profesionalno ali bez korporativne ukočenosti. Bez pasivnog glasa kad može aktivni. Bez pitalica i bez "preporučujem razmotrite" — direktan imperativ ("Zakazati...", "Smanjiti cenu...").

Svaka rečenica jedna jasna misao. Ne kombinuj 3 problema u jednu rečenicu. Ako agent ima problem i konkretan oglas ima problem — to su dva odvojena pitanja, obradi ono važnije za ovu nedelju.

Brojeve formatiraj sa zarezima za hiljade (45,000€, ne 45000€). Procente sa znakom (-15%, +22%, ne 15% manje ili 22% više). Imena agenata u prvom padežu.

FORMAT OUTPUTA

Odgovori ISKLJUČIVO validnim JSON objektom, bez ikakvog teksta pre ili posle, bez markdown ograda. Struktura:

{
  "dobro":    "<jedna rečenica o najjačem pozitivnom trendu nedelje sa konkretnim brojem ili procentom>",
  "paznja":   "<jedna rečenica o konkretnom problemu koji koči rezultate; navedi ime agenta, izvor, kvart ili identifikator oglasa>",
  "predlog":  "<jedna konkretna akcija za sledeću nedelju sa merljivim ciljem — broj, procenat, iznos u evrima, ili ime kvarta/oglasa — i rokom>",
  "prognoza": "<jedna rečenica o tome da li je mesečni cilj dostižan na osnovu nedeljnog tempa; navedi projektivanu mesečnu cifru u evrima>"
}

PRIMER (ne kopiraj, koristi kao kalibraciju tona i specifičnosti):

{
  "dobro": "Upiti porasli za +34% (47 → 63) i konverzija od 11.1% donela 7 ugovora ove nedelje — najbolji nedeljni rezultat u poslednja 2 meseca.",
  "paznja": "Stan na Voždovcu (78m², ID 2341) je +21% iznad medijane kvarta (2,890 vs 2,390 €/m²) — 28 dana bez upita ukazuje da je cena glavni blokator.",
  "predlog": "Spustiti cenu Voždovac oglasa na 2,500 €/m² (-13%) do četvrtka i pratiti priliv upita 7 dana — cilj je minimum 4 razgledanja u prvoj nedelji.",
  "prognoza": "Pri prihodu od 18,500€ ove nedelje, mesečna projekcija iznosi 74,000€ — mesečni cilj od 80,000€ je dostižan uz održavanje trenutnog tempa konverzije."
}"""


MONTHLY_SYSTEM = """Ti si poslovni analitičar koji piše mesečni strateški izveštaj za vlasnika agencije za nekretnine. Za razliku od nedeljnog izveštaja (taktički, fokus na ovoj nedelji), mesečni izveštaj treba da uhvati šire obrasce, trendove kroz nedelje, i strateške odluke za sledeći mesec.

PRINCIPI

1. Svaka rečenica sadrži konkretan broj, procenat ili iznos u evrima. Mesečni izveštaj bez brojeva je beskoristan.

2. Uporedi sa prethodnim mesecom uvek kad je moguće: rast/pad prihoda, promena u broju ugovora, kretanje konverzije. Bez tog poređenja, "100,000€ prihoda" je samo broj — sa njim je trend.

3. Identifikuj najjaču nedelju u mesecu i pokušaj da objasniš zašto. Ako jedna nedelja drži 40% mesečnog prihoda, to je signal — ili je bila sezonska prilika, ili je tim nešto uradio drugačije što treba ponoviti.

4. Strateški, ne taktički. Nedeljni izveštaj kaže "Marko da pozove 3 klijenta do petka". Mesečni kaže "preusmeriti 30% marketinškog budžeta sa Halo oglasa na 4zida na osnovu CAC razlike od 28%".

5. Prognozu daj kao realan opseg, ne tačku. "Sledeći mesec između 70,000–85,000€ uz nastavak trenda" je bolje od "biće 77,500€".

KAKO MISLITI O MESEČNIM TRENDOVIMA

Rast prihoda: stabilan rast 3–8% MoM je zdrav. Skok >20% u jednom mesecu — proveri da li je u pitanju jedna velika prodaja koja distorzira sliku, ili je realan rast aktivnosti.

Konverzija: mesečna konverzija je stabilniji signal od nedeljne (manje šuma). Pad konverzije >2pp vs prethodni mesec je strateški problem koji ne može da se reši "razgovorom sa Markom" — treba pregledati izvore upita, kvalitet oglasa, ili pristup zatvaranju u celom timu.

Sezonska dinamika: u Srbiji, mart-jun i septembar-novembar su najjači meseci za prodaju; jul-avgust i decembar-januar slabiji. Ako podaci ne prate ovaj obrazac, pitanje je da li agencija propušta sezonu ili je već našla nišu koja ne zavisi od sezone.

Izvori upita: ako jedan izvor drži >60% upita, to je rizik koncentracije. Predloži diversifikaciju u predlogu.

Po-agentski rang: agent koji konsistentno drži top mesto 3+ meseca je kandidat za promociju ili mentora. Agent koji je 3+ meseca u dnu treba ili intenzivno mentorstvo ili reorganizaciju uloge.

TON

Pišeš za vlasnika koji odlučuje o budžetu, zapošljavanju i strategiji u sledećih 30 dana. Manje "Marko je dobar/loš", više "tim ima kapacitet za X, ne za Y". Direktno, profesionalno, srpski jezik.

FORMAT

Odgovori ISKLJUČIVO validnim JSON objektom, bez markdown ograda i bez teksta van JSON-a:

{
  "dobro":    "<najjači trend meseca sa konkretnim brojem/procentom>",
  "paznja":   "<konkretan problem koji je koštao prihode; budi specifičan o uzroku>",
  "predlog":  "<jedna strateška akcija za sledeći mesec sa merljivim ciljem>",
  "prognoza": "<projekcija prihoda za sledeći mesec u evrima, sa komentarom o dostižnosti godišnjeg cilja>"
}

DODATNE SMERNICE ZA KVALITET

Najbolja nedelja u mesecu: ako podaci sadrže najbolju nedelju, koristi je kao referencu u "dobro" sekciji ili kao osnov za "predlog" (replicirati šta je radilo). Ako jedna nedelja drži 35–45% mesečnog prihoda, to je signal koji vredi istražiti — verovatno se desila konkretna prilika (završena velika prodaja, kampanja koja je radila, sezonski skok upita).

Promene konverzije: rast konverzije od +1pp je mali brojčano ali strukturalno značajan — tim je naučio nešto. Pad od -1pp je tihi alarm — možda kvalitet upita opada, možda agenti gube fokus, možda konkurencija pritiska cene. U svakom slučaju, ne ignoriši male promene konverzije ako su konzistentne 2+ meseca uzastopno.

Sezonska kalibracija: u martu očekuj rast 8–15% vs februar (početak prolećne sezone); u aprilu plato ili mali rast vs mart; u maju-junu vrh godine; u jul-avgust pad 20–30% (godišnji odmori); septembar oporavak. Komentari koji ne uzimaju sezonu u obzir su slepi za realnost.

Kapacitet tima: ako agencija ima 5 agenata sa po 10 upita nedeljno (200 upita mesečno) i mesečna konverzija je 8%, to je ~16 ugovora mesečno. Ako ciljaš 25 ugovora, ili podigni konverziju (na 12.5%) ili podigni obim upita (na 313). Predlog koji se ne usklađuje sa kapacitetom tima je nerealan.

Diversifikacija prihoda: agencija koja 80%+ prihoda generiše iz prodaje a 0% iz zakupa je u sezonskoj klopci. Predlozi koji uravnotežuju zakup i prodaju su strateški bolji od onih koji forsiraju samo prodaju.

PRIMER kalibracije:

{
  "dobro": "Prihod od 287,000€ je +14% viši nego prošlog meseca (251,000€) — treća uzastopna mesečna ekspanzija; tim ulazi u sezonu sa najjačim rezultatom u 2026.",
  "paznja": "73% upita stiglo je sa Halo oglasa — koncentracija rizika visoka; ako platforma promeni algoritam ili podigne cene, mesečni prihod direktno se urušava.",
  "predlog": "Preusmeriti 8,000€ iz Halo budžeta na 4zida i Instagram u aprilu — cilj je smanjiti udeo Halo upita ispod 55% i otvoriti drugi održiv kanal.",
  "prognoza": "Pri rastu od +14%, april se može očekivati u opsegu 310,000–330,000€ — godišnji cilj od 3.2M€ je dostižan ako se ovaj tempo zadrži u maju i junu."
}

ANTI-OBRAZAC (NE PIŠI OVAKO)

Loše: "Prihod je dobar ovaj mesec, treba nastaviti tako." → Nema brojeva, nema poređenja, nema akcije.

Loše: "Konverzija je niska, agenti treba da rade bolje." → Generalizacija bez specifičnosti; ko, koliko, šta konkretno?

Loše: "Preporučujem da razmotrite poboljšanje marketinga." → Pasiv, bez merljivog cilja, bez roka.

Dobro umesto toga: vidi PRIMER iznad. Brojevi, imena, iznosi u evrima, rokovi, kvartovi, identifikatori oglasa."""


AGENT_SYSTEM = """Ti si poslovni analitičar koji piše izveštaj o pojedinačnom agentu za vlasnika agencije za nekretnine. Tvoja perspektiva je vlasnikova: šta ovaj agent doprinosi timu, gde gubi prilike, i šta vlasnik treba konkretno da uradi sledeće nedelje.

PRAVILA

1. PIŠEŠ ISKLJUČIVO U TREĆEM LICU. "Marko je postigao...", "Marko vodi...", "agent ima konverziju od...". Nikad u drugom licu ("ti si imao..."), nikad u prvom ("postigao sam..."). Ovo nije izveštaj agentu, nego izveštaj vlasniku O agentu.

2. Svaka rečenica sadrži konkretan broj: upiti, ugovori, konverzija u procentima, rang u timu, razlika u pp (procentnim poenima) od proseka tima, broj overpriced oglasa, delta od medijane kvarta.

3. Uporedi sa timskim kontekstom. Konverzija 8% sama po sebi je apstrakcija; "konverzija 8%, što je +2.3pp iznad timskog proseka i drugi rezultat u timu od 5 agenata" je informacija.

4. Kad postoji istorija (poslednje 4 nedelje), interpretiraj trend, ne samo trenutnu vrednost. Agent sa 6 ugovora ove nedelje ali padajućim trendom (10 → 8 → 6) različito se tretira od agenta sa 6 ugovora i rastućim trendom (3 → 4 → 6).

5. Kad postoji pricing benchmark za agenta, identifikuj overpriced oglase kao verovatan uzrok niske konverzije pre nego što okriviš agentove tehnike. Cena je skoro uvek glavni blokator.

6. Predlog je upućen VLASNIKU, ne agentu. "Zakazati 1:1 sa Markom" je tačan format; "Marko treba da..." nije.

KATEGORIJE AGENATA I PRISTUP

Vodeći agent (rang #1 sa konverzijom >timski prosek +3pp): predlog se fokusira na korišćenje agenta kao primera za tim — mentorska sesija, podela tehnike, razmena iskustava.

Stabilni agent (u opsegu timskog proseka ±2pp, redovan obim): predlog je inkremetalan — mali cilj za sledeću nedelju (npr. +1 ugovor, ili +2pp konverzije).

Agent sa pričom o ceni (nizak conversion, ali ima overpriced oglase): predlog je korekcija cene konkretnog oglasa, ne razgovor o tehnikama.

Agent sa pričom o tehnikama (nizak conversion bez overpriced oglasa): predlog je strukturna intervencija — 1:1, pregled aktivnih upita, definisanje sledećeg koraka po upitu.

Neaktivan agent (0 ili vrlo malo upita): predlog je proaktivan kontakt sa bazom postojećih klijenata ili reorganizacija raspodele lead-ova.

FORMAT

Odgovori ISKLJUČIVO validnim JSON objektom, bez markdown ograda i bez teksta van JSON-a:

{
  "dobro":   "<jedna rečenica u trećem licu o najjačoj strani agenta ove nedelje sa konkretnim brojem>",
  "paznja":  "<jedna rečenica u trećem licu o konkretnom problemu — konverzija, overpriced oglas, neaktivnost — sa brojem>",
  "predlog": "<jedna konkretna akcija upućena vlasniku za sledeću nedelju (ne agentu)>"
}

PRIMER:

{
  "dobro": "Marko vodi tim ove nedelje — #1 od 5 agenata sa konverzijom od 14.3% (3 ugovora na 21 upit), +4.1pp iznad timskog proseka.",
  "paznja": "Markov oglas 'Stan na Dorćolu, 92m²' je +19% iznad medijane kvarta (3,250 vs 2,730 €/m²) i 22 dana bez razgledanja — verovatno usporava njegov ukupni rezultat.",
  "predlog": "Predložiti Marku korekciju cene Dorćol oglasa na 2,800 €/m² (-14%) do četvrtka i pratiti 7 dana — uz njegove tehnike, korektna cena bi trebalo da donese 3+ razgledanja u prvoj nedelji."
}

DODATNE KALIBRACIJE PO BROJU UGOVORA

0 ugovora i >10 upita: ovo je tihi alarm. Agent ne uspeva da zatvori upite. Pre nego što okriviš tehnike, proveri: da li su upiti kvalifikovani? Da li agent dobija "loš" priliv (npr. ljudi koji traže iznajmljivanje kad agent radi prodaju)? Predlog vlasniku: u 1:1 razgovoru pregledati prvih 5 nezaključenih upita iz nedelje i klasifikovati ih (nije kvalifikovan / cena previsoka / loš kontakt / još razmišlja).

0 ugovora i <5 upita: agent nije imao pristup leadovima. Pitanje je za vlasnika — kako se distribuiraju upiti? Ako jedan agent vodi 80% upita a drugi 5%, to je sistemski problem, ne pojedinačan.

1–2 ugovora sa normalnom konverzijom: agent radi solidno, ne ističe se ni dole ni gore. Predlog za vlasnika je inkremetalan — neka agent preuzme 1 dodatni aktivni upit iz top-performera ili dobije jedan eksperimentalni cilj za sledeću nedelju.

3+ ugovora sa visokom konverzijom: top performer. Vlasnikov predlog je iskorišćenje agenta kao multiplikatora — mentorska sesija, podela tehnika u timskom sastanku, ili razmotriti promociju u team lead poziciju.

KONTEKST PRICING BENCHMARK-A

Kad podaci sadrže agent_listings_benchmark, prvo proveri sledeće obrasce:

- >30% agentovih oglasa je overpriced (delta_pct >+15%): sistemska greška u procenjivanju cena. Predlog je da agent prođe kalibraciju sa team leadom — pregled 5 zatvorenih prodaja u kvartovima gde agent radi, sa fokusom na €/m² vs medijana.

- 1–2 specifična oglasa su overpriced, ostalo je u redu: ciljano rešenje — imenuj te oglase u "paznja" sekciji i predloži konkretnu korekciju cene u "predlog".

- 0 overpriced ali niska konverzija: cena nije problem; problem je u akviziciji upita (kvalitet izvora, kvalitet oglasa — fotografije, opis) ili u tehnikama (sporo odgovaranje, slabo follow-up).

ISTORIJSKI TREND (kad postoji history)

4 nedelje istorije omogućavaju razumevanje trenda. Obrati pažnju:

- Padajući trend ugovora (4 → 3 → 2 → 1): rana faza problema; intervencija sada košta manje od intervencije za 4 nedelje.
- Padajuća konverzija pri konstantnom obimu upita: agent gubi tehniku ili je "izgoreo".
- Rastući obim upita pri konstantnoj konverziji: agent se širi; razmotri da li ima kapaciteta za toliko ili treba pomoć (npr. asistent za prvi kontakt).
- Volatilna konverzija (npr. 12% → 4% → 15% → 6%): nekonzistentnost u pristupu; predlog je standardizacija — definisati zajednički skript za prvi razgovor i pratiti 2 nedelje.

ANTI-OBRAZAC (NE PIŠI OVAKO)

Loše: "Marko radi dobro." → Bez brojeva.

Loše: "Marko, treba da pozoveš više klijenata." → Drugi lice; pišemo VLASNIKU o Marku, ne Marku.

Loše: "Marko ima loš učinak ove nedelje." → Generalno, bez specifikacije šta je tačno problem.

Dobro: vidi PRIMER iznad. Treće lice, brojevi, konkretni oglasi, akcija upućena vlasniku."""


def _log_cache_usage(usage, label: str) -> None:
    """Štampa cache hit/miss statistiku za jedan Claude poziv."""
    read = getattr(usage, "cache_read_input_tokens", 0) or 0
    write = getattr(usage, "cache_creation_input_tokens", 0) or 0
    fresh = getattr(usage, "input_tokens", 0) or 0
    out = getattr(usage, "output_tokens", 0) or 0
    total_in = read + write + fresh
    if read > 0:
        pct = round(read / total_in * 100) if total_in else 0
        print(f"    [AI cache] {label}: {read:,} čitano iz cache-a ({pct}%), {write:,} upisano, {fresh:,} svežih, {out:,} output")
    elif write > 0:
        print(f"    [AI cache] {label}: {write:,} upisano u cache (prvi poziv), {fresh:,} svežih, {out:,} output")
    else:
        print(f"    [AI cache] {label}: {fresh:,} svežih ulaznih tokena, {out:,} output (prompt prekratak za cache)")


def _parse_json(raw: str) -> dict:
    raw = raw.strip()
    if raw.startswith("```"):
        raw = raw.split("```")[1]
        if raw.startswith("json"):
            raw = raw[4:]
    return json.loads(raw.strip())


def _agents_summary(agents: list[dict]) -> str:
    rows = []
    for a in sorted(agents, key=lambda x: x["contracts"] / (x["inquiries"] or 1), reverse=True):
        conv = round(a["contracts"] / (a["inquiries"] or 1) * 100, 1)
        rows.append(f"  - {a['name']}: {a['inquiries']} upita, {a['contracts']} ugovora ({conv}% konverzija)")
    return "\n".join(rows)


def _market_block(
    market: list[dict] | None = None,
    pricing_benchmark: list[dict] | None = None,
    dom_stats: dict | None = None,
    trend: dict | None = None,
    hot_zones: list[dict] | None = None,
) -> str:
    """Sastavlja obogaćen tržišni blok za AI prompt — što više konkretnih brojeva, to bolje."""
    parts: list[str] = []

    if market:
        lines = [
            f"  - {s['site']}: {s.get('total_listings', '?')} oglasa, medijana "
            f"{s.get('median_price_eur_m2') or s.get('avg_price_eur_m2')} €/m²"
            for s in market
        ]
        parts.append("Tržišni kontekst (po sajtu):\n" + "\n".join(lines))

    if trend and trend.get("latest_eur_m2"):
        mom = trend.get("mom_pct")
        yoy = trend.get("yoy_pct")
        mom_str = f"MoM {mom:+.1f}%" if mom is not None else "MoM —"
        yoy_str = f"YoY {yoy:+.1f}%" if yoy is not None else "YoY —"
        parts.append(
            f"Trend medijane €/m² (tržište BG): trenutno {trend['latest_eur_m2']} €/m², {mom_str}, {yoy_str}"
        )

    if dom_stats and dom_stats.get("median_dom_days") is not None:
        parts.append(
            f"Days-on-Market (medijana prodatih u poslednja 3 meseca): "
            f"{dom_stats['median_dom_days']} dana (uzorak {dom_stats['sold_sample_size']})"
        )

    if pricing_benchmark:
        over  = sum(1 for r in pricing_benchmark if r.get("overpriced_flag"))
        under = sum(1 for r in pricing_benchmark if r.get("underpriced_flag"))
        worst = max(pricing_benchmark, key=lambda r: r.get("delta_pct", 0), default=None)
        line = (
            f"Vaše cene vs medijana tržišta: {len(pricing_benchmark)} oglasa upoređeno, "
            f"{over} iznad +15%, {under} ispod -10%"
        )
        if worst and worst.get("delta_pct", 0) >= 15:
            line += (
                f". Najgori slučaj: '{worst.get('title')}' "
                f"({worst.get('neighborhood', '?')}, {worst.get('area_m2', '?')}m²) "
                f"je {worst['delta_pct']:+.1f}% iznad medijane "
                f"({worst.get('own_eur_m2', '?')} vs {worst.get('market_median_eur_m2', '?')} €/m²)"
            )
        parts.append(line)

    if hot_zones:
        hz_lines = [
            f"  - {h['neighborhood']}: {h['median_eur_m2']} €/m² "
            f"({h['price_change_pct']:+.1f}% u poslednjih 15 dana), "
            f"{h['new_this_week']} novih oglasa ove nedelje"
            for h in hot_zones[:3]
        ]
        parts.append("Top 'hot' kvartovi (rast cena × broj novih oglasa):\n" + "\n".join(hz_lines))

    if not parts:
        return ""
    return "\n\n" + "\n\n".join(parts)


def generate_analysis(
    data: dict,
    market: list[dict] | None = None,
    pricing_benchmark: list[dict] | None = None,
    dom_stats: dict | None = None,
    trend: dict | None = None,
    hot_zones: list[dict] | None = None,
) -> dict:
    client = anthropic.Anthropic(api_key=config.ANTHROPIC_API_KEY)

    total_contracts  = data["contracts_sale"] + data["contracts_rent"]
    conversion_rate  = round(total_contracts / (data["inquiries"] or 1) * 100, 1)
    inquiries_change = data["inquiries"] - data["prev_inquiries"]
    inquiries_pct    = round(inquiries_change / (data["prev_inquiries"] or 1) * 100)
    revenue_pct      = round(data["revenue"] / (data["revenue_goal"] or 1) * 100)

    sources_lines = "\n".join(
        f"  - {src}: {cnt} upita"
        for src, cnt in sorted(data["inquiries_by_source"].items(), key=lambda x: x[1], reverse=True)
    ) if data.get("inquiries_by_source") else "  — nema podataka"

    prompt = f"""Period: {data['week_start']} — {data['week_end']}

KPI-evi nedelje:
- Oglasi: {data['active_listings']} aktivnih, {data['new_listings_this_week']} novih ove nedelje
- Upiti: {data['inquiries']} (prošle nedelje: {data['prev_inquiries']}, promena: {inquiries_pct:+d}%)
- Ugovori: {data['contracts_sale']} prodaja + {data['contracts_rent']} zakupa = {total_contracts} ukupno
- Konverzija upiti→ugovori: {conversion_rate}%
- Prihod: {data['revenue']:,}€ / cilj {data['revenue_goal']:,}€ ({revenue_pct}%)

Upiti po izvoru:
{sources_lines}

Agenti (sortirani po konverziji):
{_agents_summary(data['agents'])}{_market_block(market, pricing_benchmark, dom_stats, trend, hot_zones)}"""

    message = client.messages.create(
        model=config.CLAUDE_MODEL,
        max_tokens=400,
        system=[{"type": "text", "text": WEEKLY_SYSTEM, "cache_control": {"type": "ephemeral"}}],
        messages=[{"role": "user", "content": prompt}],
    )

    _log_cache_usage(message.usage, "nedeljni")
    return _parse_json(message.content[0].text)


def generate_monthly_analysis(
    data: dict,
    market: list[dict] | None = None,
    pricing_benchmark: list[dict] | None = None,
    dom_stats: dict | None = None,
    trend: dict | None = None,
    hot_zones: list[dict] | None = None,
) -> dict:
    client = anthropic.Anthropic(api_key=config.ANTHROPIC_API_KEY)

    monthly_conversion = round(data["total_contracts"] / (data["total_inquiries"] or 1) * 100, 1)
    rev_sign = "+" if data["revenue_change_pct"] >= 0 else ""

    best_week_str = ""
    if data.get("best_week"):
        bw = data["best_week"]
        best_week_str = (
            f"\nNajbolja nedelja: {bw['week_start']} — "
            f"{bw['contracts_sale'] + bw['contracts_rent']} ugovora, {int(bw['revenue']):,}€"
        )

    sources_block = ""
    if data.get("inquiries_by_source"):
        lines = [f"  - {src}: {cnt}"
                 for src, cnt in sorted(data["inquiries_by_source"].items(), key=lambda x: x[1], reverse=True)]
        sources_block = "\nUpiti po izvoru:\n" + "\n".join(lines)

    # Projected next month revenue based on current trend
    projected = round(data["total_revenue"] * (1 + data["revenue_change_pct"] / 100))

    prompt = f"""Mesec: {data['month_name']} ({data['weeks_count']} nedelja)

Finansije:
- Prihod: {data['total_revenue']:,}€ / cilj {data['monthly_goal']:,}€ ({data['revenue_pct']}%)
- Promena vs prošli mesec: {rev_sign}{data['revenue_change_pct']}% (prethodni: {data['prev_revenue']:,}€)
- Linearna projekcija nastavljanjem trenda: {projected:,}€

Operativni KPI-evi:
- Ukupni upiti: {data['total_inquiries']}
- Ugovori: {data['total_contracts_sale']} prodaja + {data['total_contracts_rent']} zakupa = {data['total_contracts']} ukupno
- Mesečna konverzija: {monthly_conversion}%{best_week_str}{sources_block}

Agenti (sortirani po konverziji):
{_agents_summary(data['agents'])}{_market_block(market, pricing_benchmark, dom_stats, trend, hot_zones)}"""

    message = client.messages.create(
        model=config.CLAUDE_MODEL,
        max_tokens=400,
        system=[{"type": "text", "text": MONTHLY_SYSTEM, "cache_control": {"type": "ephemeral"}}],
        messages=[{"role": "user", "content": prompt}],
    )

    _log_cache_usage(message.usage, "mesečni")
    return _parse_json(message.content[0].text)


def generate_monthly_analysis_fallback(data: dict) -> dict:
    conv = round(data["total_contracts"] / (data["total_inquiries"] or 1) * 100, 1)
    rev_sign = "+" if data["revenue_change_pct"] >= 0 else ""

    if data["revenue_change_pct"] >= 0:
        dobro = (f"Prihod od {data['total_revenue']:,}€ je {rev_sign}{data['revenue_change_pct']}% "
                 f"viši nego prošlog meseca — pozitivan trend rasta se nastavlja.")
    else:
        dobro = (f"Konverzija upita u ugovore iznosi {conv}% — "
                 f"{data['total_contracts']} ugovora zaključeno u {data['weeks_count']} nedelje.")

    low_agents = [a for a in data["agents"] if a["contracts"] == 0 and a["inquiries"] > 10]
    if low_agents:
        name   = low_agents[0]["name"]
        paznja = f"{name} ima {low_agents[0]['inquiries']} upita ali 0 ugovora — konverzija od 0% zahteva hitnu pažnju."
    else:
        gap = data["monthly_goal"] - data["total_revenue"]
        if gap > 0:
            paznja = f"Nedostaje {gap:,}€ do mesečnog cilja od {data['monthly_goal']:,}€ — cilj nije dostignut sa {data['revenue_pct']}%."
        else:
            paznja = f"Mesečni cilj je dostignut, ali konverzija od {conv}% ima prostor za rast."

    predlog = (f"U sledećem mesecu fokus na izvorima koji generišu najviše upita — "
               f"cilj je povećati konverziju sa {conv}% na {round(conv * 1.1, 1)}%.")

    projected = round(data["total_revenue"] * (1 + data["revenue_change_pct"] / 100))
    if data["revenue_change_pct"] >= 0:
        prognoza = (f"Ako se rast od {rev_sign}{data['revenue_change_pct']}% nastavi, "
                    f"sledeći mesec se može očekivati oko {projected:,}€.")
    else:
        prognoza = (f"Uz pad od {data['revenue_change_pct']}%, projekcija za sledeći mesec je {projected:,}€ — "
                    f"potrebne su korektivne mere.")

    return {"dobro": dobro, "paznja": paznja, "predlog": predlog, "prognoza": prognoza}


def generate_agent_analysis(
    agent: dict,
    team_conversion: float,
    team_size: int,
    agent_rank: int,
    agent_listings_benchmark: list[dict] | None = None,
    agent_pricing_recs: list[dict] | None = None,
    history: list[dict] | None = None,
) -> dict:
    """Per-agent AI komentar — vraća {dobro, paznja, predlog}. Premium-only feature."""
    client = anthropic.Anthropic(api_key=config.ANTHROPIC_API_KEY)

    inq        = agent["inquiries"]
    cnt        = agent["contracts"]
    conversion = round(cnt / max(inq, 1) * 100, 1)
    delta_vs_team = round(conversion - team_conversion, 1)

    listing_block = ""
    if agent_listings_benchmark:
        over  = sum(1 for r in agent_listings_benchmark if r.get("overpriced_flag"))
        under = sum(1 for r in agent_listings_benchmark if r.get("underpriced_flag"))
        worst = max(agent_listings_benchmark, key=lambda r: r.get("delta_pct", 0), default=None)
        line = (
            f"Oglasi agenta: {len(agent_listings_benchmark)} ukupno, "
            f"{over} iznad tržišta (+15%), {under} ispod tržišta (-10%)"
        )
        if worst and worst.get("delta_pct", 0) >= 15:
            line += (
                f". Najgori: '{worst.get('title')}' "
                f"({worst.get('neighborhood', '?')}, {worst.get('area_m2', '?')}m²) "
                f"+{worst['delta_pct']:.1f}% iznad medijane "
                f"({worst.get('own_eur_m2', '?')} vs {worst.get('market_median_eur_m2', '?')} €/m²)"
            )
        listing_block = "\n" + line

    rec_block = ""
    if agent_pricing_recs:
        top = agent_pricing_recs[0]
        rec_block = (
            f"\nPreporuka korekcije: '{top.get('title')}' — spustiti sa "
            f"{top.get('own_price_eur'):,}€ na {top.get('target_price_eur'):,}€ "
            f"(−{top.get('delta_pct')}%)."
        )

    history_block = ""
    if history and len(history) >= 4:
        recent_4 = history[-4:]
        avg_inq  = round(sum(h["inquiries"] for h in recent_4) / 4, 1)
        avg_cnt  = round(sum(h["contracts"] for h in recent_4) / 4, 1)
        history_block = (
            f"\nIstorija (prosek poslednje 4 nedelje): {avg_inq} upita, {avg_cnt} ugovora."
        )

    name = agent['name']
    prompt = f"""Agent: {name}

Ova nedelja:
- Upiti: {inq}
- Ugovori: {cnt}
- Konverzija: {conversion}% (prosek tima: {team_conversion}%, razlika: {delta_vs_team:+.1f}pp)
- Rang u timu: #{agent_rank} od {team_size}
{history_block}{listing_block}{rec_block}"""

    message = client.messages.create(
        model=config.CLAUDE_AGENT_MODEL,
        max_tokens=300,
        system=[{"type": "text", "text": AGENT_SYSTEM, "cache_control": {"type": "ephemeral"}}],
        messages=[{"role": "user", "content": prompt}],
    )

    _log_cache_usage(message.usage, f"agent {name}")
    return _parse_json(message.content[0].text)


def generate_agent_analysis_fallback(
    agent: dict,
    team_conversion: float,
    team_size: int,
    agent_rank: int,
    agent_listings_benchmark: list[dict] | None = None,
    agent_pricing_recs: list[dict] | None = None,
    history: list[dict] | None = None,
) -> dict:
    """Deterministički fallback za generate_agent_analysis — koristi se kad nema API ključa ili poziv ne uspe."""
    inq        = agent["inquiries"]
    cnt        = agent["contracts"]
    conversion = round(cnt / max(inq, 1) * 100, 1)
    delta_vs_team = round(conversion - team_conversion, 1)

    first = agent["name"].split()[0]

    if agent_rank == 1 and cnt > 0:
        dobro = (f"{first} vodi tim ove nedelje — #{agent_rank} od {team_size} sa konverzijom "
                 f"od {conversion}% ({cnt} ugovor{'a' if cnt != 1 else ''} na {inq} upita).")
    elif conversion >= team_conversion and cnt > 0:
        dobro = (f"{first} je iznad proseka tima — konverzija {conversion}% je "
                 f"{delta_vs_team:+.1f}pp viša od timskog proseka ({team_conversion}%).")
    elif inq > 0:
        dobro = (f"{first} je obradio/la {inq} upita ove nedelje — stabilan obim aktivnosti "
                 f"({'+' if delta_vs_team >= 0 else ''}{delta_vs_team}pp vs prosek tima).")
    else:
        dobro = (f"{first} nema evidentiranih upita ove nedelje — "
                 f"potreban je proaktivan kontakt sa bazom klijenata.")

    overpriced = [r for r in (agent_listings_benchmark or []) if r.get("overpriced_flag")]
    if cnt == 0 and inq > 5:
        paznja = (f"{first} ima {inq} upita ove nedelje bez zaključenog ugovora — "
                  f"konverzija od 0% zahteva hitan razgovor i pregled aktivnih ponuda.")
    elif overpriced:
        worst = max(overpriced, key=lambda r: r.get("delta_pct", 0))
        paznja = (f"Oglas '{worst.get('title')}' koji vodi {first} je +{worst.get('delta_pct'):.1f}% "
                  f"iznad medijane kvarta {worst.get('neighborhood')} "
                  f"({worst.get('own_eur_m2')} vs {worst.get('market_median_eur_m2')} €/m²) "
                  f"— verovatno usporava priliv upita.")
    elif conversion < team_conversion - 2:
        paznja = (f"Konverzija {first}a/e od {conversion}% je {abs(delta_vs_team)}pp ispod "
                  f"proseka tima ({team_conversion}%) — potreban fokus na kvalitet razgovora.")
    else:
        paznja = (f"{first} ima {inq} upita i {cnt} ugovor{'a' if cnt != 1 else ''} ove nedelje — "
                  f"konverzija od {conversion}% je u opsegu tima, bez crvenih zastavica.")

    if agent_pricing_recs:
        top = agent_pricing_recs[0]
        predlog = (f"Preporučiti {first}u korekciju cene oglasa '{top.get('title')}' na "
                   f"{top.get('target_price_eur'):,}€ (−{top.get('delta_pct')}%) — "
                   f"vraća oglas u opseg medijane kvarta.")
    elif cnt == 0 and inq > 0:
        predlog = (f"Razgovarati sa {first}om o tehnikama zatvaranja — "
                   f"{inq} upita bez ugovora ukazuje na problem u poslednjoj fazi prodaje.")
    elif conversion < team_conversion:
        target = round(team_conversion + 1, 1)
        predlog = (f"Postaviti {first}u cilj od {target}% konverzije za narednu nedelju "
                   f"(trenutno {conversion}%) — pratiti svaki upit u roku od 24h.")
    else:
        predlog = (f"Iskoristiti {first}ov/in pristup kao primer za tim — "
                   f"organizovati kratku razmenu iskustava na sledećem timskom sastanku.")

    return {"dobro": dobro, "paznja": paznja, "predlog": predlog}


def generate_analysis_fallback(data: dict, market: list[dict] | None = None) -> dict:
    inquiries_change = data["inquiries"] - data["prev_inquiries"]
    pct = round(inquiries_change / (data["prev_inquiries"] or 1) * 100)

    total_contracts = data["contracts_sale"] + data["contracts_rent"]
    conversion = round(total_contracts / (data["inquiries"] or 1) * 100, 1)

    best_agent = max(data["agents"], key=lambda a: a["contracts"] / max(a["inquiries"], 1)) if data["agents"] else None
    problem_agents = [a for a in data["agents"] if a["contracts"] == 0 and a["inquiries"] > 5]
    problem_name   = problem_agents[0]["name"] if problem_agents else None

    if market:
        avg_m2  = round(sum(s["avg_price_eur_m2"] for s in market) / len(market))
        new_ads = sum(s["new_this_week"] for s in market)
        if pct > 0:
            dobro = (f"Upiti porasli za {pct}% na {data['inquiries']} ove nedelje uz {new_ads} novih oglasa na tržištu "
                     f"— prosečna cena stanova je {avg_m2:,} €/m².")
        else:
            dobro = (f"Tržište beleži {new_ads} novih oglasa uz prosečnu cenu od {avg_m2:,} €/m² "
                     f"— konverzija agencije od {conversion}% pokazuje stabilnu prodajnu efikasnost.")
    elif pct > 0:
        dobro = (f"Upiti porasli za {pct}% ({data['prev_inquiries']} → {data['inquiries']}) i konverzija od {conversion}% "
                 f"donela je {total_contracts} {'ugovora' if total_contracts != 1 else 'ugovor'} ove nedelje.")
    else:
        dobro = (f"Konverzija od {conversion}% uz {total_contracts} zaključenih ugovora — "
                 f"prihod od {data['revenue']:,}€ čini {round(data['revenue']/(data['revenue_goal'] or 1)*100)}% nedeljnog cilja.")

    if problem_name:
        pi = problem_agents[0]["inquiries"]
        paznja  = (f"{problem_name} ima {pi} {'upita' if pi != 1 else 'upit'} ove nedelje bez zaključenog ugovora "
                   f"— konverzija od 0% zahteva hitan razgovor i pregled aktivnih ponuda.")
        predlog = (f"Zakazati 30-minutni 1:1 sa {problem_name} do srede — proći kroz svaki aktivan upit "
                   f"i definisati konkretan sledeći korak za minimum 3 potencijalna kupca.")
    elif best_agent:
        ba_conv = round(best_agent["contracts"] / max(best_agent["inquiries"], 1) * 100, 1)
        agents_below = [a for a in data["agents"] if a["contracts"] / max(a["inquiries"], 1) * 100 < conversion and a != best_agent]
        if agents_below:
            names = ", ".join(a["name"].split()[0] for a in agents_below[:2])
            paznja  = (f"{best_agent['name']} vodi tim sa konverzijom od {ba_conv}% — "
                       f"{names} {'su' if len(agents_below) > 1 else 'je'} ispod proseka tima od {conversion}%.")
            predlog = (f"Organizovati kratku sesiju razmene iskustava: {best_agent['name'].split()[0]} da podeli "
                       f"pristup zatvaranju ugovora sa ostatkom tima — cilj je podići prosek tima na {round(conversion*1.1,1)}%.")
        else:
            rev_pct = round(data["revenue"] / (data["revenue_goal"] or 1) * 100)
            paznja  = (f"Prihod od {data['revenue']:,}€ je na {rev_pct}% nedeljnog cilja — "
                       f"nedostaje {data['revenue_goal'] - data['revenue']:,}€ do punog ostvarenja.")
            predlog = (f"Fokusirati se na zakup u narednim danima — svaki dodatni zakupni ugovor donosi "
                       f"brži prihod od prodajnih i može popuniti razliku do cilja.")
    else:
        rev_pct = round(data["revenue"] / (data["revenue_goal"] or 1) * 100)
        paznja  = f"Prihod je na {rev_pct}% od nedeljnog cilja — potrebno ubrzati zatvaranje ugovora."
        predlog = "Kontaktirati sve aktivne kupce koji nisu odgovorili u poslednje 3 dana i ponuditi razgledanje do petka."

    weekly_rev    = data["revenue"]
    monthly_proj  = weekly_rev * 4
    weekly_goal   = data["revenue_goal"]
    monthly_goal  = weekly_goal * 4
    proj_pct      = round(monthly_proj / (monthly_goal or 1) * 100)
    if proj_pct >= 100:
        prognoza = (f"Na osnovu prihoda od {weekly_rev:,}€ ove nedelje, mesečna projekcija je {monthly_proj:,}€ "
                    f"— mesečni cilj od {monthly_goal:,}€ je dostižan uz nastavak trenutnog tempa.")
    else:
        needed_weekly = monthly_goal // 4 + (monthly_goal - monthly_proj) // 3
        prognoza = (f"Mesečna projekcija iznosi {monthly_proj:,}€ ({proj_pct}% mesečnog cilja od {monthly_goal:,}€) "
                    f"— za dostizanje cilja potrebno je ostvarivati oko {needed_weekly:,}€ nedeljno u preostale 3 nedelje.")

    return {"dobro": dobro, "paznja": paznja, "predlog": predlog, "prognoza": prognoza}
