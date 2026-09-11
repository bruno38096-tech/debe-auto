"""DEBE research v4: fast, evidence-led and useful for beta users.

The engine deliberately separates three evidence scopes:
- model/year reviews -> strengths and model-level weaknesses
- engine-family sources -> engine/emissions weaknesses
- preventive checks -> useful buying checks even when evidence is sparse

No vehicle-specific profile is hardcoded.
"""
from concurrent.futures import ThreadPoolExecutor, as_completed
from urllib.parse import urlparse
import re, unicodedata, requests
import debe_runtime_fast as base

HEADERS={'User-Agent':'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 Chrome/124 Safari/537.36','Accept-Language':'pt-PT,pt;q=0.9,en-GB;q=0.8,en;q=0.7'}
S=requests.Session()

def clean(s): return re.sub(r'\s+',' ',s or '').strip()
def alow(s): return unicodedata.normalize('NFKD',(s or '').replace('–','-').replace('—','-')).encode('ascii','ignore').decode().lower()

def research_model(model):
    value=clean(model);plain=alow(value);parts=value.split()
    if plain.startswith('bmw '):
        d=re.search(r'\b([1-8]\d{2})[a-z]{0,2}\b',plain)
        if d:return 'BMW '+d.group(1)
        s=re.search(r'\bserie\s+([1-8])\b',plain)
        if s:return 'BMW Série '+s.group(1)
    if len(parts)>=3 and alow(parts[1]) in ('serie','classe','range','model'):
        return ' '.join(parts[:3])
    return ' '.join(parts[:2]) if len(parts)>=2 else value

def engine_parts(engine):
    e=clean(engine).replace(',','.')
    power=''
    m=re.search(r'\b(\d{2,3})\s*(?:cv|hp|bhp|ps)\b',e,re.I)
    if m:power=m.group(1)
    core=re.sub(r'\b\d{2,3}\s*(?:cv|hp|bhp|ps)\b','',e,flags=re.I).strip(' ,.-')
    full=clean(core+' '+power) if power else core
    return core,full,power

def read_page(url):
    if not url:return ''
    try:
        r=S.get('https://r.jina.ai/'+url,headers=HEADERS,timeout=(2,4));r.raise_for_status()
        return clean(r.text[:16000])
    except Exception:return ''

def model_match(text,model):
    toks=[x for x in re.split(r'\W+',alow(model)) if len(x)>=2]
    low=alow(text)
    return sum(1 for x in toks if x in low)>=max(1,min(2,len(toks)))

def engine_match(text,core,power=''):
    low=alow(text);compact=re.sub(r'\W+','',low);ccompact=re.sub(r'\W+','',alow(core))
    family=[x for x in re.split(r'\W+',alow(core)) if len(x)>=2 and not x.isdigit()]
    family_ok=(ccompact and ccompact in compact) or (family and sum(1 for x in family if x in low)>=max(1,min(2,len(family))))
    return bool(family_ok and (not power or power in low or family_ok))

def fragments(text):
    return [clean(x) for x in re.split(r'(?<=[.!?;])\s+|\n+',text or '') if clean(x)]

NEG=('problem','problems','issue','issues','fault','faults','failure','fail','failed','clog','blocked','leak','wear','recall','warning','jerk','hesitat','malfunction','avaria','avarias','problema','problemas','falha','falhas','fuga','desgaste','entup')
NEGATE=(' no ',' not ',' without ',' sem problema',' no problem',' trouble-free',' trouble free')
POS=('good','great','excellent','impressive','comfortable','refined','smooth','quality','well built','well-made','well made','solid','strong','agile','economical','efficient','reliable','dependable','robust','pleasant','premium','upscale','quiet','confident','bom','boa','confortavel','economico','fiavel')

def negative_hits(blob,terms):
    out=[]
    lowall=' '+alow(blob)+' '
    title_problem=any(x in lowall[:600] for x in ('common problems','known problems','common faults','pontos fracos','problemas do'))
    for part in fragments(blob):
        low=' '+alow(part)+' '
        if any(n in low for n in NEGATE):continue
        if any(alow(t) in low for t in terms) and (title_problem or any(n in low for n in NEG)):
            out.append(part[:500])
    return out

def positive_hits(blob,terms):
    out=[]
    for part in fragments(blob):
        low=' '+alow(part)+' '
        if any(n in low for n in (' poor ',' bad ',' unreliable ',' uncomfortable ',' disappointing ',' cramped ',' harsh ')):continue
        if any(alow(t) in low for t in terms) and any(p in low for p in POS):out.append(part[:500])
    return out

def source_domain(r):return urlparse(r.get('url','')).netloc.lower()

