import unittest

from search_poc.models import Vehicle
from search_poc.dedup import match_vehicle, cross_source_matches
from search_poc.query_validation import query_matches_text
from search_poc.beta_engine import _dedup, _discount
from search_poc.connectors.standvirtual import _route_for_query
from search_poc.connectors.volvo_inventory import _parse_inventory_html


class SearchPocQueryValidationTests(unittest.TestCase):
    def test_bmw_x1_rejects_wrong_drive_variant(self):
        self.assertFalse(query_matches_text(
            "BMW X1 xDrive30e SUV",
            "BMW X1 xDrive25e",
            "2024 · 31.993 km · BMW Premium Selection",
        ))
        self.assertTrue(query_matches_text(
            "BMW X1 xDrive30e SUV",
            "BMW X1 xDrive30e",
            "2024 · 31.993 km · SUV",
        ))

    def test_mercedes_300e_rejects_300de(self):
        self.assertFalse(query_matches_text(
            "Mercedes-Benz GLC 300 e SUV",
            "Mercedes-Benz GLC 300 de 4Matic",
            "SUV · Híbrido Plug-In",
        ))
        self.assertTrue(query_matches_text(
            "Mercedes-Benz GLC 300 e SUV",
            "Mercedes-Benz GLC 300 e 4Matic",
            "SUV · Híbrido Plug-In",
        ))

    def test_body_conflict_is_rejected(self):
        self.assertFalse(query_matches_text(
            "BMW Série 3 330e Touring",
            "BMW 330 e Pack M",
            "Sedan · 2023",
        ))
        self.assertTrue(query_matches_text(
            "BMW Série 3 330e Touring",
            "BMW 330 e Pack M",
            "Carrinha · 2023",
        ))

    def test_glc_exact_engine_without_body_label_is_accepted(self):
        self.assertTrue(query_matches_text(
            "Mercedes-Benz GLC 300 e SUV",
            "Mercedes-Benz GLC 300 e 4Matic",
            "Híbrido Plug-In · 2022 · 74 500 km",
        ))

    def test_audi_engine_badge_is_variant_defining(self):
        self.assertFalse(query_matches_text(
            "Audi A4 40 TDI Avant",
            "Audi A4 Avant 35 TDI S tronic",
            "Diesel · 2022",
        ))
        self.assertTrue(query_matches_text(
            "Audi A4 40 TDI Avant",
            "Audi A4 Avant 40 TDI S tronic advanced",
            "Diesel · 2022",
        ))

    def test_volvo_split_model_and_powertrain_are_normalized(self):
        self.assertFalse(query_matches_text(
            "Volvo XC60 T6 SUV",
            "Volvo XC 60 2.0 T8 PHEV Inscription AWD",
            "Híbrido Plug-In · 2022",
        ))
        self.assertTrue(query_matches_text(
            "Volvo XC60 T6 SUV",
            "Volvo XC 60 2.0 T6 PHEV Plus Dark AWD",
            "Híbrido Plug-In · 2025",
        ))


class SearchPocMarketplaceRouteTests(unittest.TestCase):
    def test_glc_300_uses_narrow_route(self):
        self.assertIn("/glc-300", _route_for_query("Mercedes-Benz GLC 300 e SUV"))

    def test_a4_station_uses_avant_route(self):
        self.assertTrue(_route_for_query("Audi A4 40 TDI Avant").endswith("/a4-avant"))

    def test_volvo_uses_hyphenated_model_slug(self):
        self.assertTrue(_route_for_query("Volvo XC60 T6 SUV").endswith("/xc-60"))



class SearchPocVolvoConnectorTests(unittest.TestCase):
    def test_inventory_rows_keep_unique_detail_urls(self):
        html = """
        <div class="card">
          <a href="/pt/shop/details/xc60-hybrid/stock-a/?token=1">
            <span>Disponível em 2 semanas</span>
            <h3>XC60 Core, T6 AWD Híbrido Plug-in</h3>
            <span>2026 • 82 km autonomia elétrica</span>
            <span>PRVP</span><span>73 908 €</span>
          </a>
        </div>
        <div class="card">
          <a href="/pt/shop/details/xc60-hybrid/stock-b/?token=2">
            <span>Disponível em 2 semanas</span>
            <h3>XC60 Plus, T6 AWD Híbrido Plug-in</h3>
            <span>2026 • 81 km autonomia elétrica</span>
            <span>PRVP</span><span>76 417 €</span>
          </a>
        </div>
        """
        rows=_parse_inventory_html(html)
        self.assertEqual(2,len(rows))
        self.assertNotEqual(rows[0].url,rows[1].url)
        self.assertEqual("stock-a",rows[0].source_id)
        self.assertEqual(73908.0,rows[0].price_eur)
        self.assertEqual("XC60 Core",rows[0].model)
        self.assertIn("T6",rows[0].variant)




