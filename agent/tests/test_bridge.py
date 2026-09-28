import json
import os
from pathlib import Path
import subprocess
import tempfile
import unittest

try:
    from ultron_team.bridge import Bridge
except ImportError:
    Bridge = None


class BridgeTests(unittest.TestCase):
    def setUp(self):
        self.assertIsNotNone(Bridge, 'Profile bridge has not been implemented')
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name)
        for name in ('gmail', 'easysapers', 'reunioes'):
            directory = self.root / 'profiles' / name
            directory.mkdir(parents=True)
            (directory / 'SOUL.md').write_text(name, encoding='utf-8')
            (directory / 'config.yaml').write_text('{}', encoding='utf-8')
        self.calls = []

    def runner(self, argv, **kwargs):
        self.calls.append((argv, kwargs))
        profile = Path(kwargs['env']['HERMES_HOME']).name
        request = json.loads(kwargs['input'])
        payload = {'status': 'ok', 'profile': profile, 'answer': request['task'],
                   'session_id': 'synthetic-session', 'failed': False}
        return subprocess.CompletedProcess(argv, 0, json.dumps(payload), '')

    def test_profile_home_and_stdin_are_isolated(self):
        before = dict(os.environ)
        task = 'Veja $(segredo); "aspas" e `codigo`\nsegunda linha'
        result = Bridge(self.root, runner=self.runner).dispatch('gmail', task)
        self.assertEqual(result['answer'], task)
        argv, options = self.calls[0]
        self.assertNotIn(task, argv)
        self.assertFalse(options.get('shell', False))
        self.assertEqual(Path(options['env']['HERMES_HOME']), self.root / 'profiles/gmail')
        self.assertEqual(options['env']['ULTRON_PROFILE'], 'gmail')
        self.assertEqual(dict(os.environ), before)

    def test_unknown_profile_never_spawns(self):
        bridge = Bridge(self.root, runner=self.runner)
        for name in ('../default', 'bigode', '', '/root', 'gmail;echo'):
            with self.subTest(name=name):
                self.assertEqual(bridge.dispatch(name, 'oi')['status'], 'error')
        self.assertEqual(self.calls, [])

    def test_distinct_profile_homes(self):
        bridge = Bridge(self.root, runner=self.runner)
        for name in ('gmail', 'easysapers', 'reunioes'):
            self.assertEqual(bridge.dispatch(name, 'oi')['profile'], name)
        homes = {kwargs['env']['HERMES_HOME'] for _, kwargs in self.calls}
        self.assertEqual(len(homes), 3)

    def test_wrong_worker_identity_is_rejected(self):
        def wrong(argv, **kwargs):
            return subprocess.CompletedProcess(argv, 0, '{"status":"ok","profile":"thor","answer":"oi"}', '')
        result = Bridge(self.root, runner=wrong).dispatch('gmail', 'oi')
        self.assertEqual(result['error'], 'worker_identity_mismatch')

    def test_failed_worker_cannot_report_success(self):
        def failed(argv, **kwargs):
            return subprocess.CompletedProcess(argv, 0, '{"status":"ok","profile":"gmail","failed":true,"answer":"parcial"}', '')
        self.assertEqual(Bridge(self.root, runner=failed).dispatch('gmail', 'oi')['status'], 'error')

    def test_timeout_and_stderr_are_sanitized(self):
        def timeout(argv, **kwargs):
            raise subprocess.TimeoutExpired(argv, 1, output='password=SECRET')
        result = Bridge(self.root, runner=timeout).dispatch('gmail', 'oi')
        self.assertEqual(result['error'], 'worker_timeout')
        self.assertNotIn('SECRET', json.dumps(result))

    def test_missing_profile_fails_without_fallback_to_default(self):
        (self.root / 'profiles/gmail/config.yaml').unlink()
        result = Bridge(self.root, runner=self.runner).dispatch('gmail', 'oi')
        self.assertEqual(result['error'], 'profile_not_installed')
        self.assertEqual(self.calls, [])


if __name__ == '__main__':
    unittest.main()
