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
from search_poc.query_validation import query_matches_row

HEADERS={
    "User-Agent":"Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 Chrome/124 Safari/537.36",
    "Accept-Language":"pt-PT,pt;q=0.9,en;q=0.7",
}
_cache={}
_cache_lock=threading.Lock()
CACHE_TTL=600
_sitemap_cache={}
_sitemap_lock=threading.Lock()
SITEMAP_TTL=3600

# Brand-specific routing keeps searches fast while retaining national dealer coverage.
COMMON_KEYS={"carclasse","santogal","caetano","bmcar","mcoutinho","filinto","standvirtual"}
BRAND_KEYS={
    "bmw":{"bmw_new","bmw_premium","bmw_caetano_new"},
    "mercedes":{"mercedes_new","mercedes_certified"},
    "audi":{"audi_immediate","audi_used","dwa"},
    "volkswagen":{"vw_new","dwa"},
    "vw":{"vw_new","dwa"},
    "seat":{"seat_new","dwa"},
    "cupra":{"cupra_new","dwa"},
    "skoda":{"skoda_new","dwa"},
    "porsche":{"porsche_finder"},
    "volvo":{"volvo_inventory","volvo_selekt"},
    "ford":{"ford_new","ford_approved"},
    "hyundai":{"hyundai_new","hyundai_goon"},
    "toyota":{"toyota_new","toyota_used"},
    "lexus":{"lexus_new","lexus_select"},
    "nissan":{"nissan_new","nissan_choice"},
    "renault":{"renault_new","renault_renew"},
    "dacia":{"dacia_new","renault_renew"},
    "kia":{"kia"},
    "peugeot":{"peugeot_new","stellantis_you","spoticar"},
    "citroen":{"citroen_new","stellantis_you","spoticar"},
    "citroën":{"citroen_new","stellantis_you","spoticar"},
    "opel":{"opel_new","stellantis_you","spoticar"},
    "fiat":{"fiat_new","stellantis_you","spoticar"},
    "jeep":{"jeep_new","stellantis_you","spoticar"},
    "tesla":{"tesla"},
}

def _relevant_sources(q):
    low=ascii_low(q)
    brand_keys=set()
    for brand,keys in BRAND_KEYS.items():
        if re.search(r"\b"+re.escape(ascii_low(brand))+r"\b",low):
            brand_keys |= keys
    if brand_keys:
        allow=brand_keys | COMMON_KEYS
        return [s for s in SOURCES if s["key"] in allow]
    # Generic searches are intentionally capped to the broadest national sources.
    generic={"bmw_premium","mercedes_certified","audi_immediate","dwa","porsche_finder",
             "volvo_inventory","ford_approved","hyundai_goon","toyota_used","lexus_select",
             "stellantis_you","spoticar"} | COMMON_KEYS
    return [s for s in SOURCES if s["key"] in generic]


def _xml_soup(text):
    """Parse simple RSS/sitemap XML without requiring lxml in clean CI/runtime images."""
    try:
        return BeautifulSoup(text, "xml")
    except Exception:
        return BeautifulSoup(text, "html.parser")


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
    if len(kinds)==1 and kinds[0]=="new_stock":
        # Only inventory-specific portals may imply immediate stock without
        # an explicit availability phrase. Generic manufacturer model pages
        # are not treated as stock merely because they sell new cars.
        trusted={"audi_immediate","volvo_inventory","bmw_caetano_new","tesla"}
        return "new_stock" if source.get("key") in trusted else "unknown"
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
    """Normalize public-index price snippets.

    A trade-in-only price is not the unconditional asking price. Keep it in a
    separate conditional field so DEBE never presents it as cash price.
    """
    if not prices:
        return (None,None,None,None,"")
    if len(prices)==1:
        return (prices[0],None,None,None,"")
    b=ascii_low(blob)
    if not any(x in b for x in ("desconto","antes","pvp","pvpr","preco original","preço original","campanha","retoma")):
        return (prices[0],None,None,None,"")
    hi=max(prices); lo=min(prices)
    if hi<=lo:
        return (lo,None,None,None,"")
    d=hi-lo
    pct=round(d/hi*100,1)
    conditional=any(x in b for x in ("retoma","trade-in","trade in"))
    if conditional:
        return (hi,hi,pct,lo,"retoma")
    return (lo,hi,pct,None,"")