class SearchPocPriceTests(unittest.TestCase):
    def test_single_price_is_not_lost(self):
        self.assertEqual(_discount([41990.0],"BMW 330e 41.990 EUR"),(41990.0,None,None,None,""))

    def test_trade_in_price_is_conditional(self):
        current,list_price,pct,conditional,condition=_discount(
            [44490.0,46490.0],
            "Preço 44.490 EUR PVP 46.490 EUR desconto direto na retoma",
        )
        self.assertEqual(current,46490.0)
        self.assertEqual(list_price,46490.0)
        self.assertEqual(conditional,44490.0)
        self.assertEqual(condition,"retoma")
        self.assertGreater(pct,0)


class SearchPocDedupTests(unittest.TestCase):
    def _row(self, **kw):
        row={
            "source_key":"bmw_premium","source":"BMW Premium Selection","official":True,
            "title":"BMW iX3 Impressive","snippet":"2023 · 74.981 km · MCoutinho Viseu",
            "url":"https://example.test/a","year":2023,"mileage_km":74981,
            "price_eur":47900.0,"dealer":"MCoutinho Viseu","discovery":"direct_connector",
        }
        row.update(kw)
        return row

    def test_ix3_rounding_duplicate_is_merged(self):
        a=self._row()
        b=self._row(
            source_key="standvirtual",source="Standvirtual — benchmark",official=False,
            url="https://example.test/b",mileage_km=75000,
            snippet="2023 · 75.000 km · MCOUTINHO Viseu",
            discovery="public_index",
        )
        out=_dedup([a,b])
        self.assertEqual(len(out),1)
        self.assertEqual(len(out[0]["occurrences"]),2)
        self.assertIn("Standvirtual — benchmark",out[0]["also_at"])

    def test_direct_dealer_becomes_primary_source(self):
        bps=self._row(
            title="BMW 330e Touring Pack M Pro",snippet="2025 · 31.700 km · BMcar",
            year=2025,mileage_km=31700,price_eur=46900.0,dealer="BMcar",
            url="https://example.test/bps",
        )
        dealer=self._row(
            source_key="bmcar",source="BMcar",official=True,
            title="BMW 330e Touring Pack M Pro",snippet="2025 · 31.700 km · BMcar",
            year=2025,mileage_km=31700,price_eur=52946.0,dealer="BMcar",
            url="https://example.test/bmcar",discovery="direct_connector",
        )
        out=_dedup([bps,dealer])
        self.assertEqual(len(out),1)
        self.assertEqual(out[0]["source_key"],"bmcar")
        self.assertEqual(out[0]["price_eur"],52946.0)
        self.assertEqual(len(out[0]["occurrences"]),2)

    def test_different_dealers_are_not_merged(self):
        a=self._row(dealer="Dealer A",url="https://example.test/a")
        b=self._row(
            source_key="standvirtual",source="Standvirtual — benchmark",official=False,
            dealer="Dealer B",url="https://example.test/b",mileage_km=74990,price_eur=47900.0,
        )
        self.assertEqual(len(_dedup([a,b])),2)

    def test_vehicle_matcher_is_generic_not_330e_specific(self):
        a=Vehicle(
            source="bmw_premium_selection",source_id="1",url="a",
            make="BMW",model="iX3",variant="Impressive",body="SUV",
            year=2023,mileage_km=74981,price_eur=47900,dealer="MCoutinho Viseu",
        )
        b=Vehicle(
            source="standvirtual",source_id="2",url="b",
            make="BMW",model="iX3",variant="Impressive",body="SUV",
            year=2023,mileage_km=75000,price_eur=47900,dealer="MCOUTINHO Viseu",
        )
        score,reasons=match_vehicle(a,b)
        self.assertGreaterEqual(score,0.85)
        self.assertIn("identity_code",reasons)
        self.assertEqual(len(cross_source_matches([a],[b])),1)


if __name__=="__main__":
    unittest.main()
