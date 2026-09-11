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
        from concurrent.futures import ThreadPoolExecutor
        import app as debe_app
        import debe_runtime_fast as fast
        from debe_search_providers import make_search
        from debe_research_v2 import make_research
        from debe_market_v2 import make_view

        cloud_search = make_search(fast.search_web)

        # OLX often puts the exact engine/power only in the description, while
        # the old parser looked mainly at the title/structured fields.
        original_engine_hint = debe_app.engine_hint
        def robust_engine_hint(text, url=''):
            first = original_engine_hint(text, url)
            if first:
                return first
            blob = debe_app.clean((debe_app.title_line(text) or '') + ' ' + (text or '')[:12000])
            patterns = [
                r'\b(\d[.,]\d)\s*(TDI|TFSI|TSI|dCi|BlueHDi|PureTech)\s*(\d{2,3})\s*(?:cv|hp|bhp|ps)\b',
                r'\b(\d[.,]\d)\s*(TDI|TFSI|TSI|dCi|BlueHDi|PureTech)\b[^\n.]{0,100}?\b(\d{2,3})\s*(?:cv|hp|bhp|ps)\b',
                r'\b(\d[.,]\d)\s*(TDI|TFSI|TSI|dCi|BlueHDi|PureTech)\b'
            ]
            for pat in patterns:
                m=re.search(pat,blob,re.I)
                if not m:
                    continue
                if len(m.groups())>=3:
                    return debe_app.clean(f'{m.group(1)} {m.group(2)} {m.group(3)} cv').replace(',','.')
                return debe_app.clean(f'{m.group(1)} {m.group(2)}').replace(',','.')
            return ''
        debe_app.engine_hint = robust_engine_hint

        # Strengthen OLX parsing. Normalize non-breaking spaces first because
        # OLX/Jina can render 18.950 €, 18 950 € or 18 950 € depending on the run.
        original_parse_olx = debe_app.parse_olx
        def robust_parse_olx(text, url):
            d=original_parse_olx(text,url)
            d['engine']=robust_engine_hint(text,url) or d.get('engine','')
            if not d.get('price'):
                price_n=0
                normalized=(text or '').replace('\u00a0',' ').replace('\u202f',' ')
                compact=debe_app.clean(normalized)
                candidates=[normalized,compact]
                patterns=[
                    r'(?:^|\n)\s*(?:#+\s*)?([0-9]{1,3}(?:[ .][0-9]{3})+)\s*€\s*(?:$|\n)',
                    r'\b([0-9]{1,3}(?:[ .][0-9]{3})+)\s*€',
                    r'\b([0-9]{4,6})\s*€',
                    r'"price"\s*:\s*"?([0-9]{4,6})"?'
                ]
                for blob in candidates:
                    for pat in patterns:
                        for m in re.finditer(pat,blob,re.I|re.M):
                            n=debe_app.num(m.group(1))
                            if debe_app.valid_price(n):
                                price_n=n;break
                        if price_n:break
                    if price_n:break

                # Exact-ad search fallback. Searching only by the OLX ID is more
                # reliable than combining ID + full title, which was too strict.
                if not price_n:
                    adid=''
                    mm=re.search(r'-ID([A-Za-z0-9]+)\.html',url or '',re.I)
                    if mm:adid='ID'+mm.group(1)
                    title=debe_app.title_line(text) or d.get('title','')
                    queries=[]
                    if adid:queries.append(f'"{adid}"')
                    if title:queries.append(f'"{title}" site:olx.pt')
                    for query in queries:
                        try:rows=cloud_search(query,10)
                        except Exception:rows=[]
                        for row in rows:
                            blob=debe_app.clean(((row.get('title') or '')+' '+(row.get('snippet') or '')).replace('\u00a0',' ').replace('\u202f',' '))
                            m=re.search(r'\b([0-9]{1,3}(?:[ .][0-9]{3})+|[0-9]{4,6})\s*€',blob,re.I)
                            if m and debe_app.valid_price(debe_app.num(m.group(1))):
                                price_n=debe_app.num(m.group(1));break
                        if price_n:break
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

        def _norm(s):
            return re.sub(r'[^a-z0-9]+','',fast.alow(s or ''))

        def _model_ok(blob,model):
            low=fast.alow(blob)
            toks=[x for x in re.split(r'\W+',fast.alow(model)) if len(x)>=2]
            return sum(1 for x in toks if x in low)>=max(1,min(2,len(toks)))

        def snippet_fallback(model,engine,year,fuel):
            """Cheap fallback using search snippets only; runs beside full research."""
            engine_core=re.sub(r'\b\d{2,3}\s*(?:cv|hp|bhp|ps)\b','',engine or '',flags=re.I).strip()
            issue_q=f'"{model}" "{engine_core}" common problems DPF EGR turbo gearbox reliability'
            positive_q=f'"{model}" {year} review comfort build quality fuel economy handling'
            try:issue_rows=cloud_search(issue_q,10)
            except Exception:issue_rows=[]
            try:positive_rows=cloud_search(positive_q,10)
            except Exception:positive_rows=[]

            issue_rows=[r for r in issue_rows if _model_ok((r.get('title') or '')+' '+(r.get('snippet') or ''),model)]
            positive_rows=[r for r in positive_rows if _model_ok((r.get('title') or '')+' '+(r.get('snippet') or ''),model)]

            outissues=[];checks=[];evidence=[];strengths=[];strength_evidence=[];sources=[]
            neg_words=('problem','problems','issue','issues','fault','failure','fail','recall','clog','blocked','leak','weak','avaria','problema','falha')
            for label,terms,text,check in fast.CATS:
                if label=='AdBlue / SCR / NOx' and str(year).isdigit() and int(year)<2010:
                    continue
                matches=[]
                for r in issue_rows:
                    blob=fast.alow((r.get('title') or '')+' '+(r.get('snippet') or ''))
                    if any(fast.alow(t) in blob for t in terms) and any(w in blob for w in neg_words):
                        matches.append(r)
                if matches:
                    conf=min(82,58+8*min(3,len(matches)))
                    outissues.append(text);checks.append({'title':label,'detail':check});evidence.append({'category':label,'confidence':conf,'matches':len(matches),'scope':'snippet'})
                    for r in matches[:2]:
                        if r.get('url') and not any(s.get('url')==r.get('url') for s in sources):
                            sources.append({'title':debe_app.clean(r.get('title','')),'url':r['url']})
                if len(outissues)>=3:break

            positive_categories=[
                ('Conforto / refinamento',['comfortable','comfort','refined','smooth','ride quality','quiet','confortavel'],'Conforto e refinamento aparecem como pontos favoráveis em avaliações deste modelo e época.'),
                ('Qualidade de construção',['build quality','interior quality','high quality','well made','well built','solid','top-notch','acabamento'],'Qualidade de construção/interior é referida como ponto positivo deste modelo.'),
                ('Eficiência',['fuel economy','economical','efficient','good mpg','low consumption','consumption','consumos'],'Eficiência e consumos são apontados como aspetos positivos deste modelo e época.'),
                ('Dinâmica / desempenho',['handling','steering','performance','torque','responsive','agile','road holding'],'Comportamento dinâmico, direção ou desempenho são mencionados de forma favorável.'),
                ('Fiabilidade / robustez',['reliable','reliability','dependable','robust','durable','trouble free','fiavel'],'Há referências favoráveis à robustez/fiabilidade deste modelo quando a manutenção é cumprida.')
            ]
            pos_words=('good','great','excellent','impressive','comfortable','refined','smooth','quality','solid','strong','agile','economical','efficient','reliable','top-notch','pleasant','bom','boa','confortavel')
            for label,terms,text in positive_categories:
                matches=[]
                for r in positive_rows:
                    blob=fast.alow((r.get('title') or '')+' '+(r.get('snippet') or ''))
                    if any(fast.alow(t) in blob for t in terms) and any(w in blob for w in pos_words):
                        matches.append(r)
                if matches:
                    strengths.append(text);strength_evidence.append({'category':label,'confidence':min(86,62+8*min(3,len(matches))),'matches':len(matches),'scope':'snippet'})
                    r=matches[0]
                    if r.get('url') and not any(s.get('url')==r.get('url') for s in sources):
                        sources.append({'title':debe_app.clean(r.get('title','')),'url':r['url']})
                if len(strengths)>=3:break
            return {'issues':outissues,'checks':checks,'evidence':evidence,'strengths':strengths,'strength_evidence':strength_evidence,'sources':sources[:8],
                    'search_results':len(issue_rows),'positive_results':len(positive_rows)}

        def _generic_message(values):
            text=' '.join(values or []).lower()
            return (not values or 'não foi encontrada evidência' in text or 'não foram encontrados pontos fortes' in text
                    or 'sem repetição suficiente' in text or 'sem consistência suficiente' in text)

        def logged_research(model,engine,year,fuel):
            # Run the snippet fallback in parallel so it does not add another
            # wait after the full research has already completed.
            with ThreadPoolExecutor(max_workers=2) as ex:
                full_job=ex.submit(generic_research,model,engine,year,fuel)
                quick_job=ex.submit(snippet_fallback,model,engine,year,fuel)
                result=full_job.result()
                quick=quick_job.result()

            if _generic_message(result.get('strengths')) and quick.get('strengths'):
                result['strengths']=quick['strengths'][:3]
                result['strength_evidence']=quick.get('strength_evidence',[])[:5]
            if _generic_message(result.get('issues')) and quick.get('issues'):
                result['issues']=quick['issues'][:4]
                result['checks']=quick.get('checks',[])[:4] or result.get('checks')
                result['evidence']=quick.get('evidence',[])[:6]
                result['research_score']=max([x.get('confidence',0) for x in result['evidence']],default=result.get('research_score',30))
            if quick.get('strengths') or quick.get('issues'):
                result['research_available']=True
            merged=[]
            for src in (result.get('sources') or [])+(quick.get('sources') or []):
                if src.get('url') and not any(x.get('url')==src.get('url') for x in merged):
                    merged.append(src)
            result['sources']=merged[:8]
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
        print('DEBE runtime: resilient OLX parser + parallel evidence fallback active', flush=True)
    except Exception as e:
        print('DEBE runtime worker patch failed:', e, flush=True)
