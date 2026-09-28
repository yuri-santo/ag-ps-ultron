import json
from pathlib import Path
import tempfile
import unittest
import urllib.error

from ultron_lab import homelab


class FakeResponse:
    def __init__(self, status):
        self.status = status

    def __enter__(self):
        return self

    def __exit__(self, *args):
        return False


class FakeOpener:
    def __init__(self, table):
        self.table = table
        self.requests = []

    def open(self, request, timeout):
        self.requests.append((request.full_url, dict(request.header_items()), timeout))
        outcome = self.table[request.full_url]
        if isinstance(outcome, Exception):
            raise outcome
        if outcome >= 400:
            raise urllib.error.HTTPError(request.full_url, outcome, 'x', {}, None)
        return FakeResponse(outcome)


class HomelabTests(unittest.TestCase):
    def inventory(self, services):
        directory = tempfile.TemporaryDirectory()
        self.addCleanup(directory.cleanup)
        path = Path(directory.name) / 'homelab.json'
        path.write_text(json.dumps({'servicos': services}), encoding='utf-8')
        return path

    def test_reports_up_down_and_critical(self):
        path = self.inventory([
            {'nome': 'ai-memory', 'url': 'http://127.0.0.1:49374/healthz', 'grupo': 'ia', 'critico': True},
            {'nome': 'frankmd', 'url': 'http://127.0.0.1:7591/up', 'grupo': 'arquivos', 'esperado': [200, 401]},
            {'nome': 'ollama', 'url': 'http://127.0.0.1:11434/api/version', 'grupo': 'ia'},
        ])
        opener = FakeOpener({'http://127.0.0.1:49374/healthz': urllib.error.URLError(ConnectionRefusedError()),
                             'http://127.0.0.1:7591/up': 401, 'http://127.0.0.1:11434/api/version': 200})
        result = homelab.status(path, opener=opener, environ={})
        self.assertEqual(result['verificados'], 3)
        self.assertEqual(result['fora'], ['ai-memory'])
        self.assertEqual(result['criticos_fora'], ['ai-memory'])
        by_name = {s['nome']: s for s in result['servicos']}
        self.assertEqual(by_name['ai-memory']['erro'], 'ConnectionRefusedError')
        self.assertEqual(by_name['frankmd']['status'], 'ok')

    def test_filters_and_unknown_filter(self):
        path = self.inventory([{'nome': 'a', 'url': 'http://h:1/', 'grupo': 'ia'},
                               {'nome': 'b', 'url': 'http://h:2/', 'grupo': 'core'}])
        opener = FakeOpener({'http://h:1/': 200, 'http://h:2/': 500})
        self.assertEqual(homelab.status(path, grupo='ia', opener=opener, environ={})['verificados'], 1)
        self.assertEqual(homelab.status(path, nome='b', opener=opener, environ={})['fora'], ['b'])
        with self.assertRaises(homelab.HomelabError):
            homelab.status(path, grupo='nada', opener=opener, environ={})

    def test_secret_headers_come_from_env_and_never_return(self):
        path = self.inventory([{'nome': 'grafana', 'url': 'https://g.example.com/api/health',
                                'headers_env': {'CF-Access-Client-Secret': 'CF_SECRET'}}])
        opener = FakeOpener({'https://g.example.com/api/health': 200})
        result = homelab.status(path, opener=opener, environ={'CF_SECRET': 'segredo-real'})
        self.assertEqual(opener.requests[0][1].get('Cf-access-client-secret'), 'segredo-real')
        self.assertNotIn('segredo-real', json.dumps(result))
        missing = homelab.status(path, opener=opener, environ={})
        self.assertIn('CF_SECRET', missing['servicos'][0]['aviso'])

    def test_rejects_unsafe_inventory(self):
        bad = [
            [{'nome': 'x', 'url': 'file:///etc/passwd'}],
            [{'nome': 'x', 'url': 'http://user:pass@h/'}],
            [{'nome': 'X Maiusculo', 'url': 'http://h/'}],
            [{'nome': 'x', 'url': 'http://h/'}, {'nome': 'x', 'url': 'http://h/'}],
            [{'nome': 'x', 'url': 'http://h/', 'timeout': 60}],
            [{'nome': 'x', 'url': 'http://h/', 'headers_env': {'Auth': 'segredo literal'}}],
            [],
        ]
        for services in bad:
            with self.assertRaises(homelab.HomelabError, msg=services):
                homelab.load_inventory(self.inventory(services))

    def test_shipped_inventories_are_valid(self):
        root = Path(__file__).resolve().parents[1] / 'homelab' / 'inventario'
        for name in ('homelab.pc.json', 'homelab.servidor.json'):
            services = homelab.load_inventory(root / name)
            self.assertTrue(any(s['nome'] == 'ai-memory' and s['critico'] for s in services))


if __name__ == '__main__':
    unittest.main()
