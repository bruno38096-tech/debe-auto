"""Deterministic regression checks for DEBE Search, no external HTTP required."""
import unittest
from unittest.mock import patch
from search_poc import beta_engine as engine
from search_poc.query_validation import query_matches_text

Q = "BMW Série 3 330e Touring"
ROW = {
    "source_key": "bmw_premium", "source": "BMW Premium Selection",
    "official": True, "title": "BMW Série 3 330e Touring",
    "snippet": "2023 · 22 000 km · 330e Touring",
    "url": "https://bmwpremiumselection.bmw.pt/carros-usados/bmw-serie-3-330e-touring/12345/",
    "condition": "used_certified", "year": 2023, "mileage_km": 22000,
    "price_eur": 49000.0, "dealer": "Concessionário teste",
    "discount_pct": None, "discovery": "direct_connector",
}


class SearchRegressions(unittest.TestCase):
    def test_exact_engine_and_body(self):
        self.assertTrue(query_matches_text(Q, "BMW 330e Touring", "2023 22 000 km"))
        self.assertFalse(query_matches_text(Q, "BMW 320d Touring", "2023 22 000 km"))
        self.assertFalse(query_matches_text(Q, "BMW Série 3 330e Sedan", "2023"))

    def test_audi_e_tron_route_and_variant(self):
        from search_poc.connectors.standvirtual import _route_for_query
        q = "Audi A6 e-tron Avant"
        self.assertEqual(_route_for_query(q),
            "https://www.standvirtual.com/carros/audi/a6-avant-e-tron")
        self.assertTrue(query_matches_text(q, "Audi A6 Avant e-tron 100 kWh", "2025 7 200 km"))
        self.assertFalse(query_matches_text(q, "Audi A6 Avant 40 TDI", "2020 55 000 km"))

    def test_real_listing_can_have_missing_price(self):
        row = {**ROW, "price_eur": None}
        self.assertTrue(engine._complete_vehicle_row(row))
        self.assertTrue(row["data_incomplete"])
        self.assertFalse(engine._complete_vehicle_row({
            **ROW, "price_eur": None, "mileage_km": None
        }))

    def test_known_direct_vehicle_survives_search_pipeline(self):
        source = next(x for x in engine.SOURCES if x["key"] == "bmw_premium")
        # All internet discovery is stubbed, so this is deterministic in CI.
        with patch.object(engine, "_relevant_sources", return_value=[source]), \
             patch.object(engine, "_direct_specials", return_value=[ROW.copy()]), \
             patch.object(engine, "_source_query", return_value=([], "")):
            result = engine.search_all(Q + " unit-test-unique", max_per_source=1)
        self.assertEqual(result["summary"]["total"], 1)
        self.assertEqual(result["results"][0]["price_eur"], 49000)
        self.assertTrue(result["source_links"])

    def test_no_fake_results_on_empty_sources(self):
        source = next(x for x in engine.SOURCES if x["key"] == "bmw_premium")
        with patch.object(engine, "_relevant_sources", return_value=[source]), \
             patch.object(engine, "_direct_specials", return_value=[]), \
             patch.object(engine, "_source_query", return_value=([], "")):
            result = engine.search_all(Q + " unit-test-empty", max_per_source=1)
        self.assertEqual(result["results"], [])
        self.assertGreaterEqual(len(result["source_links"]), 1)


if __name__ == "__main__":
    unittest.main()
