from flask import Flask, request, jsonify, send_from_directory
import requests, re, html as htmllib, unicodedata
from bs4 import BeautifulSoup
from urllib.parse import quote_plus, urljoin, urlparse, parse_qs, unquote
from datetime import datetime
from concurrent.futures import ThreadPoolExecutor, as_completed

app = Flask(__name__, static_folder='.')
HEADERS = {
    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 Chrome/124 Safari/537.36',
    'Accept-Language': 'pt-PT,pt;q=0.9,en;q=0.8'
}

def clean(s):
    return re.sub(r'\s+', ' ', htmllib.unescape(s or '')).strip()

def ascii_low(s):
    return unicodedata.normalize('NFKD', s or '').encode('ascii', 'ignore').decode().lower()

def slugify(s):
    return re.sub(r'[^a-z0-9]+', '-', ascii_low(s)).strip('-')

def numeric(v):
    try:
        return int(re.sub(r'\D', '', str(v or '')) or 0)
    except Exception:
        return 0

def format_eur(n):
    return f'{n:,}'.replace(',', '.') + ' €' if n else ''

def format_km(n):
    return f'{n:,}'.replace(',', '.') + ' km' if n else ''

def fetch_text(url):
    r = requests.get('https://r.jina.ai/' + url, headers=HEADERS, timeout=(4, 16))
    r.raise_for_status()
    return r.text

def fetch_image(url, text=''):
    try:
        r = requests.get(url, headers=HEADERS, timeout=(3, 8))
        r.raise_for_status()
        soup = BeautifulSoup(r.text, 'html.parser')
        for selector, attr in [
            ('meta[property="og:image"]', 'content'),
            ('meta[name="twitter:image"]', 'content'),
            ('meta[property="twitter:image"]', 'content')
        ]:
            tag = soup.select_one(selector)
            if tag and tag.get(attr):
                candidate = urljoin(url, tag.get(attr).strip())
                if candidate.startswith('http'):
                    return candidate
        for img in soup.find_all('img'):
            candidate = img.get('src') or img.get('data-src') or img.get('data-lazy-src')
            if candidate:
                candidate = urljoin(url, candidate.strip())
                low = candidate.lower()
                if candidate.startswith('http') and not any(x in low for x in ['logo','icon','avatar','sprite','placeholder']):
                    return candidate
    except Exception:
        pass
    if text:
        for pat in [r'!\[[^\]]*\]\((https?://[^)\s]+)', r'(https?://[^\s)]+\.(?:jpg|jpeg|png|webp)(?:\?[^\s)]*)?)']:
            m = re.search(pat, text, re.I)
            if m:
                return m.group(1)
    return ''

def field_after(text, label):
    m = re.search(r'(?:^|\n)' + re.escape(label) + r'\s*\n+\s*([^\n]+)', text, re.I)
    return clean(re.sub(r'^#+\s*', '', m.group(1))) if m else ''

def title_line(text):
    m = re.search(r'^Title:\s*(.+)$', text or '', re.I | re.M)
    return clean(m.group(1)) if m else ''

def detect_fuel(text):
    low = ascii_low(text)
    if 'plug-in' in low or 'plug in' in low or 'phev' in low: return 'Híbrido Plug-in'
    if 'hybrid' in low or 'hibrid' in low: return 'Híbrido'
    if 'eletric' in low or 'electric' in low: return 'Elétrico'
    if 'diesel' in low or 'bluehdi' in low or 'tdi' in low or 'dci' in low: return 'Diesel'
    if 'gasolina' in low or 'petrol' in low or 'puretech' in low or 'tsi' in low: return 'Gasolina'
    return ''

def fuel_from_url(url):
    low = ascii_low(url)
    if 'plug-in' in low or 'plug_in' in low or 'phev' in low: return 'Híbrido Plug-in'
    if 'hibrid' in low or 'hybrid' in low: return 'Híbrido'
    if 'eletric' in low or 'electric' in low: return 'Elétrico'
    if 'diesel' in low: return 'Diesel'
    if 'gasolina' in low or 'petrol' in low: return 'Gasolina'
    return ''

def labelled_vin(text):
    # Never treat arbitrary 17-digit IDs as VINs. Require an explicit nearby label.
    patterns = [
        r'\bVIN\b\s*[:\-]?\s*\n?\s*([A-HJ-NPR-Z0-9]{17})\b',
        r'\b(?:N[uú]mero\s+de\s+chassis|Chassis)\b\s*[:\-]?\s*\n?\s*([A-HJ-NPR-Z0-9]{17})\b'
    ]
    for pat in patterns:
        m = re.search(pat, text or '', re.I)
        if m:
            vin = m.group(1).upper()
            if not vin.isdigit():
                return vin
    return ''

