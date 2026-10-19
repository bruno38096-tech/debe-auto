"""Ensure DEBE social PNG media is Instagram-compatible and publicly routable."""
import unittest
from io import BytesIO
from PIL import Image
from search_poc.social_cards import CREATIVES,render_png
from search_beta_app import app

class SocialImageTests(unittest.TestCase):
    def test_every_social_image_is_full_quality_png(self):
        for slug in CREATIVES:
            with self.subTest(slug=slug):
                raw=render_png(slug)
                self.assertTrue(raw.startswith(b'\\x89PNG\\r\\n\\x1a\\n'.decode('unicode_escape').encode('latin1')))
                img=Image.open(BytesIO(raw))
                self.assertEqual(img.size,(1080,1350))
                self.assertLess(len(raw),3_000_000)
    def test_public_routes(self):
        client=app.test_client()
        for slug in CREATIVES:
            with self.subTest(slug=slug):
                response=client.get('/social/'+slug+'.png')
                self.assertEqual(response.status_code,200)
                self.assertEqual(response.content_type,'image/png')
        self.assertEqual(client.get('/social/missing.png').status_code,404)

if __name__=='__main__':
    unittest.main()
