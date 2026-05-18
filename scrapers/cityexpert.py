import time
from .base import Listing, MarketSnapshot, aggregate_from_listings, get_session, fetch_with_retry

SITE = "CityExpert"

API_BASE = "https://cityexpert.rs/api/Search/"
PUBLIC_URLS = {
    "sale": "https://cityexpert.rs/prodaja/{city}",
    "rent": "https://cityexpert.rs/izdavanje/{city}",
}

RENT_OR_SALE = {"sale": "S", "rent": "R"}
RESULTS_PER_PAGE = 24

SALE_PRICE_RANGE = (10_000, 5_000_000)
RENT_PRICE_RANGE = (50, 10_000)


def scrape(city: str = "beograd", transaction_type: str = "sale", max_pages: int = 5) -> MarketSnapshot:
    public_url = PUBLIC_URLS.get(transaction_type, PUBLIC_URLS["sale"]).format(city=city)
    flag = RENT_OR_SALE.get(transaction_type, "S")
    listings: list[Listing] = []
    total_from_api: int | None = None
    session = get_session(referer=public_url)

    try:
        for page in range(1, max_pages + 1):
            api_url = (
                f"{API_BASE}?cityName={city}&ptId=1&rentOrSale={flag}"
                f"&currentPage={page}&resultsPerPage={RESULTS_PER_PAGE}"
            )
            resp = fetch_with_retry(session, api_url, referer=public_url)
            if resp is None:
                if page == 1:
                    raise RuntimeError("API ne odgovara")
                break
            data = resp.json()

            if page == 1:
                total_from_api = data.get("totalCount", 0)

            results = data.get("result", []) or data.get("results", [])
            if not results:
                break

            for raw in results:
                listing = _parse_api_result(raw, transaction_type, city)
                if listing:
                    listings.append(listing)

            time.sleep(1.0)  # API je već laka — kratko pauziramo

        if not listings:
            return _mock(public_url, transaction_type)

        agg = aggregate_from_listings(listings)
        return MarketSnapshot(
            site=SITE,
            url=public_url,
            transaction_type=transaction_type,
            city=city,
            total_listings=total_from_api or len(listings),
            new_this_week=0,
            listings=listings,
            is_mock=False,
            **agg,
        )
    except Exception as e:
        print(f"[CityExpert] API failed: {type(e).__name__}: {e}")
        return _mock(public_url, transaction_type)


def _parse_api_result(raw: dict, transaction_type: str, city: str) -> Listing | None:
    """CityExpert JSON polja variraju po verzijama API-ja — defensive lookup."""
    lo, hi = SALE_PRICE_RANGE if transaction_type == "sale" else RENT_PRICE_RANGE

    # external_id
    ext = raw.get("propId") or raw.get("id") or raw.get("uniqueID")
    if ext is None:
        return None
    external_id = str(ext)

    # cena
    price_raw = raw.get("price") or raw.get("totalPrice")
    price = None
    try:
        if price_raw is not None:
            price = int(float(price_raw))
            if not (lo <= price <= hi):
                price = None
    except (TypeError, ValueError):
        price = None

    # površina
    area_raw = raw.get("size") or raw.get("area") or raw.get("squareMeters")
    try:
        area = float(area_raw) if area_raw is not None else None
        if area is not None and not (10 <= area <= 1000):
            area = None
    except (TypeError, ValueError):
        area = None

    # sobe
    rooms_raw = raw.get("structure") or raw.get("rooms") or raw.get("numberOfRooms")
    try:
        rooms = float(rooms_raw) if rooms_raw is not None else None
    except (TypeError, ValueError):
        rooms = None

    # kvart
    neighborhood = (
        raw.get("municipality") or raw.get("neighborhood")
        or raw.get("part") or raw.get("location")
    )

    # listed_at
    listed_at = raw.get("listingDate") or raw.get("createDate") or raw.get("date")
    if listed_at and isinstance(listed_at, str):
        listed_at = listed_at[:10]  # uzmi samo YYYY-MM-DD deo

    # URL — CityExpert ima propId u URL-u
    url = raw.get("url") or f"https://cityexpert.rs/{'prodaja' if transaction_type == 'sale' else 'izdavanje'}/{external_id}"

    # Publisher: CityExpert je sam agencija (svi oglasi su njihovi)
    publisher = "CityExpert"
    publisher_type = "agency"

    title = raw.get("title") or raw.get("name")

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
        listed_at=listed_at,
        publisher=publisher,
        publisher_type=publisher_type,
        title=title,
    )


_MOCK_NEIGHBORHOODS = [
    ("Vračar", 28), ("Savski venac", 22), ("Stari grad", 17),
    ("Novi Beograd", 14), ("Voždovac", 9), ("Palilula", 6),
]


def _mock(url: str, transaction_type: str) -> MarketSnapshot:
    import random
    rnd = random.Random(45)
    listings: list[Listing] = []
    is_sale = transaction_type == "sale"

    for nb, count in _MOCK_NEIGHBORHOODS:
        for i in range(min(count, 12)):
            area = rnd.choice([35, 45, 55, 65, 75, 90, 110, 130])
            if is_sale:
                price_m2 = rnd.randint(2100, 3800)
                price = price_m2 * area
            else:
                price_m2 = rnd.randint(8, 17)
                price = price_m2 * area
            listings.append(Listing(
                site=SITE,
                external_id=f"mock-ce-{nb}-{i}-{transaction_type}",
                url=f"{url}/mock/{nb}/{i}",
                transaction_type=transaction_type,
                neighborhood=nb,
                area_m2=area,
                rooms=rnd.choice([1, 1.5, 2, 2.5, 3, 3.5, 4]),
                price_eur=price,
                publisher="CityExpert",
                publisher_type="agency",
                title=f"Stan, {nb}, {area}m²",
            ))

    agg = aggregate_from_listings(listings)
    total = 876 if is_sale else 342
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
