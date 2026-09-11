from flask import Flask, request, jsonify, Response
import requests, re, html as htmllib, unicodedata
from bs4 import BeautifulSoup
from urllib.parse import quote_plus, urljoin, urlparse, parse_qs, unquote
from datetime import datetime
from pathlib import Path
from concurrent.futures import ThreadPoolExecutor, as_completed

app = Flask(__name__, static_folder='.')
HEADERS={'User-Agent':'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 Chrome/124 Safari/537.36','Accept-Language':'pt-PT,pt;q=0.9,en;q=0.8'}

def clean(s): return re.sub(r'\s+',' ',htmllib.unescape(s or '')).strip()
def alow(s): return unicodedata.normalize('NFKD',s or '').encode('ascii','ignore').decode().lower()
def num(v):
    try:return int(re.sub(r'\D','',str(v or '')) or 0)
    except:return 0
def eur(n): return f'{n:,}'.replace(',','.')+' €' if n else ''
def kms(n): return f'{n:,}'.replace(',','.')+' km' if n else ''
def slug(s): return re.sub(r'[^a-z0-9]+','-',alow(s)).strip('-')
def valid_price(n): return 1000<=n<=1000000

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
    if 'hybrid' in x or 'hibrid' in x:return 'Híbrido'
    if 'eletric' in x or 'electric' in x:return 'Elétrico'
    if any(k in x for k in ['diesel','bluehdi','tdi','dci','cdti','crdi']):return 'Diesel'
    if any(k in x for k in ['gasolina','petrol','puretech','tsi','tfsi','ecoboost']):return 'Gasolina'
    return ''
def fuel_group(v):
    x=alow(v)
    if any(k in x for k in ['plug','phev','hybrid','hibrid']):return 'hybrid'
    if 'eletr' in x or 'electric' in x:return 'electric'
    if 'diesel' in x:return 'diesel'
    if 'gasolina' in x or 'petrol' in x:return 'gasoline'
    return ''
def fuel_term(v): return {'hybrid':'híbrido','electric':'elétrico','diesel':'diesel','gasoline':'gasolina'}.get(fuel_group(v),'')
def vin(t):
    for p in [r'\bVIN\b\s*[:\-]?\s*\n?\s*([A-HJ-NPR-Z0-9]{17})\b',r'\b(?:N[uú]mero\s+de\s+chassis|Chassis)\b\s*[:\-]?\s*\n?\s*([A-HJ-NPR-Z0-9]{17})\b']:
        m=re.search(p,t or '',re.I)
        if m and not m.group(1).isdigit():return m.group(1).upper()
    return ''
def engine_hint(t,url=''):
    x=clean(title_line(t)+' '+field(t,'Versão')+' '+field(t,'Motor')+' '+url)
    pats=[
        r'\b\d[.,]\d\s*TDI\s*\d{2,3}\s*(?:cv|hp)?',r'\b\d[.,]\d\s*TFSI\s*\d{2,3}\s*(?:cv|hp)?',
        r'\b\d[.,]\d\s*TSI\s*\d{2,3}\s*(?:cv|hp)?',r'\b\d[.,]\d\s*dCi\s*\d{2,3}\s*(?:cv|hp)?',
        r'\b\d[.,]\d\s*BlueHDi\s*\d{2,3}\s*(?:cv|hp)?',r'\b\d[.,]\d\s*PureTech\s*\d{2,3}\s*(?:cv|hp)?',
        r'\b\d{2}\s*TDI\b',r'\b\d{2}\s*TFSI\b',r'\b\d{2,3}\s*kWh\b',r'\bHybrid\s*\d{2,3}\b'
    ]
    for p in pats:
        m=re.search(p,x,re.I)
        if m:return clean(m.group(0)).replace(',','.')
    # BMW marketplace URLs often keep the exact derivative (216, 330e, ...)
    # even when the page's structured "Modelo" field only says "Série 2".
    # Preserve that useful engine/model identifier for the technical research.
    bm=re.search(r'(?:^|[/_-])bmw[-_ ]([1-8]\d{2})(?:[-_ ]|$)',url or '',re.I)
    if bm:
        suffix=''
        if re.search(r'(?:^|[-_])(?:ver[-_])?d(?:[-_]|$)',url or '',re.I):suffix='d'
        elif re.search(r'(?:^|[-_])(?:ver[-_])?e(?:[-_]|$)',url or '',re.I):suffix='e'
        elif re.search(r'(?:^|[-_])(?:ver[-_])?i(?:[-_]|$)',url or '',re.I):suffix='i'
        return bm.group(1)+suffix
    return ''

