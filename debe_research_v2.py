"""DEBE generic research v2.
Generic model/engine evidence search with cloud-friendly sequential querying.
"""
from concurrent.futures import ThreadPoolExecutor, as_completed
from urllib.parse import urlparse
import re, unicodedata, requests
import debe_runtime_fast as base

HEADERS={'User-Agent':'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 Chrome/124 Safari/537.36','Accept-Language':'pt-PT,pt;q=0.9,en-GB;q=0.8,en;q=0.7'}
S=requests.Session()
def clean(s): return re.sub(r'\s+',' ',s or '').strip()
def alow(s): return unicodedata.normalize('NFKD',(s or '').replace('–','-').replace('—','-')).encode('ascii','ignore').decode().lower()

def research_model(model,engine=''):
    """Keep the make/model/derivative, discard equipment marketing text."""
    value=clean(model);plain=alow(value)
    if plain.startswith('bmw '):
        derivative=re.search(r'\b([1-8]\d{2})[a-z]{0,2}\b',plain)
        if derivative:
            suffix=''
            em=re.search(r'\b'+re.escape(derivative.group(1))+r'([a-z]{1,2})\b',alow(engine))
            if em:suffix=em.group(1)
            return 'BMW '+derivative.group(1)+suffix
        series=re.search(r'\bserie\s+([1-8])\b',plain)
        if series:return 'BMW Série '+series.group(1)
    parts=value.split()
    if len(parts)>=3 and alow(parts[1]) in ('serie','classe','range','model'):
        return ' '.join(parts[:3])
    return ' '.join(parts[:2]) if len(parts)>=2 else value

def engine_variants(engine):
    e=clean(engine);low=alow(e).replace(',','.')
    m=re.search(r'\b(\d{2,3})\s*(?:cv|hp|bhp|ps)\b',low,re.I);power=m.group(1) if m else ''
    core=re.sub(r'\b\d{2,3}\s*(?:cv|hp|bhp|ps)\b','',e,flags=re.I).strip()
    vals=[clean(core+' '+power+' hp') if power else core,core]
    out=[]
    for v in vals:
        if v and alow(v) not in [alow(x) for x in out]: out.append(v)
    return out,power

def contains(text,term):
    return bool(re.search(r'(?<!\w)'+re.escape(alow(term))+r'(?!\w)',alow(text)))

def year_matches(text,year):
    if not str(year).isdigit():return False
    ranges=re.findall(r'\b((?:19|20)\d{2})\s*[-–—/]\s*((?:19|20)\d{2})\b',text)
    if ranges:return any(int(a)<=int(year)<=int(b) for a,b in ranges)
    return contains(text,str(year))

def evidence_fragments(blob,terms,positive=False):
    fragments=re.split(r'(?<=[.!?;])\s+|\n+',blob)
    result=[]
    for fragment in fragments:
        if not any(contains(fragment,t) for t in terms):continue
        if re.search(r"\b(not|no|without|poor|bad|unreliable|lack|lacks|nao|sem)\b",fragment):continue
        if positive:
            if not re.search(r'\b(good|great|excellent|impressive|comfortable|refined|economical|efficient|spacious|practical|reliable|robust|well built|well made|quiet|smooth|positive|bom|boa|confortavel|economico)\b',fragment):continue
        elif not re.search(r'\b(fail(?:ure|ures|ed|ing)?|faults?|problems?|leaks?|broken|defect(?:ive)?|recall|falhas?|avarias?|problemas?|fugas?)\b',fragment):continue
        result.append(clean(fragment)[:500])
    return result

def read_page(u):
    try:
        r=S.get('https://r.jina.ai/'+u,headers=HEADERS,timeout=(2,6));r.raise_for_status();return r.text[:24000]
    except Exception:return ''

