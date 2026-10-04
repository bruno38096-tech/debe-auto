"""Direct PiscaPisca model-page connector for DEBE Search beta."""
import re
from urllib.parse import urljoin
import requests
from bs4 import BeautifulSoup

from search_poc.query_validation import query_matches_text

BASE="https://www.piscapisca.pt"
HEADERS={
    "User-Agent":"Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 Chrome/124 Safari/537.36",
    "Accept-Language":"pt-PT,pt;q=0.9",
}


def _ascii(s):
    import unicodedata
    return unicodedata.normalize("NFKD",s or "").encode("ascii","ignore").decode().lower()


def _route_for_query(query):
    q=_ascii(query)
    if "bmw" in q:
        if "ix3" in q:return f"{BASE}/carros/bmw/ix3"
        if re.search(r"\bx1\b",q):return f"{BASE}/carros/bmw/x1"
        if "serie 3" in q or re.search(r"\b3(?:30|20|18|16)[a-z]?\b",q):
            return f"{BASE}/carros/bmw/serie-3"
    if "mercedes" in q and "glc" in q:
        return f"{BASE}/carros/mercedes-benz/glc"
    if "audi" in q:
        if "a4" in q and any(x in q for x in ("avant","carrinha","station","wagon","estate")):
            return f"{BASE}/carros/audi/a4-avant"
        if "a4" in q:return f"{BASE}/carros/audi/a4"
        for model in ("a3","a5","a6","q3","q5","q7","q8"):
            if re.search(rf"\b{model}\b",q):
                return f"{BASE}/carros/audi/{model}"
    if "volvo" in q:
        for model in ("xc60","xc40","xc90","ex30","ex40","v60","v90"):
            if model in q:return f"{BASE}/carros/volvo/{model}"
    if "porsche" in q:
        for model in ("911","718","cayman","boxster","macan","cayenne","taycan"):
            if model in q:return f"{BASE}/carros/porsche/{model}"
    return ""


def _card_block(anchor):
    node=anchor
    for _ in range(8):
        text=node.get_text(" ",strip=True)
        if "€" in text and re.search(r"\b20\d{2}\b",text) and re.search(r"[\d\.\s\xa0]+\s*km\b",text,re.I):
            # Avoid climbing into the whole results list when a smaller card exists.
            if len(text)<3500:
                return node
        node=getattr(node,"parent",None)
        if node is None:break
    return None


def _parse_listing_html(html, query="", limit=80):
    soup=BeautifulSoup(html,"html.parser")
    out=[]; seen=set()
    for a in soup.find_all("a",href=True):
        href=a.get("href","")
        if "/carros/usados/" not in href:
            continue
        url=urljoin(BASE,href.split("?")[0])
        if url in seen:continue

        label=re.sub(r"\s+"," ",a.get_text(" ",strip=True)).strip()
        km_m=re.search(r"([\d\.\s\xa0]+)\s*km\b",label,re.I)
        yr_m=re.search(r"\b(20\d{2})\b",label)
        if not km_m or not yr_m:
            continue

        block=_card_block(a)
        if block is None:continue
        block_text=re.sub(r"\s+"," ",block.get_text(" ",strip=True)).strip()
        price_m=re.search(r"([\d\.\s\xa0]{4,})\s*€",block_text)
        if not price_m:continue

        title=label[:km_m.start()].strip(" -·")
        if not title:continue
        if query and not query_matches_text(query,title,label):
            continue

        price_digits=re.sub(r"\D","",price_m.group(1))
        km_digits=re.sub(r"\D","",km_m.group(1))
        if not price_digits or not km_digits:continue

        low=_ascii(title+" "+label)
        body=(
            "station" if any(x in low for x in ("avant","touring","carrinha","wagon","estate"))
            else ("suv" if any(x in low for x in ("glc","xc60","xc40","xc90","x1","x3","x5","q3","q5","q7","q8")) else "")
        )
        out.append({
            "source_key":"piscapisca",
            "source":"PiscaPisca — benchmark",
            "official":False,
            "title":title,
            "snippet":label[:420],
            "url":url,
            "condition":"used",
            "availability":"",
            "price_eur":float(price_digits),
            "list_price_eur":None,
            "conditional_price_eur":None,
            "price_condition":"",
            "discount_eur":None,
            "discount_pct":None,
            "mileage_km":int(km_digits),
            "year":int(yr_m.group(1)),
            "dealer":"",
            "body":body,
            "discovery":"direct_connector",
        })
        seen.add(url)
        if len(out)>=limit:break
    return out


def discover_rows(query, limit=80, timeout=7, pages=2):
    route=_route_for_query(query)
    if not route:return []
    out=[]; seen=set()
    for page in range(1,max(1,pages)+1):
        url=route if page==1 else f"{route}?page={page}"
        try:
            r=requests.get(url,headers=HEADERS,timeout=timeout)
            r.raise_for_status()
        except Exception:
            continue
        for row in _parse_listing_html(r.text,query=query,limit=limit):
            if row["url"] in seen:continue
            seen.add(row["url"]); out.append(row)
            if len(out)>=limit:return out
    return out
