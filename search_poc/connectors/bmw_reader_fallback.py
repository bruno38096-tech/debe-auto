"""BMW Premium Selection fallback using Jina Reader when site blocks server requests.

Every result requires an individual BMW offer URL plus a nearby odometer,
year and published asking price. Never construct fictional vehicle URLs.
"""
import re
from urllib.parse import urlparse
import requests

URL = "https://bmwpremiumselection.bmw.pt/serie-3/330e-touring/"
HEADERS = {"User-Agent": "Mozilla/5.0", "Accept": "text/plain", "X-Return-Format": "markdown"}

# Reader Markdown places an optional quoted offer ID after the URL and often
# wraps thumbnails in nested image links. Match the real URL independently
# of the link label and use the last anchor for each offer card.
_OFFER = re.compile(
    r'(https?://(?:www\.)?bmwpremiumselection\.bmw\.pt/'
    r'[^\s)"]+/bmw-serie-3-330e-touring/(\d{6,})/?)',
    re.I,
)
_FACTS = re.compile(
    r"(\d{1,3}(?:[.\s]\d{3})+)\s*km[\s\S]{0,180}?\b(20(?:1\d|2\d))\b",
    re.I,
)
_PRICE = re.compile(r"Pre[cç]o\s*:?\s*([\d.\s]+,\d{2})\s*€", re.I)
_PRICE_NEXT = re.compile(r"^\s*([\d.\s]+,\d{2})\s*€", re.I)


def money(value):
    return float(value.replace(" ", "").replace(".", "").replace(",", "."))


def parse_bmw_reader(markdown):
    """Extract independently clickable offers from reader Markdown, not category links."""
    matches = list(_OFFER.finditer(markdown or ""))
    # Each card has multiple linked photographs. Take the FIRST link for
    # each distinct offer, then extract facts until the NEXT offer begins.
    # Taking the last thumbnail discarded kilometre/year/price metadata.
    first_by_id = {}
    for match in matches:
        first_by_id.setdefault(match.group(2), match)
    offers = sorted(first_by_id.values(), key=lambda item: item.start())
    out = []
    seen = set()
    for index, match in enumerate(offers):
        link, offer_id = match.groups()
        if offer_id in seen:
            continue
        limit = offers[index + 1].start() if index + 1 < len(offers) else len(markdown)
        text = markdown[match.end():min(limit, match.end() + 14000)]
        # The public Reader wraps asking prices in **bold Markdown**, e.g.
        # "Preço:**43.450,00 €**"; strip formatting before monetary parsing.
        text = re.sub(r"\\*{1,3}", "", text)
        # BMW places the model year inside image alt text but the odometer
        # below the image carousel; they need not be adjacent.
        km_match = re.search(r"(\d{1,3}(?:[.\s]\d{3})+)\s*km\b", text, re.I)
        year_match = re.search(r"\b20(?:1\d|2\d)\b", text)
        price_match = _PRICE.search(text)
        if not km_match or not year_match or not price_match:
            continue
        km = int(re.sub(r"\D", "", km_match.group(1)))
        year = int(year_match.group(0))
        displayed_price = money(price_match.group(1))
        if not (0 < km < 1000000 and 2010 <= year <= 2030 and 3000 <= displayed_price <= 250000):
            continue

        # The second amount immediately after BMW's Price label is normally
        # the undiscounted cash price for a conditional trade-in promotion.
        # Don't advertise a trade-in-only amount as a universal asking price.
        after = text[price_match.end():price_match.end() + 160]
        second = _PRICE_NEXT.match(after)
        promo = re.search(r"desconto\s+direto[\s\S]{0,60}?retoma", text[:2700], re.I)
        comparison = money(second.group(1)) if second else None
        conditional = None
        price_condition = ""
        asking_price = displayed_price
        if promo and comparison and comparison > displayed_price:
            conditional = displayed_price
            asking_price = comparison
            price_condition = "retoma"
        dealer_match = re.search(r"Ve[ií]culo\s+oferecido\s+pela\s+([^\n]+)", text, re.I)
        dealer = re.sub(r"\s+", " ", dealer_match.group(1)).strip(" *") if dealer_match else ""
        if urlparse(link).hostname not in {"bmwpremiumselection.bmw.pt", "www.bmwpremiumselection.bmw.pt"}:
            continue
        seen.add(offer_id)
        out.append({
            "source_key": "bmw_premium", "source": "BMW Premium Selection",
            "official": True, "title": "BMW Série 3 330e Touring",
            "snippet": f"{year} · {km:,} km · {dealer}".replace(",", "."),
            "url": link, "condition": "used_certified", "availability": "",
            "price_eur": asking_price, "list_price_eur": comparison if price_condition else None,
            "conditional_price_eur": conditional, "price_condition": price_condition,
            "discount_eur": round(comparison - conditional, 2) if conditional is not None else None,
            "discount_pct": round((comparison - conditional) / comparison * 100, 1) if conditional is not None else None,
            "mileage_km": km, "year": year, "dealer": dealer,
            "discovery": "reader_fallback", "stock_ref": offer_id,
        })
    return out


def discover_rows(timeout=8):
    response = requests.get("https://r.jina.ai/" + URL, headers=HEADERS, timeout=(3, timeout))
    response.raise_for_status()
    return parse_bmw_reader(response.text)