def _query_aliases(q):
    """Generate robust discovery variants without requiring exact dealer wording."""
    q=clean(q)
    out=[q]
    # 300 e / 300e and 300 de / 300de are both common in Portuguese stock systems.
    out.append(re.sub(r"\b(\d{3})\s+(de|e)\b",r"\1\2",q,flags=re.I))
    out.append(q.replace("Mercedes-Benz","Mercedes"))
    # Dealer titles often omit the BMW series name: "BMW 330e Touring".
    out.append(re.sub(r"\bS[eé]rie\s+\d+\b","",q,flags=re.I))
    # Body terms help the UI but can over-constrain search engine discovery.
    out.append(re.sub(r"\b(SUV|crossover|station wagon|carrinha|Touring|Avant|Estate|Station|Variant|Combi|Sportstourer|SW)\b","",q,flags=re.I))
    # Compact aliases after the above transformations.
    more=[]
    for x in out:
        more.append(re.sub(r"\b(\d{3})\s+(de|e)\b",r"\1\2",x,flags=re.I))
        more.append(x.replace("Mercedes-Benz","Mercedes"))
    return [clean(x) for x in dict.fromkeys(out+more) if clean(x)]


def _condition_from_detail(text, source):
    b=ascii_low(text)
    m=re.search(r"Condi[cç][aã]o\s*(?:\n|:)?\s*(Novo|Servi[cç]o|Usado|Seminovo|KM0)",text or "",re.I)
    if m:
        v=ascii_low(m.group(1))
        if "novo"==v:return "new_stock"
        if "servico" in v:return "demo_service"
        if "seminovo" in v or "km0" in v:return "km0"
        if "usado" in v:
            return "used_certified" if any(x in b for x in ("certified","premium selection","approved","selektion","selek")) else "used"
    return _condition(text,source)


def _detail_enrich(row, source, timeout=5):
    """Read dealer detail pages so results do not depend only on search snippets."""
    if source.get("key") not in {"carclasse","bmcar","santogal","caetano","mcoutinho","filinto"}:
        return row
    try:
        r=requests.get(row["url"],headers=HEADERS,timeout=timeout)
        r.raise_for_status()
        soup=BeautifulSoup(r.text,"html.parser")
        text=soup.get_text("\n",strip=True)
        h1=soup.find("h1")
        h2=soup.find("h2")
        title=clean(h1.get_text(" ",strip=True) if h1 else (h2.get_text(" ",strip=True) if h2 else row.get("title","")))
        if title and len(title)>5:
            row["title"]=title

        # Generic facts.
        km=_km(text)
        yr=_year(text)
        if km is not None: row["mileage_km"]=km
        if yr is not None: row["year"]=yr
        row["condition"]=_condition_from_detail(text,source)

        if source.get("key")=="carclasse":
            p=re.search(r"P\.V\.P\.\s*([\d\.\s]+)\s*(?:EUR|€)",text,re.I)
            newp=re.search(r"Pre[cç]o\s+em\s+novo\s*([\d\.\s]+)\s*(?:EUR|€)",text,re.I)
            current=float(re.sub(r"\D","",p.group(1))) if p else None
            listp=float(re.sub(r"\D","",newp.group(1))) if newp else None
            if current: row["price_eur"]=current
            if listp and current and listp>current:
                row["list_price_eur"]=listp
                row["discount_eur"]=round(listp-current,2)
                row["discount_pct"]=round((listp-current)/listp*100,1)

        elif source.get("key")=="bmcar":
            p=re.search(r"PVP:\s*([\d\.\s]+(?:,\d{2})?)\s*€",text,re.I)
            if p:
                raw=p.group(1).replace(" ","").replace(".","").replace(",",".")
                try: row["price_eur"]=float(raw)
                except Exception: pass
            row["dealer"]="BMcar"

        # Keep a useful concise snippet from the actual page.
        facts=[]
        if row.get("year"): facts.append(str(row["year"]))
        if row.get("mileage_km") is not None: facts.append(f'{row["mileage_km"]:,} km'.replace(",","."))
        if row.get("dealer"): facts.append(row["dealer"])
        if facts: row["snippet"]=" · ".join(facts)
        row["discovery"]="dealer_detail"
    except Exception:
        pass
    return row



