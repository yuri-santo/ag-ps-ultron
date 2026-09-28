from contextlib import contextmanager
import json
from pathlib import Path
import tempfile
import unittest

from ultron_lab import homelab, monitor

GOLPE = (b'Received: from x (unknown [45.67.89.10]) by mx\r\n'
         b'Authentication-Results: mx; spf=fail; dkim=none; dmarc=fail\r\n'
         b'From: "Banco Itau" <alerta@itau-seguranca.xyz>\r\nSubject: URGENTE conta bloqueada\r\n\r\n'
         b'Sua conta sera bloqueada em ate 24 horas. Clique aqui e confirme seus dados: http://45.67.89.10/x\r\n')
NORMAL = (b'Received: from y by mx\r\nAuthentication-Results: mx; spf=pass; dkim=pass; dmarc=pass\r\n'
          b'From: Maria <maria@empresa.com>\r\nSubject: Pauta\r\n\r\nSegue a pauta da reuniao de quinta.\r\n')


class FakeImap:
    def __init__(self, messages):
        self.messages = messages

    def uid(self, command, uid, spec):
        raw = self.messages[uid]
        if 'RFC822.SIZE' in spec:
            return 'OK', [f'1 (UID {uid} RFC822.SIZE {len(raw)})'.encode()]
        return 'OK', [(b'1 (BODY[]', raw), b')']


class FakeTools:
    def __init__(self, messages, validity='7'):
        self.messages, self.validity, self.account = messages, validity, 'gmail'

    def list_messages(self, limit=10):
        items = [{'uid': uid, 'from': 'x', 'subject': 'assunto ' + uid} for uid in sorted(self.messages, reverse=True)]
        return {'status': 'ok', 'uidvalidity': self.validity, 'messages': items[:limit]}

    @contextmanager
    def _mail(self):
        yield FakeImap(self.messages), len(self.messages), self.validity


class FakeTelegram:
    def __init__(self):
        self.sent = []

    def send(self, text):
        self.sent.append(text)
        return True


class MonitorTests(unittest.TestCase):
    def setUp(self):
        directory = tempfile.TemporaryDirectory()
        self.addCleanup(directory.cleanup)
        self.base = Path(directory.name)

    def test_homelab_alerts_after_two_failures_and_on_recovery(self):
        sequence = iter([False, False, False, True, True])
        def status_fn(_):
            ok = next(sequence)
            return {'servicos': [{'nome': 'ai-memory', 'status': 'ok' if ok else 'falha', 'critico': True,
                                  **({} if ok else {'erro': 'ConnectionRefusedError'})}]}
        state, outputs = {}, []
        for _ in range(5):
            outputs.append(monitor.check_homelab('x', state, status_fn))
        self.assertEqual(outputs[0], [])
        self.assertIn('ai-memory (crítico)', outputs[1][0])
        self.assertEqual(outputs[2], [])
        self.assertIn('voltou', outputs[3][0])
        self.assertEqual(outputs[4], [])

    def test_services_marked_no_alert_never_alert(self):
        down = lambda _: {'servicos': [{'nome': 'lm-studio', 'status': 'falha', 'critico': False, 'alertar': False}]}
        state = {}
        self.assertEqual([monitor.check_homelab('x', state, down) for _ in range(3)], [[], [], []])

    def test_email_baseline_then_alerts_only_new_scams(self):
        tools = FakeTools({'10': NORMAL, '11': GOLPE})
        state = {}
        found, errors = monitor.check_email(['gmail'], state, self.base, lambda conta: tools)
        self.assertEqual((found, errors), ([], []))
        tools.messages.update({'12': GOLPE, '13': NORMAL})
        found, errors = monitor.check_email(['gmail'], state, self.base, lambda conta: tools)
        self.assertEqual(errors, [])
        self.assertEqual(len(found), 1)
        self.assertIn('Gmail', found[0])
        self.assertIn('mail_fraud_check gmail 12', found[0])
        self.assertNotIn('http://45.67', found[0])
        found, _ = monitor.check_email(['gmail'], state, self.base, lambda conta: tools)
        self.assertEqual(found, [])

    def test_uidvalidity_change_resets_baseline(self):
        tools = FakeTools({'1': NORMAL})
        state = {}
        monitor.check_email(['gmail'], state, self.base, lambda conta: tools)
        tools.validity = '8'
        tools.messages['2'] = GOLPE
        found, _ = monitor.check_email(['gmail'], state, self.base, lambda conta: tools)
        self.assertEqual(found, [])

    def test_run_is_silent_when_everything_is_fine_and_persists_state(self):
        telegram = FakeTelegram()
        settings = {'homelab_inventory': str(self.base / 'inv.json')}
        ok = lambda _: {'servicos': [{'nome': 'a', 'status': 'ok', 'critico': False}]}
        summary = monitor.run('homelab', self.base, telegram=telegram, status_fn=ok, settings=settings)
        self.assertEqual((summary['alertas'], telegram.sent), ([], []))
        self.assertTrue((self.base / 'ultron_lab' / 'monitor_estado.json').is_file())

    def test_run_sends_alerts_and_dry_run_does_not(self):
        settings = {'homelab_inventory': 'x'}
        down = lambda _: {'servicos': [{'nome': 'a', 'status': 'falha', 'critico': True}]}
        telegram = FakeTelegram()
        monitor.run('homelab', self.base, telegram=telegram, status_fn=down, settings=settings)
        summary = monitor.run('homelab', self.base, telegram=telegram, status_fn=down, settings=settings)
        self.assertEqual(summary['enviados'], 1)
        self.assertEqual(len(telegram.sent), 1)
        (self.base / 'ultron_lab' / 'monitor_estado.json').unlink()
        dry = FakeTelegram()
        monitor.run('homelab', self.base, telegram=dry, status_fn=down, settings=settings, dry_run=True)
        summary = monitor.run('homelab', self.base, telegram=dry, status_fn=down, settings=settings, dry_run=True)
        self.assertEqual((summary['enviados'], dry.sent), (0, []))
        self.assertEqual(len(summary['alertas']), 1)

    def test_missing_inventory_is_reported_not_raised(self):
        summary = monitor.run('homelab', self.base, telegram=FakeTelegram(), settings={
            'homelab_inventory': str(self.base / 'nao-existe.json')})
        self.assertIn('homelab: inventario_ausente', summary['erros'])

    def test_telegram_config_from_env_file(self):
        (self.base / '.env').write_text('TELEGRAM_BOT_TOKEN="123:abc"\nTELEGRAM_ALLOWED_USERS=777, 888\n')
        telegram = monitor.telegram_from_env(self.base, environ={})
        self.assertEqual((telegram.token, telegram.chat), ('123:abc', '777'))
        (self.base / '.env').write_text('TELEGRAM_BOT_TOKEN=1\nTELEGRAM_HOME_CHANNEL=-100\nTELEGRAM_ALLOWED_USERS=777\n')
        self.assertEqual(monitor.telegram_from_env(self.base, environ={}).chat, '-100')
        (self.base / '.env').write_text('')
        self.assertIsNone(monitor.telegram_from_env(self.base, environ={}))

    def test_any_response_mode_for_services_without_health_route(self):
        path = self.base / 'inv.json'
        path.write_text(json.dumps({'servicos': [{'nome': 'rag', 'url': 'http://h/', 'esperado': 'qualquer'}]}))
        service = homelab.load_inventory(path)[0]
        self.assertIn(404, service['esperado'])
        self.assertNotIn(502, service['esperado'])


if __name__ == '__main__':
    unittest.main()