def parse_piscapisca(text, url):
    raw = title_line(text)
    # Typical title:
    # Peugeot 2008 - Usado - 20499€ - SUV e TT - Manual - 45875 Kms - 2024 - Pisca Pisca
    model = ''
    year = ''
    price = ''
    km = ''
    if raw:
        m = re.search(
            r'^(.*?)\s*-\s*(?:Usado|Usada)\s*-\s*([0-9 .]+)\s*€\s*-.*?\s*-\s*(?:Manual|Autom[aá]tica)\s*-\s*([0-9 .]+)\s*Kms?\s*-\s*(20\d{2})\s*-\s*Pisca\s*Pisca',
            raw, re.I
        )
        if m:
            model = clean(m.group(1))
            p = numeric(m.group(2)); k = numeric(m.group(3)); y = numeric(m.group(4))
            price = format_eur(p) if 1000 <= p <= 1000000 else ''
            km = format_km(k) if 0 < k <= 1000000 else ''
            year = str(y) if 1990 <= y <= datetime.now().year + 1 else ''
        else:
            # Conservative fallback: model is everything before "- Usado".
            mm = re.match(r'^(.*?)\s*-\s*(?:Usado|Usada)\b', raw, re.I)
            model = clean(mm.group(1)) if mm else clean(re.sub(r'\s*-\s*Pisca\s*Pisca.*$', '', raw, flags=re.I))
            # Year must be near the end, so model names such as Peugeot 2008 are not mistaken for a year.
            ym = re.search(r'\s-\s(20\d{2})\s-\sPisca\s*Pisca', raw, re.I)
            pm = re.search(r'\s-\s([0-9 .]+)\s*€\s-', raw)
            km_m = re.search(r'\s-\s([0-9 .]+)\s*Kms?\s-', raw, re.I)
            if ym: year = ym.group(1)
            if pm:
                p = numeric(pm.group(1)); price = format_eur(p) if 1000 <= p <= 1000000 else ''
            if km_m:
                k = numeric(km_m.group(1)); km = format_km(k) if 0 < k <= 1000000 else ''

    fuel = fuel_from_url(url)
    if not fuel:
        # Prefer labelled/overview information, not arbitrary mentions elsewhere on the page.
        overview = (field_after(text, 'Combustível') or field_after(text, 'Fuel') or text[:2500])
        fuel = detect_fuel(overview)
    return {
        'title': model or 'Veículo',
        'year': year,
        'price': price,
        'km': km,
        'fuel': fuel,
        'vin': labelled_vin(text)
    }

def parse_generic(text, url):
    brand = field_after(text, 'Marca')
    model = field_after(text, 'Modelo')
    version = field_after(text, 'Versão')
    title = ' '.join(x for x in [brand, model, version] if x).strip()
    if not title:
        title = title_line(text) or 'Veículo'
    title = re.sub(r'\s*[|–-]\s*(Standvirtual|Pisca\s*Pisca).*$', '', title, flags=re.I)
    title = re.sub(r'\b(usado|usada|seminovo|seminova|used)\b', ' ', title, flags=re.I)
    title = re.sub(r'\d[\d.\s,]*\s*(?:€|EUR)\b', ' ', title, flags=re.I)
    title = re.sub(r'\s+', ' ', title).strip(' -|')

    head = text[:6000]
    ym = (re.search(r'\bAno\s*[:\n ]+\s*(20[0-3]\d)\b', head, re.I)
          or re.search(r'\b(20[0-3]\d)\b[^\n]{0,120}?\b(?:km|Autom[aá]tica|Manual)\b', head, re.I))
    year = ym.group(1) if ym else ''
    pm = (re.search(r'###\s*([0-9][0-9\s.]*)\s*\n+\s*EUR\b', text, re.I)
          or re.search(r'\b([0-9]{1,3}(?:[ .][0-9]{3})+)\s*€', text)
          or re.search(r'([0-9][0-9\s.]*)\s*EUR\b', text, re.I))
    price = ''
    if pm:
        p = numeric(pm.group(1)); price = format_eur(p) if 1000 <= p <= 1000000 else ''
    km = ''
    km_m = re.search(r'\b([0-9]{1,3}(?:[\s.]?[0-9]{3})*)\s*km\b', text, re.I)
    if km_m:
        k = numeric(km_m.group(1)); km = format_km(k) if 0 < k <= 1000000 else ''
    fuel = fuel_from_url(url) or detect_fuel(field_after(text, 'Combustível') or head)
    return {'title': title, 'year': year, 'price': price, 'km': km, 'fuel': fuel, 'vin': labelled_vin(text)}

def parse_listing(text, url):
    if 'piscapisca.pt' in (url or '').lower():
        return parse_piscapisca(text, url)
    return parse_generic(text, url)

