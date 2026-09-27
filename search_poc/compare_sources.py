import json
from search_poc.connectors.bmw_premium import fetch_bmw_330e_touring
from search_poc.connectors.standvirtual import discover_bmw_330e_touring as standvirtual
from search_poc.connectors.bmcar import discover_bmw_330e_touring as bmcar
from search_poc.dedup import cross_source_matches


def main():
    official=fetch_bmw_330e_touring()
    market=standvirtual()
    dealer=bmcar()
    payload={
        "query":"BMW 330e Touring",
        "counts":{
            "bmw_premium_selection":len(official),
            "standvirtual_discovered_lower_bound":len(market),
            "bmcar":len(dealer),
        },
        "matches":{
            "official_vs_standvirtual":[m.__dict__ for m in cross_source_matches(official,market)],
            "official_vs_bmcar":[m.__dict__ for m in cross_source_matches(official,dealer)],
            "bmcar_vs_standvirtual":[m.__dict__ for m in cross_source_matches(dealer,market)],
        },
        "vehicles":{
            "official":[v.to_dict() for v in official],
            "standvirtual":[v.to_dict() for v in market],
            "bmcar":[v.to_dict() for v in dealer],
        }
    }
    print(json.dumps(payload,ensure_ascii=False,indent=2))


if __name__=="__main__":
    main()
