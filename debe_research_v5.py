"""DEBE research v5.

Goal: reliably return useful strengths, recurring weaknesses and buyer checks for
beta users without hardcoding vehicle-specific profiles. Search provenance is
used as evidence scope; classification is deliberately less brittle than v4.
"""
from concurrent.futures import ThreadPoolExecutor, as_completed
from urllib.parse import urlparse
import re, unicodedata
import debe_runtime_fast as base


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
    m=re.search(r'\b(\d{2,3})\s*(?:cv|hp|bhp|ps)\b',e,re.I)
    power=m.group(1) if m else ''
    core=re.sub(r'\b\d{2,3}\s*(?:cv|hp|bhp|ps)\b','',e,flags=re.I).strip(' ,.-')
    return core,power

def row_blob(row):
    return clean((row.get('title') or '')+' '+(row.get('snippet') or ''))

def model_match(text,model):
    toks=[x for x in re.split(r'\W+',alow(model)) if len(x)>=2]
    low=alow(text)
    return sum(1 for x in toks if x in low)>=max(1,min(2,len(toks)))

def engine_match(text,core):
    if not core:return True
    low=alow(text);compact=re.sub(r'\W+','',low);cc=re.sub(r'\W+','',alow(core))
    if cc and cc in compact:return True
    toks=[x for x in re.split(r'\W+',alow(core)) if len(x)>=2 and not x.isdigit()]
    return bool(toks and any(x in low for x in toks))

def dedup(rows,n=12): return base.dedup(rows,n)
def domain(row): return urlparse(row.get('url','')).netloc.lower()
def has_any(text,terms):
    low=alow(text)
    return any(alow(t) in low for t in terms)

NEG=('problem','problems','issue','issues','fault','faults','failure','fail','failed','clog','blocked','leak','wear','recall','warning','malfunction','avaria','avarias','problema','problemas','falha','falhas','fuga','desgaste','entup')
BAD=('poor','bad','unreliable','uncomfortable','cramped','harsh','disappointing')
GOOD=('good','great','excellent','impressive','comfortable','refined','smooth','quality','well built','well-made','solid','strong','agile','economical','efficient','reliable','dependable','robust','pleasant','premium','upscale','quiet','confident','bom','boa','confortavel','economico','fiavel')

STRENGTHS=[
 ('Conforto / refinamento',['comfortable','comfort','refined','smooth','ride quality','quiet','pleasant ride','refinement'],
  'As avaliações consultadas destacam favoravelmente o conforto e o refinamento deste modelo/geração.'),
 ('Qualidade de construção',['build quality','interior quality','high quality','materials','well crafted','well-crafted','upscale interior','premium interior','cabin quality'],
  'A qualidade de construção e do interior surge como um dos pontos fortes deste modelo.'),
 ('Dinâmica / comportamento',['handling','steering','driving dynamics','body control','agile','confidence-inspiring','road holding'],
  'O comportamento dinâmico, a estabilidade ou a direção são referidos favoravelmente nas avaliações encontradas.'),
 ('Eficiência',['fuel economy','economical','efficient','good mpg','low consumption','consumption','fuel efficiency'],
  'A eficiência e os consumos são apontados como aspetos favoráveis nas fontes consultadas.'),
 ('Praticidade',['practical','practicality','cargo','boot space','spacious','versatile','usable space'],
  'A praticidade, o espaço ou a versatilidade são mencionados favoravelmente nas avaliações encontradas.'),
 ('Fiabilidade / robustez',['reliable','reliability','dependable','robust','durable','trouble-free','trouble free'],
  'Existem referências favoráveis à robustez/fiabilidade, desde que a manutenção tenha sido adequada.')
]

