"""Runtime improvements for DEBE beta.

This module keeps research generic: no car-by-car profiles. It performs broad
web discovery, reads a small set of sources and classifies repeated technical
signals for the detected model/engine.
"""
from concurrent.futures import ThreadPoolExecutor, as_completed
from urllib.parse import quote_plus, urlparse, parse_qs, unquote
import html
import re
import requests
from bs4 import BeautifulSoup

HEADERS={
    'User-Agent':'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 Chrome/124 Safari/537.36',
    'Accept-Language':'pt-PT,pt;q=0.9,en;q=0.8'
}
_session=requests.Session()

def clean(s):
    return re.sub(r'\s+',' ',html.unescape(s or '')).strip()

def alow(s):
    import unicodedata
    return unicodedata.normalize('NFKD',s or '').encode('ascii','ignore').decode().lower()

def resolve(h):
    if not h:return ''
    if h.startswith('//'):h='https:'+h
    try:
        q=parse_qs(urlparse(h).query)
        if q.get('uddg'):return unquote(q['uddg'][0])
    except Exception:pass
    return h

def _dedup(rows,n):
    out=[];seen=set()
    for r in rows:
        u=r.get('url','')
        if not u or u in seen:continue
        host=urlparse(u).netloc.lower()
        if any(x in host for x in ['google.','bing.com','duckduckgo.com','yahoo.com','jina.ai']):continue
        seen.add(u);out.append(r)
        if len(out)>=n:break
    return out

def _duck(q,n):
    try:
        r=_session.get('https://html.duckduckgo.com/html/?q='+quote_plus(q),headers=HEADERS,timeout=(3,9));r.raise_for_status()
        s=BeautifulSoup(r.text,'html.parser');out=[]
        for x in s.select('.result'):
            a=x.select_one('.result__a');sn=x.select_one('.result__snippet')
            if a:out.append({'title':clean(a.get_text(' ',strip=True)),'snippet':clean(sn.get_text(' ',strip=True) if sn else ''),'url':resolve(a.get('href',''))})
            if len(out)>=n:break
        return out
    except Exception:return []

def _bing(q,n):
    try:
        r=_session.get('https://www.bing.com/search?q='+quote_plus(q)+'&count='+str(max(10,n)),headers=HEADERS,timeout=(3,10));r.raise_for_status()
        s=BeautifulSoup(r.text,'html.parser');out=[]
        for x in s.select('li.b_algo'):
            a=x.select_one('h2 a');sn=x.select_one('.b_caption p') or x.select_one('p')
            if a and a.get('href','').startswith('http'):
                out.append({'title':clean(a.get_text(' ',strip=True)),'snippet':clean(sn.get_text(' ',strip=True) if sn else ''),'url':a.get('href','')})
            if len(out)>=n:break
        return out
    except Exception:return []

def _jina_serp(q,n):
    targets=[
        'https://r.jina.ai/https://www.bing.com/search?q='+quote_plus(q),
        'https://r.jina.ai/https://www.google.com/search?q='+quote_plus(q)+'&num=10&hl=en'
    ]
    pat=re.compile(r'\[([^\]\n]{3,220})\]\((https?://[^)\s]+)\)',re.I)
    for target in targets:
        try:
            r=_session.get(target,headers=HEADERS,timeout=(4,16));r.raise_for_status();out=[]
            for m in pat.finditer(r.text or ''):
                title=clean(re.sub(r'[`*_#>|]+',' ',m.group(1)));u=html.unescape(m.group(2)).strip();host=urlparse(u).netloc.lower()
                if not title or not host or any(x in host for x in ['google.','bing.com','jina.ai','gstatic.com','microsoft.com']):continue
                tail=(r.text or '')[m.end():m.end()+700]
                snippet=clean(re.sub(r'\[([^\]]+)\]\([^)]*\)',r'\1',re.sub(r'[`*_#>|]+',' ',tail)))[:550]
                out.append({'title':title,'snippet':snippet,'url':u})
                if len(out)>=n:break
            if out:return out
        except Exception:pass
    return []

