import json, sys, types, unittest
from datetime import date
from pathlib import Path
from unittest.mock import patch

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
from harvey_juridico import oficiais, planalto, prazos, jurisprudencia, register, register_legal_tools, PROMPT
from harvey_juridico.vademecum import VadeMecum, normalizar_artigo
from harvey_juridico.frank_client import Frank

DB = ROOT / 'juridico' / 'vademecum.sqlite'


class Fake:
    def __init__(self, body):
        self.body = body
    def __enter__(self): return self
    def __exit__(self, *a): pass
    def read(self, n=-1): return self.body


class VadeMecumTests(unittest.TestCase):
    vm = VadeMecum(DB)

    def test_exact_articles(self):
        r = self.vm.consultar(norma='CC', artigo='art. 50')['resultados'][0]
        self.assertIn('desvio de finalidade', r['texto'].replace('\n', ' '))
        self.assertTrue(r['citacao'].startswith('CC, art. 50'))
        cf = self.vm.consultar(norma='constituição federal', artigo='5º')['resultados'][0]
        self.assertIn('Todos são iguais perante a lei', cf['texto'].replace('\n', ' '))
        self.assertEqual(self.vm.consultar(norma='CTN', artigo='116')['resultados'][0]['sigla'], 'CTN')

    def test_fulltext_ranking_and_aviso(self):
        r = self.vm.consultar('desconsideração da personalidade jurídica', norma='CC')
        self.assertIn('50', [x['artigo'] for x in r['resultados']])
        self.assertIn('janeiro de 2026', r['aviso_vigencia'])
        self.assertTrue(self.vm.consultar('prescrição quinquenal crédito tributário')['resultados'])

    def test_bad_input(self):
        with self.assertRaises(ValueError): normalizar_artigo('abc')
        with self.assertRaises(ValueError): self.vm.consultar(norma='inexistente', artigo='1')
        with self.assertRaises(ValueError): self.vm.consultar('a')

    def test_injection_in_query_is_inert(self):
        r = self.vm.consultar('"; DROP TABLE artigos; -- OR *')
        self.assertEqual(r['status'], 'ok')


class PrazoTests(unittest.TestCase):
    def test_uteis_skip_weekend_and_holiday(self):
        # intimação sexta 10/10/2025, 5 dias úteis: 13,14,15,16,17 (12/10 domingo feriado não conta)
        r = prazos.calcular_prazo('2025-10-10', 5)
        self.assertEqual((r['inicio_contagem'], r['data_final']), ('2025-10-13', '2025-10-17'))

    def test_djen_disponibilizacao_moves_publication(self):
        # disponibilizado sexta 03/10/2025 -> publicação seg 06/10 -> início ter 07/10; 15 dias úteis
        r = prazos.calcular_prazo('2025-10-03', 15, disponibilizacao_djen=True)
        self.assertEqual(r['inicio_contagem'], '2025-10-07')
        self.assertEqual(r['data_final'], '2025-10-27')  # 07,08,09,10,13..17,20..24,27

    def test_recesso_suspends(self):
        r = prazos.calcular_prazo('2025-12-18', 5)
        self.assertEqual(r['data_final'], '2026-01-26')  # 19/12 = dia 1; recesso; 21,22,23,26/01

    def test_corridos_prorroga_final(self):
        r = prazos.calcular_prazo('2025-10-06', 5, contagem='corridos')  # termina sáb 11/10 -> seg 13/10
        self.assertEqual(r['data_final'], '2025-10-13')

    def test_easter_and_black_consciousness(self):
        self.assertEqual(prazos.pascoa(2026), date(2026, 4, 5))
        self.assertIn(date(2026, 11, 20), prazos.feriados(2026))
        self.assertIn(date(2026, 4, 3), prazos.feriados(2026))


