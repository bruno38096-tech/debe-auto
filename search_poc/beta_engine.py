"""Live multi-source discovery engine for the DEBE Search beta.

This is a beta discovery layer, not yet a contractual full-feed integration.
It queries public indexed inventory pages concurrently and normalizes the
results into one format. Dedicated direct connectors are used when available.
"""
from concurrent.futures import ThreadPoolExecutor, as_completed
from urllib.parse import quote_plus, urlparse
from bs4 import BeautifulSoup
import html, re, time, threading, requests, unicodedata

from search_poc.beta_sources import SOURCES

HEADERS={
    "User-Agent":"Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 Chrome/124 Safari/537.36",
    "Accept-Language":"pt-PT,pt;q=0.9,en;q=0.7",
}
_cache={}
_cache_lock=threading.Lock()
CACHE_TTL=600


def clean(s):
    return re.sub(r"\s+"," ",html.unescape(s or "")).strip()


def ascii_low(s):
    return unicodedata.normalize("NFKD",s or "").encode("ascii","ignore").decode().lower()


def _money_values(text):
    vals=[]
    pats=[
        r"(\d{1,3}(?:[\.\s]\d{3})+(?:,\d{1,2})?)\s*(?:€|EUR)",
        r"(?:€|EUR)\s*(\d{1,3}(?:[\.\s]\d{3})+(?:,\d{1,2})?)",
    ]
    for p in pats:
        for m in re.finditer(p,text or "",re.I):
            raw=m.group(1).replace(" ","").replace(".","").replace(",",".")
            try:
                v=float(raw)
                if 3000 <= v <= 1000000 and v not in vals: vals.append(v)
            except Exception: pass
    return vals


def _km(text):
    m=re.search(r"(\d{1,3}(?:[\.\s]\d{3})*)\s*km\b",text or "",re.I)
    if not m:return None
    try:return int(re.sub(r"\D","",m.group(1)))
    except:return None


def _year(text):
    # Prefer explicit registration-style dates, then a standalone recent model year.
    m=re.search(r"(?:1.?\s*registo|matr[ií]cula|ano)[^\d]{0,15}(20[1-2]\d)",text or "",re.I)
    if m:return int(m.group(1))
    years=[int(x) for x in re.findall(r"\b(20(?:1[0-9]|2[0-7]))\b",text or "")]
    return years[0] if years else None


def _condition(blob, source):
    b=ascii_low(blob)
    if any(x in b for x in ("veiculo novo","veículo novo","novo e disponivel","disponivel imediatamente","0 km novo")):
        return "new_stock"
    if any(x in b for x in ("demonstracao","demonstração","viatura de servico","viatura de serviço","carro de demonstracao","carro de demonstração")):
        return "demo_service"
    if any(x in b for x in ("km0","km 0","seminovo","semi-novo")):
        return "km0"
    if any(x in b for x in ("certified","approved","premium selection","selektion","selek", "usados de confianca","usados de confiança","lexus select","go on","das weltauto","intelligent choice")):
        return "used_certified"
    if "usad" in b or "re-estreio" in b:
        return "used"
    kinds=source.get("kinds") or []
    return kinds[0] if len(kinds)==1 else "unknown"


def _availability(blob):
    b=ascii_low(blob)
    if "disponivel imediatamente" in b or "disponível imediatamente" in (blob or "").lower(): return "Disponível imediatamente"
    if "em stock" in b: return "Em stock"
    m=re.search(r"dispon[ií]vel em\s+([^\.;|]{2,40})",blob or "",re.I)
    return ("Disponível em "+clean(m.group(1))) if m else ""


def _dealer(blob):
    # Useful snippets commonly expose "Disponível em <dealer>".
    m=re.search(r"(?:dispon[ií]vel em|concession[aá]rio)\s+([^\.;|]{2,60})",blob or "",re.I)
    return clean(m.group(1)) if m else ""


