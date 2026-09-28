import json, sys, types, unittest
from pathlib import Path
from unittest.mock import patch
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from ultron_agentes import financas, seguranca, register_agent_tools


class Fake:
    def __init__(self, body): self.body = body
    def __enter__(self): return self
    def __exit__(self, *a): pass
    def read(self, n=-1): return json.dumps(self.body).encode()


class FinancasTests(unittest.TestCase):
    def test_bcb_ipca_accumulates_12_months(self):
        seen = {}
        def opener(req, timeout):
            seen['url'] = req.full_url
            return Fake([{'data': f'01/{m:02d}/2025', 'valor': '0,50'} for m in range(1, 13)])
        r = financas.bcb_serie('ipca', 12, opener=opener)
        self.assertIn('bcdata.sgs.433/dados/ultimos/12', seen['url'])
        self.assertEqual(r['acumulado_12_meses_pct'], 6.17)
        with self.assertRaises(ValueError): financas.bcb_serie('bitcoin')
        with self.assertRaises(ValueError): financas.bcb_serie('selic', data_inicial='2026-01-01')

    def test_brasilapi_cnpj_filters_fields(self):
        r = financas.brasilapi('cnpj', '00.000.000/0001-91', opener=lambda req, timeout: Fake({'cnpj': '1', 'razao_social': 'X', 'email': 'a@b', 'telefone': '1'}))
        self.assertEqual(set(r['dados']), {'cnpj', 'razao_social'})
        with self.assertRaises(ValueError): financas.brasilapi('cnpj', '123')
        with self.assertRaises(ValueError): financas.brasilapi('x')

    def test_cotacao_validation_and_suffix(self):
        calls = []
        def runner(args, **kw):
            calls.append(args); return types.SimpleNamespace(returncode=0, stdout='{"ticker":"PETR4.SA","preco":30}', stderr='')
        with patch.object(Path, 'exists', return_value=True):
            r = financas.cotacao_b3('petr4', '6mo', runner=runner)
        self.assertEqual(calls[0][-2:], ['PETR4.SA', '6mo'])
        self.assertEqual(r['status'], 'ok')
        with self.assertRaises(ValueError): financas.cotacao_b3('PETR4; rm -rf /')
        self.assertEqual(financas.cotacao_b3('PETR4', python='/nao/existe')['error'], 'yfinance_nao_instalado')


class RegistroTests(unittest.TestCase):
    def test_tools_per_profile(self):
        for perfil, esperado in (('bigode', {'bcb_serie', 'brasilapi', 'cotacao_b3'}), ('mrrobot', {'seguranca_relatorio', 'backup_status'})):
            tools = {}
            ts, prompt = register_agent_tools(lambda **kw: tools.__setitem__(kw['name'], kw), perfil)
            self.assertEqual(set(tools), esperado)
            self.assertTrue(prompt)
        with self.assertRaises(ValueError): register_agent_tools(lambda **kw: None, 'harvey')

    def test_missing_report_is_json_error(self):
        tools = {}
        register_agent_tools(lambda **kw: tools.__setitem__(kw['name'], kw), 'mrrobot')
        with patch.object(seguranca, 'DIR', Path('/nao/existe')):
            out = json.loads(tools['backup_status']['handler']({}))
        self.assertEqual(out['error'], 'backup.json_ainda_nao_gerado')


if __name__ == '__main__':
    unittest.main()


class RobustezTests(unittest.TestCase):
    def test_future_dates_and_retry(self):
        calls = []
        def opener(req, timeout):
            calls.append(1)
            if len(calls) == 1:
                import urllib.error
                raise urllib.error.HTTPError(req.full_url, 502, 'bad', {}, None)
            return Fake([{'data': '04/11/2099', 'valor': '13.75'}])
        with patch('time.sleep'):
            r = financas.bcb_serie('selic_meta', 1, opener=opener)
        self.assertEqual(len(calls), 2)
        self.assertNotIn('2099', r['valores'][-1]['data'])

    def test_extra_args_like_reason_are_ignored(self):
        tools = {}
        register_agent_tools(lambda **kw: tools.__setitem__(kw['name'], kw), 'mrrobot')
        with patch.object(seguranca, 'DIR', Path('/nao/existe')):
            out = json.loads(tools['backup_status']['handler']({'reason': 'x'}))
        self.assertEqual(out['error'], 'backup.json_ainda_nao_gerado')