def _sitemap_urls(source, timeout=7):
    """Read a public XML sitemap (including one-level sitemap indexes)."""
    domain=source["domain"]
    now=time.time()
    with _sitemap_lock:
        hit=_sitemap_cache.get(domain)
        if hit and now-hit[0]<SITEMAP_TTL:
            return hit[1]

    roots=[f"https://{domain}/sitemap.xml"]
    if not domain.startswith("www."):
        roots.append(f"https://www.{domain}/sitemap.xml")
    collected=[]
    children=[]
    for root in roots:
        try:
            r=requests.get(root,headers=HEADERS,timeout=timeout)
            if r.status_code>=400: continue
            soup=_xml_soup(r.text)
            locs=[clean(x.get_text(strip=True)) for x in soup.find_all("loc")]
            if not locs: continue
            if soup.find("sitemapindex"):
                children.extend(locs[:30])
            else:
                collected.extend(locs)
            if locs: break
        except Exception:
            continue

    # One-level child sitemap traversal. Cap protects beta latency.
    for child in children[:18]:
        try:
            r=requests.get(child,headers=HEADERS,timeout=timeout)
            if r.status_code>=400: continue
            soup=_xml_soup(r.text)
            collected.extend(clean(x.get_text(strip=True)) for x in soup.find_all("loc"))
        except Exception:
            continue

    collected=list(dict.fromkeys(u for u in collected if u.startswith("http")))
    with _sitemap_lock:
        _sitemap_cache[domain]=(now,collected)
    return collected


def _sitemap_candidates(q, source, limit=3, timeout=7):
    if source.get("key") not in {"bmcar","carclasse","santogal","caetano","mcoutinho","filinto"}:
        return []
    urls=_sitemap_urls(source,timeout=timeout)
    if not urls:return []
    aliases=_query_aliases(q)
    # Match meaningful query tokens against URL slugs; dealer vehicle URLs are
    # usually descriptive enough to identify model/engine without an external index.
    query_tokens=[]
    for alias in aliases:
        toks=[x for x in re.findall(r"[a-z0-9]+",ascii_low(alias)) if len(x)>=2 and x not in {
            "mercedes","benz","bmw","audi","volvo","porsche","serie","classe","suv",
            "touring","avant","estate","station","wagon","carrinha"
        }]
        query_tokens.append(toks)

    ranked=[]
    for url in urls:
        low=ascii_low(url)
        compact=re.sub(r"[^a-z0-9]","",low)
        best=0
        for toks in query_tokens:
            if not toks: continue
            hits=sum(1 for t in toks if t in low or re.sub(r"[^a-z0-9]","",t) in compact)
            best=max(best,hits/max(1,len(toks)))
        if best>=0.66:
            # Prefer known vehicle-detail paths over category/content pages.
            bonus=1 if any(p in low for p in ("/veiculos/","/stock-viaturas/","/viatura/","/carro/")) else 0
            ranked.append((best,bonus,url))
    ranked.sort(key=lambda x:(x[0],x[1]),reverse=True)
    return [(url,"","") for _,_,url in ranked[:limit]]

def _source_query(q, source, limit=3, timeout=8):
    domain=source["domain"]
    items=[]; error=""
    # Do NOT quote the whole vehicle string: dealer titles use different naming
    # conventions (330e vs Série 3 330e; GLC 300e vs GLC 300 e).
    for alias in _query_aliases(q)[:3]:
        sq=f"site:{domain} {alias}"
        urls=["https://www.bing.com/search?format=rss&cc=pt&setlang=pt-pt&q="+quote_plus(sq)]
        for idx,u in enumerate(urls):
            try:
                r=requests.get(u,headers=HEADERS,timeout=timeout)
                r.raise_for_status()
                if idx==0 and "<item" in r.text.lower():
                    soup=_xml_soup(r.text)
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
                if len(items)>=limit: break
            except Exception as e:
                error=str(e)[:120]
        if len(items)>=limit: break

    out=[]; seen=set()
    # Core terms ignore manufacturer filler/body terminology so that official
    # and dealer naming differences do not remove valid cars.
    qlow=ascii_low(q)
    core=[x for x in re.findall(r"[a-z0-9]+",qlow) if len(x)>=2 and x not in {
        "mercedes","benz","bmw","audi","volvo","porsche","serie","suv","touring","avant",
        "estate","station","wagon","carrinha","classe"
    }]
    for title,desc,link in items:
        if link in seen:continue
        seen.add(link)
        blob=title+" "+desc
        hay=ascii_low(blob+" "+link)
        hits=sum(1 for x in core if x in hay or re.sub(r"[^a-z0-9]","",x) in re.sub(r"[^a-z0-9]","",hay))
        need=1 if len(core)<=2 else max(1,len(core)-1)
        if core and hits<need:continue
        prices=_money_values(blob)
        current,list_price,disc_pct,conditional_price,price_condition=_discount(prices,blob)
        row={
            "source_key":source["key"],"source":source["name"],"official":source["official"],
            "title":title,"snippet":desc[:420],"url":link,
            "condition":_condition(blob,source),"availability":_availability(blob),
            "price_eur":current,"list_price_eur":list_price,
            "conditional_price_eur":conditional_price,"price_condition":price_condition,
            "discount_eur":round(list_price-(conditional_price or current),2) if list_price and (conditional_price or current) and list_price>(conditional_price or current) else None,
            "discount_pct":disc_pct,"mileage_km":_km(blob),"year":_year(blob),
            "dealer":_dealer(blob),"discovery":"public_index",
        }
        out.append(_detail_enrich(row,source,timeout=min(timeout,3)))
    return out,error