def preventive_checks(fuel,year):
    x=alow(fuel);checks=[]
    if 'diesel' in x:
        checks.extend([
            {'title':'DPF / EGR','detail':'Fazer diagnóstico ao DPF/EGR: carga de cinzas/fuligem, histórico de regenerações, erros memorizados e sinais de utilização maioritariamente urbana.'},
            {'title':'Arranque a frio e injeção','detail':'Testar o motor completamente frio; verificar ralenti, fumo, correções dos injetores e eventuais erros de pressão de combustível.'},
            {'title':'Turbo e admissão','detail':'Em ensaio sob carga, confirmar pressão de sobrealimentação, ausência de assobios anormais, fugas de óleo/ar e perda de potência.'}
        ])
    elif any(k in x for k in ('gasolina','petrol')):
        checks.extend([
            {'title':'Arranque a frio / consumo de óleo','detail':'Testar a frio, procurar ruídos anormais, fumo e confirmar histórico de consumo/fugas de óleo.'},
            {'title':'Turbo e admissão','detail':'Testar resposta sob carga e verificar pressão, mangueiras, fugas e erros de sobrealimentação.'},
            {'title':'Refrigeração','detail':'Confirmar nível e estabilidade do refrigerante, fugas, bomba de água e termóstato.'}
        ])
    elif any(k in x for k in ('eletr','electric')):
        checks.extend([
            {'title':'Bateria de tração','detail':'Obter o estado de saúde (SoH), verificar desequilíbrio entre células e histórico de erros do BMS.'},
            {'title':'Carregamento','detail':'Testar carregamento AC/DC quando aplicável e confirmar ausência de erros no carregador de bordo.'},
            {'title':'Sistema de alta tensão','detail':'Confirmar diagnóstico eletrónico, campanhas/recalls e integridade do circuito de alta tensão.'}
        ])
    else:
        checks.extend([
            {'title':'Diagnóstico eletrónico','detail':'Fazer leitura completa de erros em todos os módulos antes da compra.'},
            {'title':'Arranque a frio','detail':'Testar o veículo totalmente frio e observar ruídos, fumo, vibrações e avisos no painel.'}
        ])
    checks.append({'title':'VIN e histórico','detail':'Confirmar VIN, campanhas/recalls, histórico documental de manutenção e fazer inspeção independente.'})
    return checks[:4]

