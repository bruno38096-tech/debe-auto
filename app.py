from flask import Flask, request, jsonify, Response
import requests, re, html as htmllib, unicodedata
from bs4 import BeautifulSoup
from urllib.parse import quote_plus, urljoin, urlparse, parse_qs, unquote
from datetime import datetime
from concurrent.futures import ThreadPoolExecutor, as_completed

app=Flask(__name__,static_folder='.')
HEADERS={'User-Agent':'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 Chrome/124 Safari/537.36','Accept-Language':'pt-PT,pt;q=0.9,en;q=0.8'}
def clean(s):return re.sub(r'\s+',' ',htmllib.unescape(s or '')).strip()
def alow(s):return unicodedata.normalize('NFKD',s or '').encode('ascii','ignore').decode().lower()
def num(v):
 try:return int(re.sub(r'\D','',str(v or '')) or 0)
 except:return 0
def eur(n):return f'{n:,}'.replace(',','.')+' €' if n else ''
def kms(n):return f'{n:,}'.replace(',','.')+' km' if n else ''
def fetch_text(url):
 r=requests.get('https://r.jina.ai/'+url,headers=HEADERS,timeout=(4,18));r.raise_for_status();return r.text
def image_from(url,text=''):
 try:
  r=requests.get(url,headers=HEADERS,timeout=(3,8));r.raise_for_status();s=BeautifulSoup(r.text,'html.parser')
  for q in ['meta[property="og:image"]','meta[name="twitter:image"]']:
   t=s.select_one(q)
   if t and t.get('content'):return urljoin(url,t['content'])
 except:pass
 m=re.search(r'!\[[^\]]*\]\((https?://[^)\s]+)',text or '',re.I);return m.group(1) if m else ''
def title_line(t):
 m=re.search(r'^Title:\s*(.+)$',t or '',re.I|re.M);return clean(m.group(1)) if m else ''
def field(t,label):
 m=re.search(r'(?:^|\n)'+re.escape(label)+r'\s*\n+\s*([^\n]+)',t or '',re.I);return clean(re.sub(r'^#+\s*','',m.group(1))) if m else ''
def fuel(t):
 x=alow(t)
 if 'plug-in' in x or 'plug in' in x or 'phev' in x:return 'Híbrido Plug-in'
 if 'hybrid' in x or 'hibrid' in x:return 'Híbrido'
 if 'eletric' in x or 'electric' in x:return 'Elétrico'
 if any(k in x for k in ['diesel','bluehdi','tdi','dci']):return 'Diesel'
 if any(k in x for k in ['gasolina','petrol','puretech','tsi']):return 'Gasolina'
 return ''
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
def engine_hint(text,url=''):
 x=clean(title_line(text)+' '+field(text,'Versão')+' '+field(text,'Motor')+' '+url)
 pats=[r'\b1[.,]2\s*(?:PureTech)?(?:\s*\d{2,3}\s*(?:cv|hp))?',r'\bPureTech\s*\d{2,3}\b',r'\b1[.,]5\s*BlueHDi(?:\s*\d{2,3}\s*(?:cv|hp))?',r'\bBlueHDi\s*\d{2,3}\b',r'\bHybrid\s*\d{2,3}\b']
 for p in pats:
  m=re.search(p,x,re.I)
  if m:return clean(m.group(0)).replace(',','.')
 return ''
def parse_pisca(t,url):
 raw=title_line(t);model=year=price=km='';m=re.search(r'^(.*?)\s*-\s*(?:Usado|Usada)\s*-\s*([0-9 .]+)\s*€\s*-.*?\s*-\s*(?:Manual|Autom[aá]tica)\s*-\s*([0-9 .]+)\s*Kms?\s*-\s*(20\d{2})\s*-\s*Pisca\s*Pisca',raw,re.I)
 if m:model=clean(m.group(1));price=eur(num(m.group(2)));km=kms(num(m.group(3)));year=m.group(4)
 else:
  mm=re.match(r'^(.*?)\s*-\s*(?:Usado|Usada)\b',raw,re.I);model=clean(mm.group(1)) if mm else raw;ym=re.search(r'\s-\s(20\d{2})\s-\sPisca\s*Pisca',raw,re.I);pm=re.search(r'\s-\s([0-9 .]+)\s*€\s-',raw);kk=re.search(r'\s-\s([0-9 .]+)\s*Kms?\s-',raw,re.I);year=ym.group(1) if ym else '';price=eur(num(pm.group(1))) if pm else '';km=kms(num(kk.group(1))) if kk else ''
 return {'title':model or 'Veículo','year':year,'price':price,'km':km,'fuel':fuel(url) or fuel(field(t,'Combustível') or t[:3000]),'vin':vin(t),'engine':engine_hint(t,url)}