class OficiaisTests(unittest.TestCase):
    def test_cnj_number_and_alias(self):
        info = oficiais.normalizar_cnj('0001234-55.2023.8.26.0100')
        self.assertEqual(oficiais.alias_tribunal(info), 'tjsp')
        self.assertEqual(oficiais.alias_tribunal(oficiais.normalizar_cnj('00000000000000000000'[:13] + '4030000')), 'trf3')
        with self.assertRaises(ValueError): oficiais.normalizar_cnj('123')
        stf = oficiais.normalizar_cnj('00000000020241000000')
        with self.assertRaises(ValueError): oficiais.alias_tribunal(stf)

    def test_check_digit(self):
        n, ano, j, tr, o = '0001234', '2023', '8', '26', '0100'
        dv = 98 - int(n + ano + j + tr + o + '00') % 97
        ok = oficiais.normalizar_cnj(f'{n}-{dv:02d}.{ano}.{j}.{tr}.{o}')
        self.assertTrue(ok['dv_ok'])
        bad = oficiais.datajud_processo(f'{n}-{(dv + 1) % 100:02d}.{ano}.{j}.{tr}.{o}')
        self.assertEqual(bad['error'], 'digito_verificador_invalido')

    def test_datajud_request_and_parse(self):
        n, ano, j, tr, o = '0001234', '2023', '8', '26', '0100'
        dv = 98 - int(n + ano + j + tr + o + '00') % 97
        seen = {}
        def opener(req, timeout):
            seen.update(url=req.full_url, auth=req.headers.get('Authorization'), body=json.loads(req.data))
            return Fake(json.dumps({'hits': {'hits': [{'_source': {'tribunal': 'TJSP', 'classe': {'nome': 'Procedimento Comum'},
                'movimentos': [{'nome': 'Distribuição', 'dataHora': '2023-01-02T10:00:00'}, {'nome': 'Sentença', 'dataHora': '2024-05-01T10:00:00'}]}}]}}).encode())
        r = oficiais.datajud_processo(f'{n}-{dv:02d}.{ano}.{j}.{tr}.{o}', opener=opener)
        self.assertTrue(seen['url'].endswith('/api_publica_tjsp/_search'))
        self.assertTrue(seen['auth'].startswith('APIKey '))
        self.assertEqual(r['processos'][0]['movimentos_recentes'][0]['movimento'], 'Sentença')

    def test_lexml_query_is_sanitized_and_parsed(self):
        q = oficiais.lexml_query('lei "geral" <x> de proteção de dados', tipo='Lei', ano='2018')
        self.assertNotIn('<', q); self.assertIn('date any "2018"', q)
        xml = b'''<searchRetrieveResponse xmlns="http://www.loc.gov/zing/srw/"><numberOfRecords>1</numberOfRecords><records><record><recordData>
        <srw_dc:dc xmlns:srw_dc="info:srw/schema/1/dc-schema" xmlns:dc="http://purl.org/dc/elements/1.1/"><dc:title>Lei 13.709</dc:title>
        <dc:date>2018-08-14</dc:date><urn>urn:lex:br:federal:lei:2018-08-14;13709</urn></srw_dc:dc></recordData></record></records></searchRetrieveResponse>'''
        r = oficiais.parse_lexml(xml)
        self.assertEqual(r['resultados'][0]['url'], 'https://www.lexml.gov.br/urn/urn:lex:br:federal:lei:2018-08-14;13709')
        with self.assertRaises(oficiais.FonteErro): oficiais.parse_lexml(b'<html>captcha</html>')
        with self.assertRaises(ValueError): oficiais.lexml_query('x', ano='20a8')

    def test_djen_validation(self):
        with self.assertRaises(ValueError): oficiais.djen_comunicacoes()
        with self.assertRaises(ValueError): oficiais.djen_comunicacoes(oab='12345', uf='SPX')
        seen = {}
        def opener(req, timeout):
            seen['url'] = req.full_url
            return Fake(json.dumps({'count': 1, 'items': [{'texto': 'x' * 5000, 'data_disponibilizacao': '2026-09-01'}]}).encode())
        r = oficiais.djen_comunicacoes(oab='123456', uf='sp', data_inicio='2026-09-01', opener=opener)
        self.assertIn('numeroOab=123456', seen['url']); self.assertIn('ufOab=SP', seen['url'])
        self.assertTrue(r['comunicacoes'][0]['texto'].endswith('[truncado]'))