def enrich_title_from_url(title,url):
    """Restore model derivatives that marketplace structured data omits."""
    out=clean(title)
    if re.search(r'\bbmw\b',out,re.I):
        bm=re.search(r'(?:^|[/_-])bmw[-_ ]([1-8]\d{2})(?:[-_ ]|$)',url or '',re.I)
        if bm and not re.search(r'\b'+re.escape(bm.group(1))+r'[a-z]{0,2}\b',out,re.I):
            derivative=engine_hint('',url) or bm.group(1)
            series=re.search(r'\bS[eé]rie\s+([1-8])\b',out,re.I)
            if series:
                end=series.end()
                out=clean(out[:end]+' '+derivative+' '+out[end:])
            else:
                out=clean(out+' '+derivative)
            if derivative[-1:].lower() in {'d','e','i'}:
                out=re.sub(r'\b'+re.escape(derivative)+r'\s+'+re.escape(derivative[-1])+r'\b',derivative,out,flags=re.I)
    return out

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
        r=requests.get('https://html.duckduckgo.com/html/?q='+quote_plus(q),headers=HEADERS,timeout=(3,9));r.raise_for_status()
        s=BeautifulSoup(r.text,'html.parser');out=[]
        for x in s.select('.result'):
            a=x.select_one('.result__a');sn=x.select_one('.result__snippet')
            if a:out.append({'title':clean(a.get_text(' ',strip=True)),'snippet':clean(sn.get_text(' ',strip=True) if sn else ''),'url':resolve(a.get('href',''))})
            if len(out)>=n:break
        return out
    except:return []

# ---------- listing parsers ----------
def parse_pisca(t,url):
    raw=title_line(t);model=year=price=km=''
    m=re.search(r'^(.*?)\s*-\s*(?:Usado|Usada)\s*-\s*([0-9 .]+)\s*€\s*-.*?\s*-\s*(?:Manual|Autom[aá]tica)\s*-\s*([0-9 .]+)\s*Kms?\s*-\s*(20\d{2})\s*-\s*Pisca\s*Pisca',raw,re.I)
    if m:model=clean(m.group(1));price=eur(num(m.group(2)));km=kms(num(m.group(3)));year=m.group(4)
    else:
        mm=re.match(r'^(.*?)\s*-\s*(?:Usado|Usada)\b',raw,re.I);model=clean(mm.group(1)) if mm else raw
        ym=re.search(r'\s-\s(20\d{2})\s-\sPisca\s*Pisca',raw,re.I);pm=re.search(r'\s-\s([0-9 .]+)\s*€\s-',raw);kk=re.search(r'\s-\s([0-9 .]+)\s*Kms?\s*-',raw,re.I)
        year=ym.group(1) if ym else '';price=eur(num(pm.group(1))) if pm else '';km=kms(num(kk.group(1))) if kk else ''
    return {'title':model or 'Veículo','year':year,'price':price,'km':km,'fuel':fuel(url) or fuel(field(t,'Combustível') or t[:3500]),'vin':vin(t),'engine':engine_hint(t,url)}