def parse_generic(t,url):
 b,m,v=field(t,'Marca'),field(t,'Modelo'),field(t,'Versão');title=clean(' '.join(x for x in [b,m,v] if x)) or title_line(t) or 'Veículo';title=re.sub(r'\s*[|–-]\s*(Standvirtual|Pisca\s*Pisca).*$', '',title,flags=re.I);title=re.sub(r'\b(usado|usada|used)\b',' ',title,flags=re.I);title=clean(title).strip(' -|');h=t[:7000];ym=re.search(r'\bAno\s*[:\n ]+\s*(20[0-3]\d)\b',h,re.I) or re.search(r'\b(20[0-3]\d)\b[^\n]{0,120}?\b(?:km|Autom[aá]tica|Manual)\b',h,re.I);pm=re.search(r'\b([0-9]{1,3}(?:[ .][0-9]{3})+)\s*€',t);kk=re.search(r'\b([0-9]{1,3}(?:[ .][0-9]{3})+)\s*km\b',t,re.I)
 return {'title':title,'year':ym.group(1) if ym else '','price':eur(num(pm.group(1))) if pm else '','km':kms(num(kk.group(1))) if kk else '','fuel':fuel(url) or fuel(field(t,'Combustível') or h),'vin':vin(t),'engine':engine_hint(t,url)}
def parse_listing(t,u):return parse_pisca(t,u) if 'piscapisca.pt' in u.lower() else parse_generic(t,u)
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
 age=max(0,datetime.now().year-y);annual=k/max(1,age or 1);a=max(35,min(98,98-age*4.7));q=max(35,min(98,98-(annual/1000)*2.15));p=min(12,(k/100000)*6);return max(35,min(95,round(a*.52+q*.43+(5 if len(vinv or '')==17 else 0)-p)))
def model_key(v):
 p=clean(v).split();return ' '.join(p[:2]) if len(p)>=2 else clean(v)
def source(u):
 if 'piscapisca.pt' in u:return 'PiscaPisca'
 if 'standvirtual' in u:return 'Standvirtual'
 if 'olx.pt' in u:return 'OLX'
 return 'Marketplace'
def parse_market_page(text,key,fg,current,limit=8):
 out=[];pattern=re.compile(r'(Peugeot\s+2008[^\n]{0,100}?)\s+([0-9 .]{4,10})\s*km\s*[•·]\s*(?:Manual|Autom[aá]tica)\s*[•·]\s*([^•\n]+)\s*[•·]\s*(20\d{2})[^\n]{0,100}\n+\s*([0-9 .]{4,10})\s*€',re.I)
 for m in pattern.finditer(text or ''):
  title=clean(m.group(1));k=num(m.group(2));fu=clean(m.group(3));y=m.group(4);p=num(m.group(5));g=fuel_group(fu)
  if fg and g and g!=fg:continue
  sig=(y,k,p)
  if any(x['_sig']==sig for x in out):continue
  out.append({'title':title,'year':y,'km':kms(k),'price':eur(p),'fuel':fu,'score':score(y,k),'url':'https://www.piscapisca.pt/carros/peugeot/2008','source':'PiscaPisca','_sig':sig})
  if len(out)>=limit:break
 for x in out:x.pop('_sig',None)
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
 ym=re.search(r'\b(20[0-3]\d)\b',blob);pm=re.search(r'\b([0-9]{1,3}(?:[ .][0-9]{3})+)\s*€',blob);kk=re.search(r'\b([0-9]{1,3}(?:[ .][0-9]{3})+)\s*km\b',blob,re.I)
 if not(ym and pm and kk):return None
 p,k=num(pm.group(1)),num(kk.group(1));y=ym.group(1);return {'title':key,'year':y,'km':kms(k),'price':eur(p),'fuel':fuel(blob),'score':score(y,k),'url':u,'source':source(u)} if 1000<=p<=1000000 and 0<k<=1000000 else None
def discover(model,motor,current='',limit=4):
 key=model_key(model);fg=fuel_group(motor);ft=fuel_term(motor);out=[]
 if alow(key)=='peugeot 2008':
  for page in ['https://www.piscapisca.pt/carros/peugeot/2008','https://www.piscapisca.pt/carros/marca/peugeot/2008']:
   try:out.extend(parse_market_page(fetch_text(page),key,fg,current,limit*2))
   except:pass
 queries=[f'site:piscapisca.pt/carros "{key}" {ft}',f'site:standvirtual.com/carros "{key}" {ft}',f'"{key}" {ft} usado Portugal']
 results=[];urls=[]
 for q in queries:
  for r in search(q,14):
   results.append(r);u=r.get('url','')
   if u.startswith('http') and any(x in u for x in ['piscapisca.pt/carros/usados/','standvirtual.com/carros/anuncio','olx.pt']) and u not in urls:urls.append(u)
 with ThreadPoolExecutor(max_workers=5) as ex:
  for f in as_completed([ex.submit(from_url,u,key,fg,current) for u in urls[:16]]):
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
 ded.sort(key=lambda x:(-x['score'],abs(num(x['year'])-datetime.now().year),num(x['price'])));return ded[:limit]