def search_web(q,n=12):
    rows=[]
    for provider in (_duck,_bing,_jina_serp):
        rows.extend(provider(q,n))
        rows=_dedup(rows,n)
        if len(rows)>=min(5,n):break
    return _dedup(rows,n)

def _reader(url):
    try:
        r=_session.get('https://r.jina.ai/'+url,headers=HEADERS,timeout=(4,14));r.raise_for_status()
        return clean(r.text[:18000])
    except Exception:return ''

CATEGORIES=[
 ('Lubrificação / bomba de óleo',['oil pump','oil pressure','low oil pressure','bomba de oleo','pressao de oleo','balance shaft','hex shaft','oil consumption','consumo de oleo'],
  'Foram encontradas referências recorrentes ao sistema de lubrificação, pressão/bomba de óleo ou consumo de óleo.',
  'Confirmar histórico e pressão de óleo quando aplicável; verificar se existem revisões preventivas/campanhas para esta variante.'),
 ('Injeção',['injector','injectors','injetor','injetores','piezo','siemens injector','fuel injector'],
  'Foram encontrados relatos relacionados com injetores ou sistema de injeção.',
  'Fazer diagnóstico às correções de injeção, arranque/ralenti e confirmar substituições ou campanhas anteriores.'),
 ('DPF / EGR',['dpf','diesel particulate filter','fap','egr','filtro de particulas','valvula egr','regeneration'],
  'Existem referências recorrentes a DPF/FAP, EGR ou regenerações nesta motorização.',
  'Verificar carga do filtro, histórico de regenerações, erros EGR e o tipo de utilização anterior.'),
 ('Turbo / sobrealimentação',['turbo','underboost','overboost','boost pressure','turbo actuator','atuador turbo','variable vane'],
  'Foram encontrados relatos ligados ao turbo ou ao controlo de sobrealimentação.',
  'Testar pressão/atuador sob carga e procurar erros, assobios, fumo ou perda de potência.'),
 ('Distribuição',['timing belt','timing chain','wet belt','correia de distribuicao','corrente de distribuicao','tensioner'],
  'Há referências ao sistema de distribuição nesta configuração.',
  'Confirmar tipo de distribuição, intervalo, histórico documental e ruídos/sinais anormais.'),
 ('Refrigeração',['water pump','thermostat','coolant leak','bomba de agua','termostato','fuga de refrigerante'],
  'Foram encontrados relatos relativos ao circuito de refrigeração.',
  'Verificar fugas, resíduos, bomba de água, termóstato e estabilidade da temperatura.'),
 ('Transmissão / embraiagem',['gearbox','transmission','clutch','flywheel','dsg','s tronic','multitronic','caixa','embraiagem','volante bimassa'],
  'Há referências a transmissão, embraiagem ou volante bimassa nesta configuração.',
  'Testar a frio e a quente, verificar vibrações/patinação e confirmar manutenção da caixa quando aplicável.'),
 ('AdBlue / SCR / NOx',['adblue','scr','nox sensor','sensor nox'],
  'Existem referências ao sistema SCR/AdBlue ou sensores NOx.',
  'Ler códigos de erro e confirmar funcionamento e campanhas do sistema de emissões.'),
 ('Eletrónica',['electrical fault','electrical problem','electronic fault','infotainment','falha eletrica','problema eletrico'],
  'Foram encontrados relatos de falhas elétricas ou eletrónicas.',
  'Testar todos os equipamentos e fazer diagnóstico eletrónico completo antes da compra.'),
 ('Bateria / carregamento',['battery degradation','battery health','onboard charger','charging fault','charging problem','bms','bateria de tracao','carregador de bordo'],
  'Há referências à bateria de tração ou ao sistema de carregamento.',
  'Confirmar SoH da bateria, erros BMS e testar carregamento AC/DC.')
]

