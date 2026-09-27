"""Carclasse direct connectors for validated beta searches."""
import re
import requests
from bs4 import BeautifulSoup
from search_poc.models import Vehicle

HEADERS={
    "User-Agent":"Mozilla/5.0 (compatible; DEBE-Search-Beta/0.3)",
    "Accept-Language":"pt-PT,pt;q=0.9",
}
GLC_300E_URLS=[
    "https://www.carclasse.pt/stock-viaturas/149605-mercedes-benz-glc-glc-300e",
]

def _num(text):
    d=re.sub(r"\D","",text or "")
    return int(d) if d else None

def _money(text):
    d=re.sub(r"\D","",text or "")
    return float(d) if d else None

def _parse_glc(url,timeout=6):
    r=requests.get(url,headers=HEADERS,timeout=timeout)
    if r.status_code>=400:return None
    soup=BeautifulSoup(r.text,"html.parser")
    text=soup.get_text("\n",strip=True)
    low=text.lower()
    if "glc" not in low or ("300 e" not in low and "300e" not in low):return None

    title_node=soup.find("h1")
    title=title_node.get_text(" ",strip=True) if title_node else "Mercedes GLC 300 e"
    km=re.search(r"Quilometragem\s*([\d\.\s]+)\s*Km",text,re.I)
    date=re.search(r"Data matr[ií]cula\s*\d{1,2}\s*/\s*(20\d{2})",text,re.I)
    pvp=re.search(r"P\.V\.P\.\s*([\d\.\s]+)\s*EUR",text,re.I)
    newp=re.search(r"Pre[cç]o em novo\s*([\d\.\s]+)\s*EUR",text,re.I)
    condition=re.search(r"Condi[cç][aã]o\s*(Novo|Servi[cç]o|Usado)",text,re.I)

    price=_money(pvp.group(1)) if pvp else None
    list_price=_money(newp.group(1)) if newp else None
    discount=(list_price-price) if list_price and price and list_price>price else None
    cv="new_stock" if condition and condition.group(1).lower()=="novo" else ("demo_service" if condition and "serv" in condition.group(1).lower() else "used_certified")
    return Vehicle(
        source="carclasse",source_id=url.rstrip("/").split("/")[-1],url=url,
        make="Mercedes-Benz",model="GLC",variant="GLC 300 e",body="SUV",
        year=int(date.group(1)) if date else None,
        mileage_km=_num(km.group(1)) if km else None,
        price_eur=price,dealer="Carclasse",fuel="Híbrido Plug-In",
        power_cv=313,condition=cv,list_price_eur=list_price,
        discount_eur=round(discount,2) if discount else None,
        discount_pct=round(discount/list_price*100,1) if discount and list_price else None,
        is_official_stock=True,
    )

def discover_glc_300e(timeout=6):
    out=[]
    for url in GLC_300E_URLS:
        try:
            v=_parse_glc(url,timeout)
            if v:out.append(v)
        except Exception:
            continue
    return out
