import unittest
import debe_research_v5 as research


class ResearchV5Tests(unittest.TestCase):
    def test_a5_returns_strengths_issues_and_checks(self):
        reviews = [
            {'title':'2015 Audi A5 review',
             'snippet':'Excellent interior quality, comfortable ride and good handling with efficient fuel economy.',
             'url':'https://review1.example/a5'},
            {'title':'Audi A5 road test',
             'snippet':'Premium cabin quality and refined comfort. Steering and handling are strong points.',
             'url':'https://review2.example/a5'},
        ]
        engine = [
            {'title':'2.0 TDI 190 common problems',
             'snippet':'Common problems include DPF clogging, EGR faults, turbo failure and injector issues.',
             'url':'https://engine1.example/tdi'},
            {'title':'2.0 TDI 190 reliability faults',
             'snippet':'DPF problems and EGR issues are reported, together with turbo faults and water pump leaks.',
             'url':'https://engine2.example/tdi'},
        ]
        model_faults = [
            {'title':'Audi A5 2015 common problems',
             'snippet':'Common gearbox and electrical problems reported in used buying guides.',
             'url':'https://faults.example/a5'},
        ]

        def search(q, n):
            ql=q.lower()
            if 'review' in ql:return reviews
            if 'gearbox electronics' in ql:return model_faults
            if '2.0 tdi' in ql:return engine
            return []

        result=research.make_research(search)('Audi A5','2.0 TDI 190 cv','2015','Diesel')
        self.assertGreaterEqual(len(result['strength_evidence']), 3)
        categories=[e['category'] for e in result['evidence']]
        self.assertIn('DPF / EGR', categories)
        self.assertIn('Turbo / sobrealimentação', categories)
        self.assertGreaterEqual(len(result['checks']), 4)
        self.assertTrue(all('Recomenda-se' in x['detail'] for x in result['checks']))

    def test_sparse_results_still_return_formal_checks(self):
        result=research.make_research(lambda q,n:[])('Audi A5','2.0 TDI 190 cv','2015','Diesel')
        self.assertEqual(len(result['checks']),4)
        self.assertTrue(all('Recomenda-se' in x['detail'] for x in result['checks']))
        self.assertNotIn('tu', ' '.join(result['strengths']+result['issues']).lower())


if __name__=='__main__':
    unittest.main()
