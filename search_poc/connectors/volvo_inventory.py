"""Volvo Portugal national stock connector."""
import re
import requests
from bs4 import BeautifulSoup
from search_poc.models import Vehicle

URL="https://www.volvocars.com/pt/inventory/"
HEADERS={"User-Agent":"Mozilla/5.0 (compatible; DEBE-Search-PoC/0.1)","Accept-Language":"pt-PT,pt;q=0.9"}

def fetch_inventory(timeout=15, limit=100):
    r=requests.get(URL,headers=HEADERS,timeout=timeout); r.raise_for_status()
    text=BeautifulSoup(r.text,"html.parser").get_text("\n",strip=True)
    pattern=re.compile(
        r"Disponível em\s+(?P<eta>[^\n]+)\n"
        r"(?P<model>[^\n]+)\n"
        r"(?P<year>20\d{2})\s*•\s*(?P<range>\d+)\s*km autonomia elétrica.*?"
        r"PRVP\s*(?P<price>[\d\s]+)\s*€",
        re.S
    )
    out=[]
    for i,m in enumerate(pattern.finditer(text)):
        if i>=limit: break
        model=m.group("model").strip()
        parts=model.split(",",1)
        name=parts[0].strip()
        variant=parts[1].strip() if len(parts)>1 else ""
        price=float(re.sub(r"\D","",m.group("price")))
        body="SUV" if name.startswith(("XC","EX")) else ("Wagon" if name.startswith("V") else "")
        fuel="Híbrido Plug-In" if "Híbrido Plug-in" in variant else ("Elétrico" if any(x in name for x in ("EX","ES","EC")) else "")
        out.append(Vehicle(
            source="volvo_inventory", source_id=f"volvo-{i}", url=URL,
            make="Volvo", model=name, variant=variant, body=body,
            year=int(m.group("year")), mileage_km=0, price_eur=price,
            fuel=fuel, electric_range_km=float(m.group("range")),
            condition="new_stock", availability="Disponível em "+m.group("eta").strip(),
            list_price_eur=price, is_official_stock=True
        ))
    return out
