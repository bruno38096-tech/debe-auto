import json
import time

from search_poc.connectors.bmw_premium import fetch_bmw_330e_touring
from search_poc.connectors.bmcar import inventory_summary_bmw_330e_touring
from search_poc.connectors.standvirtual import discover_bmw_330e_touring
from search_poc.connectors.mercedes_certified import discover_glc_300e_suv
from search_poc.connectors.carclasse import discover_glc_300e
from search_poc.beta_engine import search_all


def safe(name, fn):
    started=time.time()
    try:
        value=fn()
        return {"ok":True,"elapsed_s":round(time.time()-started,2),"value":value}
    except Exception as exc:
        return {"ok":False,"elapsed_s":round(time.time()-started,2),"error":repr(exc)[:300]}


def main():
    report={}
    def raw_page(url, needle):
        import requests
        r=requests.get(url,headers={"User-Agent":"Mozilla/5.0","Accept-Language":"pt-PT,pt;q=0.9"},timeout=10)
        low=r.text.lower()
        return {"status":r.status_code,"length":len(r.text),"needle":needle.lower() in low,"listing_links":low.count("/carros/anuncio/"),"url":r.url}
    report["standvirtual_raw_pages"]=safe("standvirtual_raw",lambda:{
        "ix3":raw_page("https://www.standvirtual.com/carros/bmw/ix3","ix3"),
        "x1":raw_page("https://www.standvirtual.com/carros/bmw/x1","xdrive30e"),
        "glc":raw_page("https://www.standvirtual.com/carros/mercedes-benz/glc","300 e"),
    })
    from search_poc.connectors.standvirtual import discover_rows as sv_rows
    from search_poc.connectors.bmw_premium_generic import discover_rows as bps_generic_rows
    report["diagnostic_samples"]=safe("samples",lambda:{
        "glc": [{k:r.get(k) for k in ("title","snippet","year","mileage_km","price_eur","dealer")} for r in sv_rows("Mercedes-Benz GLC 300 e SUV",limit=12,timeout=10)],
        "x1": [{k:r.get(k) for k in ("title","snippet","year","mileage_km","price_eur","dealer")} for r in sv_rows("BMW X1 xDrive30e SUV",limit=12,timeout=10)],
        "bps_ix3": bps_generic_rows("BMW iX3",timeout=10),
        "bps_x1": bps_generic_rows("BMW X1 xDrive30e SUV",timeout=10),
    })
    report["bmw_330e_bps"]=safe("bps",lambda:len(fetch_bmw_330e_touring(timeout=12)))
    report["bmw_330e_bmcar"]=safe("bmcar",lambda:inventory_summary_bmw_330e_touring(timeout=9))
    report["bmw_330e_standvirtual"]=safe("standvirtual",lambda:len(discover_bmw_330e_touring(limit=30,timeout=9)))
    report["mercedes_glc300e_certified"]=safe("mb_certified",lambda:len(discover_glc_300e_suv(timeout=5)))
    report["mercedes_glc300e_carclasse"]=safe("carclasse",lambda:len(discover_glc_300e(timeout=7)))

    for query in ("BMW iX3","BMW X1 xDrive30e SUV","Mercedes-Benz GLC 300 e SUV"):
        hit=safe(query,lambda q=query:search_all(q,max_per_source=3))
        if hit["ok"]:
            payload=hit["value"]
            hit["value"]={
                "summary":payload.get("summary"),
                "sources":[
                    {k:s.get(k) for k in ("key","count","status","rejected_irrelevant")}
                    for s in payload.get("sources",[]) if s.get("count") or s.get("rejected_irrelevant")
                ],
                "results":[
                    {k:r.get(k) for k in ("source_key","title","year","mileage_km","price_eur","conditional_price_eur","dealer","url")}
                    for r in payload.get("results",[])[:10]
                ],
            }
        report["search_all:"+query]=hit

    print(json.dumps(report,ensure_ascii=False,indent=2,default=str))


if __name__=="__main__":
    main()
