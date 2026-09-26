import re
import requests
from bs4 import BeautifulSoup
from search_poc.models import Vehicle

URL = "https://bmwpremiumselection.bmw.pt/serie-3/330e-touring/"
HEADERS = {
    "User-Agent": "Mozilla/5.0 (compatible; DEBE-Search-PoC/0.1; +https://debe-auto.onrender.com)",
    "Accept-Language": "pt-PT,pt;q=0.9,en;q=0.7",
}


def _num(text):
    if not text:
        return None
    return int(re.sub(r"\D", "", text))


def fetch_bmw_330e_touring(timeout=15):
    r = requests.get(URL, headers=HEADERS, timeout=timeout)
    r.raise_for_status()
    soup = BeautifulSoup(r.text, "html.parser")
    text = soup.get_text("\n", strip=True)

    # BMW's public inventory page renders each result with km, year, price and dealer.
    # This parser is deliberately narrow for the PoC; production will use the
    # underlying structured endpoint if/when confirmed.
    pattern = re.compile(
        r"BMW\s+Série\s*3\s*330e\s+Touring.*?"
        r"(?P<km>\d{1,3}(?:\.\d{3})*)\s*km.*?"
        r"(?P<year>20\d{2}).*?"
        r"Preço:\s*(?P<price>[\d\.]+,\d{2})\s*€.*?"
        r"Veículo\s+oferecido\s+pela\s+(?P<dealer>[^\n]+)",
        re.I | re.S,
    )

    out = []
    for i, m in enumerate(pattern.finditer(text), start=1):
        km = _num(m.group("km"))
        price = float(m.group("price").replace(".", "").replace(",", "."))
        dealer = m.group("dealer").strip()
        out.append(Vehicle(
            source="bmw_premium_selection",
            source_id=f"bmwps-330e-{i}-{km}",
            url=URL,
            make="BMW",
            model="Série 3",
            variant="330e",
            body="Touring",
            year=int(m.group("year")),
            mileage_km=km,
            price_eur=price,
            dealer=dealer,
            fuel="Híbrido Plug-In",
            power_cv=292,
        ))
    return out
