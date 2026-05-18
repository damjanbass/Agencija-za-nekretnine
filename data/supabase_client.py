from datetime import date, timedelta
from supabase import create_client, Client
import config


def get_client() -> Client:
    return create_client(config.SUPABASE_URL, config.SUPABASE_KEY)


def _effective_plan(agency: dict) -> str:
    """
    Vraća plan_id koji se zaista primenjuje na agenciju.
    Trial i active → izabrani plan; sve ostalo → 'free'.
    Mora da prati logiku public.effective_plan_id() u Supabase-u.
    """
    status = (agency or {}).get("subscription_status") or "trial"
    if status in ("trial", "active"):
        return (agency or {}).get("plan_id") or "free"
    return "free"


def get_report_data(agency_id: str) -> dict:
    """
    Vuče sve podatke za nedeljni izveštaj iz Supabase.
    agency_id je UUID iz tabele agencies.
    Prikazuje prošlu nedelju (ponedeljak–nedelja).
    """
    sb = get_client()

    today = date.today()
    # Prošla nedelja: ponedeljak
    week_start = (today - timedelta(days=today.weekday() + 7))
    week_end   = week_start + timedelta(days=6)
    prev_week  = week_start - timedelta(days=7)

    ws  = week_start.isoformat()
    pws = prev_week.isoformat()

    # --- Agencija ---
    agency = (
        sb.table("agencies")
        .select("name, email, revenue_goal, plan_id, logo_url, subscription_status, trial_ends_at, current_period_end, tracks_sale, tracks_rent")
        .eq("id", agency_id)
        .single()
        .execute()
        .data
    )

    # --- Ovonedeljni KPI ---
    kpi = (
        sb.table("weekly_kpis")
        .select("*")
        .eq("agency_id", agency_id)
        .eq("week_start", ws)
        .single()
        .execute()
        .data
    )

    # --- Prošlonedeljni KPI (za % upiti) ---
    prev_kpi = (
        sb.table("weekly_kpis")
        .select("inquiries")
        .eq("agency_id", agency_id)
        .eq("week_start", pws)
        .maybe_single()
        .execute()
        .data
    )

    # --- Upiti po izvoru ---
    sources_raw = (
        sb.table("inquiry_sources")
        .select("source, count")
        .eq("agency_id", agency_id)
        .eq("week_start", ws)
        .order("count", desc=True)
        .execute()
        .data
    )
    inquiries_by_source = {row["source"]: row["count"] for row in sources_raw}

    # --- Agenti + performanse ---
    perf_raw = (
        sb.table("agent_performance")
        .select("agent_id, inquiries, contracts, agents(name, email)")
        .eq("agency_id", agency_id)
        .eq("week_start", ws)
        .order("inquiries", desc=True)
        .execute()
        .data
    )
    agents = [
        {
            "id":        row["agent_id"],
            "name":      row["agents"]["name"],
            "email":     row["agents"].get("email") or "",
            "inquiries": row["inquiries"],
            "contracts": row["contracts"],
        }
        for row in perf_raw
    ]

    return {
        "agency_name":            agency["name"],
        "agency_email":           agency["email"],
        "plan_id":                _effective_plan(agency),
        "subscription_status":    agency.get("subscription_status"),
        "logo_url":               agency.get("logo_url"),
        "week_start":             week_start.strftime("%d.%m.%Y"),
        "week_end":               week_end.strftime("%d.%m.%Y"),
        "generated_at":           today.strftime("%d.%m.%Y"),
        "active_listings":        kpi["active_listings"],
        "new_listings_this_week": kpi["new_listings"],
        "inquiries":              kpi["inquiries"],
        "prev_inquiries":         prev_kpi["inquiries"] if prev_kpi else kpi["inquiries"],
        "contracts_sale":         kpi["contracts_sale"],
        "contracts_rent":         kpi["contracts_rent"],
        "revenue":                int(kpi["revenue"]),
        "revenue_goal":           int(agency["revenue_goal"]),
        "inquiries_by_source":    inquiries_by_source,
        "agents":                 agents,
        "tracks_sale":            agency.get("tracks_sale", True),
        "tracks_rent":            agency.get("tracks_rent", False),
    }


def save_report(agency_id: str, week_start: date, html: str, report_type: str = "weekly"):
    """Arhivira HTML izveštaj u bazu."""
    sb = get_client()
    sb.table("reports").upsert({
        "agency_id":   agency_id,
        "week_start":  week_start.isoformat(),
        "html":        html,
        "sent_at":     date.today().isoformat(),
        "report_type": report_type,
    }, on_conflict="agency_id,week_start").execute()