def _discount(prices, blob):
    if len(prices)<2:return (None,None,None)
    b=ascii_low(blob)
    if not any(x in b for x in ("desconto","antes","pvp","pvpr","preco original","preço original","campanha")):
        return (prices[0],None,None)
    hi=max(prices); lo=min(prices)
    if hi<=lo:return (lo,None,None)
    d=hi-lo
    return (lo,hi,round(d/hi*100,1))


def _source_query(q, source, limit=3, timeout=8):
    domain=source["domain"]
    sq=f'site:{domain} "{q}"'
    urls=[
        "https://www.bing.com/search?format=rss&cc=pt&setlang=pt-pt&q="+quote_plus(sq),
        "https://r.jina.ai/https://www.bing.com/search?format=rss&cc=pt&setlang=pt-pt&q="+quote_plus(sq),
    ]
    items=[]
    error=""
    for idx,u in enumerate(urls):
        try:
            r=requests.get(u,headers=HEADERS,timeout=timeout)
            r.raise_for_status()
            if idx==0 and "<item" in r.text.lower():
                soup=BeautifulSoup(r.text,"xml")
                for item in soup.find_all("item"):
                    title=clean(item.title.get_text(" ",strip=True) if item.title else "")
                    link=clean(item.link.get_text(strip=True) if item.link else "")
                    desc=clean(BeautifulSoup(item.description.get_text(" ",strip=True) if item.description else "","html.parser").get_text(" ",strip=True))
                    if domain not in urlparse(link).netloc.lower(): continue
                    items.append((title,desc,link))
                    if len(items)>=limit:break
            else:
                for m in re.finditer(r"\[([^\]\n]{3,220})\]\((https?://[^)\s]+)\)",r.text):
                    title=clean(m.group(1)); link=html.unescape(m.group(2))
                    if domain not in urlparse(link).netloc.lower(): continue
                    tail=clean(r.text[m.end():m.end()+600])
                    items.append((title,tail,link))
                    if len(items)>=limit:break
            if items: break
        except Exception as e:
            error=str(e)[:120]

    out=[]; seen=set()
    for title,desc,link in items:
        if link in seen:continue
        seen.add(link)
        blob=title+" "+desc
        # Guard against unrelated indexed pages.
        qterms=[x for x in re.findall(r"[a-z0-9]+",ascii_low(q)) if len(x)>=2]
        hay=ascii_low(blob+" "+link)
        hits=sum(1 for x in qterms if x in hay)
        need=1 if len(qterms)<=2 else max(2,len(qterms)-1)
        if qterms and hits<need:continue
        prices=_money_values(blob)
        current,list_price,disc_pct=_discount(prices,blob)
        out.append({
            "source_key":source["key"],"source":source["name"],"official":source["official"],
            "title":title,"snippet":desc[:420],"url":link,
            "condition":_condition(blob,source),"availability":_availability(blob),
            "price_eur":current,"list_price_eur":list_price,
            "discount_eur":round(list_price-current,2) if current and list_price else None,
            "discount_pct":disc_pct,"mileage_km":_km(blob),"year":_year(blob),
            "dealer":_dealer(blob),"discovery":"public_index",
        })
    return out,error


