"""No fabricated listings and manufacturer provenance in scheduled inventory."""
import unittest
from unittest.mock import patch
from scripts.refresh_search_inventory import harvest, supplemental_rows

BMW={
    "title":"BMW Série 3 330e Touring",
    "url":"https://bmwpremiumselection.bmw.pt/concessionarios/evora/a-matoscar/bmw-serie-3-330e-touring/155518138/",
    "year":2025,"mileage_km":44705,"price_eur":45450.0,
    "condition":"used_certified","source_key":"bmw_premium",
    "source":"BMW Premium Selection","official":True,
}
GLC={
    "title":"Mercedes-Benz GLC 300 e 4MATIC",
    "url":"https://www.standvirtual.com/carros/anuncio/mercedes-benz-glc-300-ver-e-4matic-ID8QXXXXX.html",
    "year":2024,"mileage_km":22000,"price_eur":49500.0,
    "condition":"used","source_key":"standvirtual",
    "source":"Standvirtual — benchmark","official":False,
}

class EnrichmentTest(unittest.TestCase):
    @patch("search_poc.connectors.bmw_reader_fallback.discover_rows",return_value=[BMW])
    @patch("scripts.refresh_search_inventory.discover_rows",return_value=[])
    def test_bmw_official_330e_touring_survives_snapshot(self, _generic, _official):
        key,rows=harvest(("BMW","Série 3"))
        self.assertEqual(key,"BMW|Série 3")
        self.assertEqual(len(rows),1)
        self.assertEqual(rows[0]["price_eur"],45450.0)
        self.assertTrue(rows[0]["official"])
        self.assertEqual(rows[0]["source_key"],"bmw_premium")
        self.assertIn("observed_at",rows[0])

    @patch("search_poc.connectors.standvirtual._reader_rows",return_value=[GLC])
    @patch("scripts.refresh_search_inventory.discover_rows",return_value=[])
    def test_glc_supplement_validated_and_preserved(self,_generic,_reader):
        key,rows=harvest(("Mercedes-Benz","GLC"))
        self.assertEqual(len(rows),1)
        self.assertIn("300 e",rows[0]["title"])
        self.assertFalse(rows[0]["official"])

if __name__=="__main__":
    unittest.main()