def make_research(search_web):
    def dynamic_research(model,engine,year,fuel):
        model=research_model(clean(model));engine=clean(engine);year=clean(str(year or ''));fuel=clean(fuel)
        core,full_engine,power=engine_parts(engine)
        model_year=clean(model+' '+year)

        queries={
            'model_issues':clean(f'"{model}" {year} common problems reliability used buying guide'),
            'model_review':clean(f'"{model}" {year} review comfort interior build quality handling pros cons'),
            'model_review2':clean(f'"{model}" review ride quality practicality fuel economy interior'),
            'engine_issues':clean(f'"{full_engine or core}" common problems DPF EGR turbo injectors water pump reliability'),
            'engine_issues2':clean(f'"{core}" {power} common faults problems reliability') if core else ''
        }
        result_sets={k:[] for k in queries}
        with ThreadPoolExecutor(max_workers=5) as ex:
            jobs={ex.submit(search_web,q,8):name for name,q in queries.items() if q}
            for f in as_completed(jobs):
                try:result_sets[jobs[f]]=base.dedup(f.result(),8)
                except Exception:result_sets[jobs[f]]=[]

        model_issue_rows=base.dedup(result_sets['model_issues'],8)
        review_rows=base.dedup(result_sets['model_review']+result_sets['model_review2'],12)
        engine_rows=base.dedup(result_sets['engine_issues']+result_sets['engine_issues2'],10)

        # Enrich only the most promising snippets; all reads happen in parallel.
        chosen=base.dedup(review_rows[:2]+model_issue_rows[:2]+engine_rows[:2],6)
        pages={}
        with ThreadPoolExecutor(max_workers=6) as ex:
            jobs={ex.submit(read_page,r.get('url','')):r.get('url','') for r in chosen if r.get('url')}
            for f in as_completed(jobs):
                try:pages[jobs[f]]=f.result()
                except Exception:pages[jobs[f]]=''

        def blob(r):return clean((r.get('title') or '')+'\n'+(r.get('snippet') or '')+'\n'+pages.get(r.get('url',''),'') )
        model_docs=[(r,blob(r)) for r in base.dedup(model_issue_rows+review_rows,16) if model_match((r.get('title') or '')+' '+(r.get('snippet') or '')+' '+pages.get(r.get('url',''),''),model)]
        review_docs=[(r,blob(r)) for r in review_rows if model_match((r.get('title') or '')+' '+(r.get('snippet') or '')+' '+pages.get(r.get('url',''),''),model)]
        engine_docs=[(r,blob(r)) for r in engine_rows if not core or engine_match((r.get('title') or '')+' '+(r.get('snippet') or '')+' '+pages.get(r.get('url',''),''),core,power)]

        # Strengths are intentionally model-level: comfort, build quality and
        # handling do not need an exact engine match.
        positive_categories=[
            ('Conforto / refinamento',['comfortable','comfort','refined','smooth','ride quality','quiet','pleasant ride','confortavel','refinamento'],'Conforto e refinamento são referidos favoravelmente em avaliações deste modelo/geração.'),
            ('Qualidade de construção',['build quality','interior quality','high quality','materials','well crafted','well-crafted','upscale interior','premium interior','acabamento'],'Qualidade de construção e do interior aparecem como pontos fortes deste modelo.'),
            ('Dinâmica / comportamento',['handling','steering','driving dynamics','body control','agile','confidence-inspiring','road holding'],'Comportamento dinâmico, estabilidade ou direção são apontados como aspetos positivos.'),
            ('Eficiência',['fuel economy','economical','efficient','good mpg','low consumption','consumption','consumos'],'Eficiência/consumos surgem como ponto favorável nas avaliações encontradas.'),
            ('Praticidade',['practical','practicality','cargo','boot space','spacious','versatile'],'Praticidade, espaço ou capacidade de carga são referidos favoravelmente.'),
            ('Fiabilidade / robustez',['reliable','reliability','dependable','robust','durable','trouble-free','trouble free','fiavel'],'Há referências favoráveis à robustez/fiabilidade, condicionadas a manutenção adequada.')
        ]
        strengths=[];strength_evidence=[];sources=[]
        for label,terms,text in positive_categories:
            matches=[];hits=[]
            for r,b in review_docs:
                local=positive_hits(b,terms)
                if local:matches.append(r);hits.extend(local)
            if matches:
                domains={source_domain(r) for r in matches if source_domain(r)}
                conf=min(92,62+10*min(2,len(domains))+4*min(3,len(hits)))
                strengths.append(text);strength_evidence.append({'category':label,'confidence':conf,'matches':len(matches),'scope':'model_generation'})
                r=matches[0]
                if r.get('url') and not any(s.get('url')==r['url'] for s in sources):sources.append({'title':clean(r.get('title','')),'url':r['url']})
            if len(strengths)>=3:break

        # Engine-related categories may use engine-family sources; transmission
        # and electronics stay model-specific to avoid cross-model contamination.
        engine_labels={'Lubrificação / bomba de óleo','Injeção','DPF / EGR','Turbo / sobrealimentação','Distribuição','Refrigeração','AdBlue / SCR / NOx'}
        issues=[];checks=[];evidence=[]
        for label,terms,text,check in base.CATS:
            if label=='AdBlue / SCR / NOx' and year.isdigit() and int(year)<2009:continue
            docs=engine_docs if label in engine_labels and engine_docs else model_docs
            matches=[];hits=[]
            for r,b in docs:
                local=negative_hits(b,terms)
                if local:matches.append(r);hits.extend(local)
            if matches:
                domains={source_domain(r) for r in matches if source_domain(r)}
                conf=min(94,60+12*min(2,len(domains))+5*min(3,len(hits)))
                issues.append((conf,label,text,check,matches))
        issues.sort(key=lambda x:-x[0])
        outissues=[]
        for conf,label,text,check,matches in issues[:4]:
            outissues.append(text);checks.append({'title':label,'detail':check});evidence.append({'category':label,'confidence':conf,'matches':len(matches),'scope':'engine_family' if label in engine_labels else 'model_generation'})
            for r in matches[:2]:
                if r.get('url') and not any(s.get('url')==r['url'] for s in sources):sources.append({'title':clean(r.get('title','')),'url':r['url']})

        # Verification advice must always be useful in the beta, even where the
        # public web evidence is too sparse to call a recurring fault.
        preventive=preventive_checks(fuel,year)
        seen={x['title'] for x in checks}
        for item in preventive:
            if item['title'] not in seen:
                checks.append(item);seen.add(item['title'])
            if len(checks)>=4:break

        if not strengths:
            strengths=['Não foi possível confirmar um ponto forte específico com as fontes devolvidas nesta pesquisa.']
        if not outissues:
            outissues=['Não foi possível confirmar um problema recorrente específico com as fontes devolvidas; usa as verificações preventivas abaixo antes da compra.']

        return {
            'strengths':strengths[:3],'issues':outissues[:4],'checks':checks[:4],'sources':sources[:8],
            'evidence':evidence[:6],'strength_evidence':strength_evidence[:5],
            'research_score':max([x['confidence'] for x in evidence],default=35),
            'engine_focus':engine,'research_available':bool(evidence or strength_evidence),'identity_used':clean(model_year+' '+engine+' '+fuel),
            'search_results':len(model_issue_rows)+len(engine_rows),'positive_results':len(review_rows),
            'relevant_sources':len(model_docs)+len(engine_docs),'positive_sources':len(review_docs),
            'queries_used':[q for q in queries.values() if q]
        }
    return dynamic_research
