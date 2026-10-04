import os
import unittest
from unittest.mock import patch

import app as debe_app


class SearchBetaIntegrationTests(unittest.TestCase):
    def setUp(self):
        debe_app.app.config.update(TESTING=True)
        self.client=debe_app.app.test_client()

    def test_search_beta_is_invisible_when_flag_off(self):
        with patch.dict(os.environ, {"DEBE_SEARCH_BETA_ENABLED":"0"}, clear=False):
            self.assertEqual(404,self.client.get("/search-beta/").status_code)
            self.assertNotIn(b"Pesquisar carros",self.client.get("/").data)

    def test_search_beta_is_exposed_when_flag_on(self):
        with patch.dict(os.environ, {"DEBE_SEARCH_BETA_ENABLED":"1"}, clear=False):
            home=self.client.get("/")
            self.assertEqual(200,home.status_code)
            self.assertIn(b"/search-beta/",home.data)
            search=self.client.get("/search-beta/")
            self.assertEqual(200,search.status_code)
            self.assertIn(b"DEBE Search",search.data)
            self.assertIn(b"/search-beta/api/catalog",search.data)

    def test_catalog_is_guarded_by_same_flag(self):
        with patch.dict(os.environ, {"DEBE_SEARCH_BETA_ENABLED":"0"}, clear=False):
            self.assertEqual(404,self.client.get("/search-beta/api/catalog").status_code)
        with patch.dict(os.environ, {"DEBE_SEARCH_BETA_ENABLED":"true"}, clear=False):
            response=self.client.get("/search-beta/api/catalog")
            self.assertEqual(200,response.status_code)
            data=response.get_json()
            self.assertIn("BMW",data["brands"])

    def test_query_uses_search_poc_without_touching_legacy_comparables(self):
        fake={"query":"BMW iX3","results":[],"sources":[],"summary":{"total":0}}
        with patch.dict(os.environ, {"DEBE_SEARCH_BETA_ENABLED":"1"}, clear=False):
            with patch("search_poc.integration.search_all",return_value=fake) as search:
                response=self.client.get("/search-beta/api/search?q=BMW+iX3")
                self.assertEqual(200,response.status_code)
                data=response.get_json()
                self.assertEqual("search-beta",data["feature"])
                search.assert_called_once_with("BMW iX3",condition="all",max_per_source=3)


if __name__=="__main__":
    unittest.main()
