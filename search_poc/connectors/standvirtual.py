"""Direct Standvirtual model-page discovery for the isolated DEBE Search PoC.

Avoids dependence on external search-engine indexing: Standvirtual's public
model result pages are server-rendered and expose listing cards/links directly.
"""
import re
import requests
from bs4 import BeautifulSoup
from urllib.parse import urljoin
from search_poc.models import Vehicle
from search_poc.query_validation import query_matches_text

BASE="https://www.standvirtual.com"
HEADERS={
    "User-Agent":"Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 Chrome/124 Safari/537.36",
    "Accept-Language":"pt-PT,pt;q=0.9,en;q=0.7",
}


def _money(text):
    vals=[float(re.sub(r"\D","",x)) for x in re.findall(r"(\d{1,3}(?:[ .]\d{3})+)\s*(?:EUR|€)",text or "",re.I)]
    vals=[x for x in vals if x>=3000]
    return vals[-1] if vals else None


def _km(text):
    m=re.search(r"(\d{1,3}(?:[ .]\d{3})*)\s*km\b",text or "",re.I)
    return int(re.sub(r"\D","",m.group(1))) if m else None


def _year(text):
    years=[int(x) for x in re.findall(r"\b(20(?:0\d|1\d|2\d))\b",text or "")]
    return years[0] if years else None


def _listing_id(url):
    m=re.search(r"-ID([A-Za-z0-9]+)\.html",url or "",re.I)
    return m.group(1) if m else url.rstrip("/").split("/")[-1]


def _dealer(card):
    lines=[re.sub(r"\s+"," ",x).strip() for x in card.get_text("\n",strip=True).split("\n") if x.strip()]
    for i,line in enumerate(lines):
        if line.lower() in {"ver anúncios","ver anuncios"}:
            for nxt in lines[i+1:i+4]:
                low=nxt.lower()
                if not any(x in low for x in ("financiamento","lavagem","entrega","oficina","publicado","para o topo","ad link")):
                    return nxt.lstrip("* ").strip()
    return ""


def _card_for_anchor(a):
    card=a.find_parent("article")
    if card is not None:
        return card
    node=a
    for _ in range(9):
        node=getattr(node,"parent",None)
        if node is None:break
        txt=node.get_text(" ",strip=True)
        if len(txt)>15000:break
        if re.search(r"\bkm\b",txt,re.I) and re.search(r"(?:EUR|€)",txt,re.I):
            return node
    return None


def _route_for_query(query):
    q=(query or "").lower()
    if "bmw" in q:
        pairs=[
            ("série 3","serie-3"),("serie 3","serie-3"),("ix3","ix3"),
            ("x1","x1"),("x3","x3"),("x5","x5"),("i4","i4"),("i5","i5"),("ix","ix"),
        ]
        for token,slug in pairs:
            if token in q:return f"{BASE}/carros/bmw/{slug}"
    if "mercedes" in q:
        # Standvirtual exposes a narrower GLC 300 route. Using it for 300 e/de
        # avoids depending on which promoted GLC rows happen to land in the
        # first few pages of the broad /glc inventory.
        if "glc" in q and re.search(r"\\b300\\s*(?:de|e)\\b",q):
            return f"{BASE}/carros/mercedes-benz/glc-300?search%5Bfilter_enum_engine_code%5D=classe-glc"
        for token,slug in (("glc","glc"),("gla","gla"),("gle","gle"),("classe c","classe-c"),("classe e","classe-e")):
            if token in q:return f"{BASE}/carros/mercedes-benz/{slug}"
    if "audi" in q:
        # A4/A6 Avant have dedicated result routes and otherwise get diluted
        # by saloons when a station-wagon body is requested.
        station=any(x in q for x in ("avant","station","wagon","carrinha","estate"))
        if "a4" in q and station:return f"{BASE}/carros/audi/a4-avant"
        if "a6" in q and station:return f"{BASE}/carros/audi/a6-avant"
        for token in ("q5","q4","q3","a6","a5","a4","a3"):
            if token in q:return f"{BASE}/carros/audi/{token}"
    if "volvo" in q:
        # Standvirtual uses hyphenated XC/EX slugs (xc-60, ex-30, ...).
        pairs=(
            ("xc60","xc-60"),("xc40","xc-40"),("xc90","xc-90"),
            ("ex30","ex-30"),("ex40","ex-40"),("v60","v60"),("v90","v90"),
        )
        for token,slug in pairs:
            if token in q:return f"{BASE}/carros/volvo/{slug}"
    return ""


def discover_rows(query, limit=40, timeout=12, validate=True, max_pages=3):
    route=_route_for_query(query)
    if not route:return []
    by_url={}
    for page in range(1,max_pages+1):
        params=None if page==1 else {"page":page}
        try:
            r=requests.get(route,params=params,headers=HEADERS,timeout=timeout)
            r.raise_for_status()
        except Exception:
            if page==1: raise
            break
        soup=BeautifulSoup(r.text,"html.parser")
        page_urls=set()
        for a in soup.find_all("a",href=True):
            href=a.get("href","")
            if "/carros/anuncio/" not in href:continue
            url=urljoin(BASE,href.split("?")[0])
            page_urls.add(url)
            card=_card_for_anchor(a)
            if card is None:continue
            text=card.get_text("\n",strip=True)
            if not _km(text) or not _money(text):continue
            heading=card.find(["h1","h2","h3"])
            title=heading.get_text(" ",strip=True) if heading else a.get_text(" ",strip=True)
            if not title or len(title)<4:
                title=next((x.strip() for x in text.split("\n") if len(x.strip())>6),"")
            candidate={
                "source_key":"standvirtual","source":"Standvirtual — benchmark","official":False,
                "title":title,"snippet":re.sub(r"\s+"," ",text)[:500],"url":url,
                "condition":"used","availability":"","price_eur":_money(text),
                "list_price_eur":None,"discount_eur":None,"discount_pct":None,
                "conditional_price_eur":None,"price_condition":"",
                "mileage_km":_km(text),"year":_year(text),"dealer":_dealer(card),
                "discovery":"marketplace_direct",
            }
            if validate and not query_matches_text(query,candidate["title"],candidate["snippet"]):
                continue
            old=by_url.get(url)
            if old is None or len(candidate["title"])>len(old.get("title","")):
                by_url[url]=candidate
            if len(by_url)>=limit:
                return list(by_url.values())
        # Stop if pagination loops back to a page already represented entirely
        # by URLs we have seen; prevents needless traffic on one-page models.
        if page>1 and page_urls and all(u in by_url for u in page_urls) and not validate:
            break
    return list(by_url.values())


def discover_bmw_330e_touring(limit=40, timeout=12):
    rows=discover_rows("BMW Série 3 330e Touring",limit=max(limit*3,80),timeout=timeout)
    out=[]
    for row in rows:
        blob=(row.get("title","")+" "+row.get("snippet","")).lower()
        compact=re.sub(r"\s+","",blob)
        if "330e" not in compact:continue
        if not any(x in blob for x in ("carrinha","touring","station","wagon")):continue
        if "plug-in" not in blob and "híbrido" not in blob and "hibrido" not in blob:continue
        out.append(Vehicle(
            source="standvirtual",source_id=str(_listing_id(row["url"])),url=row["url"],
            make="BMW",model="Série 3",variant=row["title"],body="Touring",
            year=row["year"],mileage_km=row["mileage_km"],price_eur=row["price_eur"],
            dealer=row["dealer"],fuel="Híbrido Plug-In",power_cv=292,condition="used",
        ))
        if len(out)>=limit:break
    return out
