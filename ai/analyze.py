import json
import anthropic
import config


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


def _market_block(market: list[dict]) -> str:
    if not market:
        return ""
    lines = [f"  - {s['site']}: {s['total_listings']} oglasa, prosek {s['avg_price_eur_m2']} €/m²"
             for s in market]
    return "\nTržišni kontekst:\n" + "\n".join(lines)


def generate_analysis(data: dict, market: list[dict] | None = None) -> dict:
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

    prompt = f"""Analiziraj nedeljne podatke agencije za nekretnine. Svaka rečenica mora sadržati konkretan broj ili procenat.

Period: {data['week_start']} — {data['week_end']}

KPI-evi nedelje:
- Oglasi: {data['active_listings']} aktivnih, {data['new_listings_this_week']} novih ove nedelje
- Upiti: {data['inquiries']} (prošle nedelje: {data['prev_inquiries']}, promena: {inquiries_pct:+d}%)
- Ugovori: {data['contracts_sale']} prodaja + {data['contracts_rent']} zakupa = {total_contracts} ukupno
- Konverzija upiti→ugovori: {conversion_rate}%
- Prihod: {data['revenue']:,}€ / cilj {data['revenue_goal']:,}€ ({revenue_pct}%)

Upiti po izvoru:
{sources_lines}

Agenti (sortirani po konverziji):
{_agents_summary(data['agents'])}{_market_block(market)}

Odgovori ISKLJUČIVO u JSON formatu, bez ikakvog teksta van JSON-a:
{{
    "dobro":    "jedna rečenica o najjačem pozitivnom trendu ove nedelje — navedi konkretan broj ili %",
    "paznja":   "jedna rečenica o konkretnom problemu koji koči rezultate — navedi ime agenta ili izvor ako je relevantan",
    "predlog":  "jedna konkretna akcija za sledeću nedelju sa merljivim ciljem (broj, %, ili €)",
    "prognoza": "jedna rečenica: na osnovu prihoda od {data['revenue']:,}€ ove nedelje, proceni da li je mesečni cilj od {data['revenue_goal']:,}€ dostižan — navedi projektivanu cifru"
}}"""

    message = client.messages.create(
        model=config.CLAUDE_MODEL,
        max_tokens=700,
        system="Ti si poslovni analitičar za agencije za nekretnine. Uvek odgovaraš SAMO u validnom JSON formatu. Svaka vrednost mora biti konkretna rečenica sa brojevima.",
        messages=[{"role": "user", "content": prompt}],
    )

    return _parse_json(message.content[0].text)


def generate_monthly_analysis(data: dict, market: list[dict] | None = None) -> dict:
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

    prompt = f"""Analiziraj mesečne podatke agencije za nekretnine. Budi strateški i konkretan — svaka rečenica mora sadržati broj ili procenat.

Mesec: {data['month_name']} ({data['weeks_count']} nedelja)

Finansije:
- Prihod: {data['total_revenue']:,}€ / cilj {data['monthly_goal']:,}€ ({data['revenue_pct']}%)
- Promena vs prošli mesec: {rev_sign}{data['revenue_change_pct']}% (prethodni: {data['prev_revenue']:,}€)

Operativni KPI-evi:
- Ukupni upiti: {data['total_inquiries']}
- Ugovori: {data['total_contracts_sale']} prodaja + {data['total_contracts_rent']} zakupa = {data['total_contracts']} ukupno
- Mesečna konverzija: {monthly_conversion}%{best_week_str}{sources_block}

Agenti (sortirani po konverziji):
{_agents_summary(data['agents'])}{_market_block(market)}

Odgovori ISKLJUČIVO u JSON formatu, bez ikakvog teksta van JSON-a:
{{
    "dobro":    "jedna rečenica o najjačem trendu u mesecu — navedi konkretan broj ili %",
    "paznja":   "jedna rečenica o konkretnom problemu koji je koštao prihode — budi specifičan (agent, izvor, ili KPI)",
    "predlog":  "jedna konkretna strateška akcija za sledeći mesec sa merljivim ciljem (broj, %, ili €)",
    "prognoza": "jedna rečenica: ako se trend od {rev_sign}{data['revenue_change_pct']}% nastavi, sledeći mesec se može očekivati oko {projected:,}€ — komentiraj dostižnost godišnjeg cilja"
}}"""

    message = client.messages.create(
        model=config.CLAUDE_MODEL,
        max_tokens=700,
        system="Ti si poslovni analitičar za agencije za nekretnine. Uvek odgovaraš SAMO u validnom JSON formatu. Svaka vrednost mora biti konkretna rečenica sa brojevima.",
        messages=[{"role": "user", "content": prompt}],
    )

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
