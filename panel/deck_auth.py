"""Local-device pairing. No provider credentials or session values in browser storage."""
import hashlib
import ipaddress
import json
import os
import re
import secrets
import socket
import threading
import time
from http.cookies import SimpleCookie, CookieError
from pathlib import Path
from urllib.parse import urlsplit

COOKIE = 'ultron_deck_session'
TTL = 30 * 86400
LOCAL = {'localhost', '127.0.0.1', '::1'}


def configured_hosts(path=None):
    """Operator-owned VPN/proxy aliases; never infer trust from private address ranges."""
    path = Path(path or os.environ.get('DECK_NETWORK_FILE', str(Path.home() / '.ultron-private' / 'deck-network.json')))
    if not path.exists():
        return set()
    data = json.loads(path.read_text(encoding='utf-8-sig'))
    entries = data.get('allowed_hosts', []) if isinstance(data, dict) else None
    if not isinstance(entries, list) or len(entries) > 16:
        raise ValueError('Configuracao de hosts invalida')
    hosts = set()
    for entry in entries:
        if not isinstance(entry, str) or not entry or len(entry) > 253 or entry != entry.strip():
            raise ValueError('Host configurado invalido')
        value = entry.lower()
        try:
            ipaddress.ip_address(value)
        except ValueError:
            if any(not re.fullmatch(r'[a-z0-9](?:[a-z0-9-]{0,61}[a-z0-9])?', label) for label in value.split('.')):
                raise ValueError('Informe apenas o host, sem porta, URL ou curinga')
        hosts.add(value)
    return hosts


def digest(value):
    return hashlib.sha256(value.encode()).hexdigest()


def local_client(address):
    try:
        ip = ipaddress.ip_address(address)
        return ip.is_loopback or bool(getattr(ip, 'ipv4_mapped', None) and ip.ipv4_mapped.is_loopback)
    except ValueError:
        return False


class PairingStore:
    def __init__(self, path=None, clock=time.time):
        self.path = Path(path or os.environ.get('DECK_AUTH_FILE', str(Path.home() / '.ultron-private' / 'deck-sessions.json')))
        self.clock = clock
        self.lock = threading.RLock()
        self.code_hash = None
        self.code_expiry = 0
        self.attempts = []

    def _read(self):
        if not self.path.exists():
            return []
        # Malformed storage must not turn authentication off.
        return [s for s in json.loads(self.path.read_text(encoding='utf-8')) if s['expires'] > self.clock()]

    def _save(self, sessions):
        self.path.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
        tmp = self.path.with_suffix('.tmp')
        fd = os.open(tmp, os.O_WRONLY | os.O_CREAT | os.O_TRUNC, 0o600)
        with os.fdopen(fd, 'w', encoding='utf-8') as out:
            json.dump(sessions, out)
        os.replace(tmp, self.path)

    def new_code(self):
        with self.lock:
            code = ''.join(secrets.choice('0123456789') for _ in range(8))
            self.code_hash, self.code_expiry = digest(code), self.clock() + 600
            return {'code': code, 'expires_in': 600}

    def pair(self, code, label, address):
        with self.lock:
            now = self.clock()
            self.attempts = [(at, ip) for at, ip in self.attempts if now - at < 900]
            if len(self.attempts) >= 60 or sum(ip == address for _, ip in self.attempts) >= 5:
                raise ValueError('Muitas tentativas. Aguarde 15 minutos.')
            self.attempts.append((now, address))
            if not isinstance(code, str) or not self.code_hash or now >= self.code_expiry or not secrets.compare_digest(digest(code), self.code_hash):
                raise ValueError('Codigo invalido ou expirado.')
            token = secrets.token_urlsafe(32)
            session = {'id': secrets.token_hex(8), 'hash': digest(token), 'label': str(label or 'Dispositivo')[:60], 'created': now, 'expires': now + TTL}
            sessions = self._read()
            if len(sessions) >= 32:
                raise ValueError('Limite de dispositivos. Revogue um pareamento no notebook.')
            self._save(sessions + [session])
            self.code_hash = None  # Single use, consumed only after durable persistence.
            return token

    def session(self, header):
        cookie = SimpleCookie()
        try:
            cookie.load(header or '')
            token = cookie[COOKIE].value if COOKIE in cookie else ''
        except CookieError:
            return None
        if not token or len(token) > 100:
            return None
        with self.lock:
            return next((s for s in self._read() if secrets.compare_digest(s['hash'], digest(token))), None)

    def devices(self):
        with self.lock:
            return [{k: s[k] for k in ('id', 'label', 'created', 'expires')} for s in self._read()]

    def revoke(self, device_id):
        with self.lock:
            sessions = self._read()
            self._save([s for s in sessions if s['id'] != device_id])


