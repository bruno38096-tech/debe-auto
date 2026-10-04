"""Carclasse direct connectors for validated beta searches."""
import re
import requests
from bs4 import BeautifulSoup
from urllib.parse import urljoin
from search_poc.models import Vehicle

BASE="https://www.carclasse.pt"
STOCK_URL=BASE+"/stock-viaturas"
HEADERS={
    "User-Agent":"Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 Chrome/124 Safari/537.36",
    "Accept-Language":"pt-PT,pt;q=0.9",
}


def _num(text):
    d=re.sub(r"\D","",text or "")
    return int(d) if d else None


def _money(text):
    d=re.sub(r"\D","",text or "")
    return float(d) if d else None


def _candidate_glc300e_urls(html):
    """Discover current GLC 300e detail URLs from the live stock page."""
    soup=BeautifulSoup(html,"html.parser")
    out=[]
    seen=set()
    for a in soup.find_all("a",href=True):
        href=a.get("href","")
        url=urljoin(BASE,href.split("#")[0])
        low=url.lower()
        if "/stock-viaturas/" not in low:
            continue
        # Current Carclasse detail URLs encode make/model/variant in the slug.
        if "mercedes-benz-glc-glc-300e" not in low:
            continue
        if url in seen:
            continue
        seen.add(url)
        out.append(url)
    return out


def _parse_glc(url,timeout=6):
    r=requests.get(url,headers=HEADERS,timeout=timeout)
    if r.status_code>=400:return None
    soup=BeautifulSoup(r.text,"html.parser")
    text=soup.get_text("\n",strip=True)
    low=text.lower()

    title_node=soup.find("h1")
    title=title_node.get_text(" ",strip=True) if title_node else "Mercedes GLC 300 e"
    title_low=title.lower()
    title_compact=re.sub(r"[^a-z0-9]+","",title_low)
    # Validate against the vehicle heading, not the entire page: related
    # recommendations can legitimately contain a GLC 300 de.
    if "glc" not in title_low or "glc300e" not in title_compact:return None
    if "glc300de" in title_compact:return None
    body="Coupé" if "coup" in title_low else "SUV"

    km=re.search(r"Quilometragem\s*([\d\.\s]+)\s*Km",text,re.I)
    date=re.search(r"Data matr[ií]cula\s*\d{1,2}\s*/\s*(20\d{2})",text,re.I)
    pvp=re.search(r"P\.V\.P\.\s*([\d\.\s]+)\s*EUR",text,re.I)
    newp=re.search(r"Pre[cç]o em novo\s*([\d\.\s]+)\s*EUR",text,re.I)
    condition=re.search(r"Condi[cç][aã]o\s*(Novo|Servi[cç]o|Usado)",text,re.I)
    fuel=re.search(r"Combust[ií]vel\s*([^\n]+)",text,re.I)

    price=_money(pvp.group(1)) if pvp else None
    list_price=_money(newp.group(1)) if newp else None
    discount=(list_price-price) if list_price and price and list_price>price else None
    cv=(
        "new_stock" if condition and condition.group(1).lower()=="novo"
        else ("demo_service" if condition and "serv" in condition.group(1).lower() else "used_certified")
    )
    sid_m=re.search(r"/stock-viaturas/(\d+)",url)
    sid=sid_m.group(1) if sid_m else url.rstrip("/").split("/")[-1]

    return Vehicle(
        source="carclasse",source_id=sid,url=url,
        make="Mercedes-Benz",model="GLC",variant=title,body=body,
        year=int(date.group(1)) if date else None,
        mileage_km=_num(km.group(1)) if km else None,
        price_eur=price,dealer="Carclasse",
        fuel=(fuel.group(1).strip() if fuel else "Híbrido Plug-In"),
        power_cv=313,condition=cv,list_price_eur=list_price,
        discount_eur=round(discount,2) if discount else None,
        discount_pct=round(discount/list_price*100,1) if discount and list_price else None,
        is_official_stock=True,
    )


def discover_glc_300e(timeout=6):
    urls=[]
    try:
        r=requests.get(STOCK_URL,headers=HEADERS,timeout=timeout)
        r.raise_for_status()
        urls=_candidate_glc300e_urls(r.text)
    except Exception:
        urls=[]

    out=[]
    for url in urls:
        try:
            v=_parse_glc(url,timeout)
            if v and v.body=="SUV":
                out.append(v)
        except Exception:
            continue
    return out