def resolve_search_url(href):
    if not href: return ''
    if href.startswith('//'): href = 'https:' + href
    try:
        parsed = urlparse(href)
        q = parse_qs(parsed.query)
        if 'uddg' in q and q['uddg']:
            return unquote(q['uddg'][0])
    except Exception:
        pass
    return href

def search_web(q, n=12):
    try:
        r = requests.get('https://html.duckduckgo.com/html/?q=' + quote_plus(q), headers=HEADERS, timeout=(3, 6))
        r.raise_for_status()
        soup = BeautifulSoup(r.text, 'html.parser')
        out = []
        for res in soup.select('.result'):
            a = res.select_one('.result__a'); sn = res.select_one('.result__snippet')
            if not a: continue
            href = resolve_search_url(a.get('href', ''))
            out.append({'title': clean(a.get_text(' ', strip=True)), 'snippet': clean(sn.get_text(' ', strip=True) if sn else ''), 'url': href})
            if len(out) >= n: break
        return out
    except Exception:
        return []

def sentences(results):
    out=[]
    for r in results:
        for s in re.split(r'(?<=[.!?])\s+|[•;]\s*', r['title'] + '. ' + r['snippet']):
            s=clean(s)
            if 35 <= len(s) <= 240: out.append(s)
    return out

def pick(results, words, n=5):
    vals=[]
    for s in sentences(results):
        score=sum(1 for w in words if w in s.lower())
        if score: vals.append((score,s))
    vals.sort(key=lambda x:(-x[0],len(x[1])))
    seen,out=set(),[]
    for _,s in vals:
        k=' '.join(re.sub(r'[^a-z0-9]+',' ',s.lower()).split()[:9])
        if k not in seen:
            seen.add(k); out.append(s)
        if len(out)>=n: break
    return out

def names(results,n=4): return [r['title'] for r in results[:n]]

def fallback_strengths(model):
    low=model.lower(); out=[]
    if 'hybrid' in low or 'híbrido' in low: out.append('Sistema híbrido pode reduzir consumos em utilização urbana e periurbana quando usado no perfil adequado.')
    if 'diesel' in low: out.append('Motorização diesel tende a ser adequada a utilização com muitos quilómetros e percursos longos.')
    if 'elétr' in low or 'electric' in low: out.append('Propulsão elétrica oferece condução silenciosa e custos energéticos potencialmente mais baixos quando existe carregamento conveniente.')
    out.append('Idade e quilometragem deste exemplar são fatores relevantes numa avaliação preliminar, desde que o histórico confirme o estado anunciado.')
    out.append('Uma decisão final deve combinar histórico de manutenção, VIN, inspeção pré-compra e comparação com exemplares equivalentes.')
    return out[:5]

def fallback_issues(model):
    low=model.lower(); out=[]
    if any(x in low for x in ['hybrid','híbrido','elétr','electric']): out.append('Confirmar estado da bateria, sistema elétrico/híbrido e ausência de mensagens de erro ou campanhas técnicas pendentes.')
    if 'diesel' in low: out.append('Confirmar histórico de utilização e estado de DPF/EGR, sobretudo se o veículo fez muitos percursos curtos.')
    out.append('A pesquisa externa não devolveu evidência suficiente para classificar problemas recorrentes específicos deste modelo com confiança.')
    out.append('Verificar recalls, campanhas técnicas e histórico de manutenção antes da compra.')
    return out[:5]

def vehicle_score(year, km, vin=''):
    y,k=numeric(year),numeric(km)
    if not y or not k: return 68 if len(vin or '')==17 else 64
    age=max(0,datetime.now().year-y)
    annual=k/max(1,age or 1)
    age_score=max(35,min(98,98-age*4.7))
    km_score=max(35,min(98,98-(annual/1000)*2.15))
    absolute_penalty=min(12,(k/100000)*6)
    s=round(age_score*.52+km_score*.43+(5 if len(vin or '')==17 else 0)-absolute_penalty)
    return max(35,min(95,s))

def model_key(model):
    parts=[p for p in re.split(r'\s+',clean(model)) if p]
    return ' '.join(parts[:2]) if len(parts)>=2 else clean(model)

def fuel_group(fuel):
    low=ascii_low(fuel)
    if any(x in low for x in ['plug','phev','hybrid','hibrid']): return 'hybrid'
    if 'eletr' in low or 'electric' in low: return 'electric'
    if 'diesel' in low: return 'diesel'
    if 'gasolina' in low or 'petrol' in low: return 'gasoline'
    return ''

def fuel_search_term(fuel):
    return {'hybrid':'híbrido','electric':'elétrico','diesel':'diesel','gasoline':'gasolina'}.get(fuel_group(fuel),'')

