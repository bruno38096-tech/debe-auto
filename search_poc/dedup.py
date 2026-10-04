from dataclasses import dataclass
import re
import unicodedata


@dataclass
class Match:
    left_source: str
    left_id: str
    right_source: str
    right_id: str
    confidence: float
    reasons: list


def _norm(value):
    value=unicodedata.normalize("NFKD", value or "").encode("ascii","ignore").decode().lower()
    return re.sub(r"[^a-z0-9]+"," ",value).strip()


def _identity_codes(v):
    text=_norm(" ".join([getattr(v,"model","") or "", getattr(v,"variant","") or ""]))
    text=re.sub(r"\b(\d{3})\s+(de|e|d|i)\b",r"\1\2",text)
    codes=set(re.findall(r"\b(?:xdrive|sdrive)\s*\d{2}[a-z0-9]*\b",text))
    codes.update(re.findall(r"\b\d{3}(?:de|e|d|i)\b",text))
    codes.update(re.findall(r"\b(?:ix\d|x\d|glc|gle|gla|glb|eqa|eqb|eqe|eqs|a[1-8]|q[2-8]|xc\d{2}|ex\d{2}|ec\d{2}|v\d{2}|911|718)\b",text))
    return {x.replace(" ","") for x in codes}


def _dealer_equal(a,b):
    na,nb=_norm(a),_norm(b)
    if not na or not nb:
        return None
    return na==nb or na in nb or nb in na


def match_vehicle(a, b):
    reasons=[]
    avin=_norm(getattr(a,"vin","")); bvin=_norm(getattr(b,"vin",""))
    if avin and bvin:
        return (1.0,["vin"]) if avin==bvin else (0.0,["vin_conflict"])

    aref=_norm(getattr(a,"stock_ref","")); bref=_norm(getattr(b,"stock_ref",""))
    if aref and bref and aref==bref and _norm(a.make)==_norm(b.make):
        return 0.99,["stock_ref"]

    if _norm(a.make)!=_norm(b.make):
        return 0.0,["make_conflict"]
    if a.year and b.year and a.year!=b.year:
        return 0.0,["year_conflict"]

    ca,cb=_identity_codes(a),_identity_codes(b)
    if ca and cb and not (ca & cb):
        return 0.0,["identity_conflict"]

    dealer_same=_dealer_equal(getattr(a,"dealer",""),getattr(b,"dealer",""))
    if dealer_same is False:
        return 0.0,["dealer_conflict"]

    km_delta=None if a.mileage_km is None or b.mileage_km is None else abs(a.mileage_km-b.mileage_km)
    price_delta=None if a.price_eur is None or b.price_eur is None else abs(float(a.price_eur)-float(b.price_eur))
    price_ratio=None
    if a.price_eur and b.price_eur:
        price_ratio=price_delta/max(float(a.price_eur),float(b.price_eur))

    score=0.0
    if _norm(a.model)==_norm(b.model):
        score+=0.20; reasons.append("model")
    elif ca & cb:
        score+=0.15; reasons.append("identity_model")
    if ca & cb:
        score+=0.20; reasons.append("identity_code")
    if a.year and b.year and a.year==b.year:
        score+=0.15; reasons.append("year")
    if _norm(a.body) and _norm(a.body)==_norm(b.body):
        score+=0.05; reasons.append("body")
    if dealer_same is True:
        score+=0.15; reasons.append("dealer")
    if km_delta is not None:
        if km_delta<=100:
            score+=0.15; reasons.append("mileage_100")
        elif km_delta<=750:
            score+=0.08; reasons.append("mileage_750")
    if price_delta is not None:
        if price_delta<=250:
            score+=0.10; reasons.append("price_250")
        elif price_delta<=750:
            score+=0.06; reasons.append("price_750")
        elif price_ratio is not None and price_ratio<=0.18:
            score+=0.03; reasons.append("price_drift")
    if dealer_same is True and km_delta is not None and km_delta<=100 and price_ratio is not None and price_ratio<=0.18:
        score=max(score,0.90); reasons.append("same_dealer_near_odometer")
    if dealer_same is None:
        if not (km_delta is not None and km_delta<=75 and price_delta is not None and price_delta<=300 and (ca & cb)):
            score=min(score,0.70)
    return min(score,1.0),reasons


def cross_source_matches(left, right, threshold=0.85):
    matches=[]
    for a in left:
        best=None
        for b in right:
            score,reasons=match_vehicle(a,b)
            if score>=threshold and (best is None or score>best.confidence):
                best=Match(a.source,a.source_id,b.source,b.source_id,score,reasons)
        if best:
            matches.append(best)
    return matches
