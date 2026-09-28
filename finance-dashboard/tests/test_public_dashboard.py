import importlib
from contextlib import closing
import os
from pathlib import Path
import sqlite3
import sys
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))


class PublicDashboardTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.temp = tempfile.TemporaryDirectory()
        cls.db = Path(cls.temp.name) / 'demo.db'
        from bootstrap import create_database
        create_database(cls.db, demo=True)
        os.environ.update(FIN_DB_PATH=str(cls.db), FIN_DATA_DIR=cls.temp.name,
                          DASHBOARD_PASSWORD='test-only-not-a-real-password')
        cls.app = importlib.import_module('app')

    @classmethod
    def tearDownClass(cls):
        cls.temp.cleanup()

    def test_bootstrap_refuses_existing_database(self):
        from bootstrap import create_database
        before = self.db.read_bytes()
        with self.assertRaises(FileExistsError):
            create_database(self.db, demo=True)
        self.assertEqual(before, self.db.read_bytes())

    def test_login_is_required_for_data_callbacks(self):
        client = self.app.server.test_client()
        response = client.post('/_dash-update-component', json={
            'output': 'page.children', 'inputs': [], 'state': [], 'changedPropIds': []})
        self.assertEqual(response.status_code, 401)

    def test_http_and_all_pages_with_synthetic_data(self):
        client = self.app.server.test_client()
        self.assertEqual(client.get('/').status_code, 200)
        with self.app.server.test_request_context('/'):
            self.app.flask.session['auth'] = True
            month = self.app.mes_corrente()
            for route in ('/', '/categorias', '/receita', '/cartoes', '/assinaturas',
                          '/horas', '/comportamento', '/preditivo', '/investimentos',
                          '/metas', '/mapa', '/planejamento-antigo', '/mei'):
                with self.subTest(route=route):
                    page = self.app.route(route, month)
                    self.assertNotIn('Erro ao carregar', str(page))

    def test_snapshot_uses_only_synthetic_records(self):
        from finance_engine import estado
        snapshot = estado(str(self.db))
        self.assertGreater(snapshot['renda_mes'], 0)
        self.assertAlmostEqual(snapshot['renda_mes'] - snapshot['despesas_total'], snapshot['sobra'])
        with closing(sqlite3.connect(self.db)) as db:
            self.assertEqual(db.execute("SELECT value FROM config WHERE key='dataset'").fetchone()[0], 'synthetic')

    def test_edits_require_authentication_and_reject_unknown_tables(self):
        with self.app.server.test_request_context('/'):
            with self.assertRaises(PermissionError):
                self.app.save_table('contas_a_pagar', [], '')
            with self.assertRaises(ValueError):
                self.app.read_table('config; DROP TABLE config')

    def test_edits_detect_stale_state_and_roll_back_invalid_rows(self):
        with self.app.server.test_request_context('/'):
            self.app.flask.session['auth'] = True
            _, original = self.app.read_table('contas_a_pagar')
            token = self.app.fingerprint(original)
            with self.assertRaises(ValueError):
                self.app.save_table('contas_a_pagar', original, 'stale')
            invalid = [dict(row) for row in original]
            invalid[0]['valor'] = float('nan')
            with self.assertRaises(ValueError):
                self.app.save_table('contas_a_pagar', invalid, token)
            with self.assertRaises(sqlite3.IntegrityError):
                self.app.save_table('contas_a_pagar', original + [original[0]], token)
            self.assertEqual(self.app.read_table('contas_a_pagar')[1], original)
            edited = [dict(row) for row in original]
            edited[0]['descricao'] = 'Edicao de teste'
            try:
                self.app.save_table('contas_a_pagar', edited, token)
                self.assertEqual(self.app.read_table('contas_a_pagar')[1], edited)
            finally:
                self.app.save_table('contas_a_pagar', original, self.app.fingerprint(edited))

    def test_cross_origin_posts_are_rejected(self):
        response = self.app.server.test_client().post('/_dash-update-component',
            headers={'Origin': 'https://untrusted.example'}, json={'output': 'root.children'})
        self.assertEqual(response.status_code, 403)


if __name__ == '__main__':
    unittest.main()
