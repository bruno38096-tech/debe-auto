"""Direct Mercedes-Benz Certified inventory connector.

For GLC 300 e SUV, scan the current Certified result pages in parallel and
return only exact petrol-PHEV SUV matches. A GLC 300 de or SUV Coupé is not an
exact match and is deliberately excluded.
"""
from concurrent.futures import ThreadPoolExecutor, as_completed
from urllib.parse import urljoin
from bs4 import BeautifulSoup
import re, requests
from search_poc.models import Vehicle

BASE="https://usados.mercedes-benz.pt"
HEADERS={
    "User-Agent":"Mozilla/5.0 (compatible; DEBE-Search-Beta/0.4)",
    "Accept-Language":"pt-PT,pt;q=0.9",
}

def _money(s):
    d=re.sub(r"\D","",s or "")
    return float(d) if d else None

def _km(s):
    d=re.sub(r"\D","",s or "")
    return int(d) if d else None

def _fetch_page(page,timeout=4):
    url=f"{BASE}/vehicles?page={page}"
    r=requests.get(url,headers=HEADERS,timeout=timeout)
    if not r.ok:return []
    soup=BeautifulSoup(r.text,"html.parser")
    out=[]
    seen=set()
    # Vehicle links are repeated in image/title/buttons; collect unique URLs.
    for a in soup.find_all("a",href=True):
        href=a.get("href","")
        if "vehicle?" not in href:continue
        urljoin_abs=urljoin(BASE,href)
        if urljoin_abs in seen:continue
        seen.add(urljoin_abs)
        node=a
        block=""
        for _ in range(9):
            node=getattr(node,"parent",None)
            if node is None:break
            txt=node.get_text("\n",strip=True)
            if len(txt)>10000:break
            if "Mercedes-Benz" in txt and ("Preço" in txt or "Price" in txt) and "km" in txt:
                block=txt
                break
        if block:
            out.append((urljoin_abs,block))
    return out

def discover_glc_300e_suv(timeout=4):
    rows=[]
    with ThreadPoolExecutor(max_workers=6) as ex:
        jobs=[ex.submit(_fetch_page,p,timeout) for p in range(1,13)]
        for fut in as_completed(jobs):
            try:rows.extend(fut.result())
            except Exception:pass

    out=[]; seen=set()
    for url,text in rows:
        low=text.lower()
        compact=re.sub(r"\s+","",low)
        # exact petrol PHEV: 300 e, not 300 de; SUV, not SUV Coupé.
        if "glc300e" not in compact:continue
        if "glc300de" in compact:continue
        if "coup" in low:continue
        if "suv" not in low:continue
        if "plug-in hybrid gasóleo" in low or "plug-in hybrid diesel" in low:continue

        pm=re.search(r"Pre[cç]o\s*([\d\.\s]+)\s*€",text,re.I)
        km_m=re.search(r"([\d\.\s]+)\s*km\b",text,re.I)
        date_m=re.search(r"(\d{1,2})[\.\-/](\d{1,2})[\.\-/](20\d{2})",text)
        dealer_m=re.search(r"Plug-in Hybrid(?: Gasolina| Petrol)?\s*([^\n]+)",text,re.I)
        if not pm:continue
        sid=re.search(r"(?:vehicle=|vehicle%3D)(\d+)",url,re.I)
        key=sid.group(1) if sid else url
        if key in seen:continue
        seen.add(key)
        out.append(Vehicle(
            source="mercedes_certified",source_id=key,url=url,
            make="Mercedes-Benz",model="GLC",variant="GLC 300 e 4MATIC",
            body="SUV",year=int(date_m.group(3)) if date_m else None,
            mileage_km=_km(km_m.group(1)) if km_m else None,
            price_eur=_money(pm.group(1)),
            dealer=dealer_m.group(1).strip() if dealer_m else "",
            fuel="Híbrido Plug-In",power_cv=None,
            condition="used_certified",is_official_stock=True,
        ))
    return out
