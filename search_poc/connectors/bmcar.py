"""BMcar inventory connector for the DEBE Search beta.

For BMW 330e Touring we query BMcar's own filtered inventory page first,
then open each matching detail page. Prices are NEVER taken from stale
fallback data: if a live price cannot be read, price_eur remains None.
"""
import re
import requests
from bs4 import BeautifulSoup
from urllib.parse import urljoin, quote_plus
from search_poc.models import Vehicle

HEADERS={
    "User-Agent":"Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 Chrome/124 Safari/537.36",
    "Accept-Language":"pt-PT,pt;q=0.9",
}
BASE="https://www.bmcar.pt"
FILTER_330E_TOURING=(
    "https://www.bmcar.pt/veiculos?"
    "brandIds%5B%5D=c427305a-a22d-433f-99dd-2198ccf858da&"
    "engineTypeIds%5B%5D=9&"
    "brandSegmentIds%5B%5D=9f2b387a-fa3a-4e24-554f-08d7d3ff7f58"
)
KNOWN_URLS=[
    "https://www.bmcar.pt/veiculos/bmw-serie-3-touring-330e-touring-pack-desportivo-m-pro-v51l-9d87",
]

def _fetch(url, timeout=6):
    # Source first.
    try:
        r=requests.get(url,headers=HEADERS,timeout=timeout)
        if r.ok and len(r.text)>400:
            return r.text,"html"
    except Exception:
        pass
    # Reader fallback for datacentre/IP blocking. Still reads the current source.
    try:
        r=requests.get("https://r.jina.ai/"+url,headers=HEADERS,timeout=timeout)
        if r.ok and len(r.text)>250:
            return r.text,"markdown"
    except Exception:
        pass
    return "",""

def _vehicle_links(text, mode):
    out=[]
    if not text:return out
    if mode=="html":
        soup=BeautifulSoup(text,"html.parser")
        for a in soup.find_all("a",href=True):
            href=urljoin(BASE,a.get("href",""))
            if "/veiculos/" in href and href.rstrip("/")!=BASE+"/veiculos" and href not in out:
                out.append(href)
    else:
        # Jina markdown.
        for m in re.finditer(r"\]\((https?://(?:www\.)?bmcar\.pt/veiculos/[^)\s]+)\)",text,re.I):
            href=m.group(1)
            if href not in out:out.append(href)
        # Raw URLs are also common in reader output.
        for m in re.finditer(r"https?://(?:www\.)?bmcar\.pt/veiculos/[A-Za-z0-9_\-/%]+",text,re.I):
            href=m.group(0).rstrip(".,)")
            if href not in out:out.append(href)
    return out

def _num(s):
    d=re.sub(r"\D","",s or "")
    return int(d) if d else None

def _price_from_text(text):
    # BMcar may expose PVP and/or a lower ready-payment/flash-sale price.
    values=[]
    patterns=[
      r"(?:Pronto\s+Pagamento|Flash\s+Sale)[^\d€]{0,80}([\d\.\s]+(?:,\d{2})?)\s*€",
      r"PVP:\s*([\d\.\s]+(?:,\d{2})?)\s*€",
      r"Pre[cç]o[^\d€]{0,30}([\d\.\s]+(?:,\d{2})?)\s*€",
    ]
    for p in patterns:
        m=re.search(p,text or "",re.I|re.S)
        if m:
            raw=m.group(1).replace(" ","").replace(".","").replace(",",".")
            try:
                v=float(raw)
                if 5000<=v<=500000:values.append(v)
            except Exception:pass
    # When the page exposes several purchase prices, the current cash price is
    # the lowest credible amount. This avoids showing an obsolete PVP as current.
    return min(values) if values else None

def _parse_detail(url, timeout=6):
    page,mode=_fetch(url,timeout)
    if not page:return None
    raw=BeautifulSoup(page,"html.parser").get_text("\n",strip=True) if mode=="html" else page
    low=raw.lower()
    compact=re.sub(r"\s+","",low)
    if "330e" not in compact or "touring" not in low:return None

    ym=re.search(r"Ano\s+(20\d{2})",raw,re.I)
    km=re.search(r"Quil[oó]metros\s+([\d .]+)",raw,re.I)
    if not km:
        km=re.search(r"\b(\d{1,3}(?:[\.\s]\d{3}))\s*km\b",raw,re.I)
    price=_price_from_text(raw)

    # Title/variant.
    tm=re.search(r"BMW\s+(?:S[eé]rie\s*3\s+Touring\s+)?330e\s+Touring[^\n]{0,100}",raw,re.I)
    title=tm.group(0).strip() if tm else "BMW 330e Touring"

    return Vehicle(
        source="bmcar",source_id=url.rstrip("/").split("/")[-1],url=url,
        make="BMW",model="Série 3",variant=title.replace("BMW ","").strip(),
        body="Touring",year=int(ym.group(1)) if ym else None,
        mileage_km=_num(km.group(1)) if km else None,
        price_eur=price,dealer="BMcar",fuel="Híbrido Plug-In",power_cv=292,
        condition="used_certified",is_official_stock=True,
    )

def discover_bmw_330e_touring(limit=20, timeout=6):
    urls=[]
    listing,mode=_fetch(FILTER_330E_TOURING,timeout)
    for url in _vehicle_links(listing,mode):
        if url not in urls:urls.append(url)

    # Known detail URLs only help discovery; no price/year/km fallback is used.
    for url in KNOWN_URLS:
        if url not in urls:urls.append(url)

    # Lightweight public discovery can add newly-created detail pages if the
    # filtered inventory happens to be client-side only.
    try:
        q="site:bmcar.pt/veiculos/ BMW 330e Touring"
        rss="https://www.bing.com/search?format=rss&cc=pt&setlang=pt-pt&q="+quote_plus(q)
        r=requests.get(rss,headers=HEADERS,timeout=min(timeout,5))
        if r.ok:
            soup=BeautifulSoup(r.text,"xml")
            for item in soup.find_all("item"):
                link=item.link.get_text(strip=True) if item.link else ""
                if "/veiculos/" in link and link not in urls:urls.append(link)
    except Exception:
        pass

    out=[]
    seen=set()
    for url in urls[:max(limit,20)]:
        try:
            v=_parse_detail(url,timeout=timeout)
            if not v:continue
            sig=(v.source_id,v.url)
            if sig in seen:continue
            seen.add(sig);out.append(v)
        except Exception:
            continue
    return out[:limit]
