"""BMW Portugal / official-dealer new stock discovery for DEBE Search PoC."""
import re
import requests
from bs4 import BeautifulSoup
from urllib.parse import quote_plus
from search_poc.models import Vehicle

HEADERS={"User-Agent":"Mozilla/5.0 (compatible; DEBE-Search-PoC/0.1)","Accept-Language":"pt-PT,pt;q=0.9"}

BMW_BASE_URL="https://www.bmw.pt/pt/all-models.html"
CAETANO_330E_URL="https://caetano.pt/bmw/carros-novos/330e/"


def bmw_330e_touring_list_price(timeout=12):
    r=requests.get(BMW_BASE_URL,headers=HEADERS,timeout=timeout); r.raise_for_status()
    text=BeautifulSoup(r.text,"html.parser").get_text(" ",strip=True)
    # Current public MSRP / recommended base price.
    m=re.search(r"BMW\s+330e\s+Touring.*?A partir de\s+([\d .]+)\s*€",text,re.I|re.S)
    if not m:
        return None
    return float(re.sub(r"\D","",m.group(1)))


def caetano_330e_touring_stock(timeout=12):
    r=requests.get(CAETANO_330E_URL,headers=HEADERS,timeout=timeout); r.raise_for_status()
    text=BeautifulSoup(r.text,"html.parser").get_text("\n",strip=True)
    low=text.lower()
    if "em stock" not in low or "330e auto touring" not in low:
        return []
    list_price=bmw_330e_touring_list_price(timeout=timeout)
    # Caetano currently confirms model-level stock but does not expose a public
    # unit price in the indexed page. Keep it as an availability lead, not a fake offer.
    return [Vehicle(
        source="caetano_new_stock",
        source_id="bmw-330e-touring-stock",
        url=CAETANO_330E_URL,
        make="BMW", model="Série 3", variant="330e Auto", body="Touring",
        year=None, mileage_km=0, price_eur=None,
        dealer="Caetano", fuel="Híbrido Plug-In", power_cv=292,
        condition="new_stock", availability="Em stock",
        list_price_eur=list_price, is_official_stock=True,
    )]
