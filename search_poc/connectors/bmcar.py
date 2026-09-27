"""BMcar inventory connector backed by BMcar's public vehicle API.

The BMcar Next.js frontend uses:
  GET https://api.bmcar.pt/vehicle/portal
  x-version: 2

Important: the frontend converts URL bracket parameters to arrays and its
serializer sends the API fields without [] for a single value. Using bracket
keys directly against the API causes those filters to be ignored.
"""
import re
import requests
from search_poc.models import Vehicle

API="https://api.bmcar.pt/vehicle/portal"
DETAIL_BASE="https://www.bmcar.pt/veiculos/"
HEADERS={
    "User-Agent":"Mozilla/5.0 (compatible; DEBE-Search-Beta/0.5)",
    "Accept":"application/json",
    "Accept-Language":"pt-PT,pt;q=0.9",
    "x-version":"2",
}

BMW_BRAND_ID="c427305a-a22d-433f-99dd-2198ccf858da"
HYBRID_PETROL_ID="9"
SERIE3_TOURING_SEGMENT_ID="9f2b387a-fa3a-4e24-554f-08d7d3ff7f58"


def _is_330e_touring(item):
    text=" ".join(str(item.get(k) or "") for k in (
        "name","modelName","brandSegmentName","version"
    )).lower()
    compact=re.sub(r"[^a-z0-9]","",text)
    return "330e" in compact and "touring" in text


def _condition(item):
    tags={str(x).lower() for x in (item.get("productTags") or [])}
    if "bmwpremium" in tags:
        return "used_certified"
    km=item.get("kilometers")
    if km is not None and km <= 100:
        return "km0"
    return "used"


def discover_bmw_330e_touring(limit=30, timeout=7):
    params={
        "page":1,
        "size":100,
        "brandIds":BMW_BRAND_ID,
        "engineTypeIds":HYBRID_PETROL_ID,
        "brandSegmentIds":SERIE3_TOURING_SEGMENT_ID,
    }
    r=requests.get(API,params=params,headers=HEADERS,timeout=timeout)
    r.raise_for_status()
    payload=r.json()
    data=payload.get("data") or {}
    items=data.get("items") or []

    out=[]
    for item in items:
        if not _is_330e_touring(item):
            continue

        current=item.get("priceCalculated")
        if current is None:
            current=item.get("price")
        list_price=item.get("price")
        try:
            current=float(current) if current is not None else None
        except (TypeError,ValueError):
            current=None
        try:
            list_price=float(list_price) if list_price is not None else None
        except (TypeError,ValueError):
            list_price=None

        # Only show a crossed-out list price when it is genuinely higher.
        discount_eur=None
        discount_pct=None
        shown_list=None
        if current is not None and list_price is not None and list_price > current:
            shown_list=list_price
            discount_eur=round(list_price-current,2)
            discount_pct=round(discount_eur/list_price*100,1)

        slug=str(item.get("slug") or "").strip("/")
        url=DETAIL_BASE+slug if slug else "https://www.bmcar.pt/veiculos"
        model_name=str(item.get("modelName") or "330e Touring")
        version=str(item.get("version") or "").strip()
        title=str(item.get("name") or f"BMW {model_name}").strip()
        if version and version.lower() not in title.lower():
            title=f"{title} {version}"

        out.append(Vehicle(
            source="bmcar",
            source_id=str(item.get("id") or item.get("referenceId") or slug),
            url=url,
            make="BMW",
            model="Série 3",
            variant=f"{model_name} {version}".strip(),
            body="Touring",
            year=int(item["year"]) if item.get("year") else None,
            mileage_km=int(item["kilometers"]) if item.get("kilometers") is not None else None,
            price_eur=current,
            dealer="BMcar",
            fuel="Híbrido Plug-In",
            power_cv=int(item["powerHp"]) if item.get("powerHp") else None,
            condition=_condition(item),
            list_price_eur=shown_list,
            discount_eur=discount_eur,
            discount_pct=discount_pct,
            is_official_stock=True,
        ))
        if len(out)>=limit:
            break
    return out