class JurisFrankTests(unittest.TestCase):
    def test_links_are_official_plus_jusbrasil_for_humans(self):
        r = jurisprudencia.links_oficiais('dano moral & bancos')
        hosts = [l['url'] for l in r['links']]
        self.assertTrue(any('stf.jus.br' in h for h in hosts) and any('stj.jus.br' in h for h in hosts))
        self.assertTrue(any('jusbrasil' in l['url'] and 'conferência humana' in l['fonte'] for l in r['links']))
        self.assertIn('dano%20moral%20%26%20bancos', hosts[0])

    def test_tj_validation_and_missing_venv(self):
        with self.assertRaises(ValueError): jurisprudencia.tj_jurisprudencia('tjxx', 'a')
        self.assertEqual(jurisprudencia.tj_jurisprudencia('tjsp', 'dano', python='/nao/existe')['error'], 'juscraper_nao_instalado')

    def test_frank_wraps_cli_and_rejects_bad_urls(self):
        calls = []
        def runner(args, **kw):
            calls.append(args); return types.SimpleNamespace(returncode=2, stdout='{"slug":"abc","state":"pending"}', stderr='')
        with patch.object(Path, 'is_file', return_value=True):
            f = Frank('/root/.hermes', runner=runner)
            r = f.verificar('https://portal.stf.jus.br/x', evidencias=['https://planalto.gov.br/l'])
        self.assertEqual((r['status'], r['frank']['slug']), ('pending', 'abc'))
        self.assertIn('--evidence-url', calls[0])
        with self.assertRaises(ValueError): f.verificar('file:///etc/passwd')
        with self.assertRaises(ValueError): f.relatorio('../x')


class PlanaltoTests(unittest.TestCase):
    PAGE = (b'<html><head><meta charset="windows-1252"><title>L10406</title></head><body>'
            b'<p>Art. 49. Texto qualquer.</p>'
            b'<p><strike>Art. 50. Em caso de abuso da personalidade jur\xeddica (reda\xe7\xe3o antiga)</strike></p>'
            b'<p>Art. 50. Em caso de abuso da personalidade jur\xeddica, caracterizado pelo desvio de finalidade. '
            b'(Reda\xe7\xe3o dada pela Lei n\xba 13.874, de 2019)</p><p>\xa7 1\xba Para os fins...</p>'
            b'<p>Art. 50-A. Artigo inserido.</p><p>Art. 500. Outro.</p></body></html>')

    def test_current_text_without_struck_versions(self):
        seen = {}
        def opener(req, timeout):
            seen['url'] = req.full_url
            return Fake(self.PAGE)
        r = planalto.planalto_artigo('50', norma='CC', opener=opener)
        self.assertTrue(r['encontrado'])
        self.assertIn('desvio de finalidade', r['texto_vigente'])
        self.assertNotIn('antiga', r['texto_vigente'])
        self.assertNotIn('50-A', r['texto_vigente'])
        self.assertIn('Lei nº 13.874, de 2019', r['notas_de_alteracao'][0])
        self.assertIn('l10406compilada', seen['url'])
        r2 = planalto.planalto_artigo('50-A', norma='CC', opener=lambda req, timeout: Fake(self.PAGE))
        self.assertIn('Artigo inserido', r2['texto_vigente'])

    def test_only_planalto_urls(self):
        with self.assertRaises(ValueError): planalto.planalto_artigo('1', url='https://evil.example/x')
        with self.assertRaises(ValueError): planalto.planalto_artigo('1', url='http://www.planalto.gov.br/x')
        with self.assertRaises(ValueError): planalto.planalto_artigo('1', norma='XYZ')


class RegistrationTests(unittest.TestCase):
    def test_only_harvey_gets_tools(self):
        class Ctx:
            def __init__(self): self.tools, self.sections = {}, []
            def get_config(self, k, d=None): return d
            def register_tool(self, **kw): self.tools[kw['name']] = kw
            def register_system_prompt_section(self, *a, **kw): self.sections.append((a, kw))
        for home, expected in (('/root/.hermes/profiles/harvey', 10), ('/root/.hermes', 0), ('/root/.hermes/profiles/bigode', 0)):
            ctx = Ctx()
            with patch.dict(sys.modules, {'hermes_constants': types.SimpleNamespace(get_hermes_home=lambda h=home: h)}):
                register(ctx)
            self.assertEqual(len(ctx.tools), expected, home)
        self.assertLessEqual(len(PROMPT), 2000)

    def test_handler_returns_json_errors(self):
        tools = {}
        register_legal_tools(lambda **kw: tools.__setitem__(kw['name'], kw), ROOT, '/root/.hermes')
        out = json.loads(tools['vademecum_consultar']['handler']({'norma': 'CC', 'artigo': '421'}))
        self.assertEqual(out['resultados'][0]['artigo'], '421')
        err = json.loads(tools['prazo_processual']['handler']({'data_inicial': 'ontem', 'dias': 5}))
        self.assertEqual(err['status'], 'error')


if __name__ == '__main__':
    unittest.main()
