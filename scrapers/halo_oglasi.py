import re
import time
from bs4 import BeautifulSoup
from .base import Listing, MarketSnapshot, aggregate_from_listings, fetch_html

SITE = "Halo oglasi"

URLS = {
    "sale": "https://www.halooglasi.com/nekretnine/prodaja-stanova/{city}",
    "rent": "https://www.halooglasi.com/nekretnine/izdavanje-stanova/{city}",
}

# Halo oglasi paginacija: ?page=2
PAGE_PARAM = "page"

# Razuman price range za sanity filter (€)
SALE_PRICE_RANGE = (10_000, 5_000_000)
RENT_PRICE_RANGE = (50, 10_000)


def scrape(city: str = "beograd", transaction_type: str = "sale", max_pages: int = 5) -> MarketSnapshot:
    """
    Skrejpuje Halo oglase za prodaju ili zakup stanova u zadanom gradu.
    Vraća MarketSnapshot sa pojedinačnim listinzima u `listings` polju.

    Ako parsing ne uspe (struktura sajta se menjala, network, blok),
    vraća rich mock snapshot sa is_mock=True.
    """
    base_url = URLS.get(transaction_type, URLS["sale"]).format(city=city)
    listings: list[Listing] = []
    total_from_site: int | None = None
    homepage = "https://www.halooglasi.com/"

    try:
        prev_url = homepage
        for page in range(1, max_pages + 1):
            page_url = base_url if page == 1 else f"{base_url}?{PAGE_PARAM}={page}"
            # Cloudflare WAF blokira requests — prefer_browser
            html = fetch_html(
                page_url,
                referer=prev_url,
                prefer_browser=True,
                wait_for_selector=".product-item, .product-list-item, article.product",
            )
            if html is None:
                if page == 1:
                    raise RuntimeError("nijedna strana nije fetch-ovana")
                break
            soup = BeautifulSoup(html, "html.parser")

            if page == 1:
                total_from_site = _parse_total(soup)

            page_listings = _parse_listings(soup, transaction_type, city)
            if not page_listings:
                break  # nema više rezultata
            listings.extend(page_listings)
            prev_url = page_url

            time.sleep(1.5)  # rate limiting — poštujemo sajt

        if not listings:
            return _mock(base_url, transaction_type)

        agg = aggregate_from_listings(listings)
        return MarketSnapshot(
            site=SITE,
            url=base_url,
            transaction_type=transaction_type,
            city=city,
            total_listings=total_from_site or len(listings),
            new_this_week=0,  # popunjava se SQL upitom iz market_listings_sample.listed_at
            listings=listings,
            is_mock=False,
            **agg,
        )
    except Exception as e:
        print(f"[Halo oglasi] Parsing failed: {type(e).__name__}: {e}")
        return _mock(base_url, transaction_type)


# ─────────────────────────────────────────────────────────────────────────────
# Parsing helpers
# ─────────────────────────────────────────────────────────────────────────────

def _parse_total(soup: BeautifulSoup) -> int:
    """Ukupan broj rezultata pretrage (iznad listing grid-a)."""
    for sel in [".total-count", ".broj-oglasa", "h1 strong", ".product-list-title"]:
        el = soup.select_one(sel)
        if el:
            m = re.search(r"[\d\.]+", el.get_text())
            if m:
                return int(m.group().replace(".", ""))
    return 0


def _parse_listings(soup: BeautifulSoup, transaction_type: str, city: str) -> list[Listing]:
    """
    Izvlači pojedinačne oglase iz product grid-a.
    Halo oglasi koristi raznorodne klase — pokušavamo više selektora.
    """
    items: list[Listing] = []
    # Listing kartice: probaj raznorodne selektore
    cards = soup.select(".product-item, .product-list-item, [class*='listing-item'], article.product")

    for card in cards:
        listing = _parse_single_card(card, transaction_type, city)
        if listing:
            items.append(listing)

    return items


