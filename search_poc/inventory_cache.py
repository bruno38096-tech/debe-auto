"""Read periodically refreshed vehicle facts without network latency.

Availability is not guaranteed: prices/stock must be rechecked at advertiser.
Expired rows are not silently treated as current inventory.
"""
from datetime import datetime, timezone, timedelta
from functools import lru_cache
from pathlib import Path
import json

SNAPSHOT_FILE=Path(__file__).with_name("inventory_snapshot.json")
MAX_AGE=timedelta(hours=72)


@lru_cache(maxsize=1)
def read_inventory():
    try:
        obj=json.loads(SNAPSHOT_FILE.read_text(encoding="utf-8"))
        return obj if isinstance(obj,dict) else {}
    except (OSError,ValueError):
        return {}


def model_inventory(make,model):
    snapshot=read_inventory()
    rows=snapshot.get("entries",{}).get(str(make)+"|"+str(model),[])
    if not isinstance(rows,list):return []
    now=datetime.now(timezone.utc)
    fresh=[]
    for candidate in rows:
        if not isinstance(candidate,dict):continue
        stamp=candidate.get("observed_at") or ""
        try:
            dt=datetime.fromisoformat(stamp)
            if dt.tzinfo is None or now-dt>MAX_AGE or now<dt-timedelta(minutes=10):
                continue
        except (TypeError,ValueError):
            continue
        if not candidate.get("url","").startswith("https://"):
            continue
        fresh.append(dict(candidate))
    return fresh