def olx_model_from_title(raw):
    s=clean(raw);s=re.sub(r'\s*[•|–-]\s*OLX\.?pt.*$','',s,flags=re.I);s=re.sub(r'[“\"].*?[”\"]',' ',s);s=clean(s)
    stop=re.search(r'\s+(?:s[- ]?line|amg|m\s*pack|gt\s*line|r[- ]?line|fr|b7|b8|b9|\d[.,]\d\s*(?:tdi|tsi|tfsi|dci|hdi|puretech)|\d{2,3}\s*cv|look\b)',s,re.I)
    if stop:s=s[:stop.start()]
    parts=s.split();bodytypes=['sportback','avant','touring','allroad','cabrio','coupe','sedan','sw']
    base=' '.join(parts[:3]) if len(parts)>=3 and alow(parts[2]) in bodytypes else (' '.join(parts[:2]) if len(parts)>=2 else s)
    out=[]
    for p in base.split():
        lp=alow(p)
        if re.fullmatch(r'[aqsret]{1,2}\d',lp):p=p.upper()
        elif lp in bodytypes:p=p[:1].upper()+p[1:].lower()
        elif not out:p=p[:1].upper()+p[1:]
        out.append(p)
    return clean(' '.join(out))
def olx_fuel(raw,t):
    x=alow(raw+' '+field(t,'Combustível'))
    if any(k in x for k in ['tdi','diesel','dci','hdi','bluehdi']):return 'Diesel'
    if any(k in x for k in ['tfsi','tsi','gasolina','petrol','puretech']):return 'Gasolina'
    if any(k in x for k in ['plug-in','plug in','phev']):return 'Híbrido Plug-in'
    if any(k in x for k in ['hybrid','hibrid']):return 'Híbrido'
    if any(k in x for k in ['eletric','electric']):return 'Elétrico'
    return ''
def direct_olx_price(url):
    try:
        r=requests.get(url,headers=HEADERS,timeout=(3,8));r.raise_for_status();txt=r.text
        for p in [r'"price"\s*:\s*"?([0-9]{4,6})"?',r'"priceValue"\s*:\s*"?([0-9]{4,6})"?',r'"amount"\s*:\s*"?([0-9]{4,6})"?',r'([0-9]{1,3}(?:[ .][0-9]{3})+)\s*€']:
            for m in re.finditer(p,txt,re.I):
                n=num(m.group(1))
                if valid_price(n):return n
    except:pass
    return 0
def search_olx_price(raw,url):
    title=re.sub(r'\s*[•|–-]\s*OLX\.?pt.*$','',clean(raw),flags=re.I)
    for r in search(f'"{title}" site:olx.pt',8):
        blob=clean((r.get('title') or '')+' '+(r.get('snippet') or ''));m=re.search(r'\b([0-9]{1,3}(?:[ .][0-9]{3})+|[0-9]{4,6})\s*€',blob,re.I)
        if m and valid_price(num(m.group(1))):return num(m.group(1))
    return 0
def parse_olx(t,url):
    raw=title_line(t);model=olx_model_from_title(raw);h=t[:12000]
    ym=re.search(r'\bAno\s*[:\n ]+\s*(20[0-3]\d)\b',h,re.I) or re.search(r'\b(20[0-3]\d)\b',raw);price_n=0
    for blob in [raw,h,t]:
        for pat in [r'\b([0-9]{1,3}(?:[ .][0-9]{3})+|[0-9]{4,6})\s*€',r'\b([0-9]{1,3}(?:[ .][0-9]{3})+|[0-9]{4,6})\s*EUR\b']:
            m=re.search(pat,blob or '',re.I)
            if m and valid_price(num(m.group(1))):price_n=num(m.group(1));break
        if price_n:break
    if not price_n:price_n=direct_olx_price(url)
    if not price_n:price_n=search_olx_price(raw,url)
    kk=re.search(r'\b([0-9]{1,3}(?:[ .][0-9]{3})+|[0-9]{4,7})\s*km\b',h,re.I) or re.search(r'\b([0-9]{1,3}(?:[ .][0-9]{3})+|[0-9]{4,7})\s*km\b',t,re.I)
    return {'title':model or 'Veículo','year':ym.group(1) if ym else '','price':eur(price_n),'km':kms(num(kk.group(1))) if kk else '','fuel':olx_fuel(raw,t),'vin':vin(t),'engine':engine_hint(t,url)}

