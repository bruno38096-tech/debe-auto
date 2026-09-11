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
        from debe_research_v2 import make_research
        from debe_market_v2 import make_view

        cloud_search = make_search(fast.search_web)

        # OLX often puts the exact engine/power only in the description, while
        # the old parser looked mainly at the title/structured fields. That left
        # engine empty and made technical research impossible.
        original_engine_hint = debe_app.engine_hint
        def robust_engine_hint(text, url=''):
            first = original_engine_hint(text, url)
            if first:
                return first
            blob = debe_app.clean((debe_app.title_line(text) or '') + ' ' + (text or '')[:9000])
            patterns = [
                r'\b(\d[.,]\d)\s*(TDI|TFSI|TSI|dCi|BlueHDi|PureTech)\s*(\d{2,3})\s*(?:cv|hp|bhp|ps)\b',
                r'\b(\d[.,]\d)\s*(TDI|TFSI|TSI|dCi|BlueHDi|PureTech)\b[^\n.]{0,80}?\b(\d{2,3})\s*(?:cv|hp|bhp|ps)\b',
                r'\b(\d[.,]\d)\s*(TDI|TFSI|TSI|dCi|BlueHDi|PureTech)\b'
            ]
            for i,pat in enumerate(patterns):
                m=re.search(pat,blob,re.I)
                if not m: continue
                if len(m.groups())>=3:
                    return debe_app.clean(f'{m.group(1)} {m.group(2)} {m.group(3)} cv').replace(',','.')
                return debe_app.clean(f'{m.group(1)} {m.group(2)}').replace(',','.')
            return ''
        debe_app.engine_hint = robust_engine_hint

        # Strengthen OLX parsing. Some cloud responses omit the price from the
        # first viewport even when it is present later in the page or indexed by
        # search. Use the full page first, then the ad ID/title as a fallback.
        original_parse_olx = debe_app.parse_olx
        def robust_parse_olx(text, url):
            d=original_parse_olx(text,url)
            d['engine']=robust_engine_hint(text,url) or d.get('engine','')
            if not d.get('price'):
                price_n=0
                for pat in [
                    r'(?:^|\n)\s*(?:#+\s*)?([0-9]{1,3}(?:[ .][0-9]{3})+)\s*€\s*(?:$|\n)',
                    r'\b([0-9]{4,6})\s*€\b',
                    r'"price"\s*:\s*"?([0-9]{4,6})"?'
                ]:
                    for m in re.finditer(pat,text or '',re.I|re.M):
                        n=debe_app.num(m.group(1))
                        if debe_app.valid_price(n):
                            price_n=n;break
                    if price_n:break
                if not price_n:
                    adid=''
                    mm=re.search(r'-ID([A-Za-z0-9]+)\.html',url or '',re.I)
                    if mm:adid='ID'+mm.group(1)
                    title=debe_app.title_line(text) or d.get('title','')
                    query=f'"{adid}" "{title}" OLX preço' if adid else f'"{title}" site:olx.pt'
                    try:rows=cloud_search(query,8)
                    except Exception:rows=[]
                    for row in rows:
                        blob=debe_app.clean((row.get('title') or '')+' '+(row.get('snippet') or ''))
                        m=re.search(r'\b([0-9]{1,3}(?:[ .][0-9]{3})+|[0-9]{4,6})\s*€',blob,re.I)
                        if m and debe_app.valid_price(debe_app.num(m.group(1))):
                            price_n=debe_app.num(m.group(1));break
                if price_n:d['price']=debe_app.eur(price_n)
            return d
        debe_app.parse_olx = robust_parse_olx

        generic_research = make_research(cloud_search)

        def calibrated_score(year, km, vinv=''):
            """Useful 0-100 preliminary score without collapsing older cars at 35."""
            y=debe_app.num(year); k=debe_app.num(km)
            if not y or not k:
                return 68 if len(vinv or '')==17 else 64
            from datetime import datetime
            age=max(0,datetime.now().year-y)
            annual=k/max(1,age or 1)
            age_score=max(25,min(98,100-age*2.4))
            annual_score=max(25,min(98,100-(annual/1000)*2.2))
            mileage_score=max(20,min(98,100-(k/1000)*0.18))
            value=age_score*.35+annual_score*.35+mileage_score*.25+(5 if len(vinv or '')==17 else 0)
            return max(25,min(95,round(value)))

        debe_app.score = calibrated_score

        def logged_research(model,engine,year,fuel):
            result=generic_research(model,engine,year,fuel)
            print('DEBE research:', model, engine,
                  'results=',result.get('search_results'),
                  'positive=',result.get('positive_results'),
                  'relevant=',result.get('relevant_sources'),
                  'positive_relevant=',result.get('positive_sources'),
                  'evidence=',len(result.get('evidence') or []),
                  'strengths=',len(result.get('strength_evidence') or []), flush=True)
            return result

        debe_app.dynamic_research = logged_research
        debe_app.search = cloud_search
        debe_app.app.view_functions['comparables'] = make_view(debe_app)
        print('DEBE runtime: OLX parser + fast research + calibrated score active', flush=True)
    except Exception as e:
        print('DEBE runtime worker patch failed:', e, flush=True)