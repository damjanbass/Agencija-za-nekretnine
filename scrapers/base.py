from dataclasses import dataclass, field
from datetime import date
import requests


HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/124.0.0.0 Safari/537.36"
    ),
    "Accept-Language": "sr-RS,sr;q=0.9,en-US;q=0.8",
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
}


@dataclass
class MarketSnapshot:
    site:              str
    url:               str
    total_listings:    int
    avg_price_eur_m2:  int
    price_min_eur:     int
    price_max_eur:     int
    new_this_week:     int
    top_neighborhoods: list[str] = field(default_factory=list)
    scraped_at:        str = field(default_factory=lambda: date.today().isoformat())
    is_mock:           bool = False

    def to_dict(self) -> dict:
        return self.__dict__.copy()


def get_session() -> requests.Session:
    s = requests.Session()
    s.headers.update(HEADERS)
    s.timeout = 10
    return s
