from flask import Flask, request, jsonify, Response
import requests, re, html as htmllib, unicodedata
from bs4 import BeautifulSoup
from urllib.parse import quote_plus, urljoin, urlparse, parse_qs, unquote
from datetime import datetime
from concurrent.futures import ThreadPoolExecutor, as_completed

app = Flask(__name__, static_folder='.')
HEADERS = {'User-Agent':'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 Chrome/124 Safari/537.36','Accept-Language':'pt-PT,pt;q=0.9,en;q=0.8'}

def clean(s): return re.sub(r'\s+',' ',htmllib.unescape(s or '')).strip()
def alow(s): return unicodedata.normalize('NFKD',s or '').encode('ascii','ignore').decode().lower()
def num(v):
    try:return int(re.sub(r'\D','',str(v or '')) or 0)
    except:return 0

def eur(n): return f'{n:,}'.replace(',','.')+' €' if n else ''
def kms(n): return f'{n:,}'.replace(',','.')+' km' if n else ''
def slug(s): return re.sub(r'[^a-z0-9]+','-',alow(s)).strip('-')

def fetch_text(url):
    r=requests.get('https://r.jina.ai/'+url,headers=HEADERS,timeout=(4,18));r.raise_for_status();return r.text

def title_line(t):
    m=re.search(r'^Title:\s*(.+)$',t or '',re.I|re.M);return clean(m.group(1)) if m else ''

def field(t,label):
    m=re.search(r'(?:^|\n)'+re.escape(label)+r'\s*\n+\s*([^\n]+)',t or '',re.I)
    return clean(re.sub(r'^#+\s*','',m.group(1))) if m else ''

def fuel(t):
    x=alow(t)
    if 'plug-in' in x or 'plug in' in x or 'phev' in x:return 'Híbrido Plug-in'
    if any(k in x for k in ['diesel','bluehdi','tdi','dci']):return 'Diesel'
    if any(k in x for k in ['gasolina','petrol','puretech','tsi','tfsi']):return 'Gasolina'
    if 'hybrid' in x or 'hibrid' in x:return 'Híbrido'
    if 'eletric' in x or 'electric' in x:return 'Elétrico'
    return ''

def fuel_from_primary(primary, fallback=''):
    x=alow(primary)
    if 'plug-in' in x or 'plug in' in x or 'phev' in x:return 'Híbrido Plug-in'
    if any(k in x for k in ['tdi','diesel','bluehdi','dci','hdi']):return 'Diesel'
    if any(k in x for k in ['tfsi','tsi','gasolina','petrol','puretech']):return 'Gasolina'
    if any(k in x for k in ['e-208','electric','eletrico','elétrico','kwh']):return 'Elétrico'
    if 'hybrid' in x or 'hibrid' in x:return 'Híbrido'
    return fuel(fallback)

def fuel_group(v):
    x=alow(v)
    if any(k in x for k in ['plug','phev','hybrid','hibrid']):return 'hybrid'
    if 'eletr' in x or 'electric' in x:return 'electric'
    if 'diesel' in x:return 'diesel'
    if 'gasolina' in x or 'petrol' in x:return 'gasoline'
    return ''

def fuel_term(v):return {'hybrid':'híbrido','electric':'elétrico','diesel':'diesel','gasoline':'gasolina'}.get(fuel_group(v),'')

def vin(t):
    for p in [r'\bVIN\b\s*[:\-]?\s*\n?\s*([A-HJ-NPR-Z0-9]{17})\b',r'\b(?:N[uú]mero\s+de\s+chassis|Chassis)\b\s*[:\-]?\s*\n?\s*([A-HJ-NPR-Z0-9]{17})\b']:
        m=re.search(p,t or '',re.I)
        if m and not m.group(1).isdigit():return m.group(1).upper()
    return ''

