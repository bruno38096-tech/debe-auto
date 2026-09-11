"""Gunicorn hooks for DEBE beta runtime."""

def on_starting(server):
    try:
        from debe_runtime import patch_index
        from debe_ui_patch_v2 import patch_market_ui
        patch_index('index.html')
        patch_market_ui('index.html')
        print('DEBE runtime: score guide and market groups injected', flush=True)
    except Exception as e:
        print('DEBE runtime startup patch failed:', e, flush=True)


def post_worker_init(worker):
    try:
        import re
        import app as debe_app
        import debe_runtime_fast as fast
        from debe_search_providers import make_search
        from debe_research_v5 import make_research
        from debe_market_v2 import make_view

        cloud_search = make_search(fast.search_web)

        def research_search(query,n=10):
            rows=cloud_search(query,n)
            sample=' || '.join(debe_app.clean((r.get('title') or '')+' :: '+(r.get('snippet') or ''))[:220] for r in rows[:3])
            print('DEBE sample:',debe_app.clean(query)[:70],'->',sample,flush=True)
            return rows

        original_engine_hint = debe_app.engine_hint
        def robust_engine_hint(text, url=''):
            first=original_engine_hint(text,url)
            blob=debe_app.clean((debe_app.title_line(text) or '')+' '+(text or '')[:12000])
            patterns=[
                r'\b(\d[.,]\d)\s*(TDI|TFSI|TSI|dCi|BlueHDi|PureTech)\s*(\d{2,3})\s*(?:cv|hp|bhp|ps)\b',
                r'\b(\d[.,]\d)\s*(TDI|TFSI|TSI|dCi|BlueHDi|PureTech)\b[^\n.]{0,100}?\b(\d{2,3})\s*(?:cv|hp|bhp|ps)\b',
                r'\b(\d[.,]\d)\s*(TDI|TFSI|TSI|dCi|BlueHDi|PureTech)\b'
            ]
            for pat in patterns[:2]:
                m=re.search(pat,blob,re.I)
                if m:return debe_app.clean(f'{m.group(1)} {m.group(2)} {m.group(3)} cv').replace(',','.')
            if first:return first
            m=re.search(patterns[2],blob,re.I)
            return debe_app.clean(f'{m.group(1)} {m.group(2)}').replace(',','.') if m else ''
        debe_app.engine_hint=robust_engine_hint

        original_parse_olx=debe_app.parse_olx
        def robust_parse_olx(text,url):
            d=original_parse_olx(text,url)
            d['engine']=robust_engine_hint(text,url) or d.get('engine','')
            if not d.get('price'):
                normalized=(text or '').replace('\u00a0',' ').replace('\u202f',' ')
                for pat in [r'\b([0-9]{1,3}(?:[ .][0-9]{3})+)\s*€',r'\b([0-9]{4,6})\s*€',r'"price"\s*:\s*"?([0-9]{4,6})"?']:
                    found=re.search(pat,normalized,re.I)
                    if found and debe_app.valid_price(debe_app.num(found.group(1))):
                        d['price']=debe_app.eur(debe_app.num(found.group(1)));break
            return d
        debe_app.parse_olx=robust_parse_olx

        generic_research=make_research(research_search)

        def calibrated_score(year,km,vinv=''):
            y=debe_app.num(year);k=debe_app.num(km)
            if not y or not k:return 68 if len(vinv or '')==17 else 64
            from datetime import datetime
            age=max(0,datetime.now().year-y);annual=k/max(1,age or 1)
            age_score=max(25,min(98,100-age*2.4))
            annual_score=max(25,min(98,100-(annual/1000)*2.2))
            mileage_score=max(20,min(98,100-(k/1000)*0.18))
            value=age_score*.35+annual_score*.35+mileage_score*.25+(5 if len(vinv or '')==17 else 0)
            return max(25,min(95,round(value)))
        debe_app.score=calibrated_score

        def logged_research(model,engine,year,fuel):
            result=generic_research(model,engine,year,fuel)
            print('DEBE research v5:',model,engine,
                  'results=',result.get('search_results'),
                  'positive=',result.get('positive_results'),
                  'relevant=',result.get('relevant_sources'),
                  'evidence=',len(result.get('evidence') or []),
                  'strengths=',len(result.get('strength_evidence') or []),flush=True)
            return result

        debe_app.dynamic_research=logged_research
        debe_app.search=cloud_search
        debe_app.app.view_functions['comparables']=make_view(debe_app)
        print('DEBE runtime: evidence engine v5 + preventive checks active',flush=True)
    except Exception as e:
        print('DEBE runtime worker patch failed:',e,flush=True)
