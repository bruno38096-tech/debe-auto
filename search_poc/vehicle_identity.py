"""Canonical brand/model/engine matching and scalable marketplace routing.

Vehicle identity is judged only from the advert's own title and URL, never
from a neighbouring listing, dealer description, or category page.
"""
import re
import unicodedata
from urllib.parse import urlparse


def norm(text):
    value=unicodedata.normalize("NFKD",str(text or "")).encode("ascii","ignore").decode().lower()
    value=re.sub(r"\b(\d{3})\s+(de|e|d|i)\b",r"\1\2",value)
    value=re.sub(r"\b([xs])drive\s*(\d{2}[a-z0-9]+)\b",r"\1drive\2",value)
    value=re.sub(r"\b([qx])\s+(\d)\b",r"\1\2",value)
    value=re.sub(r"\b(xc|ex|ec)\s+(\d{2})\b",r"\1\2",value)
    value=re.sub(r"\be[- ]?tron\b","etron",value)
    value=re.sub(r"\be[- ]?hybrid\b","ehybrid",value)
    value=re.sub(r"\bplug[- ]?in\b","plugin",value)
    return re.sub(r"[^a-z0-9]+"," ",value).strip()


BRAND_ALIASES={
    "mercedes benz":("mercedes benz","mercedes"),
    "skoda":("skoda",),
    "citroen":("citroen",),
    "cupra":("cupra",),
    "seat":("seat",),
}
_SKIP_VARIANT={"4matic","awd","rwd"}  # handled when explicitly specified


def contains(text,phrase):
    txt=" "+norm(text)+" "; fragment=" "+norm(phrase)+" "
    return fragment in txt


def vehicle_identity_text(row):
    title=str(row.get("title") or "")
    url=str(row.get("url") or "")
    # URL model/engine is an independent advertisement identifier.
    slug=urlparse(url).path.rsplit("/",1)[-1].split("-ID")[0]
    return norm(title+" "+slug)


def spec_matches(make="",model="",variant="",body="all",row=None):
    """Conservative check for a structured search result.

    A Mercedes AMG GLC 63 must never be matched to a GLC 300. An incomplete
    title lacking the requested engine is unknown, not a positive match.
    """
    row=row or {}
    identity=vehicle_identity_text(row)
    if not identity or not make or not model:
        return False
    brand=norm(make)
    known_brands=BRAND_ALIASES.get(brand,(brand,))
    if not any(contains(identity,x) for x in known_brands):
        return False

    wanted_model=norm(model)
    if not contains(identity,wanted_model):
        # BMW stock titles sometimes omit "Série 3" and show "BMW 330e".
        if not (brand=="bmw" and re.fullmatch(r"serie [1-5]",wanted_model)
                and re.search(r"\b"+re.escape(wanted_model[-1])+r"\d{2}[a-z]\b",identity)):
            return False

    variant=norm(variant)
    if variant:
        # Model prefix in Mercedes catalog dropdown is not a powertrain token.
        if variant.startswith("amg "):
            if not contains(identity,"amg"):
                return False
            variant=variant[4:]
        if variant.startswith(wanted_model+" "):
            variant=variant[len(wanted_model)+1:]
        if not variant:
            return True
        # Check exact engine/trim tokens. Never collapse AMG 63 into GLC 300,
        # 300e into 300de, a 45 quattro into a 35 e-tron, etc.
        words=variant.split()
        # Keep both 's' and 'rs' for Porsche/Audi trims.
        for token in words:
            if token in {"ver","edition"}:
                continue
            if not contains(identity,token):
                # Normalize marketing units and synonymous transmission labels.
                if token=="plugin" and contains(identity,"phev"):continue
                if token=="electric" and (contains(identity,"eletrico") or contains(identity,"etron")):continue
                return False

    requested_body=norm(body)
    if requested_body in {"station","coupe","cabrio","sedan"}:
        alternatives={
            "station":("touring","avant","station","estate","carrinha","wagon","variant","combi","sportstourer","sw"),
            "coupe":("coupe","coup","coupé"),
            "cabrio":("cabrio","cabriolet","roadster","convertible","spyder"),
            "sedan":("sedan","berlina","limousine","saloon"),
        }[requested_body]
        if not any(contains(identity,a) for a in alternatives):
            return False
    elif requested_body=="suv":
        # A vehicle identified as a Coupé must not appear as standard SUV.
        # Model groups like GLC / Q4 / XC60 are SUV by definition.
        if contains(identity,"coupe") or contains(identity,"coup"):
            return False
    return True


MAKE_SLUGS={
    "mercedes benz":"mercedes-benz",
    "skoda":"skoda",
    "citroen":"citroen",
    "volkswagen":"volkswagen",
}


def marketplace_model_route(make,model,body="all"):
    """Generate a safe Standvirtual model-directory URL for the whole catalog."""
    import re
    from urllib.parse import quote
    brand=norm(make)
    m=norm(model)
    if not brand or not m:
        return ""
    maker=MAKE_SLUGS.get(brand,brand.replace(" ","-"))
    slug=re.sub(r"[^a-z0-9]+","-",m).strip("-")
    # Standvirtual slug conventions used for XC/EX ranges.
    slug=re.sub(r"^(xc|ex|ec)(\d{2})$",r"\1-\2",slug)
    # Audi 'e-tron' needs a hyphen, not collapsed 'etron'.
    slug=slug.replace("etron","e-tron")
    if norm(make)=="bmw":
        slug=slug.replace("serie-","serie-")
    # Station body has independent search directories in major model lines.
    if norm(body)=="station" and brand=="audi" and m in {"a4","a6"}:
        slug+="-avant"
    if brand=="audi" and m=="a6 etron":
        slug="a6-avant-e-tron" if norm(body)=="station" else "a6-sportback-e-tron"
    if brand=="mercedes benz" and m=="glc":
        slug="glc"
    return "https://www.standvirtual.com/carros/"+quote(maker,safe="-")+"/"+quote(slug,safe="-")
