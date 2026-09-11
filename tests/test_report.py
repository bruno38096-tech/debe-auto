import unittest
from unittest.mock import patch
import app
import debe_research_v2 as research
import debe_market_v2 as market

class ReportTests(unittest.TestCase):
    def test_reviews_are_read_and_wrong_era_faults_rejected(self):
        issues=[
            {'title':'Audi A4 2006 2.0 TDI 170 hp faults',
             'snippet':'Description: turbo failure reported. No AdBlue problems.',
             'url':f'https://source{i}.example/faults'} for i in range(10)]
        issues.append({'title':'Audi A4 2015–2023 2.0 TDI 170 hp',
                       'snippet':'AdBlue failure and SCR faults.',
                       'url':'https://later.example/review'})
        reviews=[{'title':'Audi A4 2004–2008 review','snippet':'Road test.',
                  'url':'https://review.example/a4'}]
        calls=[]
        def page(url):
            calls.append(url)
            if url==reviews[0]['url']:
                return 'The ride is comfortable and refined. Excellent build quality. Good handling.'
            return ''
        def search(query,n):
            return reviews if 'review comfort' in query else issues
        with patch.object(research,'read_page',side_effect=page):
            result=research.make_research(search)('Audi A4','2.0 tdi 170cv','2006','Diesel')
        self.assertIn(reviews[0]['url'],calls)
        self.assertEqual(len(result['strength_evidence']),3)
        self.assertIn('Turbo / sobrealimentação',[e['category'] for e in result['evidence']])
        self.assertNotIn('AdBlue / SCR / NOx',[e['category'] for e in result['evidence']])
        self.assertTrue(result['sources'])

    def test_word_matches_and_negative_reviews(self):
        self.assertFalse(research.contains('description subscribe','scr'))
        self.assertEqual(research.evidence_fragments('Poor comfort and bad build quality.',['comfort','build quality'],True),[])
        self.assertEqual(research.evidence_fragments('A turbo engine with manual transmission.',['turbo','transmission']),[])
        self.assertFalse(research.year_matches('Audi A4 2015–2023',2006))
        self.assertTrue(research.year_matches('Audi A4 2004–2008',2006))

    def test_model_fuel_and_year_filters(self):
        def deal(title,year,fuel,url):
            return dict(title=title,year=str(year),fuel=fuel,url=url,price='4.500 €',km='200.000 km',score=40,_price=4500,_year=year)
        candidates=[
            deal('Audi A4',2006,'Diesel','https://olx.pt/d/anuncio/a-ID1.html'),
            deal('Audi A4',2020,'Diesel','https://olx.pt/d/anuncio/b-ID2.html'),
            deal('Audi A4',2006,'Gasolina','https://olx.pt/d/anuncio/c-ID3.html'),
            deal('Audi A6',2006,'Diesel','https://olx.pt/d/anuncio/d-ID4.html')]
        with patch.object(app,'fetch_text',return_value=''),patch.object(market,'_collect_urls',return_value=[]),patch.object(market,'_fetch_many',return_value=candidates):
            found=market._same_model(app,'Audi A4','Diesel','2006','4.500 €','')
        self.assertEqual(len(found),1)
        self.assertEqual(found[0]['url'],candidates[0]['url'])

    def test_only_listing_urls(self):
        self.assertFalse(market._market_url('https://olx.pt/carros/q-audi/'))
        self.assertFalse(market._market_url('https://olx.pt.evil.example/d/anuncio/a'))
        self.assertTrue(market._market_url('https://www.olx.pt/d/anuncio/audi-ID1.html'))

    def test_budget_filters_validated_listings(self):
        deals=[dict(title='Ford Focus',year='2007',fuel='Diesel',url='https://olx.pt/d/anuncio/a-ID1.html',price='4.700 €',km='200.000 km',score=40,_price=4700,_year=2007),
               dict(title='Audi A6',year='2020',fuel='Diesel',url='https://olx.pt/d/anuncio/b-ID2.html',price='30.000 €',km='20.000 km',score=80,_price=30000,_year=2020)]
        with patch.object(market,'_collect_urls',return_value=[]),patch.object(market,'_fetch_many',return_value=deals):
            found=market._same_budget(app,'Audi A4','Diesel','2006','4500','',[])
        self.assertEqual(len(found),1)
        self.assertEqual(found[0]['title'],'Ford Focus')

    def test_served_frontend(self):
        with app.app.test_client() as client:
            self.assertIn(b'/debe_frontend_v3.js',client.get('/').data)
            script=client.get('/debe_frontend_v3.js')
            self.assertEqual(script.status_code,200)
            self.assertIn('javascript',script.content_type)

if __name__=='__main__':unittest.main()
