"""Runtime search resilience for DEBE.

Python imports sitecustomize automatically on startup.  We keep the application
code focused on DEBE logic while making requests to DuckDuckGo resilient: if
DuckDuckGo returns no usable results (common from cloud IPs), the request is
fulfilled through a Google/Bing SERP read by Jina Reader, which DEBE already
uses successfully for marketplace pages.

Only DuckDuckGo search requests are intercepted. All other HTTP traffic is
untouched.
"""

import html
import re
from urllib.parse import parse_qs, quote_plus, urlparse

import requests

_ORIGINAL_GET = requests.get


class _SyntheticResponse:
    def __init__(self, text, status_code=200, url=''):
        self.text = text
        self.status_code = status_code
        self.url = url
        self.headers = {'content-type': 'text/html; charset=utf-8'}

    def raise_for_status(self):
        if self.status_code >= 400:
            raise requests.HTTPError(f'HTTP {self.status_code}', response=self)


def _clean_markdown(text):
    text = re.sub(r'!\[[^\]]*\]\([^)]*\)', ' ', text or '')
    text = re.sub(r'\[([^\]]+)\]\([^)]*\)', r'\1', text)
    text = re.sub(r'[`*_#>|]+', ' ', text)
    text = re.sub(r'\s+', ' ', text)
    return text.strip()


def _serp_links(markdown, limit=16):
    """Extract useful result links from a Jina-rendered Google/Bing SERP."""
    out = []
    seen = set()
    pattern = re.compile(r'\[([^\]\n]{3,220})\]\((https?://[^)\s]+)\)', re.I)
    for match in pattern.finditer(markdown or ''):
        title = _clean_markdown(match.group(1))
        url = html.unescape(match.group(2)).strip()
        host = urlparse(url).netloc.lower()
        if not title or not host:
            continue
        if any(x in host for x in (
            'google.', 'bing.com', 'microsoft.com', 'jina.ai',
            'gstatic.com', 'googleusercontent.com', 'accounts.google'
        )):
            continue
        if url in seen:
            continue
        seen.add(url)
        # Text immediately after a result link generally contains the SERP
        # description and/or beginning of the page content returned by Jina.
        tail = markdown[match.end():match.end() + 900]
        snippet = _clean_markdown(tail)[:650]
        out.append((title, url, snippet))
        if len(out) >= limit:
            break
    return out


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


def _jina_serp(query, headers=None, timeout=None):
    # Reader itself allows anonymous requests; wrapping the SERP avoids the
    # cloud-IP blocking we see on direct search-engine HTML endpoints.
    targets = [
        'https://r.jina.ai/https://www.bing.com/search?q=' + quote_plus(query),
        'https://r.jina.ai/https://www.google.com/search?q=' + quote_plus(query) + '&num=10&hl=en',
    ]
    for target in targets:
        try:
            r = _ORIGINAL_GET(
                target,
                headers=headers or {'User-Agent': 'Mozilla/5.0'},
                timeout=timeout or (4, 16),
            )
            if r.status_code != 200 or not r.text:
                continue
            results = _serp_links(r.text)
            if results:
                return _SyntheticResponse(_to_duck_html(results), 200, target)
        except Exception:
            continue
    return None


def _resilient_get(url, *args, **kwargs):
    host = urlparse(str(url)).netloc.lower()
    if host != 'html.duckduckgo.com':
        return _ORIGINAL_GET(url, *args, **kwargs)

    # First keep the normal provider when it is healthy.
    try:
        direct = _ORIGINAL_GET(url, *args, **kwargs)
        if direct.status_code == 200 and 'result__a' in (direct.text or ''):
            return direct
    except Exception:
        direct = None

    try:
        query = parse_qs(urlparse(str(url)).query).get('q', [''])[0]
    except Exception:
        query = ''
    if query:
        fallback = _jina_serp(
            query,
            headers=kwargs.get('headers'),
            timeout=kwargs.get('timeout'),
        )
        if fallback is not None:
            return fallback

    # Preserve the original error/response semantics if every fallback fails.
    if direct is not None:
        return direct
    return _ORIGINAL_GET(url, *args, **kwargs)


requests.get = _resilient_get