def engine_hint(t,url=''):
    x=clean(title_line(t)+' '+field(t,'Versão')+' '+field(t,'Motor')+' '+url)
    pats=[r'\b\d[.,]\d\s*TDI\s*\d{2,3}\s*(?:cv|hp)?',r'\b\d[.,]\d\s*TFSI\s*\d{2,3}\s*(?:cv|hp)?',r'\b50\s*TDI\b',r'\b45\s*TDI\b',r'\b40\s*TDI\b',r'\b55\s*TFSI\b',r'\b50\s*kWh\b',r'\b51\s*kWh\b',r'\b1[.,]2\s*(?:PureTech)?(?:\s*\d{2,3}\s*(?:cv|hp))?',r'\bPureTech\s*\d{2,3}\b',r'\b1[.,]5\s*BlueHDi(?:\s*\d{2,3}\s*(?:cv|hp))?',r'\bHybrid\s*\d{2,3}\b']
    for p in pats:
        m=re.search(p,x,re.I)
        if m:
            z=clean(m.group(0)).replace(',','.')
            z=re.sub(r'(?i)tdi','TDI',z);z=re.sub(r'(?i)tfsi','TFSI',z);z=re.sub(r'(?i)cv','cv',z)
            return z
    return ''

def valid_price(n):return 1000<=n<=1000000

def parse_pisca(t,url):
    raw=title_line(t);model=year=price=km=''
    m=re.search(r'^(.*?)\s*-\s*(?:Usado|Usada)\s*-\s*([0-9 .]+)\s*€\s*-.*?\s*-\s*(?:Manual|Autom[aá]tica)\s*-\s*([0-9 .]+)\s*Kms?\s*-\s*(20\d{2})\s*-\s*Pisca\s*Pisca',raw,re.I)
    if m:model=clean(m.group(1));price=eur(num(m.group(2)));km=kms(num(m.group(3)));year=m.group(4)
    else:
        mm=re.match(r'^(.*?)\s*-\s*(?:Usado|Usada)\b',raw,re.I);model=clean(mm.group(1)) if mm else raw
        ym=re.search(r'\s-\s(20\d{2})\s-\sPisca\s*Pisca',raw,re.I);pm=re.search(r'\s-\s([0-9 .]+)\s*€\s-',raw);kk=re.search(r'\s-\s([0-9 .]+)\s*Kms?\s*-',raw,re.I)
        year=ym.group(1) if ym else '';price=eur(num(pm.group(1))) if pm else '';km=kms(num(kk.group(1))) if kk else ''
    return {'title':model or 'Veículo','year':year,'price':price,'km':km,'fuel':fuel_from_primary(url+' '+raw,field(t,'Combustível') or t[:3500]),'vin':vin(t),'engine':engine_hint(t,url)}

def pretty_model_name(s):
    parts=clean(s).split();out=[]
    for p in parts:
        low=p.lower()
        if re.fullmatch(r'[a-z]\d',low) or re.fullmatch(r'[a-z]\d{1,2}',low):out.append(low.upper())
        elif low in ['suv','gt','gti','rs','rs3','amg']:out.append(low.upper())
        elif low in ['sportback','allroad','avant','touring','cabrio','coupe','sedan','sw']:out.append(low.capitalize())
        else:out.append(p[:1].upper()+p[1:] if p else p)
    return ' '.join(out)

def olx_model_from_title(raw):
    s=clean(raw)
    s=re.sub(r'\s*[•|–-]\s*OLX\.?pt.*$','',s,flags=re.I)
    s=re.sub(r'\s*[•|–-]\s*OLX.*$','',s,flags=re.I)
    s=re.sub(r'[“\"].*?[”\"]',' ',s)
    s=clean(s)
    stop=re.search(r'\s+(?:s[- ]?line|amg|m\s*pack|gt\s*line|r[- ]?line|fr|\d[.,]\d\s*(?:tdi|tsi|tfsi|dci|hdi|puretech)|\d{2,3}\s*cv|look\b)',s,re.I)
    if stop:s=s[:stop.start()]
    parts=s.split()
    if len(parts)>=3 and alow(parts[2]) in ['sportback','avant','touring','allroad','cabrio','coupe','sedan','sw']:
        return pretty_model_name(' '.join(parts[:3]))
    return pretty_model_name(' '.join(parts[:2])) if len(parts)>=2 else pretty_model_name(s)

