from contextlib import contextmanager
import json
import sys
from types import SimpleNamespace
import unittest
from unittest.mock import patch

from ultron_lab import mailcheck, register


class Context:
    def __init__(self, config=None):
        self.tools, self.hooks, self.sections = {}, {}, []
        self.config = config or {}

    def get_config(self, key, default=None):
        return self.config.get(key, default)

    def register_tool(self, **kwargs):
        self.tools[kwargs['name']] = kwargs

    def register_hook(self, name, callback):
        self.hooks[name] = callback

    def register_system_prompt_section(self, *args, **kwargs):
        self.sections.append(kwargs)


def context(home, config=None):
    ctx = Context(config)
    with patch.dict(sys.modules, {'hermes_constants': SimpleNamespace(get_hermes_home=lambda: home)}):
        register(ctx)
    return ctx


class FakeIMAP:
    def __init__(self, raw, size=None, status='OK'):
        self.raw, self.size, self.status, self.calls = raw, size, status, []

    def uid(self, command, uid, spec):
        self.calls.append(spec)
        if 'RFC822.SIZE' in spec:
            return self.status, [f'1 (UID {uid} RFC822.SIZE {self.size or len(self.raw)})'.encode()]
        return self.status, [(f'1 (UID {uid} BODY[]'.encode(), self.raw), b')']


class FakeMailTools:
    account = 'gmail'

    def __init__(self, imap):
        self.imap = imap

    @contextmanager
    def _mail(self):
        yield self.imap, 10, '123'


class PluginTests(unittest.TestCase):
    def test_main_home_registers_lab_tools_and_short_prompt(self):
        ctx = context('/root/.hermes')
        self.assertEqual(set(ctx.tools), {'ultron_golpe', 'ultron_homelab'})
        self.assertTrue(all(tool['toolset'] == 'ultron_lab' for tool in ctx.tools.values()))
        self.assertEqual(len(ctx.sections), 1)
        self.assertLessEqual(ctx.sections[0]['max_chars'], 4000)
        from ultron_lab import PROMPT
        self.assertLessEqual(len(PROMPT), ctx.sections[0]['max_chars'])

    def test_mail_profiles_only_get_fraud_check(self):
        for profile in ('gmail', 'easysapers'):
            ctx = context(f'/root/.hermes/profiles/{profile}')
            self.assertEqual(set(ctx.tools), {'mail_fraud_check'})
            self.assertEqual(ctx.tools['mail_fraud_check']['toolset'], 'ultron_lab_mail')
            self.assertEqual(ctx.sections, [])

    def test_main_gets_mail_check_when_profiles_are_absent(self):
        ctx = context('/root/.hermes', {'mail_fraud_contas': ['gmail', 'easysapers', 'invalida']})
        self.assertIn('mail_fraud_check', ctx.tools)
        schema = ctx.tools['mail_fraud_check']['schema']
        self.assertEqual(schema['parameters']['properties']['conta']['enum'], ['gmail', 'easysapers'])
        result = json.loads(ctx.tools['mail_fraud_check']['handler']({'conta': 'outra', 'uid': '1'}))
        self.assertEqual(result['error'], 'conta_invalida')

    def test_other_profiles_get_nothing(self):
        for home in ('/root/.hermes/profiles/reunioes', '/root/.hermes/profiles/bigode', '/tmp/outro'):
            self.assertEqual(context(home).tools, {})

    def test_golpe_handler_returns_json_and_validates(self):
        handler = context('/root/.hermes').tools['ultron_golpe']['handler']
        result = json.loads(handler({'texto': 'mudei de número, me faz um pix agora'}))
        self.assertEqual(result['status'], 'ok')
        self.assertEqual(json.loads(handler({'texto': ''}))['error'], 'texto_invalido')
        self.assertEqual(json.loads(handler({'texto': 'x' * 200001}))['error'], 'texto_invalido')

    def test_homelab_handler_reports_missing_inventory(self):
        ctx = context('/root/.hermes', {'homelab_inventory': '/nao/existe.json'})
        result = json.loads(ctx.tools['ultron_homelab']['handler']({}))
        self.assertEqual(result['error'], 'inventario_ausente')
        self.assertEqual(json.loads(ctx.tools['ultron_homelab']['handler']({'grupo': 'x' * 41}))['error'],
                         'filtro_invalido')


