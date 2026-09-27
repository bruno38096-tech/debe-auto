"""BMcar public-stock connector for the DEBE Search PoC."""
import re
import requests
from bs4 import BeautifulSoup
from urllib.parse import quote_plus
from search_poc.models import Vehicle

HEADERS={"User-Agent":"Mozilla/5.0 (compatible; DEBE-Search-PoC/0.1)","Accept-Language":"pt-PT,pt;q=0.9"}


def _int(pattern, text):
    m=re.search(pattern,text or "",re.I)
    return int(re.sub(r"\D","",m.group(1))) if m else None


def _price(text):
    m=re.search(r"(?:PVP:|Preço:?)[^\d]*(\d{2,3}(?:[ .]\d{3})*(?:,\d{2})?)\s*€",text or "",re.I)
    return float(re.sub(r"[^\d,]","",m.group(1)).replace(",",".")) if m else None


def discover_bmw_330e_touring(limit=20, timeout=12):
    q='site:bmcar.pt/veiculos/ "330e Touring"'
    rss="https://www.bing.com/search?format=rss&cc=pt&setlang=pt-pt&q="+quote_plus(q)
    r=requests.get(rss,headers=HEADERS,timeout=timeout); r.raise_for_status()
    soup=BeautifulSoup(r.text,"xml")
    urls=[]
    for item in soup.find_all("item"):
        u=item.link.get_text(strip=True) if item.link else ""
        if "bmcar.pt/veiculos/" in u and u not in urls: urls.append(u)
        if len(urls)>=limit: break

    out=[]
    for u in urls:
        try:
            page=requests.get(u,headers=HEADERS,timeout=timeout); page.raise_for_status()
            text=BeautifulSoup(page.text,"html.parser").get_text("\n",strip=True)
            low=text.lower()
            if "330e touring" not in low: continue
            year=_int(r"Ano\s+(20\d{2})",text)
            km=_int(r"Quilómetros\s+([\d .]+)",text)
            out.append(Vehicle(
                source="bmcar",
                source_id=u.rstrip("/").split("/")[-1],
                url=u,
                make="BMW", model="Série 3", variant="330e", body="Touring",
                year=year, mileage_km=km, price_eur=_price(text),
                dealer="BMcar", fuel="Híbrido Plug-In", power_cv=292,
            ))
        except Exception:
            continue
    return out