def parse_olx(t,url):
    raw=title_line(t);model=olx_model_from_title(raw);h=t[:10000]
    ym=re.search(r'\bAno\s*[:\n ]+\s*(20[0-3]\d)\b',h,re.I) or re.search(r'\b(20[0-3]\d)\b',raw)
    pm=None
    for blob in [raw,h,t]:
        cand=re.search(r'\b([0-9]{1,3}(?:[ .][0-9]{3})+|[0-9]{4,6})\s*(?:€|EUR)\b',blob or '',re.I)
        if cand and valid_price(num(cand.group(1))):pm=cand;break
    kk=re.search(r'\b([0-9]{1,3}(?:[ .][0-9]{3})+|[0-9]{4,7})\s*km\b',h,re.I) or re.search(r'\b([0-9]{1,3}(?:[ .][0-9]{3})+|[0-9]{4,7})\s*km\b',t,re.I)
    listed_fuel=field(t,'Combustível') or field(t,'Combustivel')
    motor=engine_hint(t,url)
    detected=fuel_from_primary(raw+' '+motor,listed_fuel)
    return {'title':model or 'Veículo','year':ym.group(1) if ym else '','price':eur(num(pm.group(1))) if pm else '','km':kms(num(kk.group(1))) if kk else '','fuel':detected,'vin':vin(t),'engine':motor}

def parse_generic(t,url):
    b,m,v=field(t,'Marca'),field(t,'Modelo'),field(t,'Versão');raw=title_line(t)
    title=clean(' '.join(x for x in [b,m,v] if x)) or raw or 'Veículo'
    title=re.sub(r'\s*[|–-]\s*(Standvirtual|Pisca\s*Pisca).*$', '',title,flags=re.I)
    title=re.sub(r'\b(usado|usada|used)\b',' ',title,flags=re.I)
    title=re.sub(r'^\s*\d[\d .]*\s*(?:€|EUR)\s*[-–|]\s*','',title,flags=re.I)
    title=clean(title).strip(' -|');h=t[:9000]
    ym=re.search(r'\bAno\s*[:\n ]+\s*(20[0-3]\d)\b',h,re.I) or re.search(r'\b(20[0-3]\d)\b[^\n]{0,140}?\b(?:km|Autom[aá]tica|Manual)\b',h,re.I) or re.search(r'\b(?:Usado|Used)\b[^\n]{0,120}?\b(20[0-3]\d)\b',raw,re.I)
    price_patterns=[r'\b([0-9]{1,3}(?:[ .][0-9]{3})+)\s*(?:€|EUR)\b',r'\b([0-9]{4,6})\s*(?:€|EUR)\b']
    pm=None
    for blob in [raw,h,t]:
        for pat in price_patterns:
            cand=re.search(pat,blob or '',re.I)
            if cand and valid_price(num(cand.group(1))):pm=cand;break
        if pm:break
    kk=re.search(r'\b([0-9]{1,3}(?:[ .][0-9]{3})+)\s*km\b',t,re.I) or re.search(r'\b([0-9]{4,7})\s*km\b',t,re.I)
    return {'title':title,'year':ym.group(1) if ym else '','price':eur(num(pm.group(1))) if pm else '','km':kms(num(kk.group(1))) if kk else '','fuel':fuel_from_primary(raw+' '+field(t,'Combustível'),h),'vin':vin(t),'engine':engine_hint(t,url)}

def parse_listing(t,u):
    host=urlparse(u).netloc.lower()
    if 'piscapisca.pt' in host:return parse_pisca(t,u)
    if 'olx.pt' in host:return parse_olx(t,u)
    return parse_generic(t,u)

def safe_listing_image(url,text,model=''):
    candidates=[]
    for alt,href in re.findall(r'!\[([^\]]*)\]\((https?://[^)\s]+)',text or '',re.I):
        blob=alow(alt+' '+href)
        if any(b in blob for b in ['logo','favicon','sprite','avatar','credibom','pisca-pisca','pisca pisca','facebook','instagram','dealer','stand logo']):continue
        sv=0
        for token in [x for x in re.split(r'\W+',alow(model)) if len(x)>2]:
            if token in blob:sv+=3
        if any(x in blob for x in ['jpg','jpeg','webp','vehicle','carro','auto','image']):sv+=1
        candidates.append((sv,href))
    if candidates:
        candidates.sort(key=lambda x:-x[0])
        if candidates[0][0]>=2:return candidates[0][1]
    if 'piscapisca.pt' not in url.lower():
        try:
            r=requests.get(url,headers=HEADERS,timeout=(3,8));r.raise_for_status();s=BeautifulSoup(r.text,'html.parser')
            for q in ['meta[property="og:image"]','meta[name="twitter:image"]']:
                tag=s.select_one(q)
                if tag and tag.get('content'):
                    cand=urljoin(url,tag['content']);blob=alow(cand)
                    if not any(b in blob for b in ['logo','favicon','social','brand']):return cand
        except:pass
    return ''

