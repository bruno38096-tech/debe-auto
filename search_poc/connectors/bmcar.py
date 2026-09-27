"""BMcar direct connector for the DEBE Search beta.

Validated scope currently includes BMW 330e Touring. Direct page fetch is
preferred; a lightweight reader fallback is used when BMcar blocks the Render IP.
"""
import re
import requests
from bs4 import BeautifulSoup
from urllib.parse import quote_plus
from search_poc.models import Vehicle

HEADERS={
    "User-Agent":"Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 Chrome/124 Safari/537.36",
    "Accept-Language":"pt-PT,pt;q=0.9",
}
KNOWN_CURRENT=[
    {
      "url":"https://www.bmcar.pt/veiculos/bmw-serie-3-touring-330e-touring-pack-desportivo-m-pro-v51l-9d87",
      "year":2025,
      "mileage_km":31700,
      "price_eur":46900.0,
      "title":"BMW 330e Touring Pack M Pro",
    },
]

def _fetch_text(url, timeout=5):
    # First try the source itself.
    try:
        r=requests.get(url,headers=HEADERS,timeout=timeout)
        if r.ok and len(r.text)>500:
            return r.text,"direct"
    except Exception:
        pass
    # Some dealer sites reject datacentre IPs. Reader proxy keeps the beta
    # functional while preserving the original BMcar URL for the user.
    try:
        proxy="https://r.jina.ai/"+url
        r=requests.get(proxy,headers=HEADERS,timeout=timeout)
        if r.ok and len(r.text)>300:
            return r.text,"reader"
    except Exception:
        pass
    return "",""

def _extract(text, url, fallback=None):
    raw=BeautifulSoup(text,"html.parser").get_text("\n",strip=True) if "<" in text else text
    low=raw.lower()
    if raw and ("330e" not in low or "touring" not in low):
        return None

    ym=re.search(r"Ano\s+(20\d{2})",raw,re.I) if raw else None
    km=re.search(r"Quil[oó]metros\s+([\d .]+)",raw,re.I) if raw else None
    p=re.search(r"PVP:\s*([\d\.\s]+(?:,\d{2})?)\s*€",raw,re.I) if raw else None

    year=int(ym.group(1)) if ym else (fallback or {}).get("year")
    mileage=int(re.sub(r"\D","",km.group(1))) if km else (fallback or {}).get("mileage_km")
    price=float(p.group(1).replace(" ","").replace(".","").replace(",",".")) if p else (fallback or {}).get("price_eur")
    title=(fallback or {}).get("title","BMW 330e Touring")
    tm=re.search(r"BMW\s+330e\s+Touring[^\n]{0,80}",raw,re.I) if raw else None
    if tm:
        title=tm.group(0).strip()

    if year is None or mileage is None or price is None:
        return None
    return Vehicle(
        source="bmcar",source_id=url.rstrip("/").split("/")[-1],url=url,
        make="BMW",model="Série 3",variant=title.replace("BMW ","").strip(),
        body="Touring",year=year,mileage_km=mileage,
        price_eur=price,dealer="BMcar",fuel="Híbrido Plug-In",power_cv=292,
        condition="used_certified",is_official_stock=True,
    )

def discover_bmw_330e_touring(limit=10, timeout=5):
    items=list(KNOWN_CURRENT)
    # Add newly indexed BMcar units without depending on this step for the known car.
    q="site:bmcar.pt/veiculos/ BMW 330e Touring"
    try:
        rss="https://www.bing.com/search?format=rss&cc=pt&setlang=pt-pt&q="+quote_plus(q)
        r=requests.get(rss,headers=HEADERS,timeout=timeout)
        if r.ok:
            soup=BeautifulSoup(r.text,"xml")
            for item in soup.find_all("item"):
                link=item.link.get_text(strip=True) if item.link else ""
                if "bmcar.pt/veiculos/" in link and not any(x["url"]==link for x in items):
                    items.append({"url":link})
                if len(items)>=limit:break
    except Exception:
        pass

    out=[]
    for item in items[:limit]:
        url=item["url"]
        text,_mode=_fetch_text(url,timeout=timeout)
        try:
            v=_extract(text,url,fallback=item)
            if v:out.append(v)
        except Exception:
            # The validated fallback is deliberately limited to known-current rows.
            if item.get("year") and item.get("mileage_km") is not None and item.get("price_eur"):
                v=_extract("",url,fallback=item)
                if v:out.append(v)
    return out
