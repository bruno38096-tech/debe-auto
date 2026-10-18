"""BMW Reader fallback regression tests with mocked page content."""
import unittest
from unittest.mock import Mock, patch

from search_poc.connectors.bmw_reader_fallback import parse_bmw_reader, discover_rows

PAGE = """
Title: BMW Série 3 330e Touring usado
Markdown Content:
Veículo certificado BMW Premium Selection
[BMW Série 3330e Touring](https://bmwpremiumselection.bmw.pt/concessionarios/evora/matoscar/bmw-serie-3-330e-touring/155518138/)
Comparar
* 44.705 km
* 2025
Preço: 43.450,00 €

45.450,00 €
Desconto direto 2.000 € com retoma

### EXEMPLO DE FINANCIAMENTO BMW BANK
Produto Financeiro | Crédito
PVP da Viatura | 45.450,00 €
Veículo oferecido pela A Matoscar Évora

Veículo certificado BMW Premium Selection
[BMW Série 3330e Touring](https://bmwpremiumselection.bmw.pt/concessionarios/braga/bmcar/bmw-serie-3-330e-touring/147358164/)
Comparar
* 22.500 km
* 2025
Preço: 52.946,00 €
Veículo oferecido pela Bmcar Porto
"""


class BMWReaderTests(unittest.TestCase):
    def test_two_individual_offers_and_conditional_price(self):
        offers = parse_bmw_reader(PAGE)
        self.assertEqual(len(offers), 2)
        self.assertTrue(offers[0]["url"].endswith("/155518138/"))
        self.assertEqual(offers[0]["price_eur"], 45450)
        self.assertEqual(offers[0]["conditional_price_eur"], 43450)
        self.assertEqual(offers[0]["mileage_km"], 44705)
        self.assertEqual(offers[0]["year"], 2025)
        self.assertEqual(offers[1]["price_eur"], 52946)
        self.assertIsNone(offers[1]["conditional_price_eur"])

    def test_no_vehicle_urls_no_fabricated_offers(self):
        self.assertEqual(parse_bmw_reader(
            "BMW Série 3 330e Touring 22.500 km 2025 Preço: 50.000,00 €"
        ), [])

    @patch("search_poc.connectors.bmw_reader_fallback.requests.get")
    def test_http_reader_payload(self, get):
        get.return_value = Mock(status_code=200, text=PAGE)
        get.return_value.raise_for_status.return_value = None
        offers = discover_rows(timeout=4)
        self.assertEqual(len(offers), 2)
        self.assertTrue(get.call_args.args[0].startswith("https://r.jina.ai/https://"))


if __name__ == "__main__":
    unittest.main()
