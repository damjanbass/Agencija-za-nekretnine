import json
import anthropic
import config


def generate_analysis(data: dict, market: list[dict] | None = None) -> dict:
    client = anthropic.Anthropic(api_key=config.ANTHROPIC_API_KEY)

    inquiries_change = data["inquiries"] - data["prev_inquiries"]
    inquiries_pct    = round((inquiries_change / (data["prev_inquiries"] or 1)) * 100)
    revenue_pct      = round((data["revenue"] / (data["revenue_goal"] or 1)) * 100)

    agents_summary = "\n".join(
        f"  - {a['name']}: {a['inquiries']} upita, {a['contracts']} ugovora"
        for a in data["agents"]
    )

    market_block = ""
    if market:
        lines = [f"  - {s['site']}: {s['total_listings']} oglasa, prosek {s['avg_price_eur_m2']} €/m²"
                 for s in market]
        market_block = "\nTržišni kontekst (javni sajtovi):\n" + "\n".join(lines)

    prompt = f"""Analiziraj nedeljne podatke agencije za nekretnine i daj konkretne uvide.

Podaci za period {data['week_start']} - {data['week_end']}:
- Aktivni oglasi: {data['active_listings']} (+{data['new_listings_this_week']} novih)
- Upiti ove nedelje: {data['inquiries']} (prošle: {data['prev_inquiries']}, promena: {inquiries_pct:+d}%)
- Ugovori: {data['contracts_sale']} prodaja + {data['contracts_rent']} zakupa
- Prihod: {data['revenue']}€ od cilja {data['revenue_goal']}€ ({revenue_pct}%){market_block}
- Agenti:
{agents_summary}

Odgovori ISKLJUČIVO u JSON formatu, bez ikakvog dodatnog teksta:
{{
    "dobro": "jedna rečenica o najjačem pozitivnom trendu ove nedelje",
    "paznja": "jedna rečenica o konkretnom problemu koji treba rešiti",
    "predlog": "jedna konkretna akcija za sledeću nedelju sa merljivim ciljem"
}}"""

    message = client.messages.create(
        model=config.CLAUDE_MODEL,
        max_tokens=400,
        system="Ti si analitičar za agencije za nekretnine. Uvek odgovaraš samo u validnom JSON formatu.",
        messages=[{"role": "user", "content": prompt}],
    )

    raw = message.content[0].text.strip()
    if raw.startswith("```"):
        raw = raw.split("```")[1]
        if raw.startswith("json"):
            raw = raw[4:]
    return json.loads(raw)


def generate_analysis_fallback(data: dict, market: list[dict] | None = None) -> dict:
    inquiries_change = data["inquiries"] - data["prev_inquiries"]
    pct = round((inquiries_change / (data["prev_inquiries"] or 1)) * 100)

    problem_agents = [a for a in data["agents"] if a["contracts"] == 0 and a["inquiries"] > 5]
    problem_name = problem_agents[0]["name"] if problem_agents else None

    dobro = f"Broj upita porastao za {pct}% u odnosu na prošlu nedelju — trend rasta se nastavlja."

    if market:
        avg_m2 = round(sum(s["avg_price_eur_m2"] for s in market) / len(market))
        dobro = f"Tržište beleži {sum(s['new_this_week'] for s in market)} novih oglasa ove nedelje — aktivnost raste, prosek {avg_m2} €/m²."

    if problem_name:
        paznja  = f"{problem_name} ima visok broj upita ali 0 ugovora — potrebna je podrška u zatvaranju."
        predlog = f"Organizovati kratki 1:1 sa {problem_name} i proći kroz poslednje 3 ponude koje nisu zatvorene."
    else:
        paznja  = f"Prihod je na {round(data['revenue']/data['revenue_goal']*100)}% od nedeljnog cilja — potrebno ubrzati zatvaranje."
        predlog = "Kontaktirati sve aktivne kupce sa ponudom za razgledanje do petka."

    return {"dobro": dobro, "paznja": paznja, "predlog": predlog}
