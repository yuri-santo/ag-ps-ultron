import hashlib
import json
from pathlib import Path
import shutil
import tempfile
import unittest

import yaml

import deploy_lab

SOURCE = Path(__file__).resolve().parents[1]


class InstallTests(unittest.TestCase):
    def setUp(self):
        directory = tempfile.TemporaryDirectory()
        self.addCleanup(directory.cleanup)
        self.home = Path(directory.name) / '.hermes'
        (self.home / 'plugins').mkdir(parents=True)
        main = {'model': 'x', 'plugins': {'enabled': ['ultron_team', 'meeting_copilot']},
                'platform_toolsets': {'telegram': ['ultron_team', 'memory'], 'cli': ['ultron_team']}}
        (self.home / 'config.yaml').write_text(yaml.safe_dump(main))
        for name in ('gmail', 'easysapers', 'reunioes'):
            profile = self.home / 'profiles' / name
            profile.mkdir(parents=True)
            domain = 'ultron_meetings' if name == 'reunioes' else 'ultron_mail'
            (profile / 'config.yaml').write_text(yaml.safe_dump({
                'plugins': {'enabled': ['ultron_team']},
                'platform_toolsets': {'telegram': [domain, 'memory'], 'cli': [domain, 'memory']}}))
            (profile / 'SOUL.md').write_text('soul ' + name)
        bigode = self.home / 'profiles' / 'bigode'
        bigode.mkdir()
        (bigode / 'SOUL.md').write_text('bigode')
        (bigode / 'config.yaml').write_text('x: 1\n')

    def run_action(self, action, dry_run=False):
        return deploy_lab.Installer(self.home, SOURCE, dry_run).run(action, 'pc')

    def test_stage_then_activate(self):
        self.run_action('stage')
        plugin = self.home / 'plugins' / 'ultron_lab'
        self.assertTrue((plugin / '__init__.py').is_file())
        self.assertTrue((plugin / deploy_lab.MARK).is_file())
        self.assertFalse((plugin / '__pycache__').exists())
        for name in ('gmail', 'easysapers'):
            self.assertTrue((self.home / 'profiles' / name / 'plugins' / 'ultron_lab' / 'mailcheck.py').is_file())
        self.assertFalse((self.home / 'profiles' / 'reunioes' / 'plugins' / 'ultron_lab').exists())
        skills = sorted(p.name for p in (self.home / 'skills' / 'ultron-lab').iterdir())
        self.assertEqual(skills, ['analise-golpe', 'checar-noticia', 'homelab-ops', 'memoria-projetos', 'midia-gpu'])
        inventory = self.home / 'ultron_lab' / 'homelab.json'
        self.assertIn('ai-memory', inventory.read_text(encoding='utf-8'))
        self.assertEqual(inventory.stat().st_mode & 0o777, 0o600)
        main_before = (self.home / 'config.yaml').read_text()
        self.run_action('activate')
        self.assertNotEqual(main_before, (self.home / 'config.yaml').read_text())
        main = yaml.safe_load((self.home / 'config.yaml').read_text())
        self.assertIn('ultron_lab', main['plugins']['enabled'])
        self.assertIn('ultron_team', main['plugins']['enabled'])
        self.assertEqual(main['plugins']['entries']['ultron_lab']['settings']['homelab_inventory'], str(inventory))
        self.assertTrue(all('ultron_lab' in v for v in main['platform_toolsets'].values()))
        gmail = yaml.safe_load((self.home / 'profiles' / 'gmail' / 'config.yaml').read_text())
        self.assertIn('ultron_lab', gmail['plugins']['enabled'])
        self.assertTrue(all('ultron_lab_mail' in v for v in gmail['platform_toolsets'].values()))
        reunioes = yaml.safe_load((self.home / 'profiles' / 'reunioes' / 'config.yaml').read_text())
        self.assertNotIn('ultron_lab', reunioes['plugins']['enabled'])
        backups = sorted((self.home / 'backups').iterdir())
        manifest = json.loads((backups[-1] / 'manifest.json').read_text())
        self.assertIn(str(self.home / 'config.yaml'), manifest['changed'])
        self.assertTrue((backups[-1] / 'config.yaml').is_file())

    def test_activate_is_idempotent_and_requires_stage(self):
        with self.assertRaises(RuntimeError):
            self.run_action('activate')
        self.run_action('stage')
        self.run_action('activate')
        once = (self.home / 'config.yaml').read_text()
        self.run_action('stage')
        self.run_action('activate')
        self.assertEqual(once, (self.home / 'config.yaml').read_text())

    def test_other_profiles_untouched(self):
        digest = hashlib.sha256((self.home / 'profiles' / 'bigode' / 'SOUL.md').read_bytes()).hexdigest()
        self.run_action('stage')
        self.run_action('activate')
        self.assertEqual(digest, hashlib.sha256((self.home / 'profiles' / 'bigode' / 'SOUL.md').read_bytes()).hexdigest())

    def test_refuses_unmanaged_destination(self):
        (self.home / 'plugins' / 'ultron_lab').mkdir()
        (self.home / 'plugins' / 'ultron_lab' / 'meu.py').write_text('x')
        with self.assertRaises(RuntimeError):
            self.run_action('stage')
        self.assertTrue((self.home / 'plugins' / 'ultron_lab' / 'meu.py').is_file())

    def test_dry_run_writes_nothing(self):
        before = sorted(str(p) for p in self.home.rglob('*'))
        manifest = self.run_action('stage', dry_run=True)
        self.assertTrue(manifest['planned'])
        self.assertEqual(before, sorted(str(p) for p in self.home.rglob('*')))

    def test_missing_mail_profiles_move_check_to_main_ultron(self):
        for name in ('gmail', 'easysapers'):
            shutil.rmtree(self.home / 'profiles' / name)
        accounts = self.home / 'skills' / 'email-manager' / 'scripts' / 'accounts.json'
        accounts.parent.mkdir(parents=True)
        accounts.write_text('{}')
        manifest = self.run_action('stage')
        self.assertEqual(manifest['perfis_email'], [])
        self.assertEqual(manifest['email_no_principal'], ['gmail', 'easysapers'])
        self.run_action('activate')
        main = yaml.safe_load((self.home / 'config.yaml').read_text())
        self.assertEqual(main['plugins']['entries']['ultron_lab']['settings']['mail_fraud_contas'],
                         ['gmail', 'easysapers'])

    def test_without_profiles_or_accounts_mail_check_is_skipped(self):
        for name in ('gmail', 'easysapers'):
            shutil.rmtree(self.home / 'profiles' / name)
        self.run_action('stage')
        self.run_action('activate')
        main = yaml.safe_load((self.home / 'config.yaml').read_text())
        self.assertNotIn('mail_fraud_contas', main['plugins']['entries']['ultron_lab']['settings'])

    def test_existing_inventory_is_preserved(self):
        inventory = self.home / 'ultron_lab' / 'homelab.json'
        inventory.parent.mkdir()
        inventory.write_text('{"servicos": [{"nome": "meu", "url": "http://h/"}]}')
        self.run_action('stage')
        self.assertIn('"meu"', inventory.read_text())


if __name__ == '__main__':
    unittest.main()
