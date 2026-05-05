from datetime import date, timedelta
import random


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
