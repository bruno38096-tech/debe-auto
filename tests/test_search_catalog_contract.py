"""Exhaustive, deterministic HTTP search-engine contract for every catalog selection.

Source connectors are stubbed; these tests validate matching and response
classification, not claims of live stock in third-party portals.
"""
import unittest
from unittest.mock import patch
from search_poc.beta_engine import search_all
from search_poc.vehicle_catalog import CATALOG, canonical_query


def example_row(make, model, variant, index):
    title=" ".join(x for x in (make,model,variant) if x)
    slug="-".join(title.lower().replace(" ","-").split("-"))
    return {
        "source_key":"standvirtual", "source":"Standvirtual",
        "official":False,"title":title,"snippet":"2025 · 12000 km",
        "url":f"https://www.standvirtual.com/carros/anuncio/{slug}-ID{index:08d}.html",
        "condition":"used","availability":"","price_eur":45000,
        "year":2025,"mileage_km":12000,"dealer":"",
        "discovery":"reader_fallback",
    }


class EngineContractTests(unittest.TestCase):
    def test_every_model_and_powertrain_selection_returns_exactly_one_matching_offer(self):
        checked=0
        with patch("search_poc.beta_engine._relevant_sources",return_value=[]):
            for make,entry in CATALOG.items():
                for model,variants in entry["models"].items():
                    for variant in variants:
                        row=example_row(make,model,variant,checked+1)
                        q=canonical_query(make,model,variant)
                        with patch("search_poc.beta_engine._direct_specials",return_value=[row]):
                            result=search_all(q,make=make,model=model,variant=variant)
                        self.assertEqual(result["stock_status"],"verified_listings",
                                         (make,model,variant,result.get("summary")))
                        self.assertEqual(result["summary"]["total"],1,(make,model,variant))
                        self.assertEqual(result["results"][0]["title"],row["title"])
                        checked+=1
        self.assertGreater(checked,250)

    def test_wrong_mercedes_engine_is_never_counted_and_is_labeled_alternative(self):
        wrong=example_row("Mercedes-Benz","GLC","300",300001)
        q=canonical_query("Mercedes-Benz","GLC","AMG GLC 63","suv")
        with patch("search_poc.beta_engine._relevant_sources",return_value=[]), \
             patch("search_poc.beta_engine._direct_specials",return_value=[wrong]):
            result=search_all(q,make="Mercedes-Benz",model="GLC",
                              variant="AMG GLC 63",body="suv")
        self.assertEqual(result["summary"]["total"],0)
        self.assertEqual(result["stock_status"],"not_confirmed")
        self.assertEqual(len(result["alternatives"]),1)

    def test_no_stock_is_not_invented(self):
        q=canonical_query("Audi","Q4 e-tron","55 quattro","suv")
        with patch("search_poc.beta_engine._relevant_sources",return_value=[]), \
             patch("search_poc.beta_engine._direct_specials",return_value=[]):
            result=search_all(q,make="Audi",model="Q4 e-tron",
                              variant="55 quattro",body="suv")
        self.assertEqual(result["results"],[])
        self.assertEqual(result["stock_status"],"not_confirmed")
        self.assertTrue(result["source_links"])

if __name__ == "__main__":
    unittest.main()
