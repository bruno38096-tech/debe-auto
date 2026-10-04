import re
import unicodedata

_BODY_GROUPS = {
    "station": {"touring", "carrinha", "station", "wagon", "estate", "avant", "variant", "combi", "sportstourer", "sw"},
    "suv": {"suv", "crossover"},
    "sedan": {"sedan", "berlina", "limousine"},
    "coupe": {"coupe"},
}
_BRANDS = {"bmw","mercedes","benz","audi","volvo","porsche","volkswagen","vw","seat","cupra","skoda","toyota","lexus","ford","hyundai","kia","nissan","renault","peugeot","citroen","opel"}
_STOP = _BRANDS | {"serie","series","classe","class","auto","automatico","automatica","pack","desportivo","m","pro","usado","usados","novo","nova"}


def _ascii(s):
    return unicodedata.normalize("NFKD", s or "").encode("ascii","ignore").decode().lower()


def _compact(s):
    s=_ascii(s)
    s=re.sub(r"\b(\d{3})\s+(de|e|d|i)\b", r"\1\2", s)
    s=re.sub(r"\b([xs])drive\s+(\d{2}[a-z0-9]+)\b", r"\1drive\2", s)
    return re.sub(r"[^a-z0-9]+"," ",s).strip()


def identity_codes(text):
    t=_compact(text)
    codes=set()
    codes.update(re.findall(r"\b(?:xdrive|sdrive)\d{2}[a-z0-9]*\b",t))
    codes.update(re.findall(r"\b\d{3}(?:de|e|d|i)\b",t))
    codes.update(re.findall(r"\b(?:ix\d|x\d|glc|gle|gla|glb|eqa|eqb|eqe|eqs|a[1-8]|q[2-8]|xc\d{2}|ex\d{2}|ec\d{2}|v\d{2}|911|718)\b",t))
    return codes


def _code_family(code):
    if code.startswith(("xdrive","sdrive")):
        return "drive"
    if re.fullmatch(r"\d{3}(?:de|e|d|i)",code):
        return "engine"
    return "model"


def _body_group(text):
    toks=set(_compact(text).split())
    found=set()
    for group,words in _BODY_GROUPS.items():
        if toks & words:
            found.add(group)
    return found


def query_matches_text(query, title="", snippet=""):
    """Reject explicit model/variant conflicts before dedup and scoring."""
    q=_compact(query)
    c=_compact((title or "")+" "+(snippet or ""))
    qcodes=identity_codes(q)
    ccodes=identity_codes(c)

    for expected in qcodes:
        fam=_code_family(expected)
        peers={x for x in ccodes if _code_family(x)==fam}
        if peers and expected not in peers:
            return False

    for expected in qcodes:
        if _code_family(expected) in {"drive","engine"} and expected not in ccodes:
            return False

    qmodels={x for x in qcodes if _code_family(x)=="model"}
    if qmodels and not (qmodels & ccodes):
        return False

    qb=_body_group(q)
    cb=_body_group(c)
    if qb and cb and not (qb & cb):
        return False

    if not qcodes:
        qt={x for x in q.split() if len(x)>=2 and x not in _STOP}
        ct=set(c.split())
        if qt and len(qt & ct)<min(2,len(qt)):
            return False
    return True


def query_matches_row(query,row):
    return query_matches_text(query,row.get("title",""),row.get("snippet",""))
