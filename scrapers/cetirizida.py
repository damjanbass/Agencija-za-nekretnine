import json
import re
import time
from bs4 import BeautifulSoup
from .base import Listing, MarketSnapshot, aggregate_from_listings, fetch_html

SITE = "4zida"

URLS = {
    "sale": "https://4zida.rs/prodaja-stanova/{city}",
    "rent": "https://4zida.rs/izdavanje-stanova/{city}",
}

PAGE_PARAM = "strana"

SALE_PRICE_RANGE = (10_000, 5_000_000)
RENT_PRICE_RANGE = (50, 10_000)


def scrape(city: str = "beograd", transaction_type: str = "sale", max_pages: int = 5) -> MarketSnapshot:
    base_url = URLS.get(transaction_type, URLS["sale"]).format(city=city)
    listings: list[Listing] = []
    total_from_site: int | None = None
    homepage = "https://4zida.rs/"

    try:
        prev_url = homepage
        for page in range(1, max_pages + 1):
            page_url = base_url if page == 1 else f"{base_url}?{PAGE_PARAM}={page}"
            # 4zida je SPA — networkidle ne radi (konstantni pollers),
            # pa koristimo domcontentloaded + scroll + dug wait za hydration.
            html = fetch_html(
                page_url,
                referer=prev_url,
                prefer_browser=True,
                wait_until="domcontentloaded",
                scroll_to_load=True,
                extra_wait_ms=4500,
                wait_for_selector=None,
            )
            if html is None:
                if page == 1:
                    raise RuntimeError("nijedna strana nije fetch-ovana")
                break
            soup = BeautifulSoup(html, "html.parser")

            if page == 1:
                total_from_site = _parse_total(soup)

            page_listings = _parse_listings(soup, transaction_type, city)
            # Fallback: ako CSS selektori vrate 0, pokušaj __NEXT_DATA__ JSON
            if not page_listings:
                page_listings = _parse_next_data(soup, transaction_type, city)
            if not page_listings:
                break
            listings.extend(page_listings)
            prev_url = page_url

            time.sleep(1.5)

        if not listings:
            return _mock(base_url, transaction_type)

        agg = aggregate_from_listings(listings)
        return MarketSnapshot(
            site=SITE,
            url=base_url,
            transaction_type=transaction_type,
            city=city,
            total_listings=total_from_site or len(listings),
            new_this_week=0,
            listings=listings,
            is_mock=False,
            **agg,
        )
    except Exception as e:
        print(f"[4zida] Parsing failed: {type(e).__name__}: {e}")
        return _mock(base_url, transaction_type)


def _parse_total(soup: BeautifulSoup) -> int:
    for sel in [".results-count", ".total", "h1", "[data-cy='results-count']"]:
        el = soup.select_one(sel)
        if el:
            m = re.search(r"[\d\.]+", el.get_text())
            if m:
                return int(m.group().replace(".", ""))
    return 0


def _parse_next_data(soup: BeautifulSoup, transaction_type: str, city: str) -> list[Listing]:
    """
    Fallback: 4zida je Next.js SPA. Kad CSS selektori vrate prazno (statičke kartice
    nisu renderovane na server-side u istom obliku), pokušaj __NEXT_DATA__ JSON.
    """
    el = soup.find("script", id="__NEXT_DATA__")
    if not el or not el.string:
        return []
    try:
        data = json.loads(el.string)
    except (ValueError, TypeError):
        return []

    # Heuristički obilazak: traži listu objekata sa cenom + površinom
    candidates = _find_listing_collections(data)
    items: list[Listing] = []
    for raw in candidates:
        listing = _parse_json_listing(raw, transaction_type, city)
        if listing:
            items.append(listing)
    return items


def _find_listing_collections(obj, depth: int = 0) -> list[dict]:
    """Rekurzivno traži najveću listu rečnika koji 'liče na listinge'."""
    if depth > 8:
        return []
    if isinstance(obj, list):
        # Lista rečnika sa price/area poljima = verovatno listingi
        if obj and isinstance(obj[0], dict):
            sample = obj[0]
            keys = {k.lower() for k in sample.keys()}
            has_price = any(k in keys for k in ("price", "cena", "totalprice"))
            has_area  = any(k in keys for k in ("area", "size", "powierzchnia", "squaremeters", "m2"))
            if has_price and has_area and len(obj) >= 3:
                return obj
        # Rekurzivno
        for item in obj:
            r = _find_listing_collections(item, depth + 1)
            if r: return r
    elif isinstance(obj, dict):
        for v in obj.values():
            r = _find_listing_collections(v, depth + 1)
            if r: return r
    return []