def _parse_single_card(card, transaction_type: str, city: str) -> Listing | None:
    """Parse jedne listing kartice. Vraća None ako kartica nije validan oglas."""
    # URL i external_id
    a = card.select_one("a[href*='/oglas/'], a.product-title, h3 a")
    if not a:
        return None
    href = a.get("href") or ""
    if not href:
        return None
    url = href if href.startswith("http") else f"https://www.halooglasi.com{href}"

    # external_id: Halo oglasi koristi numerički ID na kraju URL-a, npr. .../5425675412345
    m = re.search(r"/(\d{10,})(?:/|$|\?)", url)
    if not m:
        return None
    external_id = m.group(1)

    text = card.get_text(" ", strip=True)
    title = a.get_text(strip=True) or None

    # Cena
    price = _extract_price(card, text, transaction_type)

    # Površina (m²)
    area = _extract_area(text)

    # Sobe
    rooms = _extract_rooms(text)

    # Kvart — iz lokacijskog linka ili dela title-a
    neighborhood = _extract_neighborhood(card, title)

    # Publisher (agencija ili privatni oglas)
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

    # Probaj dedicirane price elemente
    for el in card.select(".price-box, .central-feature-value, [class*='price']"):
        m = re.search(r"(\d[\d\.\s]{2,})\s*€", el.get_text())
        if m:
            val = int(re.sub(r"[\.\s]", "", m.group(1)))
            if lo <= val <= hi:
                return val

    # Fallback: regex po celom textu (€)
    for match in re.finditer(r"(\d[\d\.\s]{2,})\s*€", text):
        val = int(re.sub(r"[\.\s]", "", match.group(1)))
        if lo <= val <= hi:
            return val
    return None


def _extract_area(text: str) -> float | None:
    m = re.search(r"(\d+(?:[\.,]\d+)?)\s*m²", text)
    if m:
        try:
            v = float(m.group(1).replace(",", "."))
            if 10 <= v <= 1000:
                return v
        except ValueError:
            pass
    return None


def _extract_rooms(text: str) -> float | None:
    # "2.5 sobe", "trosoban", "dvosoban", "garsonjera"
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
    # Probaj dedicirane lokacijske elemente
    for sel in [".location", ".product-location", "[class*='lokacija']", "[class*='address']"]:
        el = card.select_one(sel)
        if el:
            txt = el.get_text(strip=True)
            if txt:
                # Halo lokacija format: "Beograd, Vračar, Centar" — uzmi 2. deo
                parts = [p.strip() for p in txt.split(",")]
                if len(parts) >= 2:
                    return parts[1]
                return parts[0]
    # Fallback: pokušaj iz title-a (npr. "Stan, Vračar, 75m²")
    if title:
        parts = [p.strip() for p in title.split(",")]
        for p in parts[1:3]:
            if p and not re.search(r"\d", p):
                return p
    return None


def _extract_publisher(card, text: str) -> tuple[str | None, str | None]:
    # Halo oglasi obeležava agencije/privatne oglasivače u dediciranim badge-ovima
    for sel in [".publisher-name", ".agency-name", "[class*='publisher']", "[class*='agency']"]:
        el = card.select_one(sel)
        if el:
            name = el.get_text(strip=True)
            if name:
                return name, "agency"

    if re.search(r"vlasnik|privatni|agencija ne", text, re.IGNORECASE):
        return "Privatni", "private"
    return None, "unknown"


# ─────────────────────────────────────────────────────────────────────────────
# Mock fallback (rich — sa pojedinačnim oglasima za downstream testing)
# ─────────────────────────────────────────────────────────────────────────────

_MOCK_NEIGHBORHOODS = [
    ("Novi Beograd", 38), ("Vračar", 24), ("Zvezdara", 19),
    ("Voždovac", 16), ("Palilula", 13), ("Čukarica", 11),
    ("Savski venac", 9), ("Stari grad", 7),
]


def _mock(url: str, transaction_type: str) -> MarketSnapshot:
    """Rich mock — generiše pojedinačne oglase tako da downstream (DB, benchmark) ima podatke."""
    import random
    rnd = random.Random(42)  # deterministički seed za stabilne testove

    listings: list[Listing] = []
    is_sale = transaction_type == "sale"

    for nb, count in _MOCK_NEIGHBORHOODS:
        for i in range(min(count, 15)):  # cap za mock veličinu
            area = rnd.choice([35, 45, 55, 65, 75, 90, 110])
            if is_sale:
                price_m2 = rnd.randint(1800, 3200)
                price = price_m2 * area
            else:
                price_m2 = rnd.randint(6, 14)
                price = price_m2 * area
            listings.append(Listing(
                site=SITE,
                external_id=f"mock-halo-{nb}-{i}-{transaction_type}",
                url=f"{url}/mock/{nb}/{i}",
                transaction_type=transaction_type,
                neighborhood=nb,
                area_m2=area,
                rooms=rnd.choice([1, 1.5, 2, 2.5, 3, 3.5, 4]),
                price_eur=price,
                publisher=rnd.choice(["Agencija A", "Agencija B", "Privatni", "Agencija C", "Privatni"]),
                publisher_type=rnd.choice(["agency", "private"]),
                title=f"Stan, {nb}, {area}m²",
            ))

    agg = aggregate_from_listings(listings)
    total = 1842 if is_sale else 612
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
