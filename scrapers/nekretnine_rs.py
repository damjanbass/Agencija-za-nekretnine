import json
import re
import time
from bs4 import BeautifulSoup
from .base import Listing, MarketSnapshot, aggregate_from_listings, fetch_html

SITE = "Nekretnine.rs"

# Nekretnine.rs URL format koristi path-segment-style filtere:
#   /stambeni-objekti/stanovi/<filter1>/<filter2>/.../lista/po-stranici/N/
# Stari format izdavanje-prodaja=prodaja vraća 404 — koristimo pravi format
# 'prodaja' / 'izdavanje' kao prvi segment posle 'stanovi/'.
URLS = {
    "sale": "https://www.nekretnine.rs/stambeni-objekti/stanovi/prodaja/grad-{city}/lista/po-stranici/20/",
    "rent": "https://www.nekretnine.rs/stambeni-objekti/stanovi/izdavanje/grad-{city}/lista/po-stranici/20/",
}
# Fallback URL-ovi ako primarni i dalje vrati 404 — proba bez grad filtera
URLS_FALLBACK = {
    "sale": "https://www.nekretnine.rs/stambeni-objekti/stanovi/lista/po-stranici/20/",
    "rent": "https://www.nekretnine.rs/stambeni-objekti/stanovi/izdavanje/lista/po-stranici/20/",
}

SALE_PRICE_RANGE = (10_000, 5_000_000)
RENT_PRICE_RANGE = (50, 10_000)


def scrape(city: str = "beograd", transaction_type: str = "sale", max_pages: int = 5) -> MarketSnapshot:
    primary_url  = URLS.get(transaction_type, URLS["sale"]).format(city=city)
    fallback_url = URLS_FALLBACK.get(transaction_type, URLS_FALLBACK["sale"])
    homepage     = "https://www.nekretnine.rs/"
    listings: list[Listing] = []
    total_from_site: int | None = None

    try:
        # Probaj primary URL; ako fail → fallback bez grad filtera
        base_url = primary_url
        first_html = fetch_html(
            base_url,
            referer=homepage,
            prefer_browser=False,
            wait_for_selector=".offer, .listing, article.advert",
        )
        if first_html is None:
            print(f"    [Nekretnine.rs] primary URL nije uspeo, probam fallback bez grad-filtera")
            base_url = fallback_url
            first_html = fetch_html(
                base_url,
                referer=homepage,
                prefer_browser=False,
                wait_for_selector=".offer, .listing, article.advert",
            )
        if first_html is None:
            raise RuntimeError("nijedna varijanta URL-a nije uspela")

        prev_url = homepage
        for page in range(1, max_pages + 1):
            if page == 1:
                html = first_html
                page_url = base_url
            else:
                # Nekretnine.rs paginacija: /stranica/N/ kao path segment na kraju
                page_url = f"{base_url}stranica/{page}/"
                html = fetch_html(
                    page_url,
                    referer=prev_url,
                    prefer_browser=False,
                    wait_for_selector=".offer, .listing, article.advert",
                )
                if html is None:
                    break
            soup = BeautifulSoup(html, "html.parser")

            if page == 1:
                total_from_site = _parse_total(soup)

            page_listings = _parse_listings(soup, transaction_type, city)
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
        print(f"[Nekretnine.rs] Parsing failed: {type(e).__name__}: {e}")
        return _mock(base_url, transaction_type)


def _parse_total(soup: BeautifulSoup) -> int:
    for sel in [".number-of-results", ".results-number", "h1 span", ".total-results"]:
        el = soup.select_one(sel)
        if el:
            m = re.search(r"[\d\.]+", el.get_text())
            if m:
                return int(m.group().replace(".", ""))
    return 0