def _parse_json_listing(raw: dict, transaction_type: str, city: str) -> Listing | None:
    lo, hi = SALE_PRICE_RANGE if transaction_type == "sale" else RENT_PRICE_RANGE

    ext = raw.get("id") or raw.get("uuid") or raw.get("slug")
    if ext is None:
        return None
    external_id = str(ext)

    # cena
    price = raw.get("price") or raw.get("cena") or raw.get("totalPrice")
    try:
        price = int(float(price)) if price is not None else None
        if price is not None and not (lo <= price <= hi):
            price = None
    except (TypeError, ValueError):
        price = None

    # površina
    area = raw.get("area") or raw.get("size") or raw.get("squareMeters") or raw.get("m2")
    try:
        area = float(area) if area is not None else None
        if area is not None and not (10 <= area <= 1000):
            area = None
    except (TypeError, ValueError):
        area = None

    rooms = raw.get("rooms") or raw.get("structure") or raw.get("noOfRooms")
    try:
        rooms = float(rooms) if rooms is not None else None
    except (TypeError, ValueError):
        rooms = None

    neighborhood = (
        raw.get("neighborhood") or raw.get("municipality") or raw.get("part")
        or (raw.get("location") or {}).get("neighborhood")
        if isinstance(raw.get("location"), dict)
        else raw.get("location")
    )
    if isinstance(neighborhood, dict):
        neighborhood = neighborhood.get("name")

    url = raw.get("url") or raw.get("link") or f"https://4zida.rs/stan/{external_id}"
    if isinstance(url, str) and not url.startswith("http"):
        url = f"https://4zida.rs{url}"

    publisher = None
    publisher_type = "unknown"
    adv = raw.get("advertiser") or raw.get("publisher")
    if isinstance(adv, dict):
        publisher = adv.get("name") or adv.get("title")
        publisher_type = "agency" if adv.get("type") == "agency" else "private"

    return Listing(
        site=SITE,
        external_id=external_id,
        url=url,
        transaction_type=transaction_type,
        property_type="apartment",
        city=city,
        neighborhood=neighborhood if isinstance(neighborhood, str) else None,
        area_m2=area,
        rooms=rooms,
        price_eur=price,
        publisher=publisher,
        publisher_type=publisher_type,
        title=raw.get("title") or raw.get("name"),
    )


_URL_4ZIDA_RE = re.compile(
    r"^/(prodaja-stanova|izdavanje-stanova)/([^/]+)/([^/]+)/([a-f0-9]{24})/?$"
)

_ROOMS_TYPE_MAP_4ZIDA = {
    "garsonjera": 0.5,
    "jednosoban-stan": 1, "jednoiposoban-stan": 1.5,
    "dvosoban-stan": 2, "dvoiposoban-stan": 2.5,
    "trosoban-stan": 3, "troiposoban-stan": 3.5,
    "cetvorosoban-stan": 4, "petosoban-stan": 5,
}


def _parse_listings(soup: BeautifulSoup, transaction_type: str, city: str) -> list[Listing]:
    """
    4zida koristi konzistentan URL pattern:
      /prodaja-stanova/{kvart-opstina-grad}/{tip-stana}/{mongo_id_24hex}
    Iz URL-a izvlačimo external_id, transaction_type, neighborhood, rooms (bez CSS klasa).
    Cena/površina se traže u parent kontejneru (deduplicate po external_id).
    """
    expected_prefix = "/prodaja-stanova/" if transaction_type == "sale" else "/izdavanje-stanova/"

    items: list[Listing] = []
    seen_ids: set[str] = set()

    for a in soup.select(f"a[href^='{expected_prefix}']"):
        href = a.get("href") or ""
        m = _URL_4ZIDA_RE.match(href)
        if not m:
            continue

        txn_path, location_slug, type_slug, external_id = m.groups()
        if external_id in seen_ids:
            continue
        seen_ids.add(external_id)

        # Nađi najbliži kontejner sa cenom (idi 3-5 nivoa naviše)
        container = a
        for _ in range(6):
            if container.parent is None:
                break
            container = container.parent
            txt = container.get_text(" ", strip=True)
            if "€" in txt and "m" in txt.lower():
                break

        text = container.get_text(" ", strip=True)
        price = _extract_price(container, text, transaction_type)
        area  = _extract_area(text)

        # Sobe iz URL slug-a (najpouzdaniji izvor)
        rooms = _ROOMS_TYPE_MAP_4ZIDA.get(type_slug.lower())

        # Kvart iz URL slug-a: "cubura-vracar-beograd" → "Čubura" (capitalize prvi segment)
        neighborhood = _slug_to_neighborhood(location_slug)

        # Title iz strukture ili text-a (fallback)
        title_el = container.select_one("h2, h3, [class*='title']")
        title = title_el.get_text(strip=True) if title_el else None

        publisher, publisher_type = _extract_publisher(container, text)

        items.append(Listing(
            site=SITE,
            external_id=external_id,
            url=f"https://4zida.rs{href}",
            transaction_type=transaction_type,
            property_type="apartment",
            city=city,
            neighborhood=neighborhood,
            area_m2=area,
            rooms=float(rooms) if rooms is not None else None,
            price_eur=price,
            publisher=publisher,
            publisher_type=publisher_type,
            title=title,
        ))

    return items