def get_monthly_report_data(agency_id: str) -> dict:
    """Agregira sve nedeljne KPI-eve za prošli mesec."""
    sb = get_client()

    today = date.today()
    month_end   = today.replace(day=1) - timedelta(days=1)
    month_start = month_end.replace(day=1)

    agency = (
        sb.table("agencies")
        .select("name, email, revenue_goal, plan_id, logo_url, subscription_status, trial_ends_at, current_period_end")
        .eq("id", agency_id)
        .single()
        .execute()
        .data
    )

    weeks_raw = (
        sb.table("weekly_kpis")
        .select("*")
        .eq("agency_id", agency_id)
        .gte("week_start", month_start.isoformat())
        .lte("week_start", month_end.isoformat())
        .order("week_start")
        .execute()
        .data
    )

    sources_raw = (
        sb.table("inquiry_sources")
        .select("source, count")
        .eq("agency_id", agency_id)
        .gte("week_start", month_start.isoformat())
        .lte("week_start", month_end.isoformat())
        .execute()
        .data
    )
    sources: dict = {}
    for row in sources_raw:
        sources[row["source"]] = sources.get(row["source"], 0) + row["count"]

    perf_raw = (
        sb.table("agent_performance")
        .select("inquiries, contracts, agents(name)")
        .eq("agency_id", agency_id)
        .gte("week_start", month_start.isoformat())
        .lte("week_start", month_end.isoformat())
        .execute()
        .data
    )
    agents: dict = {}
    for row in perf_raw:
        name = row["agents"]["name"]
        if name not in agents:
            agents[name] = {"name": name, "inquiries": 0, "contracts": 0}
        agents[name]["inquiries"] += row["inquiries"]
        agents[name]["contracts"] += row["contracts"]
    agents_list = sorted(agents.values(), key=lambda a: a["contracts"], reverse=True)

    # Prethodni mesec prihod (za poređenje)
    prev_end   = month_start - timedelta(days=1)
    prev_start = prev_end.replace(day=1)
    prev_weeks = (
        sb.table("weekly_kpis")
        .select("revenue")
        .eq("agency_id", agency_id)
        .gte("week_start", prev_start.isoformat())
        .lte("week_start", prev_end.isoformat())
        .execute()
        .data
    )
    prev_revenue = sum(w["revenue"] for w in prev_weeks)

    total_inquiries     = sum(w["inquiries"]      for w in weeks_raw)
    total_contracts_sale = sum(w["contracts_sale"] for w in weeks_raw)
    total_contracts_rent = sum(w["contracts_rent"] for w in weeks_raw)
    total_revenue       = sum(w["revenue"]         for w in weeks_raw)
    monthly_goal        = int(agency["revenue_goal"]) * len(weeks_raw) if weeks_raw else int(agency["revenue_goal"]) * 4

    best_week = max(weeks_raw, key=lambda w: w["contracts_sale"] + w["contracts_rent"]) if weeks_raw else None

    MONTHS_SR = ["", "januar", "februar", "mart", "april", "maj", "jun",
                 "jul", "avgust", "septembar", "oktobar", "novembar", "decembar"]

    return {
        "agency_name":          agency["name"],
        "agency_email":         agency["email"],
        "plan_id":              _effective_plan(agency),
        "subscription_status":  agency.get("subscription_status"),
        "logo_url":             agency.get("logo_url"),
        "month_name":           f"{MONTHS_SR[month_start.month]} {month_start.year}",
        "month_start":          month_start.strftime("%d.%m.%Y"),
        "month_end":            month_end.strftime("%d.%m.%Y"),
        "generated_at":         today.strftime("%d.%m.%Y"),
        "total_inquiries":      total_inquiries,
        "total_contracts_sale": total_contracts_sale,
        "total_contracts_rent": total_contracts_rent,
        "total_contracts":      total_contracts_sale + total_contracts_rent,
        "total_revenue":        int(total_revenue),
        "monthly_goal":         monthly_goal,
        "revenue_pct":          round((total_revenue / (monthly_goal or 1)) * 100),
        "prev_revenue":         int(prev_revenue),
        "revenue_change_pct":   round(((total_revenue - prev_revenue) / (prev_revenue or 1)) * 100),
        "weeks_count":          len(weeks_raw),
        "weekly_breakdown":     weeks_raw,
        "best_week":            best_week,
        "inquiries_by_source":  sources,
        "agents":               agents_list,
    }


def get_benchmark_data(week_start_iso: str) -> dict | None:
    """Vraća agregirane proseke svih agencija za datu nedelju."""
    sb = get_client()
    try:
        rows = (
            sb.table("weekly_kpis")
            .select("inquiries, contracts_sale, contracts_rent, revenue")
            .eq("week_start", week_start_iso)
            .execute()
            .data
        )
        if not rows or len(rows) < 2:
            return None
        convs = [
            (r["contracts_sale"] + r["contracts_rent"]) / max(r["inquiries"], 1) * 100
            for r in rows
        ]
        return {
            "avg_conversion": round(sum(convs) / len(convs), 1),
            "avg_revenue":    round(sum(r["revenue"] for r in rows) / len(rows)),
            "avg_inquiries":  round(sum(r["inquiries"] for r in rows) / len(rows)),
            "agency_count":   len(rows),
        }
    except Exception:
        return None


def get_all_active_clients() -> list[dict]:
    """Vraća sve aktivne agencije sa UUID-ovima i efektivnim planom."""
    sb = get_client()
    rows = (
        sb.table("agencies")
        .select("id, name, email, plan_id, subscription_status, tracks_sale, tracks_rent")
        .eq("active", True)
        .execute()
        .data
    )
    for r in rows:
        r["plan_id"] = _effective_plan(r)
    return rows


# ─────────────────────────────────────────────────────────────────────────────
# Market data: persist + benchmark (Faza 1 plana)
# ─────────────────────────────────────────────────────────────────────────────

