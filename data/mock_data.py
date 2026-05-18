from datetime import date, timedelta


def get_mock_monthly_data(agency_id: str = "prima") -> dict:
    today = date.today()
    month_end   = today.replace(day=1) - timedelta(days=1)
    month_start = month_end.replace(day=1)
    MONTHS_SR = ["", "januar", "februar", "mart", "april", "maj", "jun",
                 "jul", "avgust", "septembar", "oktobar", "novembar", "decembar"]
    return {
        "agency_name":          "Nekretnine Centar d.o.o.",
        "agency_email":         "office@nekretninecenrar.rs",
        "plan_id":              "pro",
        "month_name":           f"{MONTHS_SR[month_start.month]} {month_start.year}",
        "month_start":          month_start.strftime("%d.%m.%Y"),
        "month_end":            month_end.strftime("%d.%m.%Y"),
        "generated_at":         today.strftime("%d.%m.%Y"),
        "total_inquiries":      482,
        "total_contracts_sale": 14,
        "total_contracts_rent": 34,
        "total_contracts":      48,
        "total_revenue":        32800,
        "monthly_goal":         36000,
        "revenue_pct":          91,
        "prev_revenue":         27600,
        "revenue_change_pct":   19,
        "weeks_count":          4,
        "weekly_breakdown": [
            {"week_start": (month_start).strftime("%Y-%m-%d"),                       "inquiries": 108, "contracts_sale": 3, "contracts_rent": 7,  "revenue": 7200},
            {"week_start": (month_start + timedelta(days=7)).strftime("%Y-%m-%d"),   "inquiries": 119, "contracts_sale": 3, "contracts_rent": 9,  "revenue": 8100},
            {"week_start": (month_start + timedelta(days=14)).strftime("%Y-%m-%d"),  "inquiries": 127, "contracts_sale": 4, "contracts_rent": 9,  "revenue": 8900},
            {"week_start": (month_start + timedelta(days=21)).strftime("%Y-%m-%d"),  "inquiries": 128, "contracts_sale": 4, "contracts_rent": 9,  "revenue": 8600},
        ],
        "best_week": {"week_start": (month_start + timedelta(days=14)).strftime("%Y-%m-%d"), "contracts_sale": 4, "contracts_rent": 9, "revenue": 8900},
        "inquiries_by_source": {
            "Halo oglasi":      214,
            "4zida":            138,
            "Nekretnine.rs":     82,
            "Sajt agencije":     31,
            "Instagram/ostalo":  17,
        },
        "agents": [
            {"name": "Marko Petrović",    "email": "marko@nekretninecentar.rs",   "inquiries": 148, "contracts": 17},
            {"name": "Ana Nikolić",       "email": "ana@nekretninecentar.rs",     "inquiries": 127, "contracts": 14},
            {"name": "Stefan Ilić",       "email": "stefan@nekretninecentar.rs",  "inquiries": 103, "contracts": 9},
            {"name": "Jovan Đorđević",    "email": "jovan@nekretninecentar.rs",   "inquiries": 79,  "contracts": 6},
            {"name": "Milica Stojanović", "email": "milica@nekretninecentar.rs",  "inquiries": 25,  "contracts": 2},
        ],
    }