ISSUES=[
 ('DPF / EGR',['dpf','fap','diesel particulate filter','egr','regeneration'],
  'Existem referências recorrentes a DPF/FAP, EGR ou regenerações nesta motorização.',
  'Recomenda-se diagnóstico ao DPF/EGR, incluindo carga de cinzas/fuligem, histórico de regenerações e erros memorizados.'),
 ('Turbo / sobrealimentação',['turbo','underboost','overboost','boost pressure','turbo actuator','variable vane'],
  'Foram encontrados relatos relacionados com o turbo ou o controlo de sobrealimentação.',
  'Recomenda-se testar a pressão de sobrealimentação sob carga e verificar assobios anormais, fugas, fumo ou perda de potência.'),
 ('Injeção',['injector','injectors','fuel injector','injetor','injetores','piezo'],
  'Foram encontrados relatos relacionados com os injetores ou o sistema de injeção.',
  'Recomenda-se verificar correções dos injetores, arranque a frio, ralenti e eventuais erros de pressão de combustível.'),
 ('Refrigeração',['water pump','thermostat','coolant leak','coolant loss','bomba de agua','termostato'],
  'Foram encontradas referências a problemas no circuito de refrigeração.',
  'Recomenda-se verificar fugas, bomba de água, termóstato e estabilidade da temperatura de funcionamento.'),
 ('Distribuição',['timing belt','timing chain','wet belt','tensioner','correia de distribuicao','corrente de distribuicao'],
  'Existem referências ao sistema de distribuição nesta configuração.',
  'Recomenda-se confirmar o tipo de distribuição, intervalo de manutenção, histórico documental e ruídos anormais.'),
 ('Transmissão / embraiagem',['gearbox','transmission','clutch','flywheel','dsg','s tronic','multitronic','dual mass flywheel'],
  'Existem referências a transmissão, embraiagem ou volante bimassa nesta geração/configuração.',
  'Recomenda-se testar a transmissão a frio e a quente e confirmar a respetiva manutenção.'),
 ('Eletrónica',['electrical fault','electrical problem','electronic fault','infotainment','electrical issue'],
  'Foram encontrados relatos de falhas elétricas ou eletrónicas neste modelo/geração.',
  'Recomenda-se testar todos os equipamentos e realizar um diagnóstico eletrónico completo.'),
 ('Lubrificação / consumo de óleo',['oil pump','oil pressure','low oil pressure','oil consumption','balance shaft','hex shaft'],
  'Foram encontradas referências ao sistema de lubrificação, pressão ou consumo de óleo.',
  'Recomenda-se confirmar histórico, consumo de óleo e pressão de óleo quando aplicável.')
]

def preventive_checks(fuel):
    f=alow(fuel)
    if 'diesel' in f:
        return [
          {'title':'DPF / EGR','detail':'Recomenda-se diagnóstico ao DPF/EGR: carga de cinzas/fuligem, histórico de regenerações e erros memorizados.'},
          {'title':'Arranque a frio e injeção','detail':'Recomenda-se testar o motor completamente frio e verificar ralenti, fumo, correções dos injetores e pressão de combustível.'},
          {'title':'Turbo e admissão','detail':'Recomenda-se ensaio sob carga para verificar pressão de sobrealimentação, fugas, assobios anormais e perda de potência.'},
          {'title':'VIN e histórico','detail':'Recomenda-se confirmar VIN, campanhas/recalls, histórico documental de manutenção e efetuar uma inspeção independente.'}
        ]
    if any(x in f for x in ('gasolina','petrol')):
        return [
          {'title':'Arranque a frio / óleo','detail':'Recomenda-se testar o motor completamente frio e verificar ruídos, fumo, fugas e consumo de óleo.'},
          {'title':'Turbo e admissão','detail':'Recomenda-se testar a resposta sob carga e verificar pressão, mangueiras e fugas.'},
          {'title':'Refrigeração','detail':'Recomenda-se confirmar nível de refrigerante, fugas, bomba de água e termóstato.'},
          {'title':'VIN e histórico','detail':'Recomenda-se confirmar VIN, campanhas/recalls, histórico documental de manutenção e efetuar uma inspeção independente.'}
        ]
    return [
      {'title':'Diagnóstico eletrónico','detail':'Recomenda-se uma leitura completa de erros em todos os módulos antes da compra.'},
      {'title':'Arranque a frio','detail':'Recomenda-se testar o veículo completamente frio e observar ruídos, vibrações e avisos no painel.'},
      {'title':'VIN e histórico','detail':'Recomenda-se confirmar VIN, campanhas/recalls, histórico documental de manutenção e efetuar uma inspeção independente.'}
    ]