def make_research(search_web):
    def dynamic_research(model,engine,year,fuel):
        model=clean(model);engine=clean(engine);year=clean(str(year or ''));fuel=clean(fuel)
        model=research_model(model,engine)
        variants,power=engine_variants(engine);eng=variants[0] if variants else engine
        identity=clean(' '.join(x for x in [model,year,engine,fuel] if x))

        issue_queries=[
            clean(f'"{model}" {year} {eng} common problems'),
            clean(f'"{model}" {year} {eng} reliability faults'),
        ]
        positive_query=clean(f'"{model}" {year} review comfort practicality')

        rows=[]
        # Technical searches stay sequential because search providers rate-limit cloud requests.
        for i,q in enumerate(issue_queries):
            try: rows.extend(search_web(q,10))
            except Exception: pass
            if i==0 and len(base.dedup(rows,20))>=10: break
        rows=base.dedup(rows,18)

        # Always run one independent positive query. Previously this was skipped
        # whenever the first technical query returned enough rows, which caused
        # the generic "no strengths" message even when reviews existed online.
        try: positive_rows=base.dedup(search_web(positive_query,10),10)
        except Exception: positive_rows=[]

        # Reserve page reads for reviews: fault results previously filled every slot.
        combined=base.dedup(positive_rows[:4]+rows[:4],8)
        pages={}
        with ThreadPoolExecutor(max_workers=6) as ex:
            jobs={ex.submit(read_page,r.get('url','')):r.get('url','') for r in combined[:8] if r.get('url')}
            for f in as_completed(jobs):
                try: pages[jobs[f]]=f.result()
                except Exception: pages[jobs[f]]=''

        def relevant_doc(r,technical=False):
            header=alow(r.get('title','')+' '+r.get('snippet',''))
            blob=header+'\n'+alow(pages.get(r.get('url',''),''))
            model_ok=contains(header,model)
            era_ok=year_matches(header,year)
            core=variants[-1] if variants else engine
            engine_ok=bool(core) and contains(blob,core)
            power_ok=not power or contains(blob,power)
            return model_ok and era_ok and (not technical or engine_ok and power_ok),blob

        docs=[]
        for r in rows:
            ok,blob=relevant_doc(r,technical=True)
            if ok: docs.append((r,blob))

        posdocs=[]
        for r in positive_rows:
            ok,blob=relevant_doc(r)
            if ok: posdocs.append((r,blob))

        issues=[];checks=[];evidence=[];sources=[]
        for label,terms,text,check in base.CATS:
            matches=[];domains=set();hits=set()
            for r,blob in docs:
                local=evidence_fragments(blob,terms)
                # Emissions technology must be explicitly tied to this year and
                # engine in the passage, not a sidebar about a later generation.
                if label=='AdBlue / SCR / NOx':
                    local=[part for part in local if year_matches(part,year)
                           and contains(part,variants[-1] if variants else engine)]
                if local:
                    matches.append(r);domains.add(urlparse(r.get('url','')).netloc.lower());hits.update(local)
            if len(domains)>=2:
                conf=min(96,48+16*min(2,len(domains))+7*min(4,len(hits))+5*min(3,len(matches)))
                if conf>=60: issues.append((conf,label,text,check,matches))
        issues.sort(key=lambda x:-x[0]);outissues=[]
        for conf,label,text,check,matches in issues[:4]:
            outissues.append(text);checks.append({'title':label,'detail':check});evidence.append({'category':label,'confidence':conf,'matches':len(matches)})
            for r in matches[:2]:
                if r.get('url') and not any(s['url']==r['url'] for s in sources): sources.append({'title':clean(r.get('title','')),'url':r['url']})

        positive_categories=[
            ('Fiabilidade / robustez',['reliable','reliability','dependable','robust','durable','well built','fiavel','fiabilidade','robusto'],
             'Há referências favoráveis à robustez/fiabilidade desta configuração quando a manutenção é cumprida.'),
            ('Eficiência',['fuel economy','economical','efficient','good mpg','low consumption','consumption','consumos','economico'],
             'Eficiência e consumos são apontados como aspetos positivos desta configuração.'),
            ('Conforto / refinamento',['comfortable','comfort','refined','smooth','ride quality','quiet','confortavel','refinamento'],
             'Conforto e refinamento aparecem como pontos favoráveis em avaliações deste modelo/configuração.'),
            ('Espaço / versatilidade',['spacious','practical','practicality','boot space','cargo space','roomy','versatile','espacoso','bagageira'],
             'Espaço, versatilidade ou praticidade são referidos favoravelmente em avaliações deste modelo.'),
            ('Dinâmica / desempenho',['torque','strong performance','good performance','punchy','handling','steering','road holding','binario','desempenho'],
             'Desempenho, binário ou comportamento dinâmico são mencionados de forma favorável.'),
            ('Qualidade de construção',['build quality','interior quality','solid cabin','quality interior','well made','acabamento','qualidade de construcao'],
             'Qualidade de construção/interior é referida como ponto positivo deste modelo.'),
            ('Tecnologia / segurança',['safety','safe','driver assistance','technology','infotainment','connectivity','seguranca','assistencia conducao'],
             'Tecnologia, segurança ou sistemas de assistência surgem como aspetos positivos deste modelo.')
        ]
        strengths=[];strength_evidence=[]
        for label,terms,text in positive_categories:
            matches=[];domains=set();hits=set()
            for r,blob in posdocs:
                local=evidence_fragments(blob,terms,positive=True)
                if local:
                    matches.append(r);domains.add(urlparse(r.get('url','')).netloc.lower());hits.update(local)
            if matches:
                conf=min(92,50+14*min(2,len(domains))+7*min(3,len(hits)))
                if conf>=60:
                    text=text.replace('desta configuração','deste modelo e época')
                    strengths.append(text);strength_evidence.append({'category':label,'confidence':conf,'matches':len(matches),'scope':'model_year'})
                    for r in matches[:1]:
                        if r.get('url') and not any(s['url']==r['url'] for s in sources): sources.append({'title':clean(r.get('title','')),'url':r['url']})
            if len(strengths)>=3: break

        if not outissues: outissues=['Foram encontradas fontes sobre esta configuração, mas sem consistência suficiente para classificar um problema recorrente.' if rows else 'A pesquisa externa não devolveu resultados; tenta novamente dentro de instantes.']
        if not strengths:
            strengths=['Não foi encontrada evidência positiva suficientemente específica para esta combinação de modelo e motor. O DEBE prefere não inventar um ponto forte.']
        if not checks: checks=[{'title':'Diagnóstico e VIN','detail':'Confirmar campanhas/recalls pelo VIN e fazer inspeção/diagnóstico independente antes da compra.'}]
        return {
            'strengths':strengths[:3],'issues':outissues[:4],'checks':checks[:4],'sources':sources[:8],
            'evidence':evidence[:6],'strength_evidence':strength_evidence[:5],
            'research_score':max([x['confidence'] for x in evidence],default=30),
            'engine_focus':engine,'research_available':bool(evidence or strength_evidence),'identity_used':identity,
            'search_results':len(rows),'positive_results':len(positive_rows),'relevant_sources':len(docs),
            'positive_sources':len(posdocs),'queries_used':issue_queries+[positive_query]
        }
    return dynamic_research