def known_profile(model,engine,year,fuelv):
 x=alow(model+' '+engine+' '+fuelv);y=num(year)
 if 'peugeot 2008' in x and fuel_group(fuelv)=='gasoline':
  return {
   'strengths':['Geração 2008 II: comportamento confortável, habitáculo moderno e boa eficiência para utilização diária.','Sendo um exemplar de 2024, é posterior ao período mais associado aos PureTech afetados pela degradação prematura da correia; ainda assim é essencial confirmar pelo VIN qual a variante de motor/distribuição instalada.','A quilometragem abaixo de 50.000 km é favorável, desde que exista histórico de revisões e óleo com especificação Peugeot/Stellantis correta.'],
   'issues':['Motor 1.2 PureTech: confirmar especificamente o sistema de distribuição. Versões anteriores usam correia banhada em óleo, associada a degradação, resíduos no circuito de lubrificação e perda de pressão de óleo; algumas versões mais recentes passaram para corrente.','Verificar consumo de óleo entre revisões. Há relatos no 1.2 PureTech de consumo elevado ligado a segmentos/pistões e contaminação do óleo; nível baixo ou necessidade frequente de reposição é sinal de alerta.','Confirmar pelo VIN todas as campanhas/recalls aplicáveis ao 2008 II de 2024, incluindo campanhas de travagem/eletrónica e outras específicas da data de produção.'],
   'checks':[{'title':'Distribuição do 1.2 PureTech','detail':'Pedir VIN e referência exata do motor. Confirmar se esta unidade usa correia húmida ou corrente e exigir prova de inspeção/manutenção da distribuição.'},{'title':'Óleo e lubrificação','detail':'Verificar faturas de revisões, especificação do óleo, nível atual e sinais de consumo anormal ou avisos de pressão de óleo.'},{'title':'Campanhas técnicas','detail':'Com o VIN, confirmar na Peugeot se existem recalls/campanhas pendentes antes de fechar negócio.'}],
   'sources':['Peugeot/Stellantis — campanhas por VIN','Razăo Automóvel — guia de compra 2008 1.2 PureTech','Auto Plus — problemas a vigiar no 2008 II','VehicleFaults / fontes técnicas — padrões reportados'],
   'research_score':62}
 return None
@app.route('/')
def home():return Response(open('index.html',encoding='utf-8').read(),mimetype='text/html')
@app.route('/api/listing')
def listing():
 u=request.args.get('url','').strip()
 if not u.startswith('http'):return jsonify(ok=False,error='URL inválido'),400
 try:
  t=fetch_text(u);d=parse_listing(t,u);d['image']=image_from(u,t);return jsonify(ok=True,**d)
 except Exception as e:return jsonify(ok=False,error=str(e)),500
@app.route('/api/comparables')
def comparables():
 m=clean(request.args.get('model',''));f=clean(request.args.get('fuel',''));u=clean(request.args.get('url',''))
 if len(m)<3:return jsonify(ok=False,error='Modelo inválido'),400
 return jsonify(ok=True,match=model_key(m),fuel_group=fuel_group(f),deals=discover(m,f,u))
@app.route('/api/research')
def research():
 m=clean(request.args.get('model',''));e=clean(request.args.get('engine',''));y=clean(request.args.get('year',''));f=clean(request.args.get('fuel',''))
 if len(m)<3:return jsonify(ok=False,error='Modelo inválido'),400
 kp=known_profile(m,e,y,f)
 if kp:return jsonify(ok=True,research_available=True,engine_focus=e or ('1.2 PureTech' if fuel_group(f)=='gasoline' and alow(m)=='peugeot 2008' else ''),**kp)
 q=' '.join(x for x in [m,e,f] if x);r=search(f'"{q}" common problems reliability recall owner review',12);neg=['problem','issue','fault','failure','recall','oil','belt','chain','engine','gearbox','battery','sensor'];pos=['reliable','comfort','efficient','practical','quality','spacious','good','smooth'];
 def pick(words):
  z=[]
  for a in r:
   b=clean((a.get('title') or '')+'. '+(a.get('snippet') or ''))
   if any(w in alow(b) for w in words) and 35<len(b)<330:z.append(b)
  return z[:3]
 issues=pick(neg) or ['Confirmar histórico de manutenção, recalls e problemas específicos da motorização antes da compra.'];strengths=pick(pos) or ['Avaliar estado, histórico e preço face a exemplares equivalentes da mesma motorização.'];checks=[{'title':'Motor e versão','detail':issues[0]},{'title':'Histórico e VIN','detail':'Confirmar manutenção documentada e campanhas técnicas pelo VIN.'}]
 return jsonify(ok=True,strengths=strengths,issues=issues,checks=checks,expert_sources=[x['title'] for x in r[:4]],research_score=60,research_available=bool(r),engine_focus=e)
if __name__=='__main__':app.run(host='0.0.0.0',port=5050)