def _parse_listings(soup: BeautifulSoup, transaction_type: str, city: str) -> list[Listing]:
    """
    Nekretnine.rs SSR-renderuje listinge sa Google Analytics 4 dataLayer JSON-om
    u onclick atributu svake offer-title <a> taga. Taj JSON je najpouzdaniji izvor —
    sadrži price, currency, item_category (Prodaja/Izdavanje), item_category2
    (rooms info), item_category3 (location), item_category4 (area).
    """
    items: list[Listing] = []
    seen_ids: set[str] = set()

    # Primarno: dataLayer JSON pristup (precizan, otporan na class-name drift)
    anchors = soup.select("a[onclick*='analyticsSelectList']")
    for a in anchors:
        listing = _parse_from_datalayer(a, transaction_type, city)
        if listing and listing.external_id not in seen_ids:
            seen_ids.add(listing.external_id)
            items.append(listing)

    # Fallback: CSS selektori za slučaj da dataLayer izlazi iz upotrebe
    if not items:
        for card in soup.select("a[href*='/stambeni-objekti/'], h2.offer-title a"):
            listing = _parse_single_card(card, transaction_type, city)
            if listing and listing.external_id not in seen_ids:
                seen_ids.add(listing.external_id)
                items.append(listing)

    return items


_DATALAYER_RE = re.compile(r"analyticsSelectList_\w+\s*=\s*(\[.*?\]);", re.DOTALL)
_ROOMS_FROM_CAT_RE = re.compile(
    r"(garsonjer|jednosoban|jednoiposoban|dvosoban|dvoiposoban|"
    r"trosoban|troiposoban|četvorosoban|cetvorosoban|petosoban)",
    re.IGNORECASE,
)
_ROOMS_WORD_MAP = {
    "garsonjer": 0.5,
    "jednosoban": 1, "jednoiposoban": 1.5,
    "dvosoban": 2, "dvoiposoban": 2.5,
    "trosoban": 3, "troiposoban": 3.5,
    "četvorosoban": 4, "cetvorosoban": 4,
    "petosoban": 5,
}


def _parse_from_datalayer(a, transaction_type: str, city: str) -> Listing | None:
    onclick = a.get("onclick") or ""
    m = _DATALAYER_RE.search(onclick)
    if not m:
        return None
    try:
        # onclick je u atributu pa su navodnici escape-ovani (`&quot;` od BS-a vraćeni)
        data = json.loads(m.group(1))
    except (ValueError, TypeError):
        return None
    if not data or not isinstance(data, list):
        return None
    raw = data[0]

    external_id = str(raw.get("item_id") or "")
    if not external_id:
        return None

    href = a.get("href") or ""
    url = href if href.startswith("http") else f"https://www.nekretnine.rs{href}"

    # Tip tranzakcije iz item_category — proveri da li se slaže sa traženim
    cat_txn = (raw.get("item_category") or "").lower()
    expected = "prodaja" if transaction_type == "sale" else "izdavanje"
    if expected not in cat_txn:
        return None

    # Cena
    try:
        price = int(float(raw.get("price")))
        lo, hi = (SALE_PRICE_RANGE if transaction_type == "sale" else RENT_PRICE_RANGE)
        if not (lo <= price <= hi):
            price = None
    except (TypeError, ValueError):
        price = None

    # Površina (item_category4 je m²)
    try:
        area = float(raw.get("item_category4"))
        if not (10 <= area <= 1000):
            area = None
    except (TypeError, ValueError):
        area = None

    # Sobe iz item_category2 (npr. "Stan u zgradi, Trosoban stan, Stanovi, ...")
    rooms = None
    cat2 = (raw.get("item_category2") or "").lower()
    rm = _ROOMS_FROM_CAT_RE.search(cat2)
    if rm:
        rooms = float(_ROOMS_WORD_MAP[rm.group(1).lower()])

    # Kvart iz item_category3 (npr. "Novi Beograd Blok 62, Novi Beograd (sve podlokacije), Beograd, ...")
    neighborhood = None
    cat3 = raw.get("item_category3") or ""
    if cat3:
        parts = [p.strip() for p in cat3.split(",")]
        if parts:
            # Uzmi širi kvart (drugi deo) ili prvi ako nema više
            for cand in (parts[1] if len(parts) > 1 else None, parts[0]):
                if cand and not re.search(r"(beograd|srbija|grad)$", cand, re.IGNORECASE):
                    neighborhood = re.sub(r"\s*\(.*?\)\s*$", "", cand).strip()
                    if neighborhood:
                        break

    title = raw.get("item_name")

    return Listing(
        site=SITE,
        external_id=external_id,
        url=url,
        transaction_type=transaction_type,
        property_type="apartment",
        city=city,
        neighborhood=neighborhood,
        area_m2=area,
        rooms=rooms,
        price_eur=price,
        publisher=None,                # Nekretnine.rs ne izlaže agency_name u dataLayer-u
        publisher_type="unknown",
        title=title,
    )