def _slug_to_neighborhood(slug: str) -> str | None:
    """'cubura-vracar-beograd' → 'Čubura'  (prvi token, capitalize, drop 'opstina' marker)."""
    if not slug:
        return None
    parts = slug.split("-")
    if not parts:
        return None
    first = parts[0].strip()
    if not first or first in ("beograd", "novi", "grad", "opstina"):
        # fallback: drugi segment
        for p in parts[1:]:
            if p not in ("beograd", "opstina", "grad", "sve"):
                return p.capitalize()
        return None
    return first.capitalize()


def _extract_price(card, text: str, transaction_type: str) -> int | None:
    lo, hi = SALE_PRICE_RANGE if transaction_type == "sale" else RENT_PRICE_RANGE

    for el in card.select("[class*='price'], [class*='Price']"):
        m = re.search(r"(\d[\d\.\s]{2,})\s*€", el.get_text())
        if m:
            val = int(re.sub(r"[\.\s]", "", m.group(1)))
            if lo <= val <= hi:
                return val

    for match in re.finditer(r"(\d[\d\.\s]{2,})\s*€", text):
        val = int(re.sub(r"[\.\s]", "", match.group(1)))
        if lo <= val <= hi:
            return val
    return None


def _extract_area(text: str) -> float | None:
    m = re.search(r"(\d+(?:[\.,]\d+)?)\s*m²", text) or re.search(r"(\d+(?:[\.,]\d+)?)\s*m2", text)
    if m:
        try:
            v = float(m.group(1).replace(",", "."))
            if 10 <= v <= 1000:
                return v
        except ValueError:
            pass
    return None


def _extract_rooms(text: str) -> float | None:
    m = re.search(r"(\d+(?:[\.,]\d+)?)\s*sob", text, re.IGNORECASE)
    if m:
        try:
            return float(m.group(1).replace(",", "."))
        except ValueError:
            pass

    word_map = {
        "garsonjer": 0.5,
        "jednosoban": 1, "jednoiposoban": 1.5,
        "dvosoban": 2, "dvoiposoban": 2.5,
        "trosoban": 3, "troiposoban": 3.5,
        "četvorosoban": 4, "cetvorosoban": 4,
    }
    low = text.lower()
    for word, val in word_map.items():
        if word in low:
            return float(val)
    return None


def _extract_neighborhood(card, title: str | None) -> str | None:
    for sel in ["[class*='location']", "[class*='Location']", "[class*='address']"]:
        el = card.select_one(sel)
        if el:
            txt = el.get_text(strip=True)
            if txt:
                parts = [p.strip() for p in txt.split(",")]
                if len(parts) >= 2:
                    return parts[1]
                return parts[0]
    if title:
        parts = [p.strip() for p in title.split(",")]
        for p in parts[1:3]:
            if p and not re.search(r"\d", p):
                return p
    return None


def _extract_publisher(card, text: str) -> tuple[str | None, str | None]:
    for sel in ["[class*='publisher']", "[class*='agency']", "[class*='advertiser']"]:
        el = card.select_one(sel)
        if el:
            name = el.get_text(strip=True)
            if name:
                return name, "agency"

    if re.search(r"vlasnik|privatni|agencija ne", text, re.IGNORECASE):
        return "Privatni", "private"
    return None, "unknown"


# Rich mock fallback
_MOCK_NEIGHBORHOODS = [
    ("Novi Beograd", 42), ("Savski venac", 26), ("Palilula", 21),
    ("Vračar", 18), ("Voždovac", 15), ("Zvezdara", 12),
    ("Stari grad", 8), ("Zemun", 7),
]


def _mock(url: str, transaction_type: str) -> MarketSnapshot:
    import random
    rnd = random.Random(43)
    listings: list[Listing] = []
    is_sale = transaction_type == "sale"

    for nb, count in _MOCK_NEIGHBORHOODS:
        for i in range(min(count, 15)):
            area = rnd.choice([35, 45, 55, 65, 75, 90, 110])
            if is_sale:
                price_m2 = rnd.randint(1900, 3400)
                price = price_m2 * area
            else:
                price_m2 = rnd.randint(7, 15)
                price = price_m2 * area
            listings.append(Listing(
                site=SITE,
                external_id=f"mock-4zida-{nb}-{i}-{transaction_type}",
                url=f"{url}/mock/{nb}/{i}",
                transaction_type=transaction_type,
                neighborhood=nb,
                area_m2=area,
                rooms=rnd.choice([1, 1.5, 2, 2.5, 3, 3.5, 4]),
                price_eur=price,
                publisher=rnd.choice(["Agencija D", "Agencija E", "Privatni", "Agencija F"]),
                publisher_type=rnd.choice(["agency", "private"]),
                title=f"Stan, {nb}, {area}m²",
            ))

    agg = aggregate_from_listings(listings)
    total = 2341 if is_sale else 845
    return MarketSnapshot(
        site=SITE,
        url=url,
        transaction_type=transaction_type,
        total_listings=total,
        new_this_week=0,
        listings=listings,
        is_mock=True,
        **agg,
    )
