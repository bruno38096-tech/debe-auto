import json
from search_poc.connectors.audi_immediate import fetch_a6_avant_etron
from search_poc.connectors.volvo_inventory import fetch_inventory
from search_poc.connectors.bmw_new_stock import caetano_330e_touring_stock

def main():
    audi=fetch_a6_avant_etron()
    volvo=fetch_inventory()
    bmw=caetano_330e_touring_stock()
    biggest=sorted(
        [v for v in audi if v.discount_eur],
        key=lambda v:v.discount_eur or 0, reverse=True
    )
    print(json.dumps({
        "counts":{"bmw_stock_leads":len(bmw),"audi_immediate":len(audi),"volvo_inventory":len(volvo)},
        "largest_explicit_discounts":[v.to_dict() for v in biggest[:10]],
        "bmw":[v.to_dict() for v in bmw],
        "audi":[v.to_dict() for v in audi],
        "volvo":[v.to_dict() for v in volvo],
    },ensure_ascii=False,indent=2))

if __name__=="__main__":
    main()