class ResolveProfileTests(unittest.TestCase):
    def test_local_profile_names_are_resolved_by_account_type(self):
        local = {'cris': ('workmail', 'voce@empresa.com'), 'greg': ('gmail', 'voce@gmail.com')}
        self.assertEqual(mailcheck.resolve_profile('gmail', local), 'greg')
        self.assertEqual(mailcheck.resolve_profile('easysapers', local), 'cris')
        vps = {'gmail': ('gmail', 'x'), 'easysapers': ('workmail', 'y')}
        self.assertEqual(mailcheck.resolve_profile('gmail', vps), 'gmail')
        self.assertEqual(mailcheck.resolve_profile('outra', local), 'outra')


class MailCheckTests(unittest.TestCase):
    RAW = (b'Received: from x by y\r\nAuthentication-Results: mx; spf=pass; dkim=pass; dmarc=pass\r\n'
           b'From: Maria <maria@empresa.com>\r\nSubject: Pauta\r\n\r\nSegue a pauta da reuniao.\r\n')

    def test_fetch_is_peek_and_analysis_includes_uid(self):
        imap = FakeIMAP(self.RAW)
        result = mailcheck.check_uid('gmail', '/root/.hermes', '/root/.hermes/profiles/gmail', '42',
                                     mail_tools=FakeMailTools(imap))
        self.assertEqual(result['status'], 'ok')
        self.assertEqual(result['uid'], '42')
        self.assertEqual(result['uidvalidity'], '123')
        self.assertTrue(any('BODY.PEEK[]' in call for call in imap.calls))
        self.assertFalse(any('RFC822)' in call or call == '(RFC822)' for call in imap.calls))

    def test_invalid_uid_and_size_limits(self):
        tools = FakeMailTools(FakeIMAP(self.RAW))
        for uid in ('0', 'abc', '1 OR 2', True, '99999999999'):
            self.assertEqual(mailcheck.check_uid('gmail', '/b', '/h', uid, mail_tools=tools)['error'], 'uid_invalido')
        big = FakeMailTools(FakeIMAP(self.RAW, size=mailcheck.MAX_MESSAGE + 1))
        self.assertEqual(mailcheck.check_uid('gmail', '/b', '/h', '1', mail_tools=big)['error'],
                         'mensagem_grande_demais')
        missing = FakeMailTools(FakeIMAP(self.RAW, status='NO'))
        self.assertEqual(mailcheck.check_uid('gmail', '/b', '/h', '1', mail_tools=missing)['error'],
                         'mensagem_nao_encontrada')

    def test_unexpected_errors_do_not_leak_details(self):
        class Broken(FakeMailTools):
            @contextmanager
            def _mail(self):
                raise OSError('senha=abc123 host=imap')
                yield
        result = mailcheck.check_uid('gmail', '/b', '/h', '1', mail_tools=Broken(None))
        self.assertEqual(result, {'status': 'error', 'error': 'mail_indisponivel'})


if __name__ == '__main__':
    unittest.main()


try:
    from ultron_team.mail_tools import MailTools as RealMailTools
except ImportError:  # pragma: no cover - ultron_team mora no mesmo repositório
    RealMailTools = None


@unittest.skipIf(RealMailTools is None, 'ultron_team não disponível')
class RealMailToolsIntegration(unittest.TestCase):
    def test_check_uid_with_real_mail_tools_is_readonly(self):
        import tempfile
        from pathlib import Path
        raw = MailCheckTests.RAW
        state = {}

        class Server(FakeIMAP):
            def login(self, user, password):
                state['login'] = user

            def select(self, box, readonly=False):
                state['readonly'] = readonly
                return 'OK', [b'10']

            def response(self, name):
                return 'OK', [b'777']

            def logout(self):
                state['logout'] = True

        server = Server(raw)
        with tempfile.TemporaryDirectory() as directory:
            accounts = Path(directory) / 'accounts.json'
            accounts.write_text(json.dumps({'gmail': {'email': 'voce@gmail.com', 'password': 'x',
                                                      'imap_host': 'imap.example.com'}}))
            tools = RealMailTools('gmail', accounts, Path(directory), imap_factory=lambda *a, **k: server)
            result = mailcheck.check_uid('gmail', directory, directory, '7', mail_tools=tools)
        self.assertEqual(result['status'], 'ok')
        self.assertEqual(result['uidvalidity'], '777')
        self.assertTrue(state['readonly'])
        self.assertTrue(state['logout'])
        self.assertTrue(all('PEEK' in call or 'SIZE' in call for call in server.calls))
