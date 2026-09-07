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
    try: return int(re.sub(r'\D','',str(v or '')) or 0)
    except: return 0
def eur(n): return f'{n:,}'.replace(',','.')+' €' if n else ''
def kms(n): return f'{n:,}'.replace(',','.')+' km' if n else ''

def fetch_text(url):
    r=requests.get('https://r.jina.ai/'+url,headers=HEADERS,timeout=(4,16)); r.raise_for_status(); return r.text

def image_from(url,text=''):
    try:
        r=requests.get(url,headers=HEADERS,timeout=(3,8)); r.raise_for_status(); s=BeautifulSoup(r.text,'html.parser')
        for q in ['meta[property="og:image"]','meta[name="twitter:image"]']:
            t=s.select_one(q)
            if t and t.get('content'): return urljoin(url,t['content'])
    except: pass
    m=re.search(r'!\[[^\]]*\]\((https?://[^)\s]+)',text or '',re.I)
    return m.group(1) if m else ''

def title_line(text):
    m=re.search(r'^Title:\s*(.+)$',text or '',re.I|re.M); return clean(m.group(1)) if m else ''
def field(text,label):
    m=re.search(r'(?:^|\n)'+re.escape(label)+r'\s*\n+\s*([^\n]+)',text or '',re.I)
    return clean(re.sub(r'^#+\s*','',m.group(1))) if m else ''

def fuel(text):
    x=alow(text)
    if 'plug-in' in x or 'plug in' in x or 'phev' in x: return 'Híbrido Plug-in'
    if 'hybrid' in x or 'hibrid' in x: return 'Híbrido'
    if 'eletric' in x or 'electric' in x: return 'Elétrico'
    if any(k in x for k in ['diesel','bluehdi','tdi','dci']): return 'Diesel'
    if any(k in x for k in ['gasolina','petrol','puretech','tsi']): return 'Gasolina'
    return ''
def fuel_url(url): return fuel(url)
def fuel_group(v):
    x=alow(v)
    if any(k in x for k in ['plug','phev','hybrid','hibrid']): return 'hybrid'
    if 'eletr' in x or 'electric' in x: return 'electric'
    if 'diesel' in x: return 'diesel'
    if 'gasolina' in x or 'petrol' in x: return 'gasoline'
    return ''
def fuel_term(v): return {'hybrid':'híbrido','electric':'elétrico','diesel':'diesel','gasoline':'gasolina'}.get(fuel_group(v),'')

def vin(text):
    for p in [r'\bVIN\b\s*[:\-]?\s*\n?\s*([A-HJ-NPR-Z0-9]{17})\b',r'\b(?:N[uú]mero\s+de\s+chassis|Chassis)\b\s*[:\-]?\s*\n?\s*([A-HJ-NPR-Z0-9]{17})\b']:
        m=re.search(p,text or '',re.I)
        if m and not m.group(1).isdigit(): return m.group(1).upper()
    return ''

def parse_pisca(text,url):
    raw=title_line(text); model=year=price=km=''
    m=re.search(r'^(.*?)\s*-\s*(?:Usado|Usada)\s*-\s*([0-9 .]+)\s*€\s*-.*?\s*-\s*(?:Manual|Autom[aá]tica)\s*-\s*([0-9 .]+)\s*Kms?\s*-\s*(20\d{2})\s*-\s*Pisca\s*Pisca',raw,re.I)
    if m:
        model=clean(m.group(1)); p=num(m.group(2)); k=num(m.group(3)); y=num(m.group(4)); price=eur(p); km=kms(k); year=str(y)
    else:
        mm=re.match(r'^(.*?)\s*-\s*(?:Usado|Usada)\b',raw,re.I); model=clean(mm.group(1)) if mm else raw
        ym=re.search(r'\s-\s(20\d{2})\s-\sPisca\s*Pisca',raw,re.I); pm=re.search(r'\s-\s([0-9 .]+)\s*€\s-',raw); km_m=re.search(r'\s-\s([0-9 .]+)\s*Kms?\s-',raw,re.I)
        if ym: year=ym.group(1)
        if pm: price=eur(num(pm.group(1)))
        if km_m: km=kms(num(km_m.group(1)))
    return {'title':model or 'Veículo','year':year,'price':price,'km':km,'fuel':fuel_url(url) or fuel(field(text,'Combustível') or text[:2200]),'vin':vin(text)}