def get_mock_report_data(agency_id: str = "prima", plan_id: str = "pro") -> dict:
    today = date.today()
    week_start = today - timedelta(days=today.weekday() + 7)
    week_end = week_start + timedelta(days=6)

    return {
        "agency_name":  "Nekretnine Centar d.o.o.",
        "agency_email": "office@nekretninecentar.rs",
        "plan_id":      plan_id,
        "logo_url":     None,
        "week_start": week_start.strftime("%d.%m.%Y"),
        "week_end": week_end.strftime("%d.%m.%Y"),
        "generated_at": today.strftime("%d.%m.%Y"),

        # KPI
        "active_listings":        94,
        "new_listings_this_week": 8,
        "inquiries":              127,
        "prev_inquiries":         108,
        "contracts_sale":         4,
        "contracts_rent":         9,
        "revenue":                8400,
        "revenue_goal":           9000,

        # Upiti po izvoru
        "inquiries_by_source": {
            "Halo oglasi":      57,
            "4zida":            36,
            "Nekretnine.rs":    21,
            "Sajt agencije":     9,
            "Instagram/ostalo":  4,
        },

        # Agenti
        "agents": [
            {"id": "agent-marko",   "name": "Marko Petrović",    "email": "marko@nekretninecentar.rs",   "inquiries": 38, "contracts": 5},
            {"id": "agent-ana",     "name": "Ana Nikolić",       "email": "ana@nekretninecentar.rs",     "inquiries": 34, "contracts": 4},
            {"id": "agent-stefan",  "name": "Stefan Ilić",       "email": "stefan@nekretninecentar.rs",  "inquiries": 28, "contracts": 3},
            {"id": "agent-jovan",   "name": "Jovan Đorđević",    "email": "jovan@nekretninecentar.rs",   "inquiries": 20, "contracts": 1},
            {"id": "agent-milica",  "name": "Milica Stojanović", "email": "milica@nekretninecentar.rs",  "inquiries": 7,  "contracts": 0},
        ],
    }


def get_mock_agent_history(agent_id: str, weeks: int = 26) -> list[dict]:
    """Generiše mock weekly history za jednog agenta — koristi se za trend grafik."""
    today = date.today()
    profiles = {
        "agent-marko":  {"base_inq": 32, "base_cnt": 4,   "trend": 0.18,  "noise": 4},
        "agent-ana":    {"base_inq": 30, "base_cnt": 3.5, "trend": 0.10,  "noise": 3},
        "agent-stefan": {"base_inq": 28, "base_cnt": 2.5, "trend": 0.05,  "noise": 3},
        "agent-jovan":  {"base_inq": 22, "base_cnt": 1.0, "trend": -0.05, "noise": 2},
        "agent-milica": {"base_inq": 8,  "base_cnt": 0.4, "trend": -0.10, "noise": 1},
    }
    p = profiles.get(agent_id, {"base_inq": 20, "base_cnt": 2, "trend": 0.0, "noise": 2})
    series = []
    for w in range(weeks, -1, -1):
        d = today - timedelta(days=(w + 1) * 7)
        # blagi trend + deterministički "šum" preko hash-a
        wiggle_inq = ((w * 7 + hash(agent_id) % 13) % 9) - 4
        wiggle_cnt = ((w * 3 + hash(agent_id) % 7) % 5) - 2
        inq = max(0, round(p["base_inq"] + (weeks - w) * p["trend"] + wiggle_inq))
        cnt = max(0, round(p["base_cnt"] + (weeks - w) * p["trend"] * 0.15 + wiggle_cnt * 0.5))
        conv = round(cnt / max(inq, 1) * 100, 1)
        series.append({
            "week_start":   d.strftime("%Y-%m-%d"),
            "inquiries":    inq,
            "contracts":    cnt,
            "conversion":   conv,
        })
    return series


