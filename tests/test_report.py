import unittest
from unittest.mock import patch
import app
import debe_research_v4 as research
import debe_market_v2 as market

class ReportTests(unittest.TestCase):
    def test_a5_report_returns_strengths_issues_and_checks(self):
        reviews=[
            {'title':'2015 Audi A5 review','snippet':'Expert road test of the Audi A5.',
             'url':'https://review1.example/a5'},
            {'title':'Audi A5 2015 review and road test','snippet':'Audi A5 coupe review.',
             'url':'https://review2.example/a5'}]
        engine=[
            {'title':'2.0 TDI 190 common problems','snippet':'DPF clogging, EGR problems, turbo failure and water pump leaks are reported.',
             'url':'https://engine1.example/20tdi'},
            {'title':'2.0 TDI 190 reliability and faults','snippet':'Common problems include DPF issues and EGR faults.',
             'url':'https://engine2.example/20tdi'}]
        model_issues=[
            {'title':'Audi A5 2015 common problems','snippet':'Used buying guide and reliability overview.',
             'url':'https://model1.example/a5'}]

        def search(query,n):
            q=query.lower()
            if '2.0 tdi' in q and ('common problems' in q or 'common faults' in q):return engine
            if 'review' in q:return reviews
            if 'common problems reliability used buying guide' in q:return model_issues
            return []

        def page(url):
            if 'review' in url:
                return ('The ride is comfortable and refined. Interior quality is excellent with high quality materials. '
                        'Handling is good and confidence-inspiring. Fuel economy is good for the class.')
            if 'engine' in url:
                return ('Common problems include DPF clogging and EGR faults. Turbo failure can cause loss of power. '
                        'Water pump leaks are also reported on higher mileage engines.')
            return ''

        with patch.object(research,'read_page',side_effect=page):
            result=research.make_research(search)('Audi A5','2.0 TDI 190 cv','2015','Diesel')

        self.assertGreaterEqual(len(result['strength_evidence']),3)
        cats=[e['category'] for e in result['evidence']]
        self.assertIn('DPF / EGR',cats)
        self.assertIn('Turbo / sobrealimentação',cats)
        self.assertGreaterEqual(len(result['checks']),3)
        self.assertNotIn('Não foi possível confirmar um ponto forte específico',result['strengths'][0])
        self.assertNotIn('Não foi possível confirmar um problema recorrente específico',result['issues'][0])
        self.assertTrue(result['sources'])

    def test_preventive_checks_are_always_useful_for_diesel(self):
        result=research.make_research(lambda q,n:[])('Audi A5','2.0 TDI 190 cv','2015','Diesel')
        titles=[x['title'] for x in result['checks']]
        self.assertIn('DPF / EGR',titles)
        self.assertIn('Arranque a frio e injeção',titles)
        self.assertIn('Turbo e admissão',titles)
        self.assertIn('VIN e histórico',titles)

    def test_old_car_does_not_get_adblue_category(self):
        engine=[{'title':'2.0 TDI 170 common problems','snippet':'AdBlue failure, DPF problems and turbo failure.',
                 'url':'https://engine.example/20tdi'}]
        def search(query,n):return engine if '2.0 tdi' in query.lower() else []
        with patch.object(research,'read_page',return_value='Common problems: AdBlue failure. DPF problems. Turbo failure.'):
            result=research.make_research(search)('Audi A4','2.0 TDI 170 cv','2006','Diesel')
        self.assertNotIn('AdBlue / SCR / NOx',[e['category'] for e in result['evidence']])

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