def parse_generic(text,url):
    b,m,v=field(text,'Marca'),field(text,'Modelo'),field(text,'Versão'); title=clean(' '.join(x for x in [b,m,v] if x)) or title_line(text) or 'Veículo'
    title=re.sub(r'\s*[|–-]\s*(Standvirtual|Pisca\s*Pisca).*$', '', title, flags=re.I); title=re.sub(r'\b(usado|usada|used)\b',' ',title,flags=re.I); title=clean(title).strip(' -|')
    h=text[:6000]; ym=re.search(r'\bAno\s*[:\n ]+\s*(20[0-3]\d)\b',h,re.I) or re.search(r'\b(20[0-3]\d)\b[^\n]{0,120}?\b(?:km|Autom[aá]tica|Manual)\b',h,re.I)
    pm=re.search(r'\b([0-9]{1,3}(?:[ .][0-9]{3})+)\s*€',text); km_m=re.search(r'\b([0-9]{1,3}(?:[ .][0-9]{3})+)\s*km\b',text,re.I)
    return {'title':title,'year':ym.group(1) if ym else '','price':eur(num(pm.group(1))) if pm else '','km':kms(num(km_m.group(1))) if km_m else '','fuel':fuel_url(url) or fuel(field(text,'Combustível') or h),'vin':vin(text)}

def parse_listing(text,url): return parse_pisca(text,url) if 'piscapisca.pt' in url.lower() else parse_generic(text,url)

def resolve(href):
    if not href:return ''
    if href.startswith('//'): href='https:'+href
    try:
        q=parse_qs(urlparse(href).query)
        if q.get('uddg'): return unquote(q['uddg'][0])
    except: pass
    return href

def search(q,n=14):
    try:
        r=requests.get('https://html.duckduckgo.com/html/?q='+quote_plus(q),headers=HEADERS,timeout=(3,7)); r.raise_for_status(); s=BeautifulSoup(r.text,'html.parser'); out=[]
        for x in s.select('.result'):
            a=x.select_one('.result__a'); sn=x.select_one('.result__snippet')
            if not a: continue
            out.append({'title':clean(a.get_text(' ',strip=True)),'snippet':clean(sn.get_text(' ',strip=True) if sn else ''),'url':resolve(a.get('href',''))})
            if len(out)>=n: break
        return out
    except: return []

def score(year,km,vinv=''):
    y,k=num(year),num(km)
    if not y or not k:return 68 if len(vinv or '')==17 else 64
    age=max(0,datetime.now().year-y); annual=k/max(1,age or 1); a=max(35,min(98,98-age*4.7)); q=max(35,min(98,98-(annual/1000)*2.15)); p=min(12,(k/100000)*6)
    return max(35,min(95,round(a*.52+q*.43+(5 if len(vinv or '')==17 else 0)-p)))
def model_key(v):
    p=clean(v).split(); return ' '.join(p[:2]) if len(p)>=2 else clean(v)
def source(url):
    if 'piscapisca.pt' in url:return 'PiscaPisca'
    if 'standvirtual' in url:return 'Standvirtual'
    if 'olx.pt' in url:return 'OLX'
    return 'Marketplace'

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
    u=r.get('url',''); blob=clean((r.get('title') or '')+' '+(r.get('snippet') or ''))
    if not u or u.rstrip('/')==(current or '').rstrip('/') or alow(key) not in alow(blob):return None
    g=fuel_group(fuel(blob) or fuel_url(u))
    if fg and g and g!=fg:return None
    ym=re.search(r'\b(20[0-3]\d)\b',blob); pm=re.search(r'\b([0-9]{1,3}(?:[ .][0-9]{3})+)\s*€',blob); km_m=re.search(r'\b([0-9]{1,3}(?:[ .][0-9]{3})+)\s*km\b',blob,re.I)
    if not(ym and pm and km_m):return None
    p,k=num(pm.group(1)),num(km_m.group(1)); y=ym.group(1)
    return {'title':key,'year':y,'km':kms(k),'price':eur(p),'fuel':fuel(blob),'score':score(y,k),'url':u,'source':source(u)} if 1000<=p<=1000000 and 0<k<=1000000 else None

