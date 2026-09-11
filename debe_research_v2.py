"""DEBE generic research v2.
Builds broad vehicle/engine queries without any per-model profiles and classifies
technical evidence into generic automotive risk categories.
"""
from concurrent.futures import ThreadPoolExecutor, as_completed
from urllib.parse import urlparse
import re, unicodedata
import requests
import debe_runtime_fast as base

HEADERS={'User-Agent':'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 Chrome/124 Safari/537.36','Accept-Language':'pt-PT,pt;q=0.9,en-GB;q=0.8,en;q=0.7'}
S=requests.Session()

def clean(s): return re.sub(r'\s+',' ',s or '').strip()
def alow(s): return unicodedata.normalize('NFKD',s or '').encode('ascii','ignore').decode().lower()

def engine_variants(engine):
    e=clean(engine)
    low=alow(e).replace(',','.')
    # Normalize Portuguese power suffixes so international sources can match.
    power=''
    m=re.search(r'\b(\d{2,3})\s*(?:cv|hp|bhp|ps)\b',low,re.I)
    if m: power=m.group(1)
    core=re.sub(r'\s*(?:cv|hp|bhp|ps)\b','',e,flags=re.I).strip()
    vals=[core]
    if power:
        vals += [clean(core+' '+power), clean(core+' '+power+' hp'), clean(core+' '+power+' PS')]
    out=[]
    for v in vals:
        if v and alow(v) not in [alow(x) for x in out]: out.append(v)
    return out,power

def read_page(u):
    try:
        r=S.get('https://r.jina.ai/'+u,headers=HEADERS,timeout=(3,9));r.raise_for_status();return clean(r.text[:18000])
    except Exception:return ''

def make_research(search_web):
    def dynamic_research(model,engine,year,fuel):
        model=clean(model);engine=clean(engine);year=clean(str(year or ''));fuel=clean(fuel)
        variants,power=engine_variants(engine)
        eng=variants[0] if variants else engine
        identity=clean(' '.join(x for x in [model,year,engine,fuel] if x))
        neg='-site:audi.com -site:audiusa.com -site:bmw.com -site:mercedes-benz.com'
        # Generic query families: model/year, engine family, owners/forums and positives.
        queries=[
            clean(f'{model} {year} {eng} common problems faults injectors DPF EGR turbo oil pump {neg}'),
            clean(f'{model} {eng} {power} known issues reliability forum owners {neg}'),
            clean(f'{model} {year} {eng} injector turbo DPF EGR oil pressure problems {neg}'),
            clean(f'{model} {eng} review reliability fuel economy comfort performance'),
        ]
        rows=[]
        with ThreadPoolExecutor(max_workers=4) as ex:
            futs=[ex.submit(search_web,q,10) for q in queries]
            for f in as_completed(futs):
                try: rows.extend(f.result())
                except Exception: pass
        rows=base.dedup(rows,22)

        pages={}
        with ThreadPoolExecutor(max_workers=6) as ex:
            jobs={ex.submit(read_page,r.get('url','')):r.get('url','') for r in rows[:8] if r.get('url')}
            for f in as_completed(jobs):
                try: pages[jobs[f]]=f.result()
                except Exception: pages[jobs[f]]=''

        mt=[t for t in re.split(r'\W+',alow(model)) if len(t)>=2]
        et=[t for t in re.split(r'\W+',alow(eng)) if len(t)>=2 and t not in ('cv','hp','ps','bhp')]
        docs=[]
        for r in rows:
            blob=alow(' '.join([r.get('title',''),r.get('snippet',''),pages.get(r.get('url',''),'')]))
            mh=sum(1 for t in mt if t in blob)
            eh=sum(1 for t in et if t in blob)
            has_power=bool(power and power in blob)
            model_ok=mh>=max(1,min(2,len(mt)))
            engine_ok=(not et) or eh>=1
            engine_specific=(et and eh>=max(1,min(2,len(et))) and (has_power or len(et)>=2))
            if (model_ok and engine_ok) or engine_specific:
                docs.append((r,blob))

        issues=[];checks=[];evidence=[];sources=[]
        for label,terms,text,check in base.CATS:
            matches=[];domains=set();hits=set()
            for r,blob in docs:
                local=[t for t in terms if alow(t) in blob]
                if local:
                    matches.append(r);domains.add(urlparse(r.get('url','')).netloc.lower());hits.update(local)
            if matches:
                # One highly specific source can be useful; independent domains increase confidence.
                conf=min(96,50+16*min(2,len(domains))+6*min(4,len(hits))+4*min(3,len(matches)))
                if conf>=62: issues.append((conf,label,text,check,matches))
        issues.sort(key=lambda x:-x[0])
        outissues=[]
        for conf,label,text,check,matches in issues[:4]:
            outissues.append(text);checks.append({'title':label,'detail':check});evidence.append({'category':label,'confidence':conf,'matches':len(matches)})
            for r in matches[:2]:
                if r.get('url') and not any(s['url']==r['url'] for s in sources):
                    sources.append({'title':clean(r.get('title','')),'url':r['url']})

        strengths=[];joined=' '.join(blob for _,blob in docs)
        for label,terms,text in base.POS:
            if any(alow(t) in joined for t in terms):strengths.append(text)
            if len(strengths)>=3:break

        if not outissues:
            outissues=['Foram encontradas fontes sobre esta configuração, mas sem consistência suficiente para classificar um problema recorrente.' if rows else 'A pesquisa externa não devolveu resultados; tenta novamente dentro de instantes.']
        if not strengths:
            strengths=['Não foram encontrados pontos fortes técnicos com evidência pública suficiente; isto não significa que o modelo seja desfavorável.']
        if not checks:
            checks=[{'title':'Diagnóstico e VIN','detail':'Confirmar campanhas/recalls pelo VIN e fazer inspeção/diagnóstico independente antes da compra.'}]

        return {
            'strengths':strengths[:3],'issues':outissues[:4],'checks':checks[:4],
            'sources':sources[:8],'evidence':evidence[:6],
            'research_score':max([x['confidence'] for x in evidence],default=30),
            'engine_focus':engine,'research_available':bool(evidence),'identity_used':identity,
            'search_results':len(rows),'relevant_sources':len(docs),
            'queries_used':queries[:4]
        }
    return dynamic_research
