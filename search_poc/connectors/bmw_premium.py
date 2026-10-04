import re
import requests
from bs4 import BeautifulSoup
from urllib.parse import urljoin
from search_poc.models import Vehicle

URL = "https://bmwpremiumselection.bmw.pt/carros-usados/bmw-serie-3/330e-touring/"
HEADERS = {
    "User-Agent": "Mozilla/5.0 (compatible; DEBE-Search-Beta/0.2)",
    "Accept-Language": "pt-PT,pt;q=0.9,en;q=0.7",
}


def _num(text):
    if not text:
        return None
    digits = re.sub(r"\D", "", text)
    return int(digits) if digits else None


def _money(text):
    if not text:
        return None
    try:
        return float(text.replace(" ", "").replace(".", "").replace(",", "."))
    except Exception:
        return None


def _card_text(anchor):
    """Find the smallest ancestor containing the complete inventory-card facts."""
    node = anchor
    best = ""
    for _ in range(10):
        node = getattr(node, "parent", None)
        if node is None:
            break
        txt = node.get_text("\n", strip=True)
        if len(txt) > 12000:
            break
        if "km" in txt and re.search(r"Pre[cç]o", txt, re.I) and "Veículo oferecido" in txt:
            best = txt
            # First/smallest matching ancestor is the correct card in current BMW markup.
            return best
    return best


def fetch_bmw_330e_touring(timeout=15):
    r = requests.get(URL, headers=HEADERS, timeout=timeout)
    r.raise_for_status()
    soup = BeautifulSoup(r.text, "html.parser")

    # Every vehicle has its own public offer URL ending in the numeric offer ID.
    # Collect those URLs from the inventory page, de-duplicating image/title links.
    offers = []
    seen = set()
    for a in soup.find_all("a", href=True):
        href = a.get("href", "")
        if "/bmw-serie-3-330e-touring/" not in href:
            continue
        full = urljoin(URL, href)
        m = re.search(r"/bmw-serie-3-330e-touring/(\d+)/?$", full)
        if not m or full in seen:
            continue
        seen.add(full)
        offers.append((a, full, m.group(1)))

    out = []
    for a, vehicle_url, offer_id in offers:
        text = _card_text(a)
        if not text:
            continue

        km_m = re.search(r"(\d{1,3}(?:[\.\s]\d{3})*)\s*km\b", text, re.I)
        year_m = re.search(r"\b(20\d{2})\b", text)
        price_m = re.search(r"Pre[cç]o:?\s*([\d\.\s]+,\d{2})\s*€", text, re.I)
        dealer_m = re.search(r"Veículo\s+oferecido\s+pela\s+([^\n]+)", text, re.I)

        if not (km_m and year_m and price_m and dealer_m):
            continue

        km = _num(km_m.group(1))
        price = _money(price_m.group(1))
        dealer = dealer_m.group(1).strip()

        # BMW sometimes publishes a higher comparison/retoma amount directly after
        # the cash price. Keep it distinct from the vehicle's new-car MSRP.
        comparison_m = re.search(
            r"Pre[cç]o:?\s*[\d\.\s]+,\d{2}\s*€\s*([\d\.\s]+,\d{2})\s*€\s*Desconto\s+direto",
            text, re.I | re.S
        )
        comparison = _money(comparison_m.group(1)) if comparison_m else None
        discount = round(comparison - price, 2) if comparison and price and comparison > price else None
        # BMW BPS sometimes shows the lower amount only with a trade-in campaign.
        # Do not expose that as the unconditional asking price.
        conditional = bool(discount and re.search(r"retoma|trade[- ]?in", text, re.I))
        asking_price = comparison if conditional else price

        out.append(Vehicle(
            source="bmw_premium_selection",
            source_id=offer_id,
            url=vehicle_url,
            make="BMW",
            model="Série 3",
            variant="330e",
            body="Touring",
            year=int(year_m.group(1)),
            mileage_km=km,
            price_eur=asking_price,
            dealer=dealer,
            fuel="Híbrido Plug-In",
            power_cv=292,
            condition="used_certified",
            list_price_eur=comparison,
            discount_eur=discount,
            discount_pct=round(discount / comparison * 100, 1) if discount and comparison else None,
            is_official_stock=True,
            conditional_price_eur=price if conditional else None,
            price_condition="retoma" if conditional else "",
        ))

    # Fallback for markup changes: parse the page text into vehicle blocks. This
    # keeps the beta useful but deliberately does NOT invent individual URLs.
    if not out:
        text = soup.get_text("\n", strip=True)
        pattern = re.compile(
            r"BMW\s+Série\s*3\s*330e\s+Touring.*?"
            r"(?P<km>\d{1,3}(?:[\.\s]\d{3})*)\s*km.*?"
            r"(?P<year>20\d{2}).*?"
            r"Pre[cç]o:?\s*(?P<price>[\d\.\s]+,\d{2})\s*€.*?"
            r"Veículo\s+oferecido\s+pela\s+(?P<dealer>[^\n]+)",
            re.I | re.S,
        )
        for i, m in enumerate(pattern.finditer(text), start=1):
            out.append(Vehicle(
                source="bmw_premium_selection",
                source_id=f"fallback-{i}-{_num(m.group('km'))}",
                url=URL,
                make="BMW", model="Série 3", variant="330e", body="Touring",
                year=int(m.group("year")), mileage_km=_num(m.group("km")),
                price_eur=_money(m.group("price")), dealer=m.group("dealer").strip(),
                fuel="Híbrido Plug-In", power_cv=292, condition="used_certified",
                is_official_stock=True,
            ))
    return out
