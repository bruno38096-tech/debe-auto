import json
from search_poc.connectors.bmw_new_stock import bmw_330e_touring_list_price, caetano_330e_touring_stock
from search_poc.connectors.bmw_premium import fetch_bmw_330e_touring
from search_poc.connectors.bmcar import discover_bmw_330e_touring as bmcar
from search_poc.connectors.standvirtual import discover_bmw_330e_touring as standvirtual
from search_poc.dedup import cross_source_matches


def main():
    list_price=bmw_330e_touring_list_price()
    new_stock=caetano_330e_touring_stock()
    certified=fetch_bmw_330e_touring()
    dealer=bmcar()
    market=standvirtual()

    # Enrich existing used/certified records without changing original connectors.
    for v in certified:
        v.condition="used_certified"; v.is_official_stock=True
        if list_price and v.price_eur:
            v.list_price_eur=list_price
            v.discount_eur=round(list_price-v.price_eur,2)
            v.discount_pct=round((list_price-v.price_eur)/list_price*100,1)
    for v in dealer:
        v.condition="used" if (v.mileage_km or 0)>1000 else "km0"
    for v in market:
        v.condition="used" if (v.mileage_km or 0)>1000 else "km0"

    payload={
      "query":"BMW 330e Touring - any condition",
      "new_list_price_eur":list_price,
      "counts":{
        "official_new_stock_leads":len(new_stock),
        "bmw_certified":len(certified),
        "bmcar":len(dealer),
        "standvirtual_discovered_lower_bound":len(market),
      },
      "cross_source_matches":{
        "certified_vs_standvirtual":[m.__dict__ for m in cross_source_matches(certified,market)],
        "bmcar_vs_standvirtual":[m.__dict__ for m in cross_source_matches(dealer,market)],
      },
      "vehicles":{
        "new_stock":[v.to_dict() for v in new_stock],
        "certified":[v.to_dict() for v in certified],
        "bmcar":[v.to_dict() for v in dealer],
        "standvirtual":[v.to_dict() for v in market],
      }
    }
    print(json.dumps(payload,ensure_ascii=False,indent=2))


if __name__=="__main__":
    main()
