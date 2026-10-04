"""Generic BMW Premium Selection discovery for BMW queries in the Search PoC."""
import re
import requests
from bs4 import BeautifulSoup
from urllib.parse import urljoin

BASE="https://bmwpremiumselection.bmw.pt"
HEADERS={"User-Agent":"Mozilla/5.0 (compatible; DEBE-Search-PoC/0.8)","Accept-Language":"pt-PT,pt;q=0.9"}


def _route(query):
    q=(query or "").lower()
    if "bmw" not in q:return ""
    if "330" in q and "touring" in q:return ""  # dedicated connector is richer
    if "ix3" in q:return BASE+"/carros-usados/bmw-ix3/"
    for model in ("x1","x3","x5"):
        if model in q:
            vm=re.search(r"\b(?:xdrive|sdrive)\s*\d{2}[a-z0-9]*\b",q)
            if vm:
                variant=vm.group(0).replace(" ","")
                return f"{BASE}/x/{model}/{variant}/"
            return f"{BASE}/x/{model[1:]}/"
    return ""


def _money(v):
    return float((v or "").replace(" ","").replace(".","").replace(",","."))


def _num(v):
    d=re.sub(r"\D","",v or "")
    return int(d) if d else None


def discover_rows(query,timeout=10):
    url=_route(query)
    if not url:return []
    r=requests.get(url,headers=HEADERS,timeout=timeout); r.raise_for_status()
    soup=BeautifulSoup(r.text,"html.parser")
    out=[]
    seen=set()
    blocks=[]
    for a in soup.find_all("a",href=True):
        href=a.get("href","")
        full=urljoin(url,href)
        if "bmwpremiumselection.bmw.pt" not in full:continue
        if not re.search(r"/\d+/?(?:[#?].*)?$",full):continue
        node=a
        card=""
        for _ in range(10):
            node=getattr(node,"parent",None)
            if node is None:break
            txt=node.get_text("\n",strip=True)
            if len(txt)>14000:break
            if re.search(r"\bkm\b",txt,re.I) and re.search(r"Pre[cç]o",txt,re.I) and re.search(r"Veículo\s+oferecido",txt,re.I):
                card=txt; break
        if card and full not in seen:
            seen.add(full); blocks.append((full,card))
    if not blocks:
        text=soup.get_text("\n",strip=True)
        raw=re.split(r"(?=Veículo certificado BMW Premium Selection)",text)
        blocks=[(url+"#offer-"+str(i),x) for i,x in enumerate(raw) if re.search(r"\bkm\b",x,re.I) and re.search(r"Pre[cç]o",x,re.I)]

    for i,(vehicle_url,b) in enumerate(blocks):
        km=re.search(r"(\d{1,3}(?:[\.\s]\d{3})*)\s*km\b",b,re.I)
        price=re.search(r"Pre[cç]o:\s*([\d\.\s]+,\d{2})\s*€",b,re.I)
        dealer=re.search(r"Veículo oferecido pela\s+([^\n]+)",b,re.I)
        if not (km and price):continue
        years=[int(y) for y in re.findall(r"\b(20(?:1\d|2\d))\b",b[:1200])]
        lines=[x.strip() for x in b.split("\n") if x.strip()]
        title=next((x for x in lines[:12] if x.lower().startswith("bmw ") and "premium selection" not in x.lower()),"BMW")
        asking=_money(price.group(1))
        comparison=None; conditional=None; condition=""
        # Campaign pages may show a second amount next to "desconto direto" / retoma.
        cm=re.search(r"Pre[cç]o:\s*[\d\.\s]+,\d{2}\s*€\s*([\d\.\s]+,\d{2})\s*€\s*Desconto",b,re.I|re.S)
        if cm:
            comparison=_money(cm.group(1))
            if comparison>asking and re.search(r"retoma|trade[- ]?in",b,re.I):
                conditional=asking; asking=comparison; condition="retoma"
        out.append({
            "source_key":"bmw_premium","source":"BMW Premium Selection","official":True,
            "title":title,"snippet":f"{years[0] if years else ''} · {_num(km.group(1)) or 0:,} km · {dealer.group(1).strip() if dealer else ''}".replace(",","."),
            "url":vehicle_url,"condition":"used_certified","availability":"",
            "price_eur":asking,"list_price_eur":comparison,
            "conditional_price_eur":conditional,"price_condition":condition,
            "discount_eur":round(comparison-conditional,2) if comparison and conditional else None,
            "discount_pct":round((comparison-conditional)/comparison*100,1) if comparison and conditional else None,
            "mileage_km":_num(km.group(1)),"year":years[0] if years else None,
            "dealer":dealer.group(1).strip() if dealer else "","discovery":"direct_connector",
        })
    return out
