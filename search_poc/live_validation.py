import json
import time

from search_poc.connectors.bmw_premium import fetch_bmw_330e_touring
from search_poc.connectors.bmcar import inventory_summary_bmw_330e_touring
from search_poc.connectors.standvirtual import discover_bmw_330e_touring
from search_poc.connectors.mercedes_certified import discover_glc_300e_suv
from search_poc.connectors.carclasse import discover_glc_300e
from search_poc.connectors.volvo_inventory import fetch_inventory
from search_poc.beta_engine import search_all, _dedup


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
        "glc":raw_page("https://www.standvirtual.com/carros/mercedes-benz/glc-300?search%5Bfilter_enum_engine_code%5D=classe-glc","300 e"),
        "a4":raw_page("https://www.standvirtual.com/carros/audi/a4-avant","40 tdi"),
        "xc60":raw_page("https://www.standvirtual.com/carros/volvo/xc-60","t6"),
    })
    from search_poc.connectors.standvirtual import discover_rows as sv_rows
    from search_poc.connectors.bmw_premium_generic import discover_rows as bps_generic_rows
    from search_poc.query_validation import query_matches_text
    report["glc_raw_matches"]=safe("glc_raw_matches",lambda:[
        {"title":r.get("title"),"snippet":r.get("snippet"),"match":query_matches_text("Mercedes-Benz GLC 300 e SUV",r.get("title",""),r.get("snippet",""))}
        for r in sv_rows("Mercedes-Benz GLC 300 e SUV",limit=200,timeout=10,validate=False)
        if "glc" in (r.get("title","")+" "+r.get("snippet","")).lower()
    ])
    report["diagnostic_samples"]=safe("samples",lambda:{
        "glc": [{k:r.get(k) for k in ("title","snippet","year","mileage_km","price_eur","dealer")} for r in sv_rows("Mercedes-Benz GLC 300 e SUV",limit=12,timeout=10)],
        "x1": [{k:r.get(k) for k in ("title","snippet","year","mileage_km","price_eur","dealer")} for r in sv_rows("BMW X1 xDrive30e SUV",limit=12,timeout=10)],
        "a4": [{k:r.get(k) for k in ("title","snippet","year","mileage_km","price_eur","dealer")} for r in sv_rows("Audi A4 40 TDI Avant",limit=12,timeout=10)],
        "xc60": [{k:r.get(k) for k in ("title","snippet","year","mileage_km","price_eur","dealer")} for r in sv_rows("Volvo XC60 T6 SUV",limit=12,timeout=10)],
        "bps_ix3": bps_generic_rows("BMW iX3",timeout=10),
        "bps_x1": bps_generic_rows("BMW X1 xDrive30e SUV",timeout=10),
    })
    def ix3_overlap():
        sv=sv_rows("BMW iX3",limit=120,timeout=10)
        bps=bps_generic_rows("BMW iX3",timeout=10)
        merged=_dedup(bps+sv)
        overlaps=[
            {"title":r.get("title"),"year":r.get("year"),"mileage_km":r.get("mileage_km"),
             "price_eur":r.get("price_eur"),"dealer":r.get("dealer"),
             "sources":[x.get("source_key") for x in r.get("occurrences",[])]}
            for r in merged if len(r.get("occurrences",[]))>1
        ]
        return {"bps":len(bps),"standvirtual":len(sv),"merged":len(merged),"duplicates":overlaps}
    report["ix3_overlap"]=safe("ix3_overlap",ix3_overlap)
    report["bmw_330e_bps"]=safe("bps",lambda:len(fetch_bmw_330e_touring(timeout=12)))
    report["bmw_330e_bmcar"]=safe("bmcar",lambda:inventory_summary_bmw_330e_touring(timeout=9))
    report["bmw_330e_standvirtual"]=safe("standvirtual",lambda:len(discover_bmw_330e_touring(limit=30,timeout=9)))
    report["mercedes_glc300e_certified"]=safe("mb_certified",lambda:len(discover_glc_300e_suv(timeout=5)))
    report["mercedes_glc300e_carclasse"]=safe("carclasse",lambda:len(discover_glc_300e(timeout=7)))
    report["volvo_inventory_model_route"]=safe("volvo_model_route",lambda:raw_page(
        "https://www.volvocars.com/pt/inventory/xc60-hybrid/","XC60 Core"
    ))
    report["volvo_inventory_direct"]=safe("volvo_inventory",lambda:[
        {k:d.get(k) for k in ("source_id","url","model","variant","year","price_eur","electric_range_km","availability")}
        for d in (v.to_dict() for v in fetch_inventory(timeout=10,limit=20))
    ])

    for query in (
        "BMW Série 3 330e Touring",
        "BMW iX3",
        "BMW X1 xDrive30e SUV",
        "Mercedes-Benz GLC 300 e SUV",
        "Audi A4 40 TDI Avant",
        "Volvo XC60 T6 SUV",
    ):
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
