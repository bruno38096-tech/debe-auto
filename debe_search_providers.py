"""Cloud-friendly web discovery for DEBE.
Uses multiple public search surfaces because normal SERP HTML is often blocked
for cloud IP addresses. No vehicle-specific knowledge is hardcoded here.
"""
from urllib.parse import quote_plus, urlparse
import html,re,requests,unicodedata
from bs4 import BeautifulSoup

HEADERS={'User-Agent':'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 Chrome/124 Safari/537.36','Accept-Language':'en-GB,en;q=0.9,pt;q=0.8'}
S=requests.Session()
def clean(s): return re.sub(r'\s+',' ',html.unescape(s or '')).strip()
def alow(s): return unicodedata.normalize('NFKD',s or '').encode('ascii','ignore').decode().lower()

def dedup(rows,n=12):
    out=[];seen=set();blocked=('bing.com','brave.com','mojeek.com','google.','duckduckgo.com','jina.ai')
    for r in rows:
        u=clean(r.get('url',''))
        if not u.startswith('http') or u in seen: continue
        host=urlparse(u).netloc.lower()
        if any(x in host for x in blocked): continue
        seen.add(u);out.append(r)
        if len(out)>=n: break
    return out

def markdown_links(text,n=10,blocked_hosts=()):
    out=[];pat=re.compile(r'\[([^\]\n]{3,240})\]\((https?://[^)\s]+)\)',re.I)
    for m in pat.finditer(text or ''):
        u=html.unescape(m.group(2));host=urlparse(u).netloc.lower();title=clean(re.sub(r'[`*_#>|]+',' ',m.group(1)))
        if not title or any(x in host for x in blocked_hosts): continue
        tail=(text or '')[m.end():m.end()+700];snippet=clean(re.sub(r'[`*_#>|]+',' ',tail))[:500]
        out.append({'title':title,'snippet':snippet,'url':u})
        if len(out)>=n*2: break
    return dedup(out,n)

def bing_rss(q,n=10):
    urls=['https://www.bing.com/search?format=rss&setlang=en-gb&cc=gb&q='+quote_plus(q),'https://r.jina.ai/https://www.bing.com/search?format=rss&setlang=en-gb&cc=gb&q='+quote_plus(q)]
    for i,u in enumerate(urls):
        try:
            r=S.get(u,headers=HEADERS,timeout=(2,7));r.raise_for_status();out=[]
            if i==0 and '<item>' in r.text.lower():
                s=BeautifulSoup(r.text,'xml')
                for item in s.find_all('item'):
                    title=clean(item.title.get_text(' ',strip=True) if item.title else '');link=clean(item.link.get_text(strip=True) if item.link else '')
                    desc=clean(BeautifulSoup(item.description.get_text(' ',strip=True) if item.description else '','html.parser').get_text(' ',strip=True))
                    if link.startswith('http'): out.append({'title':title,'snippet':desc,'url':link})
                    if len(out)>=n: break
                out=dedup(out,n)
            else: out=markdown_links(r.text,n,('bing.com','jina.ai'))
            if out:return out
        except Exception: pass
    return []

def brave_jina(q,n=10):
    try:
        target='https://r.jina.ai/https://search.brave.com/search?q='+quote_plus(q)+'&source=web'
        r=S.get(target,headers=HEADERS,timeout=(3,10));r.raise_for_status()
        return markdown_links(r.text,n,('brave.com','jina.ai'))
    except Exception:return []

def reddit(q,n=8):
    try:
        u='https://www.reddit.com/search.json?q='+quote_plus(q)+'&limit='+str(n)+'&sort=relevance&t=all&raw_json=1'
        r=S.get(u,headers={**HEADERS,'User-Agent':'DEBE-Auto/0.1 public-research'},timeout=(2,7));r.raise_for_status();data=r.json();out=[]
        for child in data.get('data',{}).get('children',[]):
            d=child.get('data',{});title=clean(d.get('title',''));body=clean(d.get('selftext',''))[:500]
            link='https://www.reddit.com'+d.get('permalink','') if d.get('permalink') else d.get('url_overridden_by_dest','')
            if title and str(link).startswith('http'):out.append({'title':title,'snippet':body,'url':link})
        return dedup(out,n)
    except Exception:return []

