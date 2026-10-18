"""Audi A5 e-hybrid discovery / strict powertrain and updated interface regressions."""
import unittest
from unittest.mock import patch
from search_poc.vehicle_identity import spec_matches
from search_poc.connectors.standvirtual import _parse_reader_page
from search_beta_app import HTML

class A5EhybridTests(unittest.TestCase):
    def test_engine_identity_on_2025_a5_avant_and_limousine(self):
        url="https://www.standvirtual.com/carros/anuncio/audi-a5-avant-ver-e-hybrid-quattro-ID8Q13u2.html"
        self.assertTrue(spec_matches("Audi","A5","e-hybrid","all",{"title":"Audi A5 Avant e-hybrid quattro","url":url}))
        self.assertFalse(spec_matches("Audi","A5","e-hybrid","all",{"title":"Audi A5 Avant 2.0 TDI","url":"https://www.standvirtual.com/carros/anuncio/audi-a5-avant-ver-tdi-ID8QABC.html"}))
        self.assertTrue(spec_matches("Audi","A5","e-hybrid","all",{"title":"Audi A5 Limousine e-hybrid quattro","url":"https://www.standvirtual.com/carros/anuncio/audi-a5-limousine-ver-e-hybrid-quattro-ID8Q19cQ.html"}))

    def test_standvirtual_reader_image_cards_are_extractable(self):
        page="""[![Image A](https://example.com/a.png)](https://www.standvirtual.com/carros/anuncio/audi-a5-avant-ver-e-hybrid-quattro-ID8Q13u2.html)
        ### 43 000
        EUR
        mileage 52 000 km fuel_type Híbrido Plug-In gearbox Automática first_registration_year 2025
        [![Image B](https://example.com/b.png)](https://www.standvirtual.com/carros/anuncio/audi-a5-limousine-ver-e-hybrid-quattro-ID8Q19cQ.html)
        ### 49 740
        EUR
        mileage 68 000 km fuel_type Híbrido Plug-In gearbox Automática first_registration_year 2025"""
        rows=_parse_reader_page(page,"Audi A5 e-hybrid")
        self.assertEqual(len(rows),2)
        self.assertEqual(rows[0]["price_eur"],43000)
        self.assertTrue(spec_matches("Audi","A5","e-hybrid","all",rows[0]))
        self.assertTrue(spec_matches("Audi","A5","e-hybrid","all",rows[1]))

    def test_search_ui_has_clear_navigation_sorting_and_suggested_search(self):
        self.assertIn("Encontra o carro certo.",HTML)
        self.assertIn("Analisar anúncio ↗",HTML)
        self.assertIn('data-variant="e-hybrid"',HTML)
        self.assertIn('id="sort"',HTML)
        self.assertIn("const sorted=[...d.results]",HTML)
        self.assertIn("No automatic HTTP request",HTML)

if __name__=="__main__":
    unittest.main()
