"""BMcar inventory connector for DEBE Search beta.

Uses the same public API as bmcar.pt:
  GET https://api.bmcar.pt/vehicle/portal
  x-version: 2

Important: the BMcar web filter supplied by the user selects BMW + Hybrid
Petrol + Série 3 Touring. That includes 320e and 330e. DEBE then keeps only
exact 330e Touring matches when the user selected 330e.
"""
import requests
from search_poc.models import Vehicle

API="https://api.bmcar.pt/vehicle/portal"
BASE="https://www.bmcar.pt/veiculos/"
HEADERS={
    "User-Agent":"Mozilla/5.0 (compatible; DEBE-Search-Beta/0.5)",
    "Accept":"application/json",
    "Accept-Language":"pt-PT,pt;q=0.9",
    "x-version":"2",
}

BMW_BRAND_ID="c427305a-a22d-433f-99dd-2198ccf858da"
HYBRID_PETROL_ID="9"
SERIE3_TOURING_SEGMENT_ID="9f2b387a-fa3a-4e24-554f-08d7d3ff7f58"


def _fetch_inventory(timeout=7):
    # NB: BMcar's API expects scalar query keys for these single selected values.
    # Sending brandIds[]/engineTypeIds[]/brandSegmentIds[] causes the API to
    # ignore the filters and return the full catalogue.
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
    data=payload.get("data",{}) if isinstance(payload,dict) else {}
    return data.get("items",[]) if isinstance(data,dict) else []


def _is_exact_330e_touring(item):
    name=(item.get("name") or "").lower().replace(" ","")
    model=(item.get("modelName") or "").lower().replace(" ","")
    segment=(item.get("brandSegmentName") or "").lower()
    return ("330e" in name or "330e" in model) and "touring" in (name+model+segment)


def _vehicle_from_api(item):
    slug=item.get("slug") or ""
    if not slug:
        return None

    # BMcar's current public API exposes both price and priceCalculated.
    # priceCalculated is the value to present when a campaign/discount is active.
    raw_price=item.get("price")
    calculated=item.get("priceCalculated")
    current=calculated if isinstance(calculated,(int,float)) and calculated>0 else raw_price
    list_price=None
    discount_eur=None
    discount_pct=None
    if isinstance(raw_price,(int,float)) and isinstance(current,(int,float)) and raw_price>current:
        list_price=float(raw_price)
        discount_eur=round(float(raw_price-current),2)
        discount_pct=round(discount_eur/float(raw_price)*100,1)

    tags=item.get("productTags") or []
    condition="used_certified" if "BmwPremium" in tags else (
        "new_stock" if (item.get("kilometers") or 0)<=100 else "used"
    )

    return Vehicle(
        source="bmcar",
        source_id=str(item.get("id") or item.get("referenceId") or slug),
        url=BASE+slug,
        make="BMW",
        model="Série 3",
        variant=(item.get("name") or item.get("modelName") or "330e Touring").replace("BMW ","").strip(),
        body="Touring",
        year=item.get("year"),
        mileage_km=item.get("kilometers"),
        price_eur=float(current) if isinstance(current,(int,float)) and current>0 else None,
        dealer="BMcar",
        fuel="Híbrido Plug-In",
        power_cv=item.get("powerHp"),
        condition=condition,
        list_price_eur=list_price,
        discount_eur=discount_eur,
        discount_pct=discount_pct,
        is_official_stock=True,
    )


def discover_bmw_330e_touring(limit=20, timeout=7):
    try:
        items=_fetch_inventory(timeout=timeout)
    except Exception:
        return []

    out=[]
    for item in items:
        if not isinstance(item,dict) or not _is_exact_330e_touring(item):
            continue
        v=_vehicle_from_api(item)
        if v:
            out.append(v)
    return out[:limit]