def make_research(search_web):
    def dynamic_research(model,engine,year,fuel):
        model=research_model(clean(model));engine=clean(engine);year=clean(str(year or ''));fuel=clean(fuel)
        core,power=engine_parts(engine)
        queries={
          'review':clean(f'"{model}" {year} review comfort interior quality handling fuel economy'),
          'review2':clean(f'"{model}" review pros cons comfort build quality handling practicality'),
          'engine_emissions':clean(f'"{core}" {power} common problems DPF EGR turbo injectors') if core else '',
          'engine_mechanical':clean(f'"{core}" {power} common faults water pump timing oil consumption reliability') if core else '',
          'model_faults':clean(f'"{model}" {year} common problems gearbox electronics reliability')
        }
        sets={k:[] for k in queries}
        with ThreadPoolExecutor(max_workers=5) as ex:
            jobs={ex.submit(search_web,q,10):k for k,q in queries.items() if q}
            for fut in as_completed(jobs):
                try:sets[jobs[fut]]=dedup(fut.result(),10)
                except Exception:sets[jobs[fut]]=[]

        review_rows=dedup(sets['review']+sets['review2'],14)
        engine_rows=dedup(sets['engine_emissions']+sets['engine_mechanical'],14)
        model_fault_rows=dedup(sets['model_faults'],10)

        # Queries themselves already scope the evidence. Matching is used to
        # reject obvious cross-model noise, but does not discard all rows when a
        # search provider omits the quoted term from its snippet.
        model_review=[r for r in review_rows if model_match(row_blob(r),model)] or review_rows[:6]
        model_faults=[r for r in model_fault_rows if model_match(row_blob(r),model)] or model_fault_rows[:5]
        engine_docs=[r for r in engine_rows if engine_match(row_blob(r),core)] or engine_rows[:6]

        strengths=[];strength_evidence=[];issues=[];evidence=[];checks=[];sources=[]
        review_text=' '.join(row_blob(r) for r in model_review)
        review_low=alow(review_text)
        for label,terms,text in STRENGTHS:
            matched=[r for r in model_review if has_any(row_blob(r),terms)]
            # A category mention in a review query is accepted unless the same
            # result is explicitly negative. Requiring positive and category
            # words in one sentence caused the v4 false negatives seen in prod.
            matched=[r for r in matched if not any(b in alow(row_blob(r)) for b in BAD)]
            if matched:
                domains={domain(r) for r in matched if domain(r)}
                conf=min(90,60+10*min(2,len(domains))+5*min(3,len(matched)))
                strengths.append(text);strength_evidence.append({'category':label,'confidence':conf,'matches':len(matched),'scope':'model_generation'})
                r=matched[0]
                if r.get('url') and not any(s.get('url')==r['url'] for s in sources):sources.append({'title':clean(r.get('title','')),'url':r['url']})
            if len(strengths)>=3:break

        all_issue_docs=engine_docs+model_faults
        for label,terms,text,check in ISSUES:
            docs=engine_docs if label not in ('Transmissão / embraiagem','Eletrónica') else model_faults
            matched=[]
            for r in docs:
                b=row_blob(r);low=alow(b)
                if has_any(b,terms) and (any(n in low for n in NEG) or 'common problem' in low or 'common fault' in low):matched.append(r)
            if matched:
                domains={domain(r) for r in matched if domain(r)}
                conf=min(92,62+10*min(2,len(domains))+5*min(3,len(matched)))
                issues.append(text);evidence.append({'category':label,'confidence':conf,'matches':len(matched),'scope':'engine_family' if docs is engine_docs else 'model_generation'})
                checks.append({'title':label,'detail':check})
                for r in matched[:2]:
                    if r.get('url') and not any(s.get('url')==r['url'] for s in sources):sources.append({'title':clean(r.get('title','')),'url':r['url']})
            if len(issues)>=4:break

        # If the provider returned category-specific engine results but omitted
        # generic words such as "problem" from snippets, accept repeated category
        # mentions from at least two independent domains as lower-confidence evidence.
        if not issues:
            for label,terms,text,check in ISSUES:
                docs=engine_docs if label not in ('Transmissão / embraiagem','Eletrónica') else model_faults
                matched=[r for r in docs if has_any(row_blob(r),terms)]
                domains={domain(r) for r in matched if domain(r)}
                if len(domains)>=2:
                    issues.append(text);evidence.append({'category':label,'confidence':66,'matches':len(matched),'scope':'engine_family'})
                    checks.append({'title':label,'detail':check})
                if len(issues)>=3:break

        # Always return practical checks, de-duplicating evidence-led checks.
        seen={x['title'] for x in checks}
        for item in preventive_checks(fuel):
            if item['title'] not in seen:checks.append(item);seen.add(item['title'])
            if len(checks)>=4:break

        if not strengths:
            strengths=['As fontes consultadas não permitem destacar um ponto forte específico com confiança suficiente.']
        if not issues:
            issues=['As fontes consultadas não permitem classificar um problema recorrente específico com confiança suficiente. As verificações abaixo continuam a ser recomendadas antes da compra.']

        return {
          'strengths':strengths[:3],'issues':issues[:4],'checks':checks[:4],'sources':sources[:8],
          'evidence':evidence[:6],'strength_evidence':strength_evidence[:5],
          'research_score':max([e['confidence'] for e in evidence],default=35),
          'engine_focus':engine,'research_available':bool(evidence or strength_evidence),
          'identity_used':clean(model+' '+year+' '+engine+' '+fuel),
          'search_results':len(engine_rows)+len(model_fault_rows),'positive_results':len(review_rows),
          'relevant_sources':len(engine_docs)+len(model_faults),'positive_sources':len(model_review),
          'queries_used':[q for q in queries.values() if q]
        }
    return dynamic_research