def save_market_snapshot(snapshot: dict, listings: list[dict]) -> str | None:
    """
    Upisuje agregirani snapshot u market_snapshots i pojedinačne oglase u
    market_listings_sample. Idempotentno: ako snapshot za isti
    (site, city, property_type, transaction_type, date) već postoji, ažurira ga.

    Vraća UUID upisanog/ažuriranog snapshot-a, ili None pri grešci.
    """
    sb = get_client()
    snapshot_date = snapshot.get("scraped_at") or date.today().isoformat()

    snap_row = {
        "site":                 snapshot["site"],
        "city":                 snapshot.get("city", "beograd"),
        "property_type":        snapshot.get("property_type", "apartment"),
        "transaction_type":     snapshot.get("transaction_type", "sale"),
        "snapshot_date":        snapshot_date,
        "total_listings":       snapshot.get("total_listings", 0),
        "avg_price_eur_m2":     snapshot.get("avg_price_eur_m2"),
        "median_price_eur_m2":  snapshot.get("median_price_eur_m2"),
        "price_p25":            snapshot.get("price_p25"),
        "price_p75":            snapshot.get("price_p75"),
        "avg_total_price_eur":  snapshot.get("avg_total_price_eur"),
        "price_min_eur":        snapshot.get("price_min_eur") or 0,
        "price_max_eur":        snapshot.get("price_max_eur") or 0,
        "new_this_week":        snapshot.get("new_this_week", 0),
        "raw_sample_count":     snapshot.get("raw_sample_count", 0),
        "top_neighborhoods":    snapshot.get("top_neighborhoods") or [],
        "is_mock":              snapshot.get("is_mock", False),
    }

    try:
        res = (
            sb.table("market_snapshots")
            .upsert(snap_row, on_conflict="site,city,property_type,transaction_type,snapshot_date")
            .execute()
        )
        snapshot_id = (res.data or [{}])[0].get("id")
        if not snapshot_id:
            # upsert nije vratio id (RLS ili Postgres verzija) — uradi explicit lookup
            lookup = (
                sb.table("market_snapshots")
                .select("id")
                .eq("site", snap_row["site"])
                .eq("city", snap_row["city"])
                .eq("property_type", snap_row["property_type"])
                .eq("transaction_type", snap_row["transaction_type"])
                .eq("snapshot_date", snap_row["snapshot_date"])
                .single()
                .execute()
            )
            snapshot_id = lookup.data["id"]
    except Exception as e:
        print(f"[DB] save_market_snapshot failed: {e}")
        return None

    if not listings:
        return snapshot_id

    # Obriši stare uzorke za isti snapshot (idempotentno re-run istog dana)
    try:
        sb.table("market_listings_sample").delete().eq("snapshot_id", snapshot_id).execute()
    except Exception as e:
        print(f"[DB] cleanup old listings failed: {e}")

    # Bulk insert listinga (chunked, Supabase limit ~1000 per request)
    rows = []
    for l in listings:
        rows.append({
            "snapshot_id":      snapshot_id,
            "site":             l.get("site"),
            "external_id":      l.get("external_id"),
            "url":              l.get("url"),
            "transaction_type": l.get("transaction_type"),
            "property_type":    l.get("property_type", "apartment"),
            "city":             l.get("city", "beograd"),
            "neighborhood":     l.get("neighborhood"),
            "area_m2":          l.get("area_m2"),
            "rooms":            l.get("rooms"),
            "floor":            l.get("floor"),
            "year_built":       l.get("year_built"),
            "price_eur":        l.get("price_eur"),
            "price_eur_m2":     l.get("price_eur_m2"),
            "listed_at":        l.get("listed_at"),
            "snapshot_date":    snapshot_date,
            "publisher":        l.get("publisher"),
            "publisher_type":   l.get("publisher_type"),
            "title":            l.get("title"),
        })

    CHUNK = 500
    try:
        for i in range(0, len(rows), CHUNK):
            sb.table("market_listings_sample").insert(rows[i:i + CHUNK]).execute()
    except Exception as e:
        print(f"[DB] insert listings failed: {e}")

    return snapshot_id


