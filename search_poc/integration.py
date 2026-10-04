"""Feature-flagged integration of DEBE Search into the current DEBE Flask app.

The current listing-analysis flow remains untouched. Search is exposed only
when DEBE_SEARCH_BETA_ENABLED is truthy.
"""
import os

from flask import Blueprint, Response, abort, jsonify, request

from search_poc.beta_engine import search_all
from search_poc.beta_sources import SOURCES, CONDITION_LABELS
from search_poc.vehicle_catalog import CATALOG, BODY_STYLES, brands, canonical_query
from search_beta_app import HTML as SEARCH_BETA_HTML


bp = Blueprint("debe_search_beta", __name__, url_prefix="/search-beta")

_TRUE = {"1", "true", "yes", "on", "enabled"}


def search_beta_enabled():
    return str(os.getenv("DEBE_SEARCH_BETA_ENABLED", "")).strip().lower() in _TRUE


@bp.before_request
def require_search_beta():
    if not search_beta_enabled():
        abort(404)


def _integrated_html():
    html = SEARCH_BETA_HTML
    html = html.replace("fetch('/api/catalog')", "fetch('/search-beta/api/catalog')")
    html = html.replace("fetchResults('/api/search?'+p.toString())", "fetchResults('/search-beta/api/search?'+p.toString())")
    html = html.replace(
        '<div class="hero"><div><div class="brand">DEBE Search <em>Beta</em></div>',
        '<div style="margin-bottom:16px"><a href="/" style="color:#a8b9d6;text-decoration:none;font-weight:750">← Voltar ao DEBE</a></div>'
        '<div class="hero"><div><div class="brand">DEBE Search <em>Beta</em></div>',
    )
    return html


@bp.get("")
@bp.get("/")
def search_home():
    return Response(_integrated_html(), mimetype="text/html")


@bp.get("/api/catalog")
def api_catalog():
    return jsonify({
        "brands": brands(),
        "catalog": CATALOG,
        "body_styles": BODY_STYLES,
        "conditions": CONDITION_LABELS,
    })


@bp.get("/api/search")
def api_search():
    q = (request.args.get("q") or "").strip()
    make = (request.args.get("make") or "").strip()
    model = (request.args.get("model") or "").strip()
    variant = (request.args.get("variant") or "").strip()
    body = (request.args.get("body") or "all").strip()
    condition = (request.args.get("condition") or "all").strip()

    if condition not in set(CONDITION_LABELS) | {"all"}:
        condition = "all"
    if not q and make and model:
        q = canonical_query(make, model, variant, body)
    if not q:
        return jsonify({"ok": False, "error": "Pesquisa inválida"}), 400

    payload = search_all(q, condition=condition, max_per_source=3)
    payload["display_query"] = " · ".join(x for x in (make, model, variant) if x) if make else q
    payload["selectors"] = {"make": make, "model": model, "variant": variant, "body": body}
    payload["feature"] = "search-beta"
    return jsonify(payload)


@bp.get("/api/sources")
def api_sources():
    return jsonify({"count": len(SOURCES), "sources": SOURCES})


@bp.get("/health")
def health():
    return jsonify({"ok": True, "service": "debe-search-beta", "sources": len(SOURCES)})
