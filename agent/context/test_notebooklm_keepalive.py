from pathlib import Path
import subprocess
import tempfile
import unittest
from notebooklm_keepalive import refresh


class KeepaliveTests(unittest.TestCase):
    def test_success_is_silent_and_private(self):
        with tempfile.TemporaryDirectory() as d:
            state = Path(d) / 'state.json'
            def runner(*args, **kwargs):
                self.assertIn('auth', args[0])
                self.assertIn('refresh', args[0])
                self.assertEqual(kwargs['timeout'], 90)
                self.assertNotIn('NOTEBOOKLM_AUTH_JSON', kwargs['env'])
                return subprocess.CompletedProcess(args[0], 0, '', '')
            self.assertEqual(refresh(state, runner), '')
            self.assertEqual(state.stat().st_mode & 0o777, 0o600)

    def test_only_transitions_notify_and_no_provider_output_leaks(self):
        with tempfile.TemporaryDirectory() as d:
            state = Path(d) / 'state.json'
            failure = lambda *a, **kw: subprocess.CompletedProcess(a[0], 1, 'secret-value', 'secret-error')
            first = refresh(state, failure)
            self.assertIn('Ultron:', first)
            self.assertNotIn('secret', first)
            self.assertEqual(refresh(state, failure), '')
            success = lambda *a, **kw: subprocess.CompletedProcess(a[0], 0, '', '')
            self.assertIn('restabelecida', refresh(state, success))
            self.assertEqual(refresh(state, success), '')

    def test_timeout_becomes_a_safe_notification(self):
        with tempfile.TemporaryDirectory() as d:
            def runner(*a, **kw):
                raise subprocess.TimeoutExpired('notebooklm', 90)
            self.assertNotIn('Traceback', refresh(Path(d) / 'state.json', runner))


if __name__ == '__main__':
    unittest.main()
