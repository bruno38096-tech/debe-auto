"""Snapshot freshness, source provenance and deterministic cached search tests."""
import json
import tempfile
import unittest
from datetime import datetime,timezone,timedelta
from pathlib import Path
from unittest.mock import patch

from search_poc import inventory_cache
from search_poc.beta_engine import _direct_specials,search_all

EXAMPLE = {
    "source_key":"standvirtual","source":"Standvirtual — última observação",
    "official":False,"title":"Mercedes-Benz GLC 300 e 4Matic",
    "url":"https://www.standvirtual.com/carros/anuncio/mercedes-benz-glc-300-ver-e-4matic-ID8ABCD.html",
    "condition":"used","year":2024,"mileage_km":18000,"price_eur":51000,
    "discovery":"scheduled_snapshot",
}


class InventoryCacheTests(unittest.TestCase):
    def tearDown(self):
        inventory_cache.read_inventory.cache_clear()

    def test_recent_snapshot_but_not_old_or_undated(self):
        with tempfile.TemporaryDirectory() as directory:
            file=Path(directory)/"snapshot.json"
            with patch.object(inventory_cache,"SNAPSHOT_FILE",file):
                recent=datetime.now(timezone.utc).isoformat()
                file.write_text(json.dumps({"entries":{
                    "Mercedes-Benz|GLC":[{**EXAMPLE,"observed_at":recent}]
                }}))
                inventory_cache.read_inventory.cache_clear()
                rows=inventory_cache.model_inventory("Mercedes-Benz","GLC")
                self.assertEqual(len(rows),1)
                self.assertEqual(rows[0]["price_eur"],51000)
                file.write_text(json.dumps({"entries":{
                    "Mercedes-Benz|GLC":[{**EXAMPLE,"observed_at":
                        (datetime.now(timezone.utc)-timedelta(days=5)).isoformat()}]
                }}))
                inventory_cache.read_inventory.cache_clear()
                self.assertEqual(inventory_cache.model_inventory("Mercedes-Benz","GLC"),[])

    def test_cached_engine_avoids_third_party_http(self):
        with patch("search_poc.beta_engine.model_inventory",return_value=[{
            **EXAMPLE,"observed_at":datetime.now(timezone.utc).isoformat()
        }]), patch("search_poc.connectors.standvirtual.discover_rows",
                    side_effect=AssertionError("Unexpected marketplace call")):
            rows=_direct_specials("Mercedes-Benz GLC 300 e SUV",
                                 make="Mercedes-Benz",model="GLC",
                                 variant="GLC 300 e",body="suv")
            self.assertEqual(len(rows),1)

    def test_certified_condition_uses_cached_official_listings(self):
        certified={
            **EXAMPLE,"title":"BMW Série 3 330e Touring",
            "condition":"used_certified","official":True,
            "source_key":"bmw_premium",
            "observed_at":datetime.now(timezone.utc).isoformat(),
        }
        with patch("search_poc.beta_engine.model_inventory",return_value=[certified]):
            rows=_direct_specials("BMW Série 3 330e Touring",
                                 make="BMW",model="Série 3",variant="330e",
                                 body="station",condition="used_certified")
        self.assertEqual(len(rows),1)
        self.assertEqual(rows[0]["condition"],"used_certified")

    def test_cache_does_not_turn_glc_300_into_amg_63(self):
        snapshot={**EXAMPLE,"observed_at":datetime.now(timezone.utc).isoformat()}
        with patch("search_poc.beta_engine._direct_specials",return_value=[snapshot]),\
             patch("search_poc.beta_engine._relevant_sources",return_value=[]):
            response=search_all("Mercedes-Benz GLC AMG 63 SUV",
                    make="Mercedes-Benz",model="GLC",variant="AMG GLC 63",body="suv")
        self.assertEqual(response["summary"]["total"],0)
        self.assertEqual(response["stock_status"],"not_confirmed")
        self.assertEqual(len(response["alternatives"]),1)

if __name__=="__main__":
    unittest.main()
