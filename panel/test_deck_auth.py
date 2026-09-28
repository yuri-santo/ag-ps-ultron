import io
import json
import tempfile
import unittest
from email.message import Message
from pathlib import Path
from types import SimpleNamespace
from deck_auth import DeviceGuard, PairingStore, COOKIE


class Request:
    def __init__(self, method='GET', path='/inbox', address='192.168.1.77', headers=None, body=None):
        self.command, self.path = method, path
        self.client_address = (address, 10001)
        self.server = SimpleNamespace(server_port=8090)
        self.connection = None
        self.headers = Message()
        self.headers['Host'] = '192.168.1.50:8090'
        for k, v in (headers or {}).items():
            if k == 'Host':
                del self.headers['Host']
            self.headers[k] = v
        raw = json.dumps(body or {}).encode()
        if body is not None:
            self.headers['Content-Type'] = 'application/json'
            self.headers['Content-Length'] = str(len(raw))
        self.rfile, self.wfile = io.BytesIO(raw), io.BytesIO()
        self.code, self.output_headers = None, {}
    def send_response(self, code): self.code = code
    def send_header(self, key, value): self.output_headers[key] = value
    def end_headers(self): pass


class AuthTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.now = 10000
        self.store = PairingStore(Path(self.tmp.name)/'sessions.json', lambda: self.now)
        self.guard = DeviceGuard(self.store, {'localhost','127.0.0.1','192.168.1.50'})
    def tearDown(self): self.tmp.cleanup()
    def token(self):
        return self.store.pair(self.store.new_code()['code'], 'phone', '192.168.1.77')
    def test_all_verbs_and_proxies_require_pairing(self):
        for method in ['GET','POST','PUT','PATCH','DELETE','OPTIONS']:
            for path in ['/inbox','/power','/hub','/finance/_dash-update-component','/librechat/api/auth/refresh','/media/private.mp4']:
                req=Request(method,path)
                self.assertFalse(self.guard.gate(req)); self.assertEqual(req.code,401)
    def test_local_access_preserved(self):
        self.assertTrue(self.guard.gate(Request(address='127.0.0.1',headers={'Host':'localhost:8090'})))
    def test_loopback_dns_rebinding_and_cross_origin_blocked(self):
        for headers in [{'Host':'evil.example:8090'},{'Origin':'https://evil.example'}, {'Sec-Fetch-Site':'cross-site'}, {'Origin':'null'}]:
            req=Request('POST','/finance/_dash-update-component',address='127.0.0.1',headers=headers)
            self.assertFalse(self.guard.gate(req)); self.assertEqual(req.code,403)
    def test_pairing_persists_hash_only_and_survives_restart(self):
        token=self.token()
        self.assertNotIn(token,self.store.path.read_text())
        restarted=PairingStore(self.store.path,lambda:self.now)
        self.assertIsNotNone(restarted.session(f'{COOKIE}={token}'))
    def test_single_use_expiry_and_revoke(self):
        code=self.store.new_code()['code']; token=self.store.pair(code,'phone','ip')
        with self.assertRaises(ValueError):self.store.pair(code,'phone','ip')
        self.store.revoke(self.store.devices()[0]['id'])
        self.assertIsNone(self.store.session(f'{COOKIE}={token}'))
        code=self.store.new_code()['code']; self.now+=601
        with self.assertRaises(ValueError):self.store.pair(code,'phone','ip')
    def test_bruteforce_limit_and_session_expiry(self):
        token=self.token();code=self.store.new_code()['code']
        for _ in range(4):
            with self.assertRaises(ValueError):self.store.pair('wrong','x','192.168.1.77')
        with self.assertRaisesRegex(ValueError,'Muitas'):self.store.pair(code,'x','192.168.1.77')
        self.now+=31*86400
        self.assertIsNone(self.store.session(f'{COOKIE}={token}'))
    def test_cookie_flags_and_authorized_proxy(self):
        code=self.store.new_code()['code']
        req=Request('POST','/auth/pair',body={'code':code,'label':'phone'})
        self.assertFalse(self.guard.gate(req));self.assertEqual(req.code,200)
        cookie=req.output_headers['Set-Cookie']
        self.assertIn('HttpOnly',cookie);self.assertIn('SameSite=Strict',cookie)
        self.assertTrue(self.guard.gate(Request('POST','/finance/_dash-update-component',headers={'Cookie':cookie,'Origin':'http://192.168.1.50:8090'})))
    def test_remote_cannot_generate_or_revoke(self):
        token=self.token()
        for path in ['/auth/code','/auth/revoke']:
            req=Request('POST',path,headers={'Cookie':f'{COOKIE}={token}'},body={})
            self.assertFalse(self.guard.gate(req));self.assertEqual(req.code,403)
    def test_malformed_store_fails_closed(self):
        self.store.path.write_text('not-json')
        req=Request(headers={'Cookie':f'{COOKIE}=something'})
        self.assertFalse(self.guard.gate(req));self.assertEqual(req.code,503)
    def test_duplicate_host_is_rejected(self):
        req=Request();req.headers['Host']='evil.example:8090'
        self.assertFalse(self.guard.gate(req));self.assertEqual(req.code,403)


if __name__=='__main__':unittest.main()
