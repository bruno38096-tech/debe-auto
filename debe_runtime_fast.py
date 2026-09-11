"""Fast generic evidence engine for DEBE.
No per-car hardcoded profiles: model/engine are discovered from the listing and
all technical conclusions are based on web evidence found at request time.
"""
from concurrent.futures import ThreadPoolExecutor, as_completed
from urllib.parse import quote_plus, urlparse, parse_qs, unquote
import html,re,requests,unicodedata
from bs4 import BeautifulSoup

HEADERS={'User-Agent':'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 Chrome/124 Safari/537.36','Accept-Language':'pt-PT,pt;q=0.9,en;q=0.8'}
S=requests.Session()
def clean(s):return re.sub(r'\s+',' ',html.unescape(s or '')).strip()
def alow(s):return unicodedata.normalize('NFKD',s or '').encode('ascii','ignore').decode().lower()
def resolve(h):
    if not h:return ''
    if h.startswith('//'):h='https:'+h
    try:
        q=parse_qs(urlparse(h).query)
        if q.get('uddg'):return unquote(q['uddg'][0])
    except:pass
    return h

def dedup(rows,n=16):
    out=[];seen=set()
    for r in rows:
        u=r.get('url','');host=urlparse(u).netloc.lower() if u else ''
        if not u or u in seen or any(x in host for x in ['google.','bing.com','duckduckgo.com','jina.ai']):continue
        seen.add(u);out.append(r)
        if len(out)>=n:break
    return out

def bing(q,n=10):
    try:
        r=S.get('https://www.bing.com/search?q='+quote_plus(q)+'&count='+str(max(10,n)),headers=HEADERS,timeout=(2,6));r.raise_for_status();s=BeautifulSoup(r.text,'html.parser');out=[]
        for x in s.select('li.b_algo'):
            a=x.select_one('h2 a');p=x.select_one('.b_caption p') or x.select_one('p')
            if a and a.get('href','').startswith('http'):out.append({'title':clean(a.get_text(' ',strip=True)),'snippet':clean(p.get_text(' ',strip=True) if p else ''),'url':a.get('href','')})
            if len(out)>=n:break
        return out
    except:return []

def duck(q,n=10):
    try:
        r=S.get('https://html.duckduckgo.com/html/?q='+quote_plus(q),headers=HEADERS,timeout=(2,6));r.raise_for_status();s=BeautifulSoup(r.text,'html.parser');out=[]
        for x in s.select('.result'):
            a=x.select_one('.result__a');p=x.select_one('.result__snippet')
            if a:out.append({'title':clean(a.get_text(' ',strip=True)),'snippet':clean(p.get_text(' ',strip=True) if p else ''),'url':resolve(a.get('href',''))})
            if len(out)>=n:break
        return out
    except:return []

def jina(q,n=10):
    target='https://r.jina.ai/https://www.google.com/search?q='+quote_plus(q)+'&num=10&hl=en'
    try:
        r=S.get(target,headers=HEADERS,timeout=(3,9));r.raise_for_status();out=[]
        pat=re.compile(r'\[([^\]\n]{3,220})\]\((https?://[^)\s]+)\)',re.I)
        for m in pat.finditer(r.text or ''):
            u=html.unescape(m.group(2));host=urlparse(u).netloc.lower()
            if any(x in host for x in ['google.','gstatic','jina.ai']):continue
            title=clean(re.sub(r'[`*_#>|]+',' ',m.group(1)))
            tail=(r.text or '')[m.end():m.end()+500];snippet=clean(re.sub(r'[`*_#>|]+',' ',tail))[:420]
            out.append({'title':title,'snippet':snippet,'url':u})
            if len(out)>=n:break
        return out
    except:return []

def search_web(q,n=10):
    rows=bing(q,n)
    if len(rows)<4:rows+=duck(q,n)
    if len(dedup(rows,n))<4:rows+=jina(q,n)
    return dedup(rows,n)

def read_page(u):
    try:
        r=S.get('https://r.jina.ai/'+u,headers=HEADERS,timeout=(3,9));r.raise_for_status();return clean(r.text[:14000])
    except:return ''

