"""Direct Volvo Portugal national-stock connector."""
import re
import requests
from bs4 import BeautifulSoup
from urllib.parse import urljoin, urlparse
from search_poc.models import Vehicle

URL="https://www.volvocars.com/pt/inventory/"
BASE="https://www.volvocars.com"
HEADERS={
    "User-Agent":"Mozilla/5.0 (compatible; DEBE-Search-PoC/0.2)",
    "Accept-Language":"pt-PT,pt;q=0.9",
}


def _money(text):
    m=re.search(r"PRVP\s*([\d\s\xa0]+)\s*€",text or "",re.I)
    if not m:return None
    digits=re.sub(r"\D","",m.group(1))
    return float(digits) if digits else None


def _vehicle_block(anchor):
    """Return the smallest surrounding node that looks like one stock card."""
    node=anchor
    for _ in range(10):
        text=node.get_text("\n",strip=True)
        if "PRVP" in text and "Disponível em" in text and re.search(r"\b20\d{2}\b",text):
            return node
        node=getattr(node,"parent",None)
        if node is None:
            break
    return None


def _parse_inventory_html(html, limit=100):
    soup=BeautifulSoup(html,"html.parser")
    out=[]
    seen=set()

    # Volvo exposes a unique /shop/details/... link per stock vehicle. Using
    # that detail URL is essential: the inventory landing page is shared by
    # every car and therefore cannot be used as a deduplication identity.
    for a in soup.find_all("a",href=True):
        href=a.get("href","")
        if "/shop/details/" not in href:
            continue
        detail=urljoin(BASE,href)
        if detail in seen:
            continue

        block=_vehicle_block(a)
        if block is None:
            continue
        text=block.get_text("\n",strip=True)
        lines=[re.sub(r"\s+"," ",x).strip() for x in text.split("\n") if x.strip()]

        title=next((
            x for x in lines
            if re.match(r"^(?:XC|EX|EC|ES|V)\d{2}\b",x,re.I)
        ),"")
        if not title:
            continue

        price=_money(text)
        year_m=re.search(r"\b(20\d{2})\b",text)
        range_m=re.search(r"(\d+)\s*km\s+autonomia\s+el[eé]trica",text,re.I)
        avail_m=re.search(r"Dispon[ií]vel em\s+([^\n]+)",text,re.I)
        if not price or not year_m:
            continue

        parts=title.split(",",1)
        name=parts[0].strip()
        variant=parts[1].strip() if len(parts)>1 else ""
        body="SUV" if name.upper().startswith(("XC","EX")) else ("Wagon" if name.upper().startswith("V") else "")
        low_variant=variant.lower()
        fuel=(
            "Híbrido Plug-In" if "plug-in" in low_variant or "plug in" in low_variant
            else ("Elétrico" if name.upper().startswith(("EX","ES","EC")) else ("Híbrido" if "híbrido" in low_variant else ""))
        )

        path=urlparse(detail).path.rstrip("/")
        sid=path.split("/")[-1] or f"volvo-{len(out)}"
        out.append(Vehicle(
            source="volvo_inventory",
            source_id=sid,
            url=detail,
            make="Volvo",
            model=name,
            variant=variant,
            body=body,
            year=int(year_m.group(1)),
            mileage_km=0,
            price_eur=price,
            dealer="Volvo Portugal",
            fuel=fuel,
            electric_range_km=float(range_m.group(1)) if range_m else None,
            condition="new_stock",
            availability=("Disponível em "+avail_m.group(1).strip()) if avail_m else "",
            list_price_eur=price,
            is_official_stock=True,
        ))
        seen.add(detail)
        if len(out)>=limit:
            break
    return out


def fetch_inventory(timeout=15, limit=100):
    r=requests.get(URL,headers=HEADERS,timeout=timeout)
    r.raise_for_status()
    return _parse_inventory_html(r.text,limit=limit)
