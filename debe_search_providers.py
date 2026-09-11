"""Cloud-friendly web discovery for DEBE.
Uses multiple public search surfaces because normal SERP HTML is often blocked
for cloud IP addresses. No vehicle-specific knowledge is hardcoded here.
"""
from urllib.parse import quote_plus, urlparse
import html
import re
import requests
from bs4 import BeautifulSoup

HEADERS={
    'User-Agent':'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 Chrome/124 Safari/537.36',
    'Accept-Language':'en-US,en;q=0.9,pt;q=0.8'
}
S=requests.Session()

def clean(s):
    return re.sub(r'\s+',' ',html.unescape(s or '')).strip()

def dedup(rows,n=12):
    out=[];seen=set()
    blocked=('bing.com','brave.com','mojeek.com','google.','duckduckgo.com','jina.ai')
    for r in rows:
        u=clean(r.get('url',''))
        if not u.startswith('http') or u in seen: continue
        host=urlparse(u).netloc.lower()
        if any(x in host for x in blocked): continue
        seen.add(u);out.append(r)
        if len(out)>=n: break
    return out

def bing_rss(q,n=10):
    urls=[
        'https://www.bing.com/search?format=rss&q='+quote_plus(q),
        'https://r.jina.ai/https://www.bing.com/search?format=rss&q='+quote_plus(q),
    ]
    for i,u in enumerate(urls):
        try:
            r=S.get(u,headers=HEADERS,timeout=(2,7));r.raise_for_status();out=[]
            if i==0 and '<item>' in r.text.lower():
                s=BeautifulSoup(r.text,'xml')
                for item in s.find_all('item'):
                    title=clean(item.title.get_text(' ',strip=True) if item.title else '')
                    link=clean(item.link.get_text(strip=True) if item.link else '')
                    desc=clean(BeautifulSoup(item.description.get_text(' ',strip=True) if item.description else '','html.parser').get_text(' ',strip=True))
                    if link.startswith('http'): out.append({'title':title,'snippet':desc,'url':link})
                    if len(out)>=n: break
            else:
                # Jina turns feed/search links into Markdown links.
                pat=re.compile(r'\[([^\]\n]{3,220})\]\((https?://[^)\s]+)\)',re.I)
                for m in pat.finditer(r.text or ''):
                    link=html.unescape(m.group(2));host=urlparse(link).netloc.lower()
                    if 'bing.com' in host or 'jina.ai' in host: continue
                    tail=(r.text or '')[m.end():m.end()+500]
                    out.append({'title':clean(m.group(1)),'snippet':clean(re.sub(r'[`*_#>|]+',' ',tail))[:420],'url':link})
                    if len(out)>=n: break
            out=dedup(out,n)
            if out:return out
        except Exception:
            pass
    return []

def reddit(q,n=8):
    try:
        u='https://www.reddit.com/search.json?q='+quote_plus(q)+'&limit='+str(n)+'&sort=relevance&t=all&raw_json=1'
        r=S.get(u,headers={**HEADERS,'User-Agent':'DEBE-Auto/0.1 public-research'},timeout=(2,7));r.raise_for_status();data=r.json();out=[]
        for child in data.get('data',{}).get('children',[]):
            d=child.get('data',{})
            title=clean(d.get('title',''));body=clean(d.get('selftext',''))[:500]
            link='https://www.reddit.com'+d.get('permalink','') if d.get('permalink') else d.get('url_overridden_by_dest','')
            if title and str(link).startswith('http'):out.append({'title':title,'snippet':body,'url':link})
        return dedup(out,n)
    except Exception:
        return []

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
    except Exception:
        return []

def brave(q,n=8):
    try:
        r=S.get('https://search.brave.com/search?q='+quote_plus(q)+'&source=web',headers=HEADERS,timeout=(2,7));r.raise_for_status();s=BeautifulSoup(r.text,'html.parser');out=[]
        for a in s.select('a[href^="http"]'):
            u=a.get('href','');title=clean(a.get_text(' ',strip=True));host=urlparse(u).netloc.lower()
            if len(title)<8 or 'brave.com' in host:continue
            parent=a.find_parent(['div','article','li'])
            snippet=clean(parent.get_text(' ',strip=True) if parent else '')[:500]
            out.append({'title':title,'snippet':snippet,'url':u})
            if len(out)>=n*2:break
        return dedup(out,n)
    except Exception:
        return []

def make_search(original_search=None):
    def search_web(q,n=10):
        rows=[];counts={}
        for name,fn in [('bing_rss',bing_rss),('reddit',reddit),('mojeek',mojeek),('brave',brave)]:
            if len(dedup(rows,n))>=max(5,min(n,7)):break
            got=fn(q,n);counts[name]=len(got);rows.extend(got)
        if len(dedup(rows,n))<4 and original_search:
            try:
                got=original_search(q,n);counts['legacy']=len(got);rows.extend(got)
            except Exception:
                counts['legacy']=0
        final=dedup(rows,n)
        print('DEBE search:',clean(q)[:90],'providers=',counts,'final=',len(final),flush=True)
        return final
    return search_web
