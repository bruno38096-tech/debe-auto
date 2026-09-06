from flask import Flask, request, jsonify, send_from_directory
import requests, re, html as htmllib
from bs4 import BeautifulSoup
from urllib.parse import quote_plus

app = Flask(__name__, static_folder='.')
HEADERS={'User-Agent':'Mozilla/5.0 Chrome/124 Safari/537.36'}

def clean(s):
    return re.sub(r'\s+',' ',htmllib.unescape(s or '')).strip()

def fetch_text(url):
    r=requests.get('https://r.jina.ai/'+url,headers=HEADERS,timeout=20)
    r.raise_for_status(); return r.text

def field_after(text,label):
    m=re.search(r'(?:^|\n)'+re.escape(label)+r'\s*\n+\s*([^\n]+)',text,re.I)
    return clean(re.sub(r'^#+\s*','',m.group(1))) if m else ''

def parse_listing(text,url):
    brand=field_after(text,'Marca'); model=field_after(text,'Modelo'); version=field_after(text,'Versão')
    title=' '.join(x for x in [brand,model,version] if x).strip()
    if not title:
        m=re.search(r'^Title:\s*(.+)$',text,re.I|re.M); title=clean(m.group(1)) if m else 'Veículo'
    title=re.sub(r'\b(usado|usada|seminovo|seminova|used)\b',' ',title,flags=re.I)
    title=re.sub(r'\b(19[89]\d|20[0-2]\d)\b',' ',title)
    title=re.sub(r'\d[\d.\s,]*\s*(?:€|EUR)\b',' ',title,flags=re.I)
    title=re.sub(r'\s+',' ',title).strip(' -|')
    head=text[:2200]
    ym=re.search(r'Title:[^\n]*?\b(20[0-2]\d)\b',head,re.I) or re.search(r'Usado[^\n]{0,180}?\b(20[0-2]\d)\b',head,re.I)
    year=ym.group(1) if ym else ''
    pm=re.search(r'###\s*([0-9][0-9\s.]*)\s*\n+\s*EUR\b',text,re.I) or re.search(r'([0-9][0-9\s.]*)\s*EUR\b',text,re.I)
    price=''
    if pm:
        n=int(re.sub(r'\D','',pm.group(1)) or 0)
        if n>=1000: price=f'{n:,}'.replace(',','.')+' €'
    km=''; km_m=re.search(r'\b([0-9]{1,3}(?:[\s.]?[0-9]{3})*)\s*km\b',text,re.I)
    if km_m:
        n=int(re.sub(r'\D','',km_m.group(1)) or 0); km=f'{n:,}'.replace(',','.')+' km'
    fuel=''
    fm=re.search(r'Visão geral[\s\S]{0,280}?\n\s*(Elétrico|Diesel|Gasolina|Híbrido Plug-in|Híbrido)\s*\n+\s*Combustível\b',text,re.I)
    if not fm: fm=re.search(r'\b(Elétrico|Diesel|Gasolina|Híbrido Plug-in|Híbrido)\b',text,re.I)
    if fm: fuel=fm.group(1)
    vm=re.search(r'\b([A-HJ-NPR-Z0-9]{17})\b',text)
    vin=vm.group(1) if vm else ''
    return {'title':title,'year':year,'price':price,'km':km,'fuel':fuel,'vin':vin}

def ddg(q,n=8):
    r=requests.get('https://html.duckduckgo.com/html/?q='+quote_plus(q),headers=HEADERS,timeout=15); r.raise_for_status()
    soup=BeautifulSoup(r.text,'html.parser'); out=[]
    for res in soup.select('.result'):
        a=res.select_one('.result__a'); sn=res.select_one('.result__snippet')
        if not a: continue
        out.append({'title':clean(a.get_text(' ',strip=True)),'snippet':clean(sn.get_text(' ',strip=True) if sn else ''),'url':a.get('href','')})
        if len(out)>=n: break
    return out

def sentences(results):
    out=[]
    for r in results:
        for s in re.split(r'(?<=[.!?])\s+|[•;]\s*',r['title']+'. '+r['snippet']):
            s=clean(s)
            if 35<=len(s)<=240: out.append(s)
    return out

def pick(results, words, n=5):
    vals=[]
    for s in sentences(results):
        score=sum(1 for w in words if w in s.lower())
        if score: vals.append((score,s))
    vals.sort(key=lambda x:(-x[0],len(x[1]))); seen=set(); out=[]
    for _,s in vals:
        k=' '.join(re.sub(r'[^a-z0-9]+',' ',s.lower()).split()[:9])
        if k not in seen: seen.add(k); out.append(s)
        if len(out)>=n: break
    return out

def names(results,n=3):
    return [r['title'] for r in results[:n]]

@app.route('/')
def home(): return send_from_directory('.', 'index.html')

@app.route('/api/listing')
def listing():
    url=request.args.get('url','').strip()
    if not url.startswith('http'): return jsonify(ok=False,error='URL inválido'),400
    try: return jsonify(ok=True,**parse_listing(fetch_text(url),url))
    except Exception as e: return jsonify(ok=False,error=str(e)),500

@app.route('/api/research')
def research():
    model=clean(request.args.get('model',''))
    if len(model)<3: return jsonify(ok=False,error='Modelo inválido'),400
    pos=['good','great','excellent','comfortable','refined','efficient','reliable','quality','spacious','practical','performance','handling','economical','smooth','quiet','well built','value','impressive']
    neg=['problem','issue','fault','failure','weak','poor','unreliable','recall','complaint','expensive','noise','leak','wear','bug','glitch','dpf','egr','turbo','clutch','battery','sensor','infotainment']
    try:
        expert=ddg(f'"{model}" review strengths weaknesses reliability',8)
        owners=ddg(f'"{model}" owner review common problems forum reddit',8)
        official=ddg(f'"{model}" recall common faults technical bulletin',6)
        strengths=pick(expert+owners,pos,5); issues=pick(owners+official+expert,neg,5)
        if len(strengths)<3: strengths += ['A pesquisa encontrou poucas conclusões positivas consistentes; consulta as fontes antes de decidir.']
        if len(issues)<3: issues += ['Não surgiram problemas recorrentes suficientes para uma conclusão forte; confirma recalls e faz inspeção pré-compra.']
        checks=[]
        for issue in issues[:2]:
            low=issue.lower(); title='Ponto crítico do modelo'; detail=issue
            if 'dpf' in low or 'egr' in low: title='DPF / EGR'; detail='Verifica avisos, regenerações, perda de potência e histórico de intervenções no sistema de emissões.'
            elif 'turbo' in low: title='Turbo'; detail='Testa aceleração em carga, perda de potência, fumo e ruídos do turbo.'
            elif 'battery' in low or 'hybrid' in low: title='Bateria / sistema eletrificado'; detail='Confirma autonomia, carregamento, mensagens de erro e histórico de intervenções.'
            elif 'infotainment' in low or 'sensor' in low or 'electr' in low: title='Eletrónica'; detail='Testa sensores, câmaras, infotainment e assistências à condução.'
            checks.append({'title':title,'detail':detail})
        return jsonify(ok=True,strengths=strengths[:5],issues=issues[:5],checks=checks,expert_sources=names(expert),owner_sources=names(owners),official_sources=names(official))
    except Exception as e: return jsonify(ok=False,error=str(e)),500

if __name__=='__main__': app.run(host='0.0.0.0',port=5050)