def resolve(h):
    if not h:return ''
    if h.startswith('//'):h='https:'+h
    try:
        q=parse_qs(urlparse(h).query)
        if q.get('uddg'):return unquote(q['uddg'][0])
    except:pass
    return h

def search(q,n=16):
    try:
        r=requests.get('https://html.duckduckgo.com/html/?q='+quote_plus(q),headers=HEADERS,timeout=(3,9));r.raise_for_status();s=BeautifulSoup(r.text,'html.parser');out=[]
        for x in s.select('.result'):
            a=x.select_one('.result__a');sn=x.select_one('.result__snippet')
            if a:out.append({'title':clean(a.get_text(' ',strip=True)),'snippet':clean(sn.get_text(' ',strip=True) if sn else ''),'url':resolve(a.get('href',''))})
            if len(out)>=n:break
        return out
    except:return []

def score(year,km,vinv=''):
    y,k=num(year),num(km)
    if not y or not k:return 68 if len(vinv or '')==17 else 64
    age=max(0,datetime.now().year-y);annual=k/max(1,age or 1);a=max(35,min(98,98-age*4.7));q=max(35,min(98,98-(annual/1000)*2.15));p=min(12,(k/100000)*6)
    return max(35,min(95,round(a*.52+q*.43+(5 if len(vinv or '')==17 else 0)-p)))

def model_key(v):
    p=clean(v).split();return ' '.join(p[:2]) if len(p)>=2 else clean(v)

def source(u):
    if 'piscapisca.pt' in u:return 'PiscaPisca'
    if 'standvirtual' in u:return 'Standvirtual'
    if 'olx.pt' in u:return 'OLX'
    if 'custojusto.pt' in u:return 'CustoJusto'
    return 'Marketplace'

def pisca_category_url(model):
    p=clean(model).split();return f'https://www.piscapisca.pt/carros/marca/{slug(p[0])}/{slug(p[1])}' if len(p)>=2 else ''

def parse_pisca_category(text,key,fg,current='',limit=12):
    out=[]
    pat=re.compile(r'\[([^\]\n]+?)\s+([0-9 .]{1,10})\s*km\s*[•·]\s*([^•·\]\n]+)\s*[•·]\s*([^•·\]\n]+)\s*[•·]\s*(20\d{2})[^\]]*\]\((https?://[^)]+)\)[\s\S]{0,110}?([0-9 .]{4,10})\s*€',re.I)
    for m in pat.finditer(text or ''):
        title=clean(m.group(1));kmv=num(m.group(2));fuelv=clean(m.group(4));year=m.group(5);u=clean(m.group(6));price=num(m.group(7))
        if alow(model_key(title))!=alow(key):continue
        g=fuel_group(fuelv)
        if fg and g and g!=fg:continue
        if current and u.rstrip('/')==current.rstrip('/'):continue
        if not(0<kmv<=1000000 and valid_price(price)):continue
        out.append({'title':title,'year':year,'km':kms(kmv),'price':eur(price),'fuel':fuelv,'score':score(year,kmv),'url':u,'source':'PiscaPisca'})
        if len(out)>=limit:break
    return out

def from_url(url,key,fg,current):
    if not url or url.rstrip('/')==(current or '').rstrip('/'):return None
    try:
        d=parse_listing(fetch_text(url),url)
        if alow(model_key(d['title']))!=alow(key):return None
        g=fuel_group(d['fuel'])
        if fg and g and g!=fg:return None
        if not d['year'] or not d['km'] or not d['price']:return None
        return {'title':d['title'],'year':d['year'],'km':d['km'],'price':d['price'],'fuel':d['fuel'],'score':score(d['year'],d['km'],d['vin']),'url':url,'source':source(url)}
    except:return None

def from_snippet(r,key,fg,current):
    u=r.get('url','');blob=clean((r.get('title') or '')+' '+(r.get('snippet') or ''))
    if not u or u.rstrip('/')==(current or '').rstrip('/') or alow(key) not in alow(blob):return None
    g=fuel_group(fuel(blob) or fuel(u))
    if fg and g and g!=fg:return None
    ym=re.search(r'\b(20[0-3]\d)\b',blob);pm=re.search(r'\b([0-9]{1,3}(?:[ .][0-9]{3})+|[0-9]{4,6})\s*(?:€|EUR)\b',blob,re.I);kk=re.search(r'\b([0-9]{1,3}(?:[ .][0-9]{3})+|[0-9]{4,7})\s*km\b',blob,re.I)
    if not(ym and pm and kk):return None
    p,k=num(pm.group(1)),num(kk.group(1));y=ym.group(1)
    return {'title':key,'year':y,'km':kms(k),'price':eur(p),'fuel':fuel(blob),'score':score(y,k),'url':u,'source':source(u)} if valid_price(p) and 0<k<=1000000 else None

def discover(model,motor,current='',limit=4):
    key=model_key(model);fg=fuel_group(motor);ft=fuel_term(motor);out=[]
    cat=pisca_category_url(key)
    if cat:
        try:out.extend(parse_pisca_category(fetch_text(cat),key,fg,current,limit*3))
        except:pass
    queries=[f'site:piscapisca.pt/carros/usados "{key}" {ft}',f'site:standvirtual.com/carros/anuncio "{key}" {ft}',f'site:custojusto.pt "{key}" {ft}',f'site:olx.pt "{key}" {ft}',f'"{key}" {ft} usado Portugal']
    results=[];urls=[]
    for q in queries:
        for r in search(q,14):
            results.append(r);u=r.get('url','')
            if u.startswith('http') and any(x in u for x in ['piscapisca.pt/carros/usados/','standvirtual.com/carros/anuncio','olx.pt','custojusto.pt']) and u not in urls:urls.append(u)
    with ThreadPoolExecutor(max_workers=5) as ex:
        for f in as_completed([ex.submit(from_url,u,key,fg,current) for u in urls[:18]]):
            it=f.result()
            if it:out.append(it)
    for r in results:
        it=from_snippet(r,key,fg,current)
        if it:out.append(it)
    ded=[];seen=set()
    for x in out:
        sig=(num(x['year']),num(x['km']),num(x['price']))
        if sig in seen:continue
        seen.add(sig);ded.append(x)
    ded.sort(key=lambda x:(-x['score'],num(x['price'])))
    return ded[:limit]

def known_profile(model,engine,year,fuelv):
    x=alow(model+' '+engine+' '+fuelv);fg=fuel_group(fuelv)
    if 'peugeot 2008' in x and fg=='gasoline':
        return {'strengths':['2008 II: conforto, posição de condução elevada e boa eficiência são aspetos geralmente valorizados.','Num exemplar recente, o risco de desgaste acumulado é menor; histórico de revisões continua decisivo.','Com quilometragem moderada, o foco deve estar na manutenção correta do 1.2 PureTech.'],'issues':['1.2 PureTech: confirmar variante do sistema de distribuição; séries anteriores ficaram associadas à degradação da correia banhada em óleo.','Verificar consumo de óleo e histórico de lubrificação, um ponto reportado em determinadas séries PureTech.','Confirmar pelo VIN todas as campanhas técnicas/recalls aplicáveis.'],'checks':[{'title':'Distribuição','detail':'Confirmar solução instalada e manutenção prevista.'},{'title':'Óleo e lubrificação','detail':'Verificar faturas, especificação de óleo e consumo anormal.'},{'title':'Campanhas técnicas','detail':'Confirmar na Peugeot pelo VIN.'}],'sources':['Peugeot/Stellantis — campanhas por VIN','Imprensa automóvel especializada — histórico PureTech','Bases de recalls e feedback de proprietários'],'research_score':64,'engine_focus':engine or '1.2 PureTech'}
    if ('peugeot e-208' in x or 'peugeot e208' in x) and fg=='electric':
        return {'strengths':['Condução silenciosa, resposta imediata e facilidade de utilização urbana são pontos fortes frequentes do e-208.','A plataforma elétrica Stellantis tem ampla rede de assistência e conhecimento técnico.','Unidades mais recentes beneficiam de atualizações face às primeiras séries.'],'issues':['Validar eletrónica/software: existem relatos de avisos elétricos e campanhas ligadas à gestão da bateria/propulsão.','Em algumas séries foram reportados problemas de carregamento/carregador de bordo; testar AC e DC.','Confirmar saúde da bateria de tração e bateria de 12 V com diagnóstico.'],'checks':[{'title':'Carregamento AC/DC','detail':'Testar carga sem erros.'},{'title':'Bateria e diagnóstico','detail':'Pedir estado da bateria e leitura de erros.'},{'title':'Recalls e software','detail':'Confirmar campanhas pelo VIN.'}],'sources':['What Car? — e-208 reliability','Stellantis/Peugeot — campanhas técnicas','Bases oficiais de recalls'],'research_score':72,'engine_focus':engine or '50 kWh elétrico'}
    return None