def parse_generic(t,url):
    b,m,v=field(t,'Marca'),field(t,'Modelo'),field(t,'Versão');raw=title_line(t)
    title=clean(' '.join(x for x in [b,m,v] if x)) or raw or 'Veículo'
    title=re.sub(r'\s*[|–-]\s*(Standvirtual|Pisca\s*Pisca).*$', '',title,flags=re.I)
    title=re.sub(r'\b(usado|usada|used)\b',' ',title,flags=re.I)
    title=re.sub(r'^\s*\d[\d .]*\s*(?:€|EUR)\s*[-–|]\s*','',title,flags=re.I);title=clean(title).strip(' -|')
    title=enrich_title_from_url(title,url);h=t[:9000]
    ym=re.search(r'\bAno\s*[:\n ]+\s*(20[0-3]\d)\b',h,re.I) or re.search(r'\b(20[0-3]\d)\b[^\n]{0,140}?\b(?:km|Autom[aá]tica|Manual)\b',h,re.I) or re.search(r'\b(?:Usado|Used)\b[^\n]{0,120}?\b(20[0-3]\d)\b',raw,re.I)
    pm=None
    for blob in [raw,h,t]:
        for pat in [r'\b([0-9]{1,3}(?:[ .][0-9]{3})+)\s*(?:€|EUR)',r'\b([0-9]{4,6})\s*(?:€|EUR)']:
            cand=re.search(pat,blob or '',re.I)
            if cand and valid_price(num(cand.group(1))):pm=cand;break
        if pm:break
    kk=re.search(r'\b([0-9]{1,3}(?:[ .][0-9]{3})+)\s*km\b',t,re.I) or re.search(r'\b([0-9]{4,7})\s*km\b',t,re.I)
    return {'title':title,'year':ym.group(1) if ym else '','price':eur(num(pm.group(1))) if pm else '','km':kms(num(kk.group(1))) if kk else '','fuel':fuel(url) or fuel(field(t,'Combustível') or h),'vin':vin(t),'engine':engine_hint(t,url)}
def parse_listing(t,u):
    host=urlparse(u).netloc.lower()
    if 'piscapisca.pt' in host:return parse_pisca(t,u)
    if 'olx.pt' in host:return parse_olx(t,u)
    return parse_generic(t,u)

def safe_listing_image(url,text,model=''):
    host=urlparse(url).netloc.lower()
    if 'olx.pt' in host:return ''
    tokens=[x for x in re.split(r'\W+',alow(model)) if len(x)>2];candidates=[]
    for alt,href in re.findall(r'!\[([^\]]*)\]\((https?://[^)\s]+)',text or '',re.I):
        blob=alow(alt+' '+href)
        if any(b in blob for b in ['logo','favicon','sprite','avatar','credibom','pisca-pisca','pisca pisca','facebook','instagram','dealer','stand logo','weather','cloud','sky']):continue
        matched=sum(1 for token in tokens if token in blob);sv=matched*3+(1 if any(x in blob for x in ['jpg','jpeg','webp','vehicle','carro','auto','image']) else 0);candidates.append((sv,matched,href))
    if candidates:
        candidates.sort(key=lambda x:-x[0]);best=candidates[0]
        if best[1]>=1 and best[0]>=4:return best[2]
    if 'piscapisca.pt' not in host:
        try:
            r=requests.get(url,headers=HEADERS,timeout=(3,8));r.raise_for_status();s=BeautifulSoup(r.text,'html.parser')
            for q in ['meta[property="og:image"]','meta[name="twitter:image"]']:
                tag=s.select_one(q)
                if tag and tag.get('content'):
                    cand=urljoin(url,tag['content']);blob=alow(cand)
                    if not any(b in blob for b in ['logo','favicon','social','brand','weather','cloud','sky']):return cand
        except:pass
    return ''

# ---------- score and comparables ----------
def score(year,km,vinv=''):
    y,k=num(year),num(km)
    if not y or not k:return 68 if len(vinv or '')==17 else 64
    age=max(0,datetime.now().year-y);annual=k/max(1,age or 1);a=max(35,min(98,98-age*4.7));q=max(35,min(98,98-(annual/1000)*2.15));p=min(12,(k/100000)*6)
    return max(35,min(95,round(a*.52+q*.43+(5 if len(vinv or '')==17 else 0)-p)))