class DeviceGuard:
    def __init__(self, store=None, allowed_hosts=None, network_file=None, allow_loopback_bootstrap=True, external_port=None):
        self.store = store or PairingStore()
        self.allow_loopback_bootstrap = bool(allow_loopback_bootstrap)
        self.external_port = external_port
        self.hosts = set(allowed_hosts or LOCAL)
        if allowed_hosts is None:
            self.hosts.update(configured_hosts(network_file))
            self.hosts.update({socket.gethostname().lower(), socket.getfqdn().lower()})
            try:
                self.hosts.update(info[4][0] for info in socket.getaddrinfo(socket.gethostname(), None))
            except OSError:
                pass
        self.assets = Path(__file__).resolve().parent

    def reply(self, h, code, data, content_type='application/json; charset=utf-8', cookie=None):
        body = data if isinstance(data, bytes) else json.dumps(data, ensure_ascii=False).encode()
        h.send_response(code)
        h.send_header('Content-Type', content_type)
        h.send_header('Content-Length', str(len(body)))
        h.send_header('Cache-Control', 'no-store')
        if cookie is not None:
            h.send_header('Set-Cookie', cookie)
        h.end_headers()
        if h.command != 'HEAD':
            h.wfile.write(body)
        return False

    def gate(self, h):
        host = h.headers.get('Host', '')
        try:
            parsed = urlsplit('//' + host)
            valid = (len(h.headers.get_all('Host', [])) == 1 and parsed.hostname in self.hosts
                     and not parsed.username and not parsed.password and not parsed.path
                     and parsed.port == (self.external_port or h.server.server_port))
        except ValueError:
            valid = False
        if not valid:
            return self.reply(h, 403, {'ok': False, 'error': 'Host nao autorizado'})
        origin = h.headers.get('Origin')
        expected = ('https' if isinstance(h.connection, __import__('ssl').SSLSocket) else 'http') + '://' + host
        if (origin and origin != expected) or h.headers.get('Sec-Fetch-Site') == 'cross-site':
            return self.reply(h, 403, {'ok': False, 'error': 'Origem nao autorizada'})
        path = urlsplit(h.path).path
        # A forwarded VPN connection may arrive from loopback. Only an explicit
        # localhost request without proxy headers can issue/revoke device codes.
        trusted = (self.allow_loopback_bootstrap and local_client(h.client_address[0]) and parsed.hostname in LOCAL
                   and not any(h.headers.get(name) is not None for name in
                               ('Forwarded', 'X-Forwarded-For', 'X-Forwarded-Host', 'X-Real-IP')))
        # Even paired browsers cannot call privileged operations from a foreign page.
        try:
            session = self.store.session(h.headers.get('Cookie'))
        except (OSError, ValueError, TypeError, KeyError):
            return self.reply(h, 503, {'ok': False, 'error': 'Estado de autenticacao indisponivel'})
        if path in ('/auth', '/auth.js', '/auth.css') and h.command == 'GET':
            name = {'/auth': 'auth.html', '/auth.js': 'auth.js', '/auth.css': 'auth.css'}[path]
            mime = {'/auth': 'text/html', '/auth.js': 'text/javascript', '/auth.css': 'text/css'}[path]
            return self.reply(h, 200, (self.assets / name).read_bytes(), mime + '; charset=utf-8')
        if path == '/auth/status' and h.command == 'GET':
            return self.reply(h, 200, {'ok': True, 'local': trusted, 'paired': bool(session), 'devices': self.store.devices() if trusted else []})
        if path in ('/auth/code', '/auth/pair', '/auth/revoke', '/auth/logout'):
            if h.command != 'POST':
                return self.reply(h, 405, {'ok': False, 'error': 'Use POST'})
            if path in ('/auth/code', '/auth/revoke') and not trusted:
                return self.reply(h, 403, {'ok': False, 'error': 'Disponivel apenas no notebook via localhost'})
            try:
                if h.headers.get('Transfer-Encoding') or len(h.headers.get_all('Content-Length', [])) != 1:
                    raise ValueError('Tamanho invalido')
                length = int(h.headers['Content-Length'])
                if not 0 < length <= 2048:
                    raise ValueError('Conteudo excede limite')
                if h.headers.get_content_type() != 'application/json':
                    raise ValueError('Envie JSON')
                data = json.loads(h.rfile.read(length))
                if not isinstance(data, dict):
                    raise ValueError('Objeto JSON obrigatorio')
                if path == '/auth/code':
                    return self.reply(h, 200, {'ok': True, **self.store.new_code()})
                if path == '/auth/revoke':
                    self.store.revoke(data.get('id'))
                    return self.reply(h, 200, {'ok': True})
                secure = '; Secure' if expected.startswith('https:') else ''
                if path == '/auth/logout':
                    if session:
                        self.store.revoke(session['id'])
                    return self.reply(h, 200, {'ok': True}, cookie=COOKIE+'=; Max-Age=0; Path=/; HttpOnly; SameSite=Strict'+secure)
                token = self.store.pair(data.get('code'), data.get('label'), h.client_address[0])
                return self.reply(h, 200, {'ok': True}, cookie=f'{COOKIE}={token}; Max-Age={TTL}; Path=/; HttpOnly; SameSite=Strict'+secure)
            except (ValueError, TypeError, UnicodeError) as exc:
                return self.reply(h, 400, {'ok': False, 'error': str(exc)[:120]})
        if path == '/health' and h.command in ('GET', 'HEAD'):
            return self.reply(h, 200, {'ok': True})
        if trusted or session:
            return True
        if h.command == 'GET' and 'text/html' in h.headers.get('Accept', ''):
            return self.reply(h, 401, (self.assets / 'auth.html').read_bytes(), 'text/html; charset=utf-8')
        return self.reply(h, 401, {'ok': False, 'error': 'Pareie este dispositivo em /auth', 'login': '/auth'})


class AuthenticatedHandler:
    """Mixin gates every HTTP verb before application dispatch, including proxies."""
    guard = None

    def parse_request(self):
        if not super().parse_request():
            return False
        return self.guard.gate(self)

    def end_headers(self):
        self.send_header('X-Content-Type-Options', 'nosniff')
        self.send_header('X-Frame-Options', 'SAMEORIGIN')
        self.send_header('Referrer-Policy', 'same-origin')
        self.send_header('Content-Security-Policy', "frame-ancestors 'self'; object-src 'none'; base-uri 'self'")
        super().end_headers()
