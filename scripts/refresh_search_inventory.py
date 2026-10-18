"""Low-frequency public model inventory snapshot generator for DEBE Search.

Designed to run once per day on a CI runner, not on each user web request.
Stores *only* linked vehicle facts, never page text. No fabricated listings.
"""
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime, timezone, timedelta
from pathlib import Path
import json
import os
import sys
import time

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))
from search_poc.vehicle_catalog import CATALOG, canonical_query
from search_poc.vehicle_identity import spec_matches
from search_poc.connectors.standvirtual import discover_rows

DEST=ROOT/"search_poc"/"inventory_snapshot.json"
now=datetime.now(timezone.utc)
timestamp=now.isoformat(timespec="seconds")
stale_cutoff=now-timedelta(hours=72)


def load_previous():
    if not DEST.exists():return {}
    try:return json.loads(DEST.read_text(encoding="utf-8")).get("entries",{})
    except (OSError,ValueError):return {}


def key(make,model):
    return make+"|"+model


def valid_old(row):
    try:
        observed=datetime.fromisoformat(row["observed_at"])
        return observed.tzinfo is not None and observed>=stale_cutoff
    except (ValueError,TypeError,KeyError):return False


def supplemental_rows(make, model):
    """Representative manufacturer and variant directories for incomplete model feeds.

    Sources are never treated as inventory without individual advert links and
    independently extracted year, odometer and published price.
    """
    extra=[]
    if make=="Audi" and model=="A5":
        from search_poc.connectors.standvirtual import _reader_rows
        # Modern Audi A5 e-hybrid is categorised under Avant/Limousine,
        # not the historic /a5 generic inventory dominated by TDI/TFSI.
        for slug in ("a5-avant","a5-limousine"):
            try:
                extra.extend(_reader_rows(
                    "https://www.standvirtual.com/carros/audi/"+slug+
                    "?search%5Bfilter_enum_fuel_type%5D=plugin-hybrid",
                    "",timeout=10,limit=45,validate=False))
            except Exception as exc:
                print("A5_EHYBRID_FEED_ERROR",slug,str(exc)[:120],flush=True)
    if make=="BMW" and model=="Série 3":
        try:
            from search_poc.connectors.bmw_reader_fallback import discover_rows as bmw_offers
            extra.extend(bmw_offers(timeout=12))
        except Exception as exc:
            print("BMW_OFFICIAL_FEED_ERROR",str(exc)[:160],flush=True)
    if make=="Mercedes-Benz" and model=="GLC":
        from search_poc.connectors.standvirtual import _reader_rows
        for slug in ("glc-300","glc-63"):
            try:
                extra.extend(_reader_rows(
                    "https://www.standvirtual.com/carros/mercedes-benz/"+slug,
                    "",timeout=12,limit=50,validate=False))
            except Exception as exc:
                print("GLC_VARIANT_FEED_ERROR",slug,str(exc)[:130],flush=True)
    if make=="Porsche" and model=="911":
        try:
            from search_poc.connectors.standvirtual import _reader_rows
            extra.extend(_reader_rows(
                "https://www.standvirtual.com/carros/porsche/911-carrera",
                "",timeout=12,limit=40,validate=False))
        except Exception as exc:
            print("PORSCHE_911_FEED_ERROR",str(exc)[:130],flush=True)
    return extra


def harvest(pair):
    make,model=pair
    query=canonical_query(make,model,"","all")
    try:
        rows=discover_rows(query,limit=55,timeout=6,max_pages=1,
                           make=make,model=model,body="all")
    except Exception as exc:
        print("FEED_ERROR",make,model,str(exc)[:120],flush=True)
        rows=[]
    rows.extend(supplemental_rows(make,model))
    out=[];seen=set()
    for row in rows:
        if not spec_matches(make,model,"","all",row):
            continue
        url=row.get("url") or ""
        if not url.startswith("https://") or url in seen:
            continue
        if row.get("price_eur") is None or row.get("year") is None:
            continue
        seen.add(url)
        out.append({
            "title":row.get("title",""),"url":url,
            "year":row.get("year"),"mileage_km":row.get("mileage_km"),
            "price_eur":row.get("price_eur"),"condition":row.get("condition") or "used",
            "source_key":row.get("source_key") or "standvirtual",
            "source":row.get("source") or "Standvirtual — última observação",
            "official":bool(row.get("official")),"dealer":row.get("dealer") or "",
            "discovery":"scheduled_snapshot","observed_at":timestamp,
        })
        if len(out)>=40:break
    return key(make,model),out


def main():
    previous=load_previous()
    pairs=[(make,model) for make,entry in CATALOG.items()
           for model in entry["models"]]
    limit=int(os.getenv("DEBE_INVENTORY_LIMIT","0") or 0)
    if limit>0:pairs=pairs[:limit]
    print("CATALOG_MODELS",len(pairs),flush=True)
    collected={}
    good=0;failed=0
    # Conservative parallelism to avoid overwhelming public sources.
    with ThreadPoolExecutor(max_workers=3) as pool:
        futures=[pool.submit(harvest,pair) for pair in pairs]
        for future in as_completed(futures):
            label,rows=future.result()
            if rows:
                collected[label]=rows
                good+=1
            else:
                old=[r for r in previous.get(label,[]) if valid_old(r)]
                collected[label]=old
                failed+=1
            print("MODEL",label,"new",len(rows),"kept_old",len(collected[label])-len(rows),flush=True)
    if good<3 and not any(collected.values()):
        raise RuntimeError("Insufficient verified public listing data; retaining previous snapshot")
    snapshot={
        "generated_at":timestamp,
        "model_count":len(pairs),
        "models_fresh":good,
        "models_without_fresh":failed,
        "vehicle_count":sum(len(rows) for rows in collected.values()),
        "entries":collected,
    }
    # One atomic replace; a failed run must never erase existing verified offers.
    temporary=DEST.with_suffix(".json.tmp")
    temporary.write_text(json.dumps(snapshot,ensure_ascii=False,separators=(",",":")),encoding="utf-8")
    temporary.replace(DEST)
    print("SNAPSHOT",json.dumps({k:v for k,v in snapshot.items() if k!="entries"}),flush=True)


if __name__=="__main__":main()
