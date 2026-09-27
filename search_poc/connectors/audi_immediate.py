"""Audi Portugal immediate-delivery stock connector."""
import re
import requests
from bs4 import BeautifulSoup
from search_poc.models import Vehicle

BASE="https://disponivel-imediatamente.audi.pt/search"
HEADERS={"User-Agent":"Mozilla/5.0 (compatible; DEBE-Search-PoC/0.1)","Accept-Language":"pt-PT,pt;q=0.9"}

def _money(s):
    if not s: return None
    s=s.replace("\xa0"," ")
    m=re.search(r"(\d{2,3}(?:\.\d{3})*(?:,\d{2})?)\s*€",s)
    if not m: return None
    return float(m.group(1).replace(".","").replace(",","."))

def fetch_a6_avant_etron(timeout=15):
    url=BASE+"?mg=Audi+A6+Avant+e-tron"
    r=requests.get(url,headers=HEADERS,timeout=timeout); r.raise_for_status()
    soup=BeautifulSoup(r.text,"html.parser")
    text=soup.get_text("\n",strip=True)
    blocks=re.split(r"(?=Audi A6 Avant e-tron performance SE)",text)
    out=[]
    for i,b in enumerate(blocks):
        if "Disponível Imediatamente" not in b: continue
        prices=re.findall(r"(\d{2,3}(?:\.\d{3})*(?:,\d{2})?)\s*€",b)
        list_price=sale=None
        if len(prices)>=2:
            list_price=float(prices[0].replace(".","").replace(",","."))
            sale=float(prices[1].replace(".","").replace(",","."))
        dealer=""
        dm=re.search(r"Disponível em\s+([^\n]+)",b)
        if dm: dealer=dm.group(1).strip()
        discount=(list_price-sale) if list_price and sale else None
        pct=(discount/list_price*100) if discount and list_price else None
        out.append(Vehicle(
            source="audi_immediate", source_id=f"a6-etron-{i}", url=url,
            make="Audi", model="A6 Avant e-tron", variant="performance SE", body="Avant",
            year=2026, mileage_km=0, price_eur=sale, dealer=dealer,
            fuel="Elétrico", power_cv=367, condition="new_stock",
            availability="Disponível Imediatamente", list_price_eur=list_price,
            discount_eur=round(discount,2) if discount else None,
            discount_pct=round(pct,1) if pct else None, is_official_stock=True
        ))
    return out
