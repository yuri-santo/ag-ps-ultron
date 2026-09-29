import copy
from pathlib import Path
import tempfile
import unittest

from repair_fallbacks import repaired_config, update_file


class FallbackConfigTests(unittest.TestCase):
    def setUp(self):
        self.config = {'model': {'default': 'hermes-reasoning', 'base_url': 'http://localhost:20130/v1',
                                 'api_key': 'fixture-not-a-secret'},
                       'fallback_providers': [
                           {'model': 'hermes-fast', 'base_url': 'http://localhost:20130/v1',
                            'api_key': 'fixture-not-a-secret', 'provider': 'custom'},
                           {'model': 'dead', 'base_url': 'https://api.xkiro.com/v1',
                            'api_key': 'fixture-other', 'provider': 'custom'}],
                       'personality': {'sentinel': 'unchanged'}, 'plugins': {'enabled': ['example']}}

    def test_verified_routes_replace_failed_host_without_changing_personality(self):
        before = copy.deepcopy(self.config)
        updated = repaired_config(self.config, ['openrouter/openrouter/free', 'qd/efficient'], ['api.xkiro.com'])
        self.assertEqual([r['model'] for r in updated['fallback_providers']],
                         ['hermes-fast', 'openrouter/openrouter/free', 'qd/efficient'])
        self.assertEqual(updated['personality'], before['personality'])
        self.assertEqual(updated['plugins'], before['plugins'])
        self.assertEqual(self.config, before)

    def test_idempotence_duplicates_and_self_fallback(self):
        self.config['fallback_providers'].insert(0, dict(self.config['fallback_providers'][0],
            model='hermes-reasoning', base_url='http://127.0.0.1:20130/v1'))
        models = ['hermes-fast', 'hermes-fast', 'openrouter/openrouter/free', 'hermes-reasoning']
        once = repaired_config(self.config, models, ['api.xkiro.com'])
        self.assertEqual([r['model'] for r in once['fallback_providers']], ['hermes-fast', 'openrouter/openrouter/free'])
        self.assertEqual(once, repaired_config(once, models, ['api.xkiro.com']))

    def test_verified_routes_follow_requested_order(self):
        self.config['fallback_providers'].append(dict(self.config['fallback_providers'][0], model='slow'))
        result = repaired_config(self.config, ['fast', 'slow'], ['api.xkiro.com'])
        self.assertEqual([r['model'] for r in result['fallback_providers']], ['hermes-fast', 'fast', 'slow'])

    def test_dry_run_and_atomic_update_preserve_backup(self):
        import yaml
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / 'config.yaml'
            original = yaml.safe_dump(self.config).encode()
            path.write_bytes(original)
            args = (path, ['openrouter/openrouter/free'], ['api.xkiro.com'])
            self.assertFalse(update_file(*args)['applied'])
            self.assertEqual(path.read_bytes(), original)
            self.assertTrue(update_file(*args, apply=True)['applied'])
            backups = list(Path(directory).glob('*.bak-ultron-fallback-*'))
            self.assertEqual(len(backups), 1)
            self.assertEqual(backups[0].read_bytes(), original)
            self.assertFalse(update_file(*args, apply=True)['changed'])

    def test_other_providers_are_preserved(self):
        updated = repaired_config(self.config, ['openrouter/openrouter/free'], [])
        self.assertIn('dead', [r['model'] for r in updated['fallback_providers']])

    def test_refuses_nonlocal_primary_or_missing_key(self):
        for change in ({'base_url': 'https://example.com/v1'}, {'api_key': ''}):
            self.config['model'].update(change)
            with self.assertRaises(ValueError):
                repaired_config(self.config, ['openrouter/openrouter/free'], [])


if __name__ == '__main__':
    unittest.main()
