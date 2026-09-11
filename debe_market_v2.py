"""DEBE market comparison v2.
Returns two useful comparison groups:
- same model / similar era
- same budget, allowing different models
No vehicle-specific catalog is hardcoded.
"""
from concurrent.futures import ThreadPoolExecutor, as_completed
from urllib.parse import urlparse
import re
from flask import request, jsonify

MARKET_HINTS=('piscapisca.pt','standvirtual.com','olx.pt','custojusto.pt')

def _clean(s): return re.sub(r'\s+',' ',str(s or '')).strip()
def _n(v):
    try:return int(re.sub(r'\D','',str(v or '')) or 0)
    except:return 0

def _market_url(u):
    h=urlparse(u or '').netloc.lower()
    return bool(h and any(x in h for x in MARKET_HINTS))

def _key(appmod,title):
    try:return appmod.model_key(title).lower()
    except:return ' '.join(_clean(title).lower().split()[:2])

def _deal_from_url(appmod,u):
    try:
        t=appmod.fetch_text(u);d=appmod.parse_listing(t,u)
        p=_n(d.get('price'));k=_n(d.get('km'));y=_n(d.get('year'))
        if not(appmod.valid_price(p) and 1950<=y<=2035 and 0<k<=1000000):return None
        return {'title':d.get('title') or 'Veículo','year':str(y),'km':appmod.kms(k),'price':appmod.eur(p),
                'fuel':d.get('fuel') or '','score':appmod.score(y,k),'url':u,'source':appmod.source(u),
                '_price':p,'_year':y}
    except Exception:return None

def _collect_urls(appmod,queries,limit=18):
    urls=[]
    for q in queries:
        try: rows=appmod.search(q,12)
        except Exception: rows=[]
        for r in rows:
            u=_clean(r.get('url'))
            if u.startswith('http') and _market_url(u) and u not in urls:urls.append(u)
            if len(urls)>=limit:return urls
    return urls

def _fetch_many(appmod,urls,max_workers=5):
    out=[]
    with ThreadPoolExecutor(max_workers=max_workers) as ex:
        jobs={ex.submit(_deal_from_url,appmod,u):u for u in urls}
        for f in as_completed(jobs):
            try:
                d=f.result()
                if d:out.append(d)
            except Exception:pass
    return out

def _dedup(deals,current=''):
    out=[];seen=set();cur=(current or '').split('?')[0].rstrip('/')
    for d in deals:
        u=(d.get('url') or '').split('?')[0].rstrip('/')
        sig=(u,_clean(d.get('title')).lower(),d.get('year'),d.get('price'))
        if not u or u==cur or sig in seen:continue
        seen.add(sig);out.append(d)
    return out

def _same_model(appmod,model,fuel,year,price,current):
    key=appmod.model_key(model);ft=appmod.fuel_term(fuel);target_y=_n(year);target_p=_n(price)
    # Start with the existing marketplace discovery, then add searches that
    # explicitly mention the era. This avoids comparing a 2006 A4 with a 2023 A4
    # unless no closer examples exist.
    base=[]
    try:base=appmod.discover(model,fuel,current,limit=12) or []
    except Exception:base=[]
    for d in base:
        d['_price']=_n(d.get('price'));d['_year']=_n(d.get('year'))

    yrange=''
    if target_y:yrange=f'{max(1990,target_y-4)} {min(2035,target_y+4)}'
    queries=[
        f'{key} {yrange} {ft} usado Portugal',
        f'{key} {target_y or ""} {ft} OLX PiscaPisca Standvirtual',
    ]
    extra=_fetch_many(appmod,_collect_urls(appmod,queries,14),5)
    candidates=_dedup(base+extra,current)
    target_key=_key(appmod,key)
    candidates=[d for d in candidates if _key(appmod,d.get('title'))==target_key]

    def rank(d):
        yd=abs((d.get('_year') or target_y or 0)-(target_y or d.get('_year') or 0)) if target_y else 0
        pd=abs((d.get('_price') or target_p or 0)-(target_p or d.get('_price') or 0)) if target_p else 0
        return (yd,pd,-int(d.get('score') or 0))
    candidates.sort(key=rank)
    close=[d for d in candidates if not target_y or abs((d.get('_year') or target_y)-target_y)<=6]
    chosen=(close if len(close)>=2 else candidates)[:2]
    for d in chosen:
        d['group']='model';d['why']='Mesmo modelo'+(f' · {abs(d["_year"]-target_y)} ano(s) de diferença' if target_y and d.get('_year') else '')
    return chosen

def _same_budget(appmod,model,fuel,year,price,current,exclude_urls):
    target=_n(price);target_y=_n(year);ft=appmod.fuel_term(fuel);modelkey=_key(appmod,model)
    if not target:return []
    tol=max(1800,int(target*.22));low=max(1000,target-tol);high=target+tol
    queries=[
        f'carro usado {low} {high} euros {ft} Portugal',
        f'automóvel usado {target} euros Portugal OLX PiscaPisca Standvirtual',
        f'carro usado preço {target} {ft} Portugal',
    ]
    urls=_collect_urls(appmod,queries,24)
    deals=_dedup(_fetch_many(appmod,urls,6),current)
    blocked=set(exclude_urls or [])
    deals=[d for d in deals if d.get('url') not in blocked and low<=d.get('_price',0)<=high]
    # Prefer a genuinely different model; same fuel and similar era are useful
    # tie-breakers, but budget is the primary comparison axis.
    def rank(d):
        different=0 if _key(appmod,d.get('title'))!=modelkey else 1
        samefuel=0 if appmod.fuel_group(d.get('fuel'))==appmod.fuel_group(fuel) else 1
        pd=abs(d.get('_price',0)-target)
        yd=abs(d.get('_year',target_y)-target_y) if target_y and d.get('_year') else 99
        return (different,pd,samefuel,yd,-int(d.get('score') or 0))
    deals.sort(key=rank)
    chosen=[];seen_models=set()
    for d in deals:
        k=_key(appmod,d.get('title'))
        if k==modelkey:continue
        if k in seen_models and len(deals)>2:continue
        seen_models.add(k);chosen.append(d)
        if len(chosen)>=2:break
    if len(chosen)<2:
        for d in deals:
            if d not in chosen:chosen.append(d)
            if len(chosen)>=2:break
    for d in chosen:
        d['group']='budget';d['why']=f'Mesma faixa de preço · {appmod.eur(abs(d.get("_price",0)-target))} de diferença'
    return chosen[:2]

def make_view(appmod):
    def comparables_v2():
        model=_clean(request.args.get('model'));fuel=_clean(request.args.get('fuel'));current=_clean(request.args.get('url'))
        price=_clean(request.args.get('price'));year=_clean(request.args.get('year'))
        if len(model)<2:return jsonify(ok=False,error='Modelo inválido'),400
        same=_same_model(appmod,model,fuel,year,price,current)
        budget=_same_budget(appmod,model,fuel,year,price,current,[d.get('url') for d in same])
        deals=same+budget
        # Strip internal ranking fields from API output.
        for d in deals:
            d.pop('_price',None);d.pop('_year',None)
        return jsonify(ok=True,deals=deals,same_model=same[:2],same_budget=budget[:2],count=len(deals))
    return comparables_v2
