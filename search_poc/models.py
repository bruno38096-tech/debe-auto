from dataclasses import dataclass, asdict
from typing import Optional
import hashlib
import re
import unicodedata


def _norm(value: str) -> str:
    value = unicodedata.normalize("NFKD", value or "").encode("ascii", "ignore").decode()
    return re.sub(r"[^a-z0-9]+", " ", value.lower()).strip()


@dataclass
class Vehicle:
    source: str
    source_id: str
    url: str
    make: str
    model: str
    variant: str
    body: str
    year: Optional[int]
    mileage_km: Optional[int]
    price_eur: Optional[float]
    dealer: str = ""
    fuel: str = ""
    power_cv: Optional[int] = None
    co2_g_km: Optional[float] = None
    electric_range_km: Optional[float] = None
    condition: str = "used"
    availability: str = ""
    list_price_eur: Optional[float] = None
    discount_eur: Optional[float] = None
    discount_pct: Optional[float] = None
    is_official_stock: bool = False
    vin: str = ""
    stock_ref: str = ""
    observed_at: str = ""
    conditional_price_eur: Optional[float] = None
    price_condition: str = ""

    @property
    def fingerprint(self) -> str:
        strong = _norm(self.vin) or _norm(self.stock_ref)
        if strong:
            return hashlib.sha1((self.source + "|" + strong).encode()).hexdigest()[:16]
        parts = [
            _norm(self.make), _norm(self.model), _norm(self.variant), _norm(self.body),
            str(self.year or ""), str(self.mileage_km or ""), str(round(self.price_eur or 0)),
            _norm(self.dealer), _norm(self.condition),
        ]
        return hashlib.sha1("|".join(parts).encode()).hexdigest()[:16]

    def to_dict(self):
        data = asdict(self)
        data["fingerprint"] = self.fingerprint
        return data