CATS=[
('Lubrificação / bomba de óleo',['oil pump','oil pressure','low oil pressure','bomba de oleo','pressao de oleo','balance shaft','hex shaft','oil consumption','consumo de oleo'],'Foram encontradas referências recorrentes ao sistema de lubrificação, pressão/bomba de óleo ou consumo de óleo.','Confirmar histórico e pressão de óleo quando aplicável; verificar revisões preventivas/campanhas para esta variante.'),
('Injeção',['injector','injectors','injetor','injetores','piezo','siemens injector'],'Foram encontrados relatos relacionados com injetores ou sistema de injeção.','Fazer diagnóstico às correções de injeção, arranque/ralenti e confirmar substituições ou campanhas anteriores.'),
('DPF / EGR',['dpf','fap','diesel particulate filter','egr','filtro de particulas','regeneration'],'Existem referências recorrentes a DPF/FAP, EGR ou regenerações nesta motorização.','Verificar carga do filtro, histórico de regenerações, erros EGR e tipo de utilização anterior.'),
('Turbo / sobrealimentação',['turbo','underboost','overboost','boost pressure','turbo actuator','variable vane'],'Foram encontrados relatos ligados ao turbo ou ao controlo de sobrealimentação.','Testar pressão/atuador sob carga e procurar erros, assobios, fumo ou perda de potência.'),
('Distribuição',['timing belt','timing chain','wet belt','correia de distribuicao','corrente de distribuicao','tensioner'],'Há referências ao sistema de distribuição nesta configuração.','Confirmar tipo de distribuição, intervalo, histórico documental e ruídos/sinais anormais.'),
('Refrigeração',['water pump','thermostat','coolant leak','bomba de agua','termostato'],'Foram encontrados relatos relativos ao circuito de refrigeração.','Verificar fugas, resíduos, bomba de água, termóstato e estabilidade da temperatura.'),
('Transmissão / embraiagem',['gearbox','transmission','clutch','flywheel','dsg','s tronic','multitronic','embraiagem','volante bimassa'],'Há referências a transmissão, embraiagem ou volante bimassa nesta configuração.','Testar a frio/quente, verificar vibrações/patinação e confirmar manutenção da caixa.'),
('AdBlue / SCR / NOx',['adblue','scr','nox sensor','sensor nox'],'Existem referências ao sistema SCR/AdBlue ou sensores NOx.','Ler códigos de erro e confirmar funcionamento/campanhas do sistema de emissões.'),
('Eletrónica',['electrical fault','electrical problem','electronic fault','infotainment','falha eletrica'],'Foram encontrados relatos de falhas elétricas ou eletrónicas.','Testar equipamentos e fazer diagnóstico eletrónico completo.'),
('Bateria / carregamento',['battery degradation','battery health','onboard charger','charging fault','bms','bateria de tracao'],'Há referências à bateria de tração ou ao sistema de carregamento.','Confirmar SoH da bateria, erros BMS e testar carregamento AC/DC.')]
POS=[('Fiabilidade',['reliable','dependable','robust','reliability','fiavel'],'Há referências favoráveis à robustez/fiabilidade quando a manutenção é cumprida.'),('Eficiência',['fuel economy','economical','efficient','good mpg','consumos'],'Eficiência e consumos aparecem como pontos positivos desta configuração.'),('Conforto / refinamento',['comfortable','comfort','refined','smooth','confortavel'],'Conforto e refinamento são aspetos favoráveis mencionados para este modelo/configuração.'),('Desempenho / binário',['torque','strong performance','good performance','punchy','binario'],'Desempenho e entrega de binário são apontados como pontos favoráveis desta motorização.')]

def dynamic_research(model,engine,year,fuel):
    base=clean(model);core=clean(' '.join(x for x in [base,engine] if x));exact=clean(' '.join(x for x in [core,str(year or ''),fuel] if x))
    queries=[f'"{core}" common problems reliability oil pump injectors DPF EGR turbo',f'"{core}" known issues faults forum',f'"{base}" "{engine}" common problems',f'"{core}" review reliability fuel economy comfort performance']
    rows=[]
    with ThreadPoolExecutor(max_workers=4) as ex:
        futs=[ex.submit(search_web,q,10) for q in queries]
        for f in as_completed(futs):
            try:rows.extend(f.result())
            except:pass
    rows=dedup(rows,18)
    pages={}
    with ThreadPoolExecutor(max_workers=5) as ex:
        jobs={ex.submit(read_page,r['url']):r['url'] for r in rows[:6]}
        for f in as_completed(jobs):
            try:pages[jobs[f]]=f.result()
            except:pages[jobs[f]]=''
    mt=[t for t in re.split(r'\W+',alow(base)) if len(t)>=2];et=[t for t in re.split(r'\W+',alow(engine)) if len(t)>=2 and t not in ['cv','hp']]
    docs=[]
    for r in rows:
        blob=alow(' '.join([r.get('title',''),r.get('snippet',''),pages.get(r.get('url',''),'')]))
        mh=sum(1 for t in mt if t in blob);eh=sum(1 for t in et if t in blob)
        relevant=(mh>=max(1,min(2,len(mt))) and (not et or eh>=1)) or (et and eh>=max(2,min(3,len(et))))
        if relevant:docs.append((r,blob))
    issues=[];checks=[];ev=[];sources=[]
    for label,terms,text,check in CATS:
        matches=[];domains=set();hits=set()
        for r,blob in docs:
            local=[t for t in terms if alow(t) in blob]
            if local:matches.append(r);domains.add(urlparse(r.get('url','')).netloc.lower());hits.update(local)
        if matches:
            conf=min(95,42+18*min(2,len(domains))+7*min(3,len(hits)))
            if conf>=60:issues.append((conf,label,text,check,matches))
    issues.sort(key=lambda x:-x[0]);outissues=[]
    for conf,label,text,check,matches in issues[:4]:
        outissues.append(text);checks.append({'title':label,'detail':check});ev.append({'category':label,'confidence':conf,'matches':len(matches)})
        for r in matches[:2]:
            if r.get('url') and not any(s['url']==r['url'] for s in sources):sources.append({'title':clean(r.get('title','')),'url':r['url']})
    strengths=[]
    joined=' '.join(blob for _,blob in docs)
    for label,terms,text in POS:
        if any(alow(t) in joined for t in terms):strengths.append(text)
        if len(strengths)>=3:break
    if not outissues:outissues=['A pesquisa encontrou fontes, mas não evidência técnica suficientemente consistente para classificar um problema recorrente.' if rows else 'A pesquisa externa não devolveu resultados; tenta novamente dentro de instantes.']
    if not strengths:strengths=['Não foram encontrados pontos fortes técnicos com evidência pública suficiente; isto não significa que o modelo seja desfavorável.']
    if not checks:checks=[{'title':'Diagnóstico e VIN','detail':'Confirmar campanhas/recalls pelo VIN e fazer inspeção/diagnóstico independente antes da compra.'}]
    return {'strengths':strengths[:3],'issues':outissues[:4],'checks':checks[:4],'sources':sources[:8],'evidence':ev[:6],'research_score':max([x['confidence'] for x in ev],default=30),'engine_focus':engine,'research_available':bool(ev),'identity_used':exact,'search_results':len(rows),'relevant_sources':len(docs)}