def get_mock_agent_listings_benchmark(agent_id: str) -> list[dict]:
    """Per-agent subset pricing_benchmark output-a — koje oglase agent vodi i kako stoje vs tržište."""
    all_listings = {
        "agent-marko": [
            {
                "listing_id": "mock-m-1", "ref_number": "PRI-101",
                "title": "Dvosoban stan, Vračar, kod parka",
                "transaction": "sale", "neighborhood": "Vračar",
                "area_m2": 62, "rooms": 2,
                "own_price_eur": 158000, "own_eur_m2": 2548,
                "market_median_eur_m2": 2180, "sample_size": 47,
                "scope": "neighborhood", "delta_pct": 16.9,
                "overpriced_flag": True, "underpriced_flag": False,
            },
            {
                "listing_id": "mock-m-2", "ref_number": "PRI-102",
                "title": "Trosoban, Novi Beograd, blok 45",
                "transaction": "sale", "neighborhood": "Novi Beograd",
                "area_m2": 78, "rooms": 3,
                "own_price_eur": 198000, "own_eur_m2": 2538,
                "market_median_eur_m2": 2090, "sample_size": 62,
                "scope": "neighborhood", "delta_pct": 21.4,
                "overpriced_flag": True, "underpriced_flag": False,
            },
            {
                "listing_id": "mock-m-3", "ref_number": "PRI-103",
                "title": "Garsonjera, Voždovac",
                "transaction": "sale", "neighborhood": "Voždovac",
                "area_m2": 32, "rooms": 1,
                "own_price_eur": 68000, "own_eur_m2": 2125,
                "market_median_eur_m2": 2180, "sample_size": 38,
                "scope": "neighborhood", "delta_pct": -2.5,
                "overpriced_flag": False, "underpriced_flag": False,
            },
        ],
        "agent-ana": [
            {
                "listing_id": "mock-a-1", "ref_number": "PRI-201",
                "title": "Dvosoban, Zvezdara",
                "transaction": "sale", "neighborhood": "Zvezdara",
                "area_m2": 55, "rooms": 2,
                "own_price_eur": 112000, "own_eur_m2": 2036,
                "market_median_eur_m2": 2050, "sample_size": 41,
                "scope": "neighborhood", "delta_pct": -0.7,
                "overpriced_flag": False, "underpriced_flag": False,
            },
            {
                "listing_id": "mock-a-2", "ref_number": "PRI-202",
                "title": "Četvorosoban, Dedinje",
                "transaction": "sale", "neighborhood": "Dedinje",
                "area_m2": 120, "rooms": 4,
                "own_price_eur": 340000, "own_eur_m2": 2833,
                "market_median_eur_m2": 3100, "sample_size": 18,
                "scope": "neighborhood", "delta_pct": -8.6,
                "overpriced_flag": False, "underpriced_flag": False,
            },
        ],
        "agent-stefan": [
            {
                "listing_id": "mock-s-1", "ref_number": "PRI-301",
                "title": "Garsonjera, Zemun",
                "transaction": "sale", "neighborhood": "Zemun",
                "area_m2": 28, "rooms": 0.5,
                "own_price_eur": 47000, "own_eur_m2": 1679,
                "market_median_eur_m2": 1890, "sample_size": 23,
                "scope": "neighborhood", "delta_pct": -11.2,
                "overpriced_flag": False, "underpriced_flag": True,
            },
        ],
        "agent-jovan": [
            {
                "listing_id": "mock-j-1", "ref_number": "PRI-401",
                "title": "Dvosoban, Mirijevo",
                "transaction": "sale", "neighborhood": "Mirijevo",
                "area_m2": 48, "rooms": 2,
                "own_price_eur": 105000, "own_eur_m2": 2188,
                "market_median_eur_m2": 1820, "sample_size": 41,
                "scope": "neighborhood", "delta_pct": 20.2,
                "overpriced_flag": True, "underpriced_flag": False,
            },
        ],
        "agent-milica": [],
    }
    return all_listings.get(agent_id, [])