def mojeek(q,n=8):
    try:
        r=S.get('https://www.mojeek.com/search?q='+quote_plus(q),headers=HEADERS,timeout=(2,7));r.raise_for_status();s=BeautifulSoup(r.text,'html.parser');out=[]
        for li in s.select('ul.results-standard li, .results-standard li, li.result'):
            a=li.select_one('a.title') or li.select_one('h2 a') or li.select_one('a[href^="http"]')
            if not a: continue
            u=a.get('href','');p=li.select_one('.s') or li.select_one('p')
            if u.startswith('http'):out.append({'title':clean(a.get_text(' ',strip=True)),'snippet':clean(p.get_text(' ',strip=True) if p else ''),'url':u})
            if len(out)>=n:break
        return dedup(out,n)
    except Exception:return []

def brave(q,n=8):
    try:
        r=S.get('https://search.brave.com/search?q='+quote_plus(q)+'&source=web',headers=HEADERS,timeout=(2,7));r.raise_for_status();s=BeautifulSoup(r.text,'html.parser');out=[]
        for a in s.select('a[href^="http"]'):
            u=a.get('href','');title=clean(a.get_text(' ',strip=True));host=urlparse(u).netloc.lower()
            if len(title)<8 or 'brave.com' in host:continue
            parent=a.find_parent(['div','article','li']);snippet=clean(parent.get_text(' ',strip=True) if parent else '')[:500]
            out.append({'title':title,'snippet':snippet,'url':u})
            if len(out)>=n*2:break
        return dedup(out,n)
    except Exception:return []

# Search providers occasionally return unrelated popular pages while still
# reporting a full result set. Require the quoted identity (e.g. "Audi A5" or
# "2.0 TDI") to be present before those rows can stop the fallback chain.
def _identity_terms(q):
    quoted=re.findall(r'"([^"]{2,80})"',q or '')
    phrase=quoted[0] if quoted else ''
    toks=[x for x in re.findall(r'[a-z0-9]+',alow(phrase)) if len(x)>=2]
    return toks

def _relevant_rows(rows,q,n):
    terms=_identity_terms(q)
    if not terms:return dedup(rows,n)
    out=[]
    for r in rows:
        blob=alow((r.get('title') or '')+' '+(r.get('snippet') or '')+' '+(r.get('url') or ''))
        compact=re.sub(r'[^a-z0-9]+','',blob)
        hits=0
        for term in terms:
            if term in blob or term in compact:hits+=1
        # Two-token identities should match both. Longer identities may miss a
        # trim/variant, so all but one is enough.
        need=len(terms) if len(terms)<=2 else len(terms)-1
        if hits>=need:out.append(r)
    return dedup(out,n)

def make_search(original_search=None):
    def search_web(q,n=10):
        rows=[];counts={};relevant_counts={}
        providers=[('bing_rss',bing_rss),('brave_jina',brave_jina),('brave',brave),('reddit',reddit),('mojeek',mojeek)]
        for name,fn in providers:
            current=_relevant_rows(rows,q,n)
            if len(current)>=max(6,min(n,8)):break
            got=fn(q,n);counts[name]=len(got)
            good=_relevant_rows(got,q,n);relevant_counts[name]=len(good)
            rows.extend(good)
        current=_relevant_rows(rows,q,n)
        if len(current)<4 and original_search:
            try:
                got=original_search(q,n);counts['legacy']=len(got)
                good=_relevant_rows(got,q,n);relevant_counts['legacy']=len(good);rows.extend(good)
            except Exception:counts['legacy']=0;relevant_counts['legacy']=0
        final=_relevant_rows(rows,q,n)
        print('DEBE search:',clean(q)[:90],'providers=',counts,'relevant=',relevant_counts,'final=',len(final),flush=True)
        return final
    return search_web
