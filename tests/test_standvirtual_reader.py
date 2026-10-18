"""Standvirtual Reader fallback must preserve individual Audi listings."""
import unittest
from search_poc.connectors.standvirtual import _parse_reader_page

PAGE = """
Title: Audi A6 Avant e-tron - Carros - Standvirtual.com
Markdown Content:
## [Audi A6 Avant e-tron 83 kWh SE Business Plus Electric Days](https://www.standvirtual.com/carros/anuncio/audi-a6-avant-e-tron-ver-83-kwh-se-business-plus-electric-days-ID8Q16hN.html)
326 cv
mileage 6 000 km fuel_type Elétrico gearbox Automática first_registration_year 2025
* Vila Cova da Lixa (Porto)
[ad link](https://www.standvirtual.com/carros/anuncio/audi-a6-avant-e-tron-ver-83-kwh-se-business-plus-electric-days-ID8Q16hN.html)
* 2025
- 1 300 EUR
### 62 700

EUR
## [Audi A6 Avant e-tron performance edition one grey](https://www.standvirtual.com/carros/anuncio/audi-a6-avant-e-tron-performance-ID8QTTTT.html)
367 cv
mileage 19 177 km fuel_type Elétrico gearbox Automática first_registration_year 2025
### 79 700
EUR
"""

class StandvirtualReaderTests(unittest.TestCase):
    def test_two_ads_exact_audi_etron(self):
        rows = _parse_reader_page(PAGE, "Audi A6 e-tron Avant")
        self.assertEqual(len(rows), 2)
        self.assertEqual(rows[0]["price_eur"], 62700)
        self.assertEqual(rows[0]["mileage_km"], 6000)
        self.assertEqual(rows[0]["year"], 2025)
        self.assertTrue(rows[0]["url"].endswith("ID8Q16hN.html"))
        self.assertEqual(rows[1]["price_eur"], 79700)

    def test_image_only_audi_q4_and_model_route(self):
        from search_poc.connectors.standvirtual import _route_for_query
        self.assertEqual(
            _route_for_query("Audi Q4 e-tron SUV"),
            "https://www.standvirtual.com/carros/audi/q4-e-tron")
        page = """
        [![Image 1: alt](https://example.com/photo.png)](https://www.standvirtual.com/carros/anuncio/audi-q4-e-tron-ver-45-quattro-ID8Q0TpC.html)
        1 / 6
        ### 31 990
        EUR
        mileage 106 000 km fuel_type Elétrico gearbox Automática first_registration_year 2022
        [![Image 2: alt](https://example.com/photo2.png)](https://www.standvirtual.com/carros/anuncio/audi-q4-e-tron-ver-35-55-kwh-ID8Q0XIJ.html)
        ### 28 900
        EUR
        mileage 89 224 km fuel_type Elétrico gearbox Automática first_registration_year 2021
        """
        rows = _parse_reader_page(page, "Audi Q4 e-tron SUV")
        self.assertEqual(len(rows), 2)
        self.assertEqual(rows[0]["price_eur"], 31990)
        self.assertEqual(rows[0]["year"], 2022)
        self.assertTrue(rows[0]["url"].endswith("ID8Q0TpC.html"))

    def test_mercedes_300e_excludes_300de_and_coupe(self):
        page = """
        [![Image](https://example.com/one.png)](https://www.standvirtual.com/carros/anuncio/mercedes-benz-glc-300-ver-de-coup-4matic-ID8Q0Pac.html)
        ### 47 950
        EUR
        mileage 84 000 km fuel_type Híbrido Plug-In first_registration_year 2022
        [![Image](https://example.com/two.png)](https://www.standvirtual.com/carros/anuncio/mercedes-benz-glc-300-ver-e-4matic-ID8Q0AAAA.html)
        ### 54 950
        EUR
        mileage 32 000 km fuel_type Híbrido Plug-In first_registration_year 2024
        """
        rows = _parse_reader_page(page, "Mercedes-Benz GLC 300 e SUV")
        self.assertEqual(len(rows), 1)
        self.assertEqual(rows[0]["price_eur"], 54950)
        self.assertIn("300", rows[0]["title"])
        self.assertTrue(rows[0]["url"].endswith("ID8Q0AAAA.html"))
        self.assertEqual(len(_parse_reader_page(page,"Mercedes-Benz GLC SUV")), 2)

    def test_no_fake_title_or_non_matching_fuel(self):
        rows = _parse_reader_page(PAGE, "Audi A6 40 TDI Avant")
        self.assertEqual(rows, [])

if __name__ == "__main__":
    unittest.main()