def _direct_specials(q):
    """Use the direct PoC connectors where the query matches their validated scope."""
    out=[]
    low=ascii_low(q)
    if ("mercedes" in low and "glc" in low and ("300 e" in low or "300e" in low)):
        try:
            from search_poc.connectors.carclasse import discover_glc_300e
            for v in discover_glc_300e(timeout=6):
                d=v.to_dict(); d.update({
                    "source_key":"carclasse","source":"Carclasse","official":True,
                    "title":"Mercedes-Benz GLC 300 e AMG Advanced 4Matic",
                    "snippet":f"{v.year or ''} · {v.mileage_km or 0:,} km · Carclasse".replace(",","."),
                    "dealer":"Carclasse","condition":v.condition,
                    "availability":"Em stock","discovery":"direct_connector"
                })
                out.append(d)
        except Exception:
            pass
        try:
            from search_poc.connectors.mercedes_certified import discover_glc_300e_suv
            for v in discover_glc_300e_suv(timeout=4):
                d=v.to_dict(); d.update({
                    "source_key":"mercedes_certified","source":"Mercedes-Benz Certified","official":True,
                    "title":"Mercedes-Benz GLC 300 e 4MATIC",
                    "snippet":f"{v.year or ''} · {v.mileage_km or 0:,} km · {v.dealer}".replace(",","."),
                    "condition":"used_certified","availability":"",
                    "discovery":"direct_connector"
                })
                out.append(d)
        except Exception:
            pass
    if "bmw" in low and "330" in low and "touring" in low:
        try:
            from search_poc.connectors.bmw_premium import fetch_bmw_330e_touring
            for v in fetch_bmw_330e_touring(timeout=9):
                d=v.to_dict(); d.update({"source_key":"bmw_premium","source":"BMW Premium Selection","official":True,"title":f"BMW Série 3 {v.variant} Touring","snippet":f"{v.year or ''} · {v.mileage_km or 0:,} km · {v.dealer}".replace(",","."),"dealer":v.dealer,"condition":"used_certified","availability":"","discovery":"direct_connector"})
                out.append(d)
        except Exception: pass
        try:
            from search_poc.connectors.bmcar import inventory_summary_bmw_330e_touring
            bm=inventory_summary_bmw_330e_touring(timeout=9)
            for v in bm["vehicles"]:
                d=v.to_dict(); d.update({
                    "source_key":"bmcar","source":"BMcar","official":True,
                    "title":f"BMW Série 3 {v.variant}",
                    "snippet":f"{v.year or ''} · {v.mileage_km or 0:,} km · BMcar".replace(",","."),
                    "condition":v.condition or "used","availability":"",
                    "discovery":"direct_connector",
                    "source_candidate_count":bm.get("candidate_count",0),
                    "source_exact_count":bm.get("exact_count",0),
                    "source_candidate_label":"Série 3 Touring híbridos no filtro BMcar",
                })
                out.append(d)
        except Exception: pass
        try:
            from search_poc.connectors.bmw_new_stock import caetano_330e_touring_stock
            for v in caetano_330e_touring_stock(timeout=9):
                d=v.to_dict(); d.update({"source_key":"bmw_caetano_new","source":"BMW / Caetano — novos em stock","official":True,"title":"BMW 330e Touring novo em stock","snippet":"Stock confirmado no portal oficial do concessionário; preço final sob proposta quando não publicado.","condition":"new_stock","dealer":"Caetano","discovery":"direct_connector"})
                out.append(d)
        except Exception: pass
    # Standvirtual is queried directly from its public server-rendered model page.
    # This is deliberately a benchmark source, not the canonical source of truth.
    try:
        from search_poc.connectors.standvirtual import discover_rows
        out.extend(discover_rows(q,limit=40,timeout=8))
    except Exception:
        pass
    return out


