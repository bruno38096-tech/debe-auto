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

        def clean_research_rows(rows):
            cleaned=[]
            for row in rows or []:
                item=dict(row)
                snippet=item.get('snippet') or ''
                snippet=re.split(r'Find elsewhere|\[Google\]|\[Bing\]|Google\s*\(|Bing\s*\(',snippet,1,flags=re.I)[0]
                snippet=re.sub(r'https?://\S+',' ',snippet)
                snippet=re.sub(r'\[([^\]]+)\]\([^)]*\)',r'\1',snippet)
                item['snippet']=debe_app.clean(snippet)
                cleaned.append(item)
            return cleaned

        def research_search(query,n=10):
            original=query
            qlow=(query or '').lower()
            if 'review' in qlow:
                quoted=re.findall(r'"([^"]{2,80})"',query or '')
                identity=quoted[0] if quoted else ''
                year_match=re.search(r'\b(20\d{2})\b',query or '')
                if identity:
                    rows=cloud_search(f'"{identity}" review',n)
                    if len(rows)<3 and year_match:
                        extra=cloud_search(f'"{identity}" {year_match.group(1)} review',n)
                        rows=fast.dedup(rows+extra,n)
                else:rows=cloud_search(query,n)
            else:rows=cloud_search(query,n)
            rows=clean_research_rows(rows)
            sample=' || '.join(debe_app.clean((r.get('title') or '')+' :: '+(r.get('snippet') or ''))[:220] for r in rows[:3])
            print('DEBE sample:',debe_app.clean(original)[:70],'->',sample,flush=True)
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

        def configuration_strengths(engine,fuel):
            out=[];evidence=[];low=(fuel or '').lower();eng=engine or ''
            power_match=re.search(r'\b(\d{2,3})\s*(?:cv|hp|bhp|ps)\b',eng,re.I)
            if 'diesel' in low:
                out.append('A configuração Diesel é favorável para utilização rodoviária e percursos longos, sobretudo quando se procura autonomia e consumo contido.')
                evidence.append({'category':'Adequação a percursos longos','confidence':58,'matches':1,'scope':'configuration'})
            elif any(x in low for x in ('gasolina','petrol')):
                out.append('A configuração a gasolina favorece uma utilização versátil, incluindo trajetos curtos e utilização urbana frequente.')
                evidence.append({'category':'Versatilidade de utilização','confidence':58,'matches':1,'scope':'configuration'})
            if power_match:
                p=int(power_match.group(1))
                if p>=150:
                    out.append(f'A potência declarada de {p} cv oferece uma reserva de desempenho relevante para autoestrada, ultrapassagens e utilização com carga.')
                    evidence.append({'category':'Reserva de desempenho','confidence':62,'matches':1,'scope':'configuration'})
            if re.search(r'\b(TDI|dCi|BlueHDi|CDI|CRDi)\b',eng,re.I):
                out.append('A motorização turbodiesel favorece a disponibilidade de binário em regimes médios, útil em recuperações e condução diária.')
                evidence.append({'category':'Binário / recuperações','confidence':58,'matches':1,'scope':'configuration'})
            return out[:3],evidence[:3]

        def logged_research(model,engine,year,fuel):
            result=generic_research(model,engine,year,fuel)
            strength_text=' '.join(result.get('strengths') or []).lower()
            if (not result.get('strength_evidence')) or 'não permitem destacar' in strength_text or 'não foi possível' in strength_text:
                contextual,context_ev=configuration_strengths(engine,fuel)
                if contextual:
                    result['strengths']=contextual
                    result['strength_evidence']=context_ev
                    result['research_available']=True
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
        print('DEBE runtime: evidence engine v5 + configuration strengths + preventive checks active',flush=True)
    except Exception as e:
        print('DEBE runtime worker patch failed:',e,flush=True)
