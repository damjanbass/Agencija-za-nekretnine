from datetime import date, timedelta


def get_mock_monthly_data(agency_id: str = "prima") -> dict:
    today = date.today()
    month_end   = today.replace(day=1) - timedelta(days=1)
    month_start = month_end.replace(day=1)
    MONTHS_SR = ["", "januar", "februar", "mart", "april", "maj", "jun",
                 "jul", "avgust", "septembar", "oktobar", "novembar", "decembar"]
    return {
        "agency_name":          "Agencija Prima",
        "agency_email":         "vlasnik@primakretnine.rs",
        "plan_id":              "basic",
        "month_name":           f"{MONTHS_SR[month_start.month]} {month_start.year}",
        "month_start":          month_start.strftime("%d.%m.%Y"),
        "month_end":            month_end.strftime("%d.%m.%Y"),
        "generated_at":         today.strftime("%d.%m.%Y"),
        "total_inquiries":      312,
        "total_contracts_sale": 11,
        "total_contracts_rent": 24,
        "total_contracts":      35,
        "total_revenue":        17400,
        "monthly_goal":         20000,
        "revenue_pct":          87,
        "prev_revenue":         15200,
        "revenue_change_pct":   14,
        "weeks_count":          4,
        "weekly_breakdown": [
            {"week_start": "2026-04-07", "inquiries": 71, "contracts_sale": 2, "contracts_rent": 5, "revenue": 3600},
            {"week_start": "2026-04-14", "inquiries": 83, "contracts_sale": 3, "contracts_rent": 7, "revenue": 4200},
            {"week_start": "2026-04-21", "inquiries": 79, "contracts_sale": 3, "contracts_rent": 6, "revenue": 4800},
            {"week_start": "2026-04-28", "inquiries": 79, "contracts_sale": 3, "contracts_rent": 6, "revenue": 4800},
        ],
        "best_week":            {"week_start": "2026-04-21", "contracts_sale": 3, "contracts_rent": 6, "revenue": 4800},
        "inquiries_by_source": {
            "Halo oglasi": 142,
            "4zida": 89,
            "Sajt agencije": 52,
            "Instagram/ostalo": 29,
        },
        "agents": [
            {"name": "Marko Petrović",    "inquiries": 112, "contracts": 14},
            {"name": "Ana Nikolić",       "inquiries": 98,  "contracts": 11},
            {"name": "Jovan Đorđević",    "inquiries": 67,  "contracts": 7},
            {"name": "Milica Stojanović", "inquiries": 35,  "contracts": 3},
        ],
    }


def get_mock_report_data(agency_id: str = "prima") -> dict:
    today = date.today()
    week_start = today - timedelta(days=today.weekday() + 7)
    week_end = week_start + timedelta(days=6)

    return {
        "agency_name":  "Agencija Prima",
        "agency_email": "vlasnik@primakretnine.rs",
        "plan_id":      "basic",
        "week_start": week_start.strftime("%d.%m.%Y"),
        "week_end": week_end.strftime("%d.%m.%Y"),
        "generated_at": today.strftime("%d.%m.%Y"),

        # KPI
        "active_listings": 47,
        "new_listings_this_week": 5,
        "inquiries": 83,
        "prev_inquiries": 71,
        "contracts_sale": 3,
        "contracts_rent": 7,
        "revenue": 4200,
        "revenue_goal": 5000,

        # Upiti po izvoru
        "inquiries_by_source": {
            "Halo oglasi": 38,
            "4zida": 21,
            "Sajt agencije": 14,
            "Instagram/ostalo": 10,
        },

        # Agenti
        "agents": [
            {"name": "Marko Petrović", "inquiries": 31, "contracts": 4},
            {"name": "Ana Nikolić",    "inquiries": 27, "contracts": 3},
            {"name": "Jovan Đorđević", "inquiries": 18, "contracts": 2},
            {"name": "Milica Stojanović", "inquiries": 7, "contracts": 0},
        ],
    }