def get_mock_agent_pricing_recommendations(agent_id: str) -> list[dict]:
    """Per-agent overpriced listings sa target cenama (Premium-only)."""
    recs = {
        "agent-marko": [
            {
                "listing_id":       "mock-m-2",
                "ref_number":       "PRI-102",
                "title":            "Trosoban, Novi Beograd, blok 45",
                "transaction":      "sale",
                "neighborhood":     "Novi Beograd",
                "area_m2":          78,
                "own_price_eur":    198000,
                "own_eur_m2":       2538,
                "target_price_eur": 163000,
                "target_eur_m2":    2090,
                "delta_amount_eur": 35000,
                "delta_pct":        21.4,
                "sample_size":      62,
                "confidence":       "high",
                "scope":            "neighborhood",
                "rationale": (
                    "Cena je +21.4% iznad medijane (2538 vs 2090 €/m², uzorak 62). "
                    "Spuštanje na 163,000€ vraća oglas u opseg P25–P75 i ubrzava prodaju."
                ),
            },
            {
                "listing_id":       "mock-m-1",
                "ref_number":       "PRI-101",
                "title":            "Dvosoban stan, Vračar, kod parka",
                "transaction":      "sale",
                "neighborhood":     "Vračar",
                "area_m2":          62,
                "own_price_eur":    158000,
                "own_eur_m2":       2548,
                "target_price_eur": 135000,
                "target_eur_m2":    2180,
                "delta_amount_eur": 23000,
                "delta_pct":        16.9,
                "sample_size":      47,
                "confidence":       "medium",
                "scope":            "neighborhood",
                "rationale": (
                    "Cena je +16.9% iznad medijane Vračara. "
                    "Korekcija na 135,000€ poravnava sa medijanom kvarta i prosečnim DOM-om od 38 dana."
                ),
            },
        ],
        "agent-jovan": [
            {
                "listing_id":       "mock-j-1",
                "ref_number":       "PRI-401",
                "title":            "Dvosoban, Mirijevo",
                "transaction":      "sale",
                "neighborhood":     "Mirijevo",
                "area_m2":          48,
                "own_price_eur":    105000,
                "own_eur_m2":       2188,
                "target_price_eur": 87000,
                "target_eur_m2":    1820,
                "delta_amount_eur": 18000,
                "delta_pct":        20.2,
                "sample_size":      41,
                "confidence":       "medium",
                "scope":            "neighborhood",
                "rationale": (
                    "Cena je +20.2% iznad medijane Mirijeva. "
                    "Spuštanje na 87,000€ je u rangu sa svežim ugovorima u kvartu."
                ),
            },
        ],
    }
    return recs.get(agent_id, [])


def get_mock_agent_hot_zones(agent_id: str) -> list[dict]:
    """Hot zones filtrirane na kvartove gde agent ima oglase."""
    agent_neighborhoods = {
        "agent-marko":  {"Vračar", "Novi Beograd", "Voždovac"},
        "agent-ana":    {"Zvezdara", "Dedinje"},
        "agent-stefan": {"Zemun"},
        "agent-jovan":  {"Mirijevo"},
        "agent-milica": set(),
    }
    target = agent_neighborhoods.get(agent_id, set())
    if not target:
        return []
    return [z for z in get_mock_hot_zones() if z["neighborhood"] in target]


def get_mock_benchmark() -> dict:
    return {
        "avg_conversion": 9.1,
        "avg_revenue":    5800,
        "avg_inquiries":  89,
        "agency_count":   14,
    }


def get_mock_pricing_recommendations() -> list[dict]:
    return [
        {
            "listing_id":       "mock-2",
            "ref_number":       "PRI-005",
            "title":             "Trosoban stan, Novi Beograd, blok 45",
            "transaction":      "sale",
            "neighborhood":     "Novi Beograd",
            "area_m2":          78,
            "own_price_eur":    198000,
            "own_eur_m2":       2538,
            "target_price_eur": 163000,
            "target_eur_m2":    2090,
            "delta_amount_eur": 35000,
            "delta_pct":        21.4,
            "sample_size":      62,
            "confidence":       "high",
            "scope":            "neighborhood",
            "rationale":        (
                "Trenutna cena je +21.4% iznad medijane tržišta (2538 vs 2090 €/m²; uzorak 62 sličnih oglasa u kvartu). "
                "Sniženje na 163,000€ vraća oglas u opseg P25–P75 (1900–2310 €/m²)."
            ),
        },
        {
            "listing_id":       "mock-1",
            "ref_number":       "PRI-001",
            "title":             "Svetao dvosoban stan na Vračaru",
            "transaction":      "sale",
            "neighborhood":     "Vračar",
            "area_m2":          58,
            "own_price_eur":    145000,
            "own_eur_m2":       2500,
            "target_price_eur": 126000,
            "target_eur_m2":    2180,
            "delta_amount_eur": 19000,
            "delta_pct":        14.7,
            "sample_size":      47,
            "confidence":       "medium",
            "scope":            "neighborhood",
            "rationale":        (
                "Trenutna cena je +14.7% iznad medijane tržišta (2500 vs 2180 €/m²; uzorak 47 sličnih oglasa u kvartu). "
                "Sniženje na 126,000€ vraća oglas u opseg P25–P75 (1980–2420 €/m²)."
            ),
        },
    ]


