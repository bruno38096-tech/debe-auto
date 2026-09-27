from dataclasses import dataclass


@dataclass
class Match:
    left_source: str
    left_id: str
    right_source: str
    right_id: str
    confidence: float
    reasons: list


def _close(a, b, tolerance):
    if a is None or b is None:
        return False
    return abs(a - b) <= tolerance


def match_vehicle(a, b):
    """Heuristic cross-source duplicate matcher for the PoC.

    Exact VIN/source IDs will supersede this when available. Current weights
    intentionally require several agreeing public facts before calling a match.
    """
    score = 0.0
    reasons = []
    if a.make.lower() == b.make.lower() and a.model.lower() == b.model.lower():
        score += 0.15; reasons.append("make_model")
    if a.body.lower() == b.body.lower():
        score += 0.10; reasons.append("body")
    if a.year and b.year and a.year == b.year:
        score += 0.15; reasons.append("year")
    if _close(a.mileage_km, b.mileage_km, 750):
        score += 0.30; reasons.append("mileage")
    if _close(a.price_eur, b.price_eur, 750):
        score += 0.20; reasons.append("price")
    av, bv = (a.variant or "").lower(), (b.variant or "").lower()
    if av and bv and ("330" in av and "330" in bv):
        score += 0.10; reasons.append("variant_family")
    return score, reasons


def cross_source_matches(left, right, threshold=0.75):
    matches = []
    for a in left:
        best = None
        for b in right:
            score, reasons = match_vehicle(a, b)
            if score >= threshold and (best is None or score > best.confidence):
                best = Match(a.source, a.source_id, b.source, b.source_id, score, reasons)
        if best:
            matches.append(best)
    return matches