def model_key(v):
    """Return a stable make/model key without collapsing distinct model lines."""
    value=clean(v);plain=alow(value)
    if plain.startswith('bmw '):
        derivative=re.search(r'\b([1-8]\d{2})[a-z]{0,2}\b',plain)
        if derivative:return 'BMW '+derivative.group(1)
        series=re.search(r'\bserie\s+([1-8])\b',plain)
        if series:return 'BMW Série '+series.group(1)
        named=re.search(r'\b(x[1-7]|i[3-8x][a-z0-9-]*|z4|m[2-8])\b',plain)
        if named:return 'BMW '+named.group(1).upper()
    # Most listings start with make + model. Keep a third token when the
    # second one is a family word (Série, Classe, Range, ...).
    p=value.split()
    if len(p)>=3 and alow(p[1]) in {'serie','classe','range','model'}:return ' '.join(p[:3])
    return ' '.join(p[:2]) if len(p)>=2 else value
def source(u):
    if 'piscapisca.pt' in u:return 'PiscaPisca'
    if 'standvirtual' in u:return 'Standvirtual'
    if 'olx.pt' in u:return 'OLX'
    if 'custojusto.pt' in u:return 'CustoJusto'
    return 'Marketplace'
def pisca_category_url(model):
    p=clean(model).split();return f'https://www.piscapisca.pt/carros/marca/{slug(p[0])}/{slug(p[1])}' if len(p)>=2 else ''
def parse_pisca_category(text,key,fg,current='',limit=12):
    out=[];pat=re.compile(r'\[([^\]\n]+?)\s+([0-9 .]{1,10})\s*km\s*[•·]\s*([^•·\]\n]+)\s*[•·]\s*([^•·\]\n]+)\s*[•·]\s*(20\d{2})[^\]]*\]\((https?://[^)]+)\)[\s\S]{0,110}?([0-9 .]{4,10})\s*€',re.I)
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
    ym=re.search(r'\b(20[0-3]\d)\b',blob);pm=re.search(r'\b([0-9]{1,3}(?:[ .][0-9]{3})+|[0-9]{4,6})\s*(?:€|EUR)',blob,re.I);kk=re.search(r'\b([0-9]{1,3}(?:[ .][0-9]{3})+|[0-9]{4,7})\s*km\b',blob,re.I)
    if not(ym and pm and kk):return None
    p,k=num(pm.group(1)),num(kk.group(1));y=ym.group(1)
    return {'title':key,'year':y,'km':kms(k),'price':eur(p),'fuel':fuel(blob),'score':score(y,k),'url':u,'source':source(u)} if valid_price(p) and 0<k<=1000000 else None
def discover(model,motor,current='',limit=4):
    key=model_key(model);fg=fuel_group(motor);ft=fuel_term(motor);out=[];cat=pisca_category_url(key)
    if cat:
        try:out.extend(parse_pisca_category(fetch_text(cat),key,fg,current,limit*3))
        except:pass
    queries=[f'site:piscapisca.pt/carros/usados "{key}" {ft}',f'site:standvirtual.com/carros/anuncio "{key}" {ft}',f'site:custojusto.pt "{key}" {ft}',f'site:olx.pt "{key}" {ft}',f'"{key}" {ft} usado Portugal'];results=[];urls=[]
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
    ded.sort(key=lambda x:(-x['score'],num(x['price'])));return ded[:limit]

