"""Matrix contract: all catalog selections work and false matches are rejected.

Network availability is intentionally a separate test. No synthetic vehicle is
presented as a real listing or as evidence of available stock.
"""
import unittest
from search_poc.vehicle_catalog import CATALOG, canonical_query
from search_poc.vehicle_identity import spec_matches, marketplace_model_route
from search_poc.connectors.standvirtual import discover_rows


def row(title):
    return {"title": title, "url": "https://www.standvirtual.com/carros/anuncio/"
                                + title.lower().replace(" ","-")+"-ID8Q1234.html",
            "year":2025,"mileage_km":10000,"price_eur":40000.0}


class GeneralIdentityTests(unittest.TestCase):
    def test_critical_amg_not_replaced_by_glc_300(self):
        self.assertFalse(spec_matches("Mercedes-Benz","GLC","AMG GLC 63","suv",
                    row("Mercedes-Benz GLC 300 4MATIC")))
        self.assertTrue(spec_matches("Mercedes-Benz","GLC","AMG GLC 63","suv",
                    row("Mercedes-Benz AMG GLC 63 4MATIC")))
        self.assertFalse(spec_matches("Mercedes-Benz","GLC","GLC 300 e","suv",
                    row("Mercedes-Benz GLC 300 de 4MATIC")))
        self.assertTrue(spec_matches("Mercedes-Benz","GLC","GLC 300 e","suv",
                    row("Mercedes-Benz GLC 300 e 4MATIC")))

    def test_missing_variant_is_not_positive(self):
        self.assertFalse(spec_matches("Mercedes-Benz","GLC","AMG GLC 63","suv",
                    row("Mercedes-Benz GLC 300")))
        self.assertFalse(spec_matches("Audi","Q4 e-tron","45 quattro","suv",
                    row("Audi Q4 e-tron 35")))
        self.assertFalse(spec_matches("BMW","Série 3","330e","station",
                    row("BMW Série 3 320d Touring")))

    def test_national_catalog_all_models_have_route_and_match(self):
        count=0
        for make,entry in CATALOG.items():
            for model,variants in entry["models"].items():
                route=marketplace_model_route(make,model,"all")
                self.assertTrue(route.startswith("https://www.standvirtual.com/carros/"),
                                (make,model,route))
                self.assertNotIn(" ",route)
                # A listing explicitly stating the make/model/variant is
                # representable and eligible for exact-match verification.
                for variant in variants:
                    candidate=row(make+" "+model+" "+variant)
                    self.assertTrue(spec_matches(make,model,variant,"all",candidate),
                                    (make,model,variant))
                    self.assertFalse(spec_matches(make,model,variant,"all",
                                    row("Audi Q4 e-tron 40 e-tron")) if make!="Audi" else
                                    spec_matches(make,model,variant,"all",
                                    row("Mercedes-Benz GLC 300 e")),(make,model,variant))
                    count+=1
        self.assertGreater(count,250)

    def test_existing_working_models(self):
        self.assertTrue(spec_matches("BMW","Série 3","330e","station",
                   row("BMW Série 3 330e Touring")))
        self.assertTrue(spec_matches("Audi","A6 e-tron","","station",
                   row("Audi A6 Avant e-tron 83 kWh")))
        self.assertTrue(spec_matches("Audi","Q4 e-tron","","suv",
                   row("Audi Q4 e-tron 45 quattro")))
        self.assertTrue(spec_matches("Mercedes-Benz","GLC","GLC 300 e","suv",
                   row("Mercedes-Benz GLC 300 e 4MATIC")))
        self.assertFalse(spec_matches("Mercedes-Benz","GLC","AMG GLC 63","suv",
                   row("Mercedes-Benz GLC 300")))

    def test_variant_aliases_and_more_specific_trims(self):
        self.assertTrue(spec_matches("Kia","Sportage","Plug-in Hybrid","suv",
                                    row("Kia Sportage 1.6 PHEV GT Line")))
        self.assertTrue(spec_matches("Porsche","911","Carrera","coupe",
                                    row("Porsche 911 Carrera 3.0 PDK")))
        self.assertFalse(spec_matches("Porsche","911","Carrera","coupe",
                                     row("Porsche 911 Carrera S 3.0 PDK")))
        self.assertFalse(spec_matches("Porsche","911","Carrera","coupe",
                                     row("Porsche 911 Carrera Cabriolet")))
        self.assertFalse(spec_matches("Tesla","Model Y","RWD","suv",
                                     row("Tesla Model Y Long Range RWD")))
        self.assertFalse(spec_matches("Volvo","EX30","Single Motor","suv",
                                     row("Volvo EX30 Single Motor Extended Range")))

    def test_specific_model_routes(self):
        self.assertEqual(marketplace_model_route("Audi","Q4 e-tron","suv"),
                         "https://www.standvirtual.com/carros/audi/q4-e-tron")
        self.assertEqual(marketplace_model_route("BMW","Série 3","station"),
                         "https://www.standvirtual.com/carros/bmw/serie-3")
        self.assertEqual(marketplace_model_route("Audi","A6 e-tron","station"),
                         "https://www.standvirtual.com/carros/audi/a6-avant-e-tron")
        self.assertEqual(marketplace_model_route("Mercedes-Benz","GLC","suv","GLC 300 e"),
                         "https://www.standvirtual.com/carros/mercedes-benz/glc-300")
        self.assertEqual(marketplace_model_route("Mercedes-Benz","GLC","suv","AMG GLC 63"),
                         "https://www.standvirtual.com/carros/mercedes-benz/glc-63")

if __name__ == "__main__":
    unittest.main()