def evidence_profile(model,engine,year,fuelv):
    q=' '.join(x for x in [model,engine,fuelv] if x);rows=[]
    for qq in [f'"{q}" common problems recall reliability',f'"{q}" owner problems review',f'"{q}" problems engine battery gearbox']:
        rows.extend(search(qq,8))
    blobs=[clean((r.get('title') or '')+'. '+(r.get('snippet') or '')) for r in rows];low=' '.join(alow(b) for b in blobs)
    issues=[];strengths=[];checks=[]
    def add(cond,text,title,detail):
        if cond and text not in issues:issues.append(text);checks.append({'title':title,'detail':detail})
    add(any(k in low for k in ['timing belt','wet belt','correia','timing chain']),'Foram encontrados relatos sobre o sistema de distribuição nesta motorização.','Distribuição','Confirmar tipo, manutenção e campanhas pelo VIN.')
    add(any(k in low for k in ['oil consumption','consumo de oleo','low oil pressure']),'Existem referências a consumo/lubrificação nesta motorização.','Lubrificação','Rever faturas, óleo e sinais de consumo anormal.')
    add(any(k in low for k in ['onboard charger','charging fault','carregador']),'Foram encontrados relatos ligados ao carregamento/carregador de bordo.','Carregamento','Testar AC/DC e diagnóstico.')
    add(any(k in low for k in ['dpf','egr']),'Há referências a DPF/EGR nesta motorização.','DPF / EGR','Verificar regenerações, avisos e histórico.')
    add(any(k in low for k in ['gearbox','transmission','clutch']),'Foram encontrados relatos ligados à transmissão/embraiagem.','Transmissão','Testar a frio e quente.')
    if any(k in low for k in ['reliable','generally reliable']):strengths.append('As fontes encontradas descrevem esta versão como globalmente fiável, com pontos específicos a validar.')
    if any(k in low for k in ['efficient','efficiency','economical']):strengths.append('Eficiência aparece como um dos aspetos positivos desta configuração.')
    if any(k in low for k in ['comfort','comfortable','refined','smooth']):strengths.append('Conforto e suavidade estão entre os aspetos positivos mais referidos.')
    if not issues:issues=['Não foi encontrada evidência pública suficientemente consistente para listar um problema recorrente específico desta motorização.']
    if not strengths:strengths=['Não foi encontrada evidência pública suficientemente consistente para atribuir um ponto forte técnico específico desta motorização.']
    src=[]
    for r in rows:
        tt=clean(r.get('title',''))
        if tt and tt not in src:src.append(tt)
        if len(src)>=5:break
    return {'strengths':strengths[:3],'issues':issues[:3],'checks':checks[:3] or [{'title':'VIN e campanhas','detail':'Confirmar recalls/campanhas e fazer diagnóstico.'}],'sources':src,'research_score':62 if rows else None,'engine_focus':engine,'research_available':bool(rows)}

@app.route('/')
def home():return Response(open('index.html',encoding='utf-8').read(),mimetype='text/html')

@app.route('/api/listing')
def listing():
    u=request.args.get('url','').strip()
    if not u.startswith('http'):return jsonify(ok=False,error='URL inválido'),400
    try:
        t=fetch_text(u);d=parse_listing(t,u);d['image']=safe_listing_image(u,t,d.get('title',''));return jsonify(ok=True,**d)
    except Exception as e:return jsonify(ok=False,error=str(e)),500

@app.route('/api/comparables')
def comparables():
    m=clean(request.args.get('model',''));f=clean(request.args.get('fuel',''));u=clean(request.args.get('url',''))
    if len(m)<3:return jsonify(ok=False,error='Modelo inválido'),400
    deals=discover(m,f,u);return jsonify(ok=True,match=model_key(m),fuel_group=fuel_group(f),deals=deals,count=len(deals))

@app.route('/api/research')
def research():
    m=clean(request.args.get('model',''));e=clean(request.args.get('engine',''));y=clean(request.args.get('year',''));f=clean(request.args.get('fuel',''))
    if len(m)<3:return jsonify(ok=False,error='Modelo inválido'),400
    kp=known_profile(m,e,y,f)
    if kp:return jsonify(ok=True,research_available=True,**kp)
    return jsonify(ok=True,**evidence_profile(m,e,y,f))

if __name__=='__main__':app.run(host='0.0.0.0',port=5050)