POSITIVE=[
 ('Fiabilidade',['reliable','dependable','robust','reliability','fiavel','fiabilidade'],'Há referências favoráveis à robustez/fiabilidade quando a manutenção é cumprida.'),
 ('Eficiência',['fuel economy','economical','efficient','good mpg','consumption','consumos','economico'],'Eficiência e consumos aparecem como pontos positivos desta configuração.'),
 ('Conforto / refinamento',['comfortable','comfort','refined','smooth','confortavel','refinamento'],'Conforto e refinamento são aspetos favoráveis mencionados para este modelo/configuração.'),
 ('Desempenho / binário',['torque','strong performance','good performance','punchy','binario','desempenho'],'Desempenho e entrega de binário são apontados como pontos favoráveis desta motorização.')
]

def _identity(model,engine,year,fuel):
    base=clean(model)
    # Preserve the engine: it is often the strongest identifier of recurring issues.
    exact=clean(' '.join(x for x in [base,engine,str(year or ''),fuel] if x))
    core=clean(' '.join(x for x in [base,engine] if x))
    return base,exact,core

def dynamic_research(model,engine,year,fuel):
    base,exact,core=_identity(model,engine,year,fuel)
    queries=[
        f'"{core}" common problems reliability',
        f'"{core}" known issues oil pump injectors DPF EGR turbo',
        f'"{core}" forum problems faults',
        f'"{base}" "{engine}" common faults',
        f'"{exact}" problems'
    ]
    rows=[]
    for q in queries:
        rows.extend(search_web(q,10))
    rows=_dedup(rows,18)

    # Read several independent sources; this is more reliable than snippets alone.
    page_text={}
    with ThreadPoolExecutor(max_workers=5) as ex:
        jobs={ex.submit(_reader,r['url']):r for r in rows[:8]}
        for f in as_completed(jobs):
            r=jobs[f]
            try:page_text[r['url']]=f.result()
            except Exception:page_text[r['url']]=''

    model_tokens=[t for t in re.split(r'\W+',alow(base)) if len(t)>=2]
    engine_tokens=[t for t in re.split(r'\W+',alow(engine)) if len(t)>=2 and t not in ['cv','hp']]
    evidence_docs=[]
    for r in rows:
        blob=alow(' '.join([r.get('title',''),r.get('snippet',''),page_text.get(r.get('url',''),'')]))
        model_hit=sum(1 for t in model_tokens if t in blob)
        engine_hit=sum(1 for t in engine_tokens if t in blob)
        # Exact model + some engine evidence preferred; for engine-family sources allow engine-heavy evidence.
        relevant=(model_hit>=max(1,min(2,len(model_tokens))) and (not engine_tokens or engine_hit>=1)) or engine_hit>=max(2,min(3,len(engine_tokens)))
        if relevant:evidence_docs.append((r,blob))

    issues=[];checks=[];evidence=[];sources=[]
    for label,terms,text,check in CATEGORIES:
        matching=[];hits=set();domains=set()
        for r,blob in evidence_docs:
            local=[term for term in terms if alow(term) in blob]
            if local:
                matching.append(r);hits.update(local);domains.add(urlparse(r.get('url','')).netloc.lower())
        if matching:
            confidence=min(95,38+22*min(2,len(domains))+8*min(3,len(hits)))
            # One strongly-specific source is useful; two independent domains make it high-confidence.
            if confidence>=60:
                issues.append((confidence,text,label,check,matching))
    issues.sort(key=lambda x:-x[0])

    out_issues=[]
    for confidence,text,label,check,matching in issues[:4]:
        out_issues.append(text);checks.append({'title':label,'detail':check});evidence.append({'category':label,'confidence':confidence,'matches':len(matching)})
        for r in matching[:2]:
            u=r.get('url','');tt=clean(r.get('title',''))
            if u and tt and not any(s['url']==u for s in sources):sources.append({'title':tt,'url':u})

    strengths=[]
    positive_query=search_web(f'"{core}" review reliability fuel economy comfort performance',10)
    posdocs=[]
    for r in positive_query:
        blob=alow((r.get('title') or '')+' '+(r.get('snippet') or ''))
        if sum(1 for t in model_tokens if t in blob)>=1:posdocs.append((r,blob))
    for label,terms,text in POSITIVE:
        matching=[r for r,blob in posdocs if any(alow(t) in blob for t in terms)]
        if matching:
            strengths.append(text)
            for r in matching[:1]:
                if r.get('url') and not any(s['url']==r['url'] for s in sources):sources.append({'title':clean(r.get('title','')),'url':r['url']})
        if len(strengths)>=3:break

    if not out_issues:
        # Important UX distinction: provider failure vs genuinely sparse evidence.
        msg='A pesquisa externa não devolveu evidência técnica suficiente para classificar problemas com confiança.' if rows else 'A pesquisa externa não devolveu resultados; tenta novamente dentro de instantes.'
        out_issues=[msg]
    if not strengths:
        strengths=['Não foram encontrados pontos fortes técnicos com evidência pública suficiente; isto não significa que o modelo seja desfavorável.']
    if not checks:
        checks=[{'title':'Diagnóstico e VIN','detail':'Confirmar campanhas/recalls pelo VIN e fazer uma inspeção/diagnóstico independente antes da compra.'}]

    return {
        'strengths':strengths[:3], 'issues':out_issues[:4], 'checks':checks[:4],
        'sources':sources[:8], 'evidence':evidence[:6],
        'research_score':max([e['confidence'] for e in evidence],default=30),
        'engine_focus':engine, 'research_available':bool(evidence),
        'identity_used':exact, 'search_results':len(rows), 'relevant_sources':len(evidence_docs)
    }