def get_market_segment_stats(
    transaction_type: str,
    neighborhood: str | None = None,
    city: str = "beograd",
    property_type: str = "apartment",
    days_lookback: int = 14,
) -> dict | None:
    """
    Vraća medijanu, P25, P75 €/m² i broj uzoraka za zadati segment
    iz market_listings_sample (uzima poslednjih `days_lookback` dana).

    Vraća None ako uzorak nije dovoljno velik (< 5 oglasa).
    """
    sb = get_client()
    cutoff = (date.today() - timedelta(days=days_lookback)).isoformat()

    q = (
        sb.table("market_listings_sample")
        .select("price_eur_m2")
        .eq("transaction_type", transaction_type)
        .eq("city", city)
        .eq("property_type", property_type)
        .gte("snapshot_date", cutoff)
        .not_.is_("price_eur_m2", "null")
    )
    if neighborhood:
        q = q.eq("neighborhood", neighborhood)

    try:
        rows = q.execute().data or []
    except Exception as e:
        print(f"[DB] get_market_segment_stats failed: {e}")
        return None

    values = [float(r["price_eur_m2"]) for r in rows if r.get("price_eur_m2")]
    if len(values) < 5:
        return None

    values.sort()
    n = len(values)
    from statistics import median
    return {
        "sample_size":   n,
        "median_eur_m2": round(median(values)),
        "p25_eur_m2":    round(values[n // 4]),
        "p75_eur_m2":    round(values[(3 * n) // 4]),
        "neighborhood":  neighborhood,
        "city":          city,
    }


def get_agency_active_listings(agency_id: str) -> list[dict]:
    """Vraća aktivne oglase agencije sa poljima potrebnim za pricing benchmark."""
    sb = get_client()
    try:
        return (
            sb.table("listings")
            .select("id, ref_number, type, transaction, title, price, currency, area_m2, city, municipality, rooms")
            .eq("agency_id", agency_id)
            .eq("active", True)
            .execute()
            .data or []
        )
    except Exception as e:
        print(f"[DB] get_agency_active_listings failed: {e}")
        return []


def compute_pricing_benchmark(agency_id: str, days_lookback: int = 14) -> list[dict]:
    """
    Za svaki aktivan oglas agencije izračunaj kako se uklapa u tržište:
      - segment medijana €/m² (po kvartu + tranzakciji + tipu)
      - vaš €/m²
      - delta_pct (+iznad, -ispod)
      - overpriced_flag (True ako > +15%)

    Vraća listu rečnika spremnu za template iteraciju.
    Preskače oglase bez dovoljno uzoraka u segmentu ili bez cene/površine.
    """
    listings = get_agency_active_listings(agency_id)
    if not listings:
        return []

    # Mapping iz listings tabele u market vokabular
    txn_map = {"prodaja": "sale", "zakup": "rent"}
    type_map = {"stan": "apartment", "kuca": "house", "poslovni": "commercial", "plac": "land"}

    out: list[dict] = []
    for l in listings:
        try:
            price = float(l["price"])
            area  = float(l["area_m2"])
        except (TypeError, ValueError, KeyError):
            continue
        if area <= 0 or price <= 0:
            continue

        ttype = txn_map.get(l.get("transaction"))
        ptype = type_map.get(l.get("type"))
        if not ttype or not ptype:
            continue

        own_eur_m2 = price / area
        # Currency: ako nije EUR, preskačemo (za sada držimo Beograd EUR)
        if (l.get("currency") or "EUR").upper() != "EUR":
            continue

        # Pokušaj segment by neighborhood; fallback na city-wide
        stats = get_market_segment_stats(
            transaction_type=ttype,
            neighborhood=l.get("municipality"),
            city=(l.get("city") or "beograd").lower(),
            property_type=ptype,
            days_lookback=days_lookback,
        )
        scope = "neighborhood"
        if not stats:
            stats = get_market_segment_stats(
                transaction_type=ttype,
                neighborhood=None,
                city=(l.get("city") or "beograd").lower(),
                property_type=ptype,
                days_lookback=days_lookback,
            )
            scope = "city"
        if not stats:
            continue  # nema dovoljno tržišnih podataka za poređenje

        delta_pct = round((own_eur_m2 - stats["median_eur_m2"]) / stats["median_eur_m2"] * 100, 1)

        out.append({
            "listing_id":     l.get("id"),
            "ref_number":     l.get("ref_number"),
            "title":          l.get("title"),
            "transaction":    ttype,                 # 'sale' | 'rent'
            "property_type":  ptype,
            "neighborhood":   l.get("municipality"),
            "area_m2":        round(area),
            "rooms":          l.get("rooms"),
            "own_price_eur":  int(price),
            "own_eur_m2":     round(own_eur_m2),
            "market_median_eur_m2": stats["median_eur_m2"],
            "market_p25":     stats["p25_eur_m2"],
            "market_p75":     stats["p75_eur_m2"],
            "sample_size":    stats["sample_size"],
            "scope":          scope,                 # 'neighborhood' | 'city' fallback
            "delta_pct":      delta_pct,
            "overpriced_flag": delta_pct >= 15,
            "underpriced_flag": delta_pct <= -10,
        })

    # Sortiraj: prvo prekoračeni (najveća delta), pa neutralni, pa potcenjeni
    out.sort(key=lambda x: -x["delta_pct"])
    return out


# ─────────────────────────────────────────────────────────────────────────────
# Faza 2: Trend, DOM, Hot Zones
# ─────────────────────────────────────────────────────────────────────────────

def get_market_trend(
    transaction_type: str,
    city: str = "beograd",
    property_type: str = "apartment",
    neighborhood: str | None = None,
    lookback_days: int = 180,
) -> dict | None:
    """
    Vremenska serija €/m² za zadati segment.
    Vraća {series, latest_eur_m2, mom_pct, yoy_pct} ili None ako nedovoljno tačaka.

    Za kvart-specific trend agregira pojedinačne listinge po danu (medijana).
    Za grad-wide trend koristi market_snapshots agregate (po sajtu × dan, pa medijana medijana).
    """
    from statistics import median
    sb = get_client()
    cutoff = (date.today() - timedelta(days=lookback_days)).isoformat()

    by_date: dict[str, list[float]] = {}

    if neighborhood:
        q = (
            sb.table("market_listings_sample")
            .select("snapshot_date, price_eur_m2")
            .eq("transaction_type", transaction_type)
            .eq("city", city)
            .eq("property_type", property_type)
            .eq("neighborhood", neighborhood)
            .gte("snapshot_date", cutoff)
            .not_.is_("price_eur_m2", "null")
        )
        try:
            rows = q.execute().data or []
        except Exception as e:
            print(f"[DB] get_market_trend(nb) failed: {e}")
            return None
        for r in rows:
            try:
                by_date.setdefault(r["snapshot_date"], []).append(float(r["price_eur_m2"]))
            except (TypeError, ValueError):
                continue
    else:
        try:
            rows = (
                sb.table("market_snapshots")
                .select("snapshot_date, median_price_eur_m2")
                .eq("transaction_type", transaction_type)
                .eq("city", city)
                .eq("property_type", property_type)
                .gte("snapshot_date", cutoff)
                .not_.is_("median_price_eur_m2", "null")
                .execute()
                .data or []
            )
        except Exception as e:
            print(f"[DB] get_market_trend(city) failed: {e}")
            return None
        for r in rows:
            try:
                by_date.setdefault(r["snapshot_date"], []).append(float(r["median_price_eur_m2"]))
            except (TypeError, ValueError):
                continue

    if len(by_date) < 2:
        return None

    series = [
        {"date": d, "median_eur_m2": round(median(vals)), "sample": len(vals)}
        for d, vals in sorted(by_date.items())
    ]

    latest = series[-1]
    latest_date = date.fromisoformat(latest["date"])

    # MoM: tačka najbliža (latest - 30 dana)
    mom_target = latest_date - timedelta(days=30)
    mom_point = min(series[:-1], key=lambda p: abs((date.fromisoformat(p["date"]) - mom_target).days), default=None)
    mom_pct = None
    if mom_point and mom_point["median_eur_m2"]:
        mom_pct = round((latest["median_eur_m2"] - mom_point["median_eur_m2"]) / mom_point["median_eur_m2"] * 100, 1)

    # YoY: prva tačka <= (latest - 365 dana)
    yoy_target_iso = (latest_date - timedelta(days=365)).isoformat()
    yoy_candidates = [p for p in series if p["date"] <= yoy_target_iso]
    yoy_pct = None
    if yoy_candidates and yoy_candidates[-1]["median_eur_m2"]:
        yoy_point = yoy_candidates[-1]
        yoy_pct = round((latest["median_eur_m2"] - yoy_point["median_eur_m2"]) / yoy_point["median_eur_m2"] * 100, 1)

    return {
        "series":         series,
        "latest_eur_m2":  latest["median_eur_m2"],
        "mom_pct":        mom_pct,
        "yoy_pct":        yoy_pct,
        "neighborhood":   neighborhood,
        "lookback_days":  lookback_days,
    }


def compute_dom_stats(
    transaction_type: str,
    city: str = "beograd",
    property_type: str = "apartment",
    neighborhood: str | None = None,
    lookback_days: int = 90,
    considered_sold_after: int = 7,
) -> dict | None:
    """
    Days-on-Market: za svaki (site, external_id) izračunaj koliko dana je bio viđen
    pre nego što je nestao iz scrape rezultata.

    Listing se smatra "prodatim/skinutim" ako poslednji put viđen pre
    `considered_sold_after` dana.

    Vraća median/P25/P75 DOM za segment, ili None ako ima < 5 sold listinga.
    """
    from statistics import median
    sb = get_client()
    cutoff = (date.today() - timedelta(days=lookback_days)).isoformat()

    q = (
        sb.table("market_listings_sample")
        .select("site, external_id, snapshot_date")
        .eq("transaction_type", transaction_type)
        .eq("city", city)
        .eq("property_type", property_type)
        .gte("snapshot_date", cutoff)
    )
    if neighborhood:
        q = q.eq("neighborhood", neighborhood)

    try:
        rows = q.execute().data or []
    except Exception as e:
        print(f"[DB] compute_dom_stats failed: {e}")
        return None

    by_id: dict[tuple[str, str], dict[str, str]] = {}
    for r in rows:
        key = (r["site"], r["external_id"])
        sd = r["snapshot_date"]
        if key not in by_id:
            by_id[key] = {"min": sd, "max": sd}
        else:
            if sd < by_id[key]["min"]: by_id[key]["min"] = sd
            if sd > by_id[key]["max"]: by_id[key]["max"] = sd

    today = date.today()
    sold_cutoff = today - timedelta(days=considered_sold_after)

    sold_doms: list[int] = []
    still_active = 0
    for d in by_id.values():
        first = date.fromisoformat(d["min"])
        last  = date.fromisoformat(d["max"])
        duration = (last - first).days
        if last <= sold_cutoff:
            sold_doms.append(duration)
        else:
            still_active += 1

    if len(sold_doms) < 5:
        return None

    sold_doms.sort()
    n = len(sold_doms)
    return {
        "median_dom_days":   int(median(sold_doms)),
        "dom_p25":           sold_doms[n // 4],
        "dom_p75":           sold_doms[(3 * n) // 4],
        "sold_sample_size":  n,
        "still_active":      still_active,
        "neighborhood":      neighborhood,
    }


def compute_hot_zones(
    transaction_type: str,
    city: str = "beograd",
    property_type: str = "apartment",
    lookback_days: int = 30,
    top_n: int = 5,
) -> list[dict]:
    """
    Rangira kvartove po "hot" score-u: kombinacija rasta cene i broja novih oglasa.

    Score = price_change_pct + (new_this_week / 5)
    Vraća top N kvartova sa najvišim score-om.
    """
    from statistics import median
    sb = get_client()
    cutoff = (date.today() - timedelta(days=lookback_days)).isoformat()

    try:
        rows = (
            sb.table("market_listings_sample")
            .select("neighborhood, snapshot_date, price_eur_m2, listed_at")
            .eq("transaction_type", transaction_type)
            .eq("city", city)
            .eq("property_type", property_type)
            .gte("snapshot_date", cutoff)
            .not_.is_("neighborhood", "null")
            .execute()
            .data or []
        )
    except Exception as e:
        print(f"[DB] compute_hot_zones failed: {e}")
        return []

    if not rows:
        return []

    today = date.today()
    half_cutoff = (today - timedelta(days=lookback_days // 2)).isoformat()
    week_cutoff = (today - timedelta(days=7)).isoformat()

    nbs: dict[str, dict] = {}
    for r in rows:
        nb = r["neighborhood"]
        if nb not in nbs:
            nbs[nb] = {"recent": [], "older": [], "total": 0, "new_this_week": 0}
        price = r.get("price_eur_m2")
        if price is not None:
            try:
                p = float(price)
                if r["snapshot_date"] >= half_cutoff:
                    nbs[nb]["recent"].append(p)
                else:
                    nbs[nb]["older"].append(p)
            except (TypeError, ValueError):
                pass
        nbs[nb]["total"] += 1
        listed = r.get("listed_at")
        if listed and listed >= week_cutoff:
            nbs[nb]["new_this_week"] += 1

    results: list[dict] = []
    for nb, d in nbs.items():
        if not d["recent"] or not d["older"]:
            continue
        recent_med = median(d["recent"])
        older_med  = median(d["older"])
        if older_med <= 0:
            continue
        change_pct = round((recent_med - older_med) / older_med * 100, 1)
        results.append({
            "neighborhood":     nb,
            "median_eur_m2":    round(recent_med),
            "price_change_pct": change_pct,
            "new_this_week":    d["new_this_week"],
            "sample_size":      d["total"],
            "score":            round(change_pct + d["new_this_week"] / 5.0, 2),
        })

    results.sort(key=lambda x: -x["score"])
    return results[:top_n]


# ─────────────────────────────────────────────────────────────────────────────
# Faza 3: Pricing recommendations, Listing opportunities, Competitor inventory
# ─────────────────────────────────────────────────────────────────────────────

def _confidence_label(sample_size: int) -> str:
    if sample_size >= 50: return "high"
    if sample_size >= 20: return "medium"
    return "low"


def compute_pricing_recommendations(
    agency_id: str,
    days_lookback: int = 14,
    overprice_threshold_pct: float = 8.0,
) -> list[dict]:
    """
    Per-oglas konkretna preporuka korekcije cene.
    Reuses compute_pricing_benchmark i dodaje:
      - target_price_eur (zaokruženo na 100€)
      - delta_amount_eur (koliko spustiti)
      - rationale (kratak tekst za UI/email)
      - confidence (high/medium/low na osnovu sample_size segmenta)

    Vraća listu preporuka samo za oglase >= overprice_threshold_pct iznad medijane.
    Sortirano po delta_amount_eur (najveće sniženje prvo).
    """
    benchmark = compute_pricing_benchmark(agency_id, days_lookback=days_lookback)
    recs: list[dict] = []
    for row in benchmark:
        if row["delta_pct"] < overprice_threshold_pct:
            continue
        target_eur_m2  = row["market_median_eur_m2"]
        target_price   = int(round(target_eur_m2 * row["area_m2"] / 100.0) * 100)
        delta_amount   = row["own_price_eur"] - target_price
        confidence     = _confidence_label(row["sample_size"])

        rationale = (
            f"Trenutna cena je {row['delta_pct']:+.1f}% iznad medijane tržišta "
            f"({row['own_eur_m2']} vs {target_eur_m2} €/m²; uzorak {row['sample_size']} sličnih oglasa "
            f"u {'kvartu' if row['scope'] == 'neighborhood' else 'gradu'}). "
            f"Sniženje na {target_price:,}€ vraća oglas u opseg P25–P75 "
            f"({row['market_p25']}–{row['market_p75']} €/m²)."
        )

        recs.append({
            "listing_id":          row["listing_id"],
            "ref_number":          row["ref_number"],
            "title":                row["title"],
            "transaction":         row["transaction"],
            "neighborhood":        row["neighborhood"],
            "area_m2":             row["area_m2"],
            "own_price_eur":       row["own_price_eur"],
            "own_eur_m2":          row["own_eur_m2"],
            "target_price_eur":    target_price,
            "target_eur_m2":       target_eur_m2,
            "delta_amount_eur":    delta_amount,
            "delta_pct":           row["delta_pct"],
            "sample_size":         row["sample_size"],
            "confidence":          confidence,
            "scope":               row["scope"],
            "rationale":           rationale,
        })

    recs.sort(key=lambda r: -r["delta_amount_eur"])
    return recs


def compute_listing_opportunities(
    city: str = "beograd",
    transaction_type: str = "sale",
    property_type: str = "apartment",
    neighborhood: str | None = None,
    min_days_listed: int = 90,
    lookback_days: int = 120,
    top_n: int = 10,
) -> list[dict]:
    """
    Lead generation: tuđi oglasi koji su 'zaglavljeni' na tržištu
    (first_seen pre min_days_listed dana, još uvek aktivan — last_seen u poslednjih 7 dana).

    Heuristika: vlasnici takvih nekretnina su verovatno frustrirani i otvoreni
    za prijem agencije sa ekskluzivnim ugovorom (ili korekciju cene). Bez ličnih
    kontakata — samo URL i osnovne atribute.
    """
    from statistics import median
    sb = get_client()
    cutoff = (date.today() - timedelta(days=lookback_days)).isoformat()

    q = (
        sb.table("market_listings_sample")
        .select("site, external_id, snapshot_date, neighborhood, area_m2, rooms, price_eur, price_eur_m2, url, title, publisher, publisher_type")
        .eq("transaction_type", transaction_type)
        .eq("city", city)
        .eq("property_type", property_type)
        .gte("snapshot_date", cutoff)
    )
    if neighborhood:
        q = q.eq("neighborhood", neighborhood)

    try:
        rows = q.execute().data or []
    except Exception as e:
        print(f"[DB] compute_listing_opportunities failed: {e}")
        return []

    today = date.today()
    stuck_threshold = today - timedelta(days=min_days_listed)
    active_threshold = today - timedelta(days=7)

    by_id: dict[tuple[str, str], dict] = {}
    for r in rows:
        key = (r["site"], r["external_id"])
        sd = r["snapshot_date"]
        if key not in by_id:
            by_id[key] = {"min": sd, "max": sd, "row": r}
        else:
            if sd < by_id[key]["min"]: by_id[key]["min"] = sd
            if sd > by_id[key]["max"]:
                by_id[key]["max"] = sd
                by_id[key]["row"]  = r  # uzmi najnoviju kopiju atributa

    stuck: list[dict] = []
    for key, d in by_id.items():
        first = date.fromisoformat(d["min"])
        last  = date.fromisoformat(d["max"])
        if first <= stuck_threshold and last >= active_threshold:
            r = d["row"]
            stuck.append({
                "site":         r["site"],
                "external_id":  r["external_id"],
                "url":          r["url"],
                "title":        r.get("title"),
                "neighborhood": r.get("neighborhood"),
                "area_m2":      r.get("area_m2"),
                "rooms":        r.get("rooms"),
                "price_eur":    r.get("price_eur"),
                "price_eur_m2": r.get("price_eur_m2"),
                "publisher":    r.get("publisher"),
                "publisher_type": r.get("publisher_type"),
                "days_listed": (last - first).days,
                "first_seen":  d["min"],
                "last_seen":   d["max"],
            })

    stuck.sort(key=lambda x: -x["days_listed"])
    return stuck[:top_n]


def compute_competitor_inventory(
    city: str = "beograd",
    transaction_type: str = "sale",
    property_type: str = "apartment",
    snapshot_days_window: int = 7,
    top_n: int = 5,
) -> dict:
    """
    Agregirano: broj aktivnih oglasa po publisher-u (agenciji) iz poslednjeg snapshot window-a.
    Etika: NE prikazuje cene niti DOM per-agenciji — samo broj inventara.

    Vraća:
      {
        "top": [{publisher, listing_count, market_share_pct}, ...],
        "distribution": {"1-5": X, "6-20": Y, "21-50": Z, "50+": W},
        "total_agencies": N,
        "total_listings": M,
      }
    """
    sb = get_client()
    cutoff = (date.today() - timedelta(days=snapshot_days_window)).isoformat()

    try:
        rows = (
            sb.table("market_listings_sample")
            .select("publisher, external_id, site")
            .eq("transaction_type", transaction_type)
            .eq("city", city)
            .eq("property_type", property_type)
            .eq("publisher_type", "agency")
            .gte("snapshot_date", cutoff)
            .not_.is_("publisher", "null")
            .execute()
            .data or []
        )
    except Exception as e:
        print(f"[DB] compute_competitor_inventory failed: {e}")
        return {"top": [], "distribution": {}, "total_agencies": 0, "total_listings": 0}

    if not rows:
        return {"top": [], "distribution": {}, "total_agencies": 0, "total_listings": 0}

    # Distinct po (site, external_id) da izbegnem dvojnik kroz dane
    seen: set[tuple[str, str]] = set()
    by_pub: dict[str, set] = {}
    for r in rows:
        pub = (r.get("publisher") or "").strip()
        if not pub:
            continue
        key = (r["site"], r["external_id"])
        if key in seen:
            continue
        seen.add(key)
        by_pub.setdefault(pub, set()).add(key)

    counts = [(pub, len(ids)) for pub, ids in by_pub.items()]
    counts.sort(key=lambda x: -x[1])
    total_listings = sum(c for _, c in counts)
    total_agencies = len(counts)

    top = [
        {
            "publisher":         pub,
            "listing_count":     n,
            "market_share_pct":  round(n / total_listings * 100, 1) if total_listings else 0.0,
        }
        for pub, n in counts[:top_n]
    ]

    buckets = {"1-5": 0, "6-20": 0, "21-50": 0, "50+": 0}
    for _, n in counts:
        if n <= 5:    buckets["1-5"]   += 1
        elif n <= 20: buckets["6-20"]  += 1
        elif n <= 50: buckets["21-50"] += 1
        else:         buckets["50+"]   += 1

    return {
        "top":            top,
        "distribution":   buckets,
        "total_agencies": total_agencies,
        "total_listings": total_listings,
    }


def generate_market_alerts(agency_id: str, max_alerts: int = 5) -> list[dict]:
    """
    Sastavlja listu actionable alerta za daily email digest.
    Tipovi:
      - pricing: vaš oglas X% iznad medijane segmenta
      - hot_zone: kvart Y raste — uputite agente
      - opportunity: N stuck tuđih oglasa u kvartu Z (potencijalni listinzi)

    Bez duplikata kvarta — jedan alert po kvartu (najjači).
    """
    alerts: list[dict] = []

    # 1) Pricing alerts — top 2 oglasa sa najvećim sniženjem
    try:
        recs = compute_pricing_recommendations(agency_id)
        for r in recs[:2]:
            alerts.append({
                "type":      "pricing",
                "severity":  "high" if r["delta_pct"] >= 15 else "medium",
                "title":     f"Oglas „{r['title'] or r['ref_number'] or r['listing_id']}" "“ je {0:+.1f}% iznad tržišta".format(r["delta_pct"]),
                "body":      r["rationale"],
                "cta_url":   None,
                "ref":       r["ref_number"],
                "amount_eur": r["delta_amount_eur"],
            })
    except Exception as e:
        print(f"[Alerts] pricing failed: {e}")

    # 2) Hot zone — top 1 kvart po score-u
    try:
        hot = compute_hot_zones(transaction_type="sale", top_n=1)
        for h in hot:
            if h["price_change_pct"] >= 2:
                alerts.append({
                    "type":     "hot_zone",
                    "severity": "info",
                    "title":    f"{h['neighborhood']}: rast cena {h['price_change_pct']:+.1f}% (15d)",
                    "body":     (
                        f"Medijana {h['median_eur_m2']} €/m², {h['new_this_week']} novih oglasa ove nedelje. "
                        f"Razmislite o usmeravanju agenata na preuzimanje ekskluziva u {h['neighborhood']}u."
                    ),
                    "neighborhood": h["neighborhood"],
                })
    except Exception as e:
        print(f"[Alerts] hot_zone failed: {e}")

    # 3) Opportunities — top 1 kvart sa najviše stuck oglasa
    try:
        opps = compute_listing_opportunities(top_n=20)
        if opps:
            by_nb: dict[str, list] = {}
            for o in opps:
                nb = o.get("neighborhood") or "—"
                by_nb.setdefault(nb, []).append(o)
            best_nb = max(by_nb.items(), key=lambda kv: len(kv[1]))
            if len(best_nb[1]) >= 3:
                alerts.append({
                    "type":     "opportunity",
                    "severity": "info",
                    "title":    f"{len(best_nb[1])} stuck oglasa u {best_nb[0]}u (> 90 dana)",
                    "body":     (
                        "Vlasnici su verovatno otvoreni za korekciju cene ili prelazak na ekskluzivni ugovor. "
                        f"Pregled liste u tabu „Listing opportunities“ izveštaja."
                    ),
                    "neighborhood": best_nb[0],
                    "count": len(best_nb[1]),
                })
    except Exception as e:
        print(f"[Alerts] opportunity failed: {e}")

    return alerts[:max_alerts]


def expire_stale_trials() -> int:
    """Pokreće reconciliation funkciju u Postgres-u. Vraća broj promenjenih redova."""
    sb = get_client()
    res = sb.rpc("expire_stale_trials").execute()
    return res.data if isinstance(res.data, int) else 0


# ============================================================================
# Per-agent helperi za "Pojedinačni izveštaji po agentu" (Pro/Premium feature)
# ============================================================================

def get_agent_history(agent_id: str, weeks: int = 26) -> list[dict]:
    """Vraća listu nedeljnih perfomansi agenta (hronološki: najstarije → najnovije)."""
    if not agent_id:
        return []
    sb = get_client()
    cutoff = (date.today() - timedelta(days=weeks * 7)).isoformat()
    try:
        rows = (
            sb.table("agent_performance")
            .select("week_start, inquiries, contracts")
            .eq("agent_id", agent_id)
            .gte("week_start", cutoff)
            .order("week_start", desc=False)
            .execute()
            .data or []
        )
    except Exception as e:
        print(f"[DB] get_agent_history failed: {e}")
        return []

    out = []
    for r in rows:
        inq = r.get("inquiries") or 0
        cnt = r.get("contracts") or 0
        out.append({
            "week_start": r["week_start"],
            "inquiries":  inq,
            "contracts":  cnt,
            "conversion": round(cnt / max(inq, 1) * 100, 1),
        })
    return out


def _get_agent_listing_ids(agency_id: str, agent_id: str) -> set:
    """Set ID-ova aktivnih oglasa koje vodi agent."""
    if not agent_id:
        return set()
    sb = get_client()
    try:
        rows = (
            sb.table("listings")
            .select("id")
            .eq("agency_id", agency_id)
            .eq("agent_id", agent_id)
            .eq("active", True)
            .execute()
            .data or []
        )
        return {r["id"] for r in rows}
    except Exception as e:
        print(f"[DB] _get_agent_listing_ids failed: {e}")
        return set()


def get_agent_listings_with_benchmark(agency_id: str, agent_id: str) -> list[dict]:
    """pricing_benchmark filtriran samo na oglase agenta."""
    agent_listing_ids = _get_agent_listing_ids(agency_id, agent_id)
    if not agent_listing_ids:
        return []
    full = compute_pricing_benchmark(agency_id)
    return [row for row in full if row.get("listing_id") in agent_listing_ids]


def compute_agent_pricing_recommendations(agency_id: str, agent_id: str) -> list[dict]:
    """pricing_recommendations filtirano na oglase agenta."""
    agent_listing_ids = _get_agent_listing_ids(agency_id, agent_id)
    if not agent_listing_ids:
        return []
    full = compute_pricing_recommendations(agency_id)
    return [row for row in full if row.get("listing_id") in agent_listing_ids]


def _get_agent_neighborhoods(agency_id: str, agent_id: str) -> set:
    """Jedinstveni kvartovi (municipality) gde agent ima aktivne oglase."""
    if not agent_id:
        return set()
    sb = get_client()
    try:
        rows = (
            sb.table("listings")
            .select("municipality")
            .eq("agency_id", agency_id)
            .eq("agent_id", agent_id)
            .eq("active", True)
            .not_.is_("municipality", "null")
            .execute()
            .data or []
        )
        return {r["municipality"] for r in rows if r.get("municipality")}
    except Exception as e:
        print(f"[DB] _get_agent_neighborhoods failed: {e}")
        return set()


def save_agent_report_html(agency_id: str, agent_id: str, week_start: str, html: str) -> bool:
    """Upsert-uje HTML agent izveštaja u agent_reports tabelu. Vraća True ako uspešno."""
    sb = get_client()
    try:
        sb.table("agent_reports").upsert(
            {
                "agency_id":    agency_id,
                "agent_id":     agent_id,
                "week_start":   week_start,
                "html":         html,
                "generated_at": date.today().isoformat(),
            },
            on_conflict="agency_id,agent_id,week_start",
        ).execute()
        return True
    except Exception as e:
        print(f"[DB] save_agent_report_html failed: {e}")
        return False


def get_agent_report_html(agency_id: str, agent_id: str, week_start: str) -> str | None:
    """Vraća sačuvani HTML agent izveštaja ili None."""
    sb = get_client()
    try:
        res = (
            sb.table("agent_reports")
            .select("html")
            .eq("agency_id", agency_id)
            .eq("agent_id", agent_id)
            .eq("week_start", week_start)
            .single()
            .execute()
        )
        return res.data.get("html") if res.data else None
    except Exception as e:
        print(f"[DB] get_agent_report_html failed: {e}")
        return None


def list_agent_reports(agency_id: str, agent_id: str | None = None, limit: int = 12) -> list[dict]:
    """Lista sačuvanih agent izveštaja za agenciju (opcionalno filtrirano po agentu)."""
    sb = get_client()
    try:
        q = (
            sb.table("agent_reports")
            .select("agent_id, week_start, generated_at, agents(name)")
            .eq("agency_id", agency_id)
            .order("week_start", desc=True)
            .limit(limit)
        )
        if agent_id:
            q = q.eq("agent_id", agent_id)
        rows = q.execute().data or []
        return [
            {
                "agent_id":     r["agent_id"],
                "agent_name":   r["agents"]["name"] if r.get("agents") else "",
                "week_start":   r["week_start"],
                "generated_at": r["generated_at"],
            }
            for r in rows
        ]
    except Exception as e:
        print(f"[DB] list_agent_reports failed: {e}")
        return []


def get_agent_hot_zones(agency_id: str, agent_id: str, city: str = "beograd") -> list[dict]:
    """hot_zones filtrirano samo na kvartove gde agent ima oglase."""
    target = _get_agent_neighborhoods(agency_id, agent_id)
    if not target:
        return []
    try:
        full = compute_hot_zones(city=city, transaction_type="sale")
    except Exception as e:
        print(f"[DB] get_agent_hot_zones failed: {e}")
        return []
    return [z for z in (full or []) if z.get("neighborhood") in target]