def _identity_codes_from_row(row):
    text=ascii_low((row.get("title") or "")+" "+(row.get("snippet") or ""))
    text=re.sub(r"\b(\d{3})\s+(de|e|d|i)\b",r"\1\2",text)
    codes=set(re.findall(r"\b(?:xdrive|sdrive)\s*\d{2}[a-z0-9]*\b",text))
    codes.update(re.findall(r"\b\d{3}(?:de|e|d|i)\b",text))
    codes.update(re.findall(r"\b(?:ix\d|x\d|glc|gle|gla|glb|eqa|eqb|eqe|eqs|a[1-8]|q[2-8]|xc\d{2}|ex\d{2}|ec\d{2}|v\d{2}|911|718)\b",text))
    return {x.replace(" ","") for x in codes}


def _norm_dealer(value):
    return re.sub(r"[^a-z0-9]+"," ",ascii_low(value or "")).strip()


def _same_dealer(a,b):
    da,db=_norm_dealer(a.get("dealer")), _norm_dealer(b.get("dealer"))
    if not da or not db:
        return None
    return da==db or da in db or db in da


def _same_vehicle(a,b):
    # Never collapse separate rows from the same feed.
    if a.get("source_key")==b.get("source_key"):
        return False

    # Strong identifiers, when connectors expose them.
    av=(a.get("vin") or "").strip().upper(); bv=(b.get("vin") or "").strip().upper()
    if av and bv:
        return av==bv
    ar=(a.get("stock_ref") or "").strip().lower(); br=(b.get("stock_ref") or "").strip().lower()
    if ar and br and ar==br:
        return True

    if a.get("year") is not None and b.get("year") is not None and a.get("year")!=b.get("year"):
        return False

    ca,cb=_identity_codes_from_row(a),_identity_codes_from_row(b)
    if ca and cb and not (ca & cb):
        return False

    dealer_same=_same_dealer(a,b)
    if dealer_same is False:
        return False

    if a.get("mileage_km") is None or b.get("mileage_km") is None:
        return False
    km_delta=abs(int(a["mileage_km"])-int(b["mileage_km"]))

    if a.get("price_eur") is None or b.get("price_eur") is None:
        return False
    pa,pb=float(a["price_eur"]),float(b["price_eur"])
    price_delta=abs(pa-pb)
    price_ratio=price_delta/max(pa,pb) if max(pa,pb)>0 else 1

    # Known same seller + near-identical odometer tolerates campaign price drift.
    if dealer_same is True and km_delta<=100 and price_ratio<=0.18 and (ca & cb):
        return True

    # If one source omits seller identity, only merge near-exact public facts.
    if dealer_same is None and km_delta<=75 and price_delta<=300 and (ca & cb):
        return True
    return False


_DEALER_SOURCE_KEYS={"bmcar","carclasse","santogal","caetano","mcoutinho","filinto"}


def _source_priority(row):
    key=row.get("source_key") or ""
    if key in _DEALER_SOURCE_KEYS:
        return 30 + (5 if row.get("discovery") in {"direct_connector","dealer_detail"} else 0)
    if row.get("official"):
        return 20 + (3 if row.get("discovery")=="direct_connector" else 0)
    if key=="standvirtual":
        return 10
    return 5


def _occurrence(row):
    return {
        "source_key":row.get("source_key"),"source":row.get("source"),
        "url":row.get("url"),"price_eur":row.get("price_eur"),
        "conditional_price_eur":row.get("conditional_price_eur"),
        "list_price_eur":row.get("list_price_eur"),"price_condition":row.get("price_condition"),
        "mileage_km":row.get("mileage_km"),"year":row.get("year"),
        "dealer":row.get("dealer"),"discovery":row.get("discovery"),
    }


def _rebuild_occurrence_links(row):
    occ=row.get("occurrences") or []
    primary_source=row.get("source")
    row["also_at"]=list(dict.fromkeys(x.get("source") for x in occ if x.get("source") and x.get("source")!=primary_source))
    row["alternate_links"]=[
        {"source":x.get("source"),"url":x.get("url")}
        for x in occ if x.get("url") and x.get("url")!=row.get("url")
    ]


