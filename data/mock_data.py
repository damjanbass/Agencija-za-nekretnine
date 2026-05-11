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


def get_mock_report_data(agency_id: str = "prima") -> dict:
    today = date.today()
    week_start = today - timedelta(days=today.weekday() + 7)
    week_end = week_start + timedelta(days=6)

    return {
        "agency_name":  "Nekretnine Centar d.o.o.",
        "agency_email": "office@nekretninecentar.rs",
        "plan_id":      "pro",
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
            {"name": "Marko Petrović",    "email": "marko@nekretninecentar.rs",   "inquiries": 38, "contracts": 5},
            {"name": "Ana Nikolić",       "email": "ana@nekretninecentar.rs",     "inquiries": 34, "contracts": 4},
            {"name": "Stefan Ilić",       "email": "stefan@nekretninecentar.rs",  "inquiries": 28, "contracts": 3},
            {"name": "Jovan Đorđević",    "email": "jovan@nekretninecentar.rs",   "inquiries": 20, "contracts": 1},
            {"name": "Milica Stojanović", "email": "milica@nekretninecentar.rs",  "inquiries": 7,  "contracts": 0},
        ],
    }


def get_mock_benchmark() -> dict:
    return {
        "avg_conversion": 9.1,
        "avg_revenue":    5800,
        "avg_inquiries":  89,
        "agency_count":   14,
    }