def patch_index(path='index.html'):
    """Inject score interpretation UI without rewriting the current landing/report markup."""
    marker='debe-score-guide-runtime'
    try:
        txt=open(path,encoding='utf-8').read()
        if marker in txt:return
        css='''<style id="debe-score-guide-runtime">.scoreGuide{margin-top:12px;display:flex;flex-wrap:wrap;gap:6px;font-size:11px;color:#5f6673}.scoreGuide span{padding:5px 8px;border-radius:999px;background:#f2f4f8;border:1px solid #e3e6ef}.scoreGuide .active{font-weight:900;border-color:#8172ff;background:#f0edff;color:#4938bd}.scoreGuideNote{font-size:11px;color:#707785;margin-top:7px}</style>'''
        js='''<script>(function(){function apply(){var s=document.getElementById('score'),rating=document.getElementById('rating'),text=document.getElementById('scoreText');if(!s||!text)return;var n=parseInt(s.textContent)||0;if(!document.getElementById('scoreGuide')){var d=document.createElement('div');d.id='scoreGuide';d.innerHTML='<div class="scoreGuide"><span data-band="low">35–49 · Risco elevado</span><span data-band="caution">50–64 · Cautela</span><span data-band="interesting">65–79 · Interessante</span><span data-band="good">80+ · Bom candidato</span></div><div class="scoreGuideNote">Referência preliminar: a partir de 80 o DEBE considera o anúncio um bom candidato; 65–79 merece validação aprofundada.</div>';text.insertAdjacentElement('afterend',d)}var band=n>=80?'good':n>=65?'interesting':n>=50?'caution':'low';document.querySelectorAll('#scoreGuide [data-band]').forEach(function(x){x.classList.toggle('active',x.dataset.band===band)});if(rating&&n){rating.textContent=n>=80?'Bom candidato':n>=65?'Interessante, validar':n>=50?'Cautela':'Risco elevado'}var wheel=s.closest('.wheel');if(wheel&&n){var c=n>=80?'#20b26b':n>=65?'#e7b52b':n>=50?'#ff9a16':'#e85d5d';wheel.style.background='conic-gradient('+c+' 0 '+n+'%,#edf0f5 '+n+'%)'}}var obs=new MutationObserver(apply);document.addEventListener('DOMContentLoaded',function(){apply();var s=document.getElementById('score');if(s)obs.observe(s,{childList:true,characterData:true,subtree:true})});})();</script>'''
        txt=txt.replace('</head>',css+'</head>').replace('</body>',js+'</body>')
        open(path,'w',encoding='utf-8').write(txt)
    except Exception as e:
        print('DEBE index patch failed:',e,flush=True)