def get_mock_listing_opportunities() -> list[dict]:
    return [
        {
            "site":          "Halo oglasi",
            "external_id":   "5425612345678",
            "url":           "https://www.halooglasi.com/oglas/example/5425612345678",
            "title":          "Stan, Banjica, 65m²",
            "neighborhood":  "Banjica",
            "area_m2":       65,
            "rooms":         2.5,
            "price_eur":     189000,
            "price_eur_m2":  2908,
            "publisher":     "Privatni",
            "publisher_type": "private",
            "days_listed":   132,
            "first_seen":    "2026-01-05",
            "last_seen":     "2026-05-16",
        },
        {
            "site":          "4zida",
            "external_id":   "id998877",
            "url":           "https://4zida.rs/stan/example-id998877",
            "title":          "Stan, Banjica, 78m²",
            "neighborhood":  "Banjica",
            "area_m2":       78,
            "rooms":         3,
            "price_eur":     215000,
            "price_eur_m2":  2756,
            "publisher":     "Agencija X",
            "publisher_type": "agency",
            "days_listed":   118,
            "first_seen":    "2026-01-19",
            "last_seen":     "2026-05-16",
        },
        {
            "site":          "Nekretnine.rs",
            "external_id":   "778899",
            "url":           "https://www.nekretnine.rs/detaljno/example/778899/",
            "title":          "Stan, Banjica, 52m²",
            "neighborhood":  "Banjica",
            "area_m2":       52,
            "rooms":         2,
            "price_eur":     142000,
            "price_eur_m2":  2731,
            "publisher":     "Privatni",
            "publisher_type": "private",
            "days_listed":   103,
            "first_seen":    "2026-02-03",
            "last_seen":     "2026-05-15",
        },
    ]


def get_mock_competitor_inventory() -> dict:
    return {
        "top": [
            {"publisher": "City Living", "listing_count": 187, "market_share_pct": 8.4},
            {"publisher": "Beograd Estate", "listing_count": 142, "market_share_pct": 6.4},
            {"publisher": "Premium Nekretnine", "listing_count": 98, "market_share_pct": 4.4},
            {"publisher": "Galerija Stanova", "listing_count": 76, "market_share_pct": 3.4},
            {"publisher": "CityExpert", "listing_count": 64, "market_share_pct": 2.9},
        ],
        "distribution":   {"1-5": 87, "6-20": 42, "21-50": 18, "50+": 7},
        "total_agencies": 154,
        "total_listings": 2218,
    }


def get_mock_alerts() -> list[dict]:
    return [
        {
            "type":      "pricing",
            "severity":  "high",
            "title":      "Oglas „Trosoban stan, Novi Beograd, blok 45“ je +21.4% iznad tržišta",
            "body":      "Spustite cenu sa 198,000€ na 163,000€ (medijana kvarta, uzorak 62). Slični oglasi prodaju u 38 dana.",
            "ref":       "PRI-005",
            "amount_eur": 35000,
        },
        {
            "type":     "hot_zone",
            "severity": "info",
            "title":    "Voždovac: rast cena +4.7% (15d)",
            "body":     "Medijana 2180 €/m², 18 novih oglasa ove nedelje. Razmislite o usmeravanju agenata na preuzimanje ekskluziva u Voždovcu.",
            "neighborhood": "Voždovac",
        },
        {
            "type":     "opportunity",
            "severity": "info",
            "title":    "3 stuck oglasa u Banjici (> 90 dana)",
            "body":     "Vlasnici su verovatno otvoreni za korekciju cene ili prelazak na ekskluzivni ugovor. Pregled liste u tabu „Listing opportunities“ izveštaja.",
            "neighborhood": "Banjica",
            "count": 3,
        },
    ]


