import unittest

from search_poc.models import Vehicle
from search_poc.dedup import match_vehicle, cross_source_matches
from search_poc.query_validation import query_matches_text
from search_poc.beta_engine import _dedup, _discount


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
