"""BMcar direct connector for the DEBE Search beta.

Validated scope currently includes BMW 330e Touring. Discovery is kept
independent from BMW Premium Selection so BMcar-only stock can surface.
"""
import re
import requests
from bs4 import BeautifulSoup
from urllib.parse import quote_plus
from search_poc.models import Vehicle

HEADERS={
    "User-Agent":"Mozilla/5.0 (compatible; DEBE-Search-Beta/0.3)",
    "Accept-Language":"pt-PT,pt;q=0.9",
}
KNOWN_CURRENT=[
    "https://www.bmcar.pt/veiculos/bmw-serie-3-touring-330e-touring-pack-desportivo-m-pro-v51l-9d87",
]

def _parse(url, timeout=6):
    r=requests.get(url,headers=HEADERS,timeout=timeout)
    if r.status_code>=400:return None
    soup=BeautifulSoup(r.text,"html.parser")
    text=soup.get_text("\n",strip=True)
    low=text.lower()
    if "330e" not in low or "touring" not in low:return None

    ym=re.search(r"Ano\s+(20\d{2})",text,re.I)
    km=re.search(r"Quil[oó]metros\s+([\d .]+)",text,re.I)
    p=re.search(r"PVP:\s*([\d\.\s]+(?:,\d{2})?)\s*€",text,re.I)
    h=soup.find("h1") or soup.find("h2")
    title=h.get_text(" ",strip=True) if h else "BMW 330e Touring"
    if not (ym and km and p):return None
    price=float(p.group(1).replace(" ","").replace(".","").replace(",","."))
    mileage=int(re.sub(r"\D","",km.group(1)))
    return Vehicle(
        source="bmcar",source_id=url.rstrip("/").split("/")[-1],url=url,
        make="BMW",model="Série 3",variant=title.replace("BMW ","").strip(),
        body="Touring",year=int(ym.group(1)),mileage_km=mileage,
        price_eur=price,dealer="BMcar",fuel="Híbrido Plug-In",power_cv=292,
        condition="used_certified",is_official_stock=True,
    )

def discover_bmw_330e_touring(limit=10, timeout=6):
    urls=list(KNOWN_CURRENT)
    # Public discovery adds new BMcar units not yet present in the validated list.
    q="site:bmcar.pt/veiculos/ BMW 330e Touring"
    try:
        rss="https://www.bing.com/search?format=rss&cc=pt&setlang=pt-pt&q="+quote_plus(q)
        r=requests.get(rss,headers=HEADERS,timeout=timeout)
        if r.ok:
            soup=BeautifulSoup(r.text,"xml")
            for item in soup.find_all("item"):
                link=item.link.get_text(strip=True) if item.link else ""
                if "bmcar.pt/veiculos/" in link and link not in urls:
                    urls.append(link)
                if len(urls)>=limit:break
    except Exception:
        pass
    out=[]
    for url in urls[:limit]:
        try:
            v=_parse(url,timeout=timeout)
            if v:out.append(v)
        except Exception:
            continue
    return out
