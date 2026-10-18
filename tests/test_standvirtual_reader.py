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

    def test_no_fake_title_or_non_matching_fuel(self):
        rows = _parse_reader_page(PAGE, "Audi A6 40 TDI Avant")
        self.assertEqual(rows, [])

if __name__ == "__main__":
    unittest.main()
