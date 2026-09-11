"""Search resilience for DEBE.

DEBE queries DuckDuckGo HTML. Cloud IPs can receive empty/blocked SERPs, so
this layer transparently retries via Bing, Yahoo and Jina while returning the
same HTML shape that app.py already parses.
"""

import html
import re
from urllib.parse import parse_qs, quote_plus, urlparse

import requests
from bs4 import BeautifulSoup

_EXISTING_GET = requests.get
_ORIGINAL_GET = getattr(_EXISTING_GET, '_debe_original_get', _EXISTING_GET)


class _SyntheticResponse:
    def __init__(self, text, status_code=200, url=''):
        self.text = text
        self.status_code = status_code
        self.url = url
        self.headers = {'content-type': 'text/html; charset=utf-8'}

    def raise_for_status(self):
        if self.status_code >= 400:
            raise requests.HTTPError(f'HTTP {self.status_code}', response=self)


def _clean(text):
    text = re.sub(r'!\[[^\]]*\]\([^)]*\)', ' ', text or '')
    text = re.sub(r'\[([^\]]+)\]\([^)]*\)', r'\1', text)
    text = re.sub(r'[`*_#>|]+', ' ', text)
    return re.sub(r'\s+', ' ', text).strip()


def _to_duck_html(results):
    blocks = []
    for title, url, snippet in results:
        blocks.append(
            '<div class="result">'
            f'<a class="result__a" href="{html.escape(url, quote=True)}">{html.escape(title)}</a>'
            f'<div class="result__snippet">{html.escape(snippet)}</div>'
            '</div>'
        )
    return '<html><body>' + ''.join(blocks) + '</body></html>'


def _bing_serp(query, headers=None, timeout=None, limit=16):
    try:
        url = 'https://www.bing.com/search?q=' + quote_plus(query) + '&count=20&setlang=en'
        r = _ORIGINAL_GET(url, headers=headers or {'User-Agent': 'Mozilla/5.0'}, timeout=timeout or (4, 12))
        if r.status_code != 200 or not r.text:
            return None
        soup = BeautifulSoup(r.text, 'html.parser')
        out, seen = [], set()
        for item in soup.select('li.b_algo'):
            a = item.select_one('h2 a')
            if not a or not a.get('href'):
                continue
            target = a.get('href').strip()
            if not target.startswith('http') or target in seen:
                continue
            seen.add(target)
            title = _clean(a.get_text(' ', strip=True))
            sn = item.select_one('.b_caption p') or item.select_one('p')
            snippet = _clean(sn.get_text(' ', strip=True) if sn else '')
            if title:
                out.append((title, target, snippet))
            if len(out) >= limit:
                break
        return _SyntheticResponse(_to_duck_html(out), 200, url) if out else None
    except Exception:
        return None


def _yahoo_serp(query, headers=None, timeout=None, limit=16):
    try:
        url = 'https://search.yahoo.com/search?p=' + quote_plus(query)
        r = _ORIGINAL_GET(url, headers=headers or {'User-Agent': 'Mozilla/5.0'}, timeout=timeout or (4, 12))
        if r.status_code != 200 or not r.text:
            return None
        soup = BeautifulSoup(r.text, 'html.parser')
        out, seen = [], set()
        for item in soup.select('#web ol li, .algo'):
            a = item.select_one('h3 a') or item.select_one('a')
            if not a or not a.get('href'):
                continue
            target = a.get('href').strip()
            if not target.startswith('http') or target in seen:
                continue
            seen.add(target)
            title = _clean(a.get_text(' ', strip=True))
            p = item.select_one('p')
            snippet = _clean(p.get_text(' ', strip=True) if p else '')
            if title:
                out.append((title, target, snippet))
            if len(out) >= limit:
                break
        return _SyntheticResponse(_to_duck_html(out), 200, url) if out else None
    except Exception:
        return None


def _jina_links(markdown, limit=16):
    out, seen = [], set()
    pattern = re.compile(r'\[([^\]\n]{3,220})\]\((https?://[^)\s]+)\)', re.I)
    for match in pattern.finditer(markdown or ''):
        title = _clean(match.group(1))
        target = html.unescape(match.group(2)).strip()
        host = urlparse(target).netloc.lower()
        if not title or not host:
            continue
        if any(x in host for x in ('google.', 'bing.com', 'yahoo.com', 'jina.ai', 'microsoft.com', 'gstatic.com')):
            continue
        if target in seen:
            continue
        seen.add(target)
        snippet = _clean(markdown[match.end():match.end() + 700])[:500]
        out.append((title, target, snippet))
        if len(out) >= limit:
            break
    return out


def _jina_serp(query, headers=None, timeout=None):
    for target in [
        'https://r.jina.ai/https://www.bing.com/search?q=' + quote_plus(query),
        'https://r.jina.ai/https://www.google.com/search?q=' + quote_plus(query) + '&num=10&hl=en',
    ]:
        try:
            r = _ORIGINAL_GET(target, headers=headers or {'User-Agent': 'Mozilla/5.0'}, timeout=timeout or (4, 16))
            if r.status_code != 200 or not r.text:
                continue
            results = _jina_links(r.text)
            if results:
                return _SyntheticResponse(_to_duck_html(results), 200, target)
        except Exception:
            continue
    return None


def _resilient_get(url, *args, **kwargs):
    host = urlparse(str(url)).netloc.lower()
    if host != 'html.duckduckgo.com':
        return _ORIGINAL_GET(url, *args, **kwargs)

    direct = None
    try:
        direct = _ORIGINAL_GET(url, *args, **kwargs)
        if direct.status_code == 200 and 'result__a' in (direct.text or ''):
            return direct
    except Exception:
        pass

    try:
        query = parse_qs(urlparse(str(url)).query).get('q', [''])[0]
    except Exception:
        query = ''

    if query:
        headers, timeout = kwargs.get('headers'), kwargs.get('timeout')
        for provider in (_bing_serp, _yahoo_serp, _jina_serp):
            fallback = provider(query, headers=headers, timeout=timeout)
            if fallback is not None and 'result__a' in fallback.text:
                return fallback

    if direct is not None:
        return direct
    return _ORIGINAL_GET(url, *args, **kwargs)


_resilient_get._debe_search_resilience = True
_resilient_get._debe_original_get = _ORIGINAL_GET
requests.get = _resilient_get
