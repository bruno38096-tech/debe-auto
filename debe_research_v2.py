"""DEBE generic research v3.
Faster generic model/engine evidence search, with sensible matching for older cars.
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
    if not term:return False
    return bool(re.search(r'(?<!\w)'+re.escape(alow(term))+r'(?!\w)',alow(text)))

def years_in(text):
    return [int(x) for x in re.findall(r'\b((?:19|20)\d{2})\b',text or '')]

def era_matches(text,year,tolerance=4):
    if not str(year).isdigit():return True
    y=int(year)
    ranges=re.findall(r'\b((?:19|20)\d{2})\s*[-–—/]\s*((?:19|20)\d{2})\b',text or '')
    if ranges and any(int(a)<=y<=int(b) for a,b in ranges):return True
    found=years_in(text)
    if not found:return True
    return min(abs(v-y) for v in found)<=tolerance

def evidence_fragments(blob,terms,positive=False):
    fragments=re.split(r'(?<=[.!?;])\s+|\n+',blob)
    result=[]
    for fragment in fragments:
        if not any(contains(fragment,t) for t in terms):continue
        if re.search(r"\b(not|no|without|poor|bad|unreliable|lack|lacks|nao|sem)\b",fragment):continue
        if positive:
            if not re.search(r'\b(good|great|excellent|impressive|comfortable|refined|economical|efficient|spacious|practical|reliable|robust|durable|well built|well made|quiet|smooth|positive|strong|bom|boa|confortavel|economico|fiavel)\b',fragment):continue
        elif not re.search(r'\b(fail(?:ure|ures|ed|ing)?|faults?|problems?|issues?|leaks?|broken|defect(?:ive)?|recall|weakness|falhas?|avarias?|problemas?|fugas?)\b',fragment):continue
        result.append(clean(fragment)[:500])
    return result

def read_page(u):
    try:
        r=S.get('https://r.jina.ai/'+u,headers=HEADERS,timeout=(2,5));r.raise_for_status();return r.text[:18000]
    except Exception:return ''

def make_research(search_web):
    def dynamic_research(model,engine,year,fuel):
        model=research_model(clean(model),clean(engine));engine=clean(engine);year=clean(str(year or ''));fuel=clean(fuel)
        variants,power=engine_variants(engine);core=variants[-1] if variants else engine
        identity=clean(' '.join(x for x in [model,year,engine,fuel] if x))

        queries={
            'issues1':clean(f'"{model}" "{core}" common problems faults'),
            'issues2':clean(f'"{model}" "{core}" reliability issues review'),
            'positive1':clean(f'"{model}" review reliability comfort practicality'),
            'positive2':clean(f'"{model}" review build quality handling fuel economy'),
        }
        result_sets={k:[] for k in queries}
        # Search in parallel. This cuts the previous sequential wait while keeping
        # concurrency low enough for cloud search providers.
        with ThreadPoolExecutor(max_workers=3) as ex:
            jobs={ex.submit(search_web,q,8):name for name,q in queries.items()}
            for f in as_completed(jobs):
                try:result_sets[jobs[f]]=base.dedup(f.result(),8)
                except Exception:result_sets[jobs[f]]=[]

        rows=base.dedup(result_sets['issues1']+result_sets['issues2'],14)
        positive_rows=base.dedup(result_sets['positive1']+result_sets['positive2'],12)

        # Read only the highest-value results. Six parallel reads are enough to
        # validate snippets without making the report feel stalled.
        combined=base.dedup(positive_rows[:3]+rows[:3],6)
        pages={}
        with ThreadPoolExecutor(max_workers=6) as ex:
            jobs={ex.submit(read_page,r.get('url','')):r.get('url','') for r in combined if r.get('url')}
            for f in as_completed(jobs):
                try:pages[jobs[f]]=f.result()
                except Exception:pages[jobs[f]]=''

        model_tokens=[x for x in re.split(r'\W+',alow(model)) if len(x)>=2]
        def model_match(header):
            return sum(1 for t in model_tokens if t in alow(header))>=max(1,min(2,len(model_tokens)))

        def relevant_doc(r,technical=False):
            header=clean(r.get('title','')+' '+r.get('snippet',''))
            blob=alow(header+'\n'+pages.get(r.get('url',''),''))
            if not model_match(header):return False,blob
            if not era_matches(header,year,4):return False,blob
            if technical and core and not contains(blob,core):return False,blob
            return True,blob

        docs=[]
        for r in rows:
            ok,blob=relevant_doc(r,technical=True)
            if ok:docs.append((r,blob))
        posdocs=[]
        for r in positive_rows:
            ok,blob=relevant_doc(r,technical=False)
            if ok:posdocs.append((r,blob))

        issues=[];checks=[];evidence=[];sources=[]
        for label,terms,text,check in base.CATS:
            if label=='AdBlue / SCR / NOx' and str(year).isdigit() and int(year)<2010:
                continue
            matches=[];domains=set();hits=set()
            for r,blob in docs:
                local=evidence_fragments(blob,terms)
                if local:
                    matches.append(r);domains.add(urlparse(r.get('url','')).netloc.lower());hits.update(local)
            # Two independent domains = strong evidence. One domain with multiple
            # explicit fault passages is still useful, but labelled lower-confidence.
            if len(domains)>=2 or (len(domains)==1 and len(hits)>=2):
                conf=min(94,52+14*min(2,len(domains))+6*min(4,len(hits))+4*min(3,len(matches)))
                if conf>=60:issues.append((conf,label,text,check,matches))
        issues.sort(key=lambda x:-x[0]);outissues=[]
        for conf,label,text,check,matches in issues[:4]:
            outissues.append(text);checks.append({'title':label,'detail':check});evidence.append({'category':label,'confidence':conf,'matches':len(matches)})
            for r in matches[:2]:
                if r.get('url') and not any(s['url']==r['url'] for s in sources):sources.append({'title':clean(r.get('title','')),'url':r['url']})

        positive_categories=[
            ('Fiabilidade / robustez',['reliable','reliability','dependable','robust','durable','well built','fiavel','fiabilidade','robusto'],
             'Há referências favoráveis à robustez/fiabilidade deste modelo e época quando a manutenção é cumprida.'),
            ('Eficiência',['fuel economy','economical','efficient','good mpg','low consumption','consumption','consumos','economico'],
             'Eficiência e consumos são apontados como aspetos positivos deste modelo e época.'),
            ('Conforto / refinamento',['comfortable','comfort','refined','smooth','ride quality','quiet','confortavel','refinamento'],
             'Conforto e refinamento aparecem como pontos favoráveis em avaliações deste modelo e época.'),
            ('Espaço / versatilidade',['spacious','practical','practicality','boot space','cargo space','roomy','versatile','espacoso','bagageira'],
             'Espaço, versatilidade ou praticidade são referidos favoravelmente em avaliações deste modelo.'),
            ('Dinâmica / desempenho',['torque','strong performance','good performance','punchy','handling','steering','road holding','binario','desempenho'],
             'Desempenho, binário ou comportamento dinâmico são mencionados de forma favorável.'),
            ('Qualidade de construção',['build quality','interior quality','solid cabin','quality interior','well made','acabamento','qualidade de construcao'],
             'Qualidade de construção/interior é referida como ponto positivo deste modelo.'),
        ]
        strengths=[];strength_evidence=[]
        for label,terms,text in positive_categories:
            matches=[];domains=set();hits=set()
            for r,blob in posdocs:
                local=evidence_fragments(blob,terms,positive=True)
                if local:
                    matches.append(r);domains.add(urlparse(r.get('url','')).netloc.lower());hits.update(local)
            if matches:
                conf=min(90,58+10*min(2,len(domains))+5*min(3,len(hits)))
                strengths.append(text);strength_evidence.append({'category':label,'confidence':conf,'matches':len(matches),'scope':'model_era'})
                for r in matches[:1]:
                    if r.get('url') and not any(s['url']==r['url'] for s in sources):sources.append({'title':clean(r.get('title','')),'url':r['url']})
            if len(strengths)>=3:break

        if not outissues:
            outissues=['Foram encontradas fontes sobre este modelo/motor, mas sem repetição suficiente para classificar um problema recorrente.' if rows else 'A pesquisa externa não devolveu resultados; tenta novamente dentro de instantes.']
        if not strengths:
            strengths=['Não foi encontrada evidência positiva suficientemente consistente nas fontes devolvidas. O DEBE não inventa pontos fortes.']
        if not checks:
            checks=[{'title':'Diagnóstico e VIN','detail':'Confirmar campanhas/recalls pelo VIN e fazer inspeção/diagnóstico independente antes da compra.'}]
        return {
            'strengths':strengths[:3],'issues':outissues[:4],'checks':checks[:4],'sources':sources[:8],
            'evidence':evidence[:6],'strength_evidence':strength_evidence[:5],
            'research_score':max([x['confidence'] for x in evidence],default=30),
            'engine_focus':engine,'research_available':bool(evidence or strength_evidence),'identity_used':identity,
            'search_results':len(rows),'positive_results':len(positive_rows),'relevant_sources':len(docs),
            'positive_sources':len(posdocs),'queries_used':list(queries.values())
        }
    return dynamic_research