def _parse_single_card(card, transaction_type: str, city: str) -> Listing | None:
    a = card if card.name == "a" else card.select_one("a[href*='/stambeni-objekti/']")
    if not a:
        return None
    href = a.get("href") or ""
    if not href or "/stambeni-objekti/" not in href:
        return None
    url = href if href.startswith("http") else f"https://www.nekretnine.rs{href}"

    # Nekretnine.rs ID: /detaljno/<slug>/<NUM>/
    m = re.search(r"/(\d{5,})/?(?:\?|$)", url) or re.search(r"/detaljno/([^/?#]+)", url)
    if not m:
        return None
    external_id = m.group(1)

    text = card.get_text(" ", strip=True)
    title_el = card.select_one("h2, h3, [class*='title'], .offer-title")
    title = title_el.get_text(strip=True) if title_el else None

    price        = _extract_price(card, text, transaction_type)
    area         = _extract_area(text)
    rooms        = _extract_rooms(text)
    neighborhood = _extract_neighborhood(card, title)
    publisher, publisher_type = _extract_publisher(card, text)

    return Listing(
        site=SITE,
        external_id=external_id,
        url=url,
        transaction_type=transaction_type,
        property_type="apartment",
        city=city,
        neighborhood=neighborhood,
        area_m2=area,
        rooms=rooms,
        price_eur=price,
        publisher=publisher,
        publisher_type=publisher_type,
        title=title,
    )


def _extract_price(card, text: str, transaction_type: str) -> int | None:
    lo, hi = SALE_PRICE_RANGE if transaction_type == "sale" else RENT_PRICE_RANGE

    for el in card.select(".price, .cena, [class*='price']"):
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
    for sel in [".location", ".lokacija", "[class*='location']", "[class*='address']"]:
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
    for sel in [".agency-name", ".publisher", "[class*='agency']", "[class*='advertiser']"]:
        el = card.select_one(sel)
        if el:
            name = el.get_text(strip=True)
            if name:
                return name, "agency"

    if re.search(r"vlasnik|privatni|agencija ne", text, re.IGNORECASE):
        return "Privatni", "private"
    return None, "unknown"


_MOCK_NEIGHBORHOODS = [
    ("Novi Beograd", 51), ("Zemun", 28), ("Čukarica", 23),
    ("Voždovac", 19), ("Vračar", 15), ("Palilula", 12),
    ("Zvezdara", 9), ("Stari grad", 6),
]


def _mock(url: str, transaction_type: str) -> MarketSnapshot:
    import random
    rnd = random.Random(44)
    listings: list[Listing] = []
    is_sale = transaction_type == "sale"

    for nb, count in _MOCK_NEIGHBORHOODS:
        for i in range(min(count, 15)):
            area = rnd.choice([35, 45, 55, 65, 75, 90, 110])
            if is_sale:
                price_m2 = rnd.randint(1700, 3100)
                price = price_m2 * area
            else:
                price_m2 = rnd.randint(6, 13)
                price = price_m2 * area
            listings.append(Listing(
                site=SITE,
                external_id=f"mock-nekrs-{nb}-{i}-{transaction_type}",
                url=f"{url}/mock/{nb}/{i}",
                transaction_type=transaction_type,
                neighborhood=nb,
                area_m2=area,
                rooms=rnd.choice([1, 1.5, 2, 2.5, 3, 3.5, 4]),
                price_eur=price,
                publisher=rnd.choice(["Agencija G", "Agencija H", "Privatni", "Agencija I"]),
                publisher_type=rnd.choice(["agency", "private"]),
                title=f"Stan, {nb}, {area}m²",
            ))

    agg = aggregate_from_listings(listings)
    total = 3107 if is_sale else 1024
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
