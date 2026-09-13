"""Minimal, privacy-conscious analytics for the DEBE public beta.

Events are written as structured JSON to Render application logs. This keeps the
beta dependency-free and avoids collecting names, emails, VINs, listing URLs or
other personal data. The browser supplies a random session id stored only for the
current tab so the funnel can be understood without user accounts or cookies.
"""
import json
import re
from datetime import datetime, timezone
from flask import request, jsonify

ALLOWED_EVENTS = {
    'page_view',
    'listing_submitted',
    'listing_loaded',
    'listing_failed',
    'report_started',
    'report_completed',
    'comparable_click',
    'feedback_useful',
    'feedback_reuse',
    'share_click',
}
ALLOWED_FIELDS = {
    'session', 'marketplace', 'model', 'year', 'score', 'missing_fields',
    'research_ok', 'comparables', 'group', 'source', 'value',
    'utm_source', 'utm_medium', 'utm_campaign',
}

def _scalar(value, limit=120):
    if isinstance(value, bool):
        return value
    if isinstance(value, (int, float)):
        return value
    if isinstance(value, list):
        return [_scalar(v, 40) for v in value[:8]]
    value = re.sub(r'[\r\n\t]+', ' ', str(value or '')).strip()
    return value[:limit]


def install(appmod):
    app = appmod.app
    if 'debe_event' in app.view_functions:
        return

    def debe_event():
        body = request.get_json(silent=True) or {}
        event = _scalar(body.get('event'), 40)
        if event not in ALLOWED_EVENTS:
            return jsonify(ok=False, error='Evento inválido'), 400

        payload = {
            'event': event,
            'ts': datetime.now(timezone.utc).isoformat(timespec='seconds'),
        }
        for key in ALLOWED_FIELDS:
            if key in body:
                payload[key] = _scalar(body.get(key))

        print('DEBE_EVENT ' + json.dumps(payload, ensure_ascii=False, separators=(',', ':')), flush=True)
        return jsonify(ok=True)

    app.add_url_rule('/api/event', endpoint='debe_event', view_func=debe_event, methods=['POST'])