def get_mock_market_trend() -> dict:
    """Mock vremenska serija — ~6 meseci podataka, blagi uzlazni trend."""
    today = date.today()
    series = []
    # generiši 26 nedeljnih tačaka — od najstarije ka najnovijoj
    base = 2050
    for week in range(26, -1, -1):
        d = today - timedelta(days=week * 7)
        # blagi rast + mali šum
        val = base + (26 - week) * 8 + (-15 if week % 5 == 0 else 5 if week % 3 == 0 else 0)
        series.append({"date": d.isoformat(), "median_eur_m2": val, "sample": 120 + (week % 7) * 4})
    return {
        "series":         series,
        "latest_eur_m2":  series[-1]["median_eur_m2"],
        "mom_pct":        2.4,
        "yoy_pct":        9.8,
        "neighborhood":   None,
        "lookback_days":  180,
    }


def get_mock_dom_stats() -> dict:
    return {
        "median_dom_days":   38,
        "dom_p25":           22,
        "dom_p75":           67,
        "sold_sample_size":  142,
        "still_active":      318,
        "neighborhood":      None,
    }


def get_mock_hot_zones() -> list[dict]:
    return [
        {"neighborhood": "Voždovac",    "median_eur_m2": 2180, "price_change_pct": 4.7, "new_this_week": 18, "sample_size": 142, "score": 8.3},
        {"neighborhood": "Zvezdara",    "median_eur_m2": 2050, "price_change_pct": 3.9, "new_this_week": 14, "sample_size": 119, "score": 6.7},
        {"neighborhood": "Banjica",     "median_eur_m2": 2380, "price_change_pct": 5.2, "new_this_week":  7, "sample_size":  64, "score": 6.6},
        {"neighborhood": "Novi Beograd","median_eur_m2": 2410, "price_change_pct": 1.8, "new_this_week": 22, "sample_size": 268, "score": 6.2},
        {"neighborhood": "Mirijevo",    "median_eur_m2": 1820, "price_change_pct": 6.4, "new_this_week":  3, "sample_size":  41, "score": 7.0},
    ]


def get_mock_pricing_benchmark() -> list[dict]:
    """Mock pricing benchmark — repliciram mix od overpriced/fair/underpriced za UI test."""
    return [
        {
            "listing_id":     "mock-1",
            "ref_number":     "PRI-001",
            "title":          "Svetao dvosoban stan na Vračaru",
            "transaction":    "sale",
            "property_type":  "apartment",
            "neighborhood":   "Vračar",
            "area_m2":        58,
            "rooms":          2,
            "own_price_eur":  145000,
            "own_eur_m2":     2500,
            "market_median_eur_m2": 2180,
            "market_p25":     1980,
            "market_p75":     2420,
            "sample_size":    47,
            "scope":          "neighborhood",
            "delta_pct":      14.7,
            "overpriced_flag": False,
            "underpriced_flag": False,
        },
        {
            "listing_id":     "mock-2",
            "ref_number":     "PRI-005",
            "title":          "Trosoban stan, Novi Beograd, blok 45",
            "transaction":    "sale",
            "property_type":  "apartment",
            "neighborhood":   "Novi Beograd",
            "area_m2":        78,
            "rooms":          3,
            "own_price_eur":  198000,
            "own_eur_m2":     2538,
            "market_median_eur_m2": 2090,
            "market_p25":     1900,
            "market_p75":     2310,
            "sample_size":    62,
            "scope":          "neighborhood",
            "delta_pct":      21.4,
            "overpriced_flag": True,
            "underpriced_flag": False,
        },
        {
            "listing_id":     "mock-3",
            "ref_number":     "PRI-008",
            "title":          "Garsonjera Zemun, blizu pijace",
            "transaction":    "sale",
            "property_type":  "apartment",
            "neighborhood":   "Zemun",
            "area_m2":        28,
            "rooms":          0.5,
            "own_price_eur":  47000,
            "own_eur_m2":     1679,
            "market_median_eur_m2": 1890,
            "market_p25":     1720,
            "market_p75":     2060,
            "sample_size":    23,
            "scope":          "neighborhood",
            "delta_pct":      -11.2,
            "overpriced_flag": False,
            "underpriced_flag": True,
        },
    ]