# ---------- dynamic research engine ----------
ISSUES=[
 ('Distribuição',['timing belt','timing chain','wet belt','correia distribuicao','corrente distribuicao'],
  'Há referências recorrentes ao sistema de distribuição nesta motorização.','Confirmar intervalo, histórico de substituição e ruídos/sinais anormais.'),
 ('Lubrificação / bomba de óleo',['oil pump','low oil pressure','oil pressure','bomba de oleo','pressao de oleo','oil consumption','consumo de oleo'],
  'Foram encontrados relatos relacionados com lubrificação, pressão ou consumo de óleo.','Confirmar pressão de óleo quando aplicável, fugas/consumo e histórico de manutenção.'),
 ('Injeção',['injector failure','injector problem','injectors','injetores','injetor'],
  'Foram encontrados relatos ligados aos injetores ou ao sistema de injeção.','Fazer diagnóstico às correções de injeção e confirmar histórico de substituições/campanhas.'),
 ('DPF / EGR',['dpf problem','dpf failure','egr problem','egr failure','filtro particulas','valvula egr'],
  'Existem referências recorrentes a DPF/EGR para esta configuração.','Verificar carga/regenerações do DPF, erros EGR e tipo de utilização anterior.'),
 ('Turbo',['turbo failure','turbo problem','boost problem','turbo actuator','atuador turbo'],
  'Foram encontrados relatos associados ao turbo ou controlo de sobrealimentação.','Testar pressão/atuador sob carga e procurar erros, assobios ou perda de potência.'),
 ('Refrigeração',['water pump','thermostat housing','coolant leak','bomba de agua','termostato','fuga refrigerante'],
  'Há referências a falhas ou fugas no circuito de refrigeração.','Verificar nível, fugas/resíduos, bomba de água e termóstato.'),
 ('Transmissão / embraiagem',['gearbox problem','transmission problem','clutch problem','dsg problem','s tronic problem','caixa velocidades','embraiagem'],
  'Foram encontrados relatos ligados à transmissão ou embraiagem.','Testar a frio/quente e confirmar a manutenção da caixa quando aplicável.'),
 ('AdBlue / SCR / NOx',['adblue problem','scr problem','nox sensor','adblue failure','sensor nox'],
  'Existem referências ao sistema AdBlue/SCR ou sensores NOx.','Ler códigos de erro e confirmar funcionamento/campanhas do sistema de emissões.'),
 ('Eletrónica',['electrical problems','electronic problems','infotainment problem','electrical fault','falhas eletricas','problemas eletricos'],
  'Foram encontrados relatos de falhas elétricas/eletrónicas nesta configuração.','Testar todos os módulos/equipamentos e fazer diagnóstico eletrónico completo.'),
 ('Bateria / carregamento',['battery degradation','battery problem','onboard charger','charging fault','charging problem','bateria tracao','carregador bordo'],
  'Há referências relacionadas com bateria ou sistema de carregamento.','Confirmar estado de saúde da bateria, erros BMS e teste de carregamento AC/DC.')
]
STRENGTHS=[
 ('Fiabilidade',['reliable','reliability good','dependable','robust','fiavel','fiabilidade'],
  'A fiabilidade aparece de forma favorável em fontes relativas a esta configuração, desde que a manutenção seja cumprida.'),
 ('Eficiência',['fuel economy','economical','efficient','good mpg','consumos','economico'],
  'Eficiência e consumos surgem como pontos positivos desta configuração.'),
 ('Conforto / refinamento',['comfortable','comfort','refined','smooth','confortavel','refinamento'],
  'Conforto e refinamento são aspetos positivos referidos para este modelo/configuração.'),
 ('Desempenho / binário',['strong performance','good performance','torque','punchy','performance','binario'],
  'Desempenho e entrega de binário são apontados como pontos favoráveis desta motorização.')
]

def research_identity(model,engine,year,fuelv):
    base=model_key(model)
    exact=clean(' '.join(x for x in [base,engine,str(year or ''),fuelv] if x))
    relaxed=clean(' '.join(x for x in [base,engine] if x))
    return base,exact,relaxed

def category_evidence(identity, relaxed, label, terms):
    query_terms=' OR '.join(f'"{t}"' for t in terms[:4])
    rows=search(f'"{relaxed}" ({query_terms})',10)
    if len(rows)<2:
        rows+=search(f'"{identity}" {label} problems common faults reliability',8)
    key_tokens=[x for x in re.split(r'\W+',alow(relaxed)) if len(x)>1]
    good=[];term_hits=[]
    for r in rows:
        blob=alow((r.get('title') or '')+' '+(r.get('snippet') or ''))
        specificity=sum(1 for t in key_tokens if t in blob)
        hits=[t for t in terms if alow(t) in blob]
        if hits and specificity>=max(1,min(2,len(key_tokens))):
            good.append(r);term_hits.extend(hits)
    domains={urlparse(r.get('url','')).netloc.lower() for r in good if r.get('url')}
    confidence=min(100,35*len(domains)+12*min(3,len(set(term_hits))))
    return good,confidence

