"""Embed the loopback Dash application in the Deck without exposing another LAN port."""
import json
import re
import requests

PREFIX = '/finance'
UPSTREAM = 'http://127.0.0.1:9500'
MAX_BODY = 8 * 1024 * 1024

def request_payload(raw):
    data = json.loads(raw)
    def normalize(items):
        for item in items:
            if isinstance(item, list):
                normalize(item)
            elif isinstance(item, dict) and item.get('property') == 'pathname' and isinstance(item.get('value'), str):
                value = item['value']
                if value == PREFIX or value.startswith(PREFIX + '/'):
                    item['value'] = value[len(PREFIX):] or '/'
    # Dash ALL/MATCH callbacks group component inputs in nested lists.
    # Do not recurse into component values: those are application data.
    normalize(data.get('inputs', []) + data.get('state', []))
    return json.dumps(data).encode()

def local_links(value):
    if isinstance(value, list): return [local_links(v) for v in value]
    if not isinstance(value, dict): return value
    result = {}
    for key, item in value.items():
        if key in ('href', 'src') and isinstance(item, str) and item.startswith('/') and not item.startswith('//') and not item.startswith(PREFIX + '/'):
            result[key] = PREFIX + item
        else: result[key] = local_links(item)
    return result

def html_for_deck(text):
    def config(match):
        data = json.loads(match.group(2))
        data['requests_pathname_prefix'] = PREFIX + '/'
        body = json.dumps(data, ensure_ascii=True).replace('<', '\\u003c')
        return match.group(1) + body + match.group(3)
    text = re.sub(r'(<script[^>]*id="_dash-config"[^>]*>)(.*?)(</script>)', config, text, flags=re.S)
    return re.sub(r'(href|src)="(/(?!/)[^"]*)"', lambda m: m.group(1)+'="'+PREFIX+m.group(2)+'"', text)

def serve(handler):
    path = handler.path[len(PREFIX):] or '/'
    if not path.startswith('/') or path.startswith('//'):
        handler._send(400, '{}'); return
    length = int(handler.headers.get('Content-Length') or 0)
    if length < 0 or length > MAX_BODY:
        handler._send(413, '{}'); return
    origin = handler.headers.get('Origin')
    from urllib.parse import urlsplit
    if handler.command == 'POST' and origin and urlsplit(origin).netloc != handler.headers.get('Host'):
        handler._send(403, '{}'); return
    raw = handler.rfile.read(length) if length else None
    if raw and path.split('?')[0] == '/_dash-update-component':
        try: raw = request_payload(raw)
        except (ValueError, TypeError, AttributeError): handler._send(400, '{}'); return
    headers = {k: handler.headers[k] for k in ('Content-Type', 'Cookie') if handler.headers.get(k)}
    try:
        response = requests.request(handler.command, UPSTREAM + path, data=raw, headers=headers, timeout=(3, 35), allow_redirects=False)
    except requests.RequestException:
        handler._send(503, 'Painel financeiro local indisponivel.', 'text/plain; charset=utf-8'); return
    body = response.content
    content_type = response.headers.get('Content-Type', 'application/octet-stream')
    if 'application/json' in content_type:
        try: body = json.dumps(local_links(response.json()), ensure_ascii=False).encode()
        except ValueError: pass
    elif 'text/html' in content_type:
        body = html_for_deck(response.text).encode()
    handler.send_response(response.status_code)
    handler.send_header('Content-Type', content_type)
    handler.send_header('Content-Length', str(len(body)))
    handler.send_header('Cache-Control', 'no-store')
    for cookie in response.raw.headers.getlist('Set-Cookie'):
        handler.send_header('Set-Cookie', cookie.replace('Path=/', 'Path=/finance/'))
    if response.headers.get('Location'):
        location = response.headers['Location']
        handler.send_header('Location', PREFIX + location if location.startswith('/') else location)
    handler.end_headers(); handler.wfile.write(body)