def comparable_from_url(url, wanted_key, wanted_fuel, current_url):
    if not url or url.rstrip('/') == (current_url or '').rstrip('/'):
        return None
    try:
        text = fetch_text(url)
        d = parse_listing(text, url)
        if ascii_low(model_key(d.get('title'))) != ascii_low(wanted_key):
            return None
        fg = fuel_group(d.get('fuel'))
        if wanted_fuel and fg and fg != wanted_fuel:
            return None
        if not d.get('year') or not d.get('km') or not d.get('price'):
            return None
        source = 'PiscaPisca' if 'piscapisca.pt' in url else ('Standvirtual' if 'standvirtual' in url else 'Marketplace')
        return {
            'title': d['title'], 'year': d['year'], 'km': d['km'], 'price': d['price'],
            'fuel': d.get('fuel') or '', 'score': vehicle_score(d['year'], d['km'], d.get('vin','')),
            'url': url, 'source': source
        }
    except Exception:
        return None

def discover_comparables(model, fuel, current_url='', limit=4):
    key = model_key(model)
    if len(key.split()) < 2:
        return []
    fterm = fuel_search_term(fuel)
    queries = [
        f'site:piscapisca.pt/carros/usados "{key}" {fterm}',
        f'site:standvirtual.com/carros/anuncio "{key}" {fterm}'
    ]
    urls=[]
    for q in queries:
        for r in search_web(q, 10):
            u=r.get('url','')
            if u.startswith('http') and ('piscapisca.pt/carros/usados/' in u or 'standvirtual.com/carros/anuncio' in u) and u not in urls:
                urls.append(u)
    wanted_fuel=fuel_group(fuel)
    out=[]
    with ThreadPoolExecutor(max_workers=4) as ex:
        futures=[ex.submit(comparable_from_url,u,key,wanted_fuel,current_url) for u in urls[:12]]
        for fut in as_completed(futures):
            item=fut.result()
            if item and item['url'] not in [x['url'] for x in out]:
                out.append(item)
    out.sort(key=lambda x:(-x['score'], numeric(x['price'])))
    return out[:limit]

@app.route('/')
def home(): return send_from_directory('.', 'index.html')

@app.route('/api/listing')
def listing():
    url=request.args.get('url','').strip()
    if not url.startswith('http'): return jsonify(ok=False,error='URL inválido'),400
    try:
        text=fetch_text(url); data=parse_listing(text,url); data['image']=fetch_image(url,text)
        return jsonify(ok=True,**data)
    except Exception as e:
        return jsonify(ok=False,error=str(e)),500

@app.route('/api/comparables')
def comparables():
    model=clean(request.args.get('model','')); fuel=clean(request.args.get('fuel','')); current_url=clean(request.args.get('url',''))
    if len(model)<3: return jsonify(ok=False,error='Modelo inválido'),400
    deals=discover_comparables(model,fuel,current_url)
    return jsonify(ok=True,match=model_key(model),fuel_group=fuel_group(fuel),deals=deals)

@app.route('/api/research')
def research():
    model=clean(request.args.get('model',''))
    if len(model)<3: return jsonify(ok=False,error='Modelo inválido'),400
    pos=['good','great','excellent','comfortable','refined','efficient','reliable','quality','spacious','practical','performance','handling','economical','smooth','quiet','well built','value','impressive']
    neg=['problem','issue','fault','failure','weak','poor','unreliable','recall','complaint','expensive','noise','leak','wear','bug','glitch','dpf','egr','turbo','clutch','battery','sensor','infotainment']
    results=search_web(f'"{model}" review reliability common problems owner forum recall',10)
    found_strengths=pick(results,pos,5); found_issues=pick(results,neg,5)
    strengths=found_strengths or fallback_strengths(model); issues=found_issues or fallback_issues(model)
    checks=[]
    for issue in issues[:2]:
        low=issue.lower(); title,detail='Ponto crítico do modelo',issue
        if 'dpf' in low or 'egr' in low:
            title='DPF / EGR'; detail='Verifica avisos, regenerações, perda de potência e histórico de intervenções no sistema de emissões.'
        elif 'turbo' in low:
            title='Turbo'; detail='Testa aceleração em carga, perda de potência, fumo e ruídos do turbo.'
        elif any(x in low for x in ['battery','bateria','hybrid','híbrido']):
            title='Bateria / sistema eletrificado'; detail='Confirma autonomia, funcionamento do sistema híbrido, mensagens de erro e histórico de intervenções.'
        elif any(x in low for x in ['infotainment','sensor','electr','eletr']):
            title='Eletrónica'; detail='Testa sensores, câmaras, infotainment e assistências à condução.'
        checks.append({'title':title,'detail':detail})
    research_score=max(35,min(90,60+len(found_strengths)*4-len(found_issues)*4)) if results else None
    return jsonify(ok=True,strengths=strengths[:5],issues=issues[:5],checks=checks,expert_sources=names(results),owner_sources=[],official_sources=[],research_score=research_score,research_available=bool(results))

if __name__=='__main__':
    app.run(host='0.0.0.0',port=5050)