def discover(model,motor,current='',limit=4):
    key=model_key(model); ft=fuel_term(motor); fg=fuel_group(motor)
    if len(key.split())<2:return []
    queries=[f'site:piscapisca.pt/carros/usados "{key}" {ft}',f'site:standvirtual.com/carros/anuncio "{key}" {ft}',f'"{key}" {ft} usado portugal']
    results=[]; urls=[]
    for q in queries:
        for r in search(q,12):
            results.append(r); u=r.get('url','')
            if u.startswith('http') and any(x in u for x in ['piscapisca.pt/carros/usados/','standvirtual.com/carros/anuncio','olx.pt']) and u not in urls:urls.append(u)
    out=[]
    with ThreadPoolExecutor(max_workers=5) as ex:
        for f in as_completed([ex.submit(from_url,u,key,fg,current) for u in urls[:18]]):
            it=f.result()
            if it and it['url'] not in [x['url'] for x in out]:out.append(it)
            if len(out)>=limit:break
    if len(out)<limit:
        for r in results:
            it=from_snippet(r,key,fg,current)
            if it and it['url'] not in [x['url'] for x in out]:out.append(it)
            if len(out)>=limit:break
    out.sort(key=lambda x:(-x['score'],num(x['price']))); return out[:limit]

def pick(results,words,n=5):
    cand=[]
    for r in results:
        blob=clean((r.get('title') or '')+'. '+(r.get('snippet') or ''))
        for s in re.split(r'(?<=[.!?])\s+',blob):
            if 35<=len(s)<=240:
                sc=sum(1 for w in words if w in alow(s))
                if sc:cand.append((sc,s))
    cand.sort(key=lambda x:(-x[0],len(x[1]))); return [s for _,s in cand[:n]]

@app.route('/')
def home():
    html=open('index.html',encoding='utf-8').read()
    html=html.replace('https://images.unsplash.com/photo-1634130739287-e09cea771066?auto=format&fit=crop&fm=jpg&q=90&w=2200','https://images.unsplash.com/photo-1765905986197-64ef4d5c75f5?auto=format&fit=crop&w=2200&q=88')
    html=html.replace('background-position:center;box-shadow:var(--shadow)','background-position:center 54%;box-shadow:var(--shadow)',1)
    html=html.replace('Imagem: Tim Meyer / Unsplash','Imagem automóvel: Unsplash')
    return Response(html,mimetype='text/html')

@app.route('/api/listing')
def listing():
    u=request.args.get('url','').strip()
    if not u.startswith('http'):return jsonify(ok=False,error='URL inválido'),400
    try:
        t=fetch_text(u); d=parse_listing(t,u); d['image']=image_from(u,t); return jsonify(ok=True,**d)
    except Exception as e:return jsonify(ok=False,error=str(e)),500

@app.route('/api/comparables')
def comparables():
    m=clean(request.args.get('model','')); f=clean(request.args.get('fuel','')); u=clean(request.args.get('url',''))
    if len(m)<3:return jsonify(ok=False,error='Modelo inválido'),400
    return jsonify(ok=True,match=model_key(m),fuel_group=fuel_group(f),deals=discover(m,f,u))

@app.route('/api/research')
def research():
    m=clean(request.args.get('model',''))
    if len(m)<3:return jsonify(ok=False,error='Modelo inválido'),400
    pos=['good','great','excellent','comfortable','efficient','reliable','quality','spacious','practical','smooth','quiet','value']; neg=['problem','issue','fault','failure','unreliable','recall','complaint','expensive','wear','bug','dpf','egr','turbo','clutch','battery','sensor','infotainment']
    r=search(f'"{m}" review reliability common problems owner forum recall',10); strengths=pick(r,pos,5) or ['Idade e quilometragem são fatores relevantes numa avaliação preliminar.','Comparar com exemplares equivalentes ajuda a perceber a qualidade do negócio.']; issues=pick(r,neg,5) or ['Confirmar recalls, campanhas técnicas e histórico de manutenção antes da compra.','Testar todos os sistemas eletrónicos e assistência à condução.']
    checks=[{'title':'Ponto crítico do modelo','detail':x} for x in issues[:2]]; rs=max(35,min(90,60+len(pick(r,pos,5))*4-len(pick(r,neg,5))*4)) if r else None
    return jsonify(ok=True,strengths=strengths,issues=issues,checks=checks,expert_sources=[x['title'] for x in r[:4]],research_score=rs,research_available=bool(r))

if __name__=='__main__':app.run(host='0.0.0.0',port=5050)