def _dedup(rows):
    out=[]; seen_urls=set()
    for incoming in rows:
        r=dict(incoming)
        u=r.get("url") or ""
        if u and u in seen_urls:
            continue
        r.setdefault("occurrences",[_occurrence(r)])
        merged=False
        for ex in out:
            if not _same_vehicle(ex,r):
                continue
            occurrences=list(ex.get("occurrences") or [_occurrence(ex)])
            new_occ=_occurrence(r)
            if not any(x.get("source_key")==new_occ.get("source_key") and x.get("url")==new_occ.get("url") for x in occurrences):
                occurrences.append(new_occ)

            if _source_priority(r)>_source_priority(ex):
                keep_occ=occurrences
                ex.clear(); ex.update(r)
                ex["occurrences"]=keep_occ
            else:
                ex["occurrences"]=occurrences
                for k in ("availability","dealer","conditional_price_eur","price_condition"):
                    if not ex.get(k) and r.get(k):
                        ex[k]=r[k]
            _rebuild_occurrence_links(ex)
            merged=True
            break
        if merged:
            if u: seen_urls.add(u)
            continue
        if u: seen_urls.add(u)
        _rebuild_occurrence_links(r)
        out.append(r)
    return out

def search_all(q, condition="all", max_per_source=3):
    q=clean(q)
    if not q:return {"query":"","results":[],"sources":[],"summary":{"total":0}}
    cache_key=(ascii_low(q),condition,max_per_source)
    now=time.time()
    with _cache_lock:
        hit=_cache.get(cache_key)
        if hit and now-hit[0]<CACHE_TTL:return hit[1]

    direct_results=_direct_specials(q)
    results=list(direct_results)
    statuses=[]
    selected_sources=_relevant_sources(q)
    with ThreadPoolExecutor(max_workers=min(12,max(1,len(selected_sources)))) as ex:
        jobs={ex.submit(_source_query,q,s,max_per_source,4):s for s in selected_sources}
        for fut in as_completed(jobs):
            s=jobs[fut]
            try:
                rows,err=fut.result()
                results.extend(rows)
                statuses.append({"key":s["key"],"name":s["name"],"count":len(rows),"status":"ok" if rows else ("error" if err else "empty"),"error":err})
            except Exception as e:
                statuses.append({"key":s["key"],"name":s["name"],"count":0,"status":"error","error":str(e)[:120]})

    # Direct connectors are authoritative for their current scope. Reflect their
    # hits in the source panel even if the generic public-index discovery was empty.
    direct_counts={}
    direct_meta={}
    for row in direct_results:
        key=row.get("source_key")
        if key:
            direct_counts[key]=direct_counts.get(key,0)+1
            cand=row.get("source_candidate_count")
            if cand is not None:
                direct_meta[key]={
                    "candidate_count":int(cand or 0),
                    "exact_count":int(row.get("source_exact_count") or 0),
                    "candidate_label":row.get("source_candidate_label") or "",
                }
    by_key={s["key"]:s for s in statuses}
    for key,count in direct_counts.items():
        meta=direct_meta.get(key,{})
        if key in by_key:
            by_key[key]["count"]=max(int(by_key[key].get("count") or 0),count)
            by_key[key]["status"]="ok"
            by_key[key]["error"]=""
            by_key[key].update(meta)
        else:
            src=next((x for x in selected_sources if x["key"]==key),None)
            row={"key":key,"name":src["name"] if src else key,"count":count,"status":"ok","error":""}
            row.update(meta)
            statuses.append(row)

    valid_results=[]
    rejected_by_source={}
    for row in results:
        if query_matches_row(q,row):
            valid_results.append(row)
        else:
            key=row.get("source_key") or "unknown"
            rejected_by_source[key]=rejected_by_source.get(key,0)+1
    results=valid_results
    for st in statuses:
        rejected=rejected_by_source.get(st.get("key"),0)
        if rejected:
            st["rejected_irrelevant"]=rejected

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
        "sources_checked":len(selected_sources),
        "catalog_sources":len(SOURCES),
        "rejected_irrelevant":sum(rejected_by_source.values()),
    }
    payload={"query":q,"condition":condition,"results":results,"sources":sorted(statuses,key=lambda x:(-x["count"],x["name"])),"summary":summary,"beta_note":f"Beta nacional: {len(SOURCES)} fontes no catálogo; {len(selected_sources)} relevantes consultadas nesta pesquisa. Conetores diretos + descoberta pública indexada; um resultado vazio não prova ausência de stock na fonte."}
    with _cache_lock:_cache[cache_key]=(now,payload)
    return payload
