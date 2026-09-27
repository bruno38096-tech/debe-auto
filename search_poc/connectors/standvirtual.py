"""Standvirtual discovery connector for the DEBE Search PoC.

This deliberately uses public search discovery plus detail-page parsing instead
of assuming a private marketplace API. It returns a conservative lower bound:
only listings discoverable through the public search surface are included.
"""
import re
import requests
from bs4 import BeautifulSoup
from urllib.parse import quote_plus
from search_poc.models import Vehicle

HEADERS = {
    "User-Agent": "Mozilla/5.0 (compatible; DEBE-Search-PoC/0.1)",
    "Accept-Language": "pt-PT,pt;q=0.9,en;q=0.7",
}


def _eur(text):
    if not text:
        return None
    m = re.search(r"(\d{2,3}(?:[ .]\d{3})*)\s*EUR", text, re.I)
    return float(re.sub(r"\D", "", m.group(1))) if m else None


def _km(text):
    m = re.search(r"(\d{1,3}(?:[ .]\d{3})*)\s*km", text or "", re.I)
    return int(re.sub(r"\D", "", m.group(1))) if m else None


def _year(text):
    m = re.search(r"\b(20\d{2})\b", text or "")
    return int(m.group(1)) if m else None


def _listing_id(url, text=""):
    m = re.search(r"ID([A-Za-z0-9]+)", url or "")
    if m:
        return m.group(1)
    m = re.search(r"\bID:\s*(\d+)", text or "", re.I)
    return m.group(1) if m else url


def discover_bmw_330e_touring(limit=40, timeout=12):
    # Bing RSS is used only as a public discovery surface for listing URLs.
    q = 'site:standvirtual.com/carros/anuncio/ "BMW 330e Touring"'
    rss = "https://www.bing.com/search?format=rss&cc=pt&setlang=pt-pt&q=" + quote_plus(q)
    r = requests.get(rss, headers=HEADERS, timeout=timeout)
    r.raise_for_status()
    soup = BeautifulSoup(r.text, "xml")
    urls = []
    for item in soup.find_all("item"):
        link = item.link.get_text(strip=True) if item.link else ""
        if "standvirtual.com/carros/anuncio/" in link and link not in urls:
            urls.append(link)
        if len(urls) >= limit:
            break

    out = []
    for url in urls:
        try:
            page = requests.get(url, headers=HEADERS, timeout=timeout)
            page.raise_for_status()
            text = BeautifulSoup(page.text, "html.parser").get_text("\n", strip=True)
            low = text.lower()
            if "bmw" not in low or "330" not in low or "carrinha" not in low:
                continue
            if "híbrido plug-in" not in low and "hibrido plug-in" not in low:
                continue
            title = BeautifulSoup(page.text, "html.parser").title
            title = title.get_text(" ", strip=True) if title else ""
            variant = "330e"
            vm = re.search(r"BMW\s+330\s+(.+?)(?:\s+-\s+|\|)", title, re.I)
            if vm:
                variant = "330 " + vm.group(1).strip()
            out.append(Vehicle(
                source="standvirtual",
                source_id=str(_listing_id(url, text)),
                url=url,
                make="BMW",
                model="Série 3",
                variant=variant,
                body="Touring",
                year=_year(title + "\n" + text),
                mileage_km=_km(text),
                price_eur=_eur(title + "\n" + text),
                dealer="",
                fuel="Híbrido Plug-In",
                power_cv=292,
            ))
        except Exception:
            continue
    return out