def dynamic_research(model,engine,year,fuelv):
    base,identity,relaxed=research_identity(model,engine,year,fuelv)
    issue_hits=[];strength_hits=[]
    def run_issue(item):
        label,terms,text,check=item
        rows,conf=category_evidence(identity,relaxed,label,terms)
        return label,text,check,rows,conf
    with ThreadPoolExecutor(max_workers=6) as ex:
        futs=[ex.submit(run_issue,i) for i in ISSUES]
        for f in as_completed(futs):
            label,text,check,rows,conf=f.result()
            if rows and conf>=45:issue_hits.append((conf,label,text,check,rows))
    for label,terms,text in STRENGTHS:
        rows,conf=category_evidence(identity,relaxed,label,terms)
        if rows and conf>=45:strength_hits.append((conf,label,text,rows))
    issue_hits.sort(reverse=True,key=lambda x:x[0]);strength_hits.sort(reverse=True,key=lambda x:x[0])
    issues=[];checks=[];sources=[];evidence=[]
    for conf,label,text,check,rows in issue_hits[:4]:
        issues.append(text);checks.append({'title':label,'detail':check});evidence.append({'category':label,'confidence':conf,'matches':len(rows)})
        for r in rows[:2]:
            u=r.get('url','');tt=clean(r.get('title',''))
            if u and tt and not any(s.get('url')==u for s in sources):sources.append({'title':tt,'url':u})
    strengths=[]
    for conf,label,text,rows in strength_hits[:3]:
        strengths.append(text)
        for r in rows[:1]:
            u=r.get('url','');tt=clean(r.get('title',''))
            if u and tt and not any(s.get('url')==u for s in sources):sources.append({'title':tt,'url':u})
    if not issues:
        broad=[]
        for q in [f'"{relaxed}" common problems',f'"{relaxed}" reliability issues',f'"{base}" "{engine}" forum problems']:
            broad.extend(search(q,10))
        low=' '.join(alow((r.get('title') or '')+' '+(r.get('snippet') or '')) for r in broad)
        for label,terms,text,check in ISSUES:
            hit=sum(1 for t in terms if alow(t) in low)
            if hit>=1:issues.append(text);checks.append({'title':label,'detail':check})
            if len(issues)>=3:break
        for r in broad[:5]:
            u=r.get('url','');tt=clean(r.get('title',''))
            if u and tt and not any(s.get('url')==u for s in sources):sources.append({'title':tt,'url':u})
    if not strengths:
        strengths=['Não foram encontrados pontos fortes técnicos com evidência pública suficiente; isto não é uma avaliação negativa, apenas ausência de evidência consistente.']
    if not issues:
        issues=['Não foram encontrados problemas recorrentes com evidência pública suficiente para esta combinação exata de modelo e motor.']
    if not checks:
        checks=[{'title':'Diagnóstico e VIN','detail':'Confirmar campanhas/recalls pelo VIN e fazer diagnóstico independente antes da compra.'}]
    research_score=max([e['confidence'] for e in evidence],default=35)
    return {'strengths':strengths[:3],'issues':issues[:4],'checks':checks[:4],'sources':sources[:8],
            'evidence':evidence[:6],'research_score':research_score,'engine_focus':engine,
            'research_available':bool(issue_hits or strength_hits),'identity_used':identity}

@app.route('/')
def home():
    page=Path(__file__).with_name('index.html').read_text(encoding='utf-8')
    frontend='<script src="/debe_frontend_v3.js"></script>'
    if frontend not in page:page=page.replace('</body>',frontend+'</body>')
    return Response(page,mimetype='text/html')
@app.route('/debe_frontend_v3.js')
def frontend_v3():return Response(Path(__file__).with_name('debe_frontend_v3.js').read_text(encoding='utf-8'),mimetype='application/javascript')
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
    return jsonify(ok=True,**dynamic_research(m,e,y,f))
if __name__=='__main__':app.run(host='0.0.0.0',port=5050)