def _direct_specials(q):
    """Use the direct PoC connectors where the query matches their validated scope."""
    out=[]
    low=ascii_low(q)
    if "bmw" in low and "330" in low and "touring" in low:
        try:
            from search_poc.connectors.bmw_premium import fetch_bmw_330e_touring
            for v in fetch_bmw_330e_touring(timeout=9):
                d=v.to_dict(); d.update({"source_key":"bmw_premium","source":"BMW Premium Selection","official":True,"title":f"BMW Série 3 {v.variant} Touring","snippet":f"{v.year or ''} · {v.mileage_km or 0:,} km · {v.dealer}".replace(",","."),"dealer":v.dealer,"condition":"used_certified","availability":"","discovery":"direct_connector"})
                out.append(d)
        except Exception: pass
        try:
            from search_poc.connectors.bmcar import discover_bmw_330e_touring
            for v in discover_bmw_330e_touring(timeout=9):
                d=v.to_dict(); d.update({"source_key":"bmcar","source":"BMcar","official":True,"title":f"BMW Série 3 {v.variant} Touring","snippet":f"{v.year or ''} · {v.mileage_km or 0:,} km · BMcar".replace(",","."),"condition":v.condition or "used","availability":"","discovery":"direct_connector"})
                out.append(d)
        except Exception: pass
        try:
            from search_poc.connectors.bmw_new_stock import caetano_330e_touring_stock
            for v in caetano_330e_touring_stock(timeout=9):
                d=v.to_dict(); d.update({"source_key":"bmw_caetano_new","source":"BMW / Caetano — novos em stock","official":True,"title":"BMW 330e Touring novo em stock","snippet":"Stock confirmado no portal oficial do concessionário; preço final sob proposta quando não publicado.","condition":"new_stock","dealer":"Caetano","discovery":"direct_connector"})
                out.append(d)
        except Exception: pass
    return out


def _dedup(rows):
    out=[]; seen_urls=set(); seen_sig=set()
    for r in rows:
        u=r.get("url") or ""
        if u and u in seen_urls: continue
        sig=(ascii_low(r.get("title",""))[:90],r.get("price_eur"),r.get("mileage_km"),r.get("source_key"))
        if sig in seen_sig:continue
        if u:seen_urls.add(u)
        seen_sig.add(sig);out.append(r)
    return out


def search_all(q, condition="all", max_per_source=3):
    q=clean(q)
    if not q:return {"query":"","results":[],"sources":[],"summary":{"total":0}}
    cache_key=(ascii_low(q),condition,max_per_source)
    now=time.time()
    with _cache_lock:
        hit=_cache.get(cache_key)
        if hit and now-hit[0]<CACHE_TTL:return hit[1]

    results=_direct_specials(q)
    statuses=[]
    with ThreadPoolExecutor(max_workers=10) as ex:
        jobs={ex.submit(_source_query,q,s,max_per_source):s for s in SOURCES}
        for fut in as_completed(jobs):
            s=jobs[fut]
            try:
                rows,err=fut.result()
                results.extend(rows)
                statuses.append({"key":s["key"],"name":s["name"],"count":len(rows),"status":"ok" if rows else ("error" if err else "empty"),"error":err})
            except Exception as e:
                statuses.append({"key":s["key"],"name":s["name"],"count":0,"status":"error","error":str(e)[:120]})

    results=_dedup(results)
    if condition!="all":
        results=[r for r in results if r.get("condition")==condition]

    def rank(r):
        # Explicit discount first, then official/direct, then data completeness.
        return (
            float(r.get("discount_pct") or 0),
            1 if r.get("official") else 0,
            1 if r.get("discovery")=="direct_connector" else 0,
            sum(1 for k in ("price_eur","mileage_km","year") if r.get(k) is not None),
        )
    results.sort(key=rank,reverse=True)
    summary={
        "total":len(results),
        "official":sum(1 for r in results if r.get("official")),
        "new_stock":sum(1 for r in results if r.get("condition")=="new_stock"),
        "demo_service":sum(1 for r in results if r.get("condition")=="demo_service"),
        "km0":sum(1 for r in results if r.get("condition")=="km0"),
        "used_certified":sum(1 for r in results if r.get("condition")=="used_certified"),
        "used":sum(1 for r in results if r.get("condition")=="used"),
        "explicit_discount":sum(1 for r in results if r.get("discount_pct")),
        "sources_with_hits":sum(1 for s in statuses if s["count"]>0),
        "sources_checked":len(SOURCES),
    }
    payload={"query":q,"condition":condition,"results":results,"sources":sorted(statuses,key=lambda x:(-x["count"],x["name"])),"summary":summary,"beta_note":"Cobertura beta por conetores diretos + descoberta pública indexada; um resultado vazio não prova ausência de stock na fonte."}
    with _cache_lock:_cache[cache_key]=(now,payload)
    return payload